## Why

The chat input is a single-line `<input type="text">` where Enter always sends, so users can't compose a multi-line question (no way to insert a newline). And when a turn starts, the assistant bubble is empty until the first token arrives — only the Send button shows a "…" — so the popup feels frozen for the first few hundred ms of latency.

## What Changes

- Replace the single-line chat `<input>` with a **`<textarea>` that supports multi-line input**, auto-growing up to a capped height, then scrolling.
- **Enter sends; Shift+Enter inserts a newline** (chat-standard). This preserves the existing Enter-to-send muscle memory while enabling multi-line composition. (Ctrl+Enter also sends, as a forgiving alias.)
- Show a **typing indicator inside the pending assistant bubble** from send until the first `chat://chunk` arrives, so the wait is visible where the answer will appear.

No breaking changes. Preserves: `chat_send` request flow, streaming render + final markdown, history cap (50), context strip / free-chat behavior, Esc / blur-to-close guard, draggable-header-only.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `chat-popup`: the send interaction changes (multi-line textarea; Enter sends / Shift+Enter newline) and a pending-response typing indicator is added.

## Impact

- `frontend/chat.html` — swap `<input class="chat-input">` for a `<textarea class="chat-input">`.
- `frontend/chat.css` — textarea styling, auto-grow constraints (min/max height), and typing-indicator styles.
- `frontend/chat.js` — keydown handling (Enter vs Shift+Enter vs Ctrl+Enter), auto-grow on input, reset height after send, render/remove the typing indicator around the first chunk.
- No backend, config, or dependency changes.
