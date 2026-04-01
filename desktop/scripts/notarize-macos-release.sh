#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DESKTOP_DIR="$ROOT_DIR/desktop"
source "$DESKTOP_DIR/scripts/release-artifact-paths.sh"

BUNDLE_DIR="$(cutai_release_bundle_dir "$ROOT_DIR")"
SOURCE_APP_PATH="${APP_PATH:-$(cutai_release_app_path "$ROOT_DIR")}"
SOURCE_DMG_PATH="${DMG_PATH:-$(cutai_release_dmg_path "$ROOT_DIR")}"
RELEASE_STAGE_DIR="${CUTAI_RELEASE_STAGE_DIR:-}"
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
need xattr

[[ -d "$SOURCE_APP_PATH" ]] || { echo "App bundle not found: $SOURCE_APP_PATH" >&2; exit 1; }
[[ -n "$SOURCE_DMG_PATH" && -f "$SOURCE_DMG_PATH" ]] || { echo "DMG not found under $BUNDLE_DIR/dmg" >&2; exit 1; }

if [[ -z "$APPLE_IDENTITY" ]]; then
  echo "Set APPLE_IDENTITY to your Developer ID Application/Common Name." >&2
  exit 1
fi

if [[ "$SKIP_NOTARY" != "1" && -z "$APPLE_NOTARY_PROFILE" ]]; then
  echo "Set APPLE_NOTARY_PROFILE to a notarytool keychain profile, or set SKIP_NOTARY=1." >&2
  exit 1
fi

STAGE_DIR="$(cutai_prepare_stage_dir "$RELEASE_STAGE_DIR")"
APP_PATH="$STAGE_DIR/$(basename "$SOURCE_APP_PATH")"
DMG_PATH="$STAGE_DIR/$(basename "$SOURCE_DMG_PATH")"

log "Staging release artifacts"
log "Source app: $SOURCE_APP_PATH"
log "Source DMG: $SOURCE_DMG_PATH"
log "Stage dir: $STAGE_DIR"
cutai_stage_artifact "$SOURCE_APP_PATH" "$APP_PATH"
cutai_stage_artifact "$SOURCE_DMG_PATH" "$DMG_PATH"

log "Clearing extended attributes from release artifacts before signing"
run xattr -cr "$APP_PATH"
run xattr -cr "$DMG_PATH"

log "Signing all nested Mach-O binaries inside the app bundle (inside-out)"
SIGN_COUNT=0
while IFS= read -r -d '' bin; do
  # Check if it's actually a Mach-O binary
  if file "$bin" | grep -q 'Mach-O'; then
    run codesign --force --options runtime --timestamp --sign "$APPLE_IDENTITY" "$bin"
    SIGN_COUNT=$((SIGN_COUNT + 1))
  fi
done < <(find "$APP_PATH" -type f \( -name '*.so' -o -name '*.dylib' -o -name '*.node' \) -print0)

# Also find executables with no extension that are Mach-O (python, python3, etc.)
while IFS= read -r -d '' bin; do
  if file "$bin" | grep -q 'Mach-O'; then
    # Skip if already signed above (has known extension)
    case "$bin" in
      *.so|*.dylib|*.node) continue ;;
    esac
    run codesign --force --options runtime --timestamp --sign "$APPLE_IDENTITY" "$bin"
    SIGN_COUNT=$((SIGN_COUNT + 1))
  fi
done < <(find "$APP_PATH/Contents" -type f -perm +111 -print0)

log "Signed $SIGN_COUNT nested binaries"

log "Signing top-level app bundle with hardened runtime"
run codesign --force --options runtime --timestamp --sign "$APPLE_IDENTITY" "$APP_PATH"
run codesign --verify --deep --strict --verbose=2 "$APP_PATH"

log "Recreating DMG from signed app bundle"
DMG_VOLNAME="CutAI"
DMG_TEMP="${DMG_PATH%.dmg}_unsigned.dmg"
run rm -f "$DMG_PATH" "$DMG_TEMP"
run hdiutil create -volname "$DMG_VOLNAME" -srcfolder "$APP_PATH" -ov -format UDZO "$DMG_TEMP"
run mv "$DMG_TEMP" "$DMG_PATH"

log "Signing DMG"
run codesign --force --timestamp --sign "$APPLE_IDENTITY" "$DMG_PATH"
run codesign --verify --verbose=2 "$DMG_PATH"

if [[ "$SKIP_NOTARY" == "1" ]]; then
  log "Signed app: $APP_PATH"
  log "Signed DMG: $DMG_PATH"
  log "Skipping notarization because SKIP_NOTARY=1"
  exit 0
fi

log "Submitting DMG for notarization via profile '$APPLE_NOTARY_PROFILE'"
run xcrun notarytool submit "$DMG_PATH" --keychain-profile "$APPLE_NOTARY_PROFILE" --wait

log "Stapling notarization tickets"
run xcrun stapler staple "$APP_PATH"
run xcrun stapler staple "$DMG_PATH"

log "Notarization flow complete"
log "Signed app: $APP_PATH"
log "Signed DMG: $DMG_PATH"
if [[ -n "$APPLE_TEAM_ID" ]]; then
  log "Expected team id: $APPLE_TEAM_ID"
fi
