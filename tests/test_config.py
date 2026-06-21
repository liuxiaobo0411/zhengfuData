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


def test_load_yaml_config_reads_mapping(tmp_path: Path):
    config = tmp_path / "app.yaml"
    config.write_text("app:\n  name: test\n", encoding="utf-8")

    assert load_yaml_config(config) == {"app": {"name": "test"}}
