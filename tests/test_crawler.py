from __future__ import annotations

from pathlib import Path

import app.models  # noqa: F401
from app.config import Settings
from app.database import Base, SessionLocal, configure_database
from app.models import Announcement, Attachment, ChangeLog, CrawlRun, Site, SiteSection
from app.services.crawler.parser import extract_unitbuild_requests
from app.services.crawler.runner import (
    crawl_section,
    identity_for,
    retry_attachment_download,
    run_type_for,
)
from app.services.crawler.types import FetchedPage


def fetched(url: str, body: bytes | str, content_type: str = "text/html") -> FetchedPage:
    text = body.decode() if isinstance(body, bytes) else body
    raw_body = body if isinstance(body, bytes) else body.encode()
    return FetchedPage(
        url=url,
        final_url=url,
        body=raw_body,
        text=text,
        content_type=content_type,
    )


def setup_db(tmp_path: Path):
    engine = configure_database(f"sqlite:///{tmp_path / 'crawler.db'}")
    Base.metadata.create_all(engine)
    return engine


def create_site_and_section(crawler_strategy: str = "http_static") -> int:
    with SessionLocal() as db:
        site = Site(
            name="测试政府网站",
            slug="test-gov",
            homepage_url="https://example.gov.cn/",
            enabled=True,
        )
        db.add(site)
        db.flush()
        section = SiteSection(
            site_id=site.id,
            name="公告栏目",
            url="https://example.gov.cn/list.html",
            item_type="qualification_notice",
            crawler_strategy=crawler_strategy,
            enabled=True,
            download_attachments=True,
            save_snapshot=True,
        )
        db.add(section)
        db.commit()
        return section.id


def test_run_type_for_distinguishes_manual_and_scheduled_triggers():
    assert run_type_for("scheduled") == "scheduled"
    assert run_type_for("cli_daily") == "scheduled"
    assert run_type_for("cli") == "manual"
    assert run_type_for("admin") == "manual"


def test_crawl_section_saves_html_announcement_snapshot_and_attachment(tmp_path, monkeypatch):
    setup_db(tmp_path)
    section_id = create_site_and_section()

    def fake_fetch(url: str, section: SiteSection, timeout: int | None = None):
        if url.endswith("list.html"):
            html = "<html><li><a href='detail.html'>资质核准公告</a>2026-06-21</li></html>"
            return FetchedPage(
                url=url,
                final_url=url,
                body=html.encode(),
                text=html,
                content_type="text/html",
            )
        if url.endswith("detail.html"):
            html = (
                "<html><body><main>公告正文</main><a href='files/a.pdf'>附件下载</a></body></html>"
            )
            return FetchedPage(
                url=url,
                final_url=url,
                body=html.encode(),
                text=html,
                content_type="text/html",
            )
        return FetchedPage(
            url=url,
            final_url=url,
            body=b"pdf-bytes",
            text="pdf-bytes",
            content_type="application/pdf",
        )

    monkeypatch.setattr("app.services.crawler.runner.fetch_url", fake_fetch)
    settings = Settings(APP_STORAGE_ROOT=tmp_path / "storage")
    with SessionLocal() as db:
        run = crawl_section(db, section_id, triggered_by="tester", settings=settings)

    assert run.status == "success"
    assert run.new_items == 1
    assert run.attachment_success_count == 1
    with SessionLocal() as db:
        announcement = db.query(Announcement).one()
        attachment = db.query(Attachment).one()
        changes = db.query(ChangeLog).all()
        assert announcement.title == "资质核准公告"
        assert announcement.snapshot_path.endswith(".html")
        assert attachment.download_status == "success"
        assert attachment.local_path.endswith(".pdf")
        assert (settings.storage_root / attachment.local_path).exists()
        assert {change.change_type for change in changes} == {
            "new_announcement",
            "attachment_added",
        }


def test_repeated_crawl_does_not_duplicate_records(tmp_path, monkeypatch):
    setup_db(tmp_path)
    section_id = create_site_and_section()

    def fake_fetch(url: str, section: SiteSection, timeout: int | None = None):
        if url.endswith("list.html"):
            html = "<html><li><a href='detail.html'>资质核准公告</a>2026-06-21</li></html>"
            return fetched(url, html)
        if url.endswith("detail.html"):
            html = (
                "<html><body><main>公告正文</main><a href='files/a.pdf'>附件下载</a></body></html>"
            )
            return fetched(url, html)
        return fetched(url, b"same-pdf", "application/pdf")

    monkeypatch.setattr("app.services.crawler.runner.fetch_url", fake_fetch)
    settings = Settings(APP_STORAGE_ROOT=tmp_path / "storage")
    with SessionLocal() as db:
        first_run = crawl_section(db, section_id, triggered_by="tester", settings=settings)
        second_run = crawl_section(db, section_id, triggered_by="tester", settings=settings)

    assert first_run.new_items == 1
    assert second_run.new_items == 0
    assert second_run.content_changed_items == 0
    assert second_run.attachment_added_count == 0
    assert second_run.attachment_changed_count == 0
    with SessionLocal() as db:
        assert db.query(Announcement).count() == 1
        assert db.query(Attachment).count() == 1
        assert db.query(ChangeLog).count() == 2


def test_content_change_writes_change_log(tmp_path, monkeypatch):
    setup_db(tmp_path)
    section_id = create_site_and_section()
    state = {"version": "v1"}

    with SessionLocal() as db:
        section = db.get(SiteSection, section_id)
        section.download_attachments = False
        db.commit()

    def fake_fetch(url: str, section: SiteSection, timeout: int | None = None):
        if url.endswith("list.html"):
            html = "<html><li><a href='detail.html'>资质核准公告</a>2026-06-21</li></html>"
        else:
            html = f"<html><body><main>公告正文 {state['version']}</main></body></html>"
        return fetched(url, html)

    monkeypatch.setattr("app.services.crawler.runner.fetch_url", fake_fetch)
    settings = Settings(APP_STORAGE_ROOT=tmp_path / "storage")
    with SessionLocal() as db:
        crawl_section(db, section_id, triggered_by="tester", settings=settings)
        state["version"] = "v2"
        second_run = crawl_section(db, section_id, triggered_by="tester", settings=settings)

    assert second_run.new_items == 0
    assert second_run.content_changed_items == 1
    with SessionLocal() as db:
        assert db.query(Announcement).count() == 1
        assert db.query(ChangeLog).filter_by(change_type="content_changed").count() == 1


def test_attachment_content_change_writes_change_log(tmp_path, monkeypatch):
    setup_db(tmp_path)
    section_id = create_site_and_section()
    state = {"body": b"pdf-v1"}

    def fake_fetch(url: str, section: SiteSection, timeout: int | None = None):
        if url.endswith("list.html"):
            html = "<html><li><a href='detail.html'>资质核准公告</a>2026-06-21</li></html>"
            return fetched(url, html)
        if url.endswith("detail.html"):
            html = (
                "<html><body><main>公告正文</main><a href='files/a.pdf'>附件下载</a></body></html>"
            )
            return fetched(url, html)
        return fetched(url, state["body"], "application/pdf")

    monkeypatch.setattr("app.services.crawler.runner.fetch_url", fake_fetch)
    settings = Settings(APP_STORAGE_ROOT=tmp_path / "storage")
    with SessionLocal() as db:
        crawl_section(db, section_id, triggered_by="tester", settings=settings)
        state["body"] = b"pdf-v2"
        second_run = crawl_section(db, section_id, triggered_by="tester", settings=settings)

    assert second_run.new_items == 0
    assert second_run.attachment_added_count == 0
    assert second_run.attachment_changed_count == 1
    with SessionLocal() as db:
        assert db.query(Announcement).count() == 1
        assert db.query(Attachment).count() == 1
        assert db.query(ChangeLog).filter_by(change_type="attachment_changed").count() == 1


def test_crawl_section_saves_json_api_rows(tmp_path, monkeypatch):
    setup_db(tmp_path)
    section_id = create_site_and_section("json_api")

    def fake_fetch(url: str, section: SiteSection, timeout: int | None = None):
        text = (
            '{"rows":[{"fid":"1","fentName":"测试企业",'
            '"fappContent":"资质增项公告","ftime":"2026-06-21"}]}'
        )
        body = text.encode()
        return FetchedPage(
            url=url,
            final_url=url,
            body=body,
            text=text,
            content_type="application/json",
        )

    monkeypatch.setattr("app.services.crawler.runner.fetch_url", fake_fetch)
    settings = Settings(APP_STORAGE_ROOT=tmp_path / "storage")
    with SessionLocal() as db:
        run = crawl_section(db, section_id, triggered_by="tester", settings=settings)

    assert run.status == "success"
    with SessionLocal() as db:
        announcement = db.query(Announcement).one()
        assert announcement.title == "资质增项公告"
        assert announcement.snapshot_path.endswith(".json")
        assert "测试企业" in announcement.content


def test_crawl_section_saves_qualification_query_json_rows(tmp_path, monkeypatch):
    setup_db(tmp_path)
    section_id = create_site_and_section("json_api")

    def fake_fetch(url: str, section: SiteSection, timeout: int | None = None):
        text = (
            '{"rows":[{"fid":"q1","fname":"陕西测试建筑工程有限公司",'
            '"ftypename":"施工劳务（备案）不分等级","fcertino":"D361000001",'
            '"fendtimelist":"2031-06-19"}]}'
        )
        return fetched(url, text, "application/json")

    monkeypatch.setattr("app.services.crawler.runner.fetch_url", fake_fetch)
    settings = Settings(APP_STORAGE_ROOT=tmp_path / "storage")
    with SessionLocal() as db:
        run = crawl_section(db, section_id, triggered_by="tester", settings=settings)

    assert run.status == "success"
    with SessionLocal() as db:
        announcement = db.query(Announcement).one()
        assert announcement.title == "陕西测试建筑工程有限公司"
        assert announcement.raw_published_at == "2031-06-19"
        assert "D361000001" in announcement.content


def test_unsupported_strategy_records_readable_failure(tmp_path):
    setup_db(tmp_path)
    section_id = create_site_and_section("browser_rendered")

    with SessionLocal() as db:
        run = crawl_section(
            db,
            section_id,
            triggered_by="tester",
            settings=Settings(APP_STORAGE_ROOT=tmp_path / "storage"),
        )

    assert run.status == "failed"
    assert "browser_rendered" in run.error_summary
    with SessionLocal() as db:
        assert db.query(CrawlRun).one().status == "failed"
        assert db.query(ChangeLog).one().change_type == "crawl_failed"


def test_retry_attachment_download_updates_failed_attachment(tmp_path, monkeypatch):
    setup_db(tmp_path)
    with SessionLocal() as db:
        site = Site(
            name="测试政府网站",
            slug="test-gov",
            homepage_url="https://example.gov.cn/",
            enabled=True,
        )
        db.add(site)
        db.flush()
        section = SiteSection(
            site_id=site.id,
            name="公告栏目",
            url="https://example.gov.cn/list.html",
            enabled=True,
        )
        db.add(section)
        db.flush()
        announcement = Announcement(
            site_id=site.id,
            section_id=section.id,
            identity_key="abc",
            identity_strategy="test",
            title="资质核准公告",
            item_type="qualification_notice",
            source_url="https://example.gov.cn/a.html",
        )
        db.add(announcement)
        db.flush()
        attachment = Attachment(
            announcement_id=announcement.id,
            site_id=site.id,
            attachment_key=identity_for("https://example.gov.cn/failed.pdf"),
            name="失败附件.pdf",
            safe_name="failed.pdf",
            source_url="https://example.gov.cn/failed.pdf",
            download_status="failed",
            failure_reason="timeout",
        )
        db.add(attachment)
        db.commit()
        attachment_id = attachment.id

    def fake_fetch(url: str, section: SiteSection, timeout: int | None = None):
        return fetched(url, b"pdf-content", "application/pdf")

    monkeypatch.setattr("app.services.crawler.runner.fetch_url", fake_fetch)
    settings = Settings(APP_STORAGE_ROOT=tmp_path / "storage")
    with SessionLocal() as db:
        attachment = retry_attachment_download(
            db,
            attachment_id,
            triggered_by="tester",
            settings=settings,
        )

    assert attachment is not None
    assert attachment.download_status == "success"
    assert attachment.failure_reason is None
    assert attachment.local_path.endswith(".pdf")
    assert (settings.storage_root / attachment.local_path).read_bytes() == b"pdf-content"
    with SessionLocal() as db:
        run = db.query(CrawlRun).one()
        assert run.status == "success"
        assert run.attachment_success_count == 1
        assert db.query(ChangeLog).count() == 0


def test_extract_unitbuild_requests_reads_mohurd_script():
    html = """
    <script
      url="/api-gateway/jpaas-publish-server/front/page/build/unit"
      queryData="{'parseType':'bulidstatic','pageId':'abc'}"></script>
    """

    requests = extract_unitbuild_requests(html, "https://www.mohurd.gov.cn/column/index.html")

    assert requests == [
        (
            "https://www.mohurd.gov.cn/api-gateway/jpaas-publish-server/front/page/build/unit",
            {"parseType": "bulidstatic", "pageId": "abc"},
        )
    ]
