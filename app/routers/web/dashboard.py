from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from app.config import BASE_DIR, get_settings
from app.database import SessionLocal
from app.models import Announcement, Attachment, ChangeLog, CrawlRun, Site, SiteSection
from app.routers.web.security import require_user
from app.services.scheduler import scheduler_status
from app.services.storage import prepare_storage

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    settings = get_settings()
    storage = prepare_storage(settings)
    with SessionLocal() as db:
        site_count = db.scalar(select(func.count(Site.id))) or 0
        section_count = db.scalar(select(func.count(SiteSection.id))) or 0
        enabled_section_count = (
            db.scalar(select(func.count(SiteSection.id)).where(SiteSection.enabled.is_(True))) or 0
        )
        announcement_count = db.scalar(select(func.count(Announcement.id))) or 0
        attachment_count = db.scalar(select(func.count(Attachment.id))) or 0
        attachment_success_count = (
            db.scalar(
                select(func.count(Attachment.id)).where(Attachment.download_status == "success")
            )
            or 0
        )
        attachment_failed_count = (
            db.scalar(
                select(func.count(Attachment.id)).where(Attachment.download_status == "failed")
            )
            or 0
        )
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_runs = list(
            db.scalars(select(CrawlRun).where(CrawlRun.started_at >= today_start)).all()
        )
        SiteAlias = aliased(Site)
        SectionAlias = aliased(SiteSection)
        recent_changes = db.execute(
            select(
                ChangeLog,
                SiteAlias.name.label("site_name"),
                SectionAlias.name.label("section_name"),
            )
            .outerjoin(SiteAlias, ChangeLog.site_id == SiteAlias.id)
            .outerjoin(SectionAlias, ChangeLog.section_id == SectionAlias.id)
            .order_by(ChangeLog.created_at.desc(), ChangeLog.id.desc())
            .limit(8)
        ).all()
        today_failure_count = sum(run.status == "failed" for run in today_runs) + sum(
            run.attachment_failed_count for run in today_runs
        )
    openclaw_configured = bool(settings.openclaw_webhook_url)

    context = {
        "request": request,
        "active_nav": "dashboard",
        "user": user,
        "settings": settings,
        "storage": storage,
        "scheduler": scheduler_status(settings),
        "openclaw_configured": openclaw_configured,
        "recent_changes": recent_changes,
        "metrics": [
            {"label": "政府网站", "value": str(site_count), "hint": "已配置"},
            {
                "label": "启用栏目",
                "value": f"{enabled_section_count}/{section_count}",
                "hint": "抓取入口",
            },
            {"label": "归档记录", "value": str(announcement_count), "hint": "公告 / 查询记录"},
            {
                "label": "附件成功/失败",
                "value": f"{attachment_success_count}/{attachment_failed_count}",
                "hint": f"共 {attachment_count} 个",
            },
            {"label": "今日任务", "value": str(len(today_runs)), "hint": "抓取批次"},
            {
                "label": "今日新增",
                "value": str(sum(run.new_items for run in today_runs)),
                "hint": "公告 / 记录",
            },
            {
                "label": "今日变化",
                "value": str(
                    sum(
                        run.content_changed_items + run.attachment_changed_count
                        for run in today_runs
                    )
                ),
                "hint": "正文 / 附件",
            },
            {"label": "今日失败", "value": str(today_failure_count), "hint": "任务 / 附件"},
        ],
    }
    return templates.TemplateResponse(request, "dashboard.html", context)
