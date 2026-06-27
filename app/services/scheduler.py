from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import SessionLocal
from app.models import CrawlRun, NotificationLog, Site, SiteSection
from app.services.crawler import crawl_section
from app.services.kb import ParseSummary, parse_attachments
from app.services.notifier import send_daily_report


@dataclass(frozen=True)
class DailyCrawlResult:
    section_ids: list[int]
    runs: list[CrawlRun]
    notification: NotificationLog | None
    parse_summary: ParseSummary | None = None

    @property
    def success_count(self) -> int:
        return sum(1 for run in self.runs if run.status == "success")

    @property
    def partial_count(self) -> int:
        return sum(1 for run in self.runs if run.status == "partial_success")

    @property
    def failed_count(self) -> int:
        return sum(1 for run in self.runs if run.status == "failed")


_scheduler: BackgroundScheduler | None = None


def run_daily_crawl(
    settings: Settings | None = None,
    *,
    limit: int = 0,
    notify: bool = True,
    triggered_by: str = "scheduled",
) -> DailyCrawlResult:
    settings = settings or get_settings()
    with SessionLocal() as db:
        section_ids = enabled_section_ids(db)
        if limit > 0:
            section_ids = section_ids[:limit]

        runs = [
            crawl_section(db, section_id, triggered_by=triggered_by, settings=settings)
            for section_id in section_ids
        ]
        parse_summary = (
            parse_attachments(db, limit=settings.kb_parse_batch_limit, settings=settings)
            if settings.kb_enable_attachment_parse
            else None
        )
        notification = (
            send_daily_report(db, settings=settings, run_ids=[run.id for run in runs])
            if notify
            else None
        )

    return DailyCrawlResult(
        section_ids=section_ids,
        runs=runs,
        notification=notification,
        parse_summary=parse_summary,
    )


def enabled_section_ids(db: Session) -> list[int]:
    return list(
        db.scalars(
            select(SiteSection.id)
            .join(Site, Site.id == SiteSection.site_id)
            .where(Site.enabled.is_(True))
            .where(SiteSection.enabled.is_(True))
            .order_by(SiteSection.id)
        ).all()
    )


def start_scheduler(settings: Settings | None = None) -> BackgroundScheduler | None:
    global _scheduler

    settings = settings or get_settings()
    if not settings.app_scheduler_enabled:
        return None
    if _scheduler and _scheduler.running:
        return _scheduler

    hour, minute = parse_daily_time(settings.app_scheduler_daily_time)
    scheduler = BackgroundScheduler(timezone=timezone_for(settings.app_timezone))
    scheduler.add_job(
        run_daily_crawl,
        trigger=CronTrigger(hour=hour, minute=minute),
        id="daily-crawl",
        name="每日政府公开信息抓取",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        kwargs={"settings": settings, "notify": True, "triggered_by": "scheduled"},
    )
    scheduler.start()
    _scheduler = scheduler
    return scheduler


def stop_scheduler() -> None:
    global _scheduler

    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None


def scheduler_status(settings: Settings | None = None) -> dict[str, str | bool | None]:
    settings = settings or get_settings()
    if not _scheduler:
        return {
            "enabled": settings.app_scheduler_enabled,
            "running": False,
            "daily_time": settings.app_scheduler_daily_time,
            "timezone": settings.app_timezone,
            "next_run_at": None,
        }

    jobs = _scheduler.get_jobs()
    next_run_at = jobs[0].next_run_time.isoformat() if jobs and jobs[0].next_run_time else None
    return {
        "enabled": settings.app_scheduler_enabled,
        "running": _scheduler.running,
        "daily_time": settings.app_scheduler_daily_time,
        "timezone": settings.app_timezone,
        "next_run_at": next_run_at,
    }


def parse_daily_time(value: str) -> tuple[int, int]:
    try:
        hour_text, minute_text = value.strip().split(":", maxsplit=1)
        hour = int(hour_text)
        minute = int(minute_text)
    except ValueError as exc:
        raise ValueError("APP_SCHEDULER_DAILY_TIME 格式应为 HH:MM") from exc

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("APP_SCHEDULER_DAILY_TIME 时间范围应为 00:00 到 23:59")
    return hour, minute


def timezone_for(value: str) -> ZoneInfo:
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"未知时区: {value}") from exc


def now_in_timezone(settings: Settings | None = None) -> datetime:
    settings = settings or get_settings()
    return datetime.now(timezone_for(settings.app_timezone))
