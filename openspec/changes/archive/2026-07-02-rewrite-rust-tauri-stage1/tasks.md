## 1. Project scaffold (Tauri 2.x, no JS build step)

- [x] 1.1 Create `src-tauri/Cargo.toml` with a binary crate depending on: `tauri` 2.x (features for tray-icon), `serde`/`serde_json`, `dirs`, `rdev`, `arboard`, `reqwest` (rustls or default TLS, `stream`), `tokio` (or use `tauri::async_runtime`). Pin `tauri` to 2.x.
- [x] 1.2 Create `src-tauri/build.rs` invoking `tauri_build::build()`.
- [x] 1.3 Create `src-tauri/tauri.conf.json`: app identifier, product name "Quick Translator", `frontendDist` pointing at the static `frontend/` dir, no `beforeBuildCommand` (no JS build), windows enabled, NSIS bundle target, tray icon configured.
- [x] 1.4 Copy `icon.ico` and `icon.png` into `src-tauri/icons/` and reference them for the app/tray icon (generate the extra platform icon sizes Tauri requires if needed).
- [x] 1.5 Create `frontend/` with a shared GitHub-dark theme CSS (port color values from `constants.py`: BG, SURFACE, SURFACE1, OVERLAY, MUTED, SUBTEXT, TEXT_C, RED, BORDER, BLUE). ← (verify: crate + conf compile-ready, frontendDist path correct, no node/npm step referenced)

## 2. Config store (parity with config.py)

- [x] 2.1 Implement `src-tauri/src/config.rs`: `Config` struct with fields `api_key`, `base_url`, `target_language`, `model`, `custom_prompt`, each with `#[serde(default=...)]` returning the exact defaults from `config.py` (base_url `https://api.openai.com/v1`, target_language `Vietnamese`, model `gpt-4o-mini`, custom_prompt = the DEFAULT_PROMPT translator template with `{target_language}`).
- [x] 2.2 Implement `load()`: path = `dirs::home_dir()` + `.quicktranslator_config.json`; if present and parseable, deserialize (serde defaults fill missing keys); if absent, write defaults to disk and return defaults; if malformed, return defaults without overwriting.
- [x] 2.3 Implement `save()`: `serde_json::to_string_pretty`, write UTF-8, verify non-ASCII is preserved literally (not `\u`-escaped).
- [x] 2.4 Expose a thread-safe `Mutex<Config>` in Tauri state; add a `get_config`/`update_config` accessor. ← (verify: round-trips a Python-written config unchanged; partial file merges over defaults; malformed file does not clobber)

## 3. Clipboard capture (parity with get_clipboard_after_copy)

- [x] 3.1 Implement `src-tauri/src/clipboard.rs` using `arboard`: capture previous text, poll up to 10× at 50ms for a changed non-empty value, return trimmed new value on change, trimmed previous value as fallback. Return empty string when nothing is available. ← (verify: polling count/interval and fallback match the Python logic)

## 4. Global hotkey Ctrl+C+C (parity with hotkeys.py)

- [x] 4.1 Implement `src-tauri/src/hotkey.rs`: spawn a dedicated `std::thread` running `rdev::listen` as a passive listener (does NOT suppress Ctrl+C, so the OS copy still happens).
- [x] 4.2 Port the state machine: track ctrl-held from key press/release; on `C` with ctrl held → if armed and within 0.6s fire translate, else arm + start 0.6s reset timer; enforce 0.4s debounce via last-trigger timestamp; any non-modifier/non-combo key clears the armed state. Guard shared state with a `Mutex`.
- [x] 4.3 On trigger, run the capture+translate flow off the listener thread (channel or `AppHandle` + `async_runtime::spawn`) so the listener is never blocked. ← (verify: single Ctrl+C never fires; double within 0.6s fires once; 0.4s debounce holds; reset-on-other-key works)

## 5. Streaming translation API (parity with api.py translate_stream)

- [x] 5.1 Implement `src-tauri/src/api.rs`: build system prompt by substituting `{target_language}` into `custom_prompt`, falling back to the raw prompt on failure.
- [x] 5.2 If `api_key` is empty, emit `⚠ No API key set.` + the Settings hint line to the popup and make NO HTTP call.
- [x] 5.3 POST `<base_url>/chat/completions` with bearer auth and body `{model, messages:[system,user], max_completion_tokens:1000, stream:true}` via `reqwest`.
- [x] 5.4 Parse the SSE byte stream: buffer partial lines, for each `data:` payload that isn't `[DONE]` deserialize `choices[0].delta.content` and emit non-empty deltas via a Tauri event; treat `[DONE]`/stream-end as completion.
- [x] 5.5 On HTTP failure, non-success status, or stream error, emit `⚠ Error: <message>`. ← (verify: request shape, prompt formatting, no-key path, error path, and streaming all match api.py)

## 6. Translation popup window

- [x] 6.1 Implement `frontend/popup.html`+`popup.css`+`popup.js`: frameless layout with a draggable header (`data-tauri-drag-region`) showing target language, a truncated (~120 char) original-text line, a result area with a loading indicator, GitHub-dark styling. Plain-text chunk rendering (no markdown in Stage 1).
- [x] 6.2 `popup.js` listens for the chunk/done Tauri events, hides the spinner on first chunk, appends chunks in order, keeps text selectable; closes on Escape and on window blur.
- [x] 6.3 Implement `src-tauri/src/windows.rs` create/show the popup as a frameless, always-on-top, skip-taskbar `WebviewWindow`; compute cursor position, offset, clamp on-screen, then show. Pass the original text + target language to the popup (event or query param). Do not open a popup when captured text is empty. ← (verify: opens near cursor, streams live, Esc + click-outside close, dragging works, empty selection opens nothing)

## 7. Settings window

- [x] 7.1 Implement `frontend/settings.html`+`.css`+`.js` with inputs for `api_key`, `base_url`, `model`, `target_language` and a Save button, GitHub-dark styling.
- [x] 7.2 Add a `#[tauri::command]` to read current config into the form and to save edited values via config.rs; ensure updated credentials take effect on the next translation without an app restart.
- [x] 7.3 In `windows.rs`, create/show/focus the Settings window (reuse if already open). ← (verify: edits persist to the same JSON file in the correct format; new values used immediately)

## 8. Tray + app bootstrap + lifecycle

- [x] 8.1 Implement tray in `main.rs` via `TrayIconBuilder` with menu items Settings and Quit; load bundled icon with generated fallback.
- [x] 8.2 Bootstrap in `main.rs`: load config; if `api_key` empty, open Settings on first run; start the `rdev` hotkey thread; run the Tauri app with no visible main window.
- [x] 8.3 Implement graceful shutdown on Quit: signal/stop the hotkey thread, close open windows, `app.exit(0)`. ← (verify: tray menu works, first-run opens settings, quit tears down cleanly)

## 9. Windows build + CI

- [x] 9.1 Add `src-tauri/app.manifest` (or equivalent tauri.conf setting) requesting `requireAdministrator`; wire it into the Windows bundle so the produced exe embeds it.
- [x] 9.2 Rewrite `.github/workflows/build.yml`: `windows-latest`; checkout; `dtolnay/rust-toolchain@stable`; install Tauri CLI (or use `tauri-apps/tauri-action`); build the Tauri app in release; remove all PyInstaller/Inno Setup steps.
- [x] 9.3 Upload artifacts: the `.exe` and the NSIS installer, retention 30 days. Keep triggers on push to main/master + workflow_dispatch. ← (verify: workflow compiles the Rust crate as the gate, produces + uploads exe & installer, no PyInstaller/Inno remain)

## 10. Docs

- [x] 10.1 Update `CLAUDE.md`: add a section describing the Rust/Tauri Stage-1 architecture (module map under `src-tauri/`, frontend layout) and the staged rewrite plan (Stage 1 = translate slice; Stages 2–3 = chat, markdown, TTS, full settings). Do NOT remove the existing Python architecture notes — mark them as the reference implementation. ← (verify: CLAUDE.md reflects the new architecture and staged plan without deleting Python reference)
