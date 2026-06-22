from pathlib import Path
from urllib.request import urlretrieve

from smart_labelimg.ai_backend import LocateAnythingBackend


PROJECT_ROOT = Path(__file__).parent
LOCATE_ANYTHING_CLI = PROJECT_ROOT / "vendor/locate-anything.cpp/build/examples/cli/locate-anything-cli"
LOCATE_ANYTHING_MODEL = PROJECT_ROOT / "vendor/locate-anything.cpp/models/locate-anything-q8_0.gguf"


image_path = PROJECT_ROOT / "examples" / "street_test.jpg"
if not image_path.exists():
    urlretrieve("https://raw.githubusercontent.com/ultralytics/yolov5/master/data/images/zidane.jpg", image_path)

backend = LocateAnythingBackend(str(LOCATE_ANYTHING_CLI), str(LOCATE_ANYTHING_MODEL))
boxes = backend.detect_labels(image_path, ["person"])

print(f"cli={LOCATE_ANYTHING_CLI.exists()}")
print(f"model={LOCATE_ANYTHING_MODEL.exists()} size_gb={LOCATE_ANYTHING_MODEL.stat().st_size / (1024 ** 3):.2f}")
print(f"image={image_path}")
print(f"boxes={len(boxes)}")
for box in boxes:
    print(f"{box.label}: {box.x1},{box.y1},{box.x2},{box.y2} score={box.score}")
