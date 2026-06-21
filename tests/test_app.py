from fastapi.testclient import TestClient

import app.models  # noqa: F401
import app.routers.web.archive as archive_router
from app.config import get_settings
from app.database import Base, SessionLocal, configure_database
from app.main import create_app
from app.models import (
    Announcement,
    Attachment,
    ChangeLog,
    CrawlRun,
    NotificationLog,
    Site,
    SiteSection,
)


def make_client(tmp_path, monkeypatch=None):
    engine = configure_database(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    get_settings.cache_clear()
    if monkeypatch is not None:
        monkeypatch.setenv("APP_STORAGE_ROOT", str(tmp_path / "storage"))
        get_settings.cache_clear()
    return TestClient(create_app())


def login(client: TestClient):
    return client.post(
        "/login",
        data={"username": "admin", "password": "change-me"},
        follow_redirects=False,
    )


def test_health_check(tmp_path):
    client = make_client(tmp_path)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_dashboard_requires_login(tmp_path):
    client = make_client(tmp_path)

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_login_and_dashboard_page_loads(tmp_path):
    client = make_client(tmp_path)

    response = login(client)

    assert response.status_code == 303
    dashboard_response = client.get("/")
    assert dashboard_response.status_code == 200
    assert "工作台" in dashboard_response.text
    assert "最近变化" in dashboard_response.text
    assert "/crawl-runs/run-daily" in dashboard_response.text
    assert "正式抓取模块接入后" not in dashboard_response.text


def test_settings_page_requires_login_and_masks_secrets(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    response = client.get("/settings", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"

    login(client)
    settings_response = client.get("/settings")

    assert settings_response.status_code == 200
    assert "系统配置" in settings_response.text
    assert "APP_DATABASE_URL" in settings_response.text
    assert "Windows 脚本" in settings_response.text
    assert "change-me" not in settings_response.text


def test_site_and_section_can_be_created(tmp_path):
    client = make_client(tmp_path)
    login(client)

    site_response = client.post(
        "/sites",
        data={
            "name": "住房和城乡建设部",
            "slug": "mohurd",
            "homepage_url": "https://www.mohurd.gov.cn/",
            "organization": "住建部",
            "region": "国家",
            "enabled": "on",
        },
        follow_redirects=False,
    )
    assert site_response.status_code == 303

    sites_page = client.get("/sites")
    assert sites_page.status_code == 200
    assert "住房和城乡建设部" in sites_page.text

    client.post(
        "/sites/1/sections",
        data={
            "name": "资质公告",
            "url": "https://www.mohurd.gov.cn/gongkai/",
            "item_type": "qualification_notice",
            "crawler_strategy": "http_static",
            "crawl_method": "http",
            "schedule_cron": "0 9 * * *",
            "enabled": "on",
            "download_attachments": "on",
            "save_snapshot": "on",
            "request_timeout": "20",
            "retry_times": "2",
            "request_interval_seconds": "3",
            "max_pages": "3",
            "max_items_per_run": "100",
            "crawl_date_window_days": "1",
            "stop_when_seen_existing_count": "20",
        },
        follow_redirects=False,
    )

    with SessionLocal() as db:
        assert db.get(Site, 1).name == "住房和城乡建设部"
        assert db.get(SiteSection, 1).crawler_strategy == "http_static"


def test_archive_pages_and_attachment_download(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    login(client)
    storage_root = tmp_path / "storage"
    attachment_file = storage_root / "attachments" / "mohurd" / "1" / "a.pdf"
    attachment_file.parent.mkdir(parents=True)
    attachment_file.write_bytes(b"pdf-content")

    with SessionLocal() as db:
        site = Site(
            name="住房和城乡建设部",
            slug="mohurd",
            homepage_url="https://www.mohurd.gov.cn/",
            enabled=True,
        )
        db.add(site)
        db.flush()
        section = SiteSection(
            site_id=site.id,
            name="资质公告",
            url="https://www.mohurd.gov.cn/list.html",
            enabled=True,
        )
        db.add(section)
        db.flush()
        run = CrawlRun(
            run_no="manual-test",
            status="success",
            run_type="manual",
            discovered_items=1,
            new_items=1,
        )
        db.add(run)
        db.flush()
        announcement = Announcement(
            site_id=site.id,
            section_id=section.id,
            run_id=run.id,
            identity_key="abc",
            identity_strategy="test",
            title="资质核准公告",
            item_type="qualification_notice",
            source_url="https://www.mohurd.gov.cn/a.html",
            status="active",
            content="公告正文",
            content_hash="hash",
            attachments_hash="attachments",
            snapshot_path="snapshots/mohurd/1/a.html",
        )
        db.add(announcement)
        db.flush()
        attachment = Attachment(
            announcement_id=announcement.id,
            site_id=site.id,
            run_id=run.id,
            attachment_key="att",
            name="附件",
            safe_name="a.pdf",
            source_url="https://www.mohurd.gov.cn/a.pdf",
            local_path="attachments/mohurd/1/a.pdf",
            file_size=11,
            file_hash="file-hash",
            download_status="success",
        )
        db.add(attachment)
        db.add(
            Attachment(
                announcement_id=announcement.id,
                site_id=site.id,
                run_id=run.id,
                attachment_key="failed-att",
                name="失败附件",
                safe_name="failed.pdf",
                source_url="https://www.mohurd.gov.cn/failed.pdf",
                download_status="failed",
                failure_reason="timeout",
            )
        )
        db.add(
            ChangeLog(
                announcement_id=announcement.id,
                attachment_id=attachment.id,
                site_id=site.id,
                section_id=section.id,
                run_id=run.id,
                change_type="new_announcement",
                title="资质核准公告",
                summary="首次抓取入库",
                source_url=announcement.source_url,
            )
        )
        db.add(
            NotificationLog(
                run_id=run.id,
                provider="openclaw",
                event_type="daily_crawl_report",
                status="failed",
                failure_reason="OPENCLAW_WEBHOOK_URL 未配置",
            )
        )
        db.commit()

    announcement_list = client.get("/announcements")
    assert announcement_list.status_code == 200
    assert "资质核准公告" in announcement_list.text
    assert "变化记录" in announcement_list.text
    assert str(tmp_path) not in announcement_list.text

    changes = client.get("/changes")
    assert changes.status_code == 200
    assert "new_announcement" in changes.text
    assert "首次抓取入库" in changes.text
    assert str(tmp_path) not in changes.text

    filtered_changes = client.get("/changes?change_type=content_changed")
    assert filtered_changes.status_code == 200
    assert "暂无变化记录" in filtered_changes.text

    detail = client.get("/announcements/1")
    assert detail.status_code == 200
    assert "公告正文" in detail.text
    assert "snapshots/mohurd/1/a.html" in detail.text
    assert "/attachments/2/retry" in detail.text
    assert str(tmp_path) not in detail.text

    attachments = client.get("/attachments")
    assert attachments.status_code == 200
    assert "附件" in attachments.text
    assert "失败附件" in attachments.text
    assert "timeout" in attachments.text
    assert "/attachments/2/retry" in attachments.text

    failed_attachments = client.get("/attachments?download_status=failed")
    assert failed_attachments.status_code == 200
    assert "失败附件" in failed_attachments.text
    assert "a.pdf" not in failed_attachments.text

    missing_file_attachments = client.get("/attachments?local_file=no")
    assert missing_file_attachments.status_code == 200
    assert "失败附件" in missing_file_attachments.text

    download = client.get("/attachments/1/download")
    assert download.status_code == 200
    assert download.content == b"pdf-content"

    runs = client.get("/crawl-runs")
    assert runs.status_code == 200
    assert "manual-test" in runs.text

    run_detail = client.get("/crawl-runs/1")
    assert run_detail.status_code == 200
    assert "new_announcement" in run_detail.text

    notifications = client.get("/notifications")
    assert notifications.status_code == 200
    assert "OPENCLAW_WEBHOOK_URL 未配置" in notifications.text
    assert "重试" in notifications.text


def test_web_daily_crawl_action_requires_login_and_passes_notify(tmp_path, monkeypatch):
    client = make_client(tmp_path)
    calls = []

    def fake_run_daily_crawl(*, notify, triggered_by):
        calls.append({"notify": notify, "triggered_by": triggered_by})

    monkeypatch.setattr(archive_router, "run_daily_crawl", fake_run_daily_crawl)

    anonymous_response = client.post("/crawl-runs/run-daily", follow_redirects=False)
    assert anonymous_response.status_code == 303
    assert anonymous_response.headers["location"] == "/login"
    assert calls == []

    login(client)
    crawl_runs = client.get("/crawl-runs")
    assert crawl_runs.status_code == 200
    assert "执行每日抓取" in crawl_runs.text
    assert "发送日报" in crawl_runs.text

    response = client.post(
        "/crawl-runs/run-daily",
        data={"notify": "on"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/crawl-runs"
    assert calls == [{"notify": True, "triggered_by": "admin"}]


def test_web_notification_retry_action_requires_login(tmp_path, monkeypatch):
    client = make_client(tmp_path)
    calls = []

    def fake_retry_notification(db, notification_id):
        calls.append(notification_id)

    monkeypatch.setattr(archive_router, "retry_notification", fake_retry_notification)

    anonymous_response = client.post("/notifications/7/retry", follow_redirects=False)
    assert anonymous_response.status_code == 303
    assert anonymous_response.headers["location"] == "/login"
    assert calls == []

    login(client)
    response = client.post("/notifications/7/retry", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/notifications"
    assert calls == [7]


def test_web_attachment_retry_action_requires_login(tmp_path, monkeypatch):
    client = make_client(tmp_path)
    calls = []

    def fake_retry_attachment_download(db, attachment_id, triggered_by):
        calls.append({"attachment_id": attachment_id, "triggered_by": triggered_by})

    monkeypatch.setattr(
        archive_router,
        "retry_attachment_download",
        fake_retry_attachment_download,
    )

    anonymous_response = client.post("/attachments/9/retry", follow_redirects=False)
    assert anonymous_response.status_code == 303
    assert anonymous_response.headers["location"] == "/login"
    assert calls == []

    login(client)
    response = client.post("/attachments/9/retry", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/attachments"
    assert calls == [{"attachment_id": 9, "triggered_by": "admin"}]
