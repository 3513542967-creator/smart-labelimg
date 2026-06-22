from smart_labelimg.labels import COCO_LABELS, SIMPLE_LABELS


def test_coco_labels_include_80_standard_classes_in_stable_order():
    assert len(COCO_LABELS) == 80
    assert COCO_LABELS[:8] == (
        "person",
        "bicycle",
        "car",
        "motorcycle",
        "airplane",
        "bus",
        "train",
        "truck",
    )
    assert COCO_LABELS[-1] == "toothbrush"


def test_simple_labels_are_small_click_first_default_set():
    assert SIMPLE_LABELS == [
        "object",
        "person",
        "vehicle",
        "car",
        "truck",
        "bus",
        "bike",
        "motorcycle",
    ]
