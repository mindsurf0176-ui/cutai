use std::env;
use std::fs;
use std::path::PathBuf;

use serde::Deserialize;

#[derive(Deserialize)]
struct BackendManifest {
    release_ready: bool,
    #[serde(default)]
    release_blockers: Vec<String>,
}

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-changed=../scripts/build-desktop-backend.sh");
    println!("cargo:rerun-if-changed=../../cutai");
    println!("cargo:rerun-if-changed=../../pyproject.toml");
    println!("cargo:rerun-if-env-changed=CUTAI_DESKTOP_SKIP_BACKEND_BUNDLE_CHECK");

    let profile = env::var("PROFILE").unwrap_or_default();
    let skip_check = env::var_os("CUTAI_DESKTOP_SKIP_BACKEND_BUNDLE_CHECK").is_some();

    if profile == "release" && !skip_check {
        let manifest_dir = PathBuf::from(env::var("CARGO_MANIFEST_DIR").expect("manifest dir"));
        let launcher = manifest_dir.join("gen/backend/run-backend.sh");
        let manifest_path = manifest_dir.join("gen/backend/manifest.json");
        if !launcher.exists() {
            panic!(
                "Bundled desktop backend is missing at {}. Run `pnpm backend:bundle` before release builds.",
                launcher.display()
            );
        }

        let manifest_bytes = fs::read(&manifest_path).unwrap_or_else(|err| {
            panic!(
                "Bundled desktop backend manifest is missing or unreadable at {}: {}",
                manifest_path.display(),
                err
            )
        });
        let manifest: BackendManifest =
            serde_json::from_slice(&manifest_bytes).unwrap_or_else(|err| {
                panic!(
                    "Bundled desktop backend manifest is invalid at {}: {}",
                    manifest_path.display(),
                    err
                )
            });

        if !manifest.release_ready {
            let blockers = if manifest.release_blockers.is_empty() {
                "No release blockers were recorded.".to_string()
            } else {
                manifest.release_blockers.join(" | ")
            };
            panic!(
                "Bundled desktop backend is not release-ready. {} Set CUTAI_DESKTOP_SKIP_BACKEND_BUNDLE_CHECK=1 only for local validation builds.",
                blockers
            );
        }
    }

    tauri_build::build()
}
