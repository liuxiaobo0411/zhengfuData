from fastapi.testclient import TestClient

import app.models  # noqa: F401
from app.database import Base, SessionLocal, configure_database
from app.main import create_app
from app.models import Site, SiteSection


def make_client(tmp_path):
    engine = configure_database(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
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
