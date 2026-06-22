from smart_labelimg.ai_backend import SamClickBackend
from smart_labelimg.app import MainWindow
from PySide6.QtWidgets import QApplication


def test_main_window_uses_sam_for_assisted_boxes_without_text_auto_detect():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    assert isinstance(window.backend, SamClickBackend)
    assert not hasattr(window, "locate_backend")
    window.close()
