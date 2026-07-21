## 1. custom_prompt in settings (quick adjacent win)

- [x] 1.1 Add a `<textarea>` for custom prompt (with label + `{target_language}` hint) and a "Reset to default" button to `frontend/settings.html`
- [x] 1.2 In `frontend/settings.js`, load `cfg.custom_prompt` into the textarea, include it in the save payload, and fall back to the default template when blank
- [ ] 1.3 Verify saving a custom prompt persists to `~/.quicktranslator_config.json` and a subsequent translate uses it

## 2. Chat hotkey (backend)

- [x] 2.1 Add a `Space` branch to `on_key_press` in `hotkey.rs`: fire chat when `armed && ctrl_is_down()` within the 0.6s window, respecting the 0.4s debounce (port of `hotkeys.py:56`)
- [x] 2.2 Ensure a bare Space (no armed Ctrl+C) resets armed state like any other non-combo key, and that chat/translate share the single arm window without double-firing
- [x] 2.3 Spawn a `handle_chat_trigger(app)` async task from the Space branch (parallel to the translate trigger)

## 3. Chat trigger + window (backend)

- [x] 3.1 Implement `handle_chat_trigger` in `main.rs`: capture clipboard via `get_clipboard_after_copy` on a blocking thread, read cursor pos, open the chat popup (open even when selection is empty → free chat)
- [x] 3.2 Register the `popup://ready` handshake before creating the chat window (reuse the translate pattern) so early chunks aren't lost
- [x] 3.3 Add `show_chat_popup` to `windows.rs`: frameless, always-on-top, resizable (~500×580, min ~380×320), DPI-safe physical-pixel positioning via the cursor monitor scale, built hidden then shown/focused
- [x] 3.4 Pass selected text + target context to the window via query params (URL-encoded, reusing the existing encoder)

## 4. Chat streaming (backend)

- [x] 4.1 Add `chat_stream` in `api.rs` that builds messages = system prompt + history + question and POSTs to `<base_url>/chat/completions` with `stream: true`, reusing SSE parsing + connect/idle timeouts
- [x] 4.2 Switch the system prompt on whether selected text is present (embedded-selection prompt vs. general assistant prompt), matching `api.py` `chat_with_context_stream`
- [x] 4.3 Emit `chat://chunk` / `chat://done` (+ an error event/message) to the chat window
- [x] 4.4 Handle missing API key: no request, deliver the "set API key in Settings" message to the popup
- [x] 4.5 Add a `#[tauri::command] chat_send(selected_text, question, history)` and register it in `main.rs`'s `invoke_handler`

## 5. Chat popup frontend

- [x] 5.1 Create `frontend/chat.html`: header (drag zone via `data-tauri-drag-region` + close button), optional context strip with clear button, scrollable transcript, bottom input bar with Send
- [x] 5.2 Create `frontend/chat.css` using `theme.css` variables (GitHub-dark), matching the Python layout (header 40px, expanding transcript, pinned input)
- [x] 5.3 Create `frontend/chat.js`: read init query params, hold `history` + selected-text context, `invoke("chat_send", ...)` on send, append user bubble + streaming assistant bubble, cap history to last 50 after each turn
- [x] 5.4 Wire close behaviors: Esc, close button, and blur-to-close guarded by a once-focused flag (parity with the translate popup)
- [x] 5.5 Wire the context clear control: hide strip, clear history, switch header to "Free Chat", stop sending selected-text context
- [x] 5.6 Disable Send while a response streams and re-enable on `chat://done`. (No `popup://ready` handshake needed: this popup is frontend-driven — listeners attach in init() before any `chat_send`, so chunks can't precede them.)

## 6. Markdown rendering

- [x] 6.1 Add a small markdown→HTML renderer to `frontend/` (vendored minimal lib file or compact hand-rolled) covering bold, italic, bold+italic, inline code, fenced code blocks, h1–h3, bullet + ordered lists
- [x] 6.2 Escape HTML / disable raw-HTML passthrough so assistant output is rendered as text, never executed (XSS-safe)
- [x] 6.3 Show interim text while streaming; render final markdown on `chat://done`

## 7. ACL / capabilities

- [x] 7.1 Grant the chat window `core:window:allow-close` and `core:window:allow-start-dragging` — already satisfied: `capabilities/default.json` applies to `"windows": ["*"]` and already lists both permissions, so the chat window inherits them.

## 8. Verification

- [ ] 8.1 Confirm `cargo build` / type-check passes on the CI target (no Windows-only calls outside `#[cfg]`) — BLOCKED: no Rust toolchain in this env. Static review done; run `cargo build` (or push to the Windows CI) to confirm.
- [ ] 8.2 Manually verify: Ctrl+C+Space opens chat with the selection as context; Ctrl+C+C still translates; neither double-fires — BLOCKED: needs Windows + global keyboard hook.
- [x] 8.3 Markdown renderer + XSS-safety verified via Node unit test (bold/italic/code/fence/headings/ul/ol render; `<script>`, `<img onerror>`, raw `<b>` all escaped inert). Full in-app streaming/multi-turn check still needs a Windows run + API key.
- [ ] 8.4 Manually verify: Esc / close button / click-outside all close the popup; clearing context switches to Free Chat — BLOCKED: needs Windows run.
- [ ] 8.5 Manually verify: custom prompt field loads, saves, resets to default, and blank-saves fall back to the default template — BLOCKED: needs Windows run (logic reviewed statically).
