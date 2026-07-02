## Context

Quick Translator is a Python/Tkinter tray app. The user is rewriting it to Rust + Tauri 2.x for a smaller self-contained binary, lower idle footprint, and compile-time safety. Critically: **this is a Windows GUI app and cannot be built or run on the Linux dev box** — the only correctness gate is CI compilation on `windows-latest`. To de-risk, we ship a **vertical slice (Stage 1)** proving the full architecture (tray → hotkey → clipboard → streaming API → popup → config) before porting chat, markdown, TTS, and full settings (Stages 2–3).

The existing Python modules (`hotkeys.py`, `main.py`, `api.py`, `translate_popup.py`, `config.py`, `tray.py`, `constants.py`) are the behavioral reference and stay in the repo untouched.

## Goals / Non-Goals

**Goals:**
- Faithfully reproduce the translate path's runtime behavior: double-Ctrl+C detection, clipboard polling, streaming translation, near-cursor popup, config round-trip.
- Preserve config-file compatibility with the Python app (`~/.quicktranslator_config.json`).
- Produce a compiling Tauri build on `windows-latest` yielding a `.exe` + NSIS installer, with admin elevation.
- No stubs — every Stage-1 handler is fully implemented.

**Non-Goals:**
- Chat popup, Ctrl+C+Space, markdown rendering, TTS, full settings UI, language auto-detect, history (all later stages).
- Local build/run verification (impossible here — CI only).
- Deleting or refactoring the Python source.

## Decisions

### D1: Tauri 2.x (Rust backend + plain HTML/CSS/JS frontend)
User-selected. Web UI makes the popup styling and later markdown rendering (Stage 2) straightforward. **No JS build step** — frontend is static HTML/CSS/JS served from a frontend dir, referenced by `tauri.conf.json` `frontendDist`. This avoids adding Node to CI and keeps the toolchain purely Rust.
- *Alternatives:* egui/iced (pure Rust, but manual markdown later, plainer UI). Rejected per user choice.

### D2: `rdev` raw keyboard hook for Ctrl+C+C (NOT the global-shortcut plugin)
The Tauri `global-shortcut` plugin registers discrete accelerators and cannot express "Ctrl+C pressed twice." `rdev::listen` gives raw key press/release events on a dedicated OS thread, letting us port the exact `hotkeys.py` state machine. Ctrl+C must remain a real OS copy (so the selection lands on the clipboard) — a raw *listener* (not a grab/suppress) observes the key without consuming it, preserving the native copy.
- State machine (ported from `hotkeys.py`): track `ctrl` held state from key events; on `C` with ctrl held → if armed and within 0.6s, fire translate + set last-trigger time; else arm and start a 0.6s reset timer. Enforce a 0.4s debounce using a last-trigger timestamp. Any non-modifier, non-combo key clears the armed state.
- Threading: `rdev::listen` blocks, so it runs on its own `std::thread`. It communicates trigger events to the Tauri/async world via a channel (or `AppHandle` + `tauri::async_runtime::spawn`). Shared state (armed flag, timestamps) guarded by a `Mutex` since callbacks fire on the listener thread.
- *Alternatives:* `global-shortcut` plugin (can't double-tap), `device_query` polling (misses fast taps, wastes CPU). Rejected.

### D3: `arboard` for clipboard, replicating `get_clipboard_after_copy`
Capture clipboard text before the second copy settles, then poll ≤10× at 50ms for a changed value; trimmed new value on change, trimmed previous value as fallback. `arboard` is the de-facto cross-platform clipboard crate and works off the main thread (needed since we read from the hotkey flow).

### D4: `reqwest` + tokio + manual SSE parsing (NOT async-openai)
Manual `POST <base_url>/chat/completions` with `stream: true` gives full control over arbitrary OpenAI-compatible `base_url`s (local LLMs, proxies). Parse the streamed body line-by-line; for each `data:` payload that isn't `[DONE]`, deserialize just enough (`choices[0].delta.content`) and emit non-empty deltas. Runtime: Tauri's bundled tokio (`tauri::async_runtime`) or a `#[tokio::main]`-style spawn; use `reqwest::Response::bytes_stream()` + a line/`eventsource` splitter.
- Request body: `{model, messages:[{role:system,content:<prompt>},{role:user,content:<text>}], max_completion_tokens:1000, stream:true}`. System prompt = `custom_prompt` with `{target_language}` substituted; on substitution failure, use the raw prompt (mirror the Python `try/except`).
- Delivery: emit each chunk to the popup webview via `window.emit("translate://chunk", delta)` and a terminal `translate://done`. Errors → emit `translate://chunk` with `⚠ Error: …`; missing key → `⚠ No API key set.\n…` without any HTTP call.
- *Alternatives:* `async-openai` (opinionated about endpoints/params, friction with custom base_url + `max_completion_tokens`). Rejected.

### D5: Popup as a dedicated frameless WebviewWindow
A pre-declared or dynamically-created `WebviewWindow` with `decorations:false`, `always_on_top:true`, `skip_taskbar:true`, `transparent` as needed. Backend computes cursor position (via `rdev`/tauri) and sets window position offset from the cursor, clamped on-screen, before showing. The window's JS listens for `translate://chunk`/`translate://done` events and appends text; Escape and `window blur` close it (`getCurrentWindow().close()`); a header element uses Tauri's `data-tauri-drag-region` for dragging. Original text (truncated ~120 chars) + target-language header rendered from an initial payload (passed via event or query string). GitHub-dark palette (`BG`, `SURFACE`, `TEXT_C`, etc. from `constants.py`) ported into CSS variables.
- Chunks render as **plain text** in Stage 1 (markdown is Stage 2).

### D6: Config module with serde + dirs
`Config` struct with `#[serde(default = ...)]` per field so a partial/missing file merges over defaults (mirrors `{**DEFAULT_CONFIG, **json.load}`). Path from `dirs::home_dir()` joined with `.quicktranslator_config.json`. Save via `serde_json::to_string_pretty` written UTF-8; serde_json does not ASCII-escape non-ASCII by default, satisfying `ensure_ascii=False`. Absent file → write defaults; malformed file → in-memory defaults without overwriting. Thread-safe access via a `Mutex<Config>` (config read on the API path, written from Settings).

### D7: Settings as a second WebviewWindow
A normal decorated window with four inputs (`api_key`, `base_url`, `model`, `target_language`) + Save. Save invokes a `#[tauri::command]` that updates the `Mutex<Config>` and persists. Opened on first run when `api_key` is empty, and from the tray menu.

### D8: Tray + lifecycle
Tauri v2 `TrayIconBuilder` with a menu (`Settings`, `Quit`). Icon from bundled `icon.ico`/`icon.png` (copied into `src-tauri/icons/`), generated fallback only if load fails. Quit stops the `rdev` thread (signal a shutdown flag / drop the listener) and calls `app.exit(0)`.

### D9: Windows elevation + CI
`tauri.conf.json` → `bundle.windows` sets the manifest to `requireAdministrator` (via a bundled `app.manifest` or the `bundle > windows > … > uac`-equivalent for the NSIS installer / embedded manifest). CI: `windows-latest`, `dtolnay/rust-toolchain@stable`, install the Tauri CLI (`cargo install tauri-cli` or `tauri-apps/tauri-action`), run the release build, upload `.exe` + NSIS installer artifacts (30-day retention). No Python/PyInstaller/Inno steps.

### Proposed file layout
```
src-tauri/
  Cargo.toml
  build.rs                 (tauri build script)
  tauri.conf.json
  app.manifest             (requireAdministrator)
  icons/ (icon.ico, icon.png, + generated platform icons)
  src/
    main.rs                (bootstrap: config load, tray, hotkey thread, windows)
    config.rs              (Config, load/save, Mutex state)
    hotkey.rs              (rdev listener + Ctrl+C+C state machine)
    clipboard.rs           (get_clipboard_after_copy port)
    api.rs                 (reqwest streaming + SSE parse + event emit)
    windows.rs             (create/show translate popup + settings windows)
frontend/
  popup.html / popup.css / popup.js
  settings.html / settings.css / settings.js
  shared theme css (GitHub-dark vars)
```

## Risks / Trade-offs

- **Cannot verify runtime locally** → CI compile is the gate; keep logic close to the well-understood Python reference and lean on the produced artifact for the user's manual Windows test. Document this clearly.
- **`rdev` on Windows may need admin to see elevated windows' input** → the `requireAdministrator` manifest (D9) mirrors the Python `--uac-admin` requirement.
- **`rdev` listener blocks a thread and is hard to cleanly stop** → run it detached on a dedicated thread and signal shutdown via an atomic flag; on Quit call `app.exit(0)` so the process tears down the thread. Accept that the listener thread is terminated by process exit (matches Python `keyboard.unhook_all()` + `os._exit`).
- **SSE framing variance across OpenAI-compatible servers** (chunk boundaries not aligned to lines) → buffer partial lines and split on newlines before parsing `data:` payloads; ignore blank/keep-alive lines; treat `[DONE]` or stream end as completion.
- **Transparent/frameless always-on-top window quirks on Windows** → keep the window simple; if transparency causes issues, fall back to an opaque frameless window with a CSS border (matches the Python "shadow border" trick).
- **Admin elevation UAC prompt on every launch** → inherent to the global-hook requirement; unchanged from the Python app's behavior.
- **Tauri v2 API churn** → pin `tauri` 2.x and the CLI version in CI to avoid drift; the build failing loudly in CI is acceptable since CI is the gate.

## Migration Plan

Additive: new `src-tauri/` + `frontend/` alongside the untouched Python source. `build.yml` and `CLAUDE.md` are the only modified existing files. No data migration — the config file format is intentionally identical, so users moving from the Python app to the Rust app keep their settings. Rollback = revert `build.yml`/`CLAUDE.md` and ignore/remove the new dirs; the Python app is unaffected.

## Open Questions

- None blocking. Exact Tauri v2 manifest mechanism for `requireAdministrator` (embedded `app.manifest` vs. bundle config) is an implementation detail to confirm against Tauri 2.x docs during apply; both are viable and the requirement (elevation on the produced exe) is fixed.
