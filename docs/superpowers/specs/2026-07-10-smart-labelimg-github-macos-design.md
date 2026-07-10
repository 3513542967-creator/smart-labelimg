# Smart LabelImg GitHub macOS Release Design

**Date:** 2026-07-10

**Status:** Approved design

**Target:** macOS Apple Silicon GitHub release

## 1. Goal

Improve the existing PySide6 Smart LabelImg application into a simple, reliable bounding-box annotation tool for YOLO and Pascal VOC datasets. Preserve the current working code and incrementally add the most useful LabelImg-compatible behavior, built-in MobileSAM assistance, fast previous-frame propagation, safer saving, clearer onboarding, and a downloadable macOS Apple Silicon application.

This design supersedes the native Swift/App Store rewrite in `2026-07-10-smart-labelimg-macos-design.md`. App Store submission, SwiftUI, Core ML conversion, Intel Mac support, and Windows release quality are outside this milestone.

## 2. Product Scope

### Included

- Axis-aligned rectangular bounding boxes only.
- YOLO detection TXT and Pascal VOC XML.
- Image and image-folder workflows compatible with LabelImg.
- Separate annotation folder selection.
- Manual create, select, move, resize, relabel, duplicate, delete, copy, and paste.
- MobileSAM point prompt and rough-box refinement.
- Exact copy of previous-image boxes.
- Fast previous-image propagation with displacement estimation and local MobileSAM refinement.
- Auto-save, atomic writes, visible save state, and save-before-navigation.
- Common LabelImg view, review, class, and shortcut behavior.
- macOS Apple Silicon `.app` and GitHub Release ZIP.
- A custom professional application icon.

### Excluded

- Native Swift/AppKit rewrite.
- App Store packaging or sandbox compliance.
- Polygon, mask, rotated-box, pose, or classification annotations.
- CreateML format.
- Cloud accounts, collaboration, remote inference, or telemetry.
- Windows release acceptance. Existing Windows scripts remain, but are not required to pass this milestone.

## 3. Delivery Principle

This is an incremental enhancement, not a rewrite:

- Keep the existing Python package, annotation stores, MobileSAM backend, tests, examples, and PyInstaller configuration.
- Add focused modules only when a responsibility can be extracted safely from `app.py` while implementing a requested feature.
- Preserve working behavior before adding polish.
- Avoid new heavy dependencies unless they materially improve propagation accuracy or packaging reliability.
- Keep manual annotation fully usable when MobileSAM cannot load.

## 4. Main Workflow

### Opening

- **Open Image** chooses one supported image.
- **Open Folder** loads supported images from one directory.
- **Open Annotation** loads one matching TXT or XML file for the current image.
- **Change Annotation Folder** maps labels from a separate directory by image basename.
- The app remembers recent image and annotation directories.

No project file is created and source images are not copied or moved.

### Saving

For `frame_001.jpg`:

- YOLO saves `frame_001.txt`.
- Pascal VOC saves `frame_001.xml`.
- When a separate annotation directory is selected, files go there.
- Otherwise files are saved beside the source image.
- YOLO writes `classes.txt` in the annotation destination.

Auto-save is enabled by default. A logical edit schedules a save after the edit completes. Navigation waits for the current save. If saving fails, the current image remains open and the error is shown.

### YOLO Class Safety

- Existing `classes.txt` is loaded before YOLO annotations.
- Existing class order is treated as locked schema.
- Adding a class appends it.
- Reorder, rename, merge, or deletion that changes IDs requires an explicit directory migration command.
- Unknown class IDs block overwriting the affected annotation.

## 5. Safe Save Design

Add a `SaveCoordinator` responsible for every annotation write:

1. Validate boxes, image size, class names, and class IDs.
2. Serialize annotation and `classes.txt` in memory.
3. Write sibling temporary files.
4. Flush and atomically replace destination files.
5. Update the visible state to Saved.

Save states are Saved, Saving, Unsaved, Conflict, and Failed. UI code never writes annotation files directly.

If a destination changed after it was loaded, do not overwrite it silently. Offer reload, overwrite, or save as a different file. A compact recovery snapshot may be stored in the user's application-data directory, never inside the dataset folder.

## 6. LabelImg Compatibility Priorities

The milestone includes the high-value LabelImg behavior missing from the current app:

- Undo and redo for box and class edits.
- Exact copy of boxes from the previous image.
- Duplicate selected box.
- Delete selected box and move it with arrow keys.
- Resize with edge and corner handles.
- Optional square-box constraint.
- Single-class/default-class mode.
- Show/hide all boxes and show/hide label text.
- Original size, fit window, fit width, pointer-centered zoom, and brightness controls.
- Verified image state.
- Recent directories and reset settings.
- Searchable shortcut/help dialog.

VOC `difficult` remains supported in XML and is discarded with a visible warning when converting to YOLO.

## 7. Shortcuts

Use LabelImg muscle memory while avoiding current conflicts:

| Shortcut | Action |
| --- | --- |
| `W` | Manual draw mode |
| `S` | Smart MobileSAM mode |
| `Ctrl/Cmd+J` | Edit mode |
| `A` / `D` | Previous / next image |
| `Shift+D` | Next image with smart propagation |
| `Ctrl/Cmd+V` | Exact copy of previous-image boxes |
| `Ctrl/Cmd+D` | Duplicate selected box |
| `Delete` | Delete selected box |
| Arrow keys | Move selected box one pixel |
| `Space` | Toggle verified state |
| `Ctrl/Cmd+S` | Save now |
| `Ctrl/Cmd+Shift+S` | Save As |
| `Ctrl/Cmd+R` | Change annotation folder |
| `Ctrl/Cmd+Z` | Undo |
| `Ctrl/Cmd+Shift+Z` | Redo |
| `Ctrl/Cmd++` / `Ctrl/Cmd+-` | Zoom in / out |
| `Ctrl/Cmd+0` | Fit window |
| `Return` / `Escape` | Accept / reject smart candidate |

## 8. MobileSAM Workflow

The existing MobileSAM checkpoint is bundled with the `.app`. Users do not install Python, download a model, or run a setup command.

- Click an object to create a candidate box.
- Drag a rough box to request a tighter candidate.
- Cache the current image embedding where supported by the existing backend.
- Prefetch the next image without blocking the UI.
- Show model activity and recover from failure without disabling manual mode.
- Keep masks internal; only rectangular boxes are stored.

Candidates are visually distinct. `Return` accepts, `Escape` rejects, and handles allow correction before acceptance.

## 9. Fast Previous-Image Propagation

The feature targets consecutive frames and prioritizes speed:

1. Copy each previous box and class as a starting proposal.
2. Estimate local displacement in the next image with OpenCV template matching or optical flow, using only a bounded neighborhood.
3. Expand the tracked region by a small margin.
4. Run MobileSAM refinement on the local crop.
5. Convert the mask to a tight rectangle.
6. Score match quality, size change, clipping, and SAM stability.

High-confidence boxes may be committed as one undoable batch. Low-confidence boxes remain orange candidates that require confirmation. Cancellation or navigation must not leave a partially committed batch.

`Ctrl/Cmd+V` remains exact copy with no tracking or model adjustment. `Shift+D` performs next-image smart propagation. Continuous propagation is available but off by default.

## 10. Simple User Experience

- Keep the existing three-area layout: image list, central canvas, object/class/settings side panel.
- Reduce the main toolbar to opening, saving, mode, navigation, propagation, format, and verification.
- Show one-time contextual tips for drawing, class selection, saving, and navigation.
- Keep current class visible and provide recent/searchable classes.
- Provide a persistent option to reuse the current class for repetitive datasets.
- Use plain-language errors that state whether annotations are safe and how to recover.
- Restore the last folder, format, zoom, and panel layout.
- Use Simplified Chinese and clear English for primary controls.

## 11. Application Icon

Create a clean macOS icon that remains legible at small sizes: a graphite or midnight-blue base, precise cyan bounding-box corners, and one restrained mint AI accent. It contains no text, Apple logo, or dataset-specific object. Generate the required `.icns` sizes and use the icon in Finder, Dock, application window, About dialog, and release screenshots.

## 12. Code Boundaries

Keep existing modules and add or extract only these focused responsibilities:

- `annotation.py`: format-neutral boxes plus YOLO/VOC parse and serialize behavior.
- `save_coordinator.py`: atomic save, conflicts, and recovery.
- `dataset_session.py`: image discovery, navigation, path mapping, and recent folders.
- `history.py`: undoable edit commands and batch operations.
- `propagation.py`: displacement estimation and MobileSAM local refinement.
- `ai_backend.py`: MobileSAM loading, prompts, crop transforms, and fallback.
- `canvas.py`: canvas rendering and interactions extracted from `app.py` when editing behavior is changed.
- `app.py`: window composition and coordination, not low-level persistence or inference logic.

Existing functions may move only with their tests and only when required by the current task.

## 13. Error Handling

- Invalid YOLO rows or VOC objects are reported without crashing.
- Unknown YOLO IDs prevent unsafe overwrite.
- Missing or unreadable images remain visible as errors and can be skipped.
- Failed saves keep the document dirty and block navigation.
- MobileSAM initialization or inference failures fall back to manual mode.
- Propagation failure leaves existing annotations unchanged.
- Cancelled background work does not mutate the next document.
- Packaging fails if the checkpoint, icon, or required Qt plugins are absent.

## 14. Testing and Verification

### Automated

- Preserve all current Python tests.
- Add YOLO/VOC golden round trips, empty labels, invalid IDs, Unicode paths, and class-order tests.
- Add atomic save, conflict, rollback, and recovery tests.
- Add undo/redo and batch propagation tests.
- Add deterministic propagation fixtures measuring output box and confidence behavior.
- Add UI smoke tests for window construction, actions, shortcuts, and save-state transitions.

### Manual Release Smoke Test

On Apple Silicon macOS:

1. Launch the packaged `.app` on a clean user account.
2. Open a real image folder and a separate annotation folder.
3. Create, edit, undo, redo, duplicate, and delete a box.
4. Create a MobileSAM box from a click and a rough rectangle.
5. Copy previous boxes exactly and run smart propagation.
6. Navigate while auto-save is enabled.
7. Close and reopen the dataset and confirm labels and classes reload correctly.
8. Confirm manual mode still works when MobileSAM is deliberately unavailable.
9. Confirm Dock/Finder icon, About information, and shortcuts are correct.
10. Confirm the application log contains no uncaught exception or crash.

## 15. GitHub Distribution

- Build on Apple Silicon with PyInstaller.
- Bundle Python, PySide6, OpenCV, PyTorch/MPS support, MobileSAM package, checkpoint, icon, and required runtime files.
- Produce `Smart LabelImg.app` and `Smart-LabelImg-macOS-Apple-Silicon.zip`.
- Prefer Developer ID signing and notarization when credentials are available, but unsigned GitHub testing builds are allowed for this milestone with clear right-click Open instructions.
- Publish checksums, version notes, installation steps, shortcuts, model attribution, and third-party licenses.
- Do not claim Windows support in the macOS release notes.

## 16. Delivery Order

1. Safe save and deterministic dataset/class loading.
2. Undo/redo and remaining high-value LabelImg parity.
3. Fast previous-image propagation and candidate review.
4. UI simplification, onboarding, icon, and help.
5. Apple Silicon package, clean-machine smoke test, and GitHub release artifact.

Each step must keep the app runnable and preserve the passing test suite.

## 17. Acceptance Criteria

- All current and newly added tests pass.
- A user can download, unzip, and open the macOS Apple Silicon application without installing Python.
- YOLO and VOC datasets save and reload with correct classes and box coordinates.
- Auto-save cannot silently lose or overwrite changed annotations.
- Manual annotation works with MobileSAM disabled.
- Point and rough-box MobileSAM workflows work with the bundled checkpoint.
- Exact previous copy and smart propagation are separate and predictable.
- Low-confidence propagation cannot silently become final under default settings.
- A first-time user can open a folder, draw or smart-create a box, choose a class, navigate, and find the saved label without reading external documentation.
- The packaged app completes the manual smoke test without an uncaught exception or crash.
- The GitHub release ZIP contains the correct `.app`, icon, model, README instructions, licenses, and checksum.
