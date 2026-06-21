from __future__ import annotations

import json

import app.models  # noqa: F401
from app.database import Base, SessionLocal, configure_database
from app.models import Site, SiteSection
from app.services import source_validator
from app.services.crawler.types import FetchedPage


def setup_db(tmp_path):
    engine = configure_database(f"sqlite:///{tmp_path / 'validator.db'}")
    Base.metadata.create_all(engine)


def add_section(name: str, url: str, strategy: str = "http_static", enabled: bool = True):
    with SessionLocal() as db:
        site = db.query(Site).first()
        if site is None:
            site = Site(
                name="测试站点",
                slug="test-site",
                homepage_url="https://example.gov.cn",
                enabled=True,
            )
            db.add(site)
            db.flush()
        section = SiteSection(
            site_id=site.id,
            name=name,
            url=url,
            crawler_strategy=strategy,
            enabled=enabled,
        )
        db.add(section)
        db.commit()
        return section.id


def fake_page(url: str, text: str, content_type: str = "text/html"):
    return FetchedPage(
        url=url,
        final_url=url,
        body=text.encode(),
        text=text,
        content_type=content_type,
    )


def test_validate_enabled_sources_parses_html_and_json_sections(tmp_path, monkeypatch):
    setup_db(tmp_path)
    add_section("HTML 栏目", "https://example.gov.cn/list.html")
    add_section("JSON 栏目", "https://example.gov.cn/api", strategy="json_api")
    add_section("停用栏目", "https://example.gov.cn/disabled.html", enabled=False)

    def fake_fetch(url, section):
        if section.crawler_strategy == "json_api":
            payload = {"data": [{"title": "JSON 公告", "id": "1"}]}
            return fake_page(url, json.dumps(payload), "application/json")
        return fake_page(url, "<html><li><a href='a.html'>HTML 公告</a>2026-06-21</li></html>")

    monkeypatch.setattr(source_validator, "fetch_url", fake_fetch)

    summary = source_validator.validate_enabled_sources()

    assert summary.total_count == 2
    assert summary.success_count == 2
    assert summary.failed_count == 0
    assert [result.sample_title for result in summary.results] == ["HTML 公告", "JSON 公告"]


def test_validate_enabled_sources_records_parse_failures(tmp_path, monkeypatch):
    setup_db(tmp_path)
    add_section("空栏目", "https://example.gov.cn/empty.html")

    monkeypatch.setattr(
        source_validator,
        "fetch_url",
        lambda url, section: fake_page(url, "<html><main>无列表</main></html>"),
    )

    summary = source_validator.validate_enabled_sources()

    assert summary.total_count == 1
    assert summary.failed_count == 1
    assert "未解析到列表记录" in summary.results[0].failure_reason
