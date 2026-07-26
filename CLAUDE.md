# Quick Translator — Project Memory

## Overview
Desktop translator & AI chat assistant in Rust + Tauri 2.x. Highlight text, press a hotkey, get a streaming translation or a chat popup. Small binary, low idle footprint, compile-time safety.

## Build Stages
- **Stage 1** (shipping) — translate slice: tray, Ctrl+C+C, clipboard, streaming popup, settings, CI
- **Stage 2** (shipping) — chat popup, Ctrl+C+Space, markdown rendering
- **Stage 3** (built, CI green; manual Windows QA pending) — TTS read-aloud, configurable hotkeys, screenshot → vision chat. Remaining ideas in "Stage 3 Roadmap"

## Architecture

**Stack:** Rust + Tauri 2.x + tokio backend; plain static HTML/CSS/JS frontend (no JS build step); CI on `windows-latest` → `cargo tauri build` → NSIS installer.

### Backend (`src-tauri/src/`)
| Module | Responsibility |
|---|---|
| `main.rs` | Bootstrap: single-instance plugin, config load, tray, rdev listener, Tauri commands, translate/chat/screenshot triggers, overlay-select handler |
| `config.rs` | `Config` struct, load/save (`~/.quicktranslator_config.json`), `ConfigState` (Mutex) |
| `hotkey.rs` | rdev passive listener; table-driven two-step state machine read from config via `ArcSwap`; `cursor_pos()` samples cursor on demand at fire time |
| `clipboard.rs` | `get_clipboard_after_copy`: polls arboard ≤10× @50ms for changed text |
| `api.rs` | reqwest + SSE to chat/completions; emits `translate://chunk\|done`, `chat://chunk\|done`; routes to `vision_model` when the history carries an image |
| `screenshot.rs` | xcap multi-monitor capture, crop, JPEG encode (q60 preview / q80 ≤1568px for API); `ScreenshotStore` holds captures in RAM only |
| `tts.rs` | Read-aloud via the `tts` crate (SAPI on Windows); single active utterance |
| `windows.rs` | Create/show translate popup, chat popup, settings, and per-monitor selection overlays |

### Frontend (`frontend/`)
| File | Purpose |
|---|---|
| `theme.css` | Indigo tokens (dark+light via `prefers-color-scheme`), `.ic` icon helper, spinner keyframes |
| `icons.js` | Inline SVG `<symbol>` sprite; injected as first `<body>` child |
| `popup.*` | Frameless translate popup: draggable, spinner, streaming, Esc+blur close |
| `chat.*` | Frameless chat popup: context strip, transcript, input bar, streaming bubbles |
| `markdown.js` | Minimal XSS-safe markdown→HTML for chat |
| `overlay.*` | Fullscreen region-select overlay: frozen screenshot on a canvas, drag to select, Esc/right-click cancels |
| `settings.*` | Form: api_key, base_url, model, vision_model, target_language, custom_prompt, hotkey capture |

### Key design decisions

**Hotkey / input**
- `rdev::listen` (passive, single thread) detects the double-taps — NOT the Tauri global-shortcut plugin (can't express double-tap).
- Cursor position for popup placement is sampled **on demand** via `hotkey::cursor_pos()` (`GetCursorPos`, physical px) at fire time — NOT per `MouseMove`. rdev still installs a mouse LL hook (no keyboard-only mode) but does no per-event work; dropping the mouse hook needs replacing `rdev::listen` (deferred).
- Arm-reset is **lazy** (no timer thread): both fire paths re-check `now - last_ctrl_c_time < 600ms`, so a stale `armed` can't mis-fire. Keeps the LL hook callback allocation-free — spawning a thread inside `WH_KEYBOARD_LL` risked `LowLevelHooksTimeout` (~300ms) dropping/unhooking the listener.
- Hook state lock **recovers on poison** (`lock().unwrap_or_else(|e| e.into_inner())`) so a transient panic can't permanently kill the hotkey.
- Live Ctrl state via `GetAsyncKeyState` — avoids stuck-`ctrl_held` desync from a missed KeyRelease.

**Process / lifecycle**
- **Single instance** via `tauri-plugin-single-instance` (registered FIRST). Second launch opens Settings in the primary instance instead of installing a second hook set (which would double-fire every hotkey).
- Tray-app lifecycle: Tauri exits on last-window-close, so `main.rs` uses `.build().run(|_,ev| …)` and calls `api.prevent_exit()` on `RunEvent::ExitRequested { code: None, .. }` (window close), letting `Some(_)` through (tray Quit → `app.exit`). Without this, closing a popup kills the app.
- No admin elevation: `app.manifest` requests `asInvoker` (embedded via `build.rs`). Windows UIPI means the hook won't see input while an *elevated* window is foreground; "Run as administrator" is the per-session workaround.

**API / clipboard / config**
- `arboard` polling; app only *reads* the clipboard and does NOT restore prior contents (would need continuous monitoring — rejected).
- `reqwest` + manual SSE parsing (not async-openai) for arbitrary base_url.
- `api.rs` uses a connect timeout + per-chunk idle timeout so a hung server surfaces an error, not an eternal spinner.
- Config format is interoperable with the old Python app (`~/.quicktranslator_config.json`).
- `base_url` with `http://` is allowed but Settings shows a non-blocking "API key travels unencrypted" warning; `https://`/empty stay silent.

**Windows / UI (Tauri gotchas)**
- Popup streaming uses a `popup://ready` handshake (frontend emits after listeners attach; backend waits, 2s fallback) — Tauri events aren't buffered, so a fixed sleep dropped early chunks.
- **Never `sleep()` then `emit()` at a window you just created.** This bug has now shipped three times (translate chunks, overlay preview, chat image). Events are dropped, not queued, and WebView2 startup is 100–300ms — the payload vanishes with no error. Use a handshake, or better a **pull**: store the payload in managed state and have the frontend `invoke` for it once its listeners are up (`get_overlay_preview`, `take_pending_image`). `take_pending_image` also *takes* rather than clones, so a stale crop can't re-attach to a later chat session. Emitting is only safe at a window already known to be listening.
- Tray icon is owned by code (`TrayIconBuilder`); `tauri.conf.json` must NOT declare `app.trayIcon` or two icons appear.
- Blur-to-close only fires after the window gained focus once (built `.focused(true)`) — prevents instant close.
- **Tauri 2 ACL:** `core:window:default` grants only read/query. `window.close()` needs `core:window:allow-close`; `data-tauri-drag-region` needs `core:window:allow-start-dragging`. Both must be in `capabilities/default.json` or the calls are silently denied. Custom commands + backend-side window calls are NOT ACL-gated.
- **DPI-safe positioning:** rdev reports PHYSICAL px, `WebviewWindowBuilder::position()` expects LOGICAL px. So build hidden → `set_position(PhysicalPosition)` using the cursor monitor's `scale_factor()`/bounds (`monitor_from_point`) → `show()`+`set_focus()`. Never pass rdev coords to `.position()`.
- **Overlay sizing + crop scale:** the overlay is sized with `PhysicalSize` after build, not via the builder's logical `inner_size` (which resolves against whatever scale factor the window was created on, not the target monitor's). Order matters — `set_position` BEFORE `set_size`, since moving across monitors makes Windows suggest a rescaled rect. Build `.resizable(true)` so `set_size` is honoured, then `set_resizable(false)`.
- **Don't trust `devicePixelRatio` for the crop.** It can disagree with the monitor's real scale factor. The overlay reports its canvas size and the backend derives the factor as `capture_width / viewport_width`, self-calibrating. A factor off by 1.25× crops a smaller region that then gets upscaled — looks like the screenshot is "zoomed in". Same trap inside the canvas: a rect in CSS px is not a valid `drawImage` *source* rect against a physical-res image.
- **Hotkey "then" keys must round-trip.** `settings.js` `codeToKey` has a catch-all that can emit names (`LCtrl`, `Num0`, `ArrowUp`) the engine's `map_then_key` doesn't map. Those parse to `Key::Unknown(0)`, which no real event carries — the hotkey saves fine and then silently never fires. `SUPPORTED_THEN` (frontend) and `is_supported_then` (backend, enforced in `HotkeyConfig::validate`) must stay in sync; keep RCtrl/RShift in both since double-tap uses a modifier as its "then".

**Theme / assets**
- Indigo accent (`#7C6BFF` dark / `#6D5AE6` light); dark+light driven purely by `@media (prefers-color-scheme)` in `theme.css` — one token set, no toggle, no JS. No literal hex outside `theme.css` except `#ffffff` on colored buttons.
- All glyphs are a shared inline-SVG `<symbol>` sprite (`icons.js`), `<use href="#ic-…"/>`, `currentColor` so they re-tint per theme/state. Paths adapted from MIT Lucide.
- Popups use `.transparent(true)` for rounded corners + shadow via CSS on `body`/`.chat-window` (Settings stays decorated). **OQ1 (unverified):** confirm on real Windows that transparency keeps shadow + always-on-top + positioning; if not, fall back to opaque + CSS `border-radius` (square corners) and record it here.
- App icon: two-arrows glyph on indigo gradient (`icons/icon.png` + `.ico`), generated by committed `icons/generate_icon.py`. Tray uses `default_window_icon()`.

## Stage 3 Roadmap
Behaviors worth preserving are captured as OpenSpec specs. (The Python/Tkinter prototype was removed — recoverable from git history.)
- **TTS read-aloud** — BUILT (`tts.rs`, speaker button in the translate popup). Spec: `production-cleanup-drop-python/specs/tts-read-aloud/`.
- **Configurable hotkeys** — BUILT + archived. Spec: `openspec/specs/hotkey-config/`.
- **Screenshot → vision chat** — BUILT + archived. Specs: `openspec/specs/screenshot-capture/` + `vision-chat/`. Images live in RAM only, never on disk, and nothing is sent until the user types a question.
- **Translation history / log** — idea only. Persist past translations.
- **Language auto-detection** — idea only. Detect source language instead of assuming.

## Pre-release Manual QA Checklist
Requires a Windows run with a global keyboard hook + API key (not headless/CI). Verify before tagging.

**Core**
- [ ] Ctrl+C+Space opens chat with selection as context; Ctrl+C+C still translates; neither double-fires
- [ ] Esc / close button / click-outside close the chat popup; clearing context switches to Free Chat
- [ ] Custom prompt loads, saves, resets to default; blank-save falls back to default template; a subsequent translate uses the saved prompt (persisted to `~/.quicktranslator_config.json`)
- [ ] `cargo build` / `cargo tauri build` passes on Windows CI
- [ ] Packaged exe shows NO UAC prompt; hotkeys work over normal windows; inactive over an elevated foreground window unless the app itself runs as admin

**Screenshot → vision chat** (screenshot-vision-chat) — none of this is CI-verifiable
- [ ] Screenshot hotkey (default RCtrl RCtrl) freezes the screen and shows the dimmed overlay on EVERY monitor; the frozen image is the real screen, not black
- [ ] **Crop fidelity:** the region sent matches the region dragged — no zoom, no offset. Check on a scaled display (125%/150%) and on a non-primary monitor, since that is where the CSS→physical factor goes wrong
- [ ] The bright cutout under the cursor tracks the drag accurately (it uses the same scale factor as the crop)
- [ ] Esc and right-click cancel with no popup; a <5px drag is ignored
- [ ] Crop opens chat with the thumbnail attached and NOTHING sent until a question is typed; capturing again with chat open attaches a 2nd thumbnail; a 3rd evicts the oldest and its history entry becomes the removed-screenshot placeholder
- [ ] Capture → close chat without sending → capture again: the new chat shows only the NEW image (no stale crop resurfacing)
- [ ] Vision request routes to `vision_model` when set, falls back to `model` when blank
- [ ] Closing chat / cancelling frees the captures (watch RSS after several captures — images are RAM-only by design)

**Configurable hotkeys** (configurable-hotkeys)
- [ ] All three hotkeys re-bind from Settings and take effect WITHOUT restart; the old binding stops firing
- [ ] Re-capturing the screenshot binding to RCtrl RCtrl works (a modifier is a legal "then" for double-tap)
- [ ] An unsupported key (Left Ctrl, numpad, arrows) is refused at capture with "Unsupported — try another" rather than saved-and-dead
- [ ] Duplicate combos are blocked inline; a hand-corrupted `hotkeys` block in the config file falls back to defaults with the app still functional

**Runtime footprint** (harden-runtime-footprint)
- [ ] **Single instance:** second launch does NOT start a second process (surfaces Settings); one hotkey press → exactly ONE popup + ONE API request
- [ ] **Cursor positioning (OQ1):** both popups anchor next to the cursor on high-DPI and multi-monitor (incl. non-primary at a different scale). If off, mark per-monitor-DPI-aware or convert explicitly, and record here
- [ ] **http:// warning:** `http://…` base_url saves but warns; `https://`/empty shows no warning
- [ ] Hotkey stays responsive under heavy mouse/typing (no dropped Ctrl+C+C) and still fires after long uptime

**UX** (translate-popup-ux / chat-popup-ux / settings-validation)
- [ ] Translate popup: resizes by dragging its edge; truncated original shows full text on hover; Copy is disabled while streaming, then copies plain translation with "Copied ✓". If it shows "Copy failed" (WebView2 blocks `navigator.clipboard`), switch to the Tauri clipboard-manager plugin + grant write permission in `capabilities/default.json`
- [ ] Chat input: Enter sends, Shift+Enter newline (auto-grows ~120px then scrolls), Ctrl+Enter sends, empty/whitespace does nothing, textarea resets after send; typing indicator until first token, then markdown
- [ ] Chat input with a Vietnamese/CJK IME: Enter to CONFIRM a composition does NOT send
- [ ] Settings: malformed/scheme-less base_url blocked inline; empty base_url saves (backend defaults); empty api_key saves with a warning; "Test connection" reports success / auth error / connection error using the current (possibly unsaved) form values

**UI theme** (redesign-ui-indigo-theme)
- [ ] Both popups + Settings render correctly in dark and light (toggle OS preference); indigo accent for primary/link/focus; nothing washed-out or invisible
- [ ] All glyphs are SVG (no emoji); icons tint per hover/disabled/theme; spinner spins
- [ ] Popups show rounded corners + drop shadow, visually layered; chat user bubble uses accent-soft tint, assistant stays neutral. **OQ1:** confirm `transparent:true` didn't break shadow / always-on-top / positioning; else take opaque + CSS-radius fallback and note it
- [ ] Tray icon + installer show the two-arrows indigo icon, crisp at small sizes

## Session Rules
- **Interrupted sessions:** audit `git status` + `git diff --stat` first, read changed/new files, continue from where it stopped — never start from scratch.
- **Codebase search — reach for `auggie` first.** The `auggie` MCP server (`.mcp.json`) keeps a live semantic index of this repo. Call `codebase-retrieval` with `directory_path: /root/coding/quick-translator` as the FIRST step whenever the question is "where/how does X work" and the answer spans files not yet read. One call returns Rust + JS + specs + the relevant CLAUDE.md lines, which beats three rounds of grep.
  - **Use it for:** orienting before any non-trivial change; tracing a flow across backend↔frontend (hotkey → trigger → api → popup event); finding which spec covers a behavior; "is feature X already implemented?"; picking up an interrupted session.
  - **Skip it for:** an exact symbol or string already known (`grep`), a file whose path is already known (`Read`), anything about git history (not indexed).
  - Phrase requests as natural-language questions ("How does the popup receive streaming chunks?"), not grep patterns ("find emit(").
  - Ask ONE broad question over several narrow ones — the index cross-references on its own and each call is a round trip.
  - It reads the working tree only: no history, no staged-vs-committed distinction, and just-written edits may lag the index. Confirm anything load-bearing with `Read` before editing.
  - `.augmentignore` excludes archived **delta specs** (`openspec/changes/archive/*/specs/`), build output, and binary icons. Those deltas are verbatim copies of specs already promoted into `openspec/specs/`, so indexing both made one query return 3-4 identical hits and crowded out real code. Archived `proposal.md`/`design.md`/`tasks.md` stay indexed — that rationale exists nowhere else.
  - `.augmentignore` is read once when the server builds its path filter, so edits to it need an MCP-server restart (`/mcp` → reconnect) before they take effect.
  - **Fire it automatically at these points** (no need to be asked):
    - `/opsx:propose` — before writing `proposal.md`, ask "is this already implemented, and what would it touch?" That check is what caught TTS as already-spec'd-but-unbuilt.
    - `/opsx:apply` — before the first code edit, ask how the target flow currently works, so edits land in the existing pattern.
    - `/opsx:explore` — first move, to ground the discussion in real code instead of theorizing.
    - Resuming an interrupted session — pair it with the `git status` audit above.
    - Any bug report naming a symptom rather than a file ("popup shows nothing", "hotkey stopped firing").
- **All project memory lives in this file** — do NOT use `~/.claude/` memory files.
- **Dependencies — minimal, not zero.** Adding a crate is fine when it makes the project meaningfully better and is safe: actively maintained, widely used, trusted source, pinned version, checked against typosquatting. Prefer the lightest option; don't reinvent what a vetted crate does well.

## Identified Improvements
Carried over from the prototype; NOT re-verified against current Rust code — confirm before acting.
- **Clipboard capture is polling-based** — fixed retry budget; can miss/return stale text on a slow system.
- **Completion token cap hardcoded** — long responses can truncate without warning; consider making it configurable.
- **Chat history sent whole** — capped at 50 messages but the full window is sent each turn.
- **API key in plaintext JSON** — readable by any process; consider OS keychain.
- **Settings window fixed size** — may clip on small screens.
- **Thin test coverage** — only a Node markdown-renderer test; core Rust logic (config, clipboard, SSE) untested.
- **Missing (low priority):** hotkey customization, proxy support.
