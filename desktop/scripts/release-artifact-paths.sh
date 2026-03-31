#!/usr/bin/env bash

cutai_release_bundle_dir() {
  local root_dir="${1:?root dir required}"
  printf '%s\n' "$root_dir/desktop/src-tauri/target/release/bundle"
}

cutai_release_app_path() {
  local root_dir="${1:?root dir required}"
  printf '%s\n' "$(cutai_release_bundle_dir "$root_dir")/macos/CutAI.app"
}

cutai_release_dmg_path() {
  local root_dir="${1:?root dir required}"
  local bundle_dir
  bundle_dir="$(cutai_release_bundle_dir "$root_dir")"

  python3 - "$bundle_dir" <<'PY'
from pathlib import Path
import sys

bundle_dir = Path(sys.argv[1])
candidates = sorted(
    bundle_dir.glob("dmg/CutAI_*.dmg"),
    key=lambda path: (path.stat().st_mtime, path.name),
    reverse=True,
)
if candidates:
    print(candidates[0])
PY
}

cutai_prepare_stage_dir() {
  local stage_dir="${1:-}"

  if [[ -n "$stage_dir" ]]; then
    mkdir -p "$stage_dir"
    printf '%s\n' "$stage_dir"
    return 0
  fi

  mktemp -d "${TMPDIR:-/tmp}/cutai-macos-release.XXXXXX"
}

cutai_stage_artifact() {
  local source_path="${1:?source path required}"
  local destination_path="${2:?destination path required}"

  rm -rf "$destination_path"

  if [[ -d "$source_path" ]]; then
    ditto "$source_path" "$destination_path"
  else
    cp -f "$source_path" "$destination_path"
  fi
}
