from __future__ import annotations

import app.cli as cli
import app.models  # noqa: F401
from app.config import get_settings
from app.database import Base, configure_database
from app.services.source_validator import SourceValidationResult, SourceValidationSummary


def setup_db(tmp_path, monkeypatch):
    engine = configure_database(f"sqlite:///{tmp_path / 'cli.db'}")
    Base.metadata.create_all(engine)
    monkeypatch.setenv("APP_STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ADMIN_PASSWORD", "test-password")
    get_settings.cache_clear()


def test_acceptance_check_can_skip_source_validation(tmp_path, monkeypatch, capsys):
    setup_db(tmp_path, monkeypatch)

    cli.acceptance_check(source_limit=2, skip_source_validation=True)

    output = capsys.readouterr().out
    assert "系统自检结果" in output
    assert "acceptance_report=" in output
    assert "source_validation=skipped" in output


def test_acceptance_check_fails_when_source_validation_fails(tmp_path, monkeypatch, capsys):
    setup_db(tmp_path, monkeypatch)

    def fake_validate_enabled_sources(limit: int = 0):
        assert limit == 2
        return SourceValidationSummary(
            results=[
                SourceValidationResult(
                    section_id=1,
                    section_name="失败栏目",
                    strategy="http_with_retry",
                    status="failed",
                    failure_reason="timeout",
                )
            ]
        )

    monkeypatch.setattr(cli, "validate_enabled_sources", fake_validate_enabled_sources)

    try:
        cli.acceptance_check(source_limit=2)
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("acceptance_check should exit when source validation fails")

    output = capsys.readouterr().out
    assert "FAIL section=1" in output
    assert "failed=1" in output
