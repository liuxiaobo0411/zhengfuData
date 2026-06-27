from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import (
    Announcement,
    Attachment,
    AttachmentVersion,
    ChangeLog,
    CrawlRun,
    Site,
    SiteSection,
)
from app.services.crawler.http import add_query_params, fetch_browser_rendered_page, fetch_url
from app.services.crawler.parser import (
    extract_unitbuild_requests,
    parse_date_text,
    parse_detail_page,
    parse_json_page,
    parse_list_page,
    parse_unitbuild_html,
)
from app.services.crawler.types import FetchedPage, ParsedAnnouncement, ParsedAttachment
from app.services.path_utils import safe_filename
from app.services.storage import prepare_storage


def crawl_section(
    db: Session,
    section_id: int,
    triggered_by: str = "manual",
    settings: Settings | None = None,
) -> CrawlRun:
    settings = settings or get_settings()
    storage = prepare_storage(settings)
    section = db.get(SiteSection, section_id)
    if section is None:
        raise ValueError(f"site section not found: {section_id}")
    site = db.get(Site, section.site_id)
    if site is None:
        raise ValueError(f"site not found: {section.site_id}")

    running_run = find_running_section_run(db, section.id)
    if running_run is not None:
        section.last_status = "running"
        section.last_error = f"已有抓取任务运行中: {running_run.run_no}"
        db.commit()
        db.refresh(running_run)
        return running_run

    now = datetime.now()
    run_type = run_type_for(triggered_by)
    run = CrawlRun(
        run_no=f"{run_type}-{now.strftime('%Y%m%d%H%M%S%f')}-{section.id}",
        run_type=run_type,
        status="running",
        started_at=now,
        total_sections=1,
        triggered_by=triggered_by,
    )
    db.add(run)
    db.flush()

    try:
        if section.crawler_strategy in {"custom_adapter", "manual_import"}:
            raise RuntimeError(f"当前策略暂未接入自动抓取: {section.crawler_strategy}")
        page = fetch_page_for_section(section.url, section)
        if section.crawler_strategy == "json_api":
            records = parse_json_page(page.text, page.final_url, section)
        else:
            records = parse_listing_records(page, section)
        run.discovered_items = len(records)
        new_items = 0
        content_changed_items = 0
        attachment_added = 0
        attachment_changed = 0
        attachment_success = 0
        attachment_failed = 0
        for record in records:
            result = save_record(db, site, section, run, record, storage.root, settings)
            new_items += int(result["is_new"])
            content_changed_items += int(result["content_changed"])
            attachment_added += result["attachment_added"]
            attachment_changed += result["attachment_changed"]
            attachment_success += result["attachment_success"]
            attachment_failed += result["attachment_failed"]

        run.status = "partial_success" if attachment_failed else "success"
        run.success_sections = 1
        run.new_items = new_items
        run.content_changed_items = content_changed_items
        run.attachment_added_count = attachment_added
        run.attachment_changed_count = attachment_changed
        run.attachment_success_count = attachment_success
        run.attachment_failed_count = attachment_failed
        run.finished_at = datetime.now()
        run.duration_seconds = int((run.finished_at - run.started_at).total_seconds())
        section.last_status = run.status
        section.last_crawled_at = run.finished_at
        section.last_error = None
        site.last_status = run.status
        site.last_crawled_at = run.finished_at
    except Exception as exc:
        run.status = "failed"
        run.failed_sections = 1
        run.error_summary = f"{type(exc).__name__}: {exc}"
        run.finished_at = datetime.now()
        run.duration_seconds = int((run.finished_at - run.started_at).total_seconds())
        section.last_status = "failed"
        section.last_crawled_at = run.finished_at
        section.last_error = run.error_summary
        site.last_status = "failed"
        site.last_crawled_at = run.finished_at
        db.add(
            ChangeLog(
                site_id=site.id,
                section_id=section.id,
                run_id=run.id,
                change_type="crawl_failed",
                title=section.name,
                summary=run.error_summary,
                source_url=section.url,
            )
        )
    db.commit()
    db.refresh(run)
    return run


def find_running_section_run(db: Session, section_id: int) -> CrawlRun | None:
    return db.scalar(
        select(CrawlRun)
        .where(CrawlRun.status == "running")
        .where(CrawlRun.run_no.like(f"%-{section_id}"))
        .order_by(CrawlRun.started_at.desc(), CrawlRun.id.desc())
    )


def mark_stale_running_runs(
    db: Session,
    timeout_minutes: int,
    now: datetime | None = None,
) -> int:
    threshold = (now or datetime.now()) - timedelta(minutes=max(1, timeout_minutes))
    runs = list(
        db.scalars(
            select(CrawlRun)
            .where(CrawlRun.status == "running")
            .where(CrawlRun.started_at.is_not(None))
            .where(CrawlRun.started_at < threshold)
        ).all()
    )
    finished_at = now or datetime.now()
    for run in runs:
        run.status = "failed"
        run.failed_sections = run.failed_sections or run.total_sections or 1
        run.finished_at = finished_at
        if run.started_at:
            run.duration_seconds = int((finished_at - run.started_at).total_seconds())
        run.error_summary = "应用启动时检测到任务长时间处于 running，已标记为异常中断"
    if runs:
        db.commit()
    return len(runs)


def retry_attachment_download(
    db: Session,
    attachment_id: int,
    triggered_by: str = "manual",
    settings: Settings | None = None,
) -> Attachment | None:
    settings = settings or get_settings()
    storage = prepare_storage(settings)
    attachment = db.get(Attachment, attachment_id)
    if attachment is None:
        return None

    announcement = db.get(Announcement, attachment.announcement_id)
    if announcement is None:
        return None
    site = db.get(Site, attachment.site_id)
    section = db.get(SiteSection, announcement.section_id)
    if site is None or section is None:
        return None

    now = datetime.now()
    run_type = run_type_for(triggered_by)
    run = CrawlRun(
        run_no=f"{run_type}-attachment-{now.strftime('%Y%m%d%H%M%S%f')}-{attachment.id}",
        run_type=run_type,
        status="running",
        started_at=now,
        total_sections=1,
        triggered_by=triggered_by,
    )
    db.add(run)
    db.flush()

    result = save_attachment(
        db,
        site,
        announcement,
        run,
        ParsedAttachment(name=attachment.name, url=attachment.source_url),
        section,
        storage.root,
        settings,
    )
    run.status = "success" if result["success"] else "failed"
    run.success_sections = 1 if result["success"] else 0
    run.failed_sections = 0 if result["success"] else 1
    run.attachment_success_count = 1 if result["success"] else 0
    run.attachment_failed_count = 0 if result["success"] else 1
    run.attachment_changed_count = int(result["changed"])
    if not result["success"]:
        run.error_summary = attachment.failure_reason
    run.finished_at = datetime.now()
    run.duration_seconds = int((run.finished_at - run.started_at).total_seconds())
    db.commit()
    db.refresh(attachment)
    return attachment


def run_type_for(triggered_by: str) -> str:
    if triggered_by in {"scheduled", "cli_daily"}:
        return "scheduled"
    return "manual"


def parse_listing_records(page: FetchedPage, section: SiteSection) -> list[ParsedAnnouncement]:
    records = parse_list_page(page.text, page.final_url, section)
    for endpoint, params in extract_unitbuild_requests(page.text, page.final_url):
        params = {
            **params,
            "paramJson": f'{{"pageNo":1,"pageSize":{section.max_items_per_run}}}',
        }
        fragment_page = fetch_url(add_query_params(endpoint, params), section)
        fragment_html = parse_unitbuild_html(fragment_page.text)
        if fragment_html:
            records.extend(parse_list_page(fragment_html, page.final_url, section))
    return dedupe_by_source_url(records)[: section.max_items_per_run]


def dedupe_by_source_url(records: list[ParsedAnnouncement]) -> list[ParsedAnnouncement]:
    unique: dict[str, ParsedAnnouncement] = {}
    for record in records:
        unique[record.source_url] = record
    return list(unique.values())


def fetch_page_for_section(url: str, section: SiteSection) -> FetchedPage:
    if section.crawler_strategy == "browser_rendered":
        return fetch_browser_rendered_page(url, section)
    return fetch_url(url, section)


def save_record(
    db: Session,
    site: Site,
    section: SiteSection,
    run: CrawlRun,
    record: ParsedAnnouncement,
    storage_root: Path,
    settings: Settings,
) -> dict[str, int | bool]:
    if record.content is None:
        detail_page = fetch_page_for_section(record.source_url, section)
        content, attachments = parse_detail_page(detail_page.text, detail_page.final_url, section)
        final_url = detail_page.final_url
        snapshot_path = (
            save_snapshot(storage_root, site, section, detail_page)
            if section.save_snapshot
            else None
        )
    else:
        content = record.content
        attachments = record.attachments
        final_url = record.source_url
        snapshot_path = (
            save_text_snapshot(storage_root, site, section, record)
            if section.save_snapshot
            else None
        )
    identity_key = identity_for(record.source_url)
    content_hash = sha256_text(content)
    attachment_hash = sha256_text("\n".join(sorted(item.url for item in attachments)))
    announcement = db.scalar(
        select(Announcement).where(
            Announcement.section_id == section.id,
            Announcement.identity_key == identity_key,
        )
    )
    is_new = announcement is None
    old_content_hash = announcement.content_hash if announcement else None
    old_attachments_hash = announcement.attachments_hash if announcement else None
    now = datetime.now()
    if announcement is None:
        announcement = Announcement(
            site_id=site.id,
            section_id=section.id,
            run_id=run.id,
            identity_key=identity_key,
            identity_strategy="source_url_sha256",
            title=record.title,
            item_type=section.item_type,
            source_url=record.source_url,
            first_seen_at=now,
        )
        db.add(announcement)
    announcement.run_id = run.id
    announcement.title = record.title
    announcement.final_url = final_url
    announcement.raw_published_at = record.raw_published_at
    announcement.published_at = parse_date_text(record.raw_published_at)
    announcement.raw_page_updated_at = record.raw_published_at
    announcement.page_updated_at = announcement.published_at
    announcement.fetched_at = now
    announcement.content = content
    announcement.content_summary = content[:500]
    announcement.content_hash = content_hash
    announcement.attachments_hash = attachment_hash
    announcement.snapshot_path = (
        str(snapshot_path.relative_to(settings.storage_root)) if snapshot_path else None
    )
    announcement.last_seen_at = now
    db.flush()

    if is_new:
        db.add(
            ChangeLog(
                announcement_id=announcement.id,
                site_id=site.id,
                section_id=section.id,
                run_id=run.id,
                change_type="new_announcement",
                title=announcement.title,
                summary="首次抓取入库",
                new_hash=content_hash,
                source_url=announcement.source_url,
            )
        )
    elif old_content_hash and old_content_hash != content_hash:
        db.add(
            ChangeLog(
                announcement_id=announcement.id,
                site_id=site.id,
                section_id=section.id,
                run_id=run.id,
                change_type="content_changed",
                title=announcement.title,
                summary="正文内容 hash 发生变化",
                old_hash=old_content_hash,
                new_hash=content_hash,
                source_url=announcement.source_url,
            )
        )
    if not is_new and old_attachments_hash and old_attachments_hash != attachment_hash:
        db.add(
            ChangeLog(
                announcement_id=announcement.id,
                site_id=site.id,
                section_id=section.id,
                run_id=run.id,
                change_type="attachment_list_changed",
                title=announcement.title,
                summary="附件列表 hash 发生变化",
                old_hash=old_attachments_hash,
                new_hash=attachment_hash,
                source_url=announcement.source_url,
            )
        )

    attachment_added = 0
    attachment_changed = 0
    attachment_success = 0
    attachment_failed = 0
    if section.download_attachments:
        for parsed_attachment in attachments:
            attachment_result = save_attachment(
                db,
                site,
                announcement,
                run,
                parsed_attachment,
                section,
                storage_root,
                settings,
            )
            attachment_added += int(attachment_result["is_new"])
            attachment_changed += int(attachment_result["changed"])
            if attachment_result["success"]:
                attachment_success += 1
            else:
                attachment_failed += 1
    return {
        "is_new": is_new,
        "content_changed": bool(
            (not is_new) and old_content_hash and old_content_hash != content_hash
        ),
        "attachment_added": attachment_added,
        "attachment_changed": attachment_changed,
        "attachment_success": attachment_success,
        "attachment_failed": attachment_failed,
    }


def save_attachment(
    db: Session,
    site: Site,
    announcement: Announcement,
    run: CrawlRun,
    parsed_attachment: ParsedAttachment,
    section: SiteSection,
    storage_root: Path,
    settings: Settings,
) -> dict[str, bool]:
    key = identity_for(parsed_attachment.url)
    attachment = db.scalar(
        select(Attachment).where(
            Attachment.announcement_id == announcement.id,
            Attachment.attachment_key == key,
        )
    )
    now = datetime.now()
    is_new = attachment is None
    if attachment is None:
        attachment = Attachment(
            announcement_id=announcement.id,
            site_id=site.id,
            run_id=run.id,
            attachment_key=key,
            name=parsed_attachment.name,
            safe_name=safe_filename(parsed_attachment.name),
            source_url=parsed_attachment.url,
            first_seen_at=now,
        )
        db.add(attachment)
        db.flush()
        db.add(
            ChangeLog(
                announcement_id=announcement.id,
                attachment_id=attachment.id,
                site_id=site.id,
                section_id=announcement.section_id,
                run_id=run.id,
                change_type="attachment_added",
                title=parsed_attachment.name,
                summary="首次发现附件",
                source_url=parsed_attachment.url,
            )
        )

    attachment.run_id = run.id
    attachment.last_seen_at = now
    try:
        page = fetch_url(
            parsed_attachment.url,
            section,
            timeout=max(1, settings.crawler_attachment_timeout_seconds),
        )
        filename = attachment_filename(parsed_attachment, page)
        new_hash = sha256_bytes(page.body)
        old_hash = attachment.file_hash
        changed = bool(old_hash and old_hash != new_hash)
        target = existing_attachment_target(storage_root, attachment)
        if target is None or changed:
            target = attachment_target(storage_root, site, announcement, filename)
            target.write_bytes(page.body)
        attachment.safe_name = target.name
        attachment.final_url = page.final_url
        attachment.local_path = str(target.relative_to(storage_root))
        attachment.file_size = len(page.body)
        attachment.file_hash = new_hash
        attachment.file_ext = target.suffix.lower()
        attachment.mime_type = page.content_type
        file_updated_at = parse_http_datetime(page.headers.get("last-modified"))
        if file_updated_at:
            attachment.file_updated_at = file_updated_at
        attachment.downloaded_at = now
        attachment.download_status = "success"
        attachment.failure_reason = None
        if should_record_attachment_version(is_new, changed, old_hash):
            db.add(
                AttachmentVersion(
                    attachment_id=attachment.id,
                    announcement_id=announcement.id,
                    site_id=site.id,
                    run_id=run.id,
                    version_no=next_attachment_version_no(db, attachment.id),
                    name=attachment.name,
                    safe_name=attachment.safe_name,
                    source_url=attachment.source_url,
                    final_url=attachment.final_url,
                    local_path=attachment.local_path,
                    file_size=attachment.file_size,
                    file_hash=attachment.file_hash,
                    file_updated_at=attachment.file_updated_at,
                    downloaded_at=attachment.downloaded_at,
                    download_status=attachment.download_status,
                    change_type=attachment_version_change_type(is_new, old_hash),
                )
            )
        if changed:
            db.add(
                ChangeLog(
                    announcement_id=announcement.id,
                    attachment_id=attachment.id,
                    site_id=site.id,
                    section_id=announcement.section_id,
                    run_id=run.id,
                    change_type="attachment_changed",
                    title=parsed_attachment.name,
                    summary="附件文件 hash 发生变化",
                    old_hash=old_hash,
                    new_hash=new_hash,
                    source_url=parsed_attachment.url,
                )
            )
        return {"success": True, "is_new": is_new, "changed": changed}
    except Exception as exc:
        attachment.download_status = "failed"
        attachment.failure_reason = f"{type(exc).__name__}: {exc}"
        db.add(
            ChangeLog(
                announcement_id=announcement.id,
                attachment_id=attachment.id,
                site_id=site.id,
                section_id=announcement.section_id,
                run_id=run.id,
                change_type="attachment_failed",
                title=parsed_attachment.name,
                summary=attachment.failure_reason,
                source_url=parsed_attachment.url,
            )
        )
        return {"success": False, "is_new": is_new, "changed": False}


def save_snapshot(storage_root: Path, site: Site, section: SiteSection, page: FetchedPage) -> Path:
    snapshot_dir = storage_root / "snapshots" / safe_filename(site.slug) / str(section.id)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    target = snapshot_dir / f"{identity_for(page.final_url)[:16]}.html"
    target.write_bytes(page.body)
    return target


def save_text_snapshot(
    storage_root: Path,
    site: Site,
    section: SiteSection,
    record: ParsedAnnouncement,
) -> Path:
    snapshot_dir = storage_root / "snapshots" / safe_filename(site.slug) / str(section.id)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    target = snapshot_dir / f"{identity_for(record.source_url)[:16]}.json"
    target.write_text(record.content or "", encoding="utf-8")
    return target


def attachment_target(
    storage_root: Path,
    site: Site,
    announcement: Announcement,
    filename: str,
) -> Path:
    attachment_dir = storage_root / "attachments" / safe_filename(site.slug) / str(announcement.id)
    attachment_dir.mkdir(parents=True, exist_ok=True)
    target = attachment_dir / filename
    if target.exists():
        suffix = datetime.now().strftime("%H%M%S")
        target = attachment_dir / f"{target.stem}_{suffix}{target.suffix}"
    return target


def existing_attachment_target(storage_root: Path, attachment: Attachment) -> Path | None:
    if not attachment.local_path:
        return None
    target = storage_root / attachment.local_path
    return target if target.exists() else None


def attachment_filename(parsed_attachment: ParsedAttachment, page: FetchedPage) -> str:
    parsed_path = urlparse(page.final_url).path
    source_name = Path(parsed_path).name
    candidate = source_name or parsed_attachment.name
    if not Path(candidate).suffix and Path(parsed_attachment.name).suffix:
        candidate = parsed_attachment.name
    if not Path(candidate).suffix:
        candidate = f"{parsed_attachment.name}.bin"
    return safe_filename(candidate)


def identity_for(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def should_record_attachment_version(is_new: bool, changed: bool, old_hash: str | None) -> bool:
    return is_new or changed or old_hash is None


def attachment_version_change_type(is_new: bool, old_hash: str | None) -> str:
    return "attachment_added" if is_new or old_hash is None else "attachment_changed"


def next_attachment_version_no(db: Session, attachment_id: int) -> int:
    latest = db.scalar(
        select(func.max(AttachmentVersion.version_no)).where(
            AttachmentVersion.attachment_id == attachment_id
        )
    )
    return int(latest or 0) + 1


def parse_http_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
