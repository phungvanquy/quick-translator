//! Global hotkey engine — parity with hotkeys.py
//!
//! Uses rdev::listen (passive, non-suppressing) to observe key events.
//! Implements the Ctrl+C+C double-tap state machine:
//!   - 0.6s arm window between first and second Ctrl+C
//!   - 0.4s debounce after trigger fires
//!   - Any non-modifier / non-combo key clears armed state
//!
//! Ctrl state is queried live (GetAsyncKeyState on Windows), mirroring the
//! Python `keyboard.is_pressed("ctrl")` approach — this avoids the desync bug
//! where a missed KeyRelease event would leave a tracked `ctrl_held` flag
//! stuck true (e.g. when focus moves to an elevated window mid-combo).
//!
//! Also tracks the cursor position via MouseMove events, storing it in
//! LAST_CURSOR_POS (in main.rs) for use when opening the popup.
//!
//! rdev::listen can only be called once per process — this single thread
//! handles both cursor tracking and hotkey detection.

use rdev::{listen, Event, EventType, Key};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tauri::AppHandle;

// ── Live Ctrl-key query ─────────────────────────────────────────────────────
// Parity with keyboard.is_pressed("ctrl"): read the real OS key state at the
// instant a key is pressed, instead of tracking press/release ourselves.

#[cfg(target_os = "windows")]
fn ctrl_is_down() -> bool {
    // VK_CONTROL = 0x11. GetAsyncKeyState's high bit (0x8000) = key currently down.
    const VK_CONTROL: i32 = 0x11;
    #[link(name = "user32")]
    extern "system" {
        fn GetAsyncKeyState(vkey: i32) -> i16;
    }
    (unsafe { GetAsyncKeyState(VK_CONTROL) } as u16 & 0x8000) != 0
}

#[cfg(not(target_os = "windows"))]
fn ctrl_is_down() -> bool {
    // Non-Windows builds are for CI/type-checking only (the app targets Windows).
    // Fall back to the tracked flag via thread-local isn't needed here; report false.
    false
}

// ── Shared state ──────────────────────────────────────────────────────────────

struct HotkeyState {
    armed: bool,
    last_ctrl_c_time: Option<Instant>,
    last_trigger_time: Option<Instant>,
}

impl HotkeyState {
    fn new() -> Self {
        HotkeyState {
            armed: false,
            last_ctrl_c_time: None,
            last_trigger_time: None,
        }
    }
}

// ── Modifier / combo key check ────────────────────────────────────────────────
// These keys should NOT reset the armed state.
fn is_modifier_or_combo(key: &Key) -> bool {
    matches!(
        key,
        Key::ControlLeft
            | Key::ControlRight
            | Key::ShiftLeft
            | Key::ShiftRight
            | Key::Alt
            | Key::AltGr
            | Key::MetaLeft
            | Key::MetaRight
            | Key::CapsLock
            | Key::KeyC  // The combo key itself
    )
}

// ── Spawn the single rdev listener thread ────────────────────────────────────

/// Spawn the background keyboard + cursor listener.
///
/// rdev::listen cannot be forcibly stopped from within a callback — the thread
/// exits cleanly when the process exits (via app.exit(0) from the tray).
pub fn spawn_hotkey_listener(app: AppHandle) {
    std::thread::Builder::new()
        .name("rdev-listener".into())
        .spawn(move || {
            let state = Arc::new(Mutex::new(HotkeyState::new()));

            let _ = listen(move |event: Event| match event.event_type {
                EventType::MouseMove { x, y } => {
                    *crate::LAST_CURSOR_POS.lock().unwrap() = (x, y);
                }
                EventType::KeyPress(key) => {
                    on_key_press(key, &state, &app);
                }
                _ => {}
            });
        })
        .expect("failed to spawn rdev-listener thread");
}

// ── Key press handler ─────────────────────────────────────────────────────────

fn on_key_press(key: Key, state: &Arc<Mutex<HotkeyState>>, app: &AppHandle) {
    // Ctrl press itself never arms/fires or resets — just wait for the C.
    if matches!(key, Key::ControlLeft | Key::ControlRight) {
        return;
    }

    let now = Instant::now();
    let mut s = state.lock().unwrap();

    // Debounce: ignore everything within 0.4s of last trigger
    if let Some(last) = s.last_trigger_time {
        if now.duration_since(last) < Duration::from_millis(400) {
            return;
        }
    }

    if key == Key::KeyC && ctrl_is_down() {
        // Ctrl+C pressed
        if s.armed {
            if let Some(arm_time) = s.last_ctrl_c_time {
                if now.duration_since(arm_time) < Duration::from_millis(600) {
                    // Second Ctrl+C within arm window → FIRE
                    s.armed = false;
                    s.last_trigger_time = Some(now);
                    drop(s); // release lock before spawning

                    let app_handle = app.clone();
                    tauri::async_runtime::spawn(async move {
                        crate::handle_translate_trigger(app_handle).await;
                    });
                    return;
                }
            }
        }

        // Not armed, or arm window expired → arm and schedule reset
        s.armed = true;
        s.last_ctrl_c_time = Some(now);
        drop(s);

        // Schedule reset after 0.6s — only clears if no newer Ctrl+C arrived
        let state_clone = state.clone();
        std::thread::spawn(move || {
            std::thread::sleep(Duration::from_millis(600));
            let mut st = state_clone.lock().unwrap();
            if let Some(arm_time) = st.last_ctrl_c_time {
                if arm_time.elapsed() >= Duration::from_millis(600) {
                    st.armed = false;
                }
            }
        });
    } else if !is_modifier_or_combo(&key) {
        // Non-modifier, non-combo key → reset armed state
        s.armed = false;
    }
}
