#!/usr/bin/env bash
set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
# Replace these with your actual values before building.
TEAM_ID="YOUR_TEAM_ID"                                                  # Apple Developer Team ID
BUNDLE_ID="com.whisperbatch.app"
APP_NAME="WhisperBatch"

# Signing identity for direct download (Developer ID, distributed outside App Store)
SIGNING_ID_DEVELOPER="Developer ID Application: YOUR_NAME (TEAM_ID)"

# Signing identity for App Store builds (Apple Distribution certificate)
SIGNING_ID_APP_STORE="Apple Distribution: YOUR_NAME (TEAM_ID)"

# Installer signing identity for App Store .pkg
SIGNING_ID_INSTALLER="3rd Party Mac Developer Installer: YOUR_NAME (TEAM_ID)"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
APP_DIR="${PROJECT_DIR}/app"
BUILD_DIR="${APP_DIR}/.build"
ENTITLEMENTS="${APP_DIR}/Resources/WhisperBatch.entitlements"

# ── Build Mode ────────────────────────────────────────────────────────────────
# Usage:
#   ./scripts/build.sh            Direct download build (Sparkle, Developer ID, notarize, DMG)
#   ./scripts/build.sh appstore   App Store build (no Sparkle, Apple Distribution, .pkg)

BUILD_MODE="${1:-direct}"

if [[ "$BUILD_MODE" != "direct" && "$BUILD_MODE" != "appstore" ]]; then
    echo "Usage: $0 [appstore]"
    echo ""
    echo "  (no argument)  Direct download build (Sparkle, Developer ID signing, notarization, DMG)"
    echo "  appstore       App Store build (no Sparkle, Apple Distribution signing, .pkg for upload)"
    echo ""
    exit 1
fi

cd "$APP_DIR"

# ── Build ─────────────────────────────────────────────────────────────────────
SWIFT_FLAGS="-c release"

if [[ "$BUILD_MODE" == "appstore" ]]; then
    echo "==> Building ${APP_NAME} for App Store..."
    SWIFT_FLAGS="${SWIFT_FLAGS} -Xswiftc -DAPP_STORE"
else
    echo "==> Building ${APP_NAME} for direct download..."
fi

swift build $SWIFT_FLAGS

PRODUCT_PATH="${BUILD_DIR}/release/${APP_NAME}.app"

if [[ ! -d "$PRODUCT_PATH" ]]; then
    echo "Error: Built product not found at ${PRODUCT_PATH}"
    echo "You may need to adjust the product path for your project layout."
    exit 1
fi

echo "Built product: ${PRODUCT_PATH}"

# ── Sparkle Framework ─────────────────────────────────────────────────────────
if [[ "$BUILD_MODE" == "direct" ]]; then
    # Copy Sparkle.framework into the app bundle for auto-update support
    FRAMEWORKS_DIR="${PRODUCT_PATH}/Contents/Frameworks"
    SPARKLE_FRAMEWORK="${BUILD_DIR}/artifacts/sparkle/Sparkle.xcframework/macos-arm64_x86_64/Sparkle.framework"

    if [[ -d "$SPARKLE_FRAMEWORK" ]]; then
        echo "Copying Sparkle.framework into bundle..."
        mkdir -p "$FRAMEWORKS_DIR"
        cp -R "$SPARKLE_FRAMEWORK" "$FRAMEWORKS_DIR/"
    else
        echo "Warning: Sparkle.framework not found at ${SPARKLE_FRAMEWORK}"
        echo "Auto-update will not work. Check your Sparkle dependency path."
    fi
else
    # App Store build: remove Sparkle.framework if it was copied by SwiftPM
    FRAMEWORKS_DIR="${PRODUCT_PATH}/Contents/Frameworks"
    if [[ -d "${FRAMEWORKS_DIR}/Sparkle.framework" ]]; then
        echo "Removing Sparkle.framework from App Store bundle..."
        rm -rf "${FRAMEWORKS_DIR}/Sparkle.framework"
    fi
fi

# ── Code Signing ──────────────────────────────────────────────────────────────
if [[ "$BUILD_MODE" == "appstore" ]]; then
    echo "==> Signing for App Store..."

    # Sign frameworks first, then the main bundle
    FRAMEWORKS_DIR="${PRODUCT_PATH}/Contents/Frameworks"
    if [[ -d "$FRAMEWORKS_DIR" ]]; then
        find "$FRAMEWORKS_DIR" -name "*.framework" -o -name "*.dylib" | while read -r fw; do
            codesign --force --sign "$SIGNING_ID_APP_STORE" \
                --entitlements "$ENTITLEMENTS" \
                --options runtime \
                "$fw"
        done
    fi

    codesign --force --deep --sign "$SIGNING_ID_APP_STORE" \
        --entitlements "$ENTITLEMENTS" \
        --options runtime \
        "$PRODUCT_PATH"
else
    echo "==> Signing for direct distribution..."

    # Sign Sparkle framework first
    SPARKLE_IN_BUNDLE="${PRODUCT_PATH}/Contents/Frameworks/Sparkle.framework"
    if [[ -d "$SPARKLE_IN_BUNDLE" ]]; then
        codesign --force --sign "$SIGNING_ID_DEVELOPER" \
            --options runtime \
            "$SPARKLE_IN_BUNDLE"
    fi

    codesign --force --deep --sign "$SIGNING_ID_DEVELOPER" \
        --entitlements "$ENTITLEMENTS" \
        --options runtime \
        "$PRODUCT_PATH"
fi

echo "Verifying signature..."
codesign --verify --deep --strict "$PRODUCT_PATH"
echo "Signature verified."

# ── Packaging ─────────────────────────────────────────────────────────────────
if [[ "$BUILD_MODE" == "appstore" ]]; then
    # Create a signed .pkg for App Store upload via Transporter or altool
    PKG_OUTPUT="${PROJECT_DIR}/${APP_NAME}.pkg"
    echo "==> Creating App Store .pkg..."

    productbuild \
        --component "$PRODUCT_PATH" /Applications \
        --sign "$SIGNING_ID_INSTALLER" \
        "$PKG_OUTPUT"

    echo "App Store package created: ${PKG_OUTPUT}"
    echo "Upload with: xcrun altool --upload-app -f \"${PKG_OUTPUT}\" -t osx --apiKey ... --apiIssuer ..."
    echo "         or: open Transporter.app and drag in the .pkg"

else
    # Direct download: notarize, then create a DMG
    echo "==> Notarizing..."
    NOTARIZE_ZIP="/tmp/${APP_NAME}-notarize.zip"
    ditto -c -k --keepParent "$PRODUCT_PATH" "$NOTARIZE_ZIP"

    xcrun notarytool submit "$NOTARIZE_ZIP" \
        --team-id "$TEAM_ID" \
        --wait

    xcrun stapler staple "$PRODUCT_PATH"
    rm -f "$NOTARIZE_ZIP"
    echo "Notarization complete."

    # Create DMG
    DMG_OUTPUT="${PROJECT_DIR}/${APP_NAME}.dmg"

    if ! command -v create-dmg &>/dev/null; then
        echo "Warning: create-dmg not found. Install with: brew install create-dmg"
        echo "Skipping DMG creation. The signed app is at: ${PRODUCT_PATH}"
    else
        echo "==> Creating DMG..."
        rm -f "$DMG_OUTPUT"

        create-dmg \
            --volname "$APP_NAME" \
            --volicon "${APP_DIR}/Resources/AppIcon.icns" \
            --window-pos 200 120 \
            --window-size 600 400 \
            --icon-size 100 \
            --icon "$APP_NAME.app" 150 190 \
            --app-drop-link 450 190 \
            --no-internet-enable \
            "$DMG_OUTPUT" \
            "$PRODUCT_PATH"

        echo "Notarizing DMG..."
        xcrun notarytool submit "$DMG_OUTPUT" \
            --team-id "$TEAM_ID" \
            --wait
        xcrun stapler staple "$DMG_OUTPUT"

        echo "DMG created: ${DMG_OUTPUT}"
    fi
fi

echo "Done."
