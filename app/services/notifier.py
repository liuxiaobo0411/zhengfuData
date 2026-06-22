from __future__ import annotations

import json
import subprocess
from datetime import datetime, time
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import ChangeLog, CrawlRun, NotificationLog


def build_daily_report_payload(
    db: Session,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    now = now or datetime.now()
    day_start = datetime.combine(now.date(), time.min)
    runs = list(
        db.scalars(
            select(CrawlRun)
            .where(CrawlRun.started_at >= day_start)
            .order_by(CrawlRun.started_at.desc(), CrawlRun.id.desc())
        )
    )
    latest_run = runs[0] if runs else None
    top_changes = db.scalars(
        select(ChangeLog)
        .where(ChangeLog.created_at >= day_start)
        .order_by(ChangeLog.created_at.desc(), ChangeLog.id.desc())
        .limit(10)
    ).all()
    failure_count = db.scalar(
        select(func.count(ChangeLog.id))
        .where(ChangeLog.created_at >= day_start)
        .where(ChangeLog.change_type.in_(["crawl_failed", "attachment_failed"]))
    )
    totals = {
        "runs": len(runs),
        "success_runs": sum(1 for run in runs if run.status == "success"),
        "failed_runs": sum(1 for run in runs if run.status == "failed"),
        "new_items": sum(run.new_items for run in runs),
        "content_changed_items": sum(run.content_changed_items for run in runs),
        "attachment_added": sum(run.attachment_added_count for run in runs),
        "attachment_changed": sum(run.attachment_changed_count for run in runs),
        "attachment_success": sum(run.attachment_success_count for run in runs),
        "attachment_failed": sum(run.attachment_failed_count for run in runs),
        "failures": int(failure_count or 0),
    }
    detail_url = (
        f"{settings.app_public_base_url.rstrip('/')}/crawl-runs/{latest_run.id}"
        if latest_run
        else f"{settings.app_public_base_url.rstrip('/')}/crawl-runs"
    )
    top_items = [
        {
            "title": change.title,
            "change_type": change.change_type,
            "summary": change.summary,
            "url": change.source_url,
        }
        for change in top_changes
    ]
    markdown = render_markdown_report(now, totals, detail_url, top_items)
    return {
        "event_type": "daily_crawl_report",
        "finished_at": now.isoformat(timespec="seconds"),
        "status": (
            "success"
            if totals["failed_runs"] == 0 and totals["failures"] == 0
            else "partial_success"
        ),
        "target_type": settings.wecom_notify_target_type,
        "target_id": settings.wecom_notify_target_id,
        "detail_url": detail_url,
        **totals,
        "top_items": top_items,
        "markdown": markdown,
        "text": markdown,
    }


def render_markdown_report(
    now: datetime,
    totals: dict[str, int],
    detail_url: str,
    top_items: list[dict[str, Any]],
) -> str:
    lines = [
        f"### 建筑资质公开信息抓取日报 {now.date().isoformat()}",
        "",
        (
            f"- 抓取任务：{totals['runs']}，成功 {totals['success_runs']}，"
            f"失败 {totals['failed_runs']}"
        ),
        f"- 新增公告：{totals['new_items']}",
        f"- 正文变化：{totals['content_changed_items']}",
        f"- 附件新增：{totals['attachment_added']}，附件变化：{totals['attachment_changed']}",
        f"- 附件下载：成功 {totals['attachment_success']}，失败 {totals['attachment_failed']}",
        f"- 失败事件：{totals['failures']}",
        f"- 后台入口：{detail_url}",
    ]
    if top_items:
        lines.append("")
        lines.append("#### 最新变化")
        for item in top_items[:5]:
            title = item.get("title") or "-"
            change_type = item.get("change_type") or "-"
            lines.append(f"- [{change_type}] {title}")
    return "\n".join(lines)


def send_daily_report(
    db: Session,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> NotificationLog:
    settings = settings or get_settings()
    payload = build_daily_report_payload(db, settings=settings, now=now)
    latest_run = db.scalar(select(CrawlRun).order_by(CrawlRun.id.desc()))
    log = NotificationLog(
        run_id=latest_run.id if latest_run else None,
        provider="openclaw",
        event_type="daily_crawl_report",
        target_type=settings.wecom_notify_target_type,
        target_id=settings.wecom_notify_target_id,
        status="pending",
        request_url=notification_request_url(settings),
        request_payload=json.dumps(payload, ensure_ascii=False),
    )
    db.add(log)
    db.flush()
    return dispatch_openclaw_notification(db, log, payload, settings=settings)


def retry_notification(
    db: Session,
    notification_id: int,
    settings: Settings | None = None,
) -> NotificationLog | None:
    settings = settings or get_settings()
    original = db.get(NotificationLog, notification_id)
    if original is None:
        return None

    payload = parse_payload(original.request_payload)
    retry_log = NotificationLog(
        run_id=original.run_id,
        provider=original.provider,
        event_type=original.event_type,
        target_type=original.target_type or settings.wecom_notify_target_type,
        target_id=original.target_id or settings.wecom_notify_target_id,
        status="pending",
        request_url=notification_request_url(settings) or original.request_url,
        request_payload=json.dumps(payload, ensure_ascii=False),
    )
    db.add(retry_log)
    db.flush()
    return dispatch_openclaw_notification(db, retry_log, payload, settings=settings)


def parse_payload(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {"text": value}
    return payload if isinstance(payload, dict) else {"text": payload}


def notification_request_url(settings: Settings) -> str | None:
    if settings.openclaw_notify_mode == "cli":
        target = settings.wecom_notify_target_id.strip()
        return f"openclaw-cli://wecom/{target}" if target else None
    return settings.openclaw_webhook_url or None


def dispatch_openclaw_notification(
    db: Session,
    log: NotificationLog,
    payload: dict[str, Any],
    settings: Settings,
) -> NotificationLog:
    if settings.openclaw_notify_mode == "cli":
        return dispatch_openclaw_cli_notification(db, log, payload, settings=settings)

    request_url = settings.openclaw_webhook_url or log.request_url
    if not request_url:
        log.status = "failed"
        log.failure_reason = "OPENCLAW_WEBHOOK_URL 未配置"
        db.commit()
        db.refresh(log)
        return log

    log.request_url = request_url
    total_attempts = max(1, settings.openclaw_notify_retry_times + 1)
    last_error = ""
    for _attempt in range(1, total_attempts + 1):
        try:
            response = httpx.post(request_url, json=payload, timeout=20)
            log.response_status_code = response.status_code
            log.response_body = response.text[:4000]
            response.raise_for_status()
            log.status = "success"
            log.sent_at = datetime.now()
            log.failure_reason = None
            db.commit()
            db.refresh(log)
            return log
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"

    log.status = "failed"
    log.failure_reason = f"发送失败，已尝试 {total_attempts} 次；最后错误：{last_error}"
    db.commit()
    db.refresh(log)
    return log


def dispatch_openclaw_cli_notification(
    db: Session,
    log: NotificationLog,
    payload: dict[str, Any],
    settings: Settings,
) -> NotificationLog:
    target = settings.wecom_notify_target_id.strip()
    if not target:
        log.status = "failed"
        log.failure_reason = (
            "WECOM_NOTIFY_TARGET_ID 未配置；CLI 模式需要 group:<chatid> 或 user:<userid>"
        )
        db.commit()
        db.refresh(log)
        return log

    log.request_url = f"openclaw-cli://wecom/{target}"
    total_attempts = max(1, settings.openclaw_notify_retry_times + 1)
    message = str(payload.get("markdown") or payload.get("text") or "")
    last_error = ""
    for _attempt in range(1, total_attempts + 1):
        try:
            completed = subprocess.run(
                [
                    settings.openclaw_cli_command,
                    "message",
                    "send",
                    "--channel",
                    "wecom",
                    "--target",
                    target,
                    "--message",
                    message,
                    "--json",
                ],
                capture_output=True,
                check=False,
                text=True,
                timeout=60,
            )
            log.response_status_code = completed.returncode
            log.response_body = (completed.stdout + completed.stderr)[:4000]
            if completed.returncode == 0:
                log.status = "success"
                log.sent_at = datetime.now()
                log.failure_reason = None
                db.commit()
                db.refresh(log)
                return log
            last_error = f"openclaw CLI exit {completed.returncode}: {log.response_body}"
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"

    log.status = "failed"
    log.failure_reason = f"发送失败，已尝试 {total_attempts} 次；最后错误：{last_error}"
    db.commit()
    db.refresh(log)
    return log
