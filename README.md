# Smart LabelImg

Smart LabelImg is a modern LabelImg-style annotation tool with YOLO TXT, Pascal VOC XML,
and local AI-assisted boxes.
The main workflow is MobileSAM-assisted: draw around an object and MobileSAM tightens the box.

## Download And Run

For macOS Apple Silicon users, download:

```text
Smart-LabelImg-macOS-Apple-Silicon.zip
```

1. Download the release zip for your system.
2. Unzip it.
3. Open `Smart LabelImg.app`.

No Python commands are needed for end users. The packaged app includes MobileSAM
and `models/mobile_sam.pt`, so smart box refinement works without a separate
model download.

On macOS, if the system blocks the app the first time, right-click
`Smart LabelImg.app` and choose `Open`. This GitHub build is intended for direct
download; App Store distribution and notarization are future work.

On Windows, download `Smart-LabelImg-MobileSAM-Windows-x64.zip`, unzip it, and
double-click `Smart LabelImg.exe`. See
`docs/windows-install-build.md` for source install and exe build steps.

Smart box refinement runs directly through the bundled MobileSAM model. There is no
separate crop-size tuning control in the simplified app.

See the full LabelImg comparison and operating manual:
`docs/labelimg-audit-and-smart-labelimg-manual.md`.

## 快速使用

1. `Open` 打开图片或图片文件夹。
2. `Save Format` 选择 YOLO TXT 或 Pascal VOC XML。
3. `Save/Target` 选择保存位置。
4. `普通 LabelImg`：手动画矩形框。
5. `智能标注`：粗略画框，MobileSAM 自动微调。
6. 选中类别后继续画框，标注会自动保存。

常用快捷键：

- `W`：手动画框
- `S`：智能标注
- `A` / `D`：上一张 / 下一张
- `Cmd+A` / `Ctrl+A`：全选框
- `Delete`：删除框
- `Cmd+D` / `Ctrl+D`：复制框
- `Cmd+V` / `Ctrl+V`：复制上一张标注
- `Shift+D`：智能下一张
- `Cmd+S` / `Ctrl+S`：保存

## Build A Release

Release builds require the bundled MobileSAM checkpoint at:

```text
models/mobile_sam.pt
```

macOS:

```bash
conda activate ai
./build_app.sh
```

The macOS build creates:

```text
dist/Smart LabelImg.app
release/Smart-LabelImg-macOS-Apple-Silicon.zip
release/Smart-LabelImg-macOS-Apple-Silicon.zip.sha256
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
- Writes YOLO `classes.txt` next to YOLO labels in LabelImg-compatible order.
- Uses safe save checks so navigation stays on the current image if saving fails.
- Undo/redo annotation edits.
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
- Smart-next propagation from the previous image with automatic local refinement.
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
- `W`: switch to normal drawing mode.
- `S`: switch to smart mode.
- `Space`: verify / unverify the current image.
- `Shift+D`: smart-next to the next image and propagate boxes from the previous image.
- `Return`: accept low-confidence propagated candidate boxes.
- `A` / `D`: previous / next image.
- `←` / `→`: toolbar arrows for previous / next image.
- `Ctrl+D` on Windows/Linux or `Cmd+D` on macOS: duplicate selected box.
- `Ctrl+A` on Windows/Linux or `Cmd+A` on macOS: select all boxes in the current image.
- `Ctrl+V` on Windows/Linux or `Cmd+V` on macOS: copy previous image boxes.
- `Ctrl+Shift+P` on Windows/Linux or `Cmd+Shift+P` on macOS: show/hide label text.
- `Ctrl++` / `Ctrl+-` on Windows/Linux or `Cmd++` / `Cmd+-` on macOS: zoom with LabelImg-style cursor-relative positioning.
- `Ctrl` / `Cmd` + mouse wheel: zoom with LabelImg-style cursor-relative positioning.
- `Ctrl+0` on Windows/Linux or `Cmd+0` on macOS: fit image to window.
- `Ctrl+1` on Windows/Linux or `Cmd+1` on macOS: original size.
- `Ctrl+J` on Windows/Linux or `Cmd+J` on macOS: edit/select mode.
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
./scripts/verify_macos_release.sh
```

## Third Party Notices

See `THIRD_PARTY_NOTICES.md` for bundled dependency and MobileSAM model
attribution notes.

Expected evidence from `verify_demo.py`:

```text
boxes=2
car: 53,78,187,162
car: 328,173,462,257
```
