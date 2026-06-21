from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.config import BASE_DIR
from app.database import SessionLocal
from app.models import Site, SiteSection
from app.routers.web.security import require_user
from app.services.crawler import crawl_section

router = APIRouter(tags=["sites"])
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))

CRAWLER_STRATEGIES = [
    "http_static",
    "http_with_headers",
    "http_with_retry",
    "json_api",
    "browser_rendered",
    "custom_adapter",
    "manual_import",
]

ITEM_TYPES = [
    "qualification_notice",
    "government_file",
    "administrative_license",
    "company_list",
    "exam_personnel_notice",
    "other",
]


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def clean_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def checked(form: Any, key: str) -> bool:
    return form.get(key) in {"on", "true", "1", "yes"}


@router.get("/sites", response_class=HTMLResponse)
def sites_page(request: Request):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    with SessionLocal() as db:
        sites = db.scalars(
            select(Site).options(selectinload(Site.sections)).order_by(Site.created_at.desc())
        ).all()
        section_count = db.scalar(select(func.count(SiteSection.id))) or 0

    return templates.TemplateResponse(
        request,
        "sites/index.html",
        {
            "active_nav": "sites",
            "user": user,
            "sites": sites,
            "section_count": section_count,
        },
    )


@router.post("/sites")
async def create_site(request: Request):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    form = await request.form()
    site = Site(
        name=clean_text(form.get("name")),
        slug=clean_text(form.get("slug")),
        homepage_url=clean_text(form.get("homepage_url")),
        organization=clean_text(form.get("organization")) or None,
        region=clean_text(form.get("region")) or None,
        enabled=checked(form, "enabled"),
        remark=clean_text(form.get("remark")) or None,
    )
    with SessionLocal() as db:
        db.add(site)
        db.commit()
    return RedirectResponse("/sites", status_code=303)


@router.get("/sites/{site_id}/edit", response_class=HTMLResponse)
def edit_site_page(request: Request, site_id: int):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    with SessionLocal() as db:
        site = db.get(Site, site_id)
        if site is None:
            return RedirectResponse("/sites", status_code=303)
        db.expunge(site)

    return templates.TemplateResponse(
        request,
        "sites/edit.html",
        {"active_nav": "sites", "user": user, "site": site},
    )


@router.post("/sites/{site_id}/edit")
async def update_site(request: Request, site_id: int):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    form = await request.form()
    with SessionLocal() as db:
        site = db.get(Site, site_id)
        if site is not None:
            site.name = clean_text(form.get("name"))
            site.slug = clean_text(form.get("slug"))
            site.homepage_url = clean_text(form.get("homepage_url"))
            site.organization = clean_text(form.get("organization")) or None
            site.region = clean_text(form.get("region")) or None
            site.enabled = checked(form, "enabled")
            site.remark = clean_text(form.get("remark")) or None
            db.commit()
    return RedirectResponse("/sites", status_code=303)


@router.post("/sites/{site_id}/toggle")
def toggle_site(request: Request, site_id: int):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    with SessionLocal() as db:
        site = db.get(Site, site_id)
        if site is not None:
            site.enabled = not site.enabled
            db.commit()
    return RedirectResponse("/sites", status_code=303)


@router.get("/sites/{site_id}/sections/new", response_class=HTMLResponse)
def new_section_page(request: Request, site_id: int):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    with SessionLocal() as db:
        site = db.get(Site, site_id)
        if site is None:
            return RedirectResponse("/sites", status_code=303)
        db.expunge(site)

    return templates.TemplateResponse(
        request,
        "sites/section_form.html",
        {
            "active_nav": "sites",
            "user": user,
            "site": site,
            "section": None,
            "crawler_strategies": CRAWLER_STRATEGIES,
            "item_types": ITEM_TYPES,
        },
    )


@router.post("/sites/{site_id}/sections")
async def create_section(request: Request, site_id: int):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    form = await request.form()
    section = build_section_from_form(form)
    section.site_id = site_id
    with SessionLocal() as db:
        db.add(section)
        db.commit()
    return RedirectResponse("/sites", status_code=303)


@router.get("/sections/{section_id}/edit", response_class=HTMLResponse)
def edit_section_page(request: Request, section_id: int):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    with SessionLocal() as db:
        section = db.get(SiteSection, section_id)
        if section is None:
            return RedirectResponse("/sites", status_code=303)
        site = db.get(Site, section.site_id)
        db.expunge(section)
        if site is not None:
            db.expunge(site)

    return templates.TemplateResponse(
        request,
        "sites/section_form.html",
        {
            "active_nav": "sites",
            "user": user,
            "site": site,
            "section": section,
            "crawler_strategies": CRAWLER_STRATEGIES,
            "item_types": ITEM_TYPES,
        },
    )


@router.post("/sections/{section_id}/edit")
async def update_section(request: Request, section_id: int):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    form = await request.form()
    with SessionLocal() as db:
        section = db.get(SiteSection, section_id)
        if section is not None:
            update_section_from_form(section, form)
            db.commit()
    return RedirectResponse("/sites", status_code=303)


@router.post("/sections/{section_id}/toggle")
def toggle_section(request: Request, section_id: int):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    with SessionLocal() as db:
        section = db.get(SiteSection, section_id)
        if section is not None:
            section.enabled = not section.enabled
            db.commit()
    return RedirectResponse("/sites", status_code=303)


@router.post("/sections/{section_id}/crawl")
def crawl_site_section(request: Request, section_id: int):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    with SessionLocal() as db:
        crawl_section(db, section_id, triggered_by=user.username)
    return RedirectResponse("/sites", status_code=303)


def build_section_from_form(form: Any) -> SiteSection:
    section = SiteSection(site_id=0)
    update_section_from_form(section, form)
    return section


def update_section_from_form(section: SiteSection, form: Any) -> None:
    section.name = clean_text(form.get("name"))
    section.url = clean_text(form.get("url"))
    section.item_type = clean_text(form.get("item_type")) or "qualification_notice"
    section.crawl_method = clean_text(form.get("crawl_method")) or "http"
    section.crawler_strategy = clean_text(form.get("crawler_strategy")) or "http_static"
    section.schedule_cron = clean_text(form.get("schedule_cron")) or "0 9 * * *"
    section.enabled = checked(form, "enabled")
    section.download_attachments = checked(form, "download_attachments")
    section.save_snapshot = checked(form, "save_snapshot")
    section.request_timeout = clean_int(form.get("request_timeout"), 20)
    section.retry_times = clean_int(form.get("retry_times"), 2)
    section.request_interval_seconds = clean_int(form.get("request_interval_seconds"), 3)
    section.request_headers = clean_text(form.get("request_headers")) or None
    section.max_pages = clean_int(form.get("max_pages"), 3)
    section.max_items_per_run = clean_int(form.get("max_items_per_run"), 100)
    section.stop_when_seen_existing_count = clean_int(
        form.get("stop_when_seen_existing_count"),
        20,
    )
    section.crawl_date_window_days = clean_int(form.get("crawl_date_window_days"), 1)
    section.allow_full_crawl = checked(form, "allow_full_crawl")
    section.list_selector = clean_text(form.get("list_selector")) or None
    section.title_selector = clean_text(form.get("title_selector")) or None
    section.date_selector = clean_text(form.get("date_selector")) or None
    section.detail_url_selector = clean_text(form.get("detail_url_selector")) or None
    section.content_selector = clean_text(form.get("content_selector")) or None
    section.attachment_selector = clean_text(form.get("attachment_selector")) or None
    section.pagination_rule = clean_text(form.get("pagination_rule")) or None
    section.custom_adapter = clean_text(form.get("custom_adapter")) or None
