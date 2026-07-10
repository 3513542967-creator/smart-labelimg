from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Protocol

import cv2
import numpy as np

from smart_labelimg.annotation import Box


class SmartBoxBackend(Protocol):
    def detect_labels(self, image_path: Path, labels: list[str]) -> list[Box]:
        ...

    def detect_from_click(self, image: np.ndarray, x: int, y: int, label: str) -> list[Box]:
        ...

    def refine_from_box(self, image: np.ndarray, query_box: tuple[int, int, int, int], label: str) -> list[Box]:
        ...

    def find_similar(self, image: np.ndarray, query_box: tuple[int, int, int, int], label: str) -> list[Box]:
        ...


class ClassicalVisionBackend:
    """Offline Mac-friendly backend for click boxes and similar-object proposals."""

    def detect_labels(self, image_path: Path, labels: list[str]) -> list[Box]:
        return []

    def detect_from_click(self, image: np.ndarray, x: int, y: int, label: str) -> list[Box]:
        if image.size == 0:
            return []
        height, width = image.shape[:2]
        if not (0 <= x < width and 0 <= y < height):
            return []

        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
        clicked = lab[y, x].astype(np.int16)
        distance = np.linalg.norm(lab.astype(np.int16) - clicked, axis=2)
        mask = (distance < 28).astype(np.uint8) * 255
        mask = cv2.medianBlur(mask, 5)
        flood = np.zeros((height + 2, width + 2), dtype=np.uint8)
        filled = mask.copy()
        cv2.floodFill(filled, flood, (x, y), 127)
        component = (filled == 127).astype(np.uint8)

        contours, _ = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return []
        contour = max(contours, key=cv2.contourArea)
        if cv2.contourArea(contour) < 20:
            return []
        bx, by, bw, bh = cv2.boundingRect(contour)
        padded = self._pad_box((bx, by, bx + bw, by + bh), width, height, 2)
        return [Box(label, *padded, score=1.0)]

    def refine_from_box(self, image: np.ndarray, query_box: tuple[int, int, int, int], label: str) -> list[Box]:
        if image.size == 0:
            return []
        height, width = image.shape[:2]
        x1, y1, x2, y2 = self._clip_tuple(query_box, width, height)
        crop = image[y1:y2, x1:x2]
        if crop.size == 0 or crop.shape[0] < 3 or crop.shape[1] < 3:
            return []

        lab = cv2.cvtColor(crop, cv2.COLOR_RGB2LAB)
        border = np.concatenate((lab[0, :, :], lab[-1, :, :], lab[:, 0, :], lab[:, -1, :]), axis=0)
        background = np.median(border, axis=0)
        distance = np.linalg.norm(lab.astype(np.float32) - background.astype(np.float32), axis=2)
        mask = (distance > 24).astype(np.uint8) * 255
        mask = cv2.medianBlur(mask, 5)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return [Box(label, x1, y1, x2, y2, score=1.0).normalized()]
        contour = max(contours, key=cv2.contourArea)
        if cv2.contourArea(contour) < 20:
            return [Box(label, x1, y1, x2, y2, score=1.0).normalized()]
        bx, by, bw, bh = cv2.boundingRect(contour)
        padded = self._pad_box((x1 + bx, y1 + by, x1 + bx + bw, y1 + by + bh), width, height, 2)
        return [Box(label, *padded, score=1.0)]

    def find_similar(self, image: np.ndarray, query_box: tuple[int, int, int, int], label: str) -> list[Box]:
        height, width = image.shape[:2]
        x1, y1, x2, y2 = self._clip_tuple(query_box, width, height)
        template = image[y1:y2, x1:x2]
        if template.size == 0 or template.shape[0] < 8 or template.shape[1] < 8:
            return []

        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
        template_lab = lab[y1:y2, x1:x2]
        mean = template_lab.reshape(-1, 3).mean(axis=0)
        distance = np.linalg.norm(lab.astype(np.float32) - mean.astype(np.float32), axis=2)
        mask = (distance < 30).astype(np.uint8) * 255
        mask = cv2.medianBlur(mask, 5)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        query_area = max(1, (x2 - x1) * (y2 - y1))
        candidates: list[Box] = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < query_area * 0.35 or area > query_area * 2.5:
                continue
            bx, by, bw, bh = cv2.boundingRect(contour)
            aspect = bw / max(1, bh)
            query_aspect = (x2 - x1) / max(1, y2 - y1)
            if not (query_aspect * 0.45 <= aspect <= query_aspect * 2.2):
                continue
            padded = self._pad_box((bx, by, bx + bw, by + bh), width, height, 2)
            candidates.append(Box(label, *padded, score=1.0))
        return self._non_max_suppression(candidates, iou_threshold=0.25)

    def _non_max_suppression(self, boxes: list[Box], iou_threshold: float) -> list[Box]:
        sorted_boxes = sorted(boxes, key=lambda box: box.score or 0, reverse=True)
        kept: list[Box] = []
        for box in sorted_boxes:
            if all(self._iou(box, other) < iou_threshold for other in kept):
                kept.append(box)
        return kept[:50]

    def _iou(self, a: Box, b: Box) -> float:
        ax1, ay1, ax2, ay2 = a.normalized().x1, a.normalized().y1, a.normalized().x2, a.normalized().y2
        bx1, by1, bx2, by2 = b.normalized().x1, b.normalized().y1, b.normalized().x2, b.normalized().y2
        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        union = a.width * a.height + b.width * b.height - inter
        return inter / union if union else 0.0

    def _pad_box(self, box: tuple[int, int, int, int], width: int, height: int, padding: int) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = box
        return (
            max(0, x1 - padding),
            max(0, y1 - padding),
            min(width - 1, x2 + padding),
            min(height - 1, y2 + padding),
        )

    def _clip_tuple(self, box: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = box
        x1, x2 = sorted((max(0, min(width - 1, x1)), max(0, min(width, x2))))
        y1, y2 = sorted((max(0, min(height - 1, y1)), max(0, min(height, y2))))
        return x1, y1, x2, y2


def mask_to_box(mask: np.ndarray, label: str, score: float | None = None) -> Box:
    ys, xs = np.where(mask)
    if len(xs) == 0 or len(ys) == 0:
        return Box(label, 0, 0, 0, 0, score)
    return Box(label, int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()), score)


@dataclass
class SamBackend:
    checkpoint_path: str
    model_type: str = "vit_b"
    device: str | None = None

    def __post_init__(self) -> None:
        from segment_anything import SamPredictor, sam_model_registry
        import torch

        if self.device is None:
            if torch.backends.mps.is_available():
                self.device = "mps"
            elif torch.cuda.is_available():
                self.device = "cuda"
            else:
                self.device = "cpu"
        model = sam_model_registry[self.model_type](checkpoint=self.checkpoint_path)
        model.to(device=self.device)
        self.predictor = SamPredictor(model)

    def detect_labels(self, image_path: Path, labels: list[str]) -> list[Box]:
        return []

    def detect_from_click(self, image: np.ndarray, x: int, y: int, label: str) -> list[Box]:
        if image.size == 0:
            return []
        self.predictor.set_image(image)
        masks, scores, _ = self.predictor.predict(
            point_coords=np.array([[x, y]], dtype=np.float32),
            point_labels=np.array([1], dtype=np.int32),
            multimask_output=True,
        )
        if len(masks) == 0:
            return []
        areas = np.array([mask.sum() for mask in masks], dtype=np.float32)
        image_area = float(image.shape[0] * image.shape[1])
        valid = np.where((areas > 20) & (areas < image_area * 0.45))[0]
        if len(valid) == 0:
            valid = np.where(areas > 20)[0]
        if len(valid) == 0:
            return []
        max_score = float(scores[valid].max())
        near_best = valid[scores[valid] >= max_score - 0.12]
        best_index = int(near_best[np.argmax(areas[near_best])])
        mapped = mask_to_box(masks[best_index], label=label, score=float(scores[best_index])).clipped((image.shape[1], image.shape[0]))
        return [mapped] if mapped.width > 0 and mapped.height > 0 else []

    def refine_from_box(self, image: np.ndarray, query_box: tuple[int, int, int, int], label: str) -> list[Box]:
        height, width = image.shape[:2]
        x1, y1, x2, y2 = ClassicalVisionBackend()._clip_tuple(query_box, width, height)
        if x2 - x1 < 3 or y2 - y1 < 3:
            return []
        self.predictor.set_image(image)
        masks, scores, _ = self.predictor.predict(
            box=np.array([x1, y1, x2, y2], dtype=np.float32),
            multimask_output=True,
        )
        if len(masks) == 0:
            return []
        areas = np.array([mask.sum() for mask in masks], dtype=np.float32)
        valid = np.where(areas > 20)[0]
        if len(valid) == 0:
            return []
        best_index = int(valid[np.argmax(scores[valid])])
        mapped = mask_to_box(masks[best_index], label=label, score=float(scores[best_index])).clipped((width, height))
        return [mapped] if mapped.width > 0 and mapped.height > 0 else []

    def find_similar(self, image: np.ndarray, query_box: tuple[int, int, int, int], label: str) -> list[Box]:
        return ClassicalVisionBackend().find_similar(image, query_box, label)


SamClickBackend = SamBackend


@dataclass
class LocateAnythingBackend:
    """Adapter for mudler/locate-anything.cpp CLI."""

    command: str
    model_path: str
    threads: int = 8
    mode: str = "hybrid"

    def detect_labels(self, image_path: Path, labels: list[str]) -> list[Box]:
        prompt = self.build_prompt(labels)
        with NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            output_path = Path(tmp.name)
        try:
            args = [
                "detect",
                "--model",
                self.model_path,
                "--input",
                str(image_path),
                "--prompt",
                prompt,
                "--output",
                str(output_path),
                "--threads",
                str(self.threads),
                "--mode",
                self.mode,
            ]
            self.run_command(args)
            return self.parse_json_boxes(output_path.read_text(encoding="utf-8"), fallback_label=labels[0] if labels else "object")
        finally:
            output_path.unlink(missing_ok=True)

    def detect_from_click(self, image: np.ndarray, x: int, y: int, label: str) -> list[Box]:
        raise RuntimeError(
            "LocateAnythingBackend is prompt-driven. Use detect_labels(image_path, labels); clicking only selects boxes."
        )

    def refine_from_box(self, image: np.ndarray, query_box: tuple[int, int, int, int], label: str) -> list[Box]:
        raise RuntimeError("LocateAnythingBackend does not support box-prompt refinement.")

    def build_prompt(self, labels: list[str]) -> str:
        cleaned = [label.strip() for label in labels if label.strip()]
        if not cleaned:
            cleaned = ["object"]
        return "Locate all the instances that matches the following description: " + "</c>".join(cleaned) + "."

    def parse_json_boxes(self, payload: str, fallback_label: str) -> list[Box]:
        data = json.loads(payload)
        boxes = data.get("detections", data.get("boxes", data if isinstance(data, list) else []))
        parsed: list[Box] = []
        for item in boxes:
            coords = item.get("box", item)
            x1, y1, x2, y2 = (int(round(float(value))) for value in coords[:4])
            parsed.append(Box(item.get("label", fallback_label), x1, y1, x2, y2, item.get("score")))
        return parsed

    def run_command(self, args: list[str]) -> str:
        completed = subprocess.run([self.command, *args], check=True, capture_output=True, text=True)
        return completed.stdout
