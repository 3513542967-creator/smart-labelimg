#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

APP_PATH="dist/Smart LabelImg.app"
ZIP_PATH="release/Smart-LabelImg-macOS-Apple-Silicon.zip"
CHECKSUM_PATH="$ZIP_PATH.sha256"

test -d "$APP_PATH"
test -x "$APP_PATH/Contents/MacOS/Smart LabelImg"
test -f "$APP_PATH/Contents/Resources/AppIcon.icns"
find "$APP_PATH/Contents" -path "*/models/sam_vit_b_01ec64.pth" -type f | grep -q .
/usr/libexec/PlistBuddy -c "Print :CFBundleIdentifier" "$APP_PATH/Contents/Info.plist" | grep -q "com.smartlabelimg.app"
/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$APP_PATH/Contents/Info.plist" | grep -q "0.1.0"
test -f "$ZIP_PATH"
test -f "$CHECKSUM_PATH"
SMOKE_LOG="$(mktemp)"
if ! QT_QPA_PLATFORM=offscreen SMART_LABELIMG_SMOKE_EXIT=1 "$APP_PATH/Contents/MacOS/Smart LabelImg" >"$SMOKE_LOG" 2>&1; then
  cat "$SMOKE_LOG" >&2
  rm -f "$SMOKE_LOG"
  exit 1
fi
if grep -q "SAM backend unavailable" "$SMOKE_LOG"; then
  cat "$SMOKE_LOG" >&2
  rm -f "$SMOKE_LOG"
  exit 1
fi
rm -f "$SMOKE_LOG"
shasum -a 256 -c "$CHECKSUM_PATH"
LISTING="$(mktemp)"
zipinfo -1 "$ZIP_PATH" > "$LISTING"
grep -q "Smart LabelImg.app/Contents/Info.plist" "$LISTING"
grep -q "Smart LabelImg.app/Contents/Resources/AppIcon.icns" "$LISTING"
grep -q "Smart LabelImg.app/Contents/Resources/models/sam_vit_b_01ec64.pth" "$LISTING"
rm -f "$LISTING"

echo "macOS release verification passed"
