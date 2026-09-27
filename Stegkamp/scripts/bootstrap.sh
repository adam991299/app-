#!/usr/bin/env bash
# Förbereder projektet och genererar Stegkamp.xcodeproj från project.yml.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v xcodegen >/dev/null 2>&1; then
  echo "❌ XcodeGen saknas. Installera med:  brew install xcodegen"
  exit 1
fi

if [ ! -f Config/Local.xcconfig ]; then
  cp Config/Local.example.xcconfig Config/Local.xcconfig
  echo "📝 Skapade Config/Local.xcconfig – fyll i ditt Team ID (DEVELOPMENT_TEAM) där."
fi

if [ ! -f Stegkamp/Resources/GoogleService-Info.plist ]; then
  echo "ℹ️  GoogleService-Info.plist saknas – appen körs i demoläge tills du lägger in den i Stegkamp/Resources/."
fi

xcodegen generate --quiet
echo "✅ Stegkamp.xcodeproj är genererat. Öppna med:  open Stegkamp.xcodeproj"
