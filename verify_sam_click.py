from pathlib import Path
from urllib.request import urlretrieve

import cv2

from smart_labelimg.ai_backend import SamClickBackend
from smart_labelimg.app import SAM_CHECKPOINT
from smart_labelimg.annotation import save_yolo


root = Path(__file__).parent
image_path = root / "examples" / "street_test.jpg"
if not image_path.exists():
    urlretrieve("https://raw.githubusercontent.com/ultralytics/yolov5/master/data/images/zidane.jpg", image_path)

image = cv2.cvtColor(cv2.imread(str(image_path)), cv2.COLOR_BGR2RGB)
backend = SamClickBackend(str(SAM_CHECKPOINT))

# A point inside the main person in the test image.
boxes = backend.detect_from_click(image, x=980, y=300, label="person")
label_path = root / "examples" / "street_test_sam_click.txt"
save_yolo(label_path, boxes, ["object", "person", "vehicle", "car"], (image.shape[1], image.shape[0]))
annotated = image.copy()
for box in boxes:
    cv2.rectangle(annotated, (box.x1, box.y1), (box.x2, box.y2), (0, 255, 0), 3)
    cv2.putText(annotated, box.label, (box.x1, max(20, box.y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
annotated_path = root / "examples" / "street_test_sam_click.png"
cv2.imwrite(str(annotated_path), cv2.cvtColor(annotated, cv2.COLOR_RGB2BGR))

print(f"checkpoint={SAM_CHECKPOINT.exists()} size_mb={SAM_CHECKPOINT.stat().st_size / (1024 ** 2):.1f}")
print(f"image={image_path}")
print(f"boxes={len(boxes)}")
for box in boxes:
    print(f"{box.label}: {box.x1},{box.y1},{box.x2},{box.y2} score={box.score:.4f}")
print(f"saved={label_path}")
print(f"annotated={annotated_path}")
