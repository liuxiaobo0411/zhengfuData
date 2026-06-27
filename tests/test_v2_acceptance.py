from __future__ import annotations

import app.models  # noqa: F401
from app.config import Settings, get_settings
from app.database import Base, configure_database
from app.services.v2_acceptance import check_api_and_web


def setup_db(tmp_path, monkeypatch):
    engine = configure_database(f"sqlite:///{tmp_path / 'v2_acceptance.db'}")
    Base.metadata.create_all(engine)
    monkeypatch.setenv("APP_STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ADMIN_PASSWORD", "test-password")
    get_settings.cache_clear()


def test_v2_api_and_web_acceptance_covers_search_filters(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)

    checks = check_api_and_web(
        Settings(APP_SECRET_KEY="test-secret-key", ADMIN_PASSWORD="test-password")
    )

    states = {check.name: check.status for check in checks}
    assert states["api_kb_search_filters"] == "ok"
    assert states["api_kb_search_invalid_filter"] == "ok"
