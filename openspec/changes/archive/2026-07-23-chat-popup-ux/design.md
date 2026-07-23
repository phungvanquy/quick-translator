## Context

The chat popup input (`frontend/chat.html`) is `<input type="text" id="chat-input">`. `chat.js` binds `keydown` and sends on `Enter` unconditionally (`chat.js:141-143`). The assistant bubble is created empty in `send()` (`chat.js:81`) and only fills once `chat://chunk` events arrive; the sole "busy" cue is the Send button label switching to "…".

Constraints to preserve:
- The `send()` guard (`!question || streaming`) and the streaming lifecycle (`currentTurn` closure with `appendInterim`/`finish`) stay as-is.
- History cap (50) and context-strip / free-chat logic are untouched.
- Only the header is draggable; the input area must keep allowing text selection/caret (a `<textarea>` naturally does).

## Goals / Non-Goals

**Goals:**
- Multi-line composition via a `<textarea>` that auto-grows to a cap, then scrolls.
- Enter sends, Shift+Enter inserts a newline, Ctrl+Enter also sends.
- A typing indicator inside the pending assistant bubble until the first chunk.

**Non-Goals:**
- Rich input (attachments, markdown toolbar, slash-commands).
- Changing the send/stream backend contract (`chat_send`, `chat://chunk|done`).
- Persisting draft text across popup open/close.

## Decisions

### Decision: `<textarea>` with JS auto-grow, not a contenteditable
Swap `<input>` → `<textarea class="chat-input" rows="1">`. On `input`, reset `height='auto'` then set `height = min(scrollHeight, MAX)` (e.g. MAX ≈ 120px ≈ 5–6 lines); beyond MAX the textarea scrolls (`overflow-y:auto`). After a successful send, reset the height back to the single-line baseline along with clearing the value.
- **Alternative considered**: fixed multi-row textarea — rejected, wastes vertical space in a small popup when most questions are one line.
- **Alternative considered**: contenteditable div — rejected, more XSS/normalization surface for no benefit.

### Decision: Keydown routing — Enter sends, Shift+Enter newline, Ctrl+Enter sends
Replace the current handler:
```
keydown:
  if key === 'Enter' and not shiftKey:      preventDefault; send()   // Enter sends
  else if key === 'Enter' and ctrlKey:      preventDefault; send()   // Ctrl+Enter alias (fires even if Shift held? no — ctrl branch)
  // Shift+Enter (no ctrl): fall through → textarea inserts newline
```
Concretely: on `Enter`, send unless `shiftKey` is held; `Ctrl+Enter` always sends. Shift+Enter is the only combo that inserts a newline. This keeps existing Enter-to-send behavior (no regression for single-line users) while unlocking multi-line.
- **Alternative considered**: Enter=newline, Ctrl+Enter=send (IDE-style) — rejected, it silently breaks every existing user's Enter-to-send habit.

### Decision: Typing indicator is a transient child of the assistant bubble
In `send()`, after `addAiMessage()` creates `aiEl`, insert an indicator node (e.g. `<span class="typing">•••</span>` animated via CSS) as the bubble's content. In `appendInterim`, on the first delta, clear the indicator before writing text (guard with a per-turn `firstChunk` flag). `finish()` already replaces content with rendered markdown, so no cleanup needed there. If the stream produces zero chunks then `done`, `finish()` renders empty — acceptable and unchanged from today.

### Decision: Reset textarea height on send inside the existing send() flow
`send()` already does `chatInput.value = ''`. Add `chatInput.style.height = ''` (or the baseline) right after, so the box collapses back to one line for the next question.

## Risks / Trade-offs

- **Auto-grow pushing the transcript** → the input bar is `flex-shrink:0`; as it grows the transcript (`flex:1`) shrinks. Capping MAX height keeps the transcript usable. Mitigation: keep MAX modest (~120px) and verify on the 320px min window height.
- **Enter-in-IME composition sending prematurely** (CJK/Vietnamese input methods) → pressing Enter to confirm a composition could fire send. Mitigation: check `event.isComposing` (and/or `keyCode === 229`) and ignore Enter while composing. This matters for the app's Vietnamese/CJK target users — call it out in QA.
- **Typing indicator lingering if first chunk is empty-string** → backend skips empty deltas (`api.rs` guards `!delta.is_empty()`), so the first delivered chunk is always non-empty; clearing on first `appendInterim` is safe.
