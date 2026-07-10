from pathlib import Path

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
