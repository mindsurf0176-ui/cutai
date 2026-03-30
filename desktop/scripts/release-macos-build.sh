#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DESKTOP_DIR="$ROOT_DIR/desktop"
BUNDLE_DIR="$DESKTOP_DIR/src-tauri/target/release/bundle"
APP_PATH="$BUNDLE_DIR/macos/CutAI.app"
DMG_GLOB="$BUNDLE_DIR/dmg/CutAI_*.dmg"

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

cd "$DESKTOP_DIR"

log "Installing frontend dependencies if needed"
pnpm install --frozen-lockfile

log "Building Tauri desktop release bundle"
pnpm tauri build "$@"

if [[ ! -d "$APP_PATH" ]]; then
  echo "Expected app bundle not found: $APP_PATH" >&2
  exit 1
fi

DMG_PATH="$(compgen -G "$DMG_GLOB" | head -n 1 || true)"

log "Release bundle ready"
log "App: $APP_PATH"
if [[ -n "$DMG_PATH" ]]; then
  log "DMG: $DMG_PATH"
else
  log "DMG: not found"
fi

log "Current signature summary"
codesign --display --verbose=4 "$APP_PATH" 2>&1 | sed 's/^/[codesign] /'
