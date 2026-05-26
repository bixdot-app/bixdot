// Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
// Licensed under the Business Source License 1.1 (BUSL-1.1).

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Manager, RunEvent, WindowEvent,
};

// ── State ─────────────────────────────────────────────────────────────────────

struct PythonBackend(Mutex<Option<Child>>);

fn kill_backend(guard: &Mutex<Option<Child>>) {
    if let Ok(mut lock) = guard.lock() {
        if let Some(mut child) = lock.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

// ── Tauri command ─────────────────────────────────────────────────────────────

#[tauri::command]
fn backend_status(backend: tauri::State<PythonBackend>) -> String {
    if backend.0.lock().map(|g| g.is_some()).unwrap_or(false) {
        "running".to_string()
    } else {
        "stopped".to_string()
    }
}

// ── Main ─────────────────────────────────────────────────────────────────────

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(PythonBackend(Mutex::new(None)))
        .setup(|app| {
            let python  = find_python();
            let app_dir = find_app_dir();

            // ── Start backend ─────────────────────────────────────────────
            if let Some(py) = python {
                println!("[BixDot] Starting backend: {py} -m core.main in {app_dir:?}");
                match Command::new(&py)
                    .args(["-m", "core.main"])
                    .current_dir(&app_dir)
                    .spawn()
                {
                    Ok(child) => {
                        *app.state::<PythonBackend>().0.lock().unwrap() = Some(child);
                        println!("[BixDot] Backend started — waiting for it to be ready...");
                        // Give the backend 2 seconds to start up before the window loads
                        std::thread::sleep(std::time::Duration::from_millis(2000));
                    }
                    Err(e) => eprintln!("[BixDot] Failed to start backend: {e}"),
                }
            } else {
                eprintln!("[BixDot] Python 3.11+ not found. Please install Python and Ollama.");
            }

            // ── Navigate window to backend ────────────────────────────────
            // Always point to http://localhost:8747 — the backend serves
            // the full frontend including setup/loading pages itself.
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.navigate("http://localhost:8747".parse().unwrap());
            }

            // ── System tray ───────────────────────────────────────────────
            let open_item = MenuItem::with_id(app, "open", "Open BixDot", true, None::<&str>)?;
            let quit_item = MenuItem::with_id(app, "quit", "Quit",        true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&open_item, &quit_item])?;

            let _tray = TrayIconBuilder::new()
                .menu(&menu)
                .tooltip("BixDot — Local AI Agent")
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "open" => show_window(app),
                    "quit" => {
                        kill_backend(&app.state::<PythonBackend>().0);
                        app.exit(0);
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event {
                        show_window(tray.app_handle());
                    }
                })
                .build(app)?;

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![backend_status])
        .build(tauri::generate_context!())
        .expect("Error building BixDot")
        .run(|app, event| match event {
            RunEvent::WindowEvent {
                label,
                event: WindowEvent::CloseRequested { api, .. },
                ..
            } if label == "main" => {
                api.prevent_close();
                if let Some(w) = app.get_webview_window("main") {
                    let _ = w.hide();
                }
            }
            RunEvent::Exit => {
                kill_backend(&app.state::<PythonBackend>().0);
            }
            _ => {}
        });
}

fn show_window(app: &AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.show();
        let _ = w.set_focus();
    }
}

fn find_app_dir() -> std::path::PathBuf {
    let cwd = std::env::current_dir().unwrap_or_default();
    if cwd.join("core").exists() { return cwd; }
    if let Ok(exe) = std::env::current_exe() {
        let d = exe.parent().unwrap_or(&exe).to_path_buf();
        if d.join("core").exists() { return d.clone(); }
        if let Some(p) = d.parent() {
            if p.join("core").exists() { return p.to_path_buf(); }
        }
    }
    cwd
}

fn find_python() -> Option<String> {
    for candidate in &["python3", "python", "py"] {
        if let Ok(out) = Command::new(candidate).arg("--version").output() {
            if out.status.success() {
                let ver = String::from_utf8_lossy(&out.stdout).to_string()
                    + &String::from_utf8_lossy(&out.stderr);
                if ver.contains("3.11") || ver.contains("3.12") || ver.contains("3.13") {
                    return Some(candidate.to_string());
                }
            }
        }
    }
    None
}
