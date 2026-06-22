#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python -m PyInstaller --clean --noconfirm smart-labelimg.spec
echo "Build complete:"
if [ -d "dist/Smart LabelImg.app" ]; then
  echo "  dist/Smart LabelImg.app"
elif [ -f "dist/Smart LabelImg/Smart LabelImg.exe" ]; then
  echo "  dist/Smart LabelImg/Smart LabelImg.exe"
else
  echo "  dist/Smart LabelImg/"
fi
