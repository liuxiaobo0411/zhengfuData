from __future__ import annotations

from datetime import datetime, time

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.config import BASE_DIR
from app.database import SessionLocal
from app.models import SearchIndex
from app.routers.web.security import require_user
from app.services.kb import SEARCH_ENTITY_TYPES, search_knowledge

router = APIRouter(tags=["kb"])
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


@router.get("/kb/search", response_class=HTMLResponse)
def kb_search_page(request: Request):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    query = request.query_params.get("q", "").strip()
    entity_type = normalize_entity_type(request.query_params.get("entity_type", "").strip())
    site_name = request.query_params.get("site_name", "").strip()
    published_from = request.query_params.get("published_from", "").strip()
    published_to = request.query_params.get("published_to", "").strip()
    with SessionLocal() as db:
        site_names = list(
            db.scalars(
                select(SearchIndex.site_name)
                .where(SearchIndex.site_name.is_not(None))
                .distinct()
                .order_by(SearchIndex.site_name)
            )
        )
        results = (
            search_knowledge(
                db,
                query,
                limit=50,
                entity_type=entity_type or None,
                site_name=site_name or None,
                published_from=parse_date_start(published_from),
                published_to=parse_date_end(published_to),
            )
            if query
            else []
        )

    return templates.TemplateResponse(
        request,
        "kb/search.html",
        {
            "active_nav": "kb",
            "user": user,
            "query": query,
            "entity_type": entity_type,
            "site_name": site_name,
            "published_from": published_from,
            "published_to": published_to,
            "site_names": site_names,
            "results": results,
        },
    )


def parse_date_start(value: str) -> datetime | None:
    parsed = parse_date(value)
    return datetime.combine(parsed, time.min) if parsed else None


def parse_date_end(value: str) -> datetime | None:
    parsed = parse_date(value)
    return datetime.combine(parsed, time.max) if parsed else None


def parse_date(value: str):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def normalize_entity_type(value: str) -> str:
    return value if value in SEARCH_ENTITY_TYPES else ""
