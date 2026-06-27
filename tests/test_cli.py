from __future__ import annotations

from datetime import datetime, time

import app.cli as cli
import app.models  # noqa: F401
from app.config import get_settings
from app.database import Base, configure_database
from app.services.kb import ParseSummary
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


def test_kb_search_prints_results(tmp_path, monkeypatch, capsys):
    setup_db(tmp_path, monkeypatch)

    class Result:
        entity_type = "announcement"
        entity_id = 1
        score = 120
        title = "建筑业企业资质延续公告"
        snippet = "资质延续"
        source_url = "https://example.gov.cn/a.html"

    calls = []

    def fake_search_knowledge(
        db,
        query,
        limit,
        entity_type=None,
        site_name=None,
        published_from=None,
        published_to=None,
    ):
        calls.append(
            {
                "query": query,
                "limit": limit,
                "entity_type": entity_type,
                "site_name": site_name,
                "published_from": published_from,
                "published_to": published_to,
            }
        )
        return [Result()]

    monkeypatch.setattr(cli, "search_knowledge", fake_search_knowledge)

    cli.kb_search(
        "资质延续",
        limit=5,
        entity_type="attachment",
        site_name="陕西省住房和城乡建设厅",
        published_from="2026-06-23",
        published_to="2026-06-25",
    )

    output = capsys.readouterr().out
    assert "announcement#1" in output
    assert "建筑业企业资质延续公告" in output
    assert "summary total=1" in output
    assert calls == [
        {
            "query": "资质延续",
            "limit": 5,
            "entity_type": "attachment",
            "site_name": "陕西省住房和城乡建设厅",
            "published_from": datetime(2026, 6, 23, 0, 0),
            "published_to": datetime.combine(datetime(2026, 6, 25).date(), time.max),
        }
    ]


def test_kb_search_rejects_invalid_date(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)

    try:
        cli.kb_search("资质", limit=5, published_from="2026/06/23")
    except SystemExit as exc:
        assert "日期格式应为 YYYY-MM-DD" in str(exc)
    else:
        raise AssertionError("kb_search should exit on invalid date")


def test_kb_search_rejects_invalid_entity_type(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)

    try:
        cli.kb_search("资质", limit=5, entity_type="unknown")
    except SystemExit as exc:
        assert "entity-type 仅支持" in str(exc)
    else:
        raise AssertionError("kb_search should exit on invalid entity type")


def test_kb_search_rejects_reversed_date_range(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)

    try:
        cli.kb_search(
            "资质",
            limit=5,
            published_from="2026-06-25",
            published_to="2026-06-23",
        )
    except SystemExit as exc:
        assert "published-from 不能晚于 published-to" in str(exc)
    else:
        raise AssertionError("kb_search should exit on reversed date range")


def test_kb_ask_prints_answer(tmp_path, monkeypatch, capsys):
    setup_db(tmp_path, monkeypatch)

    def fake_ask_knowledge(db, question, limit):
        return {
            "answer": "找到 1 条相关信息",
            "items": [{"title": "资质公告", "source_url": "https://example.gov.cn/a.html"}],
        }

    monkeypatch.setattr(cli, "ask_knowledge", fake_ask_knowledge)

    cli.kb_ask("资质", limit=5)

    output = capsys.readouterr().out
    assert "找到 1 条相关信息" in output
    assert "资质公告" in output


def test_run_daily_prints_attachment_parse_summary(tmp_path, monkeypatch, capsys):
    setup_db(tmp_path, monkeypatch)

    class Result:
        section_ids = [1]
        runs = []
        notification = None
        parse_summary = ParseSummary(total=3, success=2, failed=0, unsupported=1)
        success_count = 1
        partial_count = 0
        failed_count = 0

    def fake_run_daily_crawl(settings, limit, notify, triggered_by):
        assert limit == 2
        assert notify is False
        assert triggered_by == "cli_daily"
        return Result()

    monkeypatch.setattr(cli, "run_daily_crawl", fake_run_daily_crawl)

    cli.run_daily(limit=2, notify=False)

    output = capsys.readouterr().out
    assert "daily sections=1 success=1 partial=0 failed=0" in output
    assert "parse total=3 success=2 failed=0 unsupported=1" in output
