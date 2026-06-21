from __future__ import annotations

from pathlib import Path

import app.models  # noqa: F401
from app.config import Settings
from app.database import Base, SessionLocal, configure_database
from app.models import Announcement, Attachment, ChangeLog, CrawlRun, Site, SiteSection
from app.services.crawler.parser import extract_unitbuild_requests
from app.services.crawler.runner import crawl_section
from app.services.crawler.types import FetchedPage


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
