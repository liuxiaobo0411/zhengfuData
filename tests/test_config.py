from pathlib import Path

from app.config import BASE_DIR, Settings, load_yaml_config, resolve_project_path


def test_resolve_project_path_keeps_absolute_path(tmp_path: Path):
    assert resolve_project_path(tmp_path) == tmp_path


def test_resolve_project_path_resolves_relative_path():
    assert resolve_project_path("storage") == (BASE_DIR / "storage").resolve()


def test_settings_exposes_storage_and_database_paths():
    settings = Settings(APP_STORAGE_ROOT="storage", APP_DATABASE_URL="sqlite:///data/app.db")

    assert settings.storage_root == (BASE_DIR / "storage").resolve()
    assert settings.database_path == (BASE_DIR / "data" / "app.db").resolve()


def test_settings_exposes_scheduler_options():
    settings = Settings(
        APP_SCHEDULER_ENABLED=True,
        APP_SCHEDULER_DAILY_TIME="08:30",
        APP_TIMEZONE="Asia/Shanghai",
    )

    assert settings.app_scheduler_enabled is True
    assert settings.app_scheduler_daily_time == "08:30"
    assert settings.app_timezone == "Asia/Shanghai"
    assert settings.app_running_run_timeout_minutes == 360
    assert settings.crawler_attachment_timeout_seconds == 10


def test_load_yaml_config_reads_mapping(tmp_path: Path):
    config = tmp_path / "app.yaml"
    config.write_text("app:\n  name: test\n", encoding="utf-8")

    assert load_yaml_config(config) == {"app": {"name": "test"}}
