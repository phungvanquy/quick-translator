// Prevent a console window on Windows
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod api;
mod clipboard;
mod config;
mod hotkey;
mod windows;

use std::sync::Mutex;

use config::{Config, ConfigState, ConfigUpdate};
use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    AppHandle, Manager,
};

// ── Shared cursor position ────────────────────────────────────────────────────
// Updated by the rdev listener; read when opening the popup.
lazy_static::lazy_static! {
    pub static ref LAST_CURSOR_POS: Mutex<(f64, f64)> = Mutex::new((100.0, 100.0));
}

// ── Tauri commands ────────────────────────────────────────────────────────────

/// Return the current config to the Settings UI.
#[tauri::command]
fn get_config(state: tauri::State<'_, ConfigState>) -> Config {
    state.get()
}

/// Save updated config fields from the Settings UI.
#[tauri::command]
fn update_config(
    state: tauri::State<'_, ConfigState>,
    update: ConfigUpdate,
) -> Result<(), String> {
    state.update(update)
}

/// Open (or focus) the settings window.
#[tauri::command]
fn open_settings_cmd(app: AppHandle) -> Result<(), String> {
    windows::show_settings_window(&app)
}

// ── Translate trigger ─────────────────────────────────────────────────────────

/// Called from hotkey.rs via tauri::async_runtime when Ctrl+C+C fires.
pub async fn handle_translate_trigger(app: AppHandle) {
    // Clipboard polling blocks for up to 500ms — run on a blocking thread
    let text = tokio::task::spawn_blocking(clipboard::get_clipboard_after_copy)
        .await
        .unwrap_or_default();

    if text.trim().is_empty() {
        return;
    }

    let cfg = app.state::<ConfigState>().get();

    let (cx, cy) = *LAST_CURSOR_POS.lock().unwrap();

    // Create the popup window
    if let Err(e) = windows::show_translate_popup(&app, &text, &cfg.target_language, cx, cy) {
        eprintln!("popup error: {e}");
        return;
    }

    // Give the webview time to initialise before streaming
    tokio::time::sleep(std::time::Duration::from_millis(300)).await;

    let popup_window = match app.get_webview_window("translate-popup") {
        Some(w) => w,
        None => return,
    };

    api::translate_stream(text, cfg, popup_window).await;
}

// ── Entry point ───────────────────────────────────────────────────────────────

fn main() {
    let cfg = config::load();

    tauri::Builder::default()
        .manage(ConfigState::new(cfg.clone()))
        .setup(move |app| {
            // ── Tray menu ──────────────────────────────────────────────────────
            let menu = Menu::new(app.handle())?;

            let settings_item = MenuItem::with_id(
                app.handle(),
                "settings",
                "Settings",
                true,
                None::<&str>,
            )?;
            let quit_item = MenuItem::with_id(
                app.handle(),
                "quit",
                "Quit",
                true,
                None::<&str>,
            )?;

            menu.append(&settings_item)?;
            menu.append(&quit_item)?;

            // ── Tray icon ──────────────────────────────────────────────────────
            let icon = app
                .default_window_icon()
                .cloned()
                .unwrap_or_else(|| {
                    // Fallback: 16×16 solid white RGBA square
                    let rgba = vec![0xffu8; 16 * 16 * 4];
                    tauri::image::Image::new_owned(rgba, 16, 16)
                });

            TrayIconBuilder::new()
                .menu(&menu)
                .icon(icon)
                .tooltip("Quick Translator")
                .on_menu_event(|app, event| match event.id().as_ref() {
                    "settings" => {
                        if let Err(e) = windows::show_settings_window(app) {
                            eprintln!("settings window error: {e}");
                        }
                    }
                    "quit" => {
                        // Signal hotkey thread to stop (best-effort) then exit
                        app.exit(0);
                    }
                    _ => {}
                })
                .build(app.handle())?;

            // ── First-run: open settings if no API key ─────────────────────────
            let api_key_empty = app
                .state::<ConfigState>()
                .get()
                .api_key
                .trim()
                .is_empty();

            if api_key_empty {
                let app_handle = app.handle().clone();
                tauri::async_runtime::spawn(async move {
                    tokio::time::sleep(std::time::Duration::from_millis(600)).await;
                    if let Err(e) = windows::show_settings_window(&app_handle) {
                        eprintln!("first-run settings error: {e}");
                    }
                });
            }

            // ── Spawn combined rdev listener (hotkeys + cursor tracking) ───────
            let app_handle = app.handle().clone();
            hotkey::spawn_hotkey_listener(app_handle);

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_config,
            update_config,
            open_settings_cmd
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
