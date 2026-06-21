from __future__ import annotations

import re
from pathlib import Path

WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def safe_filename(value: str, max_bytes: int = 235) -> str:
    """Return a readable filename compatible with Windows, macOS, and Linux."""

    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .") or "未命名"
    suffix = Path(cleaned).suffix
    stem = cleaned[: -len(suffix)] if suffix else cleaned
    if stem.upper() in WINDOWS_RESERVED_NAMES:
        stem = f"{stem}_"

    suffix_bytes = len(suffix.encode("utf-8"))
    byte_budget = max(1, max_bytes - suffix_bytes)
    while len(stem.encode("utf-8")) > byte_budget:
        stem = stem[:-1]

    stem = stem.rstrip(" .") or "未命名"
    return f"{stem}{suffix}"


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
