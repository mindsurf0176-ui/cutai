# CutAI macOS external-alpha release

This guide is the practical release path for getting the Tauri desktop app from **internal alpha** to a macOS build that is credible for external testers.

## Goal

Ship a DMG that passes the important trust checks:

- app bundle signed with **Developer ID Application**
- DMG signed
- DMG notarized
- app + DMG stapled
- Gatekeeper assessment captured before sharing

## Current repo status

What already existed before this pass:

- `pnpm tauri build` already produces a `.app` and `.dmg`
- the generated DMG build script supports DMG signing/notarization hooks internally
- the current built app on this machine was only **ad-hoc signed**
- the current built DMG on this machine was **unsigned**

What was missing and is now covered in-repo:

- a reproducible build script for the macOS release bundle
- a dedicated signing + notarization helper
- a dedicated verification helper for codesign / Gatekeeper / stapler checks
- one place documenting the exact release order and required env vars

## Required Apple-side setup

You still need real Apple release credentials outside the repo:

1. **Developer ID Application certificate** installed in Keychain Access
2. Apple team membership that allows notarization
3. a `notarytool` keychain profile

Recommended one-time setup:

```bash
xcrun notarytool store-credentials "cutai-notary" \
  --apple-id "YOUR_APPLE_ID" \
  --team-id "YOUR_TEAM_ID" \
  --password "YOUR_APP_SPECIFIC_PASSWORD"
```

Then export:

```bash
export APPLE_IDENTITY="Developer ID Application: YOUR NAME (TEAMID)"
export APPLE_TEAM_ID="TEAMID"
export APPLE_NOTARY_PROFILE="cutai-notary"
```

## Release scripts

All helpers live in `desktop/scripts/`.

### 1) Build release bundle

```bash
cd desktop
./scripts/release-macos-build.sh
```

This runs `pnpm tauri build` and prints the app/DMG paths plus current signature state.

### 2) Sign + notarize + staple

```bash
cd desktop
APPLE_IDENTITY="$APPLE_IDENTITY" \
APPLE_TEAM_ID="$APPLE_TEAM_ID" \
APPLE_NOTARY_PROFILE="$APPLE_NOTARY_PROFILE" \
./scripts/notarize-macos-release.sh
```

Useful modes:

```bash
# show exact commands without executing them
DRY_RUN=1 APPLE_IDENTITY="$APPLE_IDENTITY" APPLE_NOTARY_PROFILE="$APPLE_NOTARY_PROFILE" ./scripts/notarize-macos-release.sh

# sign only, skip notary submit/staple
SKIP_NOTARY=1 APPLE_IDENTITY="$APPLE_IDENTITY" ./scripts/notarize-macos-release.sh
```

### 3) Verify release artifacts

```bash
cd desktop
./scripts/verify-macos-release.sh
```

For a fully notarized candidate, require stapler validation too:

```bash
EXPECT_NOTARIZED=1 ./scripts/verify-macos-release.sh
```

## End-to-end release flow

Use this exact order:

```bash
cd /path/to/cutai/desktop
export APPLE_IDENTITY="Developer ID Application: YOUR NAME (TEAMID)"
export APPLE_TEAM_ID="TEAMID"
export APPLE_NOTARY_PROFILE="cutai-notary"

./scripts/release-macos-build.sh
./scripts/notarize-macos-release.sh
EXPECT_NOTARIZED=1 ./scripts/verify-macos-release.sh
```

## What the verification should prove

### App signing

Expected:

- `codesign --display --verbose=4` shows a real TeamIdentifier
- app is **not** ad-hoc signed
- `codesign --verify --deep --strict` succeeds

### DMG signing

Expected:

- `codesign --display --verbose=4` shows a signature instead of `not signed at all`
- `codesign --verify` succeeds

### Gatekeeper

Expected:

- `/usr/sbin/spctl --assess --type execute` succeeds for the app
- `/usr/sbin/spctl --assess --type open` succeeds for the DMG

### Notarization / stapling

Expected:

- `xcrun notarytool submit ... --wait` succeeds
- `xcrun stapler validate` succeeds for both the `.app` and `.dmg`

## Known blocker that remains outside the repo

The repo is now set up for the flow, but this machine still needs:

- real Developer ID certificate access
- real notarytool credentials/profile
- one successful credential-backed notarization run and captured verification output

Without those, we can only get to **release-process ready**, not fully **external-alpha trusted**.

## Suggested release evidence to save

Before sharing the DMG externally, save terminal output for:

```bash
./scripts/release-macos-build.sh
./scripts/notarize-macos-release.sh
EXPECT_NOTARIZED=1 ./scripts/verify-macos-release.sh
```

That output becomes the release trust record for the external alpha drop.
