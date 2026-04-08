# Quick Translator — Project Memory

## Overview
Desktop translator & AI chat assistant (Python/Tkinter). Runs in system tray, uses global hotkeys to translate or chat about selected text via OpenAI-compatible APIs.

## Build & Deployment
- **NOT built locally** — Uses GitHub Actions workflow (`.github/workflows/build.yml`)
- Workflow triggers on push to main/master or manual dispatch
- Runs on `windows-latest`, Python 3.11
- PyInstaller builds standalone `.exe` (with `--uac-admin` for global hotkeys)
- Inno Setup (`iscc installer.iss`) builds Windows installer
- Artifacts uploaded: `QuickTranslator-Windows` (.exe) and `QuickTranslator-Setup` (installer)
- Retention: 30 days
- `--add-data` bundles all `.py` modules + `icon.ico` + `icon.png` alongside the exe
- **When adding a new `.py` module, you MUST add a corresponding `--add-data` line in `build.yml`**

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
| `utils.py` | 58 | Shared UI helpers: bind_close_outside, block_edits |
| `constants.py` | 207 | Color palette (GitHub dark), platform-aware fonts, padding, UI helpers (bind_hover, fade_in, LoadingSpinner) |
| `requirements.txt` | — | openai, keyboard, pyperclip, pystray, Pillow, mistune |
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
