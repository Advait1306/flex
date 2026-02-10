#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="Flex Daemon"
APP_BUNDLE="$DIR/$APP_NAME.app"

echo "Building release binary..."
cd "$DIR"
swift build -c release

echo "Creating app bundle..."
mkdir -p "$APP_BUNDLE/Contents/MacOS"

cp .build/release/FlexDaemonCLI "$APP_BUNDLE/Contents/MacOS/FlexDaemonCLI"

cat > "$APP_BUNDLE/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>FlexDaemonCLI</string>
    <key>CFBundleIdentifier</key>
    <string>com.flex.daemon</string>
    <key>CFBundleName</key>
    <string>Flex Daemon</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>LSUIElement</key>
    <false/>
</dict>
</plist>
PLIST

# Copy .env into the bundle if it exists
if [ -f "$DIR/.env" ]; then
    cp "$DIR/.env" "$APP_BUNDLE/Contents/MacOS/.env"
    echo "Copied .env into bundle"
else
    echo "Warning: No .env file found at $DIR/.env"
    echo "Create one with: echo 'BACKEND_URL=http://localhost:8000' > $DIR/.env"
fi

echo "Bundle created: $APP_BUNDLE"
open -R "$APP_BUNDLE"
