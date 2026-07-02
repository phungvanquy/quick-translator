//! Global hotkey engine — parity with hotkeys.py
//!
//! Uses rdev::listen (passive, non-suppressing) to observe key events.
//! Implements the Ctrl+C+C double-tap state machine:
//!   - 0.6s arm window between first and second Ctrl+C
//!   - 0.4s debounce after trigger fires
//!   - Any non-modifier / non-combo key clears armed state
//!
//! Also tracks the cursor position via MouseMove events, storing it in
//! LAST_CURSOR_POS (in main.rs) for use when opening the popup.
//!
//! rdev::listen can only be called once per process — this single thread
//! handles both cursor tracking and hotkey detection.

use rdev::{listen, Event, EventType, Key};
use std::sync::{Arc, Mutex};
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};
use tauri::AppHandle;

// ── Shared state ──────────────────────────────────────────────────────────────

struct HotkeyState {
    ctrl_held: bool,
    armed: bool,
    last_ctrl_c_time: Option<Instant>,
    last_trigger_time: Option<Instant>,
}

impl HotkeyState {
    fn new() -> Self {
        HotkeyState {
            ctrl_held: false,
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
/// Returns a shutdown flag (set to true to signal exit intent).
/// Note: rdev::listen cannot be forcibly stopped from within a callback —
/// the thread will exit cleanly when the process exits (via app.exit(0)).
pub fn spawn_hotkey_listener(app: AppHandle) -> Arc<AtomicBool> {
    let shutdown = Arc::new(AtomicBool::new(false));
    let shutdown_clone = shutdown.clone();

    std::thread::Builder::new()
        .name("rdev-listener".into())
        .spawn(move || {
            let state = Arc::new(Mutex::new(HotkeyState::new()));
            let shutdown_flag = shutdown_clone;

            let _ = listen(move |event: Event| {
                if shutdown_flag.load(Ordering::Relaxed) {
                    return;
                }

                match event.event_type {
                    EventType::MouseMove { x, y } => {
                        *crate::LAST_CURSOR_POS.lock().unwrap() = (x, y);
                    }
                    EventType::KeyPress(key) => {
                        on_key_press(key, &state, &app);
                    }
                    EventType::KeyRelease(key) => {
                        on_key_release(key, &state);
                    }
                    _ => {}
                }
            });
        })
        .expect("failed to spawn rdev-listener thread");

    shutdown
}

// ── Key release handler ───────────────────────────────────────────────────────

fn on_key_release(key: Key, state: &Arc<Mutex<HotkeyState>>) {
    if matches!(key, Key::ControlLeft | Key::ControlRight) {
        state.lock().unwrap().ctrl_held = false;
    }
}

// ── Key press handler ─────────────────────────────────────────────────────────

fn on_key_press(key: Key, state: &Arc<Mutex<HotkeyState>>, app: &AppHandle) {
    let now = Instant::now();

    // Update ctrl held state first
    if matches!(key, Key::ControlLeft | Key::ControlRight) {
        state.lock().unwrap().ctrl_held = true;
        return;
    }

    let mut s = state.lock().unwrap();

    // Debounce: ignore everything within 0.4s of last trigger
    if let Some(last) = s.last_trigger_time {
        if now.duration_since(last) < Duration::from_millis(400) {
            return;
        }
    }

    if key == Key::KeyC && s.ctrl_held {
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

        // Schedule reset after 0.6s
        let state_clone = state.clone();
        std::thread::spawn(move || {
            std::thread::sleep(Duration::from_millis(600));
            let mut st = state_clone.lock().unwrap();
            // Only clear if the arm event we just set is still the latest one
            // (i.e., no newer Ctrl+C arrived)
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
