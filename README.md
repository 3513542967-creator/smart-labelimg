# Smart LabelImg

Smart LabelImg is a modern LabelImg-style annotation tool with YOLO TXT, Pascal VOC XML,
and local AI-assisted boxes.
The main workflow is MobileSAM-assisted: draw around an object and MobileSAM tightens the box.

## Download And Run

For end users, use the release file for your system:

1. Download the release zip for your system.
2. Unzip it.
3. Open the app:
   - macOS: `Smart LabelImg.app`
   - Windows: `Smart LabelImg\Smart LabelImg.exe`
   - Linux: `Smart LabelImg`

No Python commands are needed for end users. The packaged app includes MobileSAM
and `models/mobile_sam.pt`, so smart box refinement works without a separate
model download.

On macOS, if the system blocks the app the first time, right-click
`Smart LabelImg.app` and choose `Open`.

On Windows, download `Smart-LabelImg-MobileSAM-Windows-x64.zip`, unzip it, and
double-click `Smart LabelImg.exe`. See
`docs/windows-install-build.md` for source install and exe build steps.

Fast Crop size is selectable in the right-side settings panel. Smart box
refinement crops a 1.5x larger area around your drawn box by default; choose
`Full Image` when you need maximum accuracy on large or edge-touching objects.

See the full LabelImg comparison and operating manual:
`docs/labelimg-audit-and-smart-labelimg-manual.md`.

## Build A Release

macOS:

```bash
./setup.sh
.venv/bin/python -m pip install -r requirements-ai.txt -r requirements-build.txt
./build_app.sh
```

Windows PowerShell:

```powershell
.\build_windows.ps1
```

The Windows build creates `dist\Smart LabelImg\Smart LabelImg.exe` and
`release\Smart-LabelImg-MobileSAM-Windows-x64.zip`.

Linux:

```bash
./setup.sh
.venv/bin/python -m pip install -r requirements-ai.txt -r requirements-build.txt
./build_app.sh
```

PyInstaller builds must be created on the target OS: build `.exe` on Windows,
`.app` on macOS, and the Linux executable on Linux.

## Run From Source

For development:

```bash
./setup.sh
./run.sh
```

Windows PowerShell:

```powershell
.\setup_windows.ps1
.\run_windows.ps1
```

If PowerShell blocks scripts, use the batch wrappers:

```bat
setup_windows.bat
run_windows.bat
```

## Main Features

- Open one image or a folder of images from a single `Open` button.
- Open a matching label file or label folder from `Open Label`.
- Save and load YOLO `.txt` and Pascal VOC `.xml` labels.
- Choose the save format and save target file or folder from the top toolbar.
- Automatically save annotation changes to the selected save target.
- Draw boxes manually in normal LabelImg mode.
- Select, move, and resize boxes with LabelImg-style controls.
- Draw rough boxes in smart mode and let MobileSAM refine them.
- Use right click / secondary click in smart mode to generate a MobileSAM box from one point.
- Click a box to change its class or delete it.
- Add, double-click rename, and delete class names in the right-side class panel.
- Renaming a class also renames all existing boxes that use that class.
- Move the selected box with arrow keys.
- Use the image list to jump through an opened folder.
- Duplicate the selected box and copy boxes from the previous image.
- Toggle label text display, zoom, fit window, and mark images as verified.
- Use the same class-name workflow as YOLO datasets.
- Keeps the default UI simple: object, person, vehicle, car, truck, bus, bike, motorcycle.
- Keeps COCO 80 classes in code for future expansion.

## Controls

- `Open`: choose one image or an image folder.
- `Open Label`: choose one `.xml` / `.txt` label file or a label folder.
- `普通 LabelImg`: manual box mode.
- `智能标注`: rough-box MobileSAM refinement mode.
- `Save Format`: choose YOLO TXT or Pascal VOC XML before saving.
- `Save/Target`: choose a label file or label folder; annotation changes save automatically.
- `Fast Crop Size`: choose 512, 768, 1024, or Full Image for smart segmentation speed/quality.
- `Save`: save to the loaded label file, or to a same-name `.txt` / `.xml` file.
- `Add Class` / double-click a class / `Delete Class`: edit the class list.
- `Duplicate Box`: copy the selected box with a small offset.
- `Copy Prev Boxes`: copy annotations from the previous image.
- `Labels`: show or hide label text over boxes.
- Bottom zoom slider: drag left/right to zoom out/in with LabelImg-style cursor-relative positioning.
- `Verify`: mark the current image as checked.
- Left-drag inside an existing box to move it.
- Drag a selected box corner or edge handle to resize it.
- Select a box, then click a class name in the left panel to change that box label.
- Right-click an existing box to open class-change and delete actions.
- Arrow keys move the selected box by 1 px.
- `Shift`: toggle between smart mode and normal LabelImg mode.
- `W`: switch to normal drawing mode.
- `Space`: switch to smart mode.
- `A` / `D`: previous / next image.
- `←` / `→`: toolbar arrows for previous / next image.
- `Ctrl+D` on Windows/Linux or `Cmd+D` on macOS: duplicate selected box.
- `Ctrl+V` on Windows/Linux or `Cmd+V` on macOS: copy previous image boxes.
- `Ctrl+Shift+P` on Windows/Linux or `Cmd+Shift+P` on macOS: show/hide label text.
- `Ctrl++` / `Ctrl+-` on Windows/Linux or `Cmd++` / `Cmd+-` on macOS: zoom with LabelImg-style cursor-relative positioning.
- `Ctrl` / `Cmd` + mouse wheel: zoom with LabelImg-style cursor-relative positioning.
- `Ctrl+F` on Windows/Linux or `Cmd+F` on macOS: fit image to window.
- `Ctrl+S` on Windows/Linux or `Cmd+S` on macOS: save.

## Default Classes

The default class list is intentionally small:

```text
object
person
vehicle
car
truck
bus
bike
motorcycle
```

The standard COCO 80-class order is still available in `smart_labelimg/labels.py`.

## LocateAnything-3B Utility

The app UI no longer exposes text auto-detection, but the LocateAnything adapter and
standalone verification script remain available for experiments:

```text
vendor/locate-anything.cpp/build/examples/cli/locate-anything-cli
vendor/locate-anything.cpp/models/locate-anything-q8_0.gguf
```

Prepare the C++ runtime:

```bash
./scripts/install_locate_anything_cpp.sh
```

The 3B model weights are large. Keep them under:

```text
vendor/locate-anything.cpp/models/
```

## Verification

```bash
conda activate ai
pytest -q
python verify_demo.py
python verify_app.py
python verify_locateanything.py
python verify_sam_click.py
```

Expected evidence from `verify_demo.py`:

```text
boxes=2
car: 53,78,187,162
car: 328,173,462,257
```
