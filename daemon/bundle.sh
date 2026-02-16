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

# Copy .env.prod into the bundle as .env
if [ -f "$DIR/.env.prod" ]; then
    cp "$DIR/.env.prod" "$APP_BUNDLE/Contents/MacOS/.env"
    echo "Copied .env.prod into bundle"
else
    echo "Warning: No .env.prod file found at $DIR/.env.prod"
    echo "Create one with: echo 'BACKEND_URL=http://your-server.com' > $DIR/.env.prod"
fi

echo "Bundle created: $APP_BUNDLE"
open -R "$APP_BUNDLE"
