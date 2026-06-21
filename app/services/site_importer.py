from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Site, SiteSection


def import_sites_from_yaml(db: Session, path: Path) -> dict[str, int]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sites_data = data.get("sites", [])
    if not isinstance(sites_data, list):
        raise ValueError("sites.yaml must contain a sites list")

    site_count = 0
    section_count = 0
    for site_data in sites_data:
        if not isinstance(site_data, dict):
            continue
        site = upsert_site(db, site_data)
        site_count += 1
        for section_data in site_data.get("sections", []):
            if isinstance(section_data, dict):
                upsert_section(db, site, section_data)
                section_count += 1
    db.commit()
    return {"sites": site_count, "sections": section_count}


def upsert_site(db: Session, data: dict[str, Any]) -> Site:
    slug = required_text(data, "slug")
    site = db.scalar(select(Site).where(Site.slug == slug))
    if site is None:
        site = Site(
            slug=slug,
            name=required_text(data, "name"),
            homepage_url=required_text(data, "homepage_url"),
        )
        db.add(site)
    site.name = required_text(data, "name")
    site.homepage_url = required_text(data, "homepage_url")
    site.organization = optional_text(data, "organization")
    site.region = optional_text(data, "region")
    site.enabled = bool(data.get("enabled", True))
    site.remark = optional_text(data, "remark")
    db.flush()
    return site


def upsert_section(db: Session, site: Site, data: dict[str, Any]) -> SiteSection:
    url = required_text(data, "url")
    section = db.scalar(
        select(SiteSection).where(
            SiteSection.site_id == site.id,
            SiteSection.url == url,
        )
    )
    if section is None:
        section = SiteSection(site_id=site.id, name=required_text(data, "name"), url=url)
        db.add(section)
    section.name = required_text(data, "name")
    section.url = url
    section.item_type = optional_text(data, "item_type") or "qualification_notice"
    section.crawl_method = optional_text(data, "crawl_method") or "http"
    section.crawler_strategy = optional_text(data, "crawler_strategy") or "http_static"
    section.schedule_cron = optional_text(data, "schedule_cron") or "0 9 * * *"
    section.enabled = bool(data.get("enabled", True))
    section.download_attachments = bool(data.get("download_attachments", True))
    section.save_snapshot = bool(data.get("save_snapshot", True))
    section.request_timeout = int(data.get("request_timeout", 20))
    section.retry_times = int(data.get("retry_times", 2))
    section.request_interval_seconds = int(data.get("request_interval_seconds", 3))
    section.request_headers = optional_text(data, "request_headers")
    section.max_pages = int(data.get("max_pages", 1))
    section.max_items_per_run = int(data.get("max_items_per_run", 100))
    section.stop_when_seen_existing_count = int(data.get("stop_when_seen_existing_count", 20))
    section.crawl_date_window_days = int(data.get("crawl_date_window_days", 1))
    section.allow_full_crawl = bool(data.get("allow_full_crawl", False))
    section.list_selector = optional_text(data, "list_selector")
    section.title_selector = optional_text(data, "title_selector")
    section.date_selector = optional_text(data, "date_selector")
    section.detail_url_selector = optional_text(data, "detail_url_selector")
    section.content_selector = optional_text(data, "content_selector")
    section.attachment_selector = optional_text(data, "attachment_selector")
    section.pagination_rule = optional_text(data, "pagination_rule")
    section.custom_adapter = optional_text(data, "custom_adapter")
    return section


def required_text(data: dict[str, Any], key: str) -> str:
    value = optional_text(data, key)
    if not value:
        raise ValueError(f"missing required field: {key}")
    return value


def optional_text(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None
