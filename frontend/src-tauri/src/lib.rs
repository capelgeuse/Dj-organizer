#![cfg_attr(mobile, tauri::mobile_entry_point)]

use std::env;
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::Mutex;

#[cfg(windows)]
use std::os::windows::process::CommandExt;
use tauri::{AppHandle, Manager, State, WindowEvent};

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x08000000;

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

    fn packaged_executable(app: &AppHandle) -> Result<PathBuf, String> {
        if let Ok(value) = env::var("CAPELHOUSE_BACKEND_EXE") {
            return Ok(PathBuf::from(value));
        }

        let resource_dir = app
            .path()
            .resource_dir()
            .map_err(|error| error.to_string())?;
        let executable_dir = env::current_exe()
            .ok()
            .and_then(|path| path.parent().map(ToOwned::to_owned));
        let target = env::var("TAURI_TARGET_TRIPLE")
            .unwrap_or_else(|_| "x86_64-pc-windows-msvc".to_string());
        let target_name = format!("backend_bridge-{target}.exe");

        let mut candidates = vec![
            resource_dir.join("binaries").join(&target_name),
            resource_dir.join(&target_name),
            resource_dir.join("backend_bridge.exe"),
        ];
        if let Some(directory) = executable_dir {
            candidates.push(directory.join("binaries").join(&target_name));
            candidates.push(directory.join(&target_name));
            candidates.push(directory.join("backend_bridge.exe"));
        }

        candidates
            .into_iter()
            .find(|candidate| candidate.is_file())
            .ok_or_else(|| "Packaged Python sidecar was not found beside the app or in Tauri resources.".to_string())
    }

    fn spawn(app: &AppHandle) -> Result<BridgeProcess, String> {
        let mut command = if cfg!(debug_assertions) {
            let root = Self::process_root()?;
            let python = env::var("CAPELHOUSE_PYTHON").unwrap_or_else(|_| {
                if cfg!(windows) {
                    "python".to_string()
                } else {
                    "python3".to_string()
                }
            });
            let mut command = Command::new(python);
            command
                .args(["-m", "bridge.local_bridge"])
                .current_dir(root);
            command
        } else {
            Command::new(Self::packaged_executable(app)?)
        };

        #[cfg(windows)]
        if !cfg!(debug_assertions) {
            command.creation_flags(CREATE_NO_WINDOW);
        }

        command
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit());
        let mut child = command
            .spawn()
            .map_err(|error| format!("Could not start Python bridge: {error}"))?;
        let stdin = child
            .stdin
            .take()
            .ok_or_else(|| "Python bridge stdin was unavailable.".to_string())?;
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| "Python bridge stdout was unavailable.".to_string())?;
        Ok(BridgeProcess {
            child,
            stdin,
            stdout: BufReader::new(stdout),
        })
    }

    fn request(&self, app: &AppHandle, request: String) -> Result<String, String> {
        let mut guard = self
            .0
            .lock()
            .map_err(|_| "Bridge state lock was poisoned.".to_string())?;
        if guard.is_none() {
            *guard = Some(Self::spawn(app)?);
        }
        let process = guard
            .as_mut()
            .ok_or_else(|| "Bridge process was not created.".to_string())?;
        process
            .stdin
            .write_all(request.as_bytes())
            .map_err(|error| error.to_string())?;
        process
            .stdin
            .write_all(b"\n")
            .map_err(|error| error.to_string())?;
        process.stdin.flush().map_err(|error| error.to_string())?;
        let mut response = String::new();
        if process
            .stdout
            .read_line(&mut response)
            .map_err(|error| error.to_string())?
            == 0
        {
            let _ = process.child.kill();
            let _ = process.child.wait();
            *guard = None;
            return Err("Python bridge exited before returning a response.".to_string());
        }
        Ok(response.trim_end().to_string())
    }

    fn shutdown(&self) {
        let Ok(mut guard) = self.0.lock() else { return };
        let Some(mut process) = guard.take() else {
            return;
        };
        let _ = process
            .stdin
            .write_all(b"{\"id\":\"tauri-shutdown\",\"command\":\"shutdown\",\"payload\":{}}\n");
        let _ = process.stdin.flush();
        let mut response = String::new();
        let _ = process.stdout.read_line(&mut response);
        let _ = process.child.kill();
        let _ = process.child.wait();
    }
}

#[tauri::command]
fn bridge_request(
    app: AppHandle,
    request: String,
    state: State<'_, BridgeState>,
) -> Result<String, String> {
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
