# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path


root = Path.cwd()
datas = []
mobile_sam_checkpoint = root / "models" / "mobile_sam.pt"
if mobile_sam_checkpoint.exists():
    datas.append((str(mobile_sam_checkpoint), "models"))


a = Analysis(
    ["smart_labelimg/app.py"],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "datasets",
        "IPython",
        "jupyterlab",
        "matplotlib",
        "nltk",
        "notebook",
        "onnxruntime",
        "pandas",
        "pyarrow",
        "pytest",
        "scipy",
        "sklearn",
        "spacy",
        "tensorflow",
        "tkinter",
        "torchaudio",
        "transformers",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Smart LabelImg",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Smart LabelImg",
)
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Smart LabelImg.app",
        icon=None,
        bundle_identifier="com.smartlabelimg.app",
        info_plist={
            "NSHighResolutionCapable": True,
            "CFBundleDisplayName": "Smart LabelImg",
        },
    )
