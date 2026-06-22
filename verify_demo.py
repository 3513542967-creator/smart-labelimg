from pathlib import Path

import cv2

from smart_labelimg.ai_backend import ClassicalVisionBackend
from smart_labelimg.annotation import save_yolo
from smart_labelimg.demo_data import create_demo_image


root = Path(__file__).parent
image_path = root / "examples" / "demo_vehicles.png"
label_path = image_path.with_suffix(".txt")
create_demo_image(image_path)

image = cv2.cvtColor(cv2.imread(str(image_path)), cv2.COLOR_BGR2RGB)
backend = ClassicalVisionBackend()
click_boxes = backend.detect_from_click(image, 100, 120, "car")
similar_boxes = backend.find_similar(image, (55, 80, 185, 160), "car")

boxes = []
for box in click_boxes + similar_boxes:
    key = (box.x1, box.y1, box.x2, box.y2, box.label)
    if key not in {(existing.x1, existing.y1, existing.x2, existing.y2, existing.label) for existing in boxes}:
        boxes.append(box)

save_yolo(label_path, boxes, ["person", "car", "truck", "bus", "bike", "motorcycle"], (image.shape[1], image.shape[0]))

print(f"demo_image={image_path}")
print(f"label_file={label_path}")
print(f"boxes={len(boxes)}")
for box in boxes:
    print(f"{box.label}: {box.x1},{box.y1},{box.x2},{box.y2} score={box.score}")
