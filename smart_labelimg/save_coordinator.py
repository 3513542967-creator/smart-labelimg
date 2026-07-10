from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import os
from pathlib import Path
import tempfile

from smart_labelimg.annotation import Box, save_annotation


class SaveState(str, Enum):
    SAVED = "saved"
    CONFLICT = "conflict"
    FAILED = "failed"


@dataclass(frozen=True)
class SaveResult:
    state: SaveState
    fingerprints: dict[Path, str]
    conflicts: tuple[Path, ...] = ()
    error: str | None = None


class SaveCoordinator:
    def __init__(self) -> None:
        self.expected: dict[Path, str | None] = {}

    def fingerprint(self, path: Path) -> str | None:
        try:
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            return digest.hexdigest()
        except FileNotFoundError:
            return None

    def save_bytes(self, files: dict[Path, bytes], expected: dict[Path, str | None]) -> SaveResult:
        paths = tuple(files)
        conflicts = tuple(path for path in paths if self.fingerprint(path) != expected.get(path))
        if conflicts:
            return SaveResult(SaveState.CONFLICT, {}, conflicts=conflicts)

        staged: dict[Path, Path] = {}
        backups: dict[Path, Path] = {}
        replaced: list[Path] = []
        try:
            for path, contents in files.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                descriptor, name = tempfile.mkstemp(prefix=".smart-labelimg-stage-", dir=path.parent)
                stage = Path(name)
                staged[path] = stage
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(contents)
                    stream.flush()
                    os.fsync(stream.fileno())

            for path in paths:
                if path.exists():
                    descriptor, name = tempfile.mkstemp(prefix=".smart-labelimg-backup-", dir=path.parent)
                    os.close(descriptor)
                    backup = Path(name)
                    backup.unlink()
                    os.replace(path, backup)
                    backups[path] = backup
                os.replace(staged[path], path)
                replaced.append(path)

            fingerprints = {path: value for path in paths if (value := self.fingerprint(path)) is not None}
            return SaveResult(SaveState.SAVED, fingerprints)
        except Exception as exc:
            for path in reversed(paths):
                try:
                    if path in backups:
                        os.replace(backups[path], path)
                    elif path in replaced:
                        path.unlink(missing_ok=True)
                except OSError:
                    pass
            return SaveResult(SaveState.FAILED, {}, error=str(exc))
        finally:
            for temporary in (*staged.values(), *backups.values()):
                temporary.unlink(missing_ok=True)

    def save_annotation_atomic(
        self,
        path: Path,
        boxes: list[Box],
        labels: list[str],
        image_size: tuple[int, int],
        image_path: Path,
    ) -> SaveResult:
        expected = self.expected.get(path, self.fingerprint(path))
        descriptor, name = tempfile.mkstemp(suffix=path.suffix)
        os.close(descriptor)
        serialized = Path(name)
        try:
            save_annotation(serialized, boxes, labels, image_size, image_path)
            result = self.save_bytes({path: serialized.read_bytes()}, {path: expected})
            if result.state is SaveState.SAVED:
                self.expected.update(result.fingerprints)
            return result
        except Exception as exc:
            return SaveResult(SaveState.FAILED, {}, error=str(exc))
        finally:
            serialized.unlink(missing_ok=True)
