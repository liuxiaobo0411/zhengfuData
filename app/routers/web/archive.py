from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from app.config import BASE_DIR, get_settings
from app.database import SessionLocal
from app.models import (
    Announcement,
    Attachment,
    AttachmentVersion,
    ChangeLog,
    CrawlRun,
    NotificationLog,
    Site,
    SiteSection,
)
from app.routers.web.security import require_user
from app.services.crawler import retry_attachment_download
from app.services.notifier import retry_notification
from app.services.scheduler import run_daily_crawl
from app.services.storage import prepare_storage

router = APIRouter(tags=["archive"])
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


@router.get("/announcements", response_class=HTMLResponse)
def announcement_list(request: Request):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    filters = {
        "q": request.query_params.get("q", "").strip(),
        "site_id": request.query_params.get("site_id", "").strip(),
        "section_id": request.query_params.get("section_id", "").strip(),
        "item_type": request.query_params.get("item_type", "").strip(),
        "status": request.query_params.get("status", "").strip(),
        "has_attachment": request.query_params.get("has_attachment", "").strip(),
    }
    with SessionLocal() as db:
        attachment_counts = (
            select(Attachment.announcement_id, func.count(Attachment.id).label("attachment_count"))
            .group_by(Attachment.announcement_id)
            .subquery()
        )
        query = (
            select(
                Announcement,
                Site.name.label("site_name"),
                SiteSection.name.label("section_name"),
                func.coalesce(attachment_counts.c.attachment_count, 0).label("attachment_count"),
            )
            .join(Site, Announcement.site_id == Site.id)
            .join(SiteSection, Announcement.section_id == SiteSection.id)
            .outerjoin(attachment_counts, attachment_counts.c.announcement_id == Announcement.id)
            .order_by(Announcement.fetched_at.desc(), Announcement.id.desc())
        )
        if filters["q"]:
            query = query.where(Announcement.title.contains(filters["q"]))
        if filters["site_id"].isdigit():
            query = query.where(Announcement.site_id == int(filters["site_id"]))
        if filters["section_id"].isdigit():
            query = query.where(Announcement.section_id == int(filters["section_id"]))
        if filters["item_type"]:
            query = query.where(Announcement.item_type == filters["item_type"])
        if filters["status"]:
            query = query.where(Announcement.status == filters["status"])
        if filters["has_attachment"] == "yes":
            query = query.where(func.coalesce(attachment_counts.c.attachment_count, 0) > 0)
        if filters["has_attachment"] == "no":
            query = query.where(func.coalesce(attachment_counts.c.attachment_count, 0) == 0)
        rows = db.execute(query.limit(200)).all()
        sites = db.scalars(select(Site).order_by(Site.name)).all()
        sections = db.scalars(select(SiteSection).order_by(SiteSection.name)).all()

    return templates.TemplateResponse(
        request,
        "archive/announcements.html",
        {
            "active_nav": "announcements",
            "user": user,
            "rows": rows,
            "sites": sites,
            "sections": sections,
            "filters": filters,
        },
    )


@router.get("/announcements/{announcement_id}", response_class=HTMLResponse)
def announcement_detail(request: Request, announcement_id: int):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    with SessionLocal() as db:
        row = db.execute(
            select(Announcement, Site, SiteSection)
            .join(Site, Announcement.site_id == Site.id)
            .join(SiteSection, Announcement.section_id == SiteSection.id)
            .where(Announcement.id == announcement_id)
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="announcement not found")
        announcement, site, section = row
        attachments = db.scalars(
            select(Attachment)
            .where(Attachment.announcement_id == announcement_id)
            .order_by(Attachment.id)
        ).all()
        attachment_versions = versions_for_attachments(
            db, [attachment.id for attachment in attachments]
        )
        changes = db.scalars(
            select(ChangeLog)
            .where(ChangeLog.announcement_id == announcement_id)
            .order_by(ChangeLog.created_at.desc(), ChangeLog.id.desc())
        ).all()

    return templates.TemplateResponse(
        request,
        "archive/announcement_detail.html",
        {
            "active_nav": "announcements",
            "user": user,
            "announcement": announcement,
            "site": site,
            "section": section,
            "attachments": attachments,
            "attachment_versions": attachment_versions,
            "changes": changes,
        },
    )


@router.get("/changes", response_class=HTMLResponse)
def change_list(request: Request):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    filters = {
        "change_type": request.query_params.get("change_type", "").strip(),
        "site_id": request.query_params.get("site_id", "").strip(),
        "section_id": request.query_params.get("section_id", "").strip(),
    }
    with SessionLocal() as db:
        AnnouncementAlias = aliased(Announcement)
        SiteAlias = aliased(Site)
        SectionAlias = aliased(SiteSection)
        query = (
            select(
                ChangeLog,
                AnnouncementAlias.id.label("announcement_id"),
                SiteAlias.name.label("site_name"),
                SectionAlias.name.label("section_name"),
            )
            .outerjoin(AnnouncementAlias, ChangeLog.announcement_id == AnnouncementAlias.id)
            .outerjoin(SiteAlias, ChangeLog.site_id == SiteAlias.id)
            .outerjoin(SectionAlias, ChangeLog.section_id == SectionAlias.id)
            .order_by(ChangeLog.created_at.desc(), ChangeLog.id.desc())
        )
        if filters["change_type"]:
            query = query.where(ChangeLog.change_type == filters["change_type"])
        if filters["site_id"].isdigit():
            query = query.where(ChangeLog.site_id == int(filters["site_id"]))
        if filters["section_id"].isdigit():
            query = query.where(ChangeLog.section_id == int(filters["section_id"]))
        rows = db.execute(query.limit(300)).all()
        sites = db.scalars(select(Site).order_by(Site.name)).all()
        sections = db.scalars(select(SiteSection).order_by(SiteSection.name)).all()
        change_types = list(
            db.scalars(select(ChangeLog.change_type).distinct().order_by(ChangeLog.change_type))
        )

    return templates.TemplateResponse(
        request,
        "archive/changes.html",
        {
            "active_nav": "changes",
            "user": user,
            "rows": rows,
            "sites": sites,
            "sections": sections,
            "change_types": change_types,
            "filters": filters,
        },
    )


@router.get("/attachments", response_class=HTMLResponse)
def attachment_list(request: Request):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    filters = {
        "q": request.query_params.get("q", "").strip(),
        "download_status": request.query_params.get("download_status", "").strip(),
        "site_id": request.query_params.get("site_id", "").strip(),
        "local_file": request.query_params.get("local_file", "").strip(),
    }
    with SessionLocal() as db:
        query = attachment_list_query(filters)
        rows = db.execute(query.limit(300)).all()
        version_counts = attachment_version_counts(db, [row[0].id for row in rows])
        sites = db.scalars(select(Site).order_by(Site.name)).all()
        download_statuses = list(
            db.scalars(
                select(Attachment.download_status).distinct().order_by(Attachment.download_status)
            )
        )

    return templates.TemplateResponse(
        request,
        "archive/attachments.html",
        {
            "active_nav": "attachments",
            "user": user,
            "rows": rows,
            "sites": sites,
            "download_statuses": download_statuses,
            "version_counts": version_counts,
            "filters": filters,
            "download_all_url": download_all_url(filters),
        },
    )


@router.get("/attachments/download-all")
def download_all_attachments(request: Request):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    filters = {
        "q": request.query_params.get("q", "").strip(),
        "download_status": request.query_params.get("download_status", "").strip(),
        "site_id": request.query_params.get("site_id", "").strip(),
        "local_file": "yes",
    }
    settings = get_settings()
    storage = prepare_storage(settings)
    storage_root = storage.root.resolve()
    with SessionLocal() as db:
        rows = db.execute(attachment_list_query(filters).limit(1000)).all()

    files: list[tuple[Attachment, Path]] = []
    for attachment, _announcement_title, _site_name in rows:
        if not attachment.local_path:
            continue
        file_path = (storage_root / attachment.local_path).resolve()
        if is_relative_to(file_path, storage_root) and file_path.exists():
            files.append((attachment, file_path))
    if not files:
        raise HTTPException(status_code=404, detail="no local attachments to download")

    archive_name = f"attachments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    archive_path = storage.exports / archive_name
    used_names: set[str] = set()
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        for attachment, file_path in files:
            archive.write(file_path, arcname=zip_entry_name(attachment, used_names))

    return FileResponse(
        archive_path,
        media_type="application/zip",
        filename=archive_name,
    )


@router.get("/attachments/{attachment_id}/download")
def download_attachment(request: Request, attachment_id: int):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    with SessionLocal() as db:
        attachment = db.get(Attachment, attachment_id)
        if attachment is None or not attachment.local_path:
            raise HTTPException(status_code=404, detail="attachment not found")
        settings = get_settings()
        storage_root = settings.storage_root.resolve()
        file_path = (storage_root / attachment.local_path).resolve()
        if not is_relative_to(file_path, storage_root) or not file_path.exists():
            raise HTTPException(status_code=404, detail="attachment file missing")
        return FileResponse(
            file_path,
            media_type=attachment.mime_type or "application/octet-stream",
            filename=attachment.safe_name,
        )


def attachment_list_query(filters: dict[str, str]):
    query = (
        select(
            Attachment,
            Announcement.title.label("announcement_title"),
            Site.name.label("site_name"),
        )
        .join(Announcement, Attachment.announcement_id == Announcement.id)
        .join(Site, Attachment.site_id == Site.id)
        .order_by(Attachment.created_at.desc(), Attachment.id.desc())
    )
    if filters["q"]:
        query = query.where(
            Attachment.name.contains(filters["q"]) | Announcement.title.contains(filters["q"])
        )
    if filters["download_status"]:
        query = query.where(Attachment.download_status == filters["download_status"])
    if filters["site_id"].isdigit():
        query = query.where(Attachment.site_id == int(filters["site_id"]))
    if filters["local_file"] == "yes":
        query = query.where(Attachment.local_path.is_not(None))
    if filters["local_file"] == "no":
        query = query.where(Attachment.local_path.is_(None))
    return query


def versions_for_attachments(
    db,
    attachment_ids: list[int],
    limit_per_attachment: int = 3,
) -> dict[int, list[AttachmentVersion]]:
    if not attachment_ids:
        return {}
    versions = db.scalars(
        select(AttachmentVersion)
        .where(AttachmentVersion.attachment_id.in_(attachment_ids))
        .order_by(
            AttachmentVersion.attachment_id,
            AttachmentVersion.version_no.desc(),
            AttachmentVersion.id.desc(),
        )
    ).all()
    grouped: dict[int, list[AttachmentVersion]] = {
        attachment_id: [] for attachment_id in attachment_ids
    }
    for version in versions:
        bucket = grouped.setdefault(version.attachment_id, [])
        if len(bucket) < limit_per_attachment:
            bucket.append(version)
    return grouped


def attachment_version_counts(db, attachment_ids: list[int]) -> dict[int, int]:
    if not attachment_ids:
        return {}
    rows = db.execute(
        select(AttachmentVersion.attachment_id, func.count(AttachmentVersion.id))
        .where(AttachmentVersion.attachment_id.in_(attachment_ids))
        .group_by(AttachmentVersion.attachment_id)
    ).all()
    return {attachment_id: count for attachment_id, count in rows}


def download_all_url(filters: dict[str, str]) -> str:
    query = {
        key: value
        for key, value in filters.items()
        if value and key in {"q", "download_status", "site_id"}
    }
    suffix = f"?{urlencode(query)}" if query else ""
    return f"/attachments/download-all{suffix}"


def zip_entry_name(attachment: Attachment, used_names: set[str]) -> str:
    candidate = f"{attachment.id}_{attachment.safe_name}"
    if candidate not in used_names:
        used_names.add(candidate)
        return candidate
    stem = Path(candidate).stem
    suffix = Path(candidate).suffix
    index = 2
    while f"{stem}_{index}{suffix}" in used_names:
        index += 1
    value = f"{stem}_{index}{suffix}"
    used_names.add(value)
    return value


@router.post("/attachments/{attachment_id}/retry")
def retry_attachment_from_web(request: Request, attachment_id: int):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    with SessionLocal() as db:
        retry_attachment_download(db, attachment_id, triggered_by=user.username)
    return RedirectResponse("/attachments", status_code=303)


@router.get("/crawl-runs", response_class=HTMLResponse)
def crawl_run_list(request: Request):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    with SessionLocal() as db:
        rows = db.scalars(
            select(CrawlRun).order_by(CrawlRun.started_at.desc(), CrawlRun.id.desc()).limit(200)
        ).all()

    return templates.TemplateResponse(
        request,
        "archive/crawl_runs.html",
        {"active_nav": "crawl_runs", "user": user, "runs": rows},
    )


@router.post("/crawl-runs/run-daily")
async def run_daily_crawl_from_web(request: Request):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    form = await request.form()
    notify = form.get("notify") in {"on", "true", "1", "yes"}
    run_daily_crawl(notify=notify, triggered_by=user.username)
    return RedirectResponse("/crawl-runs", status_code=303)


@router.get("/crawl-runs/{run_id}", response_class=HTMLResponse)
def crawl_run_detail(request: Request, run_id: int):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    with SessionLocal() as db:
        run = db.get(CrawlRun, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="crawl run not found")
        SiteAlias = aliased(Site)
        SectionAlias = aliased(SiteSection)
        changes = db.execute(
            select(
                ChangeLog,
                SiteAlias.name.label("site_name"),
                SectionAlias.name.label("section_name"),
            )
            .outerjoin(SiteAlias, ChangeLog.site_id == SiteAlias.id)
            .outerjoin(SectionAlias, ChangeLog.section_id == SectionAlias.id)
            .where(ChangeLog.run_id == run_id)
            .order_by(ChangeLog.created_at.desc(), ChangeLog.id.desc())
        ).all()
        notifications = db.scalars(
            select(NotificationLog)
            .where(NotificationLog.run_id == run_id)
            .order_by(NotificationLog.created_at.desc(), NotificationLog.id.desc())
        ).all()

    return templates.TemplateResponse(
        request,
        "archive/crawl_run_detail.html",
        {
            "active_nav": "crawl_runs",
            "user": user,
            "run": run,
            "changes": changes,
            "notifications": notifications,
        },
    )


@router.get("/notifications", response_class=HTMLResponse)
def notification_list(request: Request):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    with SessionLocal() as db:
        rows = db.scalars(
            select(NotificationLog)
            .order_by(NotificationLog.created_at.desc(), NotificationLog.id.desc())
            .limit(200)
        ).all()

    return templates.TemplateResponse(
        request,
        "archive/notifications.html",
        {"active_nav": "notifications", "user": user, "notifications": rows},
    )


@router.post("/notifications/{notification_id}/retry")
def retry_notification_from_web(request: Request, notification_id: int):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    with SessionLocal() as db:
        retry_notification(db, notification_id)
    return RedirectResponse("/notifications", status_code=303)


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
