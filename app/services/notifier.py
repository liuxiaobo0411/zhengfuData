from __future__ import annotations

import json
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
        request_url=settings.openclaw_webhook_url or None,
        request_payload=json.dumps(payload, ensure_ascii=False),
    )
    db.add(log)
    db.flush()
    if not settings.openclaw_webhook_url:
        log.status = "failed"
        log.failure_reason = "OPENCLAW_WEBHOOK_URL 未配置"
        db.commit()
        db.refresh(log)
        return log

    try:
        response = httpx.post(settings.openclaw_webhook_url, json=payload, timeout=20)
        log.response_status_code = response.status_code
        log.response_body = response.text[:4000]
        response.raise_for_status()
        log.status = "success"
        log.sent_at = datetime.now()
    except Exception as exc:
        log.status = "failed"
        log.failure_reason = f"{type(exc).__name__}: {exc}"
    db.commit()
    db.refresh(log)
    return log
