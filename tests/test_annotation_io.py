from pathlib import Path

from smart_labelimg.annotation import (
    AnnotationFormat,
    Box,
    find_annotation_path,
    load_annotation,
    load_voc_xml,
    load_yolo,
    save_annotation,
    save_voc_xml,
    save_yolo,
)


def test_yolo_roundtrip_preserves_label_and_box(tmp_path: Path):
    labels = ["person", "car"]
    boxes = [Box(label="car", x1=10, y1=20, x2=50, y2=80, score=0.9)]
    label_path = tmp_path / "image.txt"

    save_yolo(label_path, boxes, labels, image_size=(100, 100))
    loaded = load_yolo(label_path, labels, image_size=(100, 100))

    assert len(loaded) == 1
    assert loaded[0].label == "car"
    assert loaded[0].x1 == 10
    assert loaded[0].y1 == 20
    assert loaded[0].x2 == 50
    assert loaded[0].y2 == 80


def test_voc_xml_roundtrip_preserves_label_and_box(tmp_path: Path):
    boxes = [
        Box(label="person", x1=4, y1=8, x2=70, y2=90),
        Box(label="car", x1=10, y1=20, x2=50, y2=80),
    ]
    label_path = tmp_path / "image.xml"

    save_voc_xml(label_path, boxes, image_size=(100, 120), image_path=tmp_path / "image.jpg")
    loaded = load_voc_xml(label_path)

    assert loaded == boxes


def test_find_annotation_path_prefers_xml_then_yolo(tmp_path: Path):
    image_path = tmp_path / "image.jpg"
    image_path.write_bytes(b"fake")
    xml_path = tmp_path / "image.xml"
    txt_path = tmp_path / "image.txt"
    xml_path.write_text("<annotation />", encoding="utf-8")
    txt_path.write_text("", encoding="utf-8")

    assert find_annotation_path(image_path, AnnotationFormat.AUTO) == xml_path
    assert find_annotation_path(image_path, AnnotationFormat.YOLO) == txt_path
    assert find_annotation_path(image_path, AnnotationFormat.VOC_XML) == xml_path


def test_load_and_save_annotation_dispatch_by_suffix(tmp_path: Path):
    labels = ["person", "car"]
    image_size = (100, 100)
    yolo_path = tmp_path / "image.txt"
    xml_path = tmp_path / "image.xml"
    boxes = [Box(label="car", x1=10, y1=20, x2=50, y2=80)]

    save_annotation(yolo_path, boxes, labels, image_size, image_path=tmp_path / "image.jpg")
    save_annotation(xml_path, boxes, labels, image_size, image_path=tmp_path / "image.jpg")

    assert load_annotation(yolo_path, labels, image_size) == boxes
    assert load_annotation(xml_path, labels, image_size) == boxes
