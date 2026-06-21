from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import (
    Announcement,
    Attachment,
    AttachmentVersion,
    CrawlRun,
    NotificationLog,
    Site,
    SiteSection,
)
from app.services.storage import prepare_storage
from app.services.system_doctor import run_system_doctor


@dataclass(frozen=True)
class AcceptanceReport:
    path: Path
    markdown: str


@dataclass(frozen=True)
class FullDailyCrawlSummary:
    total_sections: int
    success_sections: int
    partial_sections: int
    failed_sections: int
    discovered_items: int
    new_items: int
    attachment_success_count: int
    attachment_failed_count: int


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
    attachment_version_count = count_rows(db, AttachmentVersion.id)
    run_count = count_rows(db, CrawlRun.id)
    notification_count = count_rows(db, NotificationLog.id)
    recent_runs = list(db.scalars(select(CrawlRun).order_by(CrawlRun.id.desc()).limit(5)).all())
    recent_notifications = list(
        db.scalars(select(NotificationLog).order_by(NotificationLog.id.desc()).limit(5)).all()
    )
    failed_runs = list(
        db.scalars(
            select(CrawlRun)
            .where(CrawlRun.status == "failed")
            .order_by(CrawlRun.id.desc())
            .limit(10)
        ).all()
    )
    failed_attachments = list(
        db.scalars(
            select(Attachment)
            .where(Attachment.download_status == "failed")
            .order_by(Attachment.id.desc())
            .limit(10)
        ).all()
    )
    failed_notifications = list(
        db.scalars(
            select(NotificationLog)
            .where(NotificationLog.status == "failed")
            .order_by(NotificationLog.id.desc())
            .limit(10)
        ).all()
    )
    attachment_status = db.execute(
        select(Attachment.download_status, func.count(Attachment.id))
        .group_by(Attachment.download_status)
        .order_by(Attachment.download_status)
    ).all()
    full_daily_summary = latest_full_daily_summary(db, enabled_section_count)
    doctor_report = run_system_doctor(db, settings=settings)
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
        f"- 附件版本：{attachment_version_count}",
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

    lines.extend(["", "## 部署自检摘要", ""])
    lines.append(
        f"- 汇总：ok={doctor_report.ok_count} warn={doctor_report.warning_count} "
        f"fail={doctor_report.failed_count}"
    )
    for check in doctor_report.checks:
        lines.append(f"- {check.status.upper()} {check.name}：{check.message}")

    lines.extend(["", "## 后台页面验收入口", ""])
    for label, path in backend_checkpoints():
        lines.append(f"- {label}：`{settings.app_public_base_url.rstrip('/')}{path}`")

    lines.extend(["", "## 失败来源与处理建议", ""])
    if not failed_runs and not failed_attachments and not failed_notifications:
        lines.append("- 当前没有失败任务、失败附件或失败通知。")
    else:
        if failed_runs:
            lines.append("")
            lines.append("### 失败抓取任务")
            for run in failed_runs:
                lines.append(
                    f"- #{run.id} `{run.run_no}` {run.error_summary or '无失败摘要'} "
                    "建议：查看任务详情和来源栏目，必要时调整请求头、重试次数或抓取策略。"
                )
        if failed_attachments:
            lines.append("")
            lines.append("### 失败附件")
            for attachment in failed_attachments:
                lines.append(
                    f"- #{attachment.id} {attachment.name} url={attachment.source_url} "
                    f"reason={attachment.failure_reason or '无失败原因'} "
                    "建议：在附件管理页点击重试，或打开原始地址确认网站限制。"
                )
        if failed_notifications:
            lines.append("")
            lines.append("### 失败通知")
            for log in failed_notifications:
                lines.append(
                    f"- #{log.id} {log.provider} {log.event_type} "
                    f"reason={log.failure_reason or '无失败原因'} "
                    "建议：检查 OPENCLAW_WEBHOOK_URL、企微目标配置和 OpenClaw 服务状态。"
                )

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
            f"- {enabled_section_count} 个启用栏目的完整每日任务："
            f"{format_full_daily_summary(full_daily_summary)}",
            "",
            "## 后续待验收",
            "",
            "- Windows 实机安装和运行。",
            "- 真实 OpenClaw webhook 企微群日报发送。",
        ]
    )
    if not full_daily_summary_passed(full_daily_summary):
        lines.append(f"- {enabled_section_count} 个启用栏目的完整每日任务验收。")
    lines.append("- 动态查询页面 Playwright 或接口适配。")
    return "\n".join(lines) + "\n"


def count_rows(db: Session, column, *conditions) -> int:
    query = select(func.count(column))
    for condition in conditions:
        query = query.where(condition)
    return int(db.scalar(query) or 0)


def secret_state(value: str) -> str:
    return "已配置" if value else "未配置"


def latest_full_daily_summary(
    db: Session,
    enabled_section_count: int,
) -> FullDailyCrawlSummary | None:
    if enabled_section_count <= 0:
        return None
    recent_daily_runs = list(
        db.scalars(
            select(CrawlRun)
            .where(CrawlRun.triggered_by == "cli_daily")
            .order_by(CrawlRun.id.desc())
            .limit(enabled_section_count)
        ).all()
    )
    if len(recent_daily_runs) < enabled_section_count:
        return None
    section_ids = {section_id_from_run_no(run.run_no) for run in recent_daily_runs}
    if None in section_ids or len(section_ids) < enabled_section_count:
        return None
    return FullDailyCrawlSummary(
        total_sections=len(recent_daily_runs),
        success_sections=sum(run.status == "success" for run in recent_daily_runs),
        partial_sections=sum(run.status == "partial_success" for run in recent_daily_runs),
        failed_sections=sum(run.status == "failed" for run in recent_daily_runs),
        discovered_items=sum(run.discovered_items for run in recent_daily_runs),
        new_items=sum(run.new_items for run in recent_daily_runs),
        attachment_success_count=sum(run.attachment_success_count for run in recent_daily_runs),
        attachment_failed_count=sum(run.attachment_failed_count for run in recent_daily_runs),
    )


def section_id_from_run_no(run_no: str) -> int | None:
    try:
        return int(run_no.rsplit("-", 1)[-1])
    except ValueError:
        return None


def format_full_daily_summary(summary: FullDailyCrawlSummary | None) -> str:
    if summary is None:
        return "待验收"
    state = "已完成" if full_daily_summary_passed(summary) else "已执行但有失败"
    return (
        f"{state} success={summary.success_sections} partial={summary.partial_sections} "
        f"failed={summary.failed_sections} "
        f"discovered={summary.discovered_items} new={summary.new_items} "
        f"attachments={summary.attachment_success_count}/{summary.attachment_failed_count}"
    )


def full_daily_summary_passed(summary: FullDailyCrawlSummary | None) -> bool:
    if summary is None:
        return False
    return (
        summary.success_sections == summary.total_sections
        and summary.partial_sections == 0
        and summary.failed_sections == 0
    )


def backend_checkpoints() -> list[tuple[str, str]]:
    return [
        ("工作台", "/"),
        ("公告列表", "/announcements"),
        ("变化记录", "/changes"),
        ("附件管理", "/attachments"),
        ("抓取任务", "/crawl-runs"),
        ("通知日志", "/notifications"),
        ("网站栏目", "/sites"),
        ("系统配置", "/settings"),
    ]
