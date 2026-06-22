from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def create_demo_image(path: Path) -> None:
    image = np.full((360, 540, 3), 240, dtype=np.uint8)
    image[80:160, 55:185] = (220, 60, 60)
    image[175:255, 330:460] = (220, 60, 60)
    image[45:95, 355:490] = (60, 170, 70)
    image[260:315, 70:170] = (65, 65, 210)
    cv2.putText(image, "demo vehicles", (30, 340), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (60, 60, 60), 2)
    cv2.imwrite(str(path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
