# Windows Install And Build

Smart LabelImg supports Windows 10/11 on 64-bit Python 3.11.

## For End Users

Use the packaged release when available:

1. Download `Smart-LabelImg-MobileSAM-Windows-x64.zip`.
2. Unzip it.
3. Open `Smart LabelImg\Smart LabelImg.exe`.

The release package includes `models\mobile_sam.pt`, so smart annotation works
without a separate model download.

## Run From Source

Install prerequisites first:

- Python 3.11 from `https://www.python.org/downloads/windows/`
- Git for Windows from `https://git-scm.com/download/win`

Then open PowerShell in the project folder:

```powershell
.\setup_windows.ps1
.\run_windows.ps1
```

If PowerShell blocks scripts, use the batch wrappers instead:

```bat
setup_windows.bat
run_windows.bat
```

## Build The Windows EXE

Build on Windows, not macOS or Linux:

```powershell
.\build_windows.ps1
```

The build output is:

```text
dist\Smart LabelImg\Smart LabelImg.exe
```

The distributable zip is:

```text
release\Smart-LabelImg-MobileSAM-Windows-x64.zip
```

## Useful Options

```powershell
.\setup_windows.ps1 -SkipAi
```

Installs only the UI dependencies. Use this only for development; smart
annotation requires MobileSAM.

```powershell
.\build_windows.ps1 -SkipInstall
```

Uses the existing `.venv` and skips dependency installation.

```powershell
.\build_windows.ps1 -NoZip
```

Builds the exe folder without creating the release zip.

## Notes

- Windows builds must be made on Windows because PyInstaller creates
  platform-specific binaries.
- If `models\mobile_sam.pt` is missing, source runs and release builds stop
  with an explicit error because this project requires MobileSAM.
- CPU works, but MobileSAM will be slower than CUDA. The app still uses the
  crop-size setting to reduce inference work.
