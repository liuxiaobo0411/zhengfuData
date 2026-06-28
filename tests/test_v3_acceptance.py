from __future__ import annotations

import app.models  # noqa: F401
from app.config import Settings, get_settings
from app.database import Base, SessionLocal, configure_database
from app.models import Enterprise, QualificationStandard
from app.services.v3_acceptance import run_v3_acceptance_check, v3_stats


def setup_db(tmp_path, monkeypatch):
    engine = configure_database(f"sqlite:///{tmp_path / 'v3_acceptance.db'}")
    Base.metadata.create_all(engine)
    monkeypatch.setenv("APP_STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ADMIN_PASSWORD", "test-password")
    get_settings.cache_clear()


def test_v3_acceptance_check_seeds_and_reports_local_data(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)

    with SessionLocal() as db:
        report = run_v3_acceptance_check(
            db,
            Settings(APP_SECRET_KEY="test-secret-key", ADMIN_PASSWORD="test-password"),
        )
        stats = v3_stats(db)

    assert report.failed_count == 0
    assert report.passed_count == 3
    assert report.path is not None
    assert "v3_1_acceptance_report_" in report.path
    assert stats["qualification_standards"] == 1
    assert stats["enterprises"] == 1

    with SessionLocal() as db:
        assert db.query(QualificationStandard).first().conditions
        assert db.query(Enterprise).first().qualifications
