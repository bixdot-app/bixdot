// Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
// Licensed under the Business Source License 1.1 (BUSL-1.1).

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::Command;
use std::sync::Mutex;
use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Manager, RunEvent, WindowEvent,
};
use bixdot_lib::{kill_backend, PythonBackend};

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(PythonBackend(Mutex::new(None)))
        .setup(|app| {
            // ── 1. Check dependencies ─────────────────────────────────────
            let python = find_python();
            let app_dir = find_app_dir();

            // Decide which page to show
            let start_url = if python.is_none() {
                // No Python found — show setup guide
                "setup.html".to_string()
            } else {
                // Python found — try to start the backend
                let py = python.unwrap();
                println!("[BixDot] Starting backend: {py} -m core.main in {app_dir:?}");

                match Command::new(&py)
                    .args(["-m", "core.main"])
                    .current_dir(&app_dir)
                    .spawn()
                {
                    Ok(child) => {
                        *app.state::<PythonBackend>().0.lock().unwrap() = Some(child);
                        "loading.html".to_string() // loading screen polls health
                    }
                    Err(e) => {
                        eprintln!("[BixDot] Failed to start backend: {e}");
                        "setup.html".to_string()
                    }
                }
            };

            // ── 2. Navigate to correct start page ─────────────────────────
            if let Some(window) = app.get_webview_window("main") {
                let url = format!("tauri://localhost/{}", start_url);
                let _ = window.navigate(url.parse().unwrap());
            }

            // ── 3. System tray ────────────────────────────────────────────
            let open_item = MenuItem::with_id(app, "open", "Open BixDot", true, None::<&str>)?;
            let quit_item = MenuItem::with_id(app, "quit", "Quit",        true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&open_item, &quit_item])?;

            let _tray = TrayIconBuilder::new()
                .menu(&menu)
                .tooltip("BixDot — Local AI Agent")
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "open" => show_window(app),
                    "quit" => {
                        kill_backend(&app.state::<PythonBackend>());
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
        .invoke_handler(tauri::generate_handler![bixdot_lib::backend_status])
        .build(tauri::generate_context!())
        .expect("Error building BixDot")
        .run(|app, event| match event {
            // Close button → hide to tray
            RunEvent::WindowEvent {
                label,
                event: WindowEvent::CloseRequested { api, .. },
                ..
            } if label == "main" => {
                api.prevent_close();
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.hide();
                }
            }
            // App quit → kill Python
            RunEvent::Exit => {
                kill_backend(&app.state::<PythonBackend>());
            }
            _ => {}
        });
}

fn show_window(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.set_focus();
    }
}

fn find_app_dir() -> std::path::PathBuf {
    let cwd = std::env::current_dir().unwrap_or_default();
    if cwd.join("core").exists() { return cwd; }

    if let Ok(exe) = std::env::current_exe() {
        let exe_dir = exe.parent().unwrap_or(&exe).to_path_buf();
        if exe_dir.join("core").exists() { return exe_dir.clone(); }
        if let Some(p) = exe_dir.parent() {
            if p.join("core").exists() { return p.to_path_buf(); }
        }
    }
    cwd
}

/// Returns Some("python") / Some("python3") if found, None if not installed.
fn find_python() -> Option<String> {
    for candidate in &["python3", "python", "py"] {
        if let Ok(out) = Command::new(candidate).arg("--version").output() {
            if out.status.success() {
                let ver = String::from_utf8_lossy(&out.stdout).to_string()
                    + &String::from_utf8_lossy(&out.stderr);
                // Require 3.11+
                if ver.contains("3.11") || ver.contains("3.12") || ver.contains("3.13") {
                    return Some(candidate.to_string());
                }
            }
        }
    }
    None
}
