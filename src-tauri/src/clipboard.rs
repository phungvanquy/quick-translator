//! Clipboard capture — parity with get_clipboard_after_copy in main.py
//!
//! Polls up to 10× at 50ms for clipboard content to change from the
//! previously captured value. Returns the trimmed new value on change,
//! or the trimmed previous value as fallback.

use std::thread;
use std::time::Duration;

/// Capture clipboard text after a Ctrl+C copy.
///
/// Reads the clipboard before and after the copy event to detect the change.
/// Returns an empty string if the clipboard is inaccessible or has no text.
pub fn get_clipboard_after_copy() -> String {
    // arboard::Clipboard must be created on the calling thread.
    let mut clipboard = match arboard::Clipboard::new() {
        Ok(cb) => cb,
        Err(_) => return String::new(),
    };

    // Capture the "before" value
    let prev = clipboard.get_text().unwrap_or_default();

    // Poll up to 10× at 50ms
    for _ in 0..10 {
        thread::sleep(Duration::from_millis(50));
        let current = clipboard.get_text().unwrap_or_default();
        if !current.is_empty() && current != prev {
            return current.trim().to_string();
        }
    }

    // Fallback: return whatever was there before
    prev.trim().to_string()
}
