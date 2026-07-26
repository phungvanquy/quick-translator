## 1. Config Schema + Parsing

- [x] 1.1 Add `HotkeyEntry` struct (`prefix: String`, `then: String`, `window_ms: u16`) and `HotkeyConfig` struct (translate, chat, screenshot fields) to `config.rs`
- [x] 1.2 Add `#[serde(default)]` `hotkeys: HotkeyConfig` field to `Config`; implement `Default` for `HotkeyConfig` with current hardcoded values (translate=Ctrl+C→C/600, chat=Ctrl+C→Space/600, screenshot=RCtrl→RCtrl/400)
- [x] 1.3 Add validation function: checks prefix in whitelist, no duplicate (prefix,then) pairs across actions, window_ms in [200,1000]; returns `Result<(), Vec<String>>`
- [x] 1.4 On config load: if validation fails, replace `hotkeys` with defaults and log warning to stderr

## 2. Parsed Hotkey Table + ArcSwap

- [x] 2.1 Add `arc-swap` crate to `Cargo.toml` (verify MSVC compat — fallback: `parking_lot::RwLock`)
- [x] 2.2 Create `ParsedHotkeys` struct: a small vec of `(ParsedPrefix, ParsedThen, Action)` tuples where prefix/then are resolved to `rdev::Key` enums + modifier flags; include a `HashSet` of keys that should not reset armed state
- [x] 2.3 Implement `ParsedHotkeys::from_config(hotkeys: &HotkeyConfig) -> Self` — maps string names ("Ctrl+C", "RCtrl", "Space", etc.) to rdev Key values
- [x] 2.4 Register `ArcSwap<ParsedHotkeys>` as Tauri managed state; initialize from loaded config at startup

## 3. State Machine Rewrite

- [x] 3.1 Replace hardcoded `on_key_press` logic with table-driven dispatch: on KeyPress, iterate parsed table checking armed prefix match → fire, then prefix match → arm
- [x] 3.2 Implement key-repeat filter for double-tap: track `prefix_key_released: bool`; only count second press as "then" if a KeyRelease of the same key was seen between the two presses
- [x] 3.3 Make `is_modifier_or_combo` dynamic: derive the "don't reset" key set from `ParsedHotkeys.no_reset_keys` instead of hardcoded matches
- [x] 3.4 Wire `ArcSwap<ParsedHotkeys>` into the rdev listener closure (Arc clone, `load()` per key event)
- [x] 3.5 Verify debounce (shared `last_trigger_time`) still works across all three actions

## 4. Hot-Swap on Config Save

- [x] 4.1 After successful config save in the `save_config` command: re-parse hotkeys, validate, and `store()` into ArcSwap; if parse fails, keep old table (do not swap)
- [x] 4.2 Frontend `settings.js`: send hotkeys as part of the config save payload (same `save_config` invoke, extended args)

## 5. Settings UI — Hotkey Section

- [x] 5.1 Add "Hotkeys" section to `settings.html`: three rows (Translate, Chat, Screenshot), each with a prefix dropdown and a "then" capture input
- [x] 5.2 Implement prefix dropdown: options from whitelist (Ctrl+C, Ctrl+Insert, RCtrl, RShift); selected value maps to config string
- [x] 5.3 Implement "then" key capture: on focus, listen for next `keydown`; record `event.code`; display human-readable label; ignore pure modifier presses (Ctrl/Shift/Alt alone)
- [x] 5.4 Detect and display conflicts: after any field change, check all three actions for duplicate (prefix, then) pairs; show inline warning badge
- [x] 5.5 Detect and display side-effect warnings: map known dangerous prefix+then combos (Ctrl+C→S = Ctrl+S, etc.) to warning text
- [x] 5.6 "Reset to defaults" button: restores all three rows to default values without saving
- [x] 5.7 On form load: populate widgets from current config hotkeys values
- [x] 5.8 On save: validate client-side (conflicts block save with inline error), then include hotkeys in the invoke payload

## 6. Verification

- [x] 6.1 `cargo build` passes with no errors (requires Windows Rust toolchain)
- [x] 6.2 `cargo clippy` passes (requires Windows Rust toolchain)
- [x] 6.3 Manual test: change translate hotkey in Settings → new hotkey fires translate, old one does not
- [x] 6.4 Manual test: set two actions to same combo → save is blocked with conflict warning
- [x] 6.5 Manual test: delete `hotkeys` from config JSON → app starts with defaults, no crash
- [x] 6.6 Manual test: RCtrl double-tap fires screenshot action (placeholder: log message, since screenshot-vision-chat not yet implemented)
