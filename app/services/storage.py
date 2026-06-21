from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import Settings
from app.services.path_utils import ensure_directory


@dataclass(frozen=True)
class StoragePaths:
    root: Path
    attachments: Path
    snapshots: Path
    exports: Path
    logs: Path


def prepare_storage(settings: Settings) -> StoragePaths:
    root = ensure_directory(settings.storage_root)
    return StoragePaths(
        root=root,
        attachments=ensure_directory(root / "attachments"),
        snapshots=ensure_directory(root / "snapshots"),
        exports=ensure_directory(root / "exports"),
        logs=ensure_directory(root / "logs"),
    )
