from __future__ import annotations

from datetime import date, datetime, time

from fastapi import APIRouter
from pydantic import BaseModel, Field, model_validator

from app.config import get_settings
from app.database import SessionLocal
from app.services.kb import (
    SEARCH_ENTITY_TYPES,
    ask_knowledge,
    format_openclaw_answer,
    search_knowledge,
)

router = APIRouter(prefix="/api", tags=["kb"])


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=50)
    entity_type: str | None = None
    site_name: str | None = None
    published_from: date | None = None
    published_to: date | None = None

    @model_validator(mode="after")
    def validate_filters(self):
        if self.entity_type and self.entity_type not in SEARCH_ENTITY_TYPES:
            allowed = ", ".join(sorted(SEARCH_ENTITY_TYPES))
            raise ValueError(f"entity_type 仅支持：{allowed}")
        if self.published_from and self.published_to and self.published_from > self.published_to:
            raise ValueError("published_from 不能晚于 published_to")
        return self


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)


class OpenClawAskRequest(BaseModel):
    text: str = Field(min_length=1)
    source: str = "wecom"
    limit: int = Field(default=5, ge=1, le=20)


@router.post("/kb/search")
def kb_search(request: SearchRequest):
    settings = get_settings()
    with SessionLocal() as db:
        results = search_knowledge(
            db,
            request.query,
            limit=request.limit,
            entity_type=request.entity_type,
            site_name=request.site_name,
            published_from=day_start(request.published_from),
            published_to=day_end(request.published_to),
        )
    return {
        "query": request.query,
        "entity_type": request.entity_type,
        "site_name": request.site_name,
        "published_from": request.published_from.isoformat() if request.published_from else None,
        "published_to": request.published_to.isoformat() if request.published_to else None,
        "total": len(results),
        "items": [
            result_to_response(result, base_url=settings.app_public_base_url) for result in results
        ],
    }


def day_start(value: date | None) -> datetime | None:
    return datetime.combine(value, time.min) if value else None


def day_end(value: date | None) -> datetime | None:
    return datetime.combine(value, time.max) if value else None


@router.post("/kb/ask")
def kb_ask(request: AskRequest):
    settings = get_settings()
    with SessionLocal() as db:
        result = ask_knowledge(
            db,
            request.question,
            limit=request.limit,
            base_url=settings.app_public_base_url,
        )
    return result


@router.post("/openclaw/kb/ask")
def openclaw_kb_ask(request: OpenClawAskRequest):
    settings = get_settings()
    with SessionLocal() as db:
        text = format_openclaw_answer(
            db,
            request.text,
            limit=request.limit,
            base_url=settings.app_public_base_url,
        )
    return {"text": text, "source": request.source}


def result_to_response(result, base_url: str) -> dict:
    backend_url = result.backend_path
    if backend_url and backend_url.startswith("/"):
        backend_url = f"{base_url.rstrip('/')}{backend_url}"
    return {
        "entity_type": result.entity_type,
        "entity_id": result.entity_id,
        "title": result.title,
        "snippet": result.snippet,
        "match_fields": result.match_fields,
        "source_url": result.source_url,
        "backend_url": backend_url,
        "site_name": result.site_name,
        "section_name": result.section_name,
        "published_at": result.published_at.isoformat() if result.published_at else None,
        "score": result.score,
    }
