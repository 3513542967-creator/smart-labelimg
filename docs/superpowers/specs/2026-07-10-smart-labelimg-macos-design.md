# Smart LabelImg for macOS — Native Rewrite Design (Superseded)

> Superseded on 2026-07-10 by `2026-07-10-smart-labelimg-github-macos-design.md`. The active milestone incrementally improves the existing PySide6 application for a macOS Apple Silicon GitHub release and does not implement this native Swift/App Store design.

**Date:** 2026-07-10

**Status:** Approved product design

**Target:** Apple Silicon, macOS 14 or later

## 1. Product Goal

Smart LabelImg is an open-source, professional macOS application for creating bounding-box datasets for object-detection models. It preserves the familiar LabelImg workflow and file layout for YOLO TXT and Pascal VOC XML while adding fast, local SAM-assisted annotation and intelligent propagation between adjacent images.

The application must be useful without an account, network connection, Python installation, model download, or proprietary project format. The long-term distribution targets are a signed and notarized direct-download build and the Mac App Store.

## 2. Success Criteria

The first production release succeeds when it:

- Opens individual images and image directories without requiring project creation.
- Reads, edits, and writes LabelImg-compatible YOLO TXT and Pascal VOC XML bounding boxes.
- Lets a new user create and save a correct first annotation without reading documentation.
- Provides the LabelImg bounding-box workflow, shortcuts, navigation, review, and view controls expected by experienced users.
- Includes a Core ML SAM model in the application and performs all inference locally.
- Propagates annotations from one sequential image to the next using tracking followed by local SAM refinement.
- Prevents silent data loss through atomic saves, conflict detection, recovery, undo, and explicit error states.
- Runs responsively on the baseline Apple Silicon Mac with no UI blocking during image decoding, saving, tracking, or model inference.
- Builds under App Sandbox with signing, Hardened Runtime, privacy metadata, and no required network entitlement.

## 3. Scope

### 3.1 Included

- Axis-aligned rectangular bounding boxes only.
- YOLO detection TXT import and export.
- Pascal VOC XML import and export.
- Manual annotation and editing.
- SAM point-prompt and rough-box refinement.
- Previous-image box copy.
- Previous-image tracking and SAM refinement.
- Class catalog management with YOLO class-ID safety.
- Image verification, review progress, undo, redo, recovery, and auto-save.
- English and Simplified Chinese localization.
- Native macOS menus, keyboard shortcuts, drag and drop, touchpad gestures, dark mode, accessibility, and window restoration.

### 3.2 Excluded

- Polygon, mask, rotated-box, keypoint, classification, and semantic-segmentation annotation.
- CreateML JSON.
- Video playback or extraction. Sequential frames already exported as images are supported.
- Cloud sync, accounts, collaboration, remote inference, training, and dataset hosting.
- Intel Macs and macOS versions earlier than 14.
- A proprietary dataset or project file format.

The internal annotation model must remain extensible, but speculative annotation types are not implemented in this release.

## 4. Product Principles

1. **Dataset files belong to the user.** The application does not copy, move, rename, or restructure source images unless the user explicitly invokes such an operation.
2. **LabelImg-compatible by default.** Image-folder and annotation-folder behavior, filenames, class ordering, and common shortcuts remain familiar.
3. **Speed without hidden errors.** Smart operations are optimized and prefetched, but uncertain results remain visible candidates until accepted.
4. **Progressive disclosure.** Basic mode contains the small set of controls needed to annotate. Professional mode exposes advanced review, migration, display, and VOC options.
5. **Manual annotation always works.** SAM, tracking, or model initialization failures never disable opening, editing, or saving annotations.
6. **No silent data loss.** Save failures, external file changes, invalid labels, and format conflicts are visible and block destructive continuation.

## 5. Technical Direction

The application is a native Swift implementation:

- SwiftUI owns application scenes, menus, toolbars, sidebars, inspectors, settings, onboarding, and state presentation.
- An AppKit `NSView` canvas owns high-frequency pointer input, drawing, hit testing, panning, zooming, selection, and resize handles. It is bridged into SwiftUI with `NSViewRepresentable`.
- Core ML executes the bundled MobileSAM encoder and decoder on Apple Silicon using the best available compute units. MobileSAM is the selected SAM-family implementation because annotation speed is the product priority.
- Apple Vision performs lightweight object tracking for adjacent-image propagation.
- Swift Concurrency isolates image loading, model inference, propagation, and disk writes from the main actor.

The native application is added under `macos/` while the existing Python/PySide6 application remains intact as a behavior reference until the native acceptance suite passes. Removal or archival of the Python application is a separate future decision.

## 6. Module Architecture

The Xcode application target depends on focused local Swift packages:

### 6.1 `AnnotationCore`

Owns `AnnotationDocument`, `BoundingBox`, `ClassDefinition`, verification state, candidate state, validation, selection-independent editing commands, and undoable mutations. Coordinates are stored in image pixel space as bounded floating-point rectangles and rounded only at serialization boundaries.

### 6.2 `DatasetIO`

Owns directory access, image discovery, annotation lookup, `YOLOStore`, `VOCStore`, `ClassCatalog`, sandbox bookmarks, recent locations, and format detection. Parsers return structured diagnostics rather than silently discarding invalid rows or objects.

### 6.3 `SaveSystem`

Owns the `SaveCoordinator` actor, save transactions, file fingerprints, atomic replacement, recovery snapshots, external-change conflicts, and save-state reporting. No UI component writes annotation files directly.

### 6.4 `CanvasKit`

Owns `AnnotationCanvas`, transforms between view and image coordinates, rendering, hit testing, nested-box selection, drawing, moving, resizing, gestures, cursor changes, candidate overlays, and accessibility elements for boxes.

### 6.5 `SmartAnnotation`

Owns `SAMService`, image-embedding cache, prompt transformation, mask-to-box conversion, candidate confidence, `PropagationEngine`, Vision tracking, crop selection, prefetching, and cancellation.

### 6.6 `SmartLabelImgApp`

Owns `DatasetSession`, navigation, SwiftUI screens, menu commands, toolbars, inspectors, onboarding, preferences, localization, status presentation, and coordination between modules.

Each module exposes protocols at its boundary. Stores and inference services have deterministic test doubles. UI state never depends directly on Core ML, XML, or raw filesystem APIs.

## 7. Dataset Opening and Navigation

### 7.1 Entry Points

The welcome screen provides three primary actions:

- **Open Image…** opens one image.
- **Open Image Folder…** opens the supported images in one directory.
- **Continue Last Task** reopens the last authorized image and annotation directories.

Users may also drag an image or folder onto the app. Version one scans the selected directory's top level, matching LabelImg behavior; it does not recursively merge unrelated subdirectories.

If two source images share a basename, such as `frame.jpg` and `frame.png`, they would map to the same annotation filename. The session reports the collision and blocks saving those images until the user removes the ambiguity; it never lets one image overwrite the other's annotation.

Supported image formats are those decoded reliably by ImageIO, including JPEG, PNG, TIFF, BMP, HEIC, and WebP when available through the system decoder. Unreadable images remain in the file list with a diagnostic state and do not crash navigation.

### 7.2 Annotation Source and Destination

The annotation directory initially defaults to the image directory. **Change Annotation Folder…** grants a separate destination and immediately remaps labels by image basename. The window always shows the active annotation format and destination.

For an image named `frame_001.jpg`:

- YOLO maps to `<annotation folder>/frame_001.txt`.
- Pascal VOC maps to `<annotation folder>/frame_001.xml`.

An explicitly opened annotation file applies to the current image and updates the active format. When both same-name TXT and XML files exist, the current format wins; otherwise the app asks which source to use and remembers the choice for the session.

### 7.3 Navigation

The left sidebar shows filename, annotated/unannotated state, verified state, error state, and current selection. Navigation is available by click, `A`/`D`, toolbar buttons, and standard next/previous menu commands.

The next image is decoded in the background. A navigation request first flushes the current save transaction. If save fails, navigation stops on the current image and explains how to recover.

## 8. Annotation Formats

### 8.1 YOLO TXT

Each valid line has exactly:

```text
class_id center_x center_y width height
```

Coordinates are normalized to the image dimensions. Serialization clamps boxes to image bounds, rejects zero-area boxes, uses stable decimal precision, and always ends non-empty files with a newline. A reviewed image with no objects is represented by an empty TXT file.

`classes.txt` resides in the active annotation directory. One class name is written per line; its zero-based line index is the YOLO class ID. When opening a dataset, the application searches for the catalog in this order:

1. Active annotation directory `classes.txt`.
2. Image directory `classes.txt` when the annotation directory differs.
3. A class file explicitly imported by the user.
4. An empty catalog that prompts the user to create or import a class before the first box is committed.

Malformed lines, non-finite coordinates, negative sizes, and unknown class IDs appear as file diagnostics. Unknown-ID files may be viewed but cannot be overwritten until the user repairs or maps the class IDs.

### 8.2 Pascal VOC XML

VOC serialization writes `folder`, `filename`, `path`, `size`, `segmented`, and one `object` per box with `name`, `pose`, `truncated`, `difficult`, and integer `bndbox` coordinates. A reviewed image with no objects is represented by valid XML with no `object` elements.

The parser preserves recognized object names and `difficult`. Unsupported metadata is retained where practical during a read-edit-write round trip so a simple box edit does not unnecessarily erase third-party VOC fields.

### 8.3 Format Switching

The user explicitly selects YOLO or Pascal VOC. Switching formats does not delete the previous-format files. The app previews the destination filenames and warns about information that cannot be represented, such as VOC `difficult` in YOLO.

## 9. Class Catalog Safety

YOLO class ordering is treated as dataset schema:

- The order locks when an existing YOLO annotation set is detected or the first annotation is saved.
- Adding a new class appends it and does not change existing IDs.
- Reordering, renaming, merging, or deleting existing classes requires the **Migrate Class Catalog…** workflow.
- Migration scans only TXT files whose basenames match images in the active dataset session, validates them, computes the ID mapping, shows a summary, writes a complete staged replacement, and commits only if every matched annotation succeeds. Unrelated text files are never changed.
- A failed migration leaves the original files and `classes.txt` unchanged.

VOC names may be edited directly because objects store names rather than numeric IDs. The shared UI still uses the catalog to provide consistent selection and filtering.

## 10. Save and Recovery System

Auto-save is enabled by default and can be disabled in Settings. A save is scheduled after a logical operation completes: drawing, moving, resizing, deleting, duplicating, changing a class, accepting a smart candidate, toggling `difficult`, or toggling verification. Pointer-move events never write to disk.

### 10.1 Transaction Flow

1. Validate the in-memory document and class catalog.
2. Compare the current on-disk file fingerprints with those captured at load or last save.
3. Serialize annotations and, for YOLO, the catalog.
4. Write temporary sibling files in the destination directory.
5. Flush and atomically replace the destination files.
6. Update fingerprints and clear the dirty state.
7. Remove the corresponding recovery snapshot.

YOLO annotation and `classes.txt` changes are treated as one application-level transaction. If a multi-file replacement cannot complete, the coordinator restores the pre-save versions before reporting failure.

### 10.2 Conflicts

If another application changed a destination after it was loaded, Smart LabelImg does not overwrite it silently. The conflict sheet offers:

- Reload disk version and discard local edits.
- Save local edits as a new file.
- Compare a concise object/class summary and intentionally overwrite.

### 10.3 Recovery

Dirty documents have compact recovery snapshots under the app's Application Support container. The dataset directory receives no private recovery files. On relaunch after abnormal termination, the welcome screen offers to restore or discard each newer snapshot.

### 10.4 Save State

The UI presents exactly one of: Saved, Saving, Unsaved, Conflict, or Save Failed. Closing a window, changing annotation directory, switching format, or navigating away waits for the save actor. A failed save prevents the destructive transition unless the user explicitly exports the recovery copy or discards changes.

## 11. Manual Bounding-Box Workflow

Three primary modes are always visible:

- **Edit** selects, moves, resizes, changes, and deletes boxes.
- **Draw Box** creates manual rectangles.
- **Smart Box** creates SAM prompts.

The canvas supports:

- Eight resize handles and whole-box dragging.
- One-pixel arrow movement and accelerated movement while Shift is held.
- Selection of overlapping boxes by choosing the smallest containing box first, with cycling for ambiguity.
- Duplicate, copy/paste, copy previous image boxes, and context-menu class changes.
- Optional square constraint.
- Show/hide all boxes, show/hide label text, label filtering, configurable colors, and selection emphasis.
- Original size, fit window, fit width, pointer-centered zoom, touchpad pinch zoom, panning, and brightness preview.
- Undo and redo for every document mutation, including accepted propagation batches.

Deleting an image moves it to the macOS Trash after confirmation. Annotation deletion is offered separately so the action is not ambiguous.

## 12. SAM-Assisted Annotation

The application bundle includes a Core ML-converted MobileSAM model suitable for Apple Silicon. Its license and source attribution are recorded in `THIRD_PARTY_NOTICES`. The model is split into an image encoder and prompt/mask decoder so one image embedding serves multiple prompts.

SAM is an internal box-generation aid. Masks are not stored or exported.

### 12.1 Interactions

- A click supplies a positive point and returns a candidate box around the selected object.
- A rough dragged rectangle supplies a box prompt and returns a tightened candidate box.
- Additional positive and negative points can correct an ambiguous candidate before acceptance.
- `Return` accepts a candidate, `Escape` rejects it, and direct handle dragging adjusts it.

The current class is assigned to the candidate. If no class exists, acceptance opens the searchable class picker.

### 12.2 Runtime Behavior

- The model loads lazily after the first dataset opens and never blocks initial app launch.
- Current-image encoding begins in the background, followed by next-image prefetch.
- Embeddings are cached with a bounded memory policy and invalidated when the source image changes.
- Inference requests are cancellable when the user navigates.
- Model errors produce a visible nonfatal message and preserve full manual operation.

Candidate boxes are visually distinct from committed boxes. Confidence is used to prioritize user attention, not to claim certainty. Low-confidence or unstable results remain orange and never auto-save as final annotations.

## 13. Intelligent Previous-Image Propagation

The feature targets sequential frames or burst images and prioritizes throughput.

### 13.1 Commands

- `Command-V` copies the previous image's boxes exactly, matching LabelImg behavior.
- `Shift-D` navigates to the next image and runs intelligent propagation once.
- **Continuous Smart Propagation** applies the same operation on each forward navigation. It is off by default to protect unordered datasets.

### 13.2 Pipeline

1. Prefetch and decode the next image before navigation when possible.
2. Use `VNTrackObjectRequest` to estimate each previous box's translation and scale in the next image.
3. Expand each tracked box by a bounded margin and crop only that local region.
4. Use the tracked box as the SAM prompt and refine the object boundary.
5. Convert the selected SAM mask to a tight axis-aligned box, clamp it to image bounds, and preserve the previous class.
6. Score tracking stability, mask stability, boundary clipping, and size change.
7. Commit high-confidence results as one undoable batch. This propagation-specific auto-accept behavior is on by default for speed and can be disabled. Low-confidence results always remain candidates and require confirmation. Ordinary click and rough-box SAM operations always present a candidate before commit under default settings.

Multiple objects are refined concurrently within a bounded task group. Image decoding, Vision tracking, and cached embeddings are reused. A stopped or cancelled batch leaves no partially committed annotations.

## 14. User Experience and Learnability

### 14.1 Layout

- Left sidebar: image list, progress, filters, and error/verified state.
- Center: canvas and small contextual candidate controls.
- Right inspector: objects, classes, selected-box properties, and advanced options.
- Toolbar: open, annotation folder, format, three modes, navigation, propagation, and verification.
- Bottom status area: image dimensions, zoom, active class, save state, SAM state, and destination.

The application uses a custom, professionally rendered macOS icon that remains recognizable from 16 to 1024 pixels. Its visual language combines a precise bounding-box symbol with one restrained local-AI accent; it contains no text, Apple trademark, or dataset-specific object that would narrow the product's meaning. The icon is used consistently in the Dock, Finder, About window, welcome screen, direct-download bundle, and future App Store listing.

Basic mode hides class migration, VOC metadata, color customization, and diagnostic details. Professional mode exposes them without changing dataset behavior.

### 14.2 Onboarding

- First-run welcome screen uses task language rather than file-format jargon.
- One-time contextual tips explain drawing, smart clicking, class selection, navigation, and saving at the moment each action becomes relevant.
- A 60-second optional walkthrough uses a bundled sample image and never modifies user files.
- The searchable command and shortcut window is available from Help.
- Empty states always state the next useful action.
- Errors say what failed, whether data is safe, and what the user can do next.

### 14.3 Class Selection

After creating a box, the class picker supports search, recent classes, and numeric choices. **Keep Using Current Class** suppresses future prompts for single-class or repetitive work. Changing a selected box's class is available from the inspector, class list, and context menu.

## 15. Keyboard Shortcuts

Shortcuts preserve LabelImg muscle memory while respecting reserved macOS commands:

| Shortcut | Command |
| --- | --- |
| `W` | Draw Box mode |
| `S` | Smart Box mode |
| `Command-J` | Edit mode |
| `A` / `D` | Previous / next image |
| `Shift-D` | Next image with intelligent propagation |
| `Command-V` | Copy previous image boxes exactly |
| `Command-D` | Duplicate selected box |
| `Delete` | Delete selected box |
| Arrow keys | Move selected box by one pixel |
| `Space` | Toggle image verified |
| `Command-S` | Save now |
| `Command-Shift-S` | Save As |
| `Command-R` | Change annotation folder |
| `Command-Z` / `Command-Shift-Z` | Undo / redo |
| `Command-Plus` / `Command-Minus` | Zoom in / out |
| `Command-0` | Fit image to window |
| `Command-Shift-P` | Toggle label text |
| `Return` / `Escape` | Accept / reject smart candidate |

All commands also exist in menus. Editable text fields take precedence over single-key canvas shortcuts.

## 16. Verification State

Pascal VOC verification uses the compatible XML verification field where present. YOLO has no standard verification field, so portable TXT output remains untouched. YOLO review state is stored in Application Support, keyed by a stable dataset-directory bookmark and relative image path. Losing app metadata never alters or invalidates annotations.

## 17. Error Handling

- Parse errors preserve the source file and display line/object-level diagnostics.
- Save errors keep the document dirty and its recovery snapshot current.
- Permission loss prompts the user to reauthorize the affected directory.
- Missing images remain listed with a resolvable error instead of shifting annotations onto another file.
- A missing or invalid `classes.txt` prevents unsafe YOLO interpretation and opens a class-mapping repair flow.
- Model and tracking errors never become save errors.
- Memory pressure evicts prefetched images and SAM embeddings before affecting the current document.

No exception, failed task, or cancellation may produce a partially mutated annotation document or partially saved propagation batch.

## 18. Performance Targets

Performance is measured on the oldest supported baseline Apple Silicon Mac:

- Initial window becomes interactive within two seconds without loading SAM.
- A prefetched 1080p next image becomes visible within 150 ms of navigation input.
- Canvas interaction maintains 60 frames per second for typical documents and remains usable with at least 1,000 boxes.
- A common 1080p local SAM refinement returns its first candidate within 1.5 seconds.
- Saving 1,000 YOLO boxes completes within 250 ms on local storage.
- No image decoding, file I/O, Vision request, or Core ML prediction executes on the main actor.

Performance regressions are tracked in repeatable benchmark tests rather than judged only by manual use.

## 19. Accessibility and Localization

- All toolbar items, inspector controls, candidate actions, and boxes have VoiceOver labels and actions.
- Full keyboard operation is supported without requiring pointer input.
- Colors meet contrast requirements and are never the sole state indicator.
- The UI respects Reduce Motion, Increase Contrast, and system appearance.
- User-facing strings are localized through String Catalogs for English and Simplified Chinese from the first release.
- Filenames, class names, and directories support Unicode without lossy conversion.

## 20. Privacy, Sandbox, and Distribution

- All processing is local; the application contains no analytics or required network client.
- App Sandbox file access uses user-selected security-scoped bookmarks for image and annotation directories.
- Direct-download builds use Developer ID signing, Hardened Runtime, and notarization.
- App Store builds use the same application code and data behavior with store-appropriate entitlements.
- A privacy manifest declares the used system APIs and the absence of tracking.
- CI builds and tests the app, verifies entitlements, validates the bundle, and produces an unsigned test artifact; release signing remains a protected release step.

The application source uses the MIT License. Bundled models and third-party libraries retain their own compatible licenses and appear in the in-app acknowledgements and `THIRD_PARTY_NOTICES`.

## 21. Testing Strategy

### 21.1 Unit and Property Tests

- YOLO and VOC golden-file parsing and serialization.
- Round trips for empty, normal, clipped, Unicode, and high-volume annotations.
- Coordinate conversion and rounding at image boundaries.
- Class-catalog locking and all-or-nothing migration.
- File fingerprint conflicts, atomic replacement, rollback, and recovery snapshots.
- Annotation commands and undo/redo invariants.
- Canvas transforms and hit testing across zoom and Retina scale factors.

### 21.2 Integration Tests

- Open image directory, authorize separate annotation directory, edit, save, close, and reopen.
- Navigate while auto-save is pending.
- External modification and permission-loss recovery.
- Format switching without deleting the source format.
- App relaunch and crash-snapshot restoration.
- Model-unavailable fallback to manual annotation.

### 21.3 Smart-Feature Regression Tests

A versioned local fixture set measures SAM box IoU, propagation box IoU, candidate failure rate, and latency. Model upgrades require comparison with the previous bundled model. Tests validate behavior and thresholds without pretending that probabilistic output is always correct.

### 21.4 UI Tests

XCUITest covers first-run onboarding, all primary toolbar flows, class selection, keyboard-only annotation, smart-candidate acceptance, propagation, save-state visibility, localization, and VoiceOver identifiers.

## 22. Delivery Sequence

The rewrite is delivered in independently usable stages:

1. **Native foundation and safe I/O:** app shell, sandbox access, dataset session, class catalog, YOLO/VOC stores, save coordinator, diagnostics, and tests.
2. **Professional manual annotator:** AppKit canvas, object/class inspectors, LabelImg editing parity, navigation, shortcuts, undo/redo, review state, onboarding, and accessibility.
3. **Bundled SAM workflow:** Core ML model integration, embedding cache, point and box prompts, candidates, model fallback, and smart regression fixtures.
4. **Fast sequential propagation:** Vision tracking, local SAM refinement, prefetch, confidence policy, batch undo, and benchmarks.
5. **Distribution readiness:** localization polish, settings, acknowledgements, CI, signing configuration, notarization instructions, App Store entitlements, privacy manifest, and release documentation.

Each stage must pass its own tests and leave the app runnable. Smart features do not delay verification of the safe manual annotation foundation.

## 23. Acceptance Checklist

The production milestone is accepted only when:

- Existing LabelImg YOLO and VOC fixture datasets open and round-trip without unintended semantic changes.
- Auto-save, manual save, conflicts, recovery, and class migration pass failure-injection tests.
- A first-time tester can open a folder, draw or smart-create a box, choose a class, navigate, and locate the saved label without assistance.
- An experienced LabelImg tester can complete the core workflow with the documented shortcuts.
- Exact previous-box copy and intelligent propagation are separate, predictable commands.
- Low-confidence smart results cannot silently become final annotations under default settings.
- The app works fully offline after installation and contains the SAM model.
- The signed bundle contains the custom multi-resolution application icon, and its 16-pixel rendition remains clear and recognizable.
- The manual workflow remains functional when the model is deliberately removed or made to fail in a test build.
- The baseline performance targets are measured and met.
- The sandboxed archive validates, direct-download notarization succeeds, and the App Store configuration contains no known architectural blocker.
