#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DESKTOP_DIR="$ROOT_DIR/desktop"
source "$DESKTOP_DIR/scripts/release-artifact-paths.sh"

BUNDLE_DIR="$(cutai_release_bundle_dir "$ROOT_DIR")"
APP_PATH="$(cutai_release_app_path "$ROOT_DIR")"

log() {
  printf '[release-build] %s\n' "$*"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

require_cmd pnpm
require_cmd cargo
require_cmd xcrun
require_cmd python3

cd "$DESKTOP_DIR"

log "Installing frontend dependencies if needed"
pnpm install --frozen-lockfile

if [[ -d "$BUNDLE_DIR" ]]; then
  log "Removing previous release bundle artifacts"
  rm -rf "$BUNDLE_DIR"
fi

log "Building Tauri desktop release bundle"
pnpm tauri build "$@"

if [[ ! -d "$APP_PATH" ]]; then
  echo "Expected app bundle not found: $APP_PATH" >&2
  exit 1
fi

DMG_PATH="$(cutai_release_dmg_path "$ROOT_DIR")"

log "Release bundle ready"
log "App: $APP_PATH"
if [[ -n "$DMG_PATH" ]]; then
  log "DMG: $DMG_PATH"
else
  log "DMG: not found"
fi

log "Current signature summary"
codesign --display --verbose=4 "$APP_PATH" 2>&1 | sed 's/^/[codesign] /'
