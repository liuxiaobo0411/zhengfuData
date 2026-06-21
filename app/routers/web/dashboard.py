from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR, get_settings
from app.services.storage import prepare_storage

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    settings = get_settings()
    storage = prepare_storage(settings)
    context = {
        "request": request,
        "settings": settings,
        "storage": storage,
        "metrics": [
            {"label": "归档记录", "value": "0", "hint": "等待首次正式抓取"},
            {"label": "新增公告", "value": "0", "hint": "今日"},
            {"label": "附件文件", "value": "0", "hint": "Word / Excel / PDF"},
            {"label": "抓取失败", "value": "0", "hint": "任务错误"},
        ],
    }
    return templates.TemplateResponse(request, "dashboard.html", context)
