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
            let app_dir = find_app_dir();

            // ── Start backend ─────────────────────────────────────────────
            // Prefer sidecar bixdot-backend (Tauri externalBin, resolved via
            // resource path) over system Python.
            let sidecar_path = app.path().resource_dir().ok().and_then(|dir| {
                let name = if cfg!(windows) { "bixdot-backend.exe" } else { "bixdot-backend" };
                // Tauri places externalBin in <resource_dir>/../
                let candidate = dir.join("..").join(name);
                if candidate.exists() { return Some(candidate); }
                // Fallback: same dir as the Tauri exe (dev / flat layout)
                if let Ok(exe) = std::env::current_exe() {
                    let d = exe.parent().unwrap_or_else(|| std::path::Path::new("."));
                    let c = d.join(name);
                    if c.exists() { return Some(c); }
                }
                None
            });
            let started = if let Some(backend_exe) = sidecar_path {
                println!("[BixDot] Starting bundled backend: {:?}", backend_exe);
                match Command::new(&backend_exe).spawn() {
                    Ok(child) => {
                        *app.state::<PythonBackend>().0.lock().unwrap() = Some(child);
                        true
                    }
                    Err(e) => {
                        eprintln!("[BixDot] Bundled backend failed to start: {e}");
                        false
                    }
                }
            } else if let Some(py) = find_python() {
                println!("[BixDot] Starting backend: {py} -m core.main in {app_dir:?}");
                match Command::new(&py)
                    .args(["-m", "core.main"])
                    .current_dir(&app_dir)
                    .spawn()
                {
                    Ok(child) => {
                        *app.state::<PythonBackend>().0.lock().unwrap() = Some(child);
                        true
                    }
                    Err(e) => {
                        eprintln!("[BixDot] Failed to start backend: {e}");
                        false
                    }
                }
            } else {
                eprintln!("[BixDot] No bundled backend or Python 3.11+ found. Install Python from https://python.org");
                false
            };

            if started {
                println!("[BixDot] Backend started — waiting for it to be ready...");
                // Give the backend 2 seconds to start up before the window loads
                std::thread::sleep(std::time::Duration::from_millis(2000));
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

            let tray_icon = app.default_window_icon().cloned();
            let mut tray_builder = TrayIconBuilder::new()
                .menu(&menu)
                .tooltip("BixDot — Local AI Agent");
            if let Some(icon) = tray_icon {
                tray_builder = tray_builder.icon(icon);
            }
            let _tray = tray_builder
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
