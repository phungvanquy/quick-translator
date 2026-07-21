## Why

The Rust/Tauri rewrite has only reached Stage 1 (translate flow). The Python reference app has a second core interaction — a chat assistant triggered by Ctrl+C+Space that lets the user ask questions about selected text with multi-turn history and markdown-rendered answers. Without it, the Rust build is not at feature parity and users lose the assistant they rely on. This change delivers Stage 2 chat, and along the way closes a small gap: the `custom_prompt` config field is already stored and used by the backend but was never surfaced in the settings UI.

## What Changes

- Add a **Ctrl+C+Space** branch to the global hotkey state machine that captures the current selection and opens a chat popup (parallel to the existing Ctrl+C+C translate trigger).
- Add a **chat popup** window (frameless, draggable header, cursor-anchored, DPI-safe) with a scrollable message area and a text input pinned to the bottom.
- Support **multi-turn conversation history** within a chat session, sending prior turns as context on each request, capped to bound token usage (Python caps at 50 messages).
- **Stream** assistant responses into the latest message bubble, reusing the existing SSE parsing approach.
- **Render markdown** in assistant messages (bold, italic, inline code, fenced code blocks, headings, lists) — in a webview this is HTML rendering rather than the Python tk.Text tag renderer.
- Add a backend **chat streaming command** mirroring `chat_with_context_stream`, including the "selected text" system prompt.
- Surface the existing **`custom_prompt`** field in the settings form (textarea + reset-to-default), wiring it to the already-supported backend config path.

Out of scope (deferred to a later change): TTS / read-aloud.

## Capabilities

### New Capabilities
- `chat-hotkey`: Detect Ctrl+C+Space as a distinct combo (sharing the arm window with Ctrl+C+C) and trigger the chat flow with the freshly copied selection.
- `chat-popup`: The chat popup window — layout, positioning, drag/close behavior, scrollable transcript, and input bar.
- `chat-streaming`: Backend chat request with conversation history and selected-text context, streaming assistant responses to the popup.
- `chat-markdown`: Rendering of markdown in assistant messages within the popup.

### Modified Capabilities
- `config-store`: The `custom_prompt` field becomes user-editable through the settings UI. (Backend storage already exists; this documents the requirement that the field be surfaced and editable.)

## Impact

- **Backend (`src-tauri/src/`)**: `hotkey.rs` (add Space branch + chat trigger), `main.rs` (chat trigger handler, register chat command + window wiring), `api.rs` (add chat streaming fn/command), `windows.rs` (create chat popup window). Chat session history held in memory for the popup's lifetime.
- **Frontend (`frontend/`)**: new `chat.html` / `chat.css` / `chat.js`; a small markdown-to-HTML renderer or minimal lib; updates to `settings.html` / `settings.js` to add the custom-prompt textarea.
- **Capabilities/ACL**: the chat window needs the same `core:window:allow-close` / `core:window:allow-start-dragging` grants the translate popup uses.
- **Dependencies**: markdown rendering may add one small frontend dependency (or a hand-rolled renderer to avoid a JS build step, consistent with the no-build-step frontend). No new Rust crates expected beyond what `api.rs`/`windows.rs` already use.
- **No breaking changes** to config format — `~/.quicktranslator_config.json` stays interoperable with the Python app.
