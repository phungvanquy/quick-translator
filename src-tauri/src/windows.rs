//! Window management — create/show translation popup and settings windows.

use tauri::{AppHandle, Manager, PhysicalPosition, WebviewUrl, WebviewWindowBuilder};

// ── Translation popup ─────────────────────────────────────────────────────────

/// Create and show the translation popup near the cursor.
/// `original`: captured text (may be truncated in HTML layer)
/// `target_language`: shown in the popup header
/// `cursor_x`, `cursor_y`: current cursor position in PHYSICAL screen pixels
///   (rdev reports physical pixels; Tauri's builder `position()` expects logical
///   pixels, so we instead build the window hidden and position it afterwards
///   with `set_position(PhysicalPosition)` — correct on any DPI scale).
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

    // URL-encode the init parameters to pass via query string
    let orig_encoded = url_encode(original);
    let lang_encoded = url_encode(target_language);

    let url = format!("popup.html?original={}&lang={}", orig_encoded, lang_encoded);

    // Build hidden so we can position by physical pixels before the first paint,
    // avoiding a flash at the wrong spot on high-DPI displays.
    let window = WebviewWindowBuilder::new(app, "translate-popup", WebviewUrl::App(url.into()))
        .title("Quick Translator")
        .inner_size(popup_w, popup_h)
        .decorations(false)
        .always_on_top(true)
        .skip_taskbar(true)
        .resizable(false)
        .focused(true)
        .visible(false)
        .build()
        .map_err(|e| format!("failed to create popup: {e}"))?;

    // Anchor the popup to the cursor, clamped to the monitor under the cursor.
    // rdev gives physical pixels and set_position takes physical pixels, so all
    // math here is in physical space — no logical/physical mismatch, DPI-safe.
    // Scale comes from the cursor's monitor (correct on mixed-DPI multi-monitor).
    let cursor_monitor = window.monitor_from_point(cursor_x, cursor_y).ok().flatten();
    let scale = cursor_monitor
        .as_ref()
        .map(|m| m.scale_factor())
        .unwrap_or_else(|| window.scale_factor().unwrap_or(1.0));

    let popup_pw = popup_w * scale;
    let popup_ph = popup_h * scale;
    let offset = 16.0 * scale;

    let mut x = cursor_x + offset;
    let mut y = cursor_y + offset;

    if let Some(monitor) = cursor_monitor {
        let m_pos = monitor.position();
        let m_size = monitor.size();
        let left = m_pos.x as f64;
        let top = m_pos.y as f64;
        let right = left + m_size.width as f64;
        let bottom = top + m_size.height as f64;

        if x + popup_pw > right {
            x = right - popup_pw - 10.0 * scale;
        }
        if y + popup_ph > bottom {
            y = bottom - popup_ph - 10.0 * scale;
        }
        if x < left {
            x = left + 10.0 * scale;
        }
        if y < top {
            y = top + 10.0 * scale;
        }
    }

    let _ = window.set_position(PhysicalPosition::new(x, y));
    let _ = window.show();
    let _ = window.set_focus();

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
