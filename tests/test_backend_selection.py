import smart_labelimg.app as app_module
from smart_labelimg.app import MainWindow
from PySide6.QtWidgets import QApplication


class FakeSamBackend:
    def __init__(self, checkpoint_path: str):
        self.checkpoint_path = checkpoint_path


def test_main_window_uses_sam_for_assisted_boxes_without_text_auto_detect(monkeypatch, tmp_path):
    checkpoint = tmp_path / "sam_vit_b_01ec64.pth"
    checkpoint.write_bytes(b"fake checkpoint")
    monkeypatch.setattr(app_module, "SAM_CHECKPOINT", checkpoint)
    monkeypatch.setattr(app_module, "SamClickBackend", FakeSamBackend)

    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    assert isinstance(window.backend, FakeSamBackend)
    assert window.backend.checkpoint_path == str(checkpoint)
    assert not hasattr(window, "locate_backend")
    window.close()
