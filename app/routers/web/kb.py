from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR
from app.database import SessionLocal
from app.routers.web.security import require_user
from app.services.kb import search_knowledge

router = APIRouter(tags=["kb"])
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


@router.get("/kb/search", response_class=HTMLResponse)
def kb_search_page(request: Request):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    query = request.query_params.get("q", "").strip()
    entity_type = request.query_params.get("entity_type", "").strip()
    with SessionLocal() as db:
        results = search_knowledge(db, query, limit=50) if query else []
    if entity_type:
        results = [item for item in results if item.entity_type == entity_type]

    return templates.TemplateResponse(
        request,
        "kb/search.html",
        {
            "active_nav": "kb",
            "user": user,
            "query": query,
            "entity_type": entity_type,
            "results": results,
        },
    )
