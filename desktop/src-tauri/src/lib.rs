use serde::Serialize;
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
        cmd.args(["-m", "cutai.cli", "server", "--host", BACKEND_HOST, "--port"])
            .arg(BACKEND_PORT.to_string());
        attempts.push(cmd);
    }

    for python in ["python3", "python"] {
        let mut cmd = Command::new(python);
        cmd.args(["-m", "cutai.cli", "server", "--host", BACKEND_HOST, "--port"])
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
            return Err(format!("CutAI backend exited before startup completed ({status})"));
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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(BackendState::default())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![start_backend])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| {
            if let tauri::RunEvent::Exit = event {
                stop_backend_process(app);
            }
        });
}
