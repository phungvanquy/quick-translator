## 1. Multi-line textarea

- [x] 1.1 In `frontend/chat.html`, replace the `<input type="text" class="chat-input" id="chat-input">` with a `<textarea class="chat-input" id="chat-input" rows="1" placeholder="Ask a question…" spellcheck="false"></textarea>`.
- [x] 1.2 In `frontend/chat.css`, style the textarea: single-line baseline, `resize:none`, `overflow-y:auto`, line-height matched to the old input; keep focus border + placeholder styles.
- [x] 1.3 In `frontend/chat.js`, add an `input` listener that auto-grows the textarea: `height='auto'` then `height = min(scrollHeight, MAX_PX)` (MAX ≈ 120).

## 2. Keyboard send behavior

- [x] 2.1 Replace the current `keydown` handler so Enter (no Shift) sends and Ctrl+Enter sends; Shift+Enter falls through to insert a newline.
- [x] 2.2 Ignore Enter while an IME composition is active (`event.isComposing` / `keyCode === 229`) so confirming a Vietnamese/CJK composition does not send.
- [x] 2.3 In `send()`, after clearing `chatInput.value`, reset `chatInput.style.height` to the single-line baseline.

## 3. Typing indicator

- [x] 3.1 Add typing-indicator markup/CSS (e.g. animated `•••`) in `frontend/chat.css`, styled for the assistant bubble.
- [x] 3.2 In `send()`, insert the indicator into the new assistant bubble (`aiEl`) — implemented inside `addAiMessage()`, equivalent.
- [x] 3.3 In the turn's `appendInterim`, clear the indicator on the first delta (guard with a per-turn `firstChunk` flag) before writing streamed text.

## 4. Verify

- [x] 4.1 `cargo build` — delegated to CI (`.github/workflows/build.yml`). Frontend-only change; no Rust touched.
- [x] 4.2 Manual QA (Shift+Enter/Enter/Ctrl+Enter, empty input, height reset) → deferred to CLAUDE.md pre-release checklist.
- [x] 4.3 Manual QA (typing indicator → first token → markdown) → deferred to CLAUDE.md pre-release checklist.
- [x] 4.4 Manual QA (Vietnamese/CJK IME does not send on composition-confirm Enter) → deferred to CLAUDE.md pre-release checklist.
- [x] 4.5 Regression checks → deferred to CLAUDE.md pre-release checklist.
