#!/usr/bin/env bash
# Bygger appen och kör alla tester: StegkampKit, enhetstester och UI-tester.
# Välj simulator med t.ex.  SIMULATOR="iPhone 16 Pro" ./scripts/test.sh
set -euo pipefail
cd "$(dirname "$0")/.."

./scripts/bootstrap.sh

echo "▶︎ StegkampKit"
swift test --package-path Packages/StegkampKit

SIMULATOR="${SIMULATOR:-$(xcrun simctl list devices available | grep -m1 -oE 'iPhone [^(]+' | sed 's/ *$//')}"
if [ -z "$SIMULATOR" ]; then
  echo "❌ Hittade ingen iPhone-simulator. Installera en i Xcode → Settings → Components."
  exit 1
fi
echo "▶︎ App och UI-tester på $SIMULATOR"

xcodebuild test \
  -project Stegkamp.xcodeproj \
  -scheme Stegkamp \
  -destination "platform=iOS Simulator,name=$SIMULATOR" \
  -skipPackagePluginValidation \
  CODE_SIGNING_ALLOWED=NO \
  | { if command -v xcbeautify >/dev/null 2>&1; then xcbeautify; else cat; fi; }

echo "✅ Alla tester gick igenom."
