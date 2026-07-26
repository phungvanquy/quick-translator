//! Global hotkey engine — table-driven, configurable.
//!
//! Uses rdev::listen (passive, non-suppressing) to observe key events.
//! The state machine interprets a parsed hotkey table (hot-swappable via ArcSwap)
//! rather than hardcoded key sequences.
//!
//! Every hotkey is a two-step sequence: prefix → then, within a time window.
//! Double-tap is the degenerate case where prefix == then (requires a KeyRelease
//! between the two presses to filter out key-repeat).
//!
//! Ctrl state is queried live (GetAsyncKeyState on Windows) to avoid stuck-key
//! desync from missed KeyRelease events.
//!
//! rdev::listen can only be called once per process — this single thread handles
//! all hotkey detection.

use arc_swap::ArcSwap;
use rdev::{listen, Event, EventType, Key};
use std::collections::HashSet;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tauri::AppHandle;

use crate::config::HotkeyConfig;

// ── Actions ──────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Action {
    Translate,
    Chat,
    Screenshot,
}

// ── Parsed prefix representation ─────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ParsedPrefix {
    pub key: Key,
    pub requires_ctrl: bool,
}

// ── Parsed hotkey entry ──────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct ParsedEntry {
    pub prefix: ParsedPrefix,
    pub then_key: Key,
    pub then_requires_ctrl: bool,
    pub window_ms: u16,
    pub action: Action,
    pub is_double_tap: bool,
}

// ── Parsed hotkey table ──────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct ParsedHotkeys {
    pub entries: Vec<ParsedEntry>,
    pub no_reset_keys: HashSet<Key>,
}

impl ParsedHotkeys {
    pub fn from_config(cfg: &HotkeyConfig) -> Self {
        let raw = [
            (&cfg.translate, Action::Translate),
            (&cfg.chat, Action::Chat),
            (&cfg.screenshot, Action::Screenshot),
        ];

        let mut entries = Vec::with_capacity(3);
        let mut no_reset_keys: HashSet<Key> = HashSet::new();

        // Always exempt modifier keys from resetting armed state
        for k in [
            Key::ControlLeft, Key::ControlRight,
            Key::ShiftLeft, Key::ShiftRight,
            Key::Alt, Key::AltGr,
            Key::MetaLeft, Key::MetaRight,
            Key::CapsLock,
        ] {
            no_reset_keys.insert(k);
        }

        for (entry, action) in raw {
            let prefix = parse_prefix(&entry.prefix);
            let (then_key, then_requires_ctrl) = parse_then(&entry.then, &entry.prefix);
            let is_double_tap = prefix.key == then_key
                && prefix.requires_ctrl == then_requires_ctrl;

            // Keys involved in any hotkey should not reset armed state
            no_reset_keys.insert(prefix.key);
            no_reset_keys.insert(then_key);

            entries.push(ParsedEntry {
                prefix,
                then_key,
                then_requires_ctrl,
                window_ms: entry.window_ms,
                action,
                is_double_tap,
            });
        }

        ParsedHotkeys { entries, no_reset_keys }
    }
}

fn parse_prefix(s: &str) -> ParsedPrefix {
    match s {
        "Ctrl+C" => ParsedPrefix { key: Key::KeyC, requires_ctrl: true },
        "Ctrl+Insert" => ParsedPrefix { key: Key::Insert, requires_ctrl: true },
        "RCtrl" => ParsedPrefix { key: Key::ControlRight, requires_ctrl: false },
        "RShift" => ParsedPrefix { key: Key::ShiftRight, requires_ctrl: false },
        _ => ParsedPrefix { key: Key::KeyC, requires_ctrl: true }, // fallback
    }
}

fn parse_then(then: &str, prefix: &str) -> (Key, bool) {
    // For double-tap patterns, the "then" key is the same as the prefix key
    if then == "RCtrl" {
        return (Key::ControlRight, false);
    }
    if then == "RShift" {
        return (Key::ShiftRight, false);
    }

    // For prefix "Ctrl+C" / "Ctrl+Insert", Ctrl is still held when "then" fires
    let ctrl = prefix.starts_with("Ctrl+");

    let key = match then {
        "C" => Key::KeyC,
        "Space" => Key::Space,
        "A" => Key::KeyA,
        "B" => Key::KeyB,
        "D" => Key::KeyD,
        "E" => Key::KeyE,
        "F" => Key::KeyF,
        "G" => Key::KeyG,
        "H" => Key::KeyH,
        "I" => Key::KeyI,
        "J" => Key::KeyJ,
        "K" => Key::KeyK,
        "L" => Key::KeyL,
        "M" => Key::KeyM,
        "N" => Key::KeyN,
        "O" => Key::KeyO,
        "P" => Key::KeyP,
        "Q" => Key::KeyQ,
        "R" => Key::KeyR,
        "S" => Key::KeyS,
        "T" => Key::KeyT,
        "U" => Key::KeyU,
        "V" => Key::KeyV,
        "W" => Key::KeyW,
        "X" => Key::KeyX,
        "Y" => Key::KeyY,
        "Z" => Key::KeyZ,
        "Insert" => Key::Insert,
        "0" => Key::Num0,
        "1" => Key::Num1,
        "2" => Key::Num2,
        "3" => Key::Num3,
        "4" => Key::Num4,
        "5" => Key::Num5,
        "6" => Key::Num6,
        "7" => Key::Num7,
        "8" => Key::Num8,
        "9" => Key::Num9,
        "F1" => Key::F1,
        "F2" => Key::F2,
        "F3" => Key::F3,
        "F4" => Key::F4,
        "F5" => Key::F5,
        "F6" => Key::F6,
        "F7" => Key::F7,
        "F8" => Key::F8,
        "F9" => Key::F9,
        "F10" => Key::F10,
        "F11" => Key::F11,
        "F12" => Key::F12,
        _ => Key::Unknown(0), // shouldn't happen with validated config
    };
    (key, ctrl)
}

// ── On-demand cursor position ─────────────────────────────────────────────────

/// Current cursor position in physical screen pixels.
#[cfg(target_os = "windows")]
pub fn cursor_pos() -> (f64, f64) {
    #[repr(C)]
    struct POINT { x: i32, y: i32 }
    #[link(name = "user32")]
    extern "system" {
        fn GetCursorPos(point: *mut POINT) -> i32;
    }
    let mut p = POINT { x: 100, y: 100 };
    unsafe { GetCursorPos(&mut p); }
    (p.x as f64, p.y as f64)
}

#[cfg(not(target_os = "windows"))]
pub fn cursor_pos() -> (f64, f64) {
    (100.0, 100.0)
}

// ── Live Ctrl-key query ──────────────────────────────────────────────────────

#[cfg(target_os = "windows")]
fn ctrl_is_down() -> bool {
    const VK_CONTROL: i32 = 0x11;
    #[link(name = "user32")]
    extern "system" {
        fn GetAsyncKeyState(vkey: i32) -> i16;
    }
    (unsafe { GetAsyncKeyState(VK_CONTROL) } as u16 & 0x8000) != 0
}

#[cfg(not(target_os = "windows"))]
fn ctrl_is_down() -> bool {
    false
}

// ── Shared state ─────────────────────────────────────────────────────────────

struct HotkeyState {
    armed_prefix: Option<(Key, bool, Instant)>, // (prefix_key, requires_ctrl, arm_time)
    last_trigger_time: Option<Instant>,
    prefix_released: bool, // for double-tap key-repeat filtering
}

impl HotkeyState {
    fn new() -> Self {
        HotkeyState {
            armed_prefix: None,
            last_trigger_time: None,
            prefix_released: false,
        }
    }
}

// ── Spawn ────────────────────────────────────────────────────────────────────

pub fn spawn_hotkey_listener(app: AppHandle, hotkeys: Arc<ArcSwap<ParsedHotkeys>>) {
    std::thread::Builder::new()
        .name("rdev-listener".into())
        .spawn(move || {
            let state = Arc::new(Mutex::new(HotkeyState::new()));

            let _ = listen(move |event: Event| {
                match event.event_type {
                    EventType::KeyPress(key) => {
                        on_key_press(key, &state, &app, &hotkeys);
                    }
                    EventType::KeyRelease(key) => {
                        on_key_release(key, &state);
                    }
                    _ => {}
                }
            });
        })
        .expect("failed to spawn rdev-listener thread");
}

// ── Key release handler (for double-tap filtering) ───────────────────────────

fn on_key_release(key: Key, state: &Arc<Mutex<HotkeyState>>) {
    let mut s = state.lock().unwrap_or_else(|e| e.into_inner());
    // If the released key matches the armed prefix key, mark released
    if let Some((prefix_key, _, _)) = s.armed_prefix {
        if key == prefix_key {
            s.prefix_released = true;
        }
    }
}

// ── Key press handler ────────────────────────────────────────────────────────

fn on_key_press(
    key: Key,
    state: &Arc<Mutex<HotkeyState>>,
    app: &AppHandle,
    hotkeys: &Arc<ArcSwap<ParsedHotkeys>>,
) {
    let table = hotkeys.load();
    let now = Instant::now();

    let mut s = state.lock().unwrap_or_else(|e| e.into_inner());

    // Debounce: ignore everything within 0.4s of last trigger
    if let Some(last) = s.last_trigger_time {
        if now.duration_since(last) < Duration::from_millis(400) {
            return;
        }
    }

    // Check if this key press matches any "then" for the currently armed prefix
    if let Some((armed_key, armed_ctrl, arm_time)) = s.armed_prefix {
        for entry in &table.entries {
            if entry.prefix.key != armed_key || entry.prefix.requires_ctrl != armed_ctrl {
                continue;
            }
            let window = Duration::from_millis(entry.window_ms as u64);
            if now.duration_since(arm_time) >= window {
                continue;
            }

            // Check if this key matches the "then" for this entry
            let key_matches = key == entry.then_key;
            let ctrl_ok = !entry.then_requires_ctrl || ctrl_is_down();

            if key_matches && ctrl_ok {
                // Double-tap: require a release between the two presses
                if entry.is_double_tap && !s.prefix_released {
                    continue;
                }

                // FIRE
                s.armed_prefix = None;
                s.last_trigger_time = Some(now);
                s.prefix_released = false;
                let action = entry.action;
                drop(s);

                fire_action(action, app);
                return;
            }
        }
    }

    // Check if this key press matches any prefix → arm
    let ctrl_down = ctrl_is_down();
    for entry in &table.entries {
        let prefix_matches = key == entry.prefix.key;
        let ctrl_ok = !entry.prefix.requires_ctrl || ctrl_down;

        if prefix_matches && ctrl_ok {
            s.armed_prefix = Some((entry.prefix.key, entry.prefix.requires_ctrl, now));
            s.prefix_released = false;
            return;
        }
    }

    // If the key is not in no_reset_keys, clear armed state
    if !table.no_reset_keys.contains(&key) {
        s.armed_prefix = None;
        s.prefix_released = false;
    }
}

fn fire_action(action: Action, app: &AppHandle) {
    let app_handle = app.clone();
    match action {
        Action::Translate => {
            tauri::async_runtime::spawn(async move {
                crate::handle_translate_trigger(app_handle).await;
            });
        }
        Action::Chat => {
            tauri::async_runtime::spawn(async move {
                crate::handle_chat_trigger(app_handle).await;
            });
        }
        Action::Screenshot => {
            tauri::async_runtime::spawn(async move {
                crate::handle_screenshot_trigger(app_handle).await;
            });
        }
    }
}
