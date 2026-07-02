//! Window management — create/show translation popup and settings windows.

use tauri::{AppHandle, Manager, WebviewUrl, WebviewWindowBuilder};

// ── Translation popup ─────────────────────────────────────────────────────────

/// Create and show the translation popup near the cursor.
/// `original`: captured text (may be truncated in HTML layer)
/// `target_language`: shown in the popup header
/// `cursor_x`, `cursor_y`: current cursor position in screen coordinates
///
/// If original is empty, does nothing.
pub fn show_translate_popup(
    app: &AppHandle,
    original: &str,
    target_language: &str,
    cursor_x: f64,
    cursor_y: f64,
) -> Result<(), String> {
    if original.trim().is_empty() {
        return Ok(());
    }

    // Close any existing popup before opening a new one
    if let Some(existing) = app.get_webview_window("translate-popup") {
        let _ = existing.close();
    }

    let popup_w: f64 = 460.0;
    let popup_h: f64 = 220.0;
    let offset_x: f64 = 16.0;
    let offset_y: f64 = 16.0;

    // Default screen bounds fallback (clamp conservatively)
    // We can't easily query monitor size without a window in Tauri 2 setup phase,
    // so we use a safe default; the cursor position is trusted to be on-screen already.
    let screen_w: f64 = 3840.0; // supports up to 4K — rdev coords are real screen pixels
    let screen_h: f64 = 2160.0;

    let mut x = cursor_x + offset_x;
    let mut y = cursor_y + offset_y;

    if x + popup_w > screen_w {
        x = screen_w - popup_w - 10.0;
    }
    if y + popup_h > screen_h {
        y = screen_h - popup_h - 10.0;
    }
    if x < 0.0 {
        x = 10.0;
    }
    if y < 0.0 {
        y = 10.0;
    }

    // URL-encode the init parameters to pass via query string
    let orig_encoded = url_encode(original);
    let lang_encoded = url_encode(target_language);

    let url = format!(
        "popup.html?original={}&lang={}",
        orig_encoded, lang_encoded
    );

    WebviewWindowBuilder::new(app, "translate-popup", WebviewUrl::App(url.into()))
        .title("Quick Translator")
        .inner_size(popup_w, popup_h)
        .position(x, y)
        .decorations(false)
        .always_on_top(true)
        .skip_taskbar(true)
        .resizable(false)
        .visible(true)
        .build()
        .map_err(|e| format!("failed to create popup: {e}"))?;

    Ok(())
}

// ── Settings window ───────────────────────────────────────────────────────────

/// Create or focus the Settings window.
pub fn show_settings_window(app: &AppHandle) -> Result<(), String> {
    // If already open, just focus
    if let Some(w) = app.get_webview_window("settings") {
        let _ = w.show();
        let _ = w.set_focus();
        return Ok(());
    }

    WebviewWindowBuilder::new(app, "settings", WebviewUrl::App("settings.html".into()))
        .title("Quick Translator — Settings")
        .inner_size(520.0, 420.0)
        .decorations(true)
        .always_on_top(false)
        .resizable(false)
        .visible(true)
        .build()
        .map_err(|e| format!("failed to create settings window: {e}"))?;

    Ok(())
}

// ── URL encoding helper ───────────────────────────────────────────────────────

fn url_encode(s: &str) -> String {
    let mut encoded = String::new();
    for b in s.as_bytes() {
        match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                encoded.push(*b as char);
            }
            b' ' => encoded.push('+'),
            _ => {
                encoded.push('%');
                encoded.push_str(&format!("{:02X}", b));
            }
        }
    }
    encoded
}
