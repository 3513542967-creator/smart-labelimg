# Third Party Notices

Smart LabelImg packages open-source Python and model components for the GitHub
macOS release. Review upstream licenses before redistributing modified builds.

## Runtime

- Python 3.11 runtime and standard library.
- PySide6 / Qt for the desktop UI.
- OpenCV and NumPy for image loading and local image processing.
- PyTorch for MobileSAM inference on Apple Silicon where available.
- PyInstaller for application bundling.

## Model

- MobileSAM checkpoint: `models/mobile_sam.pt`.
- The release bundles this checkpoint so end users do not need a separate model
  download.

## Project Formats

- YOLO detection TXT and Pascal VOC XML annotation formats are used for dataset
  interoperability. YOLO class names are written to `classes.txt` next to YOLO
  labels.
