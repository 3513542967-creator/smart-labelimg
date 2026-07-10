from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import json
from pathlib import Path


@dataclass(frozen=True)
class AppSettings:
    last_image_dir: str = ""
    annotation_format: str = "yolo"
    default_class: str = "object"
    recent_folders: tuple[str, ...] = ()
    brightness: int = 0


class SettingsStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> AppSettings:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return AppSettings()
        except (OSError, json.JSONDecodeError):
            self._quarantine_corrupt_file()
            return AppSettings()
        if not isinstance(raw, dict):
            return AppSettings()
        allowed = {field.name for field in fields(AppSettings)}
        values = {key: value for key, value in raw.items() if key in allowed}
        try:
            if "recent_folders" in values:
                values["recent_folders"] = tuple(str(item) for item in values["recent_folders"])
            return AppSettings(**values)
        except (TypeError, ValueError):
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(settings)
        payload["recent_folders"] = list(settings.recent_folders)
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _quarantine_corrupt_file(self) -> None:
        corrupt = self.path.with_suffix(f"{self.path.suffix}.corrupt")
        try:
            if self.path.exists():
                self.path.replace(corrupt)
        except OSError:
            pass
