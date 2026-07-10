#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-/opt/homebrew/Caskroom/miniforge/base/envs/ai/bin/python}"
APP_PATH="dist/Smart LabelImg.app"
ZIP_PATH="release/Smart-LabelImg-macOS-Apple-Silicon.zip"

"$PYTHON_BIN" -m pytest -q
"$PYTHON_BIN" -m PyInstaller --clean --noconfirm smart-labelimg.spec

if [ ! -d "$APP_PATH" ]; then
  echo "Missing app bundle: $APP_PATH" >&2
  exit 1
fi

mkdir -p release
rm -f "$ZIP_PATH" "$ZIP_PATH.sha256"
ditto -c -k --keepParent "$APP_PATH" "$ZIP_PATH"
shasum -a 256 "$ZIP_PATH" > "$ZIP_PATH.sha256"

echo "Build complete:"
echo "  $APP_PATH"
echo "  $ZIP_PATH"
echo "  $ZIP_PATH.sha256"
