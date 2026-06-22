from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import xml.etree.ElementTree as ET


class AnnotationFormat(str, Enum):
    AUTO = "auto"
    YOLO = "yolo"
    VOC_XML = "voc_xml"


@dataclass
class Box:
    label: str
    x1: int
    y1: int
    x2: int
    y2: int
    score: float | None = None

    def normalized(self) -> "Box":
        x1, x2 = sorted((int(round(self.x1)), int(round(self.x2))))
        y1, y2 = sorted((int(round(self.y1)), int(round(self.y2))))
        return Box(self.label, x1, y1, x2, y2, self.score)

    @property
    def width(self) -> int:
        box = self.normalized()
        return max(0, box.x2 - box.x1)

    @property
    def height(self) -> int:
        box = self.normalized()
        return max(0, box.y2 - box.y1)

    def clipped(self, image_size: tuple[int, int]) -> "Box":
        width, height = image_size
        box = self.normalized()
        return Box(
            self.label,
            max(0, min(width - 1, box.x1)),
            max(0, min(height - 1, box.y1)),
            max(0, min(width - 1, box.x2)),
            max(0, min(height - 1, box.y2)),
            self.score,
        )


def yolo_path_for_image(image_path: Path) -> Path:
    return image_path.with_suffix(".txt")


def voc_path_for_image(image_path: Path) -> Path:
    return image_path.with_suffix(".xml")


def infer_format_from_path(path: Path) -> AnnotationFormat:
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return AnnotationFormat.YOLO
    if suffix == ".xml":
        return AnnotationFormat.VOC_XML
    raise ValueError(f"Unsupported annotation format: {path}")


def find_annotation_path(image_path: Path, preferred_format: AnnotationFormat = AnnotationFormat.AUTO) -> Path | None:
    if preferred_format == AnnotationFormat.YOLO:
        path = yolo_path_for_image(image_path)
        return path if path.exists() else None
    if preferred_format == AnnotationFormat.VOC_XML:
        path = voc_path_for_image(image_path)
        return path if path.exists() else None

    xml_path = voc_path_for_image(image_path)
    if xml_path.exists():
        return xml_path
    yolo_path = yolo_path_for_image(image_path)
    if yolo_path.exists():
        return yolo_path
    return None


def save_yolo(path: Path, boxes: list[Box], labels: list[str], image_size: tuple[int, int]) -> None:
    width, height = image_size
    lines: list[str] = []
    for raw_box in boxes:
        box = raw_box.clipped(image_size)
        if box.label not in labels or box.width <= 0 or box.height <= 0:
            continue
        class_id = labels.index(box.label)
        cx = ((box.x1 + box.x2) / 2) / width
        cy = ((box.y1 + box.y2) / 2) / height
        bw = box.width / width
        bh = box.height / height
        lines.append(f"{class_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def load_yolo(path: Path, labels: list[str], image_size: tuple[int, int]) -> list[Box]:
    if not path.exists():
        return []
    width, height = image_size
    boxes: list[Box] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if len(parts) != 5:
            continue
        class_id = int(float(parts[0]))
        if class_id < 0 or class_id >= len(labels):
            continue
        cx, cy, bw, bh = map(float, parts[1:])
        box_width = bw * width
        box_height = bh * height
        x1 = int(round(cx * width - box_width / 2))
        y1 = int(round(cy * height - box_height / 2))
        x2 = int(round(cx * width + box_width / 2))
        y2 = int(round(cy * height + box_height / 2))
        boxes.append(Box(labels[class_id], x1, y1, x2, y2).clipped(image_size))
    return boxes


def save_voc_xml(path: Path, boxes: list[Box], image_size: tuple[int, int], image_path: Path | None = None) -> None:
    width, height = image_size
    annotation = ET.Element("annotation")
    if image_path is not None:
        ET.SubElement(annotation, "folder").text = image_path.parent.name
        ET.SubElement(annotation, "filename").text = image_path.name
        ET.SubElement(annotation, "path").text = str(image_path)
    size = ET.SubElement(annotation, "size")
    ET.SubElement(size, "width").text = str(width)
    ET.SubElement(size, "height").text = str(height)
    ET.SubElement(size, "depth").text = "3"

    for raw_box in boxes:
        box = raw_box.clipped(image_size)
        if box.width <= 0 or box.height <= 0:
            continue
        obj = ET.SubElement(annotation, "object")
        ET.SubElement(obj, "name").text = box.label
        ET.SubElement(obj, "pose").text = "Unspecified"
        ET.SubElement(obj, "truncated").text = "0"
        ET.SubElement(obj, "difficult").text = "0"
        bndbox = ET.SubElement(obj, "bndbox")
        ET.SubElement(bndbox, "xmin").text = str(box.x1)
        ET.SubElement(bndbox, "ymin").text = str(box.y1)
        ET.SubElement(bndbox, "xmax").text = str(box.x2)
        ET.SubElement(bndbox, "ymax").text = str(box.y2)

    tree = ET.ElementTree(annotation)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def load_voc_xml(path: Path) -> list[Box]:
    if not path.exists():
        return []
    root = ET.parse(path).getroot()
    boxes: list[Box] = []
    for obj in root.findall("object"):
        label = (obj.findtext("name") or "object").strip() or "object"
        bndbox = obj.find("bndbox")
        if bndbox is None:
            continue
        try:
            x1 = int(round(float(bndbox.findtext("xmin", "0"))))
            y1 = int(round(float(bndbox.findtext("ymin", "0"))))
            x2 = int(round(float(bndbox.findtext("xmax", "0"))))
            y2 = int(round(float(bndbox.findtext("ymax", "0"))))
        except ValueError:
            continue
        boxes.append(Box(label, x1, y1, x2, y2).normalized())
    return boxes


def load_annotation(path: Path, labels: list[str], image_size: tuple[int, int]) -> list[Box]:
    fmt = infer_format_from_path(path)
    if fmt == AnnotationFormat.YOLO:
        return load_yolo(path, labels, image_size)
    if fmt == AnnotationFormat.VOC_XML:
        return [box.clipped(image_size) for box in load_voc_xml(path)]
    raise ValueError(f"Unsupported annotation format: {path}")


def save_annotation(
    path: Path,
    boxes: list[Box],
    labels: list[str],
    image_size: tuple[int, int],
    image_path: Path | None = None,
) -> None:
    fmt = infer_format_from_path(path)
    if fmt == AnnotationFormat.YOLO:
        save_yolo(path, boxes, labels, image_size)
        return
    if fmt == AnnotationFormat.VOC_XML:
        save_voc_xml(path, boxes, image_size, image_path=image_path)
        return
    raise ValueError(f"Unsupported annotation format: {path}")
