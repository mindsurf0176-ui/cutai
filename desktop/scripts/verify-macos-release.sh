#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DESKTOP_DIR="$ROOT_DIR/desktop"
BUNDLE_DIR="$DESKTOP_DIR/src-tauri/target/release/bundle"
APP_PATH="${APP_PATH:-$BUNDLE_DIR/macos/CutAI.app}"
DMG_PATH="${DMG_PATH:-$(compgen -G "$BUNDLE_DIR/dmg/CutAI_*.dmg" | head -n 1 || true)}"
EXPECT_NOTARIZED="${EXPECT_NOTARIZED:-0}"
SPCTL_BIN="${SPCTL_BIN:-/usr/sbin/spctl}"
FAILURES=0

log() {
  printf '[verify] %s\n' "$*"
}

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

check() {
  local label="$1"
  shift
  log "$label"
  if "$@"; then
    return 0
  fi
  FAILURES=$((FAILURES + 1))
  log "FAILED: $label"
  return 0
}

need codesign
need xcrun
[[ -x "$SPCTL_BIN" ]] || { echo "spctl not found at $SPCTL_BIN" >&2; exit 1; }

[[ -d "$APP_PATH" ]] || { echo "App bundle not found: $APP_PATH" >&2; exit 1; }
[[ -n "$DMG_PATH" && -f "$DMG_PATH" ]] || { echo "DMG not found under $BUNDLE_DIR/dmg" >&2; exit 1; }

log "App signature details"
codesign --display --verbose=4 "$APP_PATH" 2>&1 | sed 's/^/[app-sign] /'
check "App signature verification" codesign --verify --deep --strict --verbose=2 "$APP_PATH"

log "DMG signature details"
codesign --display --verbose=4 "$DMG_PATH" 2>&1 | sed 's/^/[dmg-sign] /'
check "DMG signature verification" codesign --verify --verbose=2 "$DMG_PATH"
check "Gatekeeper assessment for app" "$SPCTL_BIN" --assess --type execute --verbose=4 "$APP_PATH"
check "Gatekeeper assessment for DMG" "$SPCTL_BIN" --assess --type open --verbose=4 "$DMG_PATH"

if [[ "$EXPECT_NOTARIZED" == "1" ]]; then
  check "Stapler validation for app" xcrun stapler validate "$APP_PATH"
  check "Stapler validation for DMG" xcrun stapler validate "$DMG_PATH"
fi

if [[ "$FAILURES" -gt 0 ]]; then
  log "Verification finished with $FAILURES failing check(s)"
  exit 1
fi

log "Verification complete"
