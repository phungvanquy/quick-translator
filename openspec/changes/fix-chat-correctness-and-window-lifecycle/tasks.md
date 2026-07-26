## 1. Duplicate question fix

- [x] 1.1 Remove the `question` parameter from `chat_stream` in `api.rs`; build `messages` as `[system] + history` with nothing appended after the history
- [x] 1.2 Remove the `question` parameter from the `chat_send` command in `main.rs` and pass through only `selected_text` + `history`
- [x] 1.3 Update the `invoke('chat_send', …)` call in `chat.js` to stop sending `question`; confirm `history.push` of the user turn stays *before* the invoke so the bubble still appears immediately
- [x] 1.4 Verify by inspection that a two-turn conversation produces `[system, user Q1, assistant A1, user Q2]` — Q2 exactly once, no trailing duplicate
- [x] 1.5 Verify an image turn sends one multimodal entry and no text-only copy of the same question

## 2. Stream cancellation

- [x] 2.1 Add `StreamRegistry(Mutex<HashMap<String, Arc<AtomicBool>>>)` to `api.rs` with `register(label)` (cancels and replaces any existing entry) and `cancel(label)`; register it via `.manage()` in `main.rs`
- [x] 2.2 Thread an `Arc<AtomicBool>` into `stream_completion`; check it once per loop iteration right after each read returns, and return through a single exit path that emits nothing
- [x] 2.3 Call `register` at the start of `translate_stream` and `chat_stream`, keyed by the target window label
- [x] 2.4 Wire `on_window_event` for `Destroyed` on both popups to call `cancel(label)`
- [ ] 2.5 Verify the replace path: two translate triggers in a row retire the first stream, and the second popup shows only its own tokens
- [ ] 2.6 Verify closing the translate popup mid-stream leaves an in-flight chat stream running

## 3. Error presentation and retry

- [x] 3.1 Add a single error-classification function in `api.rs` mapping failures to `{ summary, detail, retryable }` per the design's table; truncate `detail` to the same 200-char bound `test_connection` already uses
- [x] 3.2 Emit `translate://error` / `chat://error` with that payload instead of writing error text onto the chunk event; keep the missing-API-key path as inline guidance with no retry
- [x] 3.3 Add a `translate_retry` command that re-runs `translate_stream` for the popup's existing text and current config
- [x] 3.4 Render the error state in `popup.js`: summary line, `detail` behind a disclosure, retry control when `retryable`; retry returns the popup to its loading state
- [x] 3.5 Render the error state in `chat.js`: replace the errored bubble, re-enable Send, and retry by re-invoking `chat_send` with history unchanged
- [x] 3.6 Add error/disclosure/retry styles to `popup.css` and `chat.css` using existing `--danger` / `--btn-secondary-*` tokens; no literal hex outside `theme.css`
- [ ] 3.7 Verify a bad API key shows a readable summary (not a raw JSON body), the detail expands, and retry re-issues the request

## 4. Window chrome policy

- [x] 4.1 Consolidate the two popup builder blocks in `windows.rs` behind one helper parameterized by the fields that differ (label, url, size, min size, `skip_taskbar`); leave settings, overlay, and toast windows as separate paths
- [x] 4.2 Set `skip_taskbar(false)` for the chat popup, `true` for translate
- [x] 4.3 Remove the blur-to-close handler from `chat.js`; keep Esc and the close button. Leave `popup.js` blur-close intact
- [x] 4.4 Confirm `chat://closed` still releases captures on deliberate close, and is no longer reachable via blur
- [ ] 4.5 Verify DPI-safe positioning still holds after the builder consolidation — both popups anchor at the cursor on a scaled and a non-primary monitor

## 5. Trigger feedback toast

- [x] 5.1 Add `toast.html` / `toast.css` / `toast.js`: message read from the query string (never an emit), self-closes after ~2s, reuses `theme.css` tokens and the icon sprite
- [x] 5.2 Add `show_toast` to `windows.rs` — frameless, transparent, `always_on_top(true)`, `skip_taskbar(true)`, `focused(false)`, positioned with the existing build-hidden → `set_position(PhysicalPosition)` → `show()` sequence
- [x] 5.3 Show a toast in `handle_translate_trigger` when the clipboard yields no usable text, replacing the silent early return
- [x] 5.4 Show a toast in `handle_screenshot_trigger` on capture failure or zero monitors, and release any partially stored capture state
- [x] 5.5 Replace the `eprintln!`-only window-creation failure paths with a toast where a window can still be shown
- [ ] 5.6 Verify the toast does not steal focus (keep typing in another app while it appears), disappears on its own, and does not appear on a successful trigger

## 6. Verification and cleanup

- [ ] 6.1 `cargo build` and `cargo clippy` clean; no unused parameters left behind and no `_`-prefixed leftovers from the removed `question` — BLOCKED: no Rust toolchain in this environment, must be verified on Windows CI
- [x] 6.2 Re-read the touched files for comments that restate the code; keep only the cancellation flag and the toast's `focused(false)` rationale
- [x] 6.3 Grep the frontend for literal hex added by this change; all colors must come from `theme.css` tokens
- [x] 6.4 Add the new QA items to the CLAUDE.md pre-release checklist: chat survives blur and is alt-tab-able, cancellation on close, empty-clipboard toast, error summary + retry
- [x] 6.5 Update the CLAUDE.md architecture notes for the new `chat_send` signature, the stream registry, and the toast window
- [x] 6.6 Record OQ1 (chat `always_on_top`) and OQ2 (toast duration) in the checklist so QA resolves them
