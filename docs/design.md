# Smart LabelImg Design

## Goal

Build a local LabelImg-style desktop annotator for YOLO datasets with AI-assisted boxes:

- Keep the familiar open image/folder, draw/edit boxes, class list, and XML/YOLO save flow.
- Add MobileSAM smart annotation: drag a rough box or click a point and the tool proposes a tighter object box.
- Keep file/label folder workflows explicit through `Open`, `Open Label`, `Save Format`, and `Save Target`.
- Auto-save annotation changes once a save target is selected.

## Chosen Approach

This project implements a new PySide6 desktop app instead of directly modifying legacy LabelImg internals. A fresh implementation is easier to package for macOS/Windows/Linux and still preserves the core annotation workflow.

## Model Backend

The app has a backend boundary in `smart_labelimg/ai_backend.py`.

- `MobileSamBackend`: primary backend for smart point prompts and rough-box refinement.
- `ClassicalVisionBackend`: fallback when MobileSAM is unavailable.
- `LocateAnythingBackend`: experimental adapter retained for local experiments, but not exposed in the simplified UI.

The packaged app includes `models/mobile_sam.pt`, so smart annotation works after download without a separate model setup.

## Verification

Automated tests prove:

- XML and YOLO annotations load and save correctly.
- LabelImg-style box selection, movement, resize, duplicate, and previous-box copy work.
- Class renames update existing boxes.
- Save target file/folder and auto-save behavior work.
- MobileSAM rough-box and point prompts use original image coordinates.

Manual verification launches the app and uses the same backend functions on example images.
