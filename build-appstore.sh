#!/usr/bin/env bash
# Generate project -> archive the App Store target -> export a signed .pkg ready
# to upload to App Store Connect.
# Prereqs: brew install xcodegen ; Apple Distribution cert + Mac App Store
# provisioning configured in Xcode.
set -euo pipefail
cd "$(dirname "$0")"

command -v xcodegen >/dev/null || { echo "Install xcodegen: brew install xcodegen"; exit 1; }

xcodegen generate

ARCHIVE="build/WhisperBatch.xcarchive"
rm -rf build/export build/DerivedData/ModuleCache.noindex

# Match the module-scanning settings used by the local build.
xcodebuild -project WhisperBatch.xcodeproj \
  -scheme WhisperBatch-AppStore \
  -configuration AppStore \
  -archivePath "$ARCHIVE" \
  SWIFT_ENABLE_EXPLICIT_MODULES=NO COMPILER_INDEX_STORE_ENABLE=NO \
  archive

xcodebuild -exportArchive \
  -archivePath "$ARCHIVE" \
  -exportPath build/export \
  -exportOptionsPlist ExportOptions.plist

echo
echo "✓ Exported package:"
ls -1 build/export/*.pkg
echo
echo "Next: upload it. Drag the .pkg into Transporter.app, or:"
echo "  xcrun altool --upload-app -f build/export/*.pkg --type macos \\"
echo "    --apiKey <KEY_ID> --apiIssuer <ISSUER_ID>"
