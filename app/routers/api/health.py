from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings, load_yaml_config

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health_check():
    settings = get_settings()
    yaml_config = load_yaml_config(settings.config_file)
    return {
        "status": "ok",
        "app_env": settings.app_env,
        "database_url": settings.app_database_url,
        "storage_root": str(settings.storage_root),
        "config_loaded": bool(yaml_config),
        "openclaw_gateway_url": settings.openclaw_gateway_url,
    }
