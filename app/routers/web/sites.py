from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

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
    error = validate_site_form(form)
    if error:
        return sites_page_response(request, user, error=error)

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
        if db.scalar(select(Site).where(Site.slug == site.slug)):
            return sites_page_response(request, user, error="唯一标识已存在")
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
    error = validate_site_form(form)
    with SessionLocal() as db:
        site = db.get(Site, site_id)
        if site is None:
            return RedirectResponse("/sites", status_code=303)
        if error:
            db.expunge(site)
            return templates.TemplateResponse(
                request,
                "sites/edit.html",
                {"active_nav": "sites", "user": user, "site": site, "error": error},
                status_code=400,
            )
        duplicate = db.scalar(
            select(Site).where(Site.slug == clean_text(form.get("slug"))).where(Site.id != site_id)
        )
        if duplicate:
            db.expunge(site)
            return templates.TemplateResponse(
                request,
                "sites/edit.html",
                {"active_nav": "sites", "user": user, "site": site, "error": "唯一标识已存在"},
                status_code=400,
            )
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


@router.post("/sites/{site_id}/crawl")
def crawl_site(request: Request, site_id: int):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    with SessionLocal() as db:
        section_ids = enabled_section_ids_for_site(db, site_id)
        for section_id in section_ids:
            crawl_section(db, section_id, triggered_by=user.username)
    return RedirectResponse("/crawl-runs", status_code=303)


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
    error = validate_section_form(form)
    if error:
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
                "error": error,
            },
            status_code=400,
        )
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
            error = validate_section_form(form)
            if error:
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
                        "error": error,
                    },
                    status_code=400,
                )
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


def enabled_section_ids_for_site(db, site_id: int) -> list[int]:
    return list(
        db.scalars(
            select(SiteSection.id)
            .join(Site, Site.id == SiteSection.site_id)
            .where(Site.id == site_id)
            .where(Site.enabled.is_(True))
            .where(SiteSection.enabled.is_(True))
            .order_by(SiteSection.id)
        ).all()
    )


def sites_page_response(request: Request, user, error: str | None = None):
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
            "error": error,
        },
        status_code=400 if error else 200,
    )


def validate_site_form(form: Any) -> str | None:
    if not clean_text(form.get("name")):
        return "网站名称不能为空"
    if not clean_text(form.get("slug")):
        return "唯一标识不能为空"
    if not valid_http_url(clean_text(form.get("homepage_url"))):
        return "首页地址必须是 http 或 https 地址"
    return None


def validate_section_form(form: Any) -> str | None:
    if not clean_text(form.get("name")):
        return "栏目名称不能为空"
    if not valid_http_url(clean_text(form.get("url"))):
        return "栏目地址必须是 http 或 https 地址"
    if clean_text(form.get("item_type")) not in ITEM_TYPES:
        return "信息类型不支持"
    crawler_strategy = clean_text(form.get("crawler_strategy")) or "http_static"
    if crawler_strategy not in CRAWLER_STRATEGIES:
        return "爬虫策略不支持"
    if crawler_strategy == "custom_adapter" and not clean_text(form.get("custom_adapter")):
        return "定制适配器策略需要填写适配器名称"
    if error := validate_min_int(form, "request_timeout", 1, "超时秒数"):
        return error
    if error := validate_min_int(form, "retry_times", 0, "重试次数"):
        return error
    if error := validate_min_int(form, "request_interval_seconds", 0, "请求间隔秒"):
        return error
    if error := validate_min_int(form, "max_pages", 1, "最大页数"):
        return error
    if error := validate_min_int(form, "max_items_per_run", 1, "单次最大条数"):
        return error
    if error := validate_min_int(form, "crawl_date_window_days", 1, "抓取日期窗口"):
        return error
    if error := validate_min_int(form, "stop_when_seen_existing_count", 1, "连续已存在停止数"):
        return error
    request_headers = clean_text(form.get("request_headers"))
    if request_headers:
        try:
            parsed_headers = json.loads(request_headers)
        except json.JSONDecodeError:
            return "请求头 JSON 格式不正确"
        if not isinstance(parsed_headers, dict):
            return "请求头 JSON 必须是对象"
    return None


def validate_min_int(form: Any, key: str, minimum: int, label: str) -> str | None:
    try:
        value = int(form.get(key))
    except (TypeError, ValueError):
        return f"{label}必须是数字"
    if value < minimum:
        return f"{label}不能小于 {minimum}"
    return None


def valid_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


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
