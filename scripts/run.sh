#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
APP_DIR="${PROJECT_DIR}/app"
BUILD_DIR="${APP_DIR}/.build/debug"
BUNDLE_DIR="${BUILD_DIR}/WhisperBatch.app"
RESOURCES_DIR="${APP_DIR}/Resources"

echo "Building WhisperBatch..."
cd "$APP_DIR"
swift build 2>&1

EXECUTABLE="${BUILD_DIR}/WhisperBatch"
if [[ ! -f "$EXECUTABLE" ]]; then
    echo "Error: Build failed, executable not found."
    exit 1
fi

echo "Assembling .app bundle..."

# Create .app bundle structure
rm -rf "$BUNDLE_DIR"
mkdir -p "$BUNDLE_DIR/Contents/MacOS"
mkdir -p "$BUNDLE_DIR/Contents/Resources"

# Copy executable
cp "$EXECUTABLE" "$BUNDLE_DIR/Contents/MacOS/WhisperBatch"

# Copy icon
if [[ -f "$RESOURCES_DIR/AppIcon.icns" ]]; then
    cp "$RESOURCES_DIR/AppIcon.icns" "$BUNDLE_DIR/Contents/Resources/AppIcon.icns"
fi

# Copy Sparkle framework if present
SPARKLE_FW="${BUILD_DIR}/Sparkle.framework"
if [[ -d "$SPARKLE_FW" ]]; then
    mkdir -p "$BUNDLE_DIR/Contents/Frameworks"
    cp -R "$SPARKLE_FW" "$BUNDLE_DIR/Contents/Frameworks/"
fi

# rpath is set at build time via linkerSettings in Package.swift

# Create Info.plist
cat > "$BUNDLE_DIR/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleExecutable</key>
    <string>WhisperBatch</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIconName</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.whisperbatch.app</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>WhisperBatch</string>
    <key>CFBundleDisplayName</key>
    <string>WhisperBatch</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>14.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSSupportsAutomaticTermination</key>
    <true/>
    <key>NSSupportsSuddenTermination</key>
    <false/>
    <key>NSHumanReadableCopyright</key>
    <string>Copyright 2026. All rights reserved.</string>
    <key>LSApplicationCategoryType</key>
    <string>public.app-category.productivity</string>
</dict>
</plist>
PLIST

echo "Launching WhisperBatch.app..."
open "$BUNDLE_DIR"
