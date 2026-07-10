import smart_labelimg.app as app_module
from smart_labelimg.app import MainWindow
from PySide6.QtWidgets import QApplication


class FakeMobileSamBackend:
    def __init__(self, checkpoint_path: str):
        self.checkpoint_path = checkpoint_path


def test_main_window_uses_sam_for_assisted_boxes_without_text_auto_detect(monkeypatch, tmp_path):
    checkpoint = tmp_path / "mobile_sam.pt"
    checkpoint.write_bytes(b"fake checkpoint")
    monkeypatch.setattr(app_module, "MOBILE_SAM_CHECKPOINT", checkpoint)
    monkeypatch.setattr(app_module, "SamClickBackend", FakeMobileSamBackend)

    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    assert isinstance(window.backend, FakeMobileSamBackend)
    assert window.backend.checkpoint_path == str(checkpoint)
    assert not hasattr(window, "locate_backend")
    window.close()
