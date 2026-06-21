from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment and optional YAML config."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    app_secret_key: str = Field(default="change-me", alias="APP_SECRET_KEY")
    app_database_url: str = Field(default="sqlite:///data/app.db", alias="APP_DATABASE_URL")
    app_storage_root: Path = Field(default=Path("storage"), alias="APP_STORAGE_ROOT")
    app_config_file: Path = Field(default=Path("configs/app.yaml"), alias="APP_CONFIG_FILE")

    admin_username: str = Field(default="admin", alias="ADMIN_USERNAME")
    admin_password: str = Field(default="change-me", alias="ADMIN_PASSWORD")

    openclaw_dashboard_url: str = Field(
        default="http://127.0.0.1:18789/",
        alias="OPENCLAW_DASHBOARD_URL",
    )
    openclaw_webhook_url: str = Field(default="", alias="OPENCLAW_WEBHOOK_URL")
    openclaw_gateway_url: str = Field(default="ws://127.0.0.1:18789", alias="OPENCLAW_GATEWAY_URL")
    app_public_base_url: str = Field(default="http://127.0.0.1:8000", alias="APP_PUBLIC_BASE_URL")
    wecom_notify_target_type: str = Field(default="direct", alias="WECOM_NOTIFY_TARGET_TYPE")
    wecom_notify_target_id: str = Field(default="", alias="WECOM_NOTIFY_TARGET_ID")

    @property
    def storage_root(self) -> Path:
        return resolve_project_path(self.app_storage_root)

    @property
    def database_path(self) -> Path | None:
        prefix = "sqlite:///"
        if not self.app_database_url.startswith(prefix):
            return None
        return resolve_project_path(Path(self.app_database_url.removeprefix(prefix)))

    @property
    def config_file(self) -> Path:
        return resolve_project_path(self.app_config_file)


def resolve_project_path(path: str | Path) -> Path:
    """Resolve a possibly relative path against the project root."""

    value = Path(path).expanduser()
    if value.is_absolute():
        return value
    return (BASE_DIR / value).resolve()


def load_yaml_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML config must be a mapping: {path}")
    return data


@lru_cache
def get_settings() -> Settings:
    return Settings()
