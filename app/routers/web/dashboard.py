from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from app.config import BASE_DIR, get_settings
from app.database import SessionLocal
from app.models import Announcement, Attachment, Site, SiteSection
from app.routers.web.security import require_user
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
        announcement_count = db.scalar(select(func.count(Announcement.id))) or 0
        attachment_count = db.scalar(select(func.count(Attachment.id))) or 0

    context = {
        "request": request,
        "active_nav": "dashboard",
        "user": user,
        "settings": settings,
        "storage": storage,
        "metrics": [
            {"label": "政府网站", "value": str(site_count), "hint": "已配置"},
            {"label": "监测栏目", "value": str(section_count), "hint": "抓取入口"},
            {"label": "归档公告", "value": str(announcement_count), "hint": "等待抓取接入"},
            {"label": "附件文件", "value": str(attachment_count), "hint": "Word / Excel / PDF"},
        ],
    }
    return templates.TemplateResponse(request, "dashboard.html", context)
