from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from app.config import BASE_DIR, resolve_project_path

PACKAGE_ROOT_NAME = "zhengfudata"

INCLUDED_PATHS = [
    ".env.example",
    ".gitignore",
    "CONTRIBUTING.md",
    "README.md",
    "alembic.ini",
    "pyproject.toml",
    "alembic",
    "app",
    "configs",
    "docs",
    "scripts",
]

EXCLUDED_NAMES = {
    ".DS_Store",
    ".env",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "data",
    "env",
    "exports",
    "htmlcov",
    "logs",
    "playwright-report",
    "storage",
    "temp",
    "test-results",
    "tmp",
    "venv",
}

EXCLUDED_SUFFIXES = {
    ".db",
    ".pyc",
    ".pyd",
    ".pyo",
    ".sqlite",
    ".sqlite3",
}


@dataclass(frozen=True)
class DeploymentPackage:
    path: Path
    file_count: int
    size_bytes: int


def export_deployment_package(output_path: Path | None = None) -> DeploymentPackage:
    target = resolve_output_path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    files = list(iter_package_files())
    with ZipFile(target, "w", compression=ZIP_DEFLATED) as archive:
        for file_path in files:
            archive.write(file_path, arcname=archive_name(file_path))
        archive.writestr(
            f"{PACKAGE_ROOT_NAME}/DEPLOYMENT_PACKAGE_MANIFEST.txt", manifest_text(files)
        )

    return DeploymentPackage(
        path=target,
        file_count=len(files) + 1,
        size_bytes=target.stat().st_size,
    )


def resolve_output_path(output_path: Path | None) -> Path:
    if output_path:
        target = resolve_project_path(output_path)
        if target.suffix.lower() != ".zip":
            return target / default_package_name()
        return target

    return resolve_project_path(Path("storage") / "exports" / default_package_name())


def default_package_name() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"zhengfudata_deployment_{timestamp}.zip"


def iter_package_files():
    for relative in INCLUDED_PATHS:
        path = BASE_DIR / relative
        if not path.exists():
            continue
        if path.is_file():
            if should_include(path):
                yield path
            continue
        for file_path in sorted(path.rglob("*")):
            if file_path.is_file() and should_include(file_path):
                yield file_path


def should_include(path: Path) -> bool:
    relative = path.relative_to(BASE_DIR)
    if any(part in EXCLUDED_NAMES for part in relative.parts):
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if path.name.endswith(".egg-info"):
        return False
    return True


def archive_name(path: Path) -> str:
    return f"{PACKAGE_ROOT_NAME}/{path.relative_to(BASE_DIR).as_posix()}"


def manifest_text(files: list[Path]) -> str:
    lines = [
        "zhengfudata Windows deployment package",
        "",
        "解压后先阅读 README.md 和 docs/Windows本地部署说明.md。",
        "初始化命令：scripts\\windows\\setup.ps1",
        "本机验收：scripts\\windows\\run-local-acceptance.ps1 -SourceLimit 2 -DailyLimit 2",
        "",
        "本包不包含 .env、data、storage、.venv、.git 或本机缓存。",
        "",
        "文件清单：",
    ]
    lines.extend(path.relative_to(BASE_DIR).as_posix() for path in files)
    return "\n".join(lines) + "\n"
