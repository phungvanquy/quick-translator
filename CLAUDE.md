# Quick Translator — Project Memory

## Overview
Desktop translator & AI chat assistant. Currently implemented in Python/Tkinter (reference implementation). Being rewritten to Rust + Tauri 2.x in stages — see "Rust/Tauri Rewrite" section below.

## Staged Rewrite Plan

The project is being ported from Python/Tkinter to Rust + Tauri 2.x for a smaller binary, lower idle footprint, and compile-time safety. The Python source files remain in the repo as the **behavioral reference** for Stages 2–3.

| Stage | Scope | Status |
|---|---|---|
| **Stage 1** | Translate flow vertical slice: tray, Ctrl+C+C hotkey, clipboard, streaming translation popup, settings, CI | Implemented in `src-tauri/` + `frontend/` |
| **Stage 2** | Chat popup, Ctrl+C+Space hotkey, markdown rendering in popup | Pending |
| **Stage 3** | TTS/read-aloud, full settings UI, language auto-detect, history/log | Pending |

## Rust/Tauri Stage-1 Architecture

### Tech stack
- **Backend**: Rust, Tauri 2.x, tokio async runtime
- **Frontend**: Plain static HTML/CSS/JS (no JS build step), served from `frontend/`
- **CI**: `windows-latest`, Rust stable toolchain, `cargo tauri build`, NSIS installer

### Module map (`src-tauri/src/`)

| Module | Responsibility |
|---|---|
| `main.rs` | Bootstrap: config load, tray icon, rdev listener spawn, Tauri commands, entry point |
| `config.rs` | `Config` struct, load/save (~/.quicktranslator_config.json), `ConfigState` (Mutex) |
| `hotkey.rs` | rdev passive listener: Ctrl+C+C state machine + cursor-position tracking |
| `clipboard.rs` | `get_clipboard_after_copy`: polls arboard ≤10× @50ms for changed clipboard text |
| `api.rs` | reqwest + SSE streaming to chat/completions, emits `translate://chunk`/`translate://done` |
| `windows.rs` | Create/show translate popup and settings `WebviewWindow` |

### Frontend layout (`frontend/`)

| File | Purpose |
|---|---|
| `theme.css` | GitHub-dark CSS variables (ported from constants.py) |
| `popup.html/css/js` | Frameless translate popup: draggable header, spinner, streaming text, Esc+blur close |
| `settings.html/css/js` | Settings form: api_key, base_url, model, target_language |

### Key design decisions
- `rdev::listen` (passive, single thread) for both Ctrl+C+C detection and cursor tracking — NOT the Tauri global-shortcut plugin (cannot express double-tap)
- `arboard` for clipboard polling
- `reqwest` + manual SSE parsing (not async-openai) for arbitrary base_url support
- Admin elevation via `src-tauri/app.manifest` (`requireAdministrator`) embedded by `winres` in `build.rs`
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

## Python Reference Implementation (Stages 2–3 reference)

> The Python source files below are NOT the active build — they are the behavioral reference for completing the Rust rewrite in Stages 2 and 3. The active CI build is `build.yml` (Tauri/Rust).
>
> **Location:** all Python sources, `icon.ico`/`icon.png`, `installer.iss`, and `requirements.txt` live under `python-reference/`. Module paths in the tables below are relative to that directory (e.g. `python-reference/main.py`). Imports are flat/sibling, so run the app with `python-reference/` as the working directory (`cd python-reference && python main.py`).

## Python Build Notes (reference only — CI no longer uses this)
- PyInstaller builds standalone `.exe` (with `--uac-admin` for global hotkeys)
- Inno Setup (`iscc installer.iss`) builds Windows installer
- `--add-data` bundles all `.py` modules + `icon.ico` + `icon.png` alongside the exe
- **When adding a new `.py` module, you MUST add a corresponding `--add-data` line in `build.yml`** (no longer applicable to current CI)

## Architecture (after refactoring)

| Module | ~Lines | Responsibility |
|---|---|---|
| `main.py` | 94 | Entry point, tk root, clipboard helper, handler wiring |
| `config.py` | 51 | Config load/save/get/update, DEFAULT_CONFIG, DEFAULT_PROMPT |
| `api.py` | 102 | OpenAI client management, translate_stream, chat_with_context_stream |
| `settings.py` | 156 | Settings window UI |
| `translate_popup.py` | 186 | Translation popup with streaming |
| `chat_popup.py` | 708 | Chat popup UI, markdown→tk.Text renderer (mistune 3.x AST), scrollable message frame |
| `hotkeys.py` | 78 | Global hotkey engine (Ctrl+C+C, Ctrl+C+Space) via register_hotkeys() |
| `tray.py` | 75 | System tray icon, graceful shutdown |
| `tts.py` | 40 | Offline text-to-speech via pyttsx3 (OS-native engines) |
| `utils.py` | 58 | Shared UI helpers: bind_close_outside, block_edits |
| `constants.py` | 207 | Color palette (GitHub dark), platform-aware fonts, padding, UI helpers (bind_hover, fade_in, LoadingSpinner) |
| `requirements.txt` | — | openai, keyboard, pyperclip, pystray, Pillow, mistune, pyttsx3 |
| `installer.iss` | — | Inno Setup script for Windows installer |

## Key Patterns
- Config stored at `~/.quicktranslator_config.json`, thread-safe via `_config_lock`
- OpenAI client reused, recreated only when credentials change
- Hotkeys: Ctrl+C+C → translate, Ctrl+C+Space → chat (custom key combo detection via `keyboard` lib)
- Single hidden `tk.Tk` root; all popups are `Toplevel` children
- Streaming responses: background thread yields chunks → `widget.after(0, ...)` dispatches to UI thread
- Markdown rendering: mistune AST → recursive insertion with tk.Text tags
- Platform-aware fonts: `FONT_FAMILY` in constants.py picks Segoe UI / SF Pro Text / Noto Sans based on OS

## Session Rules
- **On interrupted sessions:** Always audit `git status` and `git diff --stat` first, read changed/new files, then continue from where it stopped — never start from scratch.
- **All project memory lives in this file (`CLAUDE.md`)** — do NOT use `~/.claude/` memory files.

## Identified Improvements

### Completed (2026-04-08)
- [x] **#1** — Split main.py into 10 focused modules (config, api, settings, translate_popup, hotkeys, tray, utils)
- [x] **#2** — Deduplicated `_bind_close_outside` → now in `utils.py`
- [x] **#3** — Deduplicated `_block_edits` → now in `utils.py`
- [x] **#4** — Mid-file import of constants fixed (all imports at top)
- [x] **#13** — Platform-aware font fallbacks added (`FONT_FAMILY` in `constants.py`), all hardcoded `"Segoe UI"` replaced

### Pending

#### Error Handling / Robustness
5. **No validation on config values** — `model`, `base_url`, `target_language` accept any string with no validation. Malformed base_url will crash silently.
6. **`os._exit(0)` on quit** — Forceful exit in `tray.py` `_graceful_shutdown`. Should gracefully shutdown (close OpenAI client, stop keyboard hooks, destroy tk root).
7. **No error feedback in chat** — If API call fails, error message appears as plain text in the chat bubble but looks like a normal response.
8. **`get_clipboard_after_copy` is fragile** — Polling-based clipboard check with fixed retries. Can miss or return stale text if system is slow.

#### Performance
9. **`max_completion_tokens=1000` hardcoded** — Not configurable. Long translations or chat responses get truncated without warning.
10. **Chat history unbounded until 50 messages** — The cap at 50 messages is reasonable but sends all 50 to API every time, consuming tokens unnecessarily.

#### UI/UX
11. **No keyboard shortcut to send in chat** — Only Enter works; no Ctrl+Enter for multi-line input.
12. **Settings window hardcoded 500x660** — Not responsive; may clip on smaller screens.
14. **Readme says "Catppuccin Mocha palette"** but constants.py comments say "GitHub dark" — The actual colors are GitHub dark. Readme is outdated.
15. **No way to resize or scroll the translation popup** — Long translations get clipped at MAX_H=520.

#### Security
16. **API key stored in plaintext JSON** — `~/.quicktranslator_config.json` readable by any process. Consider OS keychain integration.

#### Testing
17. **No tests at all** — Zero test files. Core logic (config, markdown rendering, clipboard handling) is easily testable.

#### Missing Features (Low Priority)
18. No language auto-detection
19. No translation history/log
20. No hotkey customization in settings
21. No proxy support configuration
