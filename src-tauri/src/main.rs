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
struct OllamaProcess(Mutex<Option<Child>>);

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

// ── Port probes ───────────────────────────────────────────────────────────────

fn port_open(port: u16) -> bool {
    std::net::TcpStream::connect_timeout(
        &format!("127.0.0.1:{port}").parse().unwrap(),
        std::time::Duration::from_millis(300),
    ).is_ok()
}

fn wait_for_backend(timeout_ms: u64) -> bool {
    let start = std::time::Instant::now();
    while start.elapsed().as_millis() < timeout_ms as u128 {
        if port_open(8747) {
            return true;
        }
        std::thread::sleep(std::time::Duration::from_millis(200));
    }
    false
}

// ── Process spawning helpers ──────────────────────────────────────────────────

fn spawn_hidden(mut cmd: Command) -> std::io::Result<Child> {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    cmd.spawn()
}

// ── Main ─────────────────────────────────────────────────────────────────────

fn main() {
    let context = tauri::generate_context!();

    // Auto-updater (v0.5): only active once a signing pubkey is configured in
    // tauri.conf.json → plugins.updater.pubkey. With no key the plugin is not
    // registered at all and the app behaves exactly as before — graceful.
    let updater_configured = context
        .config()
        .plugins
        .0
        .get("updater")
        .and_then(|v| v.get("pubkey"))
        .and_then(|v| v.as_str())
        .map(|s| !s.is_empty())
        .unwrap_or(false);

    let mut builder = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init());
    if updater_configured {
        builder = builder.plugin(tauri_plugin_updater::Builder::new().build());
    }

    builder
        .manage(PythonBackend(Mutex::new(None)))
        .manage(OllamaProcess(Mutex::new(None)))
        .setup(move |app| {
            let app_dir = find_app_dir();

            // ── Silent auto-update (non-technical users never reinstall) ──
            if updater_configured {
                let update_handle = app.handle().clone();
                tauri::async_runtime::spawn(async move {
                    use tauri_plugin_updater::UpdaterExt;
                    match update_handle.updater() {
                        Ok(updater) => match updater.check().await {
                            Ok(Some(update)) => {
                                println!("[BixDot] Update {} found — downloading…", update.version);
                                match update.download_and_install(|_, _| {}, || {}).await {
                                    Ok(_) => println!("[BixDot] Update installed — applies on next launch."),
                                    Err(e) => eprintln!("[BixDot] Update install failed: {e}"),
                                }
                            }
                            Ok(None) => println!("[BixDot] BixDot is up to date."),
                            Err(e) => eprintln!("[BixDot] Update check failed: {e}"),
                        },
                        Err(e) => eprintln!("[BixDot] Updater unavailable: {e}"),
                    }
                });
            }

            // Resolve sidecar path now (requires app.path() which is only in setup)
            let sidecar_path = app.path().resource_dir().ok().and_then(|dir| {
                let name = if cfg!(windows) { "bixdot-backend.exe" } else { "bixdot-backend" };
                let candidate = dir.join("..").join(name);
                if candidate.exists() { return Some(candidate); }
                if let Ok(exe) = std::env::current_exe() {
                    let d = exe.parent().unwrap_or_else(|| std::path::Path::new("."));
                    let c = d.join(name);
                    if c.exists() { return Some(c); }
                }
                None
            });

            // Window starts visible immediately showing loading.html (splash screen).
            // Background thread starts the backend, then navigates to the real URL.
            let watchdog_sidecar = sidecar_path.clone();
            let app_handle = app.handle().clone();
            std::thread::spawn(move || {
                // ── Start Ollama if not already running ───────────────────
                if port_open(11434) {
                    println!("[BixDot] Ollama already running.");
                } else {
                    println!("[BixDot] Ollama not detected — starting it...");
                    let mut ollama_cmd = Command::new("ollama");
                    ollama_cmd.arg("serve");
                    match spawn_hidden(ollama_cmd) {
                        Ok(child) => {
                            *app_handle.state::<OllamaProcess>().0.lock().unwrap() = Some(child);
                            std::thread::sleep(std::time::Duration::from_millis(2000));
                            println!("[BixDot] Ollama started.");
                        }
                        Err(e) => {
                            eprintln!("[BixDot] Could not start Ollama: {e}. Install from https://ollama.ai");
                        }
                    }
                }

                // ── Start backend (skip if already listening on 8747) ─────
                if port_open(8747) {
                    println!("[BixDot] Backend already running — skipping spawn.");
                } else {
                    let started = if let Some(ref backend_exe) = sidecar_path {
                        println!("[BixDot] Starting bundled backend: {:?}", backend_exe);
                        match spawn_hidden(Command::new(backend_exe)) {
                            Ok(child) => {
                                *app_handle.state::<PythonBackend>().0.lock().unwrap() = Some(child);
                                true
                            }
                            Err(e) => {
                                eprintln!("[BixDot] Bundled backend failed to start: {e}");
                                false
                            }
                        }
                    } else if let Some(py) = find_python() {
                        println!("[BixDot] Starting backend: {py} -m core.main in {app_dir:?}");
                        let mut cmd = Command::new(&py);
                        cmd.args(["-m", "core.main"]).current_dir(&app_dir);
                        match spawn_hidden(cmd) {
                            Ok(child) => {
                                *app_handle.state::<PythonBackend>().0.lock().unwrap() = Some(child);
                                true
                            }
                            Err(e) => {
                                eprintln!("[BixDot] Failed to start backend: {e}");
                                false
                            }
                        }
                    } else {
                        eprintln!("[BixDot] No bundled backend or Python 3.11+ found.");
                        false
                    };

                    if started {
                        println!("[BixDot] Waiting for backend on port 8747...");
                        if !wait_for_backend(30_000) {
                            eprintln!("[BixDot] Backend did not become ready within 30 s.");
                        } else {
                            println!("[BixDot] Backend ready.");
                        }
                    }
                }

                // ── Navigate window from splash to the real app ────────────
                if let Some(window) = app_handle.get_webview_window("main") {
                    let _ = window.navigate("http://localhost:8747".parse().unwrap());
                }
            });

            // ── Backend watchdog (v0.6.2) ─────────────────────────────────
            // A dead backend used to strand the window on "unable to reach
            // this page" until the user relaunched the whole app. If the
            // child we spawned exits, restart it. State None means we never
            // spawned it or the user quit — never respawn in those cases.
            let watchdog_handle = app.handle().clone();
            std::thread::spawn(move || {
                let mut restarts: u32 = 0;
                loop {
                    std::thread::sleep(std::time::Duration::from_secs(10));
                    let state = watchdog_handle.state::<PythonBackend>();
                    let mut guard = match state.0.lock() {
                        Ok(g) => g,
                        Err(_) => continue,
                    };
                    let died = match guard.as_mut() {
                        Some(child) => matches!(child.try_wait(), Ok(Some(_))),
                        None => false,
                    };
                    if died && !port_open(8747) {
                        restarts += 1;
                        if restarts > 20 {
                            eprintln!("[BixDot] Backend keeps dying — giving up after 20 restarts.");
                            *guard = None;
                            break;
                        }
                        eprintln!("[BixDot] Backend died — restarting it (attempt {restarts})...");
                        *guard = match watchdog_sidecar.as_ref() {
                            Some(exe) => spawn_hidden(Command::new(exe)).ok(),
                            None => None,
                        };
                    }
                }
            });

            // ── System tray (set up immediately — does not block) ─────────
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
        .build(context)
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
                kill_backend(&app.state::<OllamaProcess>().0);
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
