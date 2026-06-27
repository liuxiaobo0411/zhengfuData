from __future__ import annotations

from datetime import datetime

import app.models  # noqa: F401
from app.config import Settings
from app.database import Base, SessionLocal, configure_database
from app.models import ChangeLog, CrawlRun, NotificationLog
from app.services.notifier import (
    build_daily_report_payload,
    notification_config_state,
    retry_notification,
    send_daily_report,
)


def setup_db(tmp_path):
    engine = configure_database(f"sqlite:///{tmp_path / 'notify.db'}")
    Base.metadata.create_all(engine)


def seed_run():
    with SessionLocal() as db:
        run = CrawlRun(
            run_no="manual-test",
            run_type="manual",
            status="success",
            started_at=datetime(2026, 6, 21, 9, 0),
            finished_at=datetime(2026, 6, 21, 9, 1),
            discovered_items=3,
            new_items=2,
            content_changed_items=1,
            attachment_added_count=4,
            attachment_changed_count=1,
            attachment_success_count=5,
            attachment_failed_count=1,
        )
        db.add(run)
        db.flush()
        db.add(
            ChangeLog(
                run_id=run.id,
                change_type="new_announcement",
                title="资质核准公告",
                summary="首次抓取入库",
                source_url="https://example.gov.cn/a.html",
            )
        )
        db.commit()


def test_build_daily_report_payload_summarizes_runs(tmp_path):
    setup_db(tmp_path)
    seed_run()

    with SessionLocal() as db:
        payload = build_daily_report_payload(
            db,
            settings=Settings(APP_PUBLIC_BASE_URL="http://localhost:8000"),
            now=datetime(2026, 6, 21, 12, 0),
        )

    assert payload["new_items"] == 2
    assert payload["content_changed_items"] == 1
    assert payload["attachment_added"] == 4
    assert payload["attachment_failed"] == 1
    assert "资质核准公告" in payload["markdown"]
    assert payload["detail_url"] == "http://localhost:8000/crawl-runs/1"


def test_build_daily_report_payload_can_summarize_cross_day_run_batch(tmp_path):
    setup_db(tmp_path)

    with SessionLocal() as db:
        before_midnight = CrawlRun(
            run_no="scheduled-before-midnight",
            run_type="scheduled",
            status="success",
            started_at=datetime(2026, 6, 21, 23, 50),
            finished_at=datetime(2026, 6, 21, 23, 59),
            discovered_items=10,
            new_items=1,
            attachment_success_count=3,
        )
        after_midnight = CrawlRun(
            run_no="scheduled-after-midnight",
            run_type="scheduled",
            status="success",
            started_at=datetime(2026, 6, 22, 0, 5),
            finished_at=datetime(2026, 6, 22, 0, 10),
            discovered_items=20,
            new_items=2,
            content_changed_items=4,
            attachment_success_count=5,
        )
        db.add_all([before_midnight, after_midnight])
        db.flush()
        db.add_all(
            [
                ChangeLog(
                    run_id=before_midnight.id,
                    change_type="new_announcement",
                    title="跨日前新增公告",
                ),
                ChangeLog(
                    run_id=after_midnight.id,
                    change_type="content_changed",
                    title="跨日后正文变化",
                ),
            ]
        )
        run_ids = [before_midnight.id, after_midnight.id]
        db.commit()

    with SessionLocal() as db:
        natural_day_payload = build_daily_report_payload(
            db,
            settings=Settings(APP_PUBLIC_BASE_URL="http://localhost:8000"),
            now=datetime(2026, 6, 22, 0, 30),
        )
        batch_payload = build_daily_report_payload(
            db,
            settings=Settings(APP_PUBLIC_BASE_URL="http://localhost:8000"),
            now=datetime(2026, 6, 22, 0, 30),
            run_ids=run_ids,
        )

    assert natural_day_payload["runs"] == 1
    assert natural_day_payload["new_items"] == 2
    assert batch_payload["runs"] == 2
    assert batch_payload["new_items"] == 3
    assert batch_payload["content_changed_items"] == 4
    assert batch_payload["attachment_success"] == 8
    assert "跨日前新增公告" in batch_payload["markdown"]
    assert "跨日后正文变化" in batch_payload["markdown"]


def test_send_daily_report_records_missing_webhook_failure(tmp_path):
    setup_db(tmp_path)
    seed_run()

    with SessionLocal() as db:
        log = send_daily_report(
            db,
            settings=Settings(OPENCLAW_NOTIFY_MODE="webhook", OPENCLAW_WEBHOOK_URL=""),
            now=datetime(2026, 6, 21, 12, 0),
        )

    assert log.status == "failed"
    assert "OPENCLAW_WEBHOOK_URL" in log.failure_reason
    with SessionLocal() as db:
        assert db.query(NotificationLog).count() == 1


def test_notification_config_state_supports_webhook_and_cli_modes():
    webhook_state = notification_config_state(
        Settings(OPENCLAW_NOTIFY_MODE="webhook", OPENCLAW_WEBHOOK_URL="https://openclaw.local")
    )
    assert webhook_state.configured is True
    assert webhook_state.mode == "webhook"
    assert "OPENCLAW_WEBHOOK_URL 已配置" in webhook_state.detail

    cli_state = notification_config_state(
        Settings(OPENCLAW_NOTIFY_MODE="cli", WECOM_NOTIFY_TARGET_ID="group:wr123")
    )
    assert cli_state.configured is True
    assert cli_state.mode == "cli"
    assert "企微目标已配置" in cli_state.detail

    missing_cli_state = notification_config_state(
        Settings(OPENCLAW_NOTIFY_MODE="cli", WECOM_NOTIFY_TARGET_ID="")
    )
    assert missing_cli_state.configured is False
    assert "WECOM_NOTIFY_TARGET_ID" in missing_cli_state.detail


def test_send_daily_report_posts_to_openclaw(tmp_path, monkeypatch):
    setup_db(tmp_path)
    seed_run()
    sent = {}

    class FakeResponse:
        status_code = 200
        text = "ok"

        def raise_for_status(self):
            return None

    def fake_post(url, json, timeout):
        sent["url"] = url
        sent["json"] = json
        sent["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("app.services.notifier.httpx.post", fake_post)
    with SessionLocal() as db:
        log = send_daily_report(
            db,
            settings=Settings(
                OPENCLAW_NOTIFY_MODE="webhook",
                OPENCLAW_WEBHOOK_URL="http://openclaw.local/webhook",
            ),
            now=datetime(2026, 6, 21, 12, 0),
        )

    assert log.status == "success"
    assert sent["url"] == "http://openclaw.local/webhook"
    assert sent["json"]["event_type"] == "daily_crawl_report"


def test_send_daily_report_sends_via_openclaw_cli(tmp_path, monkeypatch):
    setup_db(tmp_path)
    seed_run()
    calls = []

    class FakeCompleted:
        returncode = 0
        stdout = '{"ok":true}'
        stderr = ""

    def fake_run(command, capture_output, check, text, timeout):
        calls.append(
            {
                "command": command,
                "capture_output": capture_output,
                "check": check,
                "text": text,
                "timeout": timeout,
            }
        )
        return FakeCompleted()

    monkeypatch.setattr("app.services.notifier.subprocess.run", fake_run)
    with SessionLocal() as db:
        log = send_daily_report(
            db,
            settings=Settings(
                OPENCLAW_NOTIFY_MODE="cli",
                OPENCLAW_CLI_COMMAND="openclaw",
                WECOM_NOTIFY_TARGET_ID="group:wr123",
            ),
            now=datetime(2026, 6, 21, 12, 0),
        )

    assert log.status == "success"
    assert log.request_url == "openclaw-cli://wecom/wr123"
    assert calls[0]["command"][:5] == ["openclaw", "message", "send", "--channel", "wecom"]
    assert calls[0]["command"][calls[0]["command"].index("--target") + 1] == "wr123"
    assert (
        "建筑资质公开信息抓取日报"
        in calls[0]["command"][calls[0]["command"].index("--message") + 1]
    )


def test_send_daily_report_cli_requires_target(tmp_path):
    setup_db(tmp_path)
    seed_run()

    with SessionLocal() as db:
        log = send_daily_report(
            db,
            settings=Settings(OPENCLAW_NOTIFY_MODE="cli", WECOM_NOTIFY_TARGET_ID=""),
            now=datetime(2026, 6, 21, 12, 0),
        )

    assert log.status == "failed"
    assert "WECOM_NOTIFY_TARGET_ID" in log.failure_reason


def test_send_daily_report_retries_openclaw_failures(tmp_path, monkeypatch):
    setup_db(tmp_path)
    seed_run()
    attempts = []

    class FailingResponse:
        status_code = 500
        text = "server error"

        def raise_for_status(self):
            raise RuntimeError("server error")

    class SuccessResponse:
        status_code = 200
        text = "ok"

        def raise_for_status(self):
            return None

    def fake_post(url, json, timeout):
        attempts.append(url)
        if len(attempts) == 1:
            return FailingResponse()
        return SuccessResponse()

    monkeypatch.setattr("app.services.notifier.httpx.post", fake_post)
    with SessionLocal() as db:
        log = send_daily_report(
            db,
            settings=Settings(
                OPENCLAW_NOTIFY_MODE="webhook",
                OPENCLAW_WEBHOOK_URL="http://openclaw.local/webhook",
                OPENCLAW_NOTIFY_RETRY_TIMES=2,
            ),
            now=datetime(2026, 6, 21, 12, 0),
        )

    assert log.status == "success"
    assert len(attempts) == 2


def test_retry_notification_creates_new_log_from_original_payload(tmp_path, monkeypatch):
    setup_db(tmp_path)
    seed_run()
    sent = {}

    class FakeResponse:
        status_code = 200
        text = "ok"

        def raise_for_status(self):
            return None

    def fake_post(url, json, timeout):
        sent["url"] = url
        sent["json"] = json
        return FakeResponse()

    monkeypatch.setattr("app.services.notifier.httpx.post", fake_post)
    with SessionLocal() as db:
        original = NotificationLog(
            run_id=1,
            provider="openclaw",
            event_type="daily_crawl_report",
            target_type="group",
            target_id="chatid",
            status="failed",
            request_url="http://old.example/webhook",
            request_payload='{"text": "hello"}',
            failure_reason="timeout",
        )
        db.add(original)
        db.commit()

        retry_log = retry_notification(
            db,
            original.id,
            settings=Settings(OPENCLAW_NOTIFY_MODE="webhook", OPENCLAW_WEBHOOK_URL=""),
        )

        assert retry_log is not None
        assert retry_log.id != original.id
        assert retry_log.status == "success"
        assert sent["url"] == "http://old.example/webhook"
        assert sent["json"] == {"text": "hello"}
        assert db.query(NotificationLog).count() == 2
