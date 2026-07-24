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
//! The cursor position for popup placement is sampled on demand (GetCursorPos)
//! at the moment a hotkey fires — see `cursor_pos()`. We deliberately do NOT
//! track MouseMove here: that ran on the system-wide low-level mouse hook and
//! locked a mutex on every move for data only ever read once per trigger.
//!
//! rdev::listen can only be called once per process — this single thread
//! handles hotkey detection.

use rdev::{listen, Event, EventType, Key};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tauri::AppHandle;

// ── On-demand cursor position ─────────────────────────────────────────────────
// Sampled when a hotkey fires, not tracked per mouse move. GetCursorPos returns
// physical screen pixels (per-monitor DPI-aware) — the same space rdev reported
// and that windows::position_at_cursor already treats as physical.

/// Current cursor position in physical screen pixels.
#[cfg(target_os = "windows")]
pub fn cursor_pos() -> (f64, f64) {
    #[repr(C)]
    struct POINT {
        x: i32,
        y: i32,
    }
    #[link(name = "user32")]
    extern "system" {
        fn GetCursorPos(point: *mut POINT) -> i32;
    }
    let mut p = POINT { x: 100, y: 100 };
    unsafe {
        GetCursorPos(&mut p);
    }
    (p.x as f64, p.y as f64)
}

#[cfg(not(target_os = "windows"))]
pub fn cursor_pos() -> (f64, f64) {
    // Non-Windows builds are for CI/type-checking only.
    (100.0, 100.0)
}

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
            | Key::KeyC  // The translate combo key
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

            let _ = listen(move |event: Event| {
                if let EventType::KeyPress(key) = event.event_type {
                    on_key_press(key, &state, &app);
                }
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
    // Recover on poison: a transient panic elsewhere must not permanently kill
    // the global hotkey. The guarded state is plain Copy fields with no invariant
    // a mid-panic write could corrupt dangerously.
    let mut s = state.lock().unwrap_or_else(|e| e.into_inner());

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

        // Not armed, or arm window expired → arm. No reset thread: the fire
        // paths above already gate on `now - last_ctrl_c_time < 600ms`, so a
        // stale `armed` flag can never mis-fire — a later Ctrl+C outside the
        // window just re-arms with a fresh timestamp. Keeping the hook callback
        // allocation-free (no per-press thread spawn) matters for the Windows
        // LowLevelHooksTimeout budget.
        s.armed = true;
        s.last_ctrl_c_time = Some(now);
    } else if key == Key::Space && ctrl_is_down() {
        // Ctrl+Space — fires chat only if a Ctrl+C armed the window within 0.6s.
        // Shares the single arm window with the translate double-tap, so a given
        // Ctrl+C leads to translate OR chat depending on the second key.
        if s.armed {
            if let Some(arm_time) = s.last_ctrl_c_time {
                if now.duration_since(arm_time) < Duration::from_millis(600) {
                    s.armed = false;
                    s.last_trigger_time = Some(now);
                    drop(s); // release lock before spawning

                    let app_handle = app.clone();
                    tauri::async_runtime::spawn(async move {
                        crate::handle_chat_trigger(app_handle).await;
                    });
                    return;
                }
            }
        }
        // Ctrl+Space with no live armed window → clear armed state
        s.armed = false;
    } else if !is_modifier_or_combo(&key) {
        // Non-modifier, non-combo key → reset armed state.
        // A bare Space (Ctrl not held) lands here and resets, matching Python.
        s.armed = false;
    }
}
