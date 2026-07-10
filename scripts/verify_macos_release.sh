#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

APP_PATH="dist/Smart LabelImg.app"
ZIP_PATH="release/Smart-LabelImg-macOS-Apple-Silicon.zip"
CHECKSUM_PATH="$ZIP_PATH.sha256"

test -d "$APP_PATH"
test -x "$APP_PATH/Contents/MacOS/Smart LabelImg"
test -f "$APP_PATH/Contents/Resources/AppIcon.icns"
find "$APP_PATH/Contents" -path "*/models/mobile_sam.pt" -type f | grep -q .
/usr/libexec/PlistBuddy -c "Print :CFBundleIdentifier" "$APP_PATH/Contents/Info.plist" | grep -q "com.smartlabelimg.app"
/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$APP_PATH/Contents/Info.plist" | grep -q "0.1.0"
test -f "$ZIP_PATH"
test -f "$CHECKSUM_PATH"
QT_QPA_PLATFORM=offscreen SMART_LABELIMG_SMOKE_EXIT=1 "$APP_PATH/Contents/MacOS/Smart LabelImg"
shasum -a 256 -c "$CHECKSUM_PATH"
LISTING="$(mktemp)"
zipinfo -1 "$ZIP_PATH" > "$LISTING"
grep -q "Smart LabelImg.app/Contents/Info.plist" "$LISTING"
grep -q "Smart LabelImg.app/Contents/Resources/AppIcon.icns" "$LISTING"
grep -q "Smart LabelImg.app/Contents/Resources/models/mobile_sam.pt" "$LISTING"
rm -f "$LISTING"

echo "macOS release verification passed"
