from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from app.config import BASE_DIR, get_settings
from app.database import SessionLocal
from app.models import Site, SiteSection
from app.routers.web.security import require_user
from app.services.notifier import notification_config_state
from app.services.scheduler import scheduler_status
from app.services.storage import prepare_storage

router = APIRouter(tags=["settings"])
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    user = require_user(request)
    if isinstance(user, RedirectResponse):
        return user

    settings = get_settings()
    storage = prepare_storage(settings)
    notification_state = notification_config_state(settings)
    with SessionLocal() as db:
        site_count = db.scalar(select(func.count(Site.id))) or 0
        enabled_section_count = (
            db.scalar(select(func.count(SiteSection.id)).where(SiteSection.enabled.is_(True))) or 0
        )

    return templates.TemplateResponse(
        request,
        "settings/index.html",
        {
            "active_nav": "settings",
            "user": user,
            "settings": settings,
            "scheduler": scheduler_status(settings),
            "storage_info": storage_info(storage.root),
            "site_count": site_count,
            "enabled_section_count": enabled_section_count,
            "notification_state": notification_state,
            "openclaw_webhook_state": secret_state(settings.openclaw_webhook_url),
            "admin_password_state": secret_state(settings.admin_password),
            "app_secret_state": secret_state(settings.app_secret_key),
            "scripts": windows_script_states(),
        },
    )


def storage_info(root: Path) -> dict[str, str | bool]:
    return {
        "root": str(root),
        "exists": root.exists(),
        "attachments": str(root / "attachments"),
        "snapshots": str(root / "snapshots"),
        "exports": str(root / "exports"),
        "logs": str(root / "logs"),
    }


def secret_state(value: str) -> str:
    if not value:
        return "未配置"
    if value == "change-me":
        return "默认值"
    return "已配置"


def windows_script_states() -> list[dict[str, str | bool]]:
    names = [
        "setup.ps1",
        "run-server.ps1",
        "validate-sources.ps1",
        "run-daily-crawl.ps1",
        "install-daily-task.ps1",
        "doctor.ps1",
        "acceptance-check.ps1",
        "v2-acceptance-check.ps1",
        "export-acceptance-report.ps1",
    ]
    root = BASE_DIR / "scripts" / "windows"
    return [{"name": name, "exists": (root / name).exists()} for name in names]
