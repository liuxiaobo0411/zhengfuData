from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR, get_settings
from app.routers.api.health import router as health_router
from app.routers.web.archive import router as archive_router
from app.routers.web.auth import router as auth_router
from app.routers.web.dashboard import router as dashboard_router
from app.routers.web.settings import router as settings_router
from app.routers.web.sites import router as sites_router
from app.services.scheduler import start_scheduler, stop_scheduler
from app.services.storage import prepare_storage


def create_app() -> FastAPI:
    settings = get_settings()
    prepare_storage(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        start_scheduler(settings)
        try:
            yield
        finally:
            stop_scheduler()

    app = FastAPI(
        title="建筑资质公开信息监测与归档系统",
        version="0.1.0",
        description="政府公开信息抓取、归档、变化检测与企微通知系统。",
        lifespan=lifespan,
    )
    app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(archive_router)
    app.include_router(dashboard_router)
    app.include_router(settings_router)
    app.include_router(sites_router)
    return app


app = create_app()
