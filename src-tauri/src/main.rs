// Prevent a console window on Windows
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod api;
mod clipboard;
mod config;
mod hotkey;
mod screenshot;
mod tts;
mod windows;

use arc_swap::ArcSwap;
use config::{Config, ConfigState, ConfigUpdate};
use hotkey::ParsedHotkeys;
use std::sync::Arc;
use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    AppHandle, Listener, Manager,
};

// ── Tauri commands ────────────────────────────────────────────────────────────

/// Return the current config to the Settings UI.
#[tauri::command]
fn get_config(state: tauri::State<'_, ConfigState>) -> Config {
    state.get()
}

/// Save updated config fields from the Settings UI.
#[tauri::command]
fn update_config(
    app: AppHandle,
    state: tauri::State<'_, ConfigState>,
    update: ConfigUpdate,
) -> Result<(), String> {
    state.update(update)?;
    // Hot-swap the parsed hotkey table
    let new_cfg = state.get();
    let parsed = ParsedHotkeys::from_config(&new_cfg.hotkeys);
    let hotkey_state = app.state::<Arc<ArcSwap<ParsedHotkeys>>>();
    hotkey_state.store(Arc::new(parsed));
    Ok(())
}

/// Open (or focus) the settings window.
#[tauri::command]
fn open_settings_cmd(app: AppHandle) -> Result<(), String> {
    windows::show_settings_window(&app)
}

/// Test the given endpoint/key/model with a minimal live request (Settings UI).
/// Takes current-form values so the user can test before saving.
#[tauri::command]
async fn test_connection(
    state: tauri::State<'_, api::HttpClient>,
    base_url: String,
    api_key: String,
    model: String,
) -> Result<String, String> {
    api::test_connection(&state.0, base_url, api_key, model).await
}

// ── Translate trigger ─────────────────────────────────────────────────────────

/// Called from hotkey.rs via tauri::async_runtime when Ctrl+C+C fires.
pub async fn handle_translate_trigger(app: AppHandle) {
    let (cx, cy) = hotkey::cursor_pos();
    let cfg = app.state::<ConfigState>().get();

    // Spawn clipboard polling on a blocking thread — runs concurrently with
    // the ready-listener setup below. The window needs the text for its query
    // string, so we await clipboard before building, but the spawn starts the
    // work immediately rather than blocking the async task.
    let clipboard_fut = tokio::task::spawn_blocking(clipboard::get_clipboard_after_copy);

    // Register the readiness listener BEFORE creating the popup, so we can't
    // miss the popup://ready event the webview emits once its listeners are up.
    let (ready_tx, ready_rx) = tokio::sync::oneshot::channel::<()>();
    let ready_tx = std::sync::Mutex::new(Some(ready_tx));
    let ready_handler = app.once_any("popup://ready", move |_event| {
        if let Some(tx) = ready_tx.lock().unwrap().take() {
            let _ = tx.send(());
        }
    });

    // Await clipboard result
    let text = clipboard_fut.await.unwrap_or_default();

    if text.trim().is_empty() {
        app.unlisten(ready_handler);
        return;
    }

    // Create the popup window
    if let Err(e) = windows::show_translate_popup(&app, &text, &cfg.target_language, cx, cy) {
        eprintln!("popup error: {e}");
        app.unlisten(ready_handler);
        return;
    }

    // Wait for the webview to signal it has attached its event listeners.
    let _ = tokio::time::timeout(std::time::Duration::from_millis(2000), ready_rx).await;
    app.unlisten(ready_handler);

    let popup_window = match app.get_webview_window("translate-popup") {
        Some(w) => w,
        None => return,
    };

    api::translate_stream(text, cfg, &app.state::<api::HttpClient>().0, popup_window).await;
}

// ── Chat trigger ────────────────────────────────────────────────────────────────

/// Called from hotkey.rs when Ctrl+C+Space fires.
/// Captures the selection, opens the chat popup (even for an empty selection —
/// that becomes free chat), and lets the frontend drive requests via chat_send.
pub async fn handle_chat_trigger(app: AppHandle) {
    let (cx, cy) = hotkey::cursor_pos();

    // Spawn clipboard polling immediately — runs while we prepare
    let clipboard_fut = tokio::task::spawn_blocking(clipboard::get_clipboard_after_copy);

    // Await clipboard (chat accepts empty — still opens in free-chat mode)
    let selected = clipboard_fut.await.unwrap_or_default();

    if let Err(e) = windows::show_chat_popup(&app, &selected, cx, cy) {
        eprintln!("chat popup error: {e}");
    }
}

// ── Chat command (frontend-driven) ────────────────────────────────────────────

/// Stream a chat response for the given question and prior history.
/// The frontend owns the conversation history and selected-text context; this
/// command assembles the request and streams chunks back to the chat window.
#[tauri::command]
async fn chat_send(
    app: AppHandle,
    selected_text: String,
    question: String,
    history: Vec<api::ChatMessage>,
) -> Result<(), String> {
    let cfg = app.state::<ConfigState>().get();
    let client = &app.state::<api::HttpClient>().0;
    let window = app
        .get_webview_window("chat-popup")
        .ok_or_else(|| "chat popup window not found".to_string())?;
    api::chat_stream(selected_text, question, history, cfg, client, window).await;
    Ok(())
}

// ── Screenshot trigger ───────────────────────────────────────────────────────

pub async fn handle_screenshot_trigger(app: AppHandle) {
    // Capture all monitors
    let captures = match screenshot::capture_all_monitors() {
        Ok(c) => c,
        Err(e) => {
            eprintln!("screenshot capture failed: {e}");
            return;
        }
    };

    if captures.is_empty() {
        eprintln!("no monitors captured");
        return;
    }

    // Encode previews for each monitor
    let previews: Vec<(screenshot::MonitorInfo, String)> = captures
        .iter()
        .map(|(info, img)| (info.clone(), screenshot::prepare_preview(img)))
        .collect();

    // Store full-res captures in state
    {
        let store = app.state::<screenshot::ScreenshotStore>();
        let mut guard = store.0.lock().unwrap();
        *guard = Some(screenshot::ScreenshotState::new(captures));
    }

    // Open overlay windows
    if let Err(e) = windows::show_overlay_windows(&app, &previews) {
        eprintln!("overlay window error: {e}");
        let store = app.state::<screenshot::ScreenshotStore>();
        let mut guard = store.0.lock().unwrap();
        *guard = None;
        return;
    }

    // Send preview to overlay after a short delay for webview init
    let app2 = app.clone();
    tauri::async_runtime::spawn(async move {
        tokio::time::sleep(std::time::Duration::from_millis(200)).await;
        for (i, (_info, preview)) in previews.iter().enumerate() {
            let label = format!("overlay-{i}");
            if let Some(w) = app2.get_webview_window(&label) {
                use tauri::Emitter;
                let _ = w.emit("overlay://preview", preview);
            }
        }
    });
}

// ── Overlay select handler ───────────────────────────────────────────────────

async fn handle_overlay_select(app: AppHandle, event: tauri::Event) {
    // Close overlay windows immediately
    windows::close_overlay_windows(&app);

    // Parse selection rect from event payload
    #[derive(serde::Deserialize)]
    struct SelectPayload {
        x: f64,
        y: f64,
        width: f64,
        height: f64,
        dpr: f64,
    }

    let payload: SelectPayload = match serde_json::from_str(event.payload()) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("overlay select parse error: {e}");
            return;
        }
    };

    // Convert CSS px to physical px
    let rect = screenshot::PhysicalRect {
        x: (payload.x * payload.dpr) as u32,
        y: (payload.y * payload.dpr) as u32,
        width: (payload.width * payload.dpr) as u32,
        height: (payload.height * payload.dpr) as u32,
    };

    // Crop from stored full-res capture (use first monitor for now)
    let data_url = {
        let store = app.state::<screenshot::ScreenshotStore>();
        let mut guard = store.0.lock().unwrap();
        let state = match guard.as_mut() {
            Some(s) => s,
            None => {
                eprintln!("no screenshot state available");
                return;
            }
        };

        // Crop from the first monitor's capture (overlay-0 is the focused one)
        let (_, ref img) = state.captures[0];
        let cropped = screenshot::crop_region(img, &rect);
        let url = screenshot::prepare_for_api(&cropped);
        state.prepared_image = Some(url.clone());
        url
    };

    // If chat popup is already open, attach image to it
    if let Some(chat_window) = app.get_webview_window("chat-popup") {
        use tauri::Emitter;
        let _ = chat_window.emit("chat://attach-image", &data_url);
    } else {
        // Open chat popup fresh (no text context, image will arrive via event)
        let (cx, cy) = hotkey::cursor_pos();
        if let Err(e) = windows::show_chat_popup(&app, "", cx, cy) {
            eprintln!("chat popup error: {e}");
            return;
        }
        // Give the webview a moment to set up listeners, then send the image
        let app2 = app.clone();
        tauri::async_runtime::spawn(async move {
            tokio::time::sleep(std::time::Duration::from_millis(300)).await;
            if let Some(w) = app2.get_webview_window("chat-popup") {
                use tauri::Emitter;
                let _ = w.emit("chat://attach-image", &data_url);
            }
        });
    }
}

// ── TTS commands ──────────────────────────────────────────────────────────────

#[tauri::command]
fn tts_speak(state: tauri::State<'_, tts::TtsHandle>, text: String) {
    state.speak(&text);
}

#[tauri::command]
fn tts_stop(state: tauri::State<'_, tts::TtsHandle>) {
    state.stop();
}

// ── Entry point ───────────────────────────────────────────────────────────────

fn main() {
    let cfg = config::load();
    let parsed_hotkeys = Arc::new(ArcSwap::from_pointee(
        ParsedHotkeys::from_config(&cfg.hotkeys),
    ));

    tauri::Builder::default()
        // Single instance MUST be the first plugin registered. A second launch
        // runs this callback in the primary instance instead of installing a
        // second global hook set (which would double-fire every hotkey).
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            // No main window to raise — surface Settings so the user sees the
            // app is already running.
            if let Err(e) = windows::show_settings_window(app) {
                eprintln!("single-instance settings error: {e}");
            }
        }))
        .manage(ConfigState::new(cfg.clone()))
        .manage(api::HttpClient::new())
        .manage(tts::TtsHandle::new())
        .manage(parsed_hotkeys.clone())
        .manage(screenshot::ScreenshotStore::new())
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

            // ── Overlay events (screenshot selection) ──────────────────────────
            let app_select = app.handle().clone();
            app.listen_any("overlay://select", move |event| {
                let app = app_select.clone();
                tauri::async_runtime::spawn(async move {
                    handle_overlay_select(app, event).await;
                });
            });

            let app_cancel = app.handle().clone();
            app.listen_any("overlay://cancel", move |_event| {
                windows::close_overlay_windows(&app_cancel);
                let store = app_cancel.state::<screenshot::ScreenshotStore>();
                let mut guard = store.0.lock().unwrap();
                *guard = None;
            });

            let app_closed = app.handle().clone();
            app.listen_any("chat://closed", move |_event| {
                let store = app_closed.state::<screenshot::ScreenshotStore>();
                let mut guard = store.0.lock().unwrap();
                *guard = None;
            });

            // ── Spawn combined rdev listener (hotkeys + cursor tracking) ───────
            let app_handle = app.handle().clone();
            hotkey::spawn_hotkey_listener(app_handle, parsed_hotkeys.clone());

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_config,
            update_config,
            open_settings_cmd,
            chat_send,
            test_connection,
            tts_speak,
            tts_stop
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|_app, event| {
            // Tray app: having no open windows is normal, so closing the last
            // popup/settings window must NOT quit the process. ExitRequested
            // fires with code == None on window-close (prevent it) and with
            // Some(_) only when we call app.exit() from the tray Quit item.
            if let tauri::RunEvent::ExitRequested { code, api, .. } = event {
                if code.is_none() {
                    api.prevent_exit();
                }
            }
        });
}
