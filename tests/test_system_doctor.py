from __future__ import annotations

import app.models  # noqa: F401
from app.config import Settings
from app.database import Base, SessionLocal, configure_database
from app.models import Site, SiteSection
from app.services import system_doctor
from app.services.system_doctor import format_doctor_report, run_system_doctor


def setup_db(tmp_path):
    engine = configure_database(f"sqlite:///{tmp_path / 'doctor.db'}")
    Base.metadata.create_all(engine)


def test_system_doctor_warns_for_unimported_sources_without_failing(tmp_path):
    setup_db(tmp_path)

    with SessionLocal() as db:
        report = run_system_doctor(
            db,
            settings=Settings(
                APP_STORAGE_ROOT=tmp_path / "storage",
                APP_SECRET_KEY="change-me",
                ADMIN_PASSWORD="change-me",
                OPENCLAW_NOTIFY_MODE="webhook",
                OPENCLAW_WEBHOOK_URL="",
            ),
        )

    assert report.failed_count == 0
    assert any(check.name == "sources" and check.status == "warn" for check in report.checks)
    assert any(check.name == "openclaw" and check.status == "warn" for check in report.checks)
    assert any(check.name == "security" and check.status == "warn" for check in report.checks)
    rendered = format_doctor_report(report)
    assert "系统自检结果" in rendered
    assert "summary" in rendered


def test_system_doctor_passes_for_ready_local_environment(tmp_path):
    setup_db(tmp_path)
    with SessionLocal() as db:
        site = Site(
            name="测试站点",
            slug="test-site",
            homepage_url="https://example.gov.cn/",
            enabled=True,
        )
        db.add(site)
        db.flush()
        for index in range(10):
            db.add(
                SiteSection(
                    site_id=site.id,
                    name=f"栏目{index}",
                    url=f"https://example.gov.cn/list-{index}.html",
                    enabled=True,
                )
            )
        db.commit()

        report = run_system_doctor(
            db,
            settings=Settings(
                APP_STORAGE_ROOT=tmp_path / "storage",
                APP_SECRET_KEY="test-secret-key",
                ADMIN_PASSWORD="test-password",
                OPENCLAW_NOTIFY_MODE="webhook",
                OPENCLAW_WEBHOOK_URL="https://openclaw.example/webhook",
            ),
        )

    assert report.failed_count == 0
    assert report.warning_count == 0
    assert {check.name for check in report.checks} == {
        "database",
        "database_schema",
        "security",
        "storage",
        "sites_config",
        "sources",
        "openclaw",
        "windows_scripts",
        "unix_scripts",
    }


def test_system_doctor_accepts_openclaw_cli_mode(tmp_path, monkeypatch):
    setup_db(tmp_path)
    monkeypatch.setattr(system_doctor, "openclaw_gateway_reachable", lambda url: True)
    with SessionLocal() as db:
        site = Site(
            name="测试站点",
            slug="test-site",
            homepage_url="https://example.gov.cn/",
            enabled=True,
        )
        db.add(site)
        db.flush()
        for index in range(10):
            db.add(
                SiteSection(
                    site_id=site.id,
                    name=f"栏目{index}",
                    url=f"https://example.gov.cn/list-{index}.html",
                    enabled=True,
                )
            )
        db.commit()

        report = run_system_doctor(
            db,
            settings=Settings(
                APP_STORAGE_ROOT=tmp_path / "storage",
                APP_SECRET_KEY="test-secret-key",
                ADMIN_PASSWORD="test-password",
                OPENCLAW_NOTIFY_MODE="cli",
                WECOM_NOTIFY_TARGET_ID="group:wr123",
            ),
        )

    assert report.failed_count == 0
    assert report.warning_count == 0
    assert any(check.name == "openclaw" and check.status == "ok" for check in report.checks)
    assert any(check.name == "unix_scripts" and check.status == "ok" for check in report.checks)


def test_system_doctor_fails_when_core_tables_are_missing(tmp_path):
    configure_database(f"sqlite:///{tmp_path / 'empty.db'}")

    with SessionLocal() as db:
        report = run_system_doctor(
            db,
            settings=Settings(
                APP_STORAGE_ROOT=tmp_path / "storage",
                APP_SECRET_KEY="test-secret-key",
                ADMIN_PASSWORD="test-password",
                OPENCLAW_NOTIFY_MODE="webhook",
                OPENCLAW_WEBHOOK_URL="",
            ),
        )

    assert report.failed_count >= 1
    assert any(
        check.name == "database_schema"
        and check.status == "fail"
        and "alembic upgrade head" in check.message
        for check in report.checks
    )
