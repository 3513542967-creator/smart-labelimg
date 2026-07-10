from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_pyinstaller_spec_requires_macos_release_assets():
    spec = (ROOT / "smart-labelimg.spec").read_text(encoding="utf-8")

    assert "models/mobile_sam.pt is required" in spec
    assert "assets/AppIcon.icns is required" in spec
    assert 'target_arch="arm64"' in spec
    assert 'bundle_identifier="com.smartlabelimg.app"' in spec
    assert '"CFBundleShortVersionString": "0.1.0"' in spec
    assert '"LSMinimumSystemVersion": "12.0"' in spec


def test_release_scripts_define_expected_artifact_names():
    build = (ROOT / "build_app.sh").read_text(encoding="utf-8")
    verify = (ROOT / "scripts" / "verify_macos_release.sh").read_text(encoding="utf-8")

    assert "Smart-LabelImg-macOS-Apple-Silicon.zip" in build
    assert "Smart-LabelImg-macOS-Apple-Silicon.zip" in verify
    assert "pytest -q" in build
    assert "shasum -a 256 -c" in verify
