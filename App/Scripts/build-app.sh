#!/usr/bin/env bash
set -euo pipefail

# Assembles BusinessConsultant.app from the SwiftPM executable build. This
# project deliberately isn't an Xcode project (see ../../DISCOVERY.md), so
# there's no Xcode-managed app bundle to fall back on — this script builds
# one by hand: compile via SwiftPM, then wrap the binary + Info.plist + icon
# into a real .app bundle and ad-hoc sign it (local use only, not notarized;
# notarization needs an Apple Developer account this project doesn't use).

cd "$(dirname "$0")/.."  # App/

APP_NAME="BusinessConsultant"
BUNDLE_NAME="${APP_NAME}.app"
CONFIGURATION="${1:-release}"
OUTPUT_DIR=".build/app"

echo "==> Building ($CONFIGURATION)..."
swift build -c "$CONFIGURATION"

BIN_DIR=$(swift build -c "$CONFIGURATION" --show-bin-path)
BINARY_PATH="$BIN_DIR/$APP_NAME"

if [ ! -f "$BINARY_PATH" ]; then
  echo "error: built binary not found at $BINARY_PATH" >&2
  exit 1
fi

echo "==> Assembling $BUNDLE_NAME..."
rm -rf "$OUTPUT_DIR/$BUNDLE_NAME"
mkdir -p "$OUTPUT_DIR/$BUNDLE_NAME/Contents/MacOS"
mkdir -p "$OUTPUT_DIR/$BUNDLE_NAME/Contents/Resources"

cp "$BINARY_PATH" "$OUTPUT_DIR/$BUNDLE_NAME/Contents/MacOS/$APP_NAME"
cp Resources/Info.plist "$OUTPUT_DIR/$BUNDLE_NAME/Contents/Info.plist"
cp Resources/AppIcon.icns "$OUTPUT_DIR/$BUNDLE_NAME/Contents/Resources/AppIcon.icns"

echo "==> Ad-hoc code signing (local use only, not notarized)..."
codesign --force --deep --sign - "$OUTPUT_DIR/$BUNDLE_NAME"

echo "==> Done: $OUTPUT_DIR/$BUNDLE_NAME"
echo "    Run:      open \"$OUTPUT_DIR/$BUNDLE_NAME\""
echo "    Install:  cp -R \"$OUTPUT_DIR/$BUNDLE_NAME\" /Applications/"
