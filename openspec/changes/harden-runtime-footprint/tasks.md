## 1. On-demand cursor + lighter hook callback

- [x] 1.1 In `src-tauri/src/hotkey.rs`, add `pub fn cursor_pos() -> (f64, f64)` that returns the live cursor position in physical pixels (Windows: `GetCursorPos`; non-Windows stub returns `(100.0, 100.0)` for CI type-checking).
- [x] 1.2 Remove the `EventType::MouseMove` arm from the `listen(...)` callback so only `KeyPress` is processed.
- [x] 1.3 Delete the 600 ms reset thread (`hotkey.rs:151-160`); leave arm expiry to the existing lazy 600 ms check on `last_ctrl_c_time` in the fire paths. Add a one-line comment explaining the flag is judged lazily and never needs eager clearing.
- [x] 1.4 Replace `state.lock().unwrap()` in the hook thread with a recover-on-poison lock (`lock().unwrap_or_else(|e| e.into_inner())`).

## 2. Wire cursor sampling into triggers

- [x] 2.1 In `src-tauri/src/main.rs`, remove the `LAST_CURSOR_POS` static and its `use`/import.
- [x] 2.2 In `handle_translate_trigger` and `handle_chat_trigger`, replace the `*LAST_CURSOR_POS.lock()...` read with `hotkey::cursor_pos()`.

## 3. Single-instance guard

- [x] 3.1 Add `tauri-plugin-single-instance = "2"` to `src-tauri/Cargo.toml` `[dependencies]`.
- [x] 3.2 Register the plugin FIRST in `tauri::Builder` (before other setup) with a callback that, on a second launch, opens/focuses the Settings window via `windows::show_settings_window` (there is no main window to raise).

## 4. http:// downgrade warning

- [x] 4.1 In `frontend/settings.js`, when the (already URL-valid) `base_url` on save uses the `http:` protocol, show a non-blocking warning that the API key will be sent unencrypted; save still proceeds. `https:` and empty stay silent. Reuse the existing warning styling used for the empty-api-key case.

## 5. Docs

- [x] 5.1 Update CLAUDE.md architecture notes: cursor is sampled on demand (not tracked via `MouseMove`), the arm-reset thread is gone (lazy expiry), single-instance is enforced, the hook lock recovers on poison.
- [x] 5.2 Add pre-release QA items to CLAUDE.md: (a) launching twice does not double-fire / only one instance runs; (b) popup still anchors at the cursor on high-DPI + multi-monitor after the `GetCursorPos` switch (OQ1); (c) saving an `http://` base_url shows the unencrypted-key warning but still saves.

## 6. Verify

- [x] 6.1 `cargo build` — delegated to the Windows CI target (`.github/workflows/build.yml`); confirm no unused-import / dead-code warnings from the removed `LAST_CURSOR_POS` and reset thread. (No local Rust toolchain in the dev env; manually reviewed both edited Rust files, no leftover `LAST_CURSOR_POS`/`MouseMove`/`LazyLock` refs. CI is the compile gate.)
- [x] 6.2 Manual QA (single-instance, cursor positioning/OQ1, http warning) — deferred to the CLAUDE.md pre-release checklist (needs a real Windows run with the global hook active).
