from smart_labelimg.annotation import Box
from smart_labelimg.history import AnnotationHistory


def test_undo_and_redo_restore_independent_box_copies():
    history = AnnotationHistory()
    initial_boxes = [Box("car", 1, 2, 10, 20)]
    history.reset(initial_boxes, ["car"])

    initial_boxes[0].x1 = 99
    history.record([Box("car", 5, 2, 14, 20)], ["car"])

    undo_snapshot = history.undo()
    assert undo_snapshot.boxes == (Box("car", 1, 2, 10, 20),)

    redo_snapshot = history.redo()
    assert redo_snapshot.boxes == (Box("car", 5, 2, 14, 20),)


def test_new_edit_after_undo_clears_redo():
    history = AnnotationHistory()
    history.reset([], ["car"])
    history.record([Box("car", 1, 1, 5, 5)], ["car"])

    history.undo()
    history.record([Box("car", 2, 2, 6, 6)], ["car"])

    assert not history.can_redo


def test_history_limit_keeps_latest_snapshots():
    history = AnnotationHistory(limit=3)
    history.reset([], ["car"])
    history.record([Box("car", 1, 1, 5, 5)], ["car"])
    history.record([Box("car", 2, 2, 6, 6)], ["car"])
    history.record([Box("car", 3, 3, 7, 7)], ["car"])

    assert history.undo().boxes == (Box("car", 2, 2, 6, 6),)
    assert history.undo().boxes == (Box("car", 1, 1, 5, 5),)
    assert not history.can_undo
