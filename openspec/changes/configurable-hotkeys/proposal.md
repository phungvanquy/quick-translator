## Why

All hotkeys are hardcoded in `hotkey.rs` — Ctrl+C+C for translate, Ctrl+C+Space for chat. Users cannot change them, so anyone whose workflow collides with these combos (e.g. Vim double-Ctrl+C to interrupt, or editors that intercept Ctrl+Space for autocomplete) has no recourse. The upcoming screenshot feature needs a third hotkey (RCtrl+RCtrl), and future features may add more. Without a configuration layer, each new action re-hardens the single state machine and risks breaking existing combos.

Additionally, because `rdev::listen` is passive (non-suppressing), every hotkey leaks to the foreground app. The system must actively guide users away from dangerous combos — something a hardcoded system can't do.

## What Changes

- **Config schema:** add `hotkeys` object to `Config` with per-action entries: `translate`, `chat`, `screenshot`
- **Hotkey model:** every action is a two-step sequence (`prefix` → `then`, within a time window). Double-tap is the degenerate case where prefix == then. One-step hotkeys are deliberately excluded (cannot suppress, side effects guaranteed).
- **Prefix whitelist:** only safe prefixes are offered — keys/combos whose solo press is harmless (Ctrl+C = copy/idempotent, RCtrl = no-op, Ctrl+Insert = copy, RShift = no-op)
- **State machine rewrite:** `hotkey.rs` transitions from hardcoded branches to interpreting a parsed hotkey table. The table is held in a dedicated `RwLock`/`ArcSwap` so Settings can hot-swap it without restarting the listener (rdev::listen can only be called once per process).
- **Settings UI:** new "Hotkeys" section with a capture widget per action — user focuses the field and presses the desired key combo; the widget records it. Inline warnings for: known side-effects (Ctrl+S = Save), cross-action conflicts, prefix not in whitelist. "Reset to defaults" button.
- **Fail-safe:** if saved config contains an invalid or conflicting hotkey table, fall back to defaults silently at startup (never lose all hotkeys).

## Capabilities

### New Capabilities
- `hotkey-config`: User-configurable two-step hotkey sequences with prefix whitelist, conflict detection, and hot-swap reload

### Modified Capabilities
- `translate-hotkey`: hotkey source changes from hardcoded Ctrl+C+C to config-driven
- `chat-hotkey`: hotkey source changes from hardcoded Ctrl+C+Space to config-driven
- `config-store`: schema gains `hotkeys` object

## Impact

- `src-tauri/src/hotkey.rs`: state machine rewrite — hardcoded branches → table-driven dispatch; new RwLock for parsed table; key-repeat filter for double-tap prefixes
- `src-tauri/src/config.rs`: `Config` gains `hotkeys` field with defaults matching current behavior
- `src-tauri/src/main.rs`: wire parsed hotkey table into managed state; add `save_hotkeys` or extend `save_config` command
- `frontend/settings.html` + `settings.js` + `settings.css`: hotkey capture section with per-action widgets, conflict warnings, reset button
- No new crates (rdev already provides KeyPress/KeyRelease + left/right distinction)
- Backwards-compatible: missing `hotkeys` key in existing config → defaults (translate=Ctrl+C+C, chat=Ctrl+C+Space, screenshot=RCtrl+RCtrl)
