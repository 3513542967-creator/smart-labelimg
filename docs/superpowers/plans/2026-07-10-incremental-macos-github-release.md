# Incremental macOS GitHub Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Incrementally turn the existing PySide6 application into a reliable, easy-to-use macOS Apple Silicon YOLO/VOC annotator with safe saves, undo/redo, MobileSAM-assisted propagation, LabelImg-style controls, and a downloadable GitHub release bundle.

**Architecture:** Preserve the existing application and extract only focused responsibilities required by each feature. New pure-Python modules own safe persistence, edit history, and propagation; `app.py` coordinates them without duplicating their logic. Existing annotation and MobileSAM backends remain the compatibility foundation.

**Tech Stack:** Python 3.11, PySide6, OpenCV, NumPy, PyTorch/MPS, MobileSAM, pytest, PyInstaller; macOS Apple Silicon.

## Global Constraints

- Modify the existing PySide6 application incrementally; do not rewrite it in Swift or fork the whole LabelImg codebase.
- Support axis-aligned bounding boxes, YOLO detection TXT, and Pascal VOC XML only.
- Preserve LabelImg-style same-basename annotations and `classes.txt` in the selected annotation directory.
- Manual annotation must work when MobileSAM is unavailable.
- Bundle MobileSAM and `models/mobile_sam.pt`; users install no Python and download no separate model.
- Auto-save is on by default; failed saves keep the current image and dirty state.
- Low-confidence propagation results remain candidates under default settings.
- Target macOS Apple Silicon GitHub distribution; Windows is not a release blocker.
- Preserve all current tests and add focused tests before implementation.
- Use `/opt/homebrew/Caskroom/miniforge/base/envs/ai/bin/python -m pytest` for the verified local Python environment.

---

### Task 1: Safe Annotation Save Coordinator

**Files:**
- Create: `smart_labelimg/save_coordinator.py`
- Modify: `smart_labelimg/app.py:1001-1040`
- Test: `tests/test_save_coordinator.py`
- Test: `tests/test_app_smoke.py`

**Interfaces:**
- Consumes: `save_annotation(path, boxes, labels, image_size, image_path)`.
- Produces: `SaveState`, `SaveResult`, `SaveCoordinator.fingerprint(path: Path) -> str | None`, `SaveCoordinator.save_bytes(files: dict[Path, bytes], expected: dict[Path, str | None]) -> SaveResult`, and `SaveCoordinator.save_annotation_atomic(path: Path, boxes: list[Box], labels: list[str], image_size: tuple[int, int], image_path: Path) -> SaveResult`.

- [ ] Write failing tests proving atomic replacement, external-change conflict, failure cleanup, and navigation staying on the current image after save failure.

```python
def test_atomic_save_replaces_destination(tmp_path):
    target = tmp_path / "a.txt"
    target.write_text("old\n", encoding="utf-8")
    coordinator = SaveCoordinator()
    result = coordinator.save_bytes({target: b"new\n"}, expected={target: coordinator.fingerprint(target)})
    assert result.state is SaveState.SAVED
    assert target.read_text(encoding="utf-8") == "new\n"
    assert not list(tmp_path.glob(".smart-labelimg-*"))

def test_external_change_is_not_overwritten(tmp_path):
    target = tmp_path / "a.txt"
    target.write_text("loaded\n", encoding="utf-8")
    coordinator = SaveCoordinator()
    expected = coordinator.fingerprint(target)
    target.write_text("external\n", encoding="utf-8")
    result = coordinator.save_bytes({target: b"local\n"}, expected={target: expected})
    assert result.state is SaveState.CONFLICT
    assert target.read_text(encoding="utf-8") == "external\n"
```

- [ ] Run the focused tests and record the expected import/type failures.

Run: `/opt/homebrew/Caskroom/miniforge/base/envs/ai/bin/python -m pytest tests/test_save_coordinator.py -q`

Expected: FAIL because `smart_labelimg.save_coordinator` does not exist.

- [ ] Implement SHA-256 fingerprints, sibling temporary files, `os.fsync`, backup/rollback for multi-file writes, and cleanup in `finally`.

```python
class SaveState(str, Enum):
    SAVED = "saved"
    CONFLICT = "conflict"
    FAILED = "failed"

@dataclass(frozen=True)
class SaveResult:
    state: SaveState
    fingerprints: dict[Path, str]
    conflicts: tuple[Path, ...] = ()
    error: str | None = None

class SaveCoordinator:
    # Public method signatures are fixed by the Interfaces block above.
    # The implementation validates all expected fingerprints before staging any file,
    # then stages, fsyncs, replaces, fingerprints, and cleans up as one transaction.
```

- [ ] Integrate `MainWindow.save_current() -> bool`, visible `save_state`, loaded fingerprints, and save-gated `select_image`, `prev_image`, and `next_image`.

- [ ] Run focused and full tests.

Run: `/opt/homebrew/Caskroom/miniforge/base/envs/ai/bin/python -m pytest tests/test_save_coordinator.py tests/test_app_smoke.py -q`

Run: `/opt/homebrew/Caskroom/miniforge/base/envs/ai/bin/python -m pytest -q`

Expected: all tests pass.

- [ ] Commit.

```bash
git add smart_labelimg/save_coordinator.py smart_labelimg/app.py tests/test_save_coordinator.py tests/test_app_smoke.py
git commit -m "feat: add safe atomic annotation saves"
```

### Task 2: Undo/Redo and LabelImg Editing Commands

**Files:**
- Create: `smart_labelimg/history.py`
- Modify: `smart_labelimg/app.py`
- Test: `tests/test_history.py`
- Test: `tests/test_app_smoke.py`

**Interfaces:**
- Consumes: `Box` and the canvas `list[Box]`.
- Produces: `AnnotationSnapshot`, `AnnotationHistory.record(boxes, labels)`, `undo()`, `redo()`, `can_undo`, and `can_redo`.

- [ ] Write failing immutable-snapshot tests.

```python
def test_undo_and_redo_restore_independent_box_copies():
    history = AnnotationHistory()
    history.reset([Box("car", 1, 2, 10, 20)], ["car"])
    history.record([Box("car", 5, 2, 14, 20)], ["car"])
    assert history.undo().boxes == (Box("car", 1, 2, 10, 20),)
    assert history.redo().boxes == (Box("car", 5, 2, 14, 20),)

def test_new_edit_after_undo_clears_redo():
    history = AnnotationHistory()
    history.reset([], ["car"])
    history.record([Box("car", 1, 1, 5, 5)], ["car"])
    history.undo()
    history.record([Box("car", 2, 2, 6, 6)], ["car"])
    assert not history.can_redo
```

- [ ] Run RED.

Run: `/opt/homebrew/Caskroom/miniforge/base/envs/ai/bin/python -m pytest tests/test_history.py -q`

Expected: FAIL because `AnnotationHistory` does not exist.

- [ ] Implement bounded history with copied `Box` values and a default limit of 100 snapshots.

- [ ] Record completed logical edits only: draw, move/resize mouse release, delete, duplicate, relabel, class rename/delete, previous-copy, SAM accept, and propagation batch.

- [ ] Add `Cmd/Ctrl+Z`, `Cmd/Ctrl+Shift+Z`, Edit menu actions, enabled states, and auto-save after restore.

- [ ] Run focused and full tests, then commit.

```bash
git add smart_labelimg/history.py smart_labelimg/app.py tests/test_history.py tests/test_app_smoke.py
git commit -m "feat: add annotation undo and redo"
```

### Task 3: Fast Previous-Image Propagation

**Files:**
- Create: `smart_labelimg/propagation.py`
- Modify: `smart_labelimg/app.py`
- Modify: `smart_labelimg/ai_backend.py`
- Test: `tests/test_propagation.py`
- Test: `tests/test_app_smoke.py`

**Interfaces:**
- Consumes: previous/current RGB NumPy images, previous `Box` values, and a backend implementing `refine_from_box`.
- Produces: `PropagationCandidate`, `PropagationResult`, `estimate_displacement(previous, current, box, search_scale=2.0) -> tuple[int, int, float]`, and `propagate_boxes(previous, current, boxes, backend, accept_threshold=0.78) -> PropagationResult`.

- [ ] Write deterministic synthetic-frame RED tests.

```python
def test_estimate_displacement_tracks_shifted_object():
    previous = np.zeros((100, 140, 3), dtype=np.uint8)
    current = previous.copy()
    previous[30:60, 30:70] = (255, 255, 255)
    current[34:64, 38:78] = (255, 255, 255)
    dx, dy, score = estimate_displacement(previous, current, Box("car", 30, 30, 70, 60))
    assert abs(dx - 8) <= 1
    assert abs(dy - 4) <= 1
    assert score >= 0.9

def test_low_confidence_result_remains_candidate():
    result = propagate_boxes(blank, noise, [Box("car", 10, 10, 30, 30)], FakeBackend())
    assert result.committed == ()
    assert len(result.candidates) == 1
    assert result.candidates[0].requires_confirmation
```

- [ ] Run RED.

Run: `/opt/homebrew/Caskroom/miniforge/base/envs/ai/bin/python -m pytest tests/test_propagation.py -q`

Expected: FAIL because `smart_labelimg.propagation` does not exist.

- [ ] Implement bounded-neighborhood grayscale template matching, clipped shifted boxes, local MobileSAM refinement, confidence calculation, and all-or-nothing result construction.

```python
@dataclass(frozen=True)
class PropagationCandidate:
    box: Box
    confidence: float
    requires_confirmation: bool

@dataclass(frozen=True)
class PropagationResult:
    committed: tuple[Box, ...]
    candidates: tuple[PropagationCandidate, ...]

# The exact public function signatures are fixed by the Interfaces block above.
# estimate_displacement returns the best integer offset and normalized match score.
# propagate_boxes returns immutable committed and candidate collections without
# mutating either source box list.
```

- [ ] Add `Shift+D` smart-next action, keep `Cmd/Ctrl+V` exact copy, apply committed boxes as one history entry, and show low-confidence candidates without auto-save until accepted.

- [ ] Run focused/full tests and commit.

```bash
git add smart_labelimg/propagation.py smart_labelimg/app.py smart_labelimg/ai_backend.py tests/test_propagation.py tests/test_app_smoke.py
git commit -m "feat: propagate boxes across sequential images"
```

### Task 4: Essential LabelImg Parity and Simple UI

**Files:**
- Modify: `smart_labelimg/app.py`
- Create: `smart_labelimg/settings.py`
- Test: `tests/test_app_smoke.py`
- Test: `tests/test_settings.py`

**Interfaces:**
- Consumes: existing `ImageCanvas`, history, and save coordinator.
- Produces: persistent `AppSettings`, square drawing, show/hide boxes, fit width, original size, brightness preview, default-class mode, recent folders, and shortcut help.

- [ ] Write RED tests for settings round-trip and visible actions/shortcuts.

```python
def test_settings_round_trip(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.save(AppSettings(last_image_dir="/tmp/images", annotation_format="yolo", default_class="car"))
    assert store.load().default_class == "car"

def test_labelimg_shortcuts_are_exposed():
    window = MainWindow()
    assert window.action_shortcuts["draw"] == "W"
    assert window.action_shortcuts["smart"] == "S"
    assert window.action_shortcuts["verify"] == "Space"
    assert window.action_shortcuts["smart_next"] == "Shift+D"
```

- [ ] Implement JSON settings with safe defaults and corrupt-file recovery.

- [ ] Add the requested actions without changing the three-area layout: square constraint, show/hide boxes, fit width, original size, brightness +/-/reset, default class, recent folders, reset settings, and a searchable shortcut dialog.

- [ ] Resolve shortcut conflicts so `Space` verifies, `S` selects smart mode, `W` selects manual draw, and `Cmd/Ctrl+J` selects edit mode.

- [ ] Add concise Chinese/English labels where the current interface is ambiguous, keep advanced controls out of the main toolbar, run all tests, and commit.

```bash
git add smart_labelimg/app.py smart_labelimg/settings.py tests/test_app_smoke.py tests/test_settings.py
git commit -m "feat: complete essential LabelImg workflow"
```

### Task 5: macOS Icon, Packaging, and Release Verification

**Files:**
- Create: `assets/AppIcon-1024.png`
- Create: `assets/AppIcon.icns`
- Modify: `smart-labelimg.spec`
- Modify: `build_app.sh`
- Create: `scripts/verify_macos_release.sh`
- Modify: `README.md`
- Create: `THIRD_PARTY_NOTICES.md`
- Test: `tests/test_packaging_config.py`

**Interfaces:**
- Consumes: passing application and bundled `models/mobile_sam.pt`.
- Produces: `dist/Smart LabelImg.app` and `release/Smart-LabelImg-macOS-Apple-Silicon.zip`.

- [ ] Write RED tests that parse the PyInstaller spec and require the model, icon, bundle identifier, Apple Silicon target, and version metadata.

- [ ] Generate the application icon with the `imagegen` skill using the approved graphite/midnight-blue, cyan bounding-box, and mint AI accent direction; produce a 1024 PNG and multi-size ICNS.

- [ ] Update PyInstaller configuration to fail when the checkpoint/icon is absent, include required MobileSAM/PySide6 runtime data, set `target_arch="arm64"`, icon, bundle identifier, display name, and minimum macOS version metadata.

- [ ] Make `build_app.sh` run tests, build cleanly, verify the `.app`, zip it, and write SHA-256.

- [ ] Add a release verification script that launches the app offscreen for construction smoke, validates the bundle/model/icon, and checks the archive contents.

- [ ] Update README installation, Gatekeeper right-click Open steps, shortcuts, model attribution, limitations, and release artifact names; add third-party notices.

- [ ] Run verification.

Run: `/opt/homebrew/Caskroom/miniforge/base/envs/ai/bin/python -m pytest -q`

Run: `./build_app.sh`

Run: `./scripts/verify_macos_release.sh`

Expected: tests pass; `.app`, ZIP, and checksum exist; bundle contains checkpoint and icon; smoke launch exits without an uncaught exception.

- [ ] Commit.

```bash
git add assets smart-labelimg.spec build_app.sh scripts/verify_macos_release.sh README.md THIRD_PARTY_NOTICES.md tests/test_packaging_config.py
git commit -m "build: package Apple Silicon GitHub release"
```

## Final Verification

Run:

```bash
/opt/homebrew/Caskroom/miniforge/base/envs/ai/bin/python -m pytest -q
python verify_app.py
python verify_sam_click.py
./scripts/verify_macos_release.sh
git diff --check
```

Expected: all automated tests pass, both verification programs succeed, release verification succeeds, and no whitespace errors remain.
