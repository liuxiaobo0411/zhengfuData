from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Site, SiteSection
from app.services.crawler.http import fetch_url
from app.services.crawler.parser import parse_json_page
from app.services.crawler.runner import parse_listing_records


@dataclass(frozen=True)
class SourceValidationResult:
    section_id: int
    section_name: str
    strategy: str
    status: str
    record_count: int = 0
    sample_title: str = ""
    failure_reason: str = ""


@dataclass(frozen=True)
class SourceValidationSummary:
    results: list[SourceValidationResult]

    @property
    def total_count(self) -> int:
        return len(self.results)

    @property
    def success_count(self) -> int:
        return sum(1 for result in self.results if result.status == "success")

    @property
    def failed_count(self) -> int:
        return sum(1 for result in self.results if result.status == "failed")


def validate_enabled_sources(limit: int = 0) -> SourceValidationSummary:
    with SessionLocal() as db:
        sections = list(
            db.scalars(
                select(SiteSection)
                .join(Site, Site.id == SiteSection.site_id)
                .where(Site.enabled.is_(True))
                .where(SiteSection.enabled.is_(True))
                .order_by(SiteSection.id)
            ).all()
        )
        if limit > 0:
            sections = sections[:limit]

        results = [validate_section(section) for section in sections]

    return SourceValidationSummary(results=results)


def validate_section(section: SiteSection) -> SourceValidationResult:
    try:
        if section.crawler_strategy in {"browser_rendered", "custom_adapter", "manual_import"}:
            raise RuntimeError(f"当前策略不支持轻量来源验证: {section.crawler_strategy}")

        page = fetch_url(section.url, section)
        records = (
            parse_json_page(page.text, page.final_url, section)
            if section.crawler_strategy == "json_api"
            else parse_listing_records(page, section)
        )
        if not records:
            raise RuntimeError("未解析到列表记录")

        return SourceValidationResult(
            section_id=section.id,
            section_name=section.name,
            strategy=section.crawler_strategy,
            status="success",
            record_count=len(records),
            sample_title=records[0].title,
        )
    except Exception as exc:
        return SourceValidationResult(
            section_id=section.id,
            section_name=section.name,
            strategy=section.crawler_strategy,
            status="failed",
            failure_reason=f"{type(exc).__name__}: {exc}",
        )
