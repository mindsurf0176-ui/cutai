#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DESKTOP_DIR="$ROOT_DIR/desktop"
source "$DESKTOP_DIR/scripts/release-artifact-paths.sh"

BUNDLE_DIR="$(cutai_release_bundle_dir "$ROOT_DIR")"
SOURCE_APP_PATH="${APP_PATH:-$(cutai_release_app_path "$ROOT_DIR")}"
SOURCE_DMG_PATH="${DMG_PATH:-$(cutai_release_dmg_path "$ROOT_DIR")}"
VERIFY_STAGE_DIR="${CUTAI_VERIFY_STAGE_DIR:-}"
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
need xattr
[[ -x "$SPCTL_BIN" ]] || { echo "spctl not found at $SPCTL_BIN" >&2; exit 1; }

[[ -d "$SOURCE_APP_PATH" ]] || { echo "App bundle not found: $SOURCE_APP_PATH" >&2; exit 1; }
[[ -n "$SOURCE_DMG_PATH" && -f "$SOURCE_DMG_PATH" ]] || { echo "DMG not found under $BUNDLE_DIR/dmg" >&2; exit 1; }

STAGE_DIR="$(cutai_prepare_stage_dir "$VERIFY_STAGE_DIR")"
APP_PATH="$STAGE_DIR/$(basename "$SOURCE_APP_PATH")"
DMG_PATH="$STAGE_DIR/$(basename "$SOURCE_DMG_PATH")"
cutai_stage_artifact "$SOURCE_APP_PATH" "$APP_PATH"
cutai_stage_artifact "$SOURCE_DMG_PATH" "$DMG_PATH"
if ! xattr -cr "$APP_PATH"; then
  log "FAILED: unable to clear extended attributes from staged app copy"
  exit 1
fi
if ! xattr -cr "$DMG_PATH"; then
  log "FAILED: unable to clear extended attributes from staged DMG copy"
  exit 1
fi

log "Release artifacts selected"
log "Source app: $SOURCE_APP_PATH"
log "Source DMG: $SOURCE_DMG_PATH"
log "Stage dir: $STAGE_DIR"
log "Staged app: $APP_PATH"
log "Staged DMG: $DMG_PATH"

log "Extended attributes for app"
app_xattrs="$(xattr -lr "$APP_PATH" 2>/dev/null || true)"
if [[ -n "$app_xattrs" ]]; then
  printf '%s\n' "$app_xattrs" | sed 's/^/[app-xattr] /'
else
  log "No extended attributes found on app bundle"
fi

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
