from smart_labelimg.settings import AppSettings, SettingsStore


def test_settings_round_trip(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")

    store.save(AppSettings(last_image_dir="/tmp/images", annotation_format="yolo", default_class="car"))

    assert store.load().default_class == "car"
    assert store.load().last_image_dir == "/tmp/images"
    assert store.load().annotation_format == "yolo"


def test_corrupt_settings_file_recovers_with_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{broken", encoding="utf-8")
    store = SettingsStore(path)

    settings = store.load()

    assert settings == AppSettings()
    assert path.with_suffix(".json.corrupt").exists()


def test_malformed_setting_values_recover_with_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"recent_folders": 123}', encoding="utf-8")
    store = SettingsStore(path)

    assert store.load() == AppSettings()
