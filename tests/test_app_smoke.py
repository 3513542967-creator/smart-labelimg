import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QSlider, QToolBar
from PySide6.QtGui import QKeySequence, QPixmap
from PySide6.QtCore import QPoint
import cv2
import numpy as np

from smart_labelimg import app as app_module
from smart_labelimg.app import MainWindow
from smart_labelimg.annotation import AnnotationFormat, Box, save_voc_xml, save_yolo
from smart_labelimg.save_coordinator import SaveResult, SaveState


def test_main_window_initializes():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    assert window.windowTitle() == "Smart LabelImg"
    assert "car" in window.labels
    assert window.canvas.mode == "smart"
    assert window.canvas.current_label == "object"
    window.close()


def test_toolbar_does_not_include_auto_detect():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    toolbar = window.findChild(QToolBar, "Main")
    action_texts = [action.text() for action in toolbar.actions()]

    assert "Auto Detect Class" not in action_texts
    window.close()


def test_toolbar_uses_single_open_and_open_label_actions():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    toolbar = window.findChild(QToolBar, "Main")
    action_texts = [action.text() for action in toolbar.actions()]

    assert "Open" in action_texts
    assert "Open Label" in action_texts
    assert "Open Image" not in action_texts
    assert "Open Folder" not in action_texts
    assert "Open Image + Label" not in action_texts
    assert "Similar" not in action_texts
    window.close()


def test_toolbar_uses_icons_for_navigation_and_combines_save_target():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    toolbar = window.findChild(QToolBar, "Main")
    action_texts = [action.text() for action in toolbar.actions()]

    assert "←" in action_texts
    assert "→" in action_texts
    assert "Prev" not in action_texts
    assert "Next" not in action_texts
    assert "Save/Target" in action_texts
    assert "Save" not in action_texts
    assert "Save Target" not in action_texts
    assert "Zoom In" not in action_texts
    assert "Zoom Out" not in action_texts
    assert "Fit" not in action_texts
    window.close()


def test_bottom_zoom_slider_controls_canvas_zoom():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    slider = window.findChild(QSlider, "ZoomSlider")
    assert slider is not None

    slider.setValue(150)

    assert window.canvas.zoom_percent == 150
    assert window.canvas.fit_mode == "manual"
    assert "150%" in window.zoom_value_label.text()
    window.close()


def test_zoom_uses_labelimg_style_cursor_relative_view_shift():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.canvas.resize(400, 300)
    window.canvas.pixmap = QPixmap(100, 50)
    window.set_zoom(100)
    anchor = QPoint(190, 150)
    old_rect = window.canvas.image_rect()

    window.zoom_at_canvas_point(200, anchor)
    new_rect = window.canvas.image_rect()

    move_x = (anchor.x() - 0.1 * window.canvas.width()) / (window.canvas.width() - 0.2 * window.canvas.width())
    expected_x = int(round(old_rect.x() - move_x * (new_rect.width() - old_rect.width())))
    assert new_rect.x() == expected_x
    assert window.canvas.zoom_percent == 200
    assert window.canvas.fit_mode == "manual"
    window.close()


def test_default_zoom_anchor_ignores_selected_box_like_labelimg():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.canvas.resize(400, 300)
    window.canvas.pixmap = QPixmap(100, 50)
    window.canvas.boxes = [Box("object", 0, 0, 20, 20)]
    window.canvas.selected_index = 0
    window.canvas.last_mouse_pos = None

    expected_center = QPoint(window.canvas.width() // 2, window.canvas.height() // 2)
    assert window.default_zoom_anchor() == expected_center
    window.close()


def test_selected_box_label_can_be_changed():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.canvas.boxes = [Box("object", 10, 20, 40, 60)]
    window.canvas.selected_index = 0

    window.set_selected_box_label("car")

    assert window.canvas.boxes[0].label == "car"
    window.close()


def test_edit_menu_exposes_undo_redo_shortcuts():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    assert window.undo_action is not None
    assert window.redo_action is not None
    assert window.undo_action.shortcut().matches(QKeySequence(QKeySequence.StandardKey.Undo)) == QKeySequence.SequenceMatch.ExactMatch
    assert window.redo_action.shortcut().matches(QKeySequence(QKeySequence.StandardKey.Redo)) == QKeySequence.SequenceMatch.ExactMatch
    assert not window.undo_action.isEnabled()
    assert not window.redo_action.isEnabled()
    window.close()


def test_undo_and_redo_restore_boxes_and_autosave(tmp_path):
    image_path = tmp_path / "one.jpg"
    label_path = tmp_path / "one.xml"
    cv2.imwrite(str(image_path), np.zeros((80, 120, 3), dtype=np.uint8))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    window.open_image_path(image_path)
    window.set_save_target(label_path)
    window.canvas.boxes = [Box("car", 10, 12, 50, 60)]
    window.canvas.selected_index = 0
    window.record_annotation_edit()
    window.duplicate_selected_box()

    assert window.undo_action.isEnabled()
    window.undo_annotation_edit()
    assert window.canvas.boxes == [Box("car", 10, 12, 50, 60)]
    assert window.redo_action.isEnabled()
    assert "<name>car</name>" in label_path.read_text(encoding="utf-8")
    assert label_path.read_text(encoding="utf-8").count("<object>") == 1

    window.redo_annotation_edit()
    assert len(window.canvas.boxes) == 2
    assert label_path.read_text(encoding="utf-8").count("<object>") == 2
    window.close()


def test_keyboard_move_records_undo_history():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.canvas.pixmap = QPixmap(120, 80)
    window.canvas.boxes = [Box("car", 10, 12, 50, 60)]
    window.canvas.selected_index = 0
    window.history.reset(window.canvas.boxes, window.labels)

    assert window.canvas.move_selected_box(1, 0)
    window.canvas.edit_completed.emit()

    assert window.undo_action.isEnabled()
    window.undo_annotation_edit()
    assert window.canvas.boxes == [Box("car", 10, 12, 50, 60)]
    window.close()


def test_clicking_class_changes_selected_box_label():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.canvas.boxes = [Box("object", 10, 20, 40, 60)]
    window.canvas.selected_index = 0

    window.set_current_label("car")

    assert window.canvas.boxes[0].label == "car"
    assert window.canvas.current_label == "car"
    window.close()


def test_selected_box_moves_within_image_bounds():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.canvas.pixmap = QPixmap(100, 80)
    window.canvas.boxes = [Box("object", 90, 70, 99, 79)]
    window.canvas.selected_index = 0

    assert window.canvas.move_selected_box(10, 10)
    assert (window.canvas.boxes[0].x1, window.canvas.boxes[0].y1, window.canvas.boxes[0].x2, window.canvas.boxes[0].y2) == (
        90,
        70,
        99,
        79,
    )

    assert window.canvas.move_selected_box(-5, -7)
    assert (window.canvas.boxes[0].x1, window.canvas.boxes[0].y1, window.canvas.boxes[0].x2, window.canvas.boxes[0].y2) == (
        85,
        63,
        94,
        72,
    )
    window.close()


def test_selected_box_handle_hit_detection_and_resize():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.canvas.pixmap = QPixmap(100, 80)
    window.canvas.boxes = [Box("object", 10, 20, 40, 60)]
    window.canvas.selected_index = 0

    assert window.canvas.handle_at_image_point(10, 20) == "top_left"
    assert window.canvas.handle_at_image_point(40, 60) == "bottom_right"
    assert window.canvas.resize_selected_box("bottom_right", 55, 70)
    assert window.canvas.boxes[0] == Box("object", 10, 20, 55, 70)

    assert window.canvas.resize_selected_box("top_left", -20, -10)
    assert window.canvas.boxes[0] == Box("object", 0, 0, 55, 70)
    window.close()


def test_load_image_with_explicit_xml_label_path(tmp_path):
    image_path = tmp_path / "sample.jpg"
    label_path = tmp_path / "elsewhere.xml"
    cv2.imwrite(str(image_path), np.zeros((80, 120, 3), dtype=np.uint8))
    save_voc_xml(label_path, [Box("car", 10, 12, 50, 60)], image_size=(120, 80), image_path=image_path)
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    window.load_image_with_label(image_path, label_path)

    assert window.current_image == image_path
    assert window.current_label_path == label_path
    assert window.canvas.boxes == [Box("car", 10, 12, 50, 60)]
    assert "elsewhere.xml" in window.save_target_label.text()
    window.close()


def test_crop_size_setting_updates_backend():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    window.set_crop_size(512)

    assert window.crop_size == 512
    if hasattr(window.backend, "crop_size"):
        assert window.backend.crop_size == 512
    window.close()


def test_crop_size_can_be_set_to_full_image_and_box_scale_defaults_to_one_point_five():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    window.set_crop_size(0)

    assert window.crop_size == 0
    assert window.crop_size_combo.currentText() == "Full Image"
    if hasattr(window.backend, "crop_size"):
        assert window.backend.crop_size == 0
        assert window.backend.box_crop_scale == 1.5
    window.close()


def test_class_names_can_be_renamed_and_removed():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.canvas.boxes = [Box("car", 10, 20, 40, 60)]
    window.canvas.selected_index = 0

    assert window.rename_class("car", "sedan")
    assert "sedan" in window.labels
    assert "car" not in window.labels
    assert window.canvas.boxes[0].label == "sedan"

    assert window.delete_class("sedan")
    assert "sedan" not in window.labels
    assert window.canvas.boxes[0].label == "object"
    window.close()


def test_double_clicking_class_renames_all_matching_boxes(monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.canvas.boxes = [
        Box("car", 10, 20, 40, 60),
        Box("car", 50, 20, 70, 60),
        Box("person", 1, 2, 10, 20),
    ]

    monkeypatch.setattr(app_module.QInputDialog, "getText", lambda *args, **kwargs: ("sedan", True))
    item = window.class_list.item(window.labels.index("car"))

    window.class_list.itemDoubleClicked.emit(item)

    assert "sedan" in window.labels
    assert "car" not in window.labels
    assert [box.label for box in window.canvas.boxes] == ["sedan", "sedan", "person"]
    window.close()


def test_open_label_folder_matches_current_folder_image(tmp_path):
    image_folder = tmp_path / "images"
    label_folder = tmp_path / "labels"
    image_folder.mkdir()
    label_folder.mkdir()
    first_image = image_folder / "one.jpg"
    second_image = image_folder / "two.jpg"
    cv2.imwrite(str(first_image), np.zeros((80, 120, 3), dtype=np.uint8))
    cv2.imwrite(str(second_image), np.zeros((80, 120, 3), dtype=np.uint8))
    save_yolo(label_folder / "one.txt", [Box("car", 10, 12, 50, 60)], ["object", "person", "vehicle", "car"], (120, 80))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    window.open_image_path(image_folder)
    window.load_label_source(label_folder)

    assert window.current_image == first_image
    assert window.current_label_path == label_folder / "one.txt"
    assert window.canvas.boxes == [Box("car", 10, 12, 50, 60)]
    assert "labels/one.txt" in window.save_target_label.text()
    window.close()


def test_save_target_folder_autosaves_annotation_changes(tmp_path):
    image_folder = tmp_path / "images"
    label_folder = tmp_path / "labels"
    image_folder.mkdir()
    label_folder.mkdir()
    image_path = image_folder / "one.jpg"
    cv2.imwrite(str(image_path), np.zeros((80, 120, 3), dtype=np.uint8))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    window.open_image_path(image_folder)
    window.set_save_target(label_folder)
    window.canvas.boxes = [Box("car", 10, 12, 50, 60)]
    window.canvas.boxes_changed.emit()

    saved_path = label_folder / "one.txt"
    assert saved_path.exists()
    assert saved_path.read_text(encoding="utf-8").startswith("3 ")
    assert "labels/one.txt" in window.save_target_label.text()
    window.close()


def test_save_target_file_autosaves_label_renames(tmp_path):
    image_path = tmp_path / "one.jpg"
    label_path = tmp_path / "custom.xml"
    cv2.imwrite(str(image_path), np.zeros((80, 120, 3), dtype=np.uint8))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    window.open_image_path(image_path)
    window.canvas.boxes = [Box("car", 10, 12, 50, 60)]
    window.set_save_target(label_path)
    window.rename_class("car", "sedan")

    saved_text = label_path.read_text(encoding="utf-8")
    assert "<name>sedan</name>" in saved_text
    assert "custom.xml" in window.save_target_label.text()
    window.close()


def test_image_folder_populates_file_list_and_selects_by_row(tmp_path):
    image_folder = tmp_path / "images"
    image_folder.mkdir()
    first_image = image_folder / "one.jpg"
    second_image = image_folder / "two.jpg"
    cv2.imwrite(str(first_image), np.zeros((80, 120, 3), dtype=np.uint8))
    cv2.imwrite(str(second_image), np.zeros((80, 120, 3), dtype=np.uint8))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    window.open_image_path(image_folder)
    window.select_image(1)

    assert window.image_list.count() == 2
    assert window.current_image == second_image
    assert window.image_list.currentRow() == 1
    window.close()


def test_navigation_stays_on_current_image_after_save_failure(tmp_path, monkeypatch):
    image_folder = tmp_path / "images"
    image_folder.mkdir()
    first_image = image_folder / "one.jpg"
    second_image = image_folder / "two.jpg"
    cv2.imwrite(str(first_image), np.zeros((80, 120, 3), dtype=np.uint8))
    cv2.imwrite(str(second_image), np.zeros((80, 120, 3), dtype=np.uint8))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.open_image_path(image_folder)
    monkeypatch.setattr(
        window.save_coordinator,
        "save_annotation_atomic",
        lambda *args, **kwargs: SaveResult(SaveState.FAILED, {}, error="disk full"),
    )

    window.next_image()

    assert window.current_image == first_image
    assert window.image_index == 0
    assert window.image_list.currentRow() == 0
    assert window.save_state is SaveState.FAILED
    window.close()


def test_loaded_yolo_classes_conflict_blocks_save(tmp_path):
    image_path = tmp_path / "one.jpg"
    label_path = tmp_path / "one.txt"
    classes_path = tmp_path / "classes.txt"
    cv2.imwrite(str(image_path), np.zeros((80, 120, 3), dtype=np.uint8))
    label_path.write_text("old annotation\n", encoding="utf-8")
    classes_path.write_text("object\ncar\n", encoding="utf-8")
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.load_image_with_label(image_path, label_path)
    classes_path.write_text("external\n", encoding="utf-8")
    window.canvas.boxes = [Box("car", 10, 12, 50, 60)]

    assert not window.save_current()
    assert window.save_state is SaveState.CONFLICT
    assert label_path.read_text(encoding="utf-8") == "old annotation\n"
    assert classes_path.read_text(encoding="utf-8") == "external\n"
    window.close()


def test_duplicate_selected_box_adds_a_second_offset_box():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.canvas.pixmap = QPixmap(100, 80)
    window.canvas.boxes = [Box("car", 10, 20, 40, 60)]
    window.canvas.selected_index = 0

    window.duplicate_selected_box()

    assert len(window.canvas.boxes) == 2
    assert window.canvas.boxes[1] == Box("car", 15, 25, 45, 65)
    assert window.canvas.selected_index == 1
    window.close()


def test_copy_previous_boxes_loads_prior_image_annotations(tmp_path):
    image_folder = tmp_path / "images"
    label_folder = tmp_path / "labels"
    image_folder.mkdir()
    label_folder.mkdir()
    first_image = image_folder / "one.jpg"
    second_image = image_folder / "two.jpg"
    cv2.imwrite(str(first_image), np.zeros((80, 120, 3), dtype=np.uint8))
    cv2.imwrite(str(second_image), np.zeros((80, 120, 3), dtype=np.uint8))
    save_yolo(label_folder / "one.txt", [Box("car", 10, 12, 50, 60)], ["object", "person", "vehicle", "car"], (120, 80))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    window.open_image_path(image_folder)
    window.load_label_source(label_folder)
    window.select_image(1)
    window.copy_previous_boxes()

    assert window.current_image == second_image
    assert window.canvas.boxes == [Box("car", 10, 12, 50, 60)]
    window.close()


class NoRefineBackend:
    def refine_from_box(self, image, query_box, label):
        return []


def test_smart_next_action_uses_shift_d_shortcut():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    toolbar = window.findChild(QToolBar, "Main")
    smart_next = next(action for action in toolbar.actions() if action.text() == "Smart →")

    assert smart_next.shortcut().matches(QKeySequence("Shift+D")) == QKeySequence.SequenceMatch.ExactMatch
    window.close()


def test_labelimg_shortcuts_are_exposed():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    assert window.action_shortcuts["draw"] == "W"
    assert window.action_shortcuts["smart"] == "S"
    assert window.action_shortcuts["verify"] == "Space"
    assert window.action_shortcuts["edit"] == "Ctrl+J"
    assert window.action_shortcuts["smart_next"] == "Shift+D"
    window.close()


def test_labelimg_parity_actions_are_available_without_toolbar_clutter():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    for name in [
        "square",
        "show_boxes",
        "fit_width",
        "original_size",
        "brightness_up",
        "brightness_down",
        "brightness_reset",
        "default_class",
        "recent_folders",
        "reset_settings",
        "shortcuts",
    ]:
        assert name in window.actions_by_name

    toolbar = window.findChild(QToolBar, "Main")
    action_texts = [action.text() for action in toolbar.actions()]
    assert "Brightness +" not in action_texts
    assert "Shortcut Help" not in action_texts
    window.close()


def test_smart_next_propagates_current_boxes_to_next_image_and_records_one_history_entry(tmp_path):
    image_folder = tmp_path / "images"
    image_folder.mkdir()
    first_image = image_folder / "one.jpg"
    second_image = image_folder / "two.jpg"
    first = np.zeros((100, 140, 3), dtype=np.uint8)
    second = first.copy()
    first[30:60, 30:70] = (255, 255, 255)
    second[34:64, 38:78] = (255, 255, 255)
    cv2.imwrite(str(first_image), cv2.cvtColor(first, cv2.COLOR_RGB2BGR))
    cv2.imwrite(str(second_image), cv2.cvtColor(second, cv2.COLOR_RGB2BGR))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.backend = NoRefineBackend()
    window.open_image_path(image_folder)
    window.canvas.boxes = [Box("car", 30, 30, 70, 60)]

    window.smart_next_image()

    assert window.current_image == second_image
    assert len(window.canvas.boxes) == 1
    assert abs(window.canvas.boxes[0].x1 - 38) <= 1
    assert abs(window.canvas.boxes[0].y1 - 34) <= 1
    assert window.undo_action.isEnabled()
    window.undo_annotation_edit()
    assert window.canvas.boxes == []
    window.close()


def test_low_confidence_smart_next_candidates_are_visible_but_not_autosaved(tmp_path):
    image_folder = tmp_path / "images"
    image_folder.mkdir()
    first_image = image_folder / "one.jpg"
    second_image = image_folder / "two.jpg"
    cv2.imwrite(str(first_image), np.zeros((80, 100, 3), dtype=np.uint8))
    noise = np.indices((80, 100)).sum(axis=0).astype(np.uint8)
    noise = np.stack([noise, np.roll(noise, 7, axis=1), np.roll(noise, 13, axis=0)], axis=2)
    cv2.imwrite(str(second_image), cv2.cvtColor(noise, cv2.COLOR_RGB2BGR))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.backend = NoRefineBackend()
    window.open_image_path(image_folder)
    window.canvas.boxes = [Box("car", 10, 10, 30, 30)]

    window.smart_next_image()

    assert window.current_image == second_image
    assert window.canvas.boxes == []
    assert len(window.canvas.candidate_boxes) == 1
    assert len(window.propagation_candidates) == 1
    assert window.propagation_candidates[0].requires_confirmation
    assert not (image_folder / "two.txt").exists()

    window.accept_propagation_candidates()

    assert len(window.canvas.boxes) == 1
    assert window.canvas.candidate_boxes == ()
    assert len(window.propagation_candidates) == 0
    assert (image_folder / "two.txt").exists()
    window.close()


def test_display_labels_and_zoom_controls_update_canvas():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    window.toggle_label_display()
    assert not window.canvas.show_labels

    window.set_zoom(125)
    assert window.canvas.zoom_percent == 125
    assert window.canvas.fit_mode == "manual"

    window.fit_window()
    assert window.canvas.fit_mode == "window"
    window.close()


def test_toggle_verified_tracks_current_image(tmp_path):
    image_path = tmp_path / "one.jpg"
    cv2.imwrite(str(image_path), np.zeros((80, 120, 3), dtype=np.uint8))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    window.open_image_path(image_path)
    window.toggle_verified()

    assert image_path in window.verified_images
    window.toggle_verified()
    assert image_path not in window.verified_images
    window.close()


def test_save_format_and_explicit_save_path_are_used(tmp_path):
    image_path = tmp_path / "sample.jpg"
    cv2.imwrite(str(image_path), np.zeros((80, 120, 3), dtype=np.uint8))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.load_image_with_label(image_path, None)
    window.canvas.boxes = [Box("car", 10, 20, 40, 60)]

    window.save_format_combo.setCurrentIndex(window.save_format_combo.findData(AnnotationFormat.VOC_XML.value))
    window.save_current()
    assert (tmp_path / "sample.xml").exists()

    yolo_path = tmp_path / "labels" / "custom.txt"
    window.set_save_label_path(yolo_path)
    window.save_current()
    assert yolo_path.exists()
    assert "custom.txt" in window.save_target_label.text()
    window.close()


def test_shift_toggle_switches_between_smart_and_draw_modes():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    assert window.canvas.mode == "smart"
    window.toggle_mode()
    assert window.canvas.mode == "draw"
    window.toggle_mode()
    assert window.canvas.mode == "smart"
    window.close()
