#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DESKTOP_DIR="$ROOT_DIR/desktop"
BUNDLE_DIR="$DESKTOP_DIR/src-tauri/target/release/bundle"
APP_PATH="${APP_PATH:-$BUNDLE_DIR/macos/CutAI.app}"
DMG_PATH="${DMG_PATH:-$(compgen -G "$BUNDLE_DIR/dmg/CutAI_*.dmg" | head -n 1 || true)}"
APPLE_IDENTITY="${APPLE_IDENTITY:-}"
APPLE_TEAM_ID="${APPLE_TEAM_ID:-}"
APPLE_NOTARY_PROFILE="${APPLE_NOTARY_PROFILE:-}"
DRY_RUN="${DRY_RUN:-0}"
SKIP_NOTARY="${SKIP_NOTARY:-0}"

log() {
  printf '[notarize] %s\n' "$*"
}

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

run() {
  log "$*"
  if [[ "$DRY_RUN" == "1" ]]; then
    return 0
  fi
  "$@"
}

need codesign
need xcrun

[[ -d "$APP_PATH" ]] || { echo "App bundle not found: $APP_PATH" >&2; exit 1; }
[[ -n "$DMG_PATH" && -f "$DMG_PATH" ]] || { echo "DMG not found under $BUNDLE_DIR/dmg" >&2; exit 1; }

if [[ -z "$APPLE_IDENTITY" ]]; then
  echo "Set APPLE_IDENTITY to your Developer ID Application/Common Name." >&2
  exit 1
fi

if [[ "$SKIP_NOTARY" != "1" && -z "$APPLE_NOTARY_PROFILE" ]]; then
  echo "Set APPLE_NOTARY_PROFILE to a notarytool keychain profile, or set SKIP_NOTARY=1." >&2
  exit 1
fi

log "Signing app bundle with hardened runtime"
run codesign --force --deep --options runtime --timestamp --sign "$APPLE_IDENTITY" "$APP_PATH"
run codesign --verify --deep --strict --verbose=2 "$APP_PATH"

log "Checking DMG signature state"
if ! codesign --verify --verbose=2 "$DMG_PATH" >/dev/null 2>&1; then
  log "Signing DMG"
  run codesign --force --timestamp --sign "$APPLE_IDENTITY" "$DMG_PATH"
fi
run codesign --verify --verbose=2 "$DMG_PATH"

if [[ "$SKIP_NOTARY" == "1" ]]; then
  log "Skipping notarization because SKIP_NOTARY=1"
  exit 0
fi

log "Submitting DMG for notarization via profile '$APPLE_NOTARY_PROFILE'"
run xcrun notarytool submit "$DMG_PATH" --keychain-profile "$APPLE_NOTARY_PROFILE" --wait

log "Stapling notarization tickets"
run xcrun stapler staple "$APP_PATH"
run xcrun stapler staple "$DMG_PATH"

log "Notarization flow complete"
if [[ -n "$APPLE_TEAM_ID" ]]; then
  log "Expected team id: $APPLE_TEAM_ID"
fi
