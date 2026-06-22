from __future__ import annotations

import sys
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def bundled_root() -> Path | None:
    root = getattr(sys, "_MEIPASS", None)
    return Path(root) if root else None


def resource_path(relative_path: str) -> Path:
    relative = Path(relative_path)
    for root in (bundled_root(), project_root(), Path(sys.executable).resolve().parent):
        if root is None:
            continue
        candidate = root / relative
        if candidate.exists():
            return candidate
    return project_root() / relative
