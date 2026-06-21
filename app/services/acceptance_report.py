from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import Announcement, Attachment, CrawlRun, NotificationLog, Site, SiteSection
from app.services.storage import prepare_storage


@dataclass(frozen=True)
class AcceptanceReport:
    path: Path
    markdown: str


def export_acceptance_report(
    db: Session,
    settings: Settings | None = None,
    output_path: Path | None = None,
    now: datetime | None = None,
) -> AcceptanceReport:
    settings = settings or get_settings()
    storage = prepare_storage(settings)
    now = now or datetime.now()
    markdown = render_acceptance_report(db, settings=settings, now=now)
    target = output_path or (
        storage.exports / f"v1_acceptance_report_{now.strftime('%Y%m%d_%H%M%S')}.md"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8")
    return AcceptanceReport(path=target, markdown=markdown)


def render_acceptance_report(
    db: Session,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> str:
    settings = settings or get_settings()
    now = now or datetime.now()
    site_count = count_rows(db, Site.id)
    section_count = count_rows(db, SiteSection.id)
    enabled_section_count = count_rows(db, SiteSection.id, SiteSection.enabled.is_(True))
    announcement_count = count_rows(db, Announcement.id)
    attachment_count = count_rows(db, Attachment.id)
    run_count = count_rows(db, CrawlRun.id)
    notification_count = count_rows(db, NotificationLog.id)
    recent_runs = list(db.scalars(select(CrawlRun).order_by(CrawlRun.id.desc()).limit(5)).all())
    recent_notifications = list(
        db.scalars(select(NotificationLog).order_by(NotificationLog.id.desc()).limit(5)).all()
    )
    attachment_status = db.execute(
        select(Attachment.download_status, func.count(Attachment.id))
        .group_by(Attachment.download_status)
        .order_by(Attachment.download_status)
    ).all()
    lines = [
        "# V1 MVP 自动验收报告",
        "",
        f"生成时间：{now.isoformat(timespec='seconds')}",
        "",
        "## 环境",
        "",
        f"- APP_ENV：{settings.app_env}",
        f"- 数据库：`{settings.app_database_url}`",
        f"- storage：`{settings.storage_root}`",
        f"- public base url：`{settings.app_public_base_url}`",
        "",
        "## 配置概览",
        "",
        f"- 政府网站：{site_count}",
        f"- 栏目总数：{section_count}",
        f"- 启用栏目：{enabled_section_count}",
        f"- OpenClaw webhook：{secret_state(settings.openclaw_webhook_url)}",
        f"- 每日调度：{'启用' if settings.app_scheduler_enabled else '未启用'} "
        f"{settings.app_scheduler_daily_time} {settings.app_timezone}",
        "",
        "## 数据概览",
        "",
        f"- 抓取任务：{run_count}",
        f"- 归档公告：{announcement_count}",
        f"- 附件记录：{attachment_count}",
        f"- 通知日志：{notification_count}",
        "",
        "## 附件下载状态",
        "",
    ]
    if attachment_status:
        lines.extend(f"- {status or 'unknown'}：{count}" for status, count in attachment_status)
    else:
        lines.append("- 暂无附件记录")

    lines.extend(["", "## 最近抓取任务", ""])
    if recent_runs:
        for run in recent_runs:
            lines.append(
                f"- #{run.id} `{run.run_no}` {run.status} type={run.run_type} "
                f"discovered={run.discovered_items} new={run.new_items} "
                f"attachments={run.attachment_success_count}/{run.attachment_failed_count}"
            )
    else:
        lines.append("- 暂无抓取任务")

    lines.extend(["", "## 最近通知日志", ""])
    if recent_notifications:
        for log in recent_notifications:
            reason = f" reason={log.failure_reason}" if log.failure_reason else ""
            lines.append(f"- #{log.id} {log.provider} {log.event_type} {log.status}{reason}")
    else:
        lines.append("- 暂无通知日志")

    lines.extend(
        [
            "",
            "## V1 验收关注项",
            "",
            f"- 首批启用栏目是否不少于 10：{'是' if enabled_section_count >= 10 else '否'}",
            f"- 是否已有抓取任务：{'是' if run_count > 0 else '否'}",
            f"- 是否已有公告归档：{'是' if announcement_count > 0 else '否'}",
            f"- 是否已有附件记录：{'是' if attachment_count > 0 else '否'}",
            f"- 是否已有通知日志：{'是' if notification_count > 0 else '否'}",
            "",
            "## 后续待验收",
            "",
            "- Windows 实机安装和运行。",
            "- 真实 OpenClaw webhook 企微群日报发送。",
            "- 12 个启用栏目的完整每日任务验收。",
            "- 动态查询页面 Playwright 或接口适配。",
        ]
    )
    return "\n".join(lines) + "\n"


def count_rows(db: Session, column, *conditions) -> int:
    query = select(func.count(column))
    for condition in conditions:
        query = query.where(condition)
    return int(db.scalar(query) or 0)


def secret_state(value: str) -> str:
    return "已配置" if value else "未配置"
