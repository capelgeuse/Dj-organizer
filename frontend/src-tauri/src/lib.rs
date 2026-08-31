#![cfg_attr(mobile, tauri::mobile_entry_point)]

use std::env;
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::Mutex;

use tauri::{AppHandle, Manager, State, WindowEvent};

struct BridgeProcess {
    child: Child,
    stdin: ChildStdin,
    stdout: BufReader<ChildStdout>,
}

struct BridgeState(Mutex<Option<BridgeProcess>>);

impl Default for BridgeState {
    fn default() -> Self {
        Self(Mutex::new(None))
    }
}

impl BridgeState {
    fn process_root() -> Result<PathBuf, String> {
        if let Ok(value) = env::var("CAPELHOUSE_REPO_ROOT") {
            return Ok(PathBuf::from(value));
        }
        let mut current = env::current_dir().map_err(|error| error.to_string())?;
        loop {
            if current.join("bridge/local_bridge.py").is_file() {
                return Ok(current);
            }
            if !current.pop() {
                return env::current_dir().map_err(|error| error.to_string());
            }
        }
    }

    fn spawn(app: &AppHandle) -> Result<BridgeProcess, String> {
        let mut command = if cfg!(debug_assertions) {
            let root = Self::process_root()?;
            let python = env::var("CAPELHOUSE_PYTHON").unwrap_or_else(|_| "python".to_string());
            let mut command = Command::new(python);
            command.args(["-m", "bridge.local_bridge"]).current_dir(root);
            command
        } else {
            let executable = if let Ok(value) = env::var("CAPELHOUSE_BACKEND_EXE") {
                PathBuf::from(value)
            } else {
                let resource_dir = app.path().resource_dir().map_err(|error| error.to_string())?;
                let target = env::var("TAURI_TARGET_TRIPLE").unwrap_or_else(|_| "x86_64-pc-windows-msvc".to_string());
                let candidates = [
                    resource_dir.join("binaries").join(format!("backend_bridge-{target}.exe")),
                    resource_dir.join(format!("backend_bridge-{target}.exe")),
                    resource_dir.join("backend_bridge.exe"),
                ];
                candidates.into_iter().find(|candidate| candidate.is_file()).ok_or_else(|| "Packaged Python sidecar was not found in Tauri resources.".to_string())?
            };
            Command::new(executable)
        };
        command
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        let mut child = command.spawn().map_err(|error| format!("Could not start Python bridge: {error}"))?;
        let stdin = child.stdin.take().ok_or_else(|| "Python bridge stdin was unavailable.".to_string())?;
        let stdout = child.stdout.take().ok_or_else(|| "Python bridge stdout was unavailable.".to_string())?;
        Ok(BridgeProcess { child, stdin, stdout: BufReader::new(stdout) })
    }

    fn request(&self, app: &AppHandle, request: String) -> Result<String, String> {
        let mut guard = self.0.lock().map_err(|_| "Bridge state lock was poisoned.".to_string())?;
        if guard.is_none() {
            *guard = Some(Self::spawn(app)?);
        }
        let process = guard.as_mut().ok_or_else(|| "Bridge process was not created.".to_string())?;
        process.stdin.write_all(request.as_bytes()).map_err(|error| error.to_string())?;
        process.stdin.write_all(b"\n").map_err(|error| error.to_string())?;
        process.stdin.flush().map_err(|error| error.to_string())?;
        let mut response = String::new();
        if process.stdout.read_line(&mut response).map_err(|error| error.to_string())? == 0 {
            let _ = process.child.kill();
            let _ = process.child.wait();
            *guard = None;
            return Err("Python bridge exited before returning a response.".to_string());
        }
        Ok(response.trim_end().to_string())
    }

    fn shutdown(&self) {
        let Ok(mut guard) = self.0.lock() else { return };
        let Some(mut process) = guard.take() else { return };
        let _ = process.stdin.write_all(b"{\"id\":\"tauri-shutdown\",\"command\":\"shutdown\",\"payload\":{}}\n");
        let _ = process.stdin.flush();
        let mut response = String::new();
        let _ = process.stdout.read_line(&mut response);
        let _ = process.child.kill();
        let _ = process.child.wait();
    }
}

#[tauri::command]
fn bridge_request(app: AppHandle, request: String, state: State<'_, BridgeState>) -> Result<String, String> {
    state.request(&app, request)
}

#[tauri::command]
fn bridge_shutdown(state: State<'_, BridgeState>) -> Result<(), String> {
    state.shutdown();
    Ok(())
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(BridgeState::default())
        .invoke_handler(tauri::generate_handler![bridge_request, bridge_shutdown])
        .on_window_event(|window, event| {
            if matches!(event, WindowEvent::CloseRequested { .. }) {
                window.app_handle().state::<BridgeState>().shutdown();
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running CapelHouse");
}
