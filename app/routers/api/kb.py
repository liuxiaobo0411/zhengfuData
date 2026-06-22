from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config import get_settings
from app.database import SessionLocal
from app.services.kb import ask_knowledge, format_openclaw_answer, search_knowledge

router = APIRouter(prefix="/api", tags=["kb"])


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=50)


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
        results = search_knowledge(db, request.query, limit=request.limit)
    return {
        "query": request.query,
        "total": len(results),
        "items": [
            result_to_response(result, base_url=settings.app_public_base_url) for result in results
        ],
    }


@router.post("/kb/ask")
def kb_ask(request: AskRequest):
    settings = get_settings()
    with SessionLocal() as db:
        result = ask_knowledge(db, request.question, limit=request.limit)
    for item in result["items"]:
        if item.get("backend_url") and item["backend_url"].startswith("/"):
            item["backend_url"] = f"{settings.app_public_base_url.rstrip('/')}{item['backend_url']}"
    return result


@router.post("/openclaw/kb/ask")
def openclaw_kb_ask(request: OpenClawAskRequest):
    with SessionLocal() as db:
        text = format_openclaw_answer(db, request.text, limit=request.limit)
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
