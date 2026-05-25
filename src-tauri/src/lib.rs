// Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
// Licensed under the Business Source License 1.1 (BUSL-1.1).

use std::process::Child;
use std::sync::Mutex;
use tauri::State;

/// Holds the Python backend process so we can kill it on exit.
pub struct PythonBackend(pub Mutex<Option<Child>>);

/// Kill the backend process cleanly.
pub fn kill_backend(backend: &State<PythonBackend>) {
    if let Ok(mut guard) = backend.0.lock() {
        if let Some(mut child) = guard.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

/// Tauri command — frontend polls this to know if the backend is alive.
#[tauri::command]
pub fn backend_status(backend: State<PythonBackend>) -> String {
    let guard = backend.0.lock().unwrap();
    if guard.is_some() {
        "running".to_string()
    } else {
        "stopped".to_string()
    }
}
