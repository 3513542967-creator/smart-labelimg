from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_app_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("SMART_LABELIMG_SETTINGS_PATH", str(tmp_path / "app-settings.json"))
