## Why

Because the app catches hotkeys with a passive global hook (`rdev::listen`), every keystroke and every mouse move in *every* application on the system passes through this process first. That is inherent to the design, but the current implementation adds avoidable cost and fragility on top of it:

- **Mouse-move hot path**: `on` every `MouseMove` event the listener locks `LAST_CURSOR_POS` and writes it (`hotkey.rs:96-98`) — hundreds of times a second while the user moves the mouse — even though the cursor position is only ever read at the instant a hotkey fires. This burns CPU wakeups and contends a mutex for data we could sample once, on demand. It works against the project's "low idle footprint" goal.
- **Work inside the low-level hook callback**: each first `Ctrl+C` spawns a fresh OS thread that sleeps 600 ms only to (maybe) clear `armed` (`hotkey.rs:151-160`). Spawning a thread from within a `WH_KEYBOARD_LL` callback is exactly the kind of work Windows' `LowLevelHooksTimeout` (~300 ms) punishes: under load the OS can silently drop events or unhook the listener, degrading typing latency system-wide. The thread is also **redundant** — every fire path already re-checks the 600 ms window against `last_ctrl_c_time` (`hotkey.rs:130`, `:167`), so a stale `armed` flag cannot cause a wrong trigger.
- **No single-instance guard**: launching the app twice installs two sets of global hooks; both fire on the same hotkey, producing double popups and double API calls, and doubling the per-event hook cost on the whole system.
- **Listener death on a poisoned mutex**: the hook thread `.unwrap()`s its lock (`hotkey.rs:97`, `:117`). One panic while the lock is held poisons it, every later event re-panics, and the listener thread dies — the hotkey silently stops working until the app is restarted, with no indication why.
- **Plaintext API key over `http://`**: `base_url` accepts any scheme, so a mistyped or intentionally `http://` endpoint sends `Authorization: Bearer <key>` unencrypted. Settings already validates URL shape (change `settings-validation`) but does not warn about the downgrade.

## What Changes

- **Sample the cursor on demand.** Stop handling `MouseMove` in the rdev callback and stop maintaining `LAST_CURSOR_POS`; read the live cursor position at trigger time (Windows `GetCursorPos`) instead. Removes the per-move mutex lock from the system-wide hot path.
- **Do no blocking/spawning work in the hook callback, and drop the redundant reset thread.** Arm expiry is judged lazily from `last_ctrl_c_time` at the next event (already the source of truth), so the 600 ms reset thread is deleted rather than replaced.
- **Enforce a single running instance** via `tauri-plugin-single-instance`; a second launch focuses/settles into the existing instance instead of installing a second hook set.
- **Make the listener resilient to a poisoned lock** so a transient panic cannot permanently kill the global hook (recover the inner guard instead of `.unwrap()`-panicking).
- **Warn on an `http://` base URL** in Settings (non-blocking) so the user knows the API key would be sent unencrypted; `https://` and empty stay silent.

No config schema change (Python interop preserved). No change to the translate/chat/streaming behavior, hotkey timing (0.6 s arm / 0.4 s debounce), or popup positioning as observed by the user.

## Non-Goals

- **Restoring the user's pre-copy clipboard** — considered and rejected; the user's own `Ctrl+C` presses (not the app) overwrite the clipboard, and reliably restoring it would require continuously monitoring the clipboard, which contradicts the "no heavy work around the hook" goal. See `design.md`.
- **Removing the low-level *mouse* hook entirely** — `rdev::listen` always installs both keyboard and mouse hooks; eliminating the mouse hook needs a different capture mechanism (direct `SetWindowsHookEx(WH_KEYBOARD_LL)` or a keyboard-only crate). Out of scope; noted as a future option in `design.md`.
- **OS-keychain storage for the API key** — separate, larger effort; unchanged here.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `tray-lifecycle`: gains a single-instance requirement and a global-listener-resilience requirement (no blocking work in the hook callback; survive a transient lock poison).
- `config-store`: the existing "Settings input validation" requirement gains an `http://` downgrade warning scenario.

## Impact

- `src-tauri/Cargo.toml` — add `tauri-plugin-single-instance = "2"` (pinned major, official Tauri plugin).
- `src-tauri/src/hotkey.rs` — drop `MouseMove` handling and the 600 ms reset thread; add an on-demand `cursor_pos()` (Windows `GetCursorPos`, physical pixels); recover-on-poison lock helper.
- `src-tauri/src/main.rs` — remove `LAST_CURSOR_POS`; register the single-instance plugin in the builder; read cursor via `hotkey::cursor_pos()` in `handle_translate_trigger` / `handle_chat_trigger`.
- `frontend/settings.js` — add a non-blocking warning when a saved `base_url` uses `http://`.
- `openspec/specs/tray-lifecycle` + `openspec/specs/config-store` — spec deltas (this change).
- CLAUDE.md — update the architecture notes (cursor is sampled on demand, not tracked; single-instance; listener resilience) and the pre-release QA checklist.
