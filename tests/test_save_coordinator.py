from pathlib import Path

from smart_labelimg.annotation import Box
from smart_labelimg.save_coordinator import SaveCoordinator, SaveState


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
    assert result.conflicts == (target,)
    assert target.read_text(encoding="utf-8") == "external\n"


def test_failed_multi_file_save_rolls_back_and_cleans_temporary_files(tmp_path, monkeypatch):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_bytes(b"first-old")
    second.write_bytes(b"second-old")
    coordinator = SaveCoordinator()
    expected = {path: coordinator.fingerprint(path) for path in (first, second)}
    real_replace = __import__("os").replace
    destination_replacements = 0

    def fail_second_destination(source: str | Path, destination: str | Path) -> None:
        nonlocal destination_replacements
        if Path(destination) in (first, second) and ".smart-labelimg-stage-" in Path(source).name:
            destination_replacements += 1
            if destination_replacements == 2:
                raise OSError("simulated replacement failure")
        real_replace(source, destination)

    monkeypatch.setattr("smart_labelimg.save_coordinator.os.replace", fail_second_destination)

    result = coordinator.save_bytes({first: b"first-new", second: b"second-new"}, expected=expected)

    assert result.state is SaveState.FAILED
    assert first.read_bytes() == b"first-old"
    assert second.read_bytes() == b"second-old"
    assert not list(tmp_path.glob(".smart-labelimg-*"))


def test_yolo_annotation_save_writes_classes_in_same_transaction(tmp_path):
    annotation = tmp_path / "image.txt"
    classes = tmp_path / "classes.txt"
    coordinator = SaveCoordinator()

    result = coordinator.save_annotation_atomic(
        annotation,
        [Box("car", 10, 20, 30, 40)],
        ["object", "car"],
        (100, 100),
        tmp_path / "image.jpg",
    )

    assert result.state is SaveState.SAVED
    assert annotation.read_text(encoding="utf-8") == "1 0.200000 0.300000 0.200000 0.200000\n"
    assert classes.read_text(encoding="utf-8") == "object\ncar\n"
    assert set(result.fingerprints) == {annotation, classes}


def test_classes_conflict_preserves_yolo_annotation_and_classes(tmp_path):
    annotation = tmp_path / "image.txt"
    classes = tmp_path / "classes.txt"
    annotation.write_text("old annotation\n", encoding="utf-8")
    classes.write_text("object\ncar\n", encoding="utf-8")
    coordinator = SaveCoordinator()
    coordinator.expected = {
        annotation: coordinator.fingerprint(annotation),
        classes: coordinator.fingerprint(classes),
    }
    classes.write_text("external\n", encoding="utf-8")

    result = coordinator.save_annotation_atomic(
        annotation,
        [Box("car", 10, 20, 30, 40)],
        ["object", "car"],
        (100, 100),
        tmp_path / "image.jpg",
    )

    assert result.state is SaveState.CONFLICT
    assert result.conflicts == (classes,)
    assert annotation.read_text(encoding="utf-8") == "old annotation\n"
    assert classes.read_text(encoding="utf-8") == "external\n"
