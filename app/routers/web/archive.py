from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from app.config import BASE_DIR, get_settings
from app.database import SessionLocal
from app.models import (
    Announcement,
    Attachment,
    ChangeLog,
    CrawlRun,
    NotificationLog,
    Site,
    SiteSection,
)
from app.routers.web.security import require_user

router = APIRouter(tags=["archive"])
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


@router.get("/announcements", response_class=HTMLResponse)
def announcement_list(request: Request):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    filters = {
        "q": request.query_params.get("q", "").strip(),
        "site_id": request.query_params.get("site_id", "").strip(),
        "section_id": request.query_params.get("section_id", "").strip(),
        "item_type": request.query_params.get("item_type", "").strip(),
        "status": request.query_params.get("status", "").strip(),
        "has_attachment": request.query_params.get("has_attachment", "").strip(),
    }
    with SessionLocal() as db:
        attachment_counts = (
            select(Attachment.announcement_id, func.count(Attachment.id).label("attachment_count"))
            .group_by(Attachment.announcement_id)
            .subquery()
        )
        query = (
            select(
                Announcement,
                Site.name.label("site_name"),
                SiteSection.name.label("section_name"),
                func.coalesce(attachment_counts.c.attachment_count, 0).label("attachment_count"),
            )
            .join(Site, Announcement.site_id == Site.id)
            .join(SiteSection, Announcement.section_id == SiteSection.id)
            .outerjoin(attachment_counts, attachment_counts.c.announcement_id == Announcement.id)
            .order_by(Announcement.fetched_at.desc(), Announcement.id.desc())
        )
        if filters["q"]:
            query = query.where(Announcement.title.contains(filters["q"]))
        if filters["site_id"].isdigit():
            query = query.where(Announcement.site_id == int(filters["site_id"]))
        if filters["section_id"].isdigit():
            query = query.where(Announcement.section_id == int(filters["section_id"]))
        if filters["item_type"]:
            query = query.where(Announcement.item_type == filters["item_type"])
        if filters["status"]:
            query = query.where(Announcement.status == filters["status"])
        if filters["has_attachment"] == "yes":
            query = query.where(func.coalesce(attachment_counts.c.attachment_count, 0) > 0)
        if filters["has_attachment"] == "no":
            query = query.where(func.coalesce(attachment_counts.c.attachment_count, 0) == 0)
        rows = db.execute(query.limit(200)).all()
        sites = db.scalars(select(Site).order_by(Site.name)).all()
        sections = db.scalars(select(SiteSection).order_by(SiteSection.name)).all()

    return templates.TemplateResponse(
        request,
        "archive/announcements.html",
        {
            "active_nav": "announcements",
            "user": user,
            "rows": rows,
            "sites": sites,
            "sections": sections,
            "filters": filters,
        },
    )


@router.get("/announcements/{announcement_id}", response_class=HTMLResponse)
def announcement_detail(request: Request, announcement_id: int):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    with SessionLocal() as db:
        row = db.execute(
            select(Announcement, Site, SiteSection)
            .join(Site, Announcement.site_id == Site.id)
            .join(SiteSection, Announcement.section_id == SiteSection.id)
            .where(Announcement.id == announcement_id)
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="announcement not found")
        announcement, site, section = row
        attachments = db.scalars(
            select(Attachment)
            .where(Attachment.announcement_id == announcement_id)
            .order_by(Attachment.id)
        ).all()
        changes = db.scalars(
            select(ChangeLog)
            .where(ChangeLog.announcement_id == announcement_id)
            .order_by(ChangeLog.created_at.desc(), ChangeLog.id.desc())
        ).all()

    return templates.TemplateResponse(
        request,
        "archive/announcement_detail.html",
        {
            "active_nav": "announcements",
            "user": user,
            "announcement": announcement,
            "site": site,
            "section": section,
            "attachments": attachments,
            "changes": changes,
        },
    )


@router.get("/attachments", response_class=HTMLResponse)
def attachment_list(request: Request):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    with SessionLocal() as db:
        rows = db.execute(
            select(
                Attachment,
                Announcement.title.label("announcement_title"),
                Site.name.label("site_name"),
            )
            .join(Announcement, Attachment.announcement_id == Announcement.id)
            .join(Site, Attachment.site_id == Site.id)
            .order_by(Attachment.created_at.desc(), Attachment.id.desc())
            .limit(300)
        ).all()

    return templates.TemplateResponse(
        request,
        "archive/attachments.html",
        {"active_nav": "attachments", "user": user, "rows": rows},
    )


@router.get("/attachments/{attachment_id}/download")
def download_attachment(request: Request, attachment_id: int):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    with SessionLocal() as db:
        attachment = db.get(Attachment, attachment_id)
        if attachment is None or not attachment.local_path:
            raise HTTPException(status_code=404, detail="attachment not found")
        settings = get_settings()
        storage_root = settings.storage_root.resolve()
        file_path = (storage_root / attachment.local_path).resolve()
        if not is_relative_to(file_path, storage_root) or not file_path.exists():
            raise HTTPException(status_code=404, detail="attachment file missing")
        return FileResponse(
            file_path,
            media_type=attachment.mime_type or "application/octet-stream",
            filename=attachment.safe_name,
        )


@router.get("/crawl-runs", response_class=HTMLResponse)
def crawl_run_list(request: Request):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    with SessionLocal() as db:
        rows = db.scalars(
            select(CrawlRun).order_by(CrawlRun.started_at.desc(), CrawlRun.id.desc()).limit(200)
        ).all()

    return templates.TemplateResponse(
        request,
        "archive/crawl_runs.html",
        {"active_nav": "crawl_runs", "user": user, "runs": rows},
    )


@router.get("/crawl-runs/{run_id}", response_class=HTMLResponse)
def crawl_run_detail(request: Request, run_id: int):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    with SessionLocal() as db:
        run = db.get(CrawlRun, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="crawl run not found")
        SiteAlias = aliased(Site)
        SectionAlias = aliased(SiteSection)
        changes = db.execute(
            select(
                ChangeLog,
                SiteAlias.name.label("site_name"),
                SectionAlias.name.label("section_name"),
            )
            .outerjoin(SiteAlias, ChangeLog.site_id == SiteAlias.id)
            .outerjoin(SectionAlias, ChangeLog.section_id == SectionAlias.id)
            .where(ChangeLog.run_id == run_id)
            .order_by(ChangeLog.created_at.desc(), ChangeLog.id.desc())
        ).all()

    return templates.TemplateResponse(
        request,
        "archive/crawl_run_detail.html",
        {"active_nav": "crawl_runs", "user": user, "run": run, "changes": changes},
    )


@router.get("/notifications", response_class=HTMLResponse)
def notification_list(request: Request):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    with SessionLocal() as db:
        rows = db.scalars(
            select(NotificationLog)
            .order_by(NotificationLog.created_at.desc(), NotificationLog.id.desc())
            .limit(200)
        ).all()

    return templates.TemplateResponse(
        request,
        "archive/notifications.html",
        {"active_nav": "notifications", "user": user, "notifications": rows},
    )


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
