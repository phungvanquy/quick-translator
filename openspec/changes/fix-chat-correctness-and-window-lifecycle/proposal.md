## Why

A code review of the chat flow found the user's question is sent to the model **twice** every turn: `chat.js` appends it to `history` before invoking `chat_send`, and `chat_stream` appends it again after the history. With an image attached the two copies disagree — the history copy is multimodal (`text` + `image_url`), the appended copy is text-only — so every vision turn asks the same question twice with different context. This silently degrades answer quality and wastes tokens on every chat message.

The same review surfaced three adjacent defects that share the chat send→stream→close path, so they are worth fixing in one pass rather than in three separate rounds of Windows QA:
- Closing a popup mid-stream does not cancel the request; it runs to completion emitting into a dead window, still billed.
- The chat popup closes on blur and is hidden from the taskbar, so clicking away to look something up destroys the conversation and any attached screenshots with no way back.
- Several failures are entirely invisible: an empty clipboard, a failed capture, and a failed window creation all return silently or write to a `eprintln!` that goes nowhere in a release build (`windows_subsystem = "windows"` means no console).

## What Changes

- **BREAKING (internal IPC):** remove the `question` parameter from the `chat_send` command. The frontend already owns conversation history by design, so the last entry in `history` *is* the question. Deleting the parameter makes the duplicate structurally impossible instead of relying on one of two call sites staying correct.
- Cancel an in-flight stream when its target window closes. A shared cancellation flag is checked between SSE reads so the HTTP request is dropped rather than drained.
- Reclassify the chat popup as a **persistent** window while the translate popup stays **ephemeral**:
  - chat: no blur-to-close, appears in the taskbar (alt-tab-able), still closes on Esc and the close button
  - translate: unchanged (blur-to-close, hidden from taskbar)
- Give silent failures a visible outcome. Highest value is the empty-clipboard case: pressing the hotkey with nothing selected currently does nothing at all, which reads as "the app is dead".
- Present API errors as one readable line with the raw detail collapsed and a retry control, replacing the current raw `⚠ Error: HTTP 401 — {"error":{...}}` dumped into a 460×220 popup.

Explicitly out of scope, to keep this change reviewable: accessibility work (focus rings, `aria-live`, reduced-motion), the shared-frontend refactor, the TTS button label, and a real logging facility. Each is tracked as its own follow-up.

## Capabilities

### New Capabilities
- `request-cancellation`: cancelling an in-flight streaming request when the window that requested it goes away, so no work or billing continues for a result nobody can see.
- `trigger-feedback`: making otherwise-silent trigger failures (empty clipboard, capture failure, window creation failure) visible to the user.

### Modified Capabilities
- `chat-streaming`: the request message list is built from the system prompt plus history alone; the question is no longer a separate parameter appended by the backend.
- `chat-popup`: the popup is a persistent window — blur no longer closes it, and it is reachable from the taskbar.
- `translation-streaming`: API failures are surfaced as a readable summary with retry, not a raw status-and-body dump.

## Impact

- **Backend:** `main.rs` (`chat_send` signature, trigger handlers, window close wiring), `api.rs` (`chat_stream` signature, cancellation checks in `stream_completion`, error payload shape), `windows.rs` (per-window chrome policy).
- **Frontend:** `chat.js` (invoke call, persistent-window behavior), `popup.js` (error/retry rendering), `chat.css`/`popup.css` (error + retry affordance).
- **No new dependencies.** Cancellation uses `std::sync::atomic`, already available.
- **Config format unchanged** — remains interoperable with the old Python app.
- **QA:** requires one Windows session with a real API key. Hotkey behavior, DPI placement, and taskbar/alt-tab behavior are not verifiable in CI.
