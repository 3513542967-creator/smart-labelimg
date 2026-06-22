import os
from pathlib import Path
from urllib.request import urlretrieve

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from smart_labelimg.app import MainWindow
from smart_labelimg.annotation import Box


root = Path(__file__).parent
image_path = root / "examples" / "street_test.jpg"
if not image_path.exists():
    urlretrieve("https://raw.githubusercontent.com/ultralytics/yolov5/master/data/images/zidane.jpg", image_path)
label_path = image_path.with_suffix(".txt")
if label_path.exists():
    label_path.unlink()

app = QApplication.instance() or QApplication([])
window = MainWindow()
window.images = [image_path]
window.image_index = 0
window.load_current_image()
window.canvas.current_label = "person"
window.canvas.boxes.append(Box("person", 10, 10, 80, 120))
window.save_current()

print(f"loaded={window.current_image.name}")
print(f"backend={type(window.backend).__name__}")
print(f"boxes={len(window.canvas.boxes)}")
print(f"saved={label_path.exists()}")
window.close()
