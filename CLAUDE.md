# Quick Translator — Project Memory

## Overview
Desktop translator & AI chat assistant, built in Rust + Tauri 2.x. Highlight text, press a hotkey, get a streaming translation or open a chat popup. Small binary, low idle footprint, compile-time safety.

## Build Stages

The app was built up in stages. Stages 1 and 2 are implemented and shipping; Stage 3 is the remaining roadmap.

| Stage | Scope | Status |
|---|---|---|
| **Stage 1** | Translate flow vertical slice: tray, Ctrl+C+C hotkey, clipboard, streaming translation popup, settings, CI | Implemented in `src-tauri/` + `frontend/` |
| **Stage 2** | Chat popup, Ctrl+C+Space hotkey, markdown rendering in popup | Implemented in `src-tauri/` + `frontend/` |
| **Stage 3** | Roadmap — see "Stage 3 Roadmap" below | Pending |

## Rust/Tauri Architecture

### Tech stack
- **Backend**: Rust, Tauri 2.x, tokio async runtime
- **Frontend**: Plain static HTML/CSS/JS (no JS build step), served from `frontend/`
- **CI**: `windows-latest`, Rust stable toolchain, `cargo tauri build`, NSIS installer

### Module map (`src-tauri/src/`)

| Module | Responsibility |
|---|---|
| `main.rs` | Bootstrap: config load, tray icon, rdev listener spawn, Tauri commands (incl. `chat_send`), translate + chat triggers, entry point |
| `config.rs` | `Config` struct, load/save (~/.quicktranslator_config.json), `ConfigState` (Mutex) |
| `hotkey.rs` | rdev passive listener: Ctrl+C+C (translate) + Ctrl+C+Space (chat) state machine + cursor-position tracking |
| `clipboard.rs` | `get_clipboard_after_copy`: polls arboard ≤10× @50ms for changed clipboard text |
| `api.rs` | reqwest + SSE streaming to chat/completions: emits `translate://chunk`/`translate://done` and `chat://chunk`/`chat://done` |
| `windows.rs` | Create/show translate popup, chat popup, and settings `WebviewWindow` |

### Frontend layout (`frontend/`)

| File | Purpose |
|---|---|
| `theme.css` | GitHub-dark CSS variables |
| `popup.html/css/js` | Frameless translate popup: draggable header, spinner, streaming text, Esc+blur close |
| `chat.html/css/js` | Frameless chat popup: context strip, scrollable transcript, input bar, streaming assistant bubbles |
| `markdown.js` | Minimal XSS-safe markdown→HTML renderer for chat responses |
| `settings.html/css/js` | Settings form: api_key, base_url, model, target_language, custom_prompt |

### Key design decisions
- `rdev::listen` (passive, single thread) for both Ctrl+C+C detection and cursor tracking — NOT the Tauri global-shortcut plugin (cannot express double-tap)
- `arboard` for clipboard polling
- `reqwest` + manual SSE parsing (not async-openai) for arbitrary base_url support
- No admin elevation: `src-tauri/app.manifest` requests `asInvoker` (embedded via `tauri_build::WindowsAttributes::app_manifest` in `build.rs`). Elevation was dropped (change `drop-windows-admin-elevation`) — it was inherited unverified from the Python `--uac-admin` app and cost a UAC prompt on every launch. Windows UIPI means the `rdev` low-level hook won't see input while an *elevated* window is foreground (Task Manager, admin terminal, regedit); "Run as administrator" is the documented per-session workaround for that rare case
- Config format identical to Python app — `~/.quicktranslator_config.json` is interoperable
- Live Ctrl-key state via `GetAsyncKeyState` (Windows) in the hotkey handler — parity with Python `keyboard.is_pressed`, avoids stuck-`ctrl_held` desync from a missed KeyRelease
- Popup streaming uses a `popup://ready` handshake (frontend emits after listeners attach; backend waits with a 2s fallback before streaming) — Tauri events are not buffered, so a fixed sleep dropped early chunks
- Tray icon is owned solely by the code (`TrayIconBuilder` in `main.rs`); `tauri.conf.json` must NOT declare `app.trayIcon` or two icons appear (only the code one has a menu)
- Popup blur-to-close only fires after the window has gained focus once (built with `.focused(true)`) — prevents an instant close when the window never grabs focus
- `api.rs` uses a connect timeout + per-chunk stream idle timeout so a hung server surfaces an error instead of an eternal spinner
- Tauri 2 ACL: `core:window:default` grants ONLY read/query methods. Frontend `window.close()` needs `core:window:allow-close`; `data-tauri-drag-region` needs `core:window:allow-start-dragging`. Both must be listed in `capabilities/default.json` or the calls are silently denied (popup won't close/drag). Custom `#[tauri::command]`s and backend-side window calls are NOT ACL-gated.
- Tray-app lifecycle: Tauri exits the process when the last window closes. Since popups open/close constantly, `main.rs` uses `.build().run(|_,ev| ...)` and calls `api.prevent_exit()` on `RunEvent::ExitRequested { code: None, .. }` (window close), letting `Some(_)` through (tray Quit calls `app.exit`). Without this, closing the popup kills the whole app.
- Popup positioning is DPI-safe: `rdev` reports PHYSICAL pixels but `WebviewWindowBuilder::position()` expects LOGICAL pixels. So `show_translate_popup` builds the window hidden, then `set_position(PhysicalPosition)` using the cursor monitor's `scale_factor()`/bounds (`monitor_from_point`), then `show()`+`set_focus()`. Never pass rdev coords to the builder's `.position()`.

---

## Stage 3 Roadmap

Remaining features. The project was previously ported from a Python/Tkinter prototype; that reference has been removed (recoverable from git history if ever needed). Behaviors worth preserving are captured as OpenSpec specs.

- **TTS read-aloud** — spec'd in `openspec/changes/production-cleanup-drop-python/specs/tts-read-aloud/spec.md` (or its archived location once applied). A 🔊 button in the translate popup that speaks the **source** text aloud via an OS-native/offline engine (~160 wpm, ~0.9 volume), non-blocking, single active utterance (new speak stops in-progress), and stops when the popup closes. Rust approach: prefer the `tts` crate (SAPI on Windows) or a small Tauri command over the OS speech API.
- **Translation history / log** — idea only, never built. Persist past translations for review.
- **Language auto-detection** — idea only, never built. Detect source language instead of assuming.

## Pre-release Manual QA Checklist

These require a Windows run with a global keyboard hook + an API key (can't run in headless/CI). Verify before tagging a release:

- [ ] Ctrl+C+Space opens chat with the selection as context; Ctrl+C+C still translates; neither double-fires
- [ ] Esc / close button / click-outside all close the chat popup; clearing context switches to Free Chat
- [ ] Custom prompt field loads, saves, resets to default, and blank-saves fall back to the default template
- [ ] Saving a custom prompt persists to `~/.quicktranslator_config.json` and a subsequent translate uses it
- [ ] `cargo build` / `cargo tauri build` passes on the Windows CI target
- [ ] Launching the packaged exe shows NO UAC prompt; Ctrl+C+C / Ctrl+C+Space work over normal windows; hotkey is inactive over an elevated foreground window (Task Manager / admin terminal) unless the app itself is run as administrator

#### UX changes (archived: translate-popup-ux / chat-popup-ux / settings-validation)

- [ ] Translate popup: resizes by dragging its edge; hovering the truncated original shows the full text as a tooltip; the Copy button is disabled while streaming, then copies the plain translation with a "Copied ✓" confirmation once done. If the button shows "Copy failed" (WebView2 blocks `navigator.clipboard.writeText`), switch to the Tauri clipboard-manager plugin + grant the write permission in `capabilities/default.json` (see the archived translate-popup-ux design open question)
- [ ] Chat input: Enter sends, Shift+Enter inserts a newline (box auto-grows to ~120px then scrolls), Ctrl+Enter also sends, empty/whitespace input does nothing, textarea resets to one line after send; a typing indicator shows in the assistant bubble until the first token, then final markdown renders
- [ ] Chat input with a Vietnamese/CJK IME: pressing Enter to CONFIRM a composition does NOT send the message
- [ ] Settings: saving a scheme-less/malformed base_url is blocked inline; empty base_url saves (backend defaults); empty api_key saves with a warning; "Test connection" reports success with a valid key/endpoint/model, a clear auth/HTTP error with a bad key, and a connection error for an unreachable URL — using the current (possibly unsaved) form values

## Session Rules
- **On interrupted sessions:** Always audit `git status` and `git diff --stat` first, read changed/new files, then continue from where it stopped — never start from scratch.
- **All project memory lives in this file (`CLAUDE.md`)** — do NOT use `~/.claude/` memory files.

## Identified Improvements

Potential improvements carried over from the prototype. They have NOT been re-verified against the current Rust code — confirm the issue still exists before acting.

#### Error Handling / Robustness
- **No validation on config values** — `model`, `base_url`, `target_language` accept any string with no validation. A malformed `base_url` should surface a clear error rather than failing opaquely.
- **Clipboard capture is polling-based** — `get_clipboard_after_copy` polls arboard on a fixed retry budget; can miss or return stale text if the system is slow.

#### Performance
- **Completion token cap** — the max-tokens value is hardcoded; long translations/chat responses can truncate without warning. Consider making it configurable.
- **Chat history sent whole** — the transcript is capped at 50 messages but the full window is sent to the API each turn, spending tokens unnecessarily.

#### UI/UX
- **No Ctrl+Enter to send in chat** — only Enter sends; no multi-line-friendly shortcut.
- **Settings window fixed size** — not responsive; may clip on smaller screens.
- **Translate popup can't resize/scroll** — long translations can clip past the fixed max height.

#### Security
- **API key stored in plaintext JSON** — `~/.quicktranslator_config.json` is readable by any process. Consider OS keychain integration.

#### Testing
- **Thin test coverage** — only a Node unit test for the markdown renderer exists. Core Rust logic (config load/merge, clipboard, SSE parsing) is untested.

#### Missing Features (Low Priority)
- No hotkey customization in settings
- No proxy support configuration

(Language auto-detection and translation history/log now live in "Stage 3 Roadmap" above.)
