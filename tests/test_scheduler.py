from __future__ import annotations

from datetime import datetime

import pytest

import app.models  # noqa: F401
from app.config import Settings
from app.database import Base, SessionLocal, configure_database
from app.models import CrawlRun, NotificationLog, Site, SiteSection
from app.services import scheduler


def setup_db(tmp_path):
    engine = configure_database(f"sqlite:///{tmp_path / 'scheduler.db'}")
    Base.metadata.create_all(engine)


def seed_sections():
    with SessionLocal() as db:
        enabled_site = Site(
            name="启用网站",
            slug="enabled",
            homepage_url="https://example.gov.cn",
            enabled=True,
        )
        disabled_site = Site(
            name="停用网站",
            slug="disabled",
            homepage_url="https://disabled.example.gov.cn",
            enabled=False,
        )
        db.add_all([enabled_site, disabled_site])
        db.flush()
        db.add_all(
            [
                SiteSection(
                    site_id=enabled_site.id,
                    name="启用栏目",
                    url="https://example.gov.cn/list.html",
                    enabled=True,
                ),
                SiteSection(
                    site_id=enabled_site.id,
                    name="停用栏目",
                    url="https://example.gov.cn/disabled.html",
                    enabled=False,
                ),
                SiteSection(
                    site_id=disabled_site.id,
                    name="停用网站栏目",
                    url="https://disabled.example.gov.cn/list.html",
                    enabled=True,
                ),
            ]
        )
        db.commit()


def test_parse_daily_time_accepts_hh_mm():
    assert scheduler.parse_daily_time("09:30") == (9, 30)
    assert scheduler.parse_daily_time("23:59") == (23, 59)


@pytest.mark.parametrize("value", ["9", "24:00", "12:60", "abc"])
def test_parse_daily_time_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        scheduler.parse_daily_time(value)


def test_enabled_section_ids_only_returns_enabled_sections_from_enabled_sites(tmp_path):
    setup_db(tmp_path)
    seed_sections()

    with SessionLocal() as db:
        assert scheduler.enabled_section_ids(db) == [1]


def test_run_daily_crawl_crawls_enabled_sections_and_sends_report(tmp_path, monkeypatch):
    setup_db(tmp_path)
    seed_sections()
    crawled = []

    def fake_crawl_section(db, section_id, triggered_by, settings):
        crawled.append((section_id, triggered_by, settings.app_timezone))
        run = CrawlRun(
            run_no=f"test-{section_id}",
            run_type="manual",
            status="success",
            started_at=datetime(2026, 6, 21, 9, 0),
            finished_at=datetime(2026, 6, 21, 9, 1),
            total_sections=1,
            success_sections=1,
        )
        db.add(run)
        db.commit()
        return run

    def fake_send_daily_report(db, settings):
        log = NotificationLog(
            provider="openclaw",
            event_type="daily_crawl_report",
            status="success",
            target_type=settings.wecom_notify_target_type,
        )
        db.add(log)
        db.commit()
        return log

    monkeypatch.setattr(scheduler, "crawl_section", fake_crawl_section)
    monkeypatch.setattr(scheduler, "send_daily_report", fake_send_daily_report)

    result = scheduler.run_daily_crawl(
        settings=Settings(APP_TIMEZONE="Asia/Shanghai"),
        notify=True,
        triggered_by="scheduled",
    )

    assert result.section_ids == [1]
    assert result.success_count == 1
    assert result.failed_count == 0
    assert result.notification.status == "success"
    assert crawled == [(1, "scheduled", "Asia/Shanghai")]


def test_start_scheduler_respects_enabled_flag():
    scheduler.stop_scheduler()

    assert scheduler.start_scheduler(Settings(APP_SCHEDULER_ENABLED=False)) is None
    assert scheduler.scheduler_status(Settings(APP_SCHEDULER_ENABLED=False))["running"] is False
