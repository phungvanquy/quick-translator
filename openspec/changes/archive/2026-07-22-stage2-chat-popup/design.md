## Context

Stage 1 delivered the translate vertical slice in Rust/Tauri: `rdev` global hook, clipboard capture, a streaming translate popup, settings, and tray lifecycle. Stage 2 adds the second core interaction from the Python reference — a chat assistant (Ctrl+C+Space) with multi-turn history and markdown answers — plus a small fix to surface the already-backend-supported `custom_prompt` in settings.

Key existing pieces this design builds on:
- `hotkey.rs`: single `rdev::listen` thread with an arm-window/debounce state machine. Currently only the Ctrl+C+C branch fires; there is no Space branch.
- `api.rs`: reqwest + manual SSE parsing that streams to a target window via `translate://chunk` / `translate://done` events, with connect + idle timeouts.
- `windows.rs`: DPI-safe popup creation (build hidden → `set_position(PhysicalPosition)` using the cursor monitor scale → show → focus).
- `main.rs`: `handle_translate_trigger` uses a `popup://ready` handshake so early stream chunks aren't lost; tray-lifecycle keeps the app alive when the last window closes.
- Frontend is plain static HTML/CSS/JS, no build step; `theme.css` holds the GitHub-dark palette.

## Goals / Non-Goals

**Goals:**
- Ctrl+C+Space opens a chat popup with the captured selection as context (or free chat if empty).
- Multi-turn history within the popup lifetime, capped at the last 50 messages, sent as context each turn.
- Streaming assistant responses reusing the SSE approach.
- Markdown rendering of assistant messages (bold/italic/code/headings/lists) in the webview.
- Surface `custom_prompt` in the settings form with a reset-to-default.

**Non-Goals:**
- TTS / read-aloud (deferred to a later Stage 3 change).
- Persisting chat history to disk across sessions.
- Language auto-detect, translation history/log, hotkey customization (later stages).
- Changing the config file schema — it stays interoperable with the Python app.

## Decisions

### Extend the existing hotkey state machine rather than add a second listener
`rdev::listen` can only run once per process, and the arm window is shared state. Add a `Space` branch inside `on_key_press` that fires chat when `armed && ctrl_is_down()` within the 0.6s window — a direct port of `hotkeys.py:56`. Space must be added to the "does not reset armed state during the window" handling only in the armed-with-ctrl case; a bare Space with no ctrl still resets like any other key. This keeps a single source of truth for arming/debounce.
- *Alternative considered:* a separate combo tracker. Rejected — duplicates state and risks double-fires.

### Chat window mirrors the translate popup's DPI-safe creation
Add `show_chat_popup` in `windows.rs` using the same build-hidden → position-by-physical-pixels → show/focus sequence. Chat is larger (~500×580, resizable, min ~380×320) per the Python reference. Reuse the once-focused blur-to-close guard and the header-only drag zone (`data-tauri-drag-region` on the header, requiring `core:window:allow-start-dragging`).
- *Alternative considered:* reuse the translate popup window. Rejected — different layout, lifecycle, and it must coexist (translate and chat are independent).

### Reuse the streaming/handshake pattern for chat
Add `chat_stream` in `api.rs` parameterized on messages, emitting `chat://chunk` / `chat://done` (+ an error path) to the chat window. Reuse the `popup://ready` handshake so chunks emitted before the webview attaches listeners aren't dropped. The backend builds the message array (system prompt + history + question); the system prompt switches on whether selected text is present, matching `api.py`.
- *Alternative considered:* generic event names shared with translate. Rejected — distinct names keep the two popups' listeners cleanly separated.

### History lives in the frontend; backend is stateless per request
The chat popup's JS owns the `history` array (user/assistant turns) and the selected-text context, and passes them into each `invoke("chat_send", { selectedText, question, history })` call. The backend command assembles messages and streams back. This matches the Python design where `show_chat_popup` holds `chat_history` and passes it to `chat_with_context_stream`. Cap to last 50 in the frontend after each completed turn.
- *Alternative considered:* backend-held session state keyed by window. Rejected — more moving parts; the popup lifetime already scopes the history naturally.

### Markdown: render in the webview, don't port the tk renderer
The Python `render_markdown_to_text` hand-rolled a mistune-AST→tk.Text-tags renderer (~250 lines) because Tkinter has no HTML. A webview renders HTML natively, so this is markdown→HTML instead. To honor the no-build-step frontend, use a single small vendored markdown lib file (e.g. a minimal marked/snarkdown-class script dropped in `frontend/`) or a compact hand-rolled renderer covering the required subset. Rendered output MUST be treated as untrusted: render markdown to sanitized HTML (escape raw HTML, no script execution) so assistant output can't inject live markup.
- *Alternative considered:* a full npm build pipeline. Rejected — breaks the deliberate no-JS-build constraint.

### custom_prompt is a frontend-only change
Backend (`config.rs`, `api.rs`) already stores and uses `custom_prompt`. Only `settings.html` (add a `<textarea>` + reset button + hint) and `settings.js` (load into the field; include in the save payload; blank → default) change. `ConfigUpdate` already carries the field.

## Risks / Trade-offs

- **[Streaming race: chunks before webview listeners attach]** → Reuse the proven `popup://ready` handshake + 2s fallback from the translate flow; don't stream until ready or timeout.
- **[Markdown XSS from assistant/API output]** → Escape HTML and disable raw-HTML passthrough in the renderer; treat all model output as untrusted data. Verify with an input containing `<script>` and `<img onerror=...>`.
- **[Space branch causing accidental chat triggers]** → Only fire when `armed && ctrl_is_down()` inside the 0.6s window and outside the 0.4s debounce; a bare Space resets armed state like any other key. Mirror `hotkeys.py` exactly.
- **[Two popups fighting for focus / blur-close loops]** → Chat uses the same once-focused guard before enabling blur-to-close; translate and chat are separate window labels so they don't collide.
- **[Non-Windows CI build]** → `ctrl_is_down()` already has a non-Windows stub; new code must keep compiling on the CI target (no Windows-only calls outside `#[cfg]`).

## Open Questions

- Multi-line input: Python uses a single-line `Entry` (Enter sends). Keep single-line for parity, or add Shift+Enter for newlines? Default to parity (single-line, Enter sends) unless the user wants the enhancement.
- Vendored markdown lib vs. hand-rolled: pick the smallest option that covers the required subset; decide at implementation time based on size/licence.
