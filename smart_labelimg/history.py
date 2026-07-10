from __future__ import annotations

from dataclasses import dataclass

from smart_labelimg.annotation import Box


@dataclass(frozen=True)
class AnnotationSnapshot:
    boxes: tuple[Box, ...]
    labels: tuple[str, ...]


class AnnotationHistory:
    def __init__(self, limit: int = 100):
        if limit < 1:
            raise ValueError("history limit must be at least 1")
        self.limit = limit
        self._snapshots: list[AnnotationSnapshot] = []
        self._index = -1

    @property
    def can_undo(self) -> bool:
        return self._index > 0

    @property
    def can_redo(self) -> bool:
        return 0 <= self._index < len(self._snapshots) - 1

    def reset(self, boxes: list[Box], labels: list[str]) -> AnnotationSnapshot:
        snapshot = self._snapshot(boxes, labels)
        self._snapshots = [snapshot]
        self._index = 0
        return snapshot

    def record(self, boxes: list[Box], labels: list[str]) -> AnnotationSnapshot:
        snapshot = self._snapshot(boxes, labels)
        if self._index >= 0 and self._snapshots[self._index] == snapshot:
            return snapshot
        if self.can_redo:
            self._snapshots = self._snapshots[: self._index + 1]
        self._snapshots.append(snapshot)
        if len(self._snapshots) > self.limit:
            overflow = len(self._snapshots) - self.limit
            self._snapshots = self._snapshots[overflow:]
        self._index = len(self._snapshots) - 1
        return snapshot

    def undo(self) -> AnnotationSnapshot:
        if not self.can_undo:
            return self._current()
        self._index -= 1
        return self._current()

    def redo(self) -> AnnotationSnapshot:
        if not self.can_redo:
            return self._current()
        self._index += 1
        return self._current()

    def _current(self) -> AnnotationSnapshot:
        if self._index < 0:
            return self.reset([], [])
        return self._snapshots[self._index]

    @staticmethod
    def _snapshot(boxes: list[Box], labels: list[str]) -> AnnotationSnapshot:
        copied_boxes = tuple(Box(box.label, box.x1, box.y1, box.x2, box.y2, box.score) for box in boxes)
        return AnnotationSnapshot(copied_boxes, tuple(labels))
