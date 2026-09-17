#!/usr/bin/env bash
# Build an ad-hoc-signed app for local use without installing or launching it.
set -euo pipefail
cd "$(dirname "$0")"
command -v xcodegen >/dev/null || { echo "Install XcodeGen: brew install xcodegen"; exit 1; }
xcodegen generate
xcodebuild -project WhisperBatch.xcodeproj \
  -scheme WhisperBatch-AppStore -configuration AppStore \
  -derivedDataPath build/DerivedData \
  SWIFT_ENABLE_EXPLICIT_MODULES=NO COMPILER_INDEX_STORE_ENABLE=NO \
  CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO CODE_SIGN_ENTITLEMENTS="" \
  ENABLE_HARDENED_RUNTIME=NO build
APP="build/DerivedData/Build/Products/AppStore/WhisperBatch.app"
[ -d "$APP" ] || { echo "No app produced at $APP"; exit 1; }
# Finder/iCloud metadata on generated resources can prevent signing.
xattr -cr "$APP"
codesign --force --deep --sign - "$APP"
echo "Built $APP"
