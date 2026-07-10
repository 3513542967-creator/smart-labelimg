from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QImage, QKeySequence, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QComboBox,
    QSlider,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from smart_labelimg.ai_backend import ClassicalVisionBackend, SamClickBackend
from smart_labelimg.annotation import (
    AnnotationFormat,
    Box,
    find_annotation_path,
    infer_format_from_path,
    load_annotation,
    voc_path_for_image,
    yolo_path_for_image,
)
from smart_labelimg.history import AnnotationHistory, AnnotationSnapshot
from smart_labelimg.labels import SIMPLE_LABELS
from smart_labelimg.paths import resource_path
from smart_labelimg.propagation import PropagationCandidate, propagate_boxes
from smart_labelimg.save_coordinator import SaveCoordinator, SaveState
from smart_labelimg.settings import AppSettings, SettingsStore


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
MOBILE_SAM_CHECKPOINT = resource_path("models/mobile_sam.pt")


class ImageCanvas(QWidget):
    boxes_changed = Signal()
    edit_completed = Signal()
    selected_changed = Signal()
    smart_clicked = Signal(int, int)
    smart_box_drawn = Signal(int, int, int, int)
    box_menu_requested = Signal(int, QPoint)
    mode_toggle_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setMinimumSize(720, 480)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.pixmap: QPixmap | None = None
        self.image_array: np.ndarray | None = None
        self.boxes: list[Box] = []
        self.candidate_boxes: tuple[Box, ...] = ()
        self.selected_index = -1
        self.mode = "smart"
        self.current_label = "object"
        self.drag_start: QPoint | None = None
        self.drag_current: QPoint | None = None
        self.drag_action: str | None = None
        self.drag_box_start: Box | None = None
        self.drag_boxes_start: tuple[Box, ...] = ()
        self.resize_handle: str | None = None
        self.handle_radius = 6
        self.min_box_size = 3
        self.show_labels = True
        self.show_boxes = True
        self.square_drawing = False
        self.brightness = 0
        self.zoom_percent = 100
        self.fit_mode = "window"
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.last_mouse_pos: QPoint | None = None

    def set_image(self, image_path: Path) -> tuple[int, int]:
        bgr = cv2.imread(str(image_path))
        if bgr is None:
            raise ValueError(f"Could not read image: {image_path}")
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        self.image_array = rgb
        height, width = rgb.shape[:2]
        qimage = QImage(rgb.data, width, height, width * 3, QImage.Format.Format_RGB888).copy()
        self.pixmap = QPixmap.fromImage(qimage)
        self.apply_brightness(self.brightness)
        self.boxes = []
        self.candidate_boxes = ()
        self.selected_index = -1
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.update()
        return width, height

    def apply_brightness(self, value: int) -> None:
        self.brightness = max(-100, min(100, int(value)))
        if self.image_array is None:
            self.update()
            return
        adjusted = np.clip(self.image_array.astype(np.int16) + self.brightness, 0, 255).astype(np.uint8)
        height, width = adjusted.shape[:2]
        qimage = QImage(adjusted.data, width, height, width * 3, QImage.Format.Format_RGB888).copy()
        self.pixmap = QPixmap.fromImage(qimage)
        self.update()

    def constrained_drag_point(self, current: QPoint) -> QPoint:
        if not self.square_drawing or self.drag_start is None:
            return current
        dx = current.x() - self.drag_start.x()
        dy = current.y() - self.drag_start.y()
        side = max(abs(dx), abs(dy))
        return QPoint(self.drag_start.x() + (side if dx >= 0 else -side), self.drag_start.y() + (side if dy >= 0 else -side))

    def set_boxes(self, boxes: list[Box]) -> None:
        self.boxes = boxes
        self.candidate_boxes = ()
        self.selected_index = 0 if boxes else -1
        self.boxes_changed.emit()
        self.selected_changed.emit()
        self.update()

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.drag_start = None
        self.drag_current = None
        self.drag_action = None
        self.drag_box_start = None
        self.resize_handle = None
        self.update()

    def image_bounds(self) -> tuple[int, int] | None:
        if self.pixmap:
            return self.pixmap.width(), self.pixmap.height()
        if self.image_array is not None:
            height, width = self.image_array.shape[:2]
            return width, height
        return None

    def move_selected_box(self, dx: int, dy: int) -> bool:
        if not (0 <= self.selected_index < len(self.boxes)):
            return False
        bounds = self.image_bounds()
        if bounds is None:
            return False
        image_width, image_height = bounds
        box = self.boxes[self.selected_index].normalized()
        box_width = box.width
        box_height = box.height
        max_x1 = max(0, image_width - 1 - box_width)
        max_y1 = max(0, image_height - 1 - box_height)
        new_x1 = min(max(box.x1 + dx, 0), max_x1)
        new_y1 = min(max(box.y1 + dy, 0), max_y1)
        moved = Box(box.label, new_x1, new_y1, new_x1 + box_width, new_y1 + box_height, box.score)
        if moved == box:
            return True
        self.boxes[self.selected_index] = moved
        self.boxes_changed.emit()
        self.selected_changed.emit()
        self.update()
        return True

    def selected_box(self) -> Box | None:
        if 0 <= self.selected_index < len(self.boxes):
            return self.boxes[self.selected_index].normalized()
        return None

    def handle_points(self, box: Box) -> dict[str, tuple[int, int]]:
        box = box.normalized()
        mid_x = int(round((box.x1 + box.x2) / 2))
        mid_y = int(round((box.y1 + box.y2) / 2))
        return {
            "top_left": (box.x1, box.y1),
            "top": (mid_x, box.y1),
            "top_right": (box.x2, box.y1),
            "right": (box.x2, mid_y),
            "bottom_right": (box.x2, box.y2),
            "bottom": (mid_x, box.y2),
            "bottom_left": (box.x1, box.y2),
            "left": (box.x1, mid_y),
        }

    def handle_at_image_point(self, x: int, y: int) -> str | None:
        box = self.selected_box()
        if box is None:
            return None
        for name, (hx, hy) in self.handle_points(box).items():
            if abs(x - hx) <= self.handle_radius and abs(y - hy) <= self.handle_radius:
                return name
        return None

    def resize_selected_box(self, handle: str, x: int, y: int) -> bool:
        if not (0 <= self.selected_index < len(self.boxes)):
            return False
        bounds = self.image_bounds()
        if bounds is None:
            return False
        image_width, image_height = bounds
        box = self.boxes[self.selected_index].normalized()
        x = max(0, min(image_width - 1, x))
        y = max(0, min(image_height - 1, y))
        x1, y1, x2, y2 = box.x1, box.y1, box.x2, box.y2

        if "left" in handle:
            x1 = min(x, x2 - self.min_box_size)
        if "right" in handle:
            x2 = max(x, x1 + self.min_box_size)
        if "top" in handle:
            y1 = min(y, y2 - self.min_box_size)
        if "bottom" in handle:
            y2 = max(y, y1 + self.min_box_size)

        resized = Box(box.label, x1, y1, x2, y2, box.score).clipped((image_width, image_height))
        self.boxes[self.selected_index] = resized
        self.boxes_changed.emit()
        self.selected_changed.emit()
        self.update()
        return True

    def image_rect(self) -> QRect:
        if not self.pixmap:
            return QRect()
        if self.fit_mode == "manual":
            scale = max(10, self.zoom_percent) / 100
            width = max(1, int(round(self.pixmap.width() * scale)))
            height = max(1, int(round(self.pixmap.height() * scale)))
        else:
            scaled = self.pixmap.size()
            scaled.scale(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
            width = scaled.width()
            height = scaled.height()
        x = int(round((self.width() - width) / 2 + self.pan_x))
        y = int(round((self.height() - height) / 2 + self.pan_y))
        return QRect(x, y, width, height)

    def zoom_at(self, zoom_percent: int, anchor: QPoint | None = None) -> None:
        if not self.pixmap:
            self.zoom_percent = max(10, min(800, zoom_percent))
            self.fit_mode = "manual"
            self.update()
            return
        old_rect = self.image_rect()
        if anchor is None:
            anchor = self.last_mouse_pos or QPoint(self.width() // 2, self.height() // 2)

        self.zoom_percent = max(10, min(800, zoom_percent))
        self.fit_mode = "manual"
        new_scale = self.zoom_percent / 100
        new_width = max(1, int(round(self.pixmap.width() * new_scale)))
        new_height = max(1, int(round(self.pixmap.height() * new_scale)))
        base_x = (self.width() - new_width) / 2
        base_y = (self.height() - new_height) / 2

        margin = 0.1
        usable_width = max(1.0, self.width() - 2 * margin * self.width())
        usable_height = max(1.0, self.height() - 2 * margin * self.height())
        move_x = (anchor.x() - margin * self.width()) / usable_width
        move_y = (anchor.y() - margin * self.height()) / usable_height
        move_x = max(0.0, min(1.0, move_x))
        move_y = max(0.0, min(1.0, move_y))

        desired_x = old_rect.x() - move_x * (new_width - old_rect.width())
        desired_y = old_rect.y() - move_y * (new_height - old_rect.height())
        self.pan_x = desired_x - base_x
        self.pan_y = desired_y - base_y
        self.update()

    def widget_to_image(self, point: QPoint) -> tuple[int, int] | None:
        if not self.pixmap:
            return None
        rect = self.image_rect()
        if not rect.contains(point):
            return None
        x = int((point.x() - rect.x()) * self.pixmap.width() / rect.width())
        y = int((point.y() - rect.y()) * self.pixmap.height() / rect.height())
        return x, y

    def image_to_widget_rect(self, box: Box) -> QRect:
        rect = self.image_rect()
        if not self.pixmap or rect.isNull():
            return QRect()
        sx = rect.width() / self.pixmap.width()
        sy = rect.height() / self.pixmap.height()
        normalized = box.normalized()
        return QRect(
            int(rect.x() + normalized.x1 * sx),
            int(rect.y() + normalized.y1 * sy),
            int(normalized.width * sx),
            int(normalized.height * sy),
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#202124"))
        if not self.pixmap:
            painter.setPen(QColor("#e8eaed"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Open an image or folder")
            return
        target = self.image_rect()
        painter.drawPixmap(target, self.pixmap)
        if not self.show_boxes:
            return
        for index, box in enumerate(self.boxes):
            color = QColor("#00e676") if index == self.selected_index else QColor("#ffca28")
            painter.setPen(QPen(color, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            box_rect = self.image_to_widget_rect(box)
            painter.drawRect(box_rect)
            if self.show_labels:
                painter.fillRect(box_rect.x(), box_rect.y() - 20, max(60, len(box.label) * 8), 20, QBrush(color))
                painter.setPen(QColor("#111111"))
                painter.drawText(box_rect.x() + 4, box_rect.y() - 5, box.label)
            if index == self.selected_index:
                painter.setPen(QPen(QColor("#ffffff"), 1))
                painter.setBrush(QBrush(QColor("#1a73e8")))
                for hx, hy in self.handle_points(box).values():
                    widget_x = int(target.x() + hx * target.width() / self.pixmap.width())
                    widget_y = int(target.y() + hy * target.height() / self.pixmap.height())
                    painter.drawRect(
                        widget_x - self.handle_radius,
                        widget_y - self.handle_radius,
                        self.handle_radius * 2,
                        self.handle_radius * 2,
                    )
        for candidate in self.candidate_boxes:
            box_rect = self.image_to_widget_rect(candidate)
            painter.setPen(QPen(QColor("#40c4ff"), 2, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(box_rect)
            if self.show_labels:
                text = f"{candidate.label}?"
                painter.fillRect(box_rect.x(), box_rect.y() - 20, max(68, len(text) * 8), 20, QBrush(QColor("#40c4ff")))
                painter.setPen(QColor("#111111"))
                painter.drawText(box_rect.x() + 4, box_rect.y() - 5, text)
        if self.drag_start and self.drag_current:
            painter.setPen(QPen(QColor("#40c4ff"), 2, Qt.PenStyle.DashLine))
            painter.drawRect(QRect(self.drag_start, self.drag_current).normalized())

    def mousePressEvent(self, event):
        if not self.pixmap:
            return
        self.setFocus()
        self.last_mouse_pos = event.position().toPoint()
        image_point = self.widget_to_image(event.position().toPoint())
        if image_point is None:
            return

        clicked_index = self.box_at(event.position().toPoint())
        if event.button() == Qt.MouseButton.RightButton and clicked_index >= 0:
            self.selected_index = clicked_index
            self.selected_changed.emit()
            self.update()
            self.box_menu_requested.emit(clicked_index, event.globalPosition().toPoint())
            return

        if self.mode == "smart" and event.button() == Qt.MouseButton.RightButton:
            self.smart_clicked.emit(*image_point)
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        handle = self.handle_at_image_point(*image_point)
        if handle is not None:
            self.drag_action = "resize"
            self.resize_handle = handle
            self.drag_current = event.position().toPoint()
            self.drag_boxes_start = tuple(self.boxes)
            return

        if clicked_index >= 0:
            self.selected_index = clicked_index
            self.selected_changed.emit()
            self.update()
            self.drag_action = "move"
            self.drag_start = event.position().toPoint()
            self.drag_current = self.drag_start
            self.drag_box_start = self.boxes[clicked_index].normalized()
            self.drag_boxes_start = tuple(self.boxes)
            return

        if self.mode == "smart":
            self.drag_action = "smart_draw"
            self.drag_start = event.position().toPoint()
            self.drag_current = self.drag_start
            return

        if self.mode == "draw":
            self.drag_action = "draw"
            self.drag_start = event.position().toPoint()
            self.drag_current = self.drag_start

    def mouseMoveEvent(self, event):
        self.last_mouse_pos = event.position().toPoint()
        if self.drag_action == "resize" and self.resize_handle:
            point = self.widget_to_image(event.position().toPoint())
            if point:
                self.resize_selected_box(self.resize_handle, *point)
            return

        if self.drag_action == "move" and self.drag_start and self.drag_box_start:
            point = event.position().toPoint()
            rect = self.image_rect()
            if not rect.isNull() and self.pixmap:
                dx = int(round((point.x() - self.drag_start.x()) * self.pixmap.width() / rect.width()))
                dy = int(round((point.y() - self.drag_start.y()) * self.pixmap.height() / rect.height()))
                start = self.drag_box_start
                self.boxes[self.selected_index] = Box(
                    start.label,
                    start.x1,
                    start.y1,
                    start.x2,
                    start.y2,
                    start.score,
                )
                self.move_selected_box(dx, dy)
            return

        if self.drag_start:
            self.drag_current = self.constrained_drag_point(event.position().toPoint())
            self.update()

    def wheelEvent(self, event):
        if event.modifiers() & (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier
        ):
            self.last_mouse_pos = event.position().toPoint()
            delta = 10 if event.angleDelta().y() > 0 else -10
            self.zoom_at(self.zoom_percent + delta, self.last_mouse_pos)
            event.accept()
            return
        super().wheelEvent(event)

    def mouseReleaseEvent(self, event):
        if self.drag_action in {"resize", "move"}:
            changed = self.drag_boxes_start != tuple(self.boxes)
            self.drag_action = None
            self.drag_box_start = None
            self.drag_boxes_start = ()
            self.resize_handle = None
            self.refresh_after_drag()
            if changed:
                self.edit_completed.emit()
            return

        if not self.drag_start or not self.drag_current:
            return
        p1 = self.widget_to_image(self.drag_start)
        p2 = self.widget_to_image(self.constrained_drag_point(event.position().toPoint()))
        self.drag_start = None
        self.drag_current = None
        action = self.drag_action
        self.drag_action = None
        if not p1 or not p2:
            self.update()
            return
        x1, y1 = p1
        x2, y2 = p2
        if action == "smart_draw":
            box = Box(self.current_label, x1, y1, x2, y2).normalized()
            if box.width >= 3 and box.height >= 3:
                self.smart_box_drawn.emit(box.x1, box.y1, box.x2, box.y2)
            self.update()
            return

        box = Box(self.current_label, x1, y1, x2, y2).normalized()
        if action == "draw" and box.width >= 3 and box.height >= 3:
            self.boxes.append(box)
            self.selected_index = len(self.boxes) - 1
            self.boxes_changed.emit()
            self.selected_changed.emit()
            self.edit_completed.emit()
        self.update()

    def mouseDoubleClickEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or not self.pixmap:
            return
        clicked_index = self.box_at(event.position().toPoint())
        if clicked_index >= 0:
            self.selected_index = clicked_index
            self.selected_changed.emit()
            self.update()
            self.box_menu_requested.emit(clicked_index, event.globalPosition().toPoint())

    def refresh_after_drag(self) -> None:
        self.boxes_changed.emit()
        self.selected_changed.emit()
        self.update()

    def box_at(self, point: QPoint) -> int:
        for index in range(len(self.boxes) - 1, -1, -1):
            if self.image_to_widget_rect(self.boxes[index]).contains(point):
                return index
        return -1

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Shift and not event.isAutoRepeat():
            self.mode_toggle_requested.emit()
            event.accept()
            return
        moves = {
            Qt.Key.Key_Left: (-1, 0),
            Qt.Key.Key_Right: (1, 0),
            Qt.Key.Key_Up: (0, -1),
            Qt.Key.Key_Down: (0, 1),
        }
        if event.key() not in moves:
            super().keyPressEvent(event)
            return
        dx, dy = moves[event.key()]
        before = tuple(self.boxes)
        if self.move_selected_box(dx, dy):
            if tuple(self.boxes) != before:
                self.edit_completed.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart LabelImg")
        self.resize(1180, 760)
        self.crop_size = 768
        self.backend = self._create_backend()
        self.labels = SIMPLE_LABELS.copy()
        self.images: list[Path] = []
        self.image_index = -1
        self.current_image: Path | None = None
        self.image_size: tuple[int, int] | None = None
        self.current_label_path: Path | None = None
        self.label_directory: Path | None = None
        self.save_directory: Path | None = None
        self.annotation_format = AnnotationFormat.AUTO
        self._loading_image = False
        self._saving_annotation = False
        self.save_coordinator = SaveCoordinator()
        self.save_state = SaveState.SAVED
        self.loaded_fingerprints: dict[Path, str | None] = {}
        self.history = AnnotationHistory()
        self.undo_action: QAction | None = None
        self.redo_action: QAction | None = None
        self.propagation_candidates: tuple[PropagationCandidate, ...] = ()
        self.settings_store = SettingsStore(Path.home() / ".smart-labelimg" / "settings.json")
        self.settings = self.settings_store.load()
        self.action_shortcuts: dict[str, str] = {}
        self.actions_by_name: dict[str, QAction] = {}

        self.canvas = ImageCanvas()
        self.canvas.current_label = self.settings.default_class
        self.canvas.apply_brightness(self.settings.brightness)
        self.class_list = QListWidget()
        self.box_list = QListWidget()
        self.image_list = QListWidget()
        self.crop_size_combo = QComboBox()
        self.save_format_combo = QComboBox()
        self.save_target_label = QLabel()
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_value_label = QLabel("Fit")
        self.verified_images: set[Path] = set()
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self._build_ui()
        self._refresh_classes()
        self.history.reset(self.canvas.boxes, self.labels)
        self.update_history_actions()
        self.update_save_target_label()

    def _create_backend(self):
        if MOBILE_SAM_CHECKPOINT.exists():
            try:
                return SamClickBackend(str(MOBILE_SAM_CHECKPOINT), crop_size=self.crop_size)
            except Exception as exc:
                print(f"MobileSAM backend unavailable, falling back to classical vision: {exc}", file=sys.stderr)
        return ClassicalVisionBackend()

    def _build_ui(self) -> None:
        edit_menu = self.menuBar().addMenu("Edit")
        self.undo_action = QAction("Undo", self)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.triggered.connect(self.undo_annotation_edit)
        edit_menu.addAction(self.undo_action)
        self.addAction(self.undo_action)
        self.redo_action = QAction("Redo", self)
        self.redo_action.setShortcuts(
            [
                QKeySequence(QKeySequence.StandardKey.Redo),
                QKeySequence("Ctrl+Shift+Z"),
                QKeySequence("Meta+Shift+Z"),
            ]
        )
        self.redo_action.triggered.connect(self.redo_annotation_edit)
        edit_menu.addAction(self.redo_action)
        self.addAction(self.redo_action)
        view_menu = self.menuBar().addMenu("View")
        tools_menu = self.menuBar().addMenu("Tools")

        toolbar = QToolBar("Main")
        toolbar.setObjectName("Main")
        self.addToolBar(toolbar)
        toolbar_actions = [
            ("Open", self.open_dialog, QKeySequence.StandardKey.Open),
            ("Open Label", self.open_label_dialog, None),
            ("←", self.prev_image, "A"),
            ("→", self.next_image, "D"),
            ("Smart →", self.smart_next_image, "Shift+D"),
            ("普通 LabelImg", lambda: self.set_mode("draw"), "W"),
            ("智能标注", lambda: self.set_mode("smart"), "S"),
            ("Duplicate Box", self.duplicate_selected_box, "Ctrl+D"),
            ("Copy Prev Boxes", self.copy_previous_boxes, "Ctrl+V"),
            ("Verify", self.toggle_verified, "Space"),
            ("Labels", self.toggle_label_display, "Ctrl+Shift+P"),
            ("Delete Box", self.delete_selected, QKeySequence.StandardKey.Delete),
            ("Save/Target", self.save_or_target_dialog, QKeySequence.StandardKey.SaveAs),
        ]
        for text, callback, shortcut in toolbar_actions:
            action = QAction(text, self)
            action.triggered.connect(callback)
            if shortcut is not None:
                action.setShortcut(QKeySequence(shortcut))
            toolbar.addAction(action)
            self.addAction(action)
        hidden_shortcuts = [
            ("Zoom In", lambda: self.add_zoom(10), "Ctrl++"),
            ("Zoom Out", lambda: self.add_zoom(-10), "Ctrl+-"),
            ("Fit", self.fit_window, "Ctrl+F"),
            ("Save", self.save_current, QKeySequence.StandardKey.Save),
            ("Accept Propagation Candidates", self.accept_propagation_candidates, "Return"),
            ("Edit Mode", lambda: self.set_mode("edit"), "Ctrl+J"),
        ]
        for text, callback, shortcut in hidden_shortcuts:
            action = QAction(text, self)
            action.triggered.connect(callback)
            action.setShortcut(QKeySequence(shortcut))
            self.addAction(action)
        self._register_parity_action("square", "Square Boxes", self.toggle_square_drawing, "Shift+W", view_menu)
        self._register_parity_action("show_boxes", "Show/Hide Boxes", self.toggle_boxes_display, "Ctrl+B", view_menu)
        self._register_parity_action("fit_width", "Fit Width", self.fit_width, "Ctrl+Shift+F", view_menu)
        self._register_parity_action("original_size", "Original Size", self.original_size, "Ctrl+0", view_menu)
        self._register_parity_action("brightness_up", "Brightness +", lambda: self.adjust_brightness(10), "Ctrl+]", view_menu)
        self._register_parity_action("brightness_down", "Brightness -", lambda: self.adjust_brightness(-10), "Ctrl+[", view_menu)
        self._register_parity_action("brightness_reset", "Brightness Reset", self.reset_brightness, "Ctrl+Alt+0", view_menu)
        self._register_parity_action("default_class", "Default Class", self.set_default_class_dialog, "Ctrl+Shift+D", tools_menu)
        self._register_parity_action("recent_folders", "Recent Folders", self.show_recent_folders, "Ctrl+R", tools_menu)
        self._register_parity_action("reset_settings", "Reset Settings", self.reset_settings, "Ctrl+Alt+R", tools_menu)
        self._register_parity_action("shortcuts", "Shortcut Help", self.show_shortcuts_dialog, "Ctrl+/", tools_menu)
        self.action_shortcuts.update(
            {
                "draw": "W",
                "smart": "S",
                "verify": "Space",
                "edit": "Ctrl+J",
                "smart_next": "Shift+D",
            }
        )
        toolbar.addSeparator()
        toolbar.addWidget(QLabel("Save Format"))
        self.save_format_combo.addItem("YOLO TXT", AnnotationFormat.YOLO.value)
        self.save_format_combo.addItem("VOC XML", AnnotationFormat.VOC_XML.value)
        self.save_format_combo.currentIndexChanged.connect(self.set_annotation_format_from_combo)
        toolbar.addWidget(self.save_format_combo)
        self.save_target_label.setMinimumWidth(320)
        toolbar.addWidget(self.save_target_label)

        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.addWidget(QLabel("Classes"))
        side_layout.addWidget(self.class_list)
        add_class = QPushButton("Add Class")
        add_class.clicked.connect(self.add_class)
        side_layout.addWidget(add_class)
        rename_class = QPushButton("Rename Class")
        rename_class.clicked.connect(self.rename_current_class_dialog)
        side_layout.addWidget(rename_class)
        delete_class = QPushButton("Delete Class")
        delete_class.clicked.connect(self.delete_current_class)
        side_layout.addWidget(delete_class)
        side_layout.addWidget(QLabel("Fast Crop Size"))
        self.crop_size_combo.addItems(["512", "768", "1024", "Full Image"])
        self.crop_size_combo.setCurrentText(str(self.crop_size))
        self.crop_size_combo.currentTextChanged.connect(
            lambda value: self.set_crop_size(0 if value == "Full Image" else int(value))
        )
        side_layout.addWidget(self.crop_size_combo)
        side_layout.addWidget(QLabel("Images"))
        side_layout.addWidget(self.image_list)
        side_layout.addWidget(QLabel("Boxes"))
        side_layout.addWidget(self.box_list)

        splitter = QSplitter()
        splitter.addWidget(self.canvas)
        splitter.addWidget(side)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(splitter)
        zoom_bar = QWidget()
        zoom_layout = QHBoxLayout(zoom_bar)
        zoom_layout.setContentsMargins(8, 0, 8, 0)
        zoom_layout.addWidget(QLabel("−"))
        self.zoom_slider.setObjectName("ZoomSlider")
        self.zoom_slider.setRange(25, 300)
        self.zoom_slider.setSingleStep(5)
        self.zoom_slider.setPageStep(25)
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self.set_zoom_from_slider)
        zoom_layout.addWidget(self.zoom_slider, 1)
        zoom_layout.addWidget(QLabel("+"))
        self.zoom_value_label.setMinimumWidth(48)
        zoom_layout.addWidget(self.zoom_value_label)
        layout.addWidget(zoom_bar)
        self.setCentralWidget(central)

        self.class_list.currentTextChanged.connect(self.set_current_label)
        self.class_list.itemDoubleClicked.connect(self.rename_class_item)
        self.box_list.currentRowChanged.connect(self.select_box)
        self.image_list.currentRowChanged.connect(self.select_image)
        self.canvas.boxes_changed.connect(self.refresh_boxes)
        self.canvas.boxes_changed.connect(self.auto_save_current)
        self.canvas.edit_completed.connect(self.record_annotation_edit)
        self.canvas.selected_changed.connect(self.sync_selected_box)
        self.canvas.smart_clicked.connect(self.smart_click)
        self.canvas.smart_box_drawn.connect(self.smart_box)
        self.canvas.box_menu_requested.connect(self.show_box_menu)
        self.canvas.mode_toggle_requested.connect(self.toggle_mode)

    def _register_parity_action(
        self,
        name: str,
        text: str,
        callback,
        shortcut: str,
        menu: QMenu,
    ) -> QAction:
        action = QAction(text, self)
        action.triggered.connect(callback)
        action.setShortcut(QKeySequence(shortcut))
        menu.addAction(action)
        self.addAction(action)
        self.actions_by_name[name] = action
        return action

    def _persist_settings(self) -> None:
        self.settings = AppSettings(
            last_image_dir=self.settings.last_image_dir,
            annotation_format=self.annotation_format.value
            if self.annotation_format is not AnnotationFormat.AUTO
            else self.settings.annotation_format,
            default_class=self.canvas.current_label,
            recent_folders=self.settings.recent_folders,
            brightness=self.canvas.brightness,
        )
        self.settings_store.save(self.settings)

    def _remember_folder(self, folder: Path) -> None:
        folder_text = str(folder)
        recent = (folder_text, *(item for item in self.settings.recent_folders if item != folder_text))[:10]
        self.settings = AppSettings(
            last_image_dir=folder_text,
            annotation_format=self.settings.annotation_format,
            default_class=self.canvas.current_label,
            recent_folders=recent,
            brightness=self.canvas.brightness,
        )
        self.settings_store.save(self.settings)

    def record_annotation_edit(self) -> None:
        if self._loading_image:
            return
        self.history.record(self.canvas.boxes, self.labels)
        self.update_history_actions()

    def update_history_actions(self) -> None:
        if self.undo_action is not None:
            self.undo_action.setEnabled(self.history.can_undo)
        if self.redo_action is not None:
            self.redo_action.setEnabled(self.history.can_redo)

    def undo_annotation_edit(self) -> None:
        if not self.history.can_undo:
            return
        self.restore_annotation_snapshot(self.history.undo())

    def redo_annotation_edit(self) -> None:
        if not self.history.can_redo:
            return
        self.restore_annotation_snapshot(self.history.redo())

    def restore_annotation_snapshot(self, snapshot: AnnotationSnapshot) -> None:
        selected_label = self.canvas.current_label
        self.labels = list(snapshot.labels)
        self.canvas.boxes = [Box(box.label, box.x1, box.y1, box.x2, box.y2, box.score) for box in snapshot.boxes]
        self.canvas.selected_index = 0 if self.canvas.boxes else -1
        if selected_label not in self.labels:
            selected_label = self.canvas.boxes[0].label if self.canvas.boxes else (self.labels[0] if self.labels else "object")
        self.canvas.current_label = selected_label
        self._refresh_classes(selected_label)
        self.refresh_boxes()
        self.update_history_actions()
        self.canvas.update()
        self.auto_save_current()

    def _refresh_classes(self, selected_label: str | None = None) -> None:
        selected_label = selected_label or self.canvas.current_label
        self.class_list.blockSignals(True)
        self.class_list.clear()
        for label in self.labels:
            self.class_list.addItem(label)
        if selected_label in self.labels:
            row = self.labels.index(selected_label)
        else:
            row = self.labels.index("object") if "object" in self.labels else 0
        self.class_list.setCurrentRow(row)
        self.class_list.blockSignals(False)

    def set_current_label(self, label: str) -> None:
        if label:
            if 0 <= self.canvas.selected_index < len(self.canvas.boxes):
                self.set_selected_box_label(label)
                return
            self.canvas.current_label = label
            self.status.showMessage(f"Current class: {label}")

    def set_mode(self, mode: str) -> None:
        self.canvas.set_mode(mode)
        self.status.showMessage(
            "智能模式：单指拖框自动贴合；双指点击自动框选"
            if mode == "smart"
            else "普通 LabelImg：手动画框"
        )

    def toggle_mode(self) -> None:
        self.set_mode("draw" if self.canvas.mode == "smart" else "smart")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Shift and not event.isAutoRepeat():
            self.toggle_mode()
            event.accept()
            return
        super().keyPressEvent(event)

    def set_crop_size(self, crop_size: int) -> None:
        self.crop_size = crop_size
        if hasattr(self.backend, "crop_size"):
            self.backend.crop_size = crop_size
        label = "Full Image" if crop_size <= 0 else str(crop_size)
        if self.crop_size_combo.currentText() != label:
            self.crop_size_combo.setCurrentText(label)
        self.status.showMessage(f"Fast crop size: {label}")

    def set_annotation_format_from_combo(self, *_args) -> None:
        fmt_value = self.save_format_combo.currentData()
        if fmt_value:
            self.set_annotation_format(AnnotationFormat(fmt_value))

    def set_annotation_format(self, fmt: AnnotationFormat) -> None:
        if fmt == AnnotationFormat.AUTO:
            return
        previous_path = self.current_label_path
        self.annotation_format = fmt
        index = self.save_format_combo.findData(fmt.value)
        if index >= 0 and self.save_format_combo.currentIndex() != index:
            self.save_format_combo.blockSignals(True)
            self.save_format_combo.setCurrentIndex(index)
            self.save_format_combo.blockSignals(False)
        if previous_path is not None and infer_format_from_path(previous_path) != fmt:
            self.current_label_path = None
        self.update_save_target_label()
        self.settings = AppSettings(
            last_image_dir=self.settings.last_image_dir,
            annotation_format=fmt.value,
            default_class=self.canvas.current_label,
            recent_folders=self.settings.recent_folders,
            brightness=self.canvas.brightness,
        )
        self.settings_store.save(self.settings)
        self.status.showMessage(f"Save format: {'VOC XML' if fmt == AnnotationFormat.VOC_XML else 'YOLO TXT'}")

    def set_save_label_path(self, label_path: Path) -> None:
        self.set_save_target(label_path)

    def default_label_path(self) -> Path | None:
        if self.current_image is None:
            return None
        if self.save_directory is not None:
            base_path = self.save_directory / self.current_image.name
            if self.annotation_format == AnnotationFormat.VOC_XML:
                return base_path.with_suffix(".xml")
            return base_path.with_suffix(".txt")
        if self.label_directory is not None:
            base_path = self.label_directory / self.current_image.name
            if self.annotation_format == AnnotationFormat.VOC_XML:
                return base_path.with_suffix(".xml")
            return base_path.with_suffix(".txt")
        if self.annotation_format == AnnotationFormat.VOC_XML:
            return voc_path_for_image(self.current_image)
        return yolo_path_for_image(self.current_image)

    def update_save_target_label(self) -> None:
        target = self.current_save_path()
        if target is None:
            self.save_target_label.setText("Auto Save: choose target")
            return
        self.save_target_label.setText(f"Auto Save: {target}")

    def current_save_path(self) -> Path | None:
        if self.save_directory is not None:
            return self.default_label_path()
        return self.current_label_path or self.default_label_path()

    def open_dialog(self) -> None:
        mode, ok = QInputDialog.getItem(self, "Open", "Open:", ["Image", "Folder"], 0, False)
        if not ok:
            return
        if mode == "Folder":
            path = QFileDialog.getExistingDirectory(self, "Open image folder", str(Path.home()))
            if path:
                self.open_image_path(Path(path))
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open image",
            str(Path.home()),
            "Images (*.jpg *.jpeg *.png *.bmp *.webp)",
        )
        if path:
            self.open_image_path(Path(path))

    def open_label_dialog(self) -> None:
        if self.current_image is None and not self.images:
            self.status.showMessage("Open an image or folder first")
            return
        mode, ok = QInputDialog.getItem(self, "Open Label", "Open label:", ["Label File", "Label Folder"], 0, False)
        if not ok:
            return
        if mode == "Label Folder":
            folder = QFileDialog.getExistingDirectory(self, "Open label folder", str(Path.home()))
            if folder:
                self.load_label_source(Path(folder))
            return
        start = str(self.current_image.parent if self.current_image is not None else Path.home())
        path, _ = QFileDialog.getOpenFileName(self, "Open label", start, "Annotations (*.xml *.txt)")
        if path:
            self.load_label_source(Path(path))

    def open_image_path(self, path: Path) -> None:
        self.label_directory = None
        self.save_directory = None
        if path.is_dir():
            self._remember_folder(path)
            self.images = sorted(child for child in path.iterdir() if child.suffix.lower() in IMAGE_SUFFIXES)
            self.image_index = 0 if self.images else -1
            self.refresh_image_list()
            self.load_current_image()
            return
        self._remember_folder(path.parent)
        self.images = [path]
        self.image_index = 0
        self.refresh_image_list()
        self.load_current_image()

    def refresh_image_list(self) -> None:
        self.image_list.blockSignals(True)
        self.image_list.clear()
        for image_path in self.images:
            item = QListWidgetItem(image_path.name)
            self.image_list.addItem(item)
        self.image_list.setCurrentRow(self.image_index)
        self.image_list.blockSignals(False)

    def select_image(self, row: int) -> None:
        if row < 0 or row >= len(self.images) or row == self.image_index:
            return
        if not self.save_current():
            self.image_list.blockSignals(True)
            self.image_list.setCurrentRow(self.image_index)
            self.image_list.blockSignals(False)
            return
        self.image_index = row
        self.image_list.blockSignals(True)
        self.image_list.setCurrentRow(row)
        self.image_list.blockSignals(False)
        self.load_current_image()

    def label_path_for_image(self, image_path: Path) -> Path | None:
        if self.label_directory is not None:
            return find_annotation_path(self.label_directory / image_path.name, self.annotation_format)
        return find_annotation_path(image_path, self.annotation_format)

    def load_label_source(self, path: Path) -> None:
        if path.is_dir():
            self.label_directory = path
            if self.current_image is not None:
                self.load_image_with_label(self.current_image, None)
            return
        self.label_directory = None
        if self.current_image is not None:
            self.load_image_with_label(self.current_image, path)

    def load_current_image(self) -> None:
        if self.image_index < 0 or self.image_index >= len(self.images):
            return
        self.load_image_with_label(self.images[self.image_index], None)

    def load_image_with_label(self, image_path: Path, label_path: Path | None = None) -> None:
        self.current_image = image_path
        self.propagation_candidates = ()
        self.canvas.candidate_boxes = ()
        self._loading_image = True
        try:
            self.image_size = self.canvas.set_image(image_path)
        except ValueError as exc:
            self._loading_image = False
            QMessageBox.warning(self, "Image error", str(exc))
            return
        try:
            resolved_label_path = label_path or self.label_path_for_image(image_path)
            self.current_label_path = resolved_label_path
            save_path = resolved_label_path or self.current_save_path()
            if save_path is not None:
                self.loaded_fingerprints[save_path] = self.save_coordinator.fingerprint(save_path)
                self.save_coordinator.expected[save_path] = self.loaded_fingerprints[save_path]
                if save_path.suffix.lower() == ".txt":
                    classes_path = save_path.parent / "classes.txt"
                    self.loaded_fingerprints[classes_path] = self.save_coordinator.fingerprint(classes_path)
                    self.save_coordinator.expected[classes_path] = self.loaded_fingerprints[classes_path]
            if resolved_label_path is not None:
                self.annotation_format = infer_format_from_path(resolved_label_path)
                self.set_annotation_format(self.annotation_format)
                boxes = load_annotation(resolved_label_path, self.labels, self.image_size)
            else:
                boxes = []
                self.update_save_target_label()
            self.canvas.set_boxes(boxes)
            self.history.reset(self.canvas.boxes, self.labels)
            self.update_history_actions()
        finally:
            self._loading_image = False
        position = f" ({self.image_index + 1}/{len(self.images)})" if self.images else ""
        label_name = resolved_label_path.name if resolved_label_path else "no label"
        self.status.showMessage(f"Loaded {image_path.name}{position} [{label_name}]")

    def prev_image(self) -> None:
        if self.images and self.image_index > 0:
            if not self.save_current():
                return
            self.image_index -= 1
            self.refresh_image_list()
            self.load_current_image()

    def next_image(self) -> None:
        if self.images and self.image_index < len(self.images) - 1:
            if not self.save_current():
                return
            self.image_index += 1
            self.refresh_image_list()
            self.load_current_image()

    def smart_next_image(self) -> None:
        if not self.images or self.image_index < 0 or self.image_index >= len(self.images) - 1:
            return
        if self.canvas.image_array is None:
            return
        previous = self.canvas.image_array.copy()
        previous_boxes = [Box(box.label, box.x1, box.y1, box.x2, box.y2, box.score) for box in self.canvas.boxes]
        if not self.save_current():
            return
        self.image_index += 1
        self.refresh_image_list()
        self.load_current_image()
        if self.canvas.image_array is None or not previous_boxes:
            return
        result = propagate_boxes(previous, self.canvas.image_array, previous_boxes, self.backend)
        if result.committed:
            self.canvas.boxes.extend(result.committed)
            self.canvas.selected_index = len(self.canvas.boxes) - 1
            self.canvas.boxes_changed.emit()
            self.canvas.selected_changed.emit()
            self.record_annotation_edit()
            self.canvas.update()
            self.status.showMessage(f"Smart next propagated {len(result.committed)} box(es)")
            return
        if result.candidates:
            self.propagation_candidates = result.candidates
            self.canvas.candidate_boxes = tuple(candidate.box for candidate in result.candidates)
            self.refresh_boxes()
            self.canvas.selected_changed.emit()
            self.canvas.update()
            self.status.showMessage(
                f"Smart next found {len(result.candidates)} low-confidence candidate(s); press Return to accept"
            )

    def accept_propagation_candidates(self) -> None:
        if not self.propagation_candidates:
            return
        self.canvas.boxes.extend(candidate.box for candidate in self.propagation_candidates)
        self.canvas.selected_index = len(self.canvas.boxes) - 1
        self.propagation_candidates = ()
        self.canvas.candidate_boxes = ()
        self.canvas.boxes_changed.emit()
        self.canvas.selected_changed.emit()
        self.record_annotation_edit()
        self.canvas.update()
        self.status.showMessage("Accepted propagation candidates")

    def smart_click(self, x: int, y: int) -> None:
        if self.canvas.image_array is None:
            return
        boxes = self.backend.detect_from_click(self.canvas.image_array, x, y, self.canvas.current_label)
        self.canvas.boxes.extend(boxes)
        if boxes:
            self.canvas.selected_index = len(self.canvas.boxes) - 1
        self.refresh_boxes()
        if boxes:
            self.record_annotation_edit()
        self.auto_save_current()
        self.canvas.update()
        self.status.showMessage(f"Smart click added {len(boxes)} box(es)")

    def smart_box(self, x1: int, y1: int, x2: int, y2: int) -> None:
        if self.canvas.image_array is None:
            return
        boxes = self.backend.refine_from_box(
            self.canvas.image_array,
            (x1, y1, x2, y2),
            self.canvas.current_label,
        )
        if not boxes:
            boxes = [Box(self.canvas.current_label, x1, y1, x2, y2).normalized()]
        self.canvas.boxes.extend(boxes)
        self.canvas.selected_index = len(self.canvas.boxes) - 1
        self.refresh_boxes()
        self.record_annotation_edit()
        self.auto_save_current()
        self.canvas.update()
        self.status.showMessage(f"Smart box added {len(boxes)} refined box(es)")

    def show_box_menu(self, index: int, global_pos: QPoint) -> None:
        if not (0 <= index < len(self.canvas.boxes)):
            return
        self.canvas.selected_index = index
        menu = QMenu(self)
        class_menu = menu.addMenu("Change Class")
        for label in self.labels:
            action = class_menu.addAction(label)
            action.triggered.connect(lambda checked=False, label=label: self.set_selected_box_label(label))
        delete_action = menu.addAction("Delete Box")
        delete_action.triggered.connect(self.delete_selected)
        menu.exec(global_pos)

    def set_selected_box_label(self, label: str) -> None:
        index = self.canvas.selected_index
        if not (0 <= index < len(self.canvas.boxes)) or label not in self.labels:
            return
        box = self.canvas.boxes[index].normalized()
        self.canvas.boxes[index] = Box(label, box.x1, box.y1, box.x2, box.y2, box.score)
        self.canvas.current_label = label
        self.canvas.boxes_changed.emit()
        self.canvas.selected_changed.emit()
        self.record_annotation_edit()
        self.canvas.update()
        self.status.showMessage(f"Changed box {index + 1} to {label}")

    def delete_selected(self) -> None:
        index = self.canvas.selected_index
        if 0 <= index < len(self.canvas.boxes):
            del self.canvas.boxes[index]
            self.canvas.selected_index = min(index, len(self.canvas.boxes) - 1)
            self.refresh_boxes()
            self.record_annotation_edit()
            self.auto_save_current()
            self.canvas.update()

    def duplicate_selected_box(self) -> None:
        box = self.canvas.selected_box()
        if box is None:
            return
        duplicated = Box(box.label, box.x1 + 5, box.y1 + 5, box.x2 + 5, box.y2 + 5, box.score)
        bounds = self.canvas.image_bounds()
        if bounds is not None:
            duplicated = duplicated.clipped(bounds)
        self.canvas.boxes.append(duplicated)
        self.canvas.selected_index = len(self.canvas.boxes) - 1
        self.canvas.boxes_changed.emit()
        self.canvas.selected_changed.emit()
        self.record_annotation_edit()
        self.canvas.update()

    def image_size_for_path(self, image_path: Path) -> tuple[int, int] | None:
        image = cv2.imread(str(image_path))
        if image is None:
            return None
        height, width = image.shape[:2]
        return width, height

    def copy_previous_boxes(self) -> None:
        if self.image_index <= 0 or self.image_index >= len(self.images):
            return
        previous_image = self.images[self.image_index - 1]
        label_path = self.label_path_for_image(previous_image)
        image_size = self.image_size_for_path(previous_image)
        if label_path is None or image_size is None:
            return
        copied_boxes = load_annotation(label_path, self.labels, image_size)
        self.canvas.boxes.extend(copied_boxes)
        if copied_boxes:
            self.canvas.selected_index = len(self.canvas.boxes) - 1
        self.canvas.boxes_changed.emit()
        self.canvas.selected_changed.emit()
        if copied_boxes:
            self.record_annotation_edit()
        self.canvas.update()

    def toggle_label_display(self) -> None:
        self.canvas.show_labels = not self.canvas.show_labels
        self.canvas.update()

    def toggle_boxes_display(self) -> None:
        self.canvas.show_boxes = not self.canvas.show_boxes
        self.canvas.update()

    def toggle_square_drawing(self) -> None:
        self.canvas.square_drawing = not self.canvas.square_drawing
        self.status.showMessage("Square boxes on" if self.canvas.square_drawing else "Square boxes off")

    def set_zoom(self, zoom_percent: int) -> None:
        self.zoom_at_canvas_point(zoom_percent, self.default_zoom_anchor())

    def zoom_at_canvas_point(self, zoom_percent: int, anchor: QPoint | None = None) -> None:
        self.canvas.zoom_at(zoom_percent, anchor)
        slider_value = max(self.zoom_slider.minimum(), min(self.zoom_slider.maximum(), self.canvas.zoom_percent))
        if self.zoom_slider.value() != slider_value:
            self.zoom_slider.blockSignals(True)
            self.zoom_slider.setValue(slider_value)
            self.zoom_slider.blockSignals(False)
        self.zoom_value_label.setText(f"{self.canvas.zoom_percent}%")

    def default_zoom_anchor(self) -> QPoint:
        if self.canvas.last_mouse_pos is not None:
            return self.canvas.last_mouse_pos
        return QPoint(self.canvas.width() // 2, self.canvas.height() // 2)

    def set_zoom_from_slider(self, zoom_percent: int) -> None:
        self.zoom_at_canvas_point(zoom_percent, self.default_zoom_anchor())

    def add_zoom(self, delta: int) -> None:
        self.set_zoom(self.canvas.zoom_percent + delta)

    def fit_window(self) -> None:
        self.canvas.fit_mode = "window"
        self.zoom_value_label.setText("Fit")
        self.canvas.update()

    def fit_width(self) -> None:
        if not self.canvas.pixmap:
            return
        zoom = int(round(self.canvas.width() * 100 / max(1, self.canvas.pixmap.width())))
        self.set_zoom(zoom)

    def original_size(self) -> None:
        self.set_zoom(100)

    def adjust_brightness(self, delta: int) -> None:
        self.canvas.apply_brightness(self.canvas.brightness + delta)
        self._persist_settings()

    def reset_brightness(self) -> None:
        self.canvas.apply_brightness(0)
        self._persist_settings()

    def set_default_class_dialog(self) -> None:
        label, ok = QInputDialog.getItem(self, "Default Class", "Class:", self.labels, 0, False)
        if ok and label:
            self.canvas.current_label = label
            self._refresh_classes(label)
            self._persist_settings()

    def show_recent_folders(self) -> None:
        if not self.settings.recent_folders:
            self.status.showMessage("No recent folders")
            return
        folder, ok = QInputDialog.getItem(self, "Recent Folders", "Open:", list(self.settings.recent_folders), 0, False)
        if ok and folder:
            self.open_image_path(Path(folder))

    def reset_settings(self) -> None:
        self.settings = AppSettings()
        self.settings_store.save(self.settings)
        self.canvas.apply_brightness(0)
        self.canvas.current_label = self.settings.default_class
        self._refresh_classes(self.canvas.current_label)
        self.status.showMessage("Settings reset")

    def show_shortcuts_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Shortcuts")
        layout = QVBoxLayout(dialog)
        search = QLineEdit()
        search.setPlaceholderText("Search shortcuts")
        layout.addWidget(search)
        shortcuts = QListWidget()
        rows = [
            f"{name}: {shortcut}"
            for name, shortcut in sorted(
                {
                    **self.action_shortcuts,
                    **{key: action.shortcut().toString() for key, action in self.actions_by_name.items()},
                }.items()
            )
        ]
        shortcuts.addItems(rows)
        layout.addWidget(shortcuts)

        def filter_rows(text: str) -> None:
            needle = text.casefold()
            for index in range(shortcuts.count()):
                item = shortcuts.item(index)
                item.setHidden(needle not in item.text().casefold())

        search.textChanged.connect(filter_rows)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.resize(420, 420)
        dialog.exec()

    def toggle_verified(self) -> None:
        if self.current_image is None:
            return
        if self.current_image in self.verified_images:
            self.verified_images.remove(self.current_image)
            self.status.showMessage(f"Unverified {self.current_image.name}")
        else:
            self.verified_images.add(self.current_image)
            self.status.showMessage(f"Verified {self.current_image.name}")

    def save_current(self, show_status: bool = True) -> bool:
        if not self.current_image or not self.image_size:
            return True
        label_path = self.current_save_path()
        if label_path is None:
            return True
        if self._saving_annotation:
            return True
        self._saving_annotation = True
        try:
            label_path.parent.mkdir(parents=True, exist_ok=True)
            if self.save_directory is None:
                self.current_label_path = label_path
            self.annotation_format = infer_format_from_path(label_path)
            self.set_annotation_format(self.annotation_format)
            if label_path not in self.save_coordinator.expected:
                self.save_coordinator.expected[label_path] = self.loaded_fingerprints.get(
                    label_path, self.save_coordinator.fingerprint(label_path)
                )
            result = self.save_coordinator.save_annotation_atomic(
                label_path, self.canvas.boxes, self.labels, self.image_size, self.current_image
            )
            self.save_state = result.state
            if result.state is not SaveState.SAVED:
                detail = result.error or ", ".join(path.name for path in result.conflicts)
                self.status.showMessage(f"Save {result.state.value}: {detail}")
                return False
            self.loaded_fingerprints.update(result.fingerprints)
            self.update_save_target_label()
            if show_status:
                self.status.showMessage(f"Saved {label_path.name}")
            return True
        finally:
            self._saving_annotation = False

    def auto_save_current(self) -> None:
        if self._loading_image or self._saving_annotation:
            return
        if self.current_image is None or self.image_size is None:
            return
        self.save_current(show_status=False)

    def set_save_target(self, path: Path) -> None:
        if path.is_dir():
            self.save_directory = path
            self.current_label_path = None
        else:
            self.save_directory = None
            self.current_label_path = path
            self.set_annotation_format(infer_format_from_path(path))
        self.update_save_target_label()
        self.auto_save_current()

    def save_target_dialog(self) -> None:
        if not self.current_image:
            return
        mode, ok = QInputDialog.getItem(
            self,
            "Save/Target",
            "Save to:",
            ["Label File", "Label Folder"],
            0,
            False,
        )
        if not ok:
            return
        if mode == "Label Folder":
            folder = QFileDialog.getExistingDirectory(self, "Save label folder", str(Path.home()))
            if folder:
                self.set_save_target(Path(folder))
            return
        current_target = self.current_save_path() or self.current_image.with_suffix(".txt")
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save annotation as",
            str(current_target),
            "YOLO TXT (*.txt);;Pascal VOC XML (*.xml)",
        )
        if not path:
            return
        label_path = Path(path)
        if not label_path.suffix:
            label_path = label_path.with_suffix(".xml" if "XML" in selected_filter else ".txt")
        self.set_save_target(label_path)

    def save_or_target_dialog(self) -> None:
        if self.current_save_path() is None:
            self.save_target_dialog()
            return
        self.save_current()
        self.save_target_dialog()

    def rename_class(self, old_label: str, new_label: str) -> bool:
        old_label = old_label.strip()
        new_label = new_label.strip()
        if not old_label or not new_label or old_label not in self.labels:
            return False
        if new_label != old_label and new_label in self.labels:
            return False
        self.labels[self.labels.index(old_label)] = new_label
        for index, box in enumerate(self.canvas.boxes):
            if box.label == old_label:
                normalized = box.normalized()
                self.canvas.boxes[index] = Box(
                    new_label,
                    normalized.x1,
                    normalized.y1,
                    normalized.x2,
                    normalized.y2,
                    normalized.score,
                )
        if self.canvas.current_label == old_label:
            self.canvas.current_label = new_label
        self._refresh_classes(new_label)
        self.refresh_boxes()
        self.record_annotation_edit()
        self.auto_save_current()
        self.canvas.update()
        self.status.showMessage(f"Renamed class {old_label} to {new_label}")
        return True

    def delete_class(self, label: str) -> bool:
        label = label.strip()
        if not label or label not in self.labels or len(self.labels) <= 1:
            return False
        self.labels.remove(label)
        fallback_label = "object" if "object" in self.labels else self.labels[0]
        for index, box in enumerate(self.canvas.boxes):
            if box.label == label:
                normalized = box.normalized()
                self.canvas.boxes[index] = Box(
                    fallback_label,
                    normalized.x1,
                    normalized.y1,
                    normalized.x2,
                    normalized.y2,
                    normalized.score,
                )
        if self.canvas.current_label == label:
            self.canvas.current_label = fallback_label
        self._refresh_classes(fallback_label)
        self.refresh_boxes()
        self.record_annotation_edit()
        self.auto_save_current()
        self.canvas.update()
        self.status.showMessage(f"Deleted class {label}")
        return True

    def rename_current_class_dialog(self) -> None:
        item = self.class_list.currentItem()
        if item is None:
            return
        self.rename_class_item(item)

    def rename_class_item(self, item: QListWidgetItem) -> None:
        old_label = item.text()
        new_label, ok = QInputDialog.getText(self, "Rename class", "Class name:", text=old_label)
        if ok:
            self.rename_class(old_label, new_label)

    def delete_current_class(self) -> None:
        item = self.class_list.currentItem()
        if item is not None:
            self.delete_class(item.text())

    def refresh_boxes(self) -> None:
        self.box_list.blockSignals(True)
        self.box_list.clear()
        for index, box in enumerate(self.canvas.boxes):
            item = QListWidgetItem(f"{index + 1}. {box.label} [{box.x1},{box.y1},{box.x2},{box.y2}]")
            self.box_list.addItem(item)
        self.box_list.blockSignals(False)
        self.sync_selected_box()

    def sync_selected_box(self) -> None:
        self.box_list.blockSignals(True)
        self.box_list.setCurrentRow(self.canvas.selected_index)
        self.box_list.blockSignals(False)
        selected = self.canvas.selected_box()
        if selected and selected.label in self.labels:
            self.class_list.blockSignals(True)
            self.class_list.setCurrentRow(self.labels.index(selected.label))
            self.class_list.blockSignals(False)

    def select_box(self, row: int) -> None:
        self.canvas.selected_index = row
        self.canvas.selected_changed.emit()
        self.canvas.update()

    def add_class(self) -> None:
        label, ok = QInputDialog.getText(self, "Add class", "Class name:")
        label = label.strip()
        if ok and label and label not in self.labels:
            self.labels.append(label)
            self._refresh_classes()


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
