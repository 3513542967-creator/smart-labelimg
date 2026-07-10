from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import cv2
import numpy as np

from smart_labelimg.annotation import Box


class BoxRefinementBackend(Protocol):
    def refine_from_box(self, image: np.ndarray, query_box: tuple[int, int, int, int], label: str) -> list[Box]:
        ...


@dataclass(frozen=True)
class PropagationCandidate:
    box: Box
    confidence: float
    requires_confirmation: bool


@dataclass(frozen=True)
class PropagationResult:
    committed: tuple[Box, ...]
    candidates: tuple[PropagationCandidate, ...]


def estimate_displacement(
    previous: np.ndarray,
    current: np.ndarray,
    box: Box,
    search_scale: float = 2.0,
) -> tuple[int, int, float]:
    """Estimate integer object displacement from previous to current image.

    Matching is deliberately bounded around the previous box location so it is
    fast and deterministic for sequential annotation workflows.
    """

    if previous.size == 0 or current.size == 0:
        return 0, 0, 0.0
    previous_gray = _grayscale(previous)
    current_gray = _grayscale(current)
    height, width = current_gray.shape[:2]
    source = box.clipped((previous.shape[1], previous.shape[0]))
    if source.width < 2 or source.height < 2:
        return 0, 0, 0.0

    template = previous_gray[source.y1 : source.y2, source.x1 : source.x2]
    if template.size == 0:
        return 0, 0, 0.0

    margin_x = max(1, int(round(source.width * search_scale)))
    margin_y = max(1, int(round(source.height * search_scale)))
    search_x1 = max(0, source.x1 - margin_x)
    search_y1 = max(0, source.y1 - margin_y)
    search_x2 = min(width, source.x2 + margin_x)
    search_y2 = min(height, source.y2 + margin_y)
    search = current_gray[search_y1:search_y2, search_x1:search_x2]
    if search.shape[0] < template.shape[0] or search.shape[1] < template.shape[1]:
        return 0, 0, 0.0

    match = cv2.matchTemplate(search, template, cv2.TM_SQDIFF_NORMED)
    min_value, _max_value, min_location, _max_location = cv2.minMaxLoc(match)
    best_x = search_x1 + int(min_location[0])
    best_y = search_y1 + int(min_location[1])
    score = float(max(0.0, min(1.0, 1.0 - min_value)))
    return best_x - source.x1, best_y - source.y1, score


def propagate_boxes(
    previous: np.ndarray,
    current: np.ndarray,
    boxes: list[Box],
    backend: BoxRefinementBackend | None,
    accept_threshold: float = 0.78,
) -> PropagationResult:
    candidates: list[PropagationCandidate] = []
    image_size = (current.shape[1], current.shape[0]) if current.size else (0, 0)
    for source in tuple(boxes):
        normalized = source.normalized()
        dx, dy, match_score = estimate_displacement(previous, current, normalized)
        shifted = Box(
            normalized.label,
            normalized.x1 + dx,
            normalized.y1 + dy,
            normalized.x2 + dx,
            normalized.y2 + dy,
            normalized.score,
        ).clipped(image_size)
        refined = _refine_box(current, shifted, backend)
        confidence = _candidate_confidence(match_score, refined)
        candidate_box = Box(
            refined.label,
            refined.x1,
            refined.y1,
            refined.x2,
            refined.y2,
            refined.score,
        ).clipped(image_size)
        candidates.append(
            PropagationCandidate(
                box=candidate_box,
                confidence=confidence,
                requires_confirmation=confidence < accept_threshold,
            )
        )

    if candidates and all(not candidate.requires_confirmation for candidate in candidates):
        return PropagationResult(
            committed=tuple(candidate.box for candidate in candidates),
            candidates=(),
        )
    return PropagationResult(committed=(), candidates=tuple(candidates))


def _grayscale(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image.astype(np.uint8, copy=False)
    return cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)


def _refine_box(current: np.ndarray, shifted: Box, backend: BoxRefinementBackend | None) -> Box:
    if backend is None or not hasattr(backend, "refine_from_box"):
        return shifted
    try:
        refined = backend.refine_from_box(
            current,
            (shifted.x1, shifted.y1, shifted.x2, shifted.y2),
            shifted.label,
        )
    except Exception:
        return shifted
    if not refined:
        return shifted
    return refined[0].normalized()


def _candidate_confidence(match_score: float, box: Box) -> float:
    if box.score is None:
        return float(max(0.0, min(1.0, match_score)))
    return float(max(0.0, min(1.0, match_score * max(0.0, min(1.0, box.score)))))
