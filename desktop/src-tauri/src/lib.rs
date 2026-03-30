use serde::{Deserialize, Serialize};
use std::fs;
use std::env;
use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::Duration;
use tauri::{Manager, State};

const BACKEND_HOST: &str = "127.0.0.1";
const BACKEND_PORT: u16 = 18910;

struct BackendState {
    child: Mutex<Option<Child>>,
}

impl Default for BackendState {
    fn default() -> Self {
        Self {
            child: Mutex::new(None),
        }
    }
}

#[derive(Serialize)]
struct BackendStartResponse {
    started: bool,
    already_running: bool,
    port: u16,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct SaveExportRequest {
    source_path: String,
    default_file_name: String,
}

fn backend_addr() -> SocketAddr {
    format!("{BACKEND_HOST}:{BACKEND_PORT}")
        .parse()
        .expect("valid backend address")
}

fn is_backend_online() -> bool {
    TcpStream::connect_timeout(&backend_addr(), Duration::from_millis(250)).is_ok()
}

fn workspace_root() -> Option<PathBuf> {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(Path::parent)
        .map(Path::to_path_buf)
}

fn spawn_backend_command() -> Result<Child, String> {
    let root = workspace_root().ok_or("Failed to locate workspace root")?;

    let mut attempts: Vec<Command> = Vec::new();

    if let Ok(python) = env::var("CUTAI_DESKTOP_PYTHON") {
        let mut cmd = Command::new(python);
        cmd.args([
            "-m",
            "cutai.cli",
            "server",
            "--host",
            BACKEND_HOST,
            "--port",
        ])
        .arg(BACKEND_PORT.to_string());
        attempts.push(cmd);
    }

    for venv_python in [
        root.join(".venv313/bin/python"),
        root.join(".venv/bin/python"),
    ] {
        if venv_python.exists() {
            let mut cmd = Command::new(venv_python);
            cmd.args([
                "-m",
                "cutai.cli",
                "server",
                "--host",
                BACKEND_HOST,
                "--port",
            ])
            .arg(BACKEND_PORT.to_string());
            attempts.push(cmd);
        }
    }

    for python in ["python3", "python"] {
        let mut cmd = Command::new(python);
        cmd.args([
            "-m",
            "cutai.cli",
            "server",
            "--host",
            BACKEND_HOST,
            "--port",
        ])
        .arg(BACKEND_PORT.to_string());
        attempts.push(cmd);
    }

    let mut cutai_cmd = Command::new("cutai");
    cutai_cmd
        .args(["server", "--host", BACKEND_HOST, "--port"])
        .arg(BACKEND_PORT.to_string());
    attempts.push(cutai_cmd);

    let mut last_error = String::from("No backend launch command attempted");

    for mut command in attempts {
        command
            .current_dir(&root)
            .stdout(Stdio::null())
            .stderr(Stdio::null());

        match command.spawn() {
            Ok(child) => return Ok(child),
            Err(err) => {
                last_error = err.to_string();
            }
        }
    }

    Err(format!(
        "Unable to launch CutAI backend. Set CUTAI_DESKTOP_PYTHON if needed. Last error: {last_error}"
    ))
}

#[tauri::command]
fn start_backend(state: State<'_, BackendState>) -> Result<BackendStartResponse, String> {
    if is_backend_online() {
        return Ok(BackendStartResponse {
            started: false,
            already_running: true,
            port: BACKEND_PORT,
        });
    }

    let mut child_slot = state
        .child
        .lock()
        .map_err(|_| "Failed to lock backend state".to_string())?;

    if let Some(child) = child_slot.as_mut() {
        match child.try_wait() {
            Ok(None) => {
                return Ok(BackendStartResponse {
                    started: false,
                    already_running: true,
                    port: BACKEND_PORT,
                });
            }
            Ok(Some(_)) | Err(_) => {
                *child_slot = None;
            }
        }
    }

    let mut child = spawn_backend_command()?;

    for _ in 0..30 {
        if is_backend_online() {
            *child_slot = Some(child);
            return Ok(BackendStartResponse {
                started: true,
                already_running: false,
                port: BACKEND_PORT,
            });
        }

        if let Ok(Some(status)) = child.try_wait() {
            return Err(format!(
                "CutAI backend exited before startup completed ({status})"
            ));
        }

        thread::sleep(Duration::from_millis(200));
    }

    let _ = child.kill();
    let _ = child.wait();
    Err(format!(
        "CutAI backend did not become ready on {BACKEND_HOST}:{BACKEND_PORT}"
    ))
}

fn stop_backend_process(app: &tauri::AppHandle) {
    if let Some(state) = app.try_state::<BackendState>() {
        if let Ok(mut child_slot) = state.child.lock() {
            if let Some(child) = child_slot.as_mut() {
                let _ = child.kill();
                let _ = child.wait();
            }
            *child_slot = None;
        }
    }
}

fn existing_path_or_ancestor(path: &Path) -> Option<PathBuf> {
    for candidate in path.ancestors() {
        if candidate.exists() {
            return Some(candidate.to_path_buf());
        }
    }

    None
}

fn open_with_command(program: &str, args: &[&str], target: &Path) -> Result<(), String> {
    let status = Command::new(program)
        .args(args)
        .arg(target)
        .status()
        .map_err(|err| format!("Failed to launch {program}: {err}"))?;

    if status.success() {
        Ok(())
    } else {
        Err(format!("{program} exited with status {status}"))
    }
}

#[tauri::command]
fn reveal_path(path: String) -> Result<(), String> {
    let requested = PathBuf::from(path.trim());
    if path.trim().is_empty() {
        return Err("Path is required".to_string());
    }

    let existing_target = existing_path_or_ancestor(&requested).ok_or_else(|| {
        format!(
            "Path does not exist and no parent directory was found: {}",
            requested.display()
        )
    })?;

    #[cfg(target_os = "macos")]
    {
        if requested.exists() && requested.is_file() {
            return open_with_command("open", &["-R"], &requested);
        }

        return open_with_command("open", &[], &existing_target);
    }

    #[cfg(target_os = "windows")]
    {
        if requested.exists() && !requested.is_dir() {
            let status = Command::new("explorer")
                .arg(format!("/select,{}", requested.display()))
                .status()
                .map_err(|err| format!("Failed to launch explorer: {err}"))?;

            if status.success() {
                return Ok(());
            }
        }

        return open_with_command("explorer", &[], &existing_target);
    }

    #[cfg(not(any(target_os = "macos", target_os = "windows")))]
    {
        open_with_command("xdg-open", &[], &existing_target)
    }
}

#[tauri::command]
fn save_exported_file(request: SaveExportRequest) -> Result<Option<String>, String> {
    let source_path = request.source_path.trim();
    if source_path.is_empty() {
        return Err("Source path is required".to_string());
    }

    let source = PathBuf::from(source_path);
    if !source.exists() {
        return Err(format!("Source file does not exist: {}", source.display()));
    }
    if !source.is_file() {
        return Err(format!("Source path is not a file: {}", source.display()));
    }

    let default_file_name = request.default_file_name.trim();
    if default_file_name.is_empty() {
        return Err("Default file name is required".to_string());
    }

    let destination = rfd::FileDialog::new()
        .set_file_name(default_file_name)
        .save_file();

    let Some(destination) = destination else {
        return Ok(None);
    };

    if destination == source {
        return Ok(Some(destination.display().to_string()));
    }

    fs::copy(&source, &destination).map_err(|err| {
        format!(
            "Failed to export file from {} to {}: {}",
            source.display(),
            destination.display(),
            err
        )
    })?;

    Ok(Some(destination.display().to_string()))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(BackendState::default())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            start_backend,
            reveal_path,
            save_exported_file
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| {
            if let tauri::RunEvent::Exit = event {
                stop_backend_process(app);
            }
        });
}
