## Context

Four defects on the chat send → stream → close path, found by code review rather than by a bug report. Grouped into one change because they touch the same functions and because the project's real bottleneck is manual Windows QA: hotkeys, DPI placement, and taskbar behavior are not verifiable in CI, so it is cheaper to validate them together than in three separate sessions.

Current state that constrains the design:

- The frontend owns conversation history (an existing, deliberate decision). `chat_send` additionally takes `question`, and `chat_stream` appends it after the history — hence the duplicate.
- `stream_completion` in `api.rs` is the single shared streaming core for both flows. It emits errors *as content chunks* on the same event as real tokens, so the frontend cannot distinguish an error from the model's output.
- No `on_window_event` wiring exists anywhere in the app, and no atomics are in use. `tokio-util` (and its `CancellationToken`) is not a dependency.
- Both popups reuse fixed window labels (`translate-popup`, `chat-popup`) and each creation path closes the existing window with that label first.
- CLAUDE.md records a bug that has shipped three times: emitting at a window that may not have attached its listeners yet drops the payload silently. Any new backend→frontend payload must use a query string, a handshake, or a pull.

## Goals / Non-Goals

**Goals:**
- Make the duplicate question structurally impossible, not merely absent.
- Stop paying for streams whose window is gone.
- Let the user click away from a chat session without losing it.
- Replace silent failures and raw error dumps with something a user can act on.
- Add no new dependencies.

**Non-Goals:**
- Accessibility work (focus rings, `aria-live`, reduced-motion) — separate change.
- Extracting shared frontend chrome (`window-chrome.js`, shared markdown CSS) — separate change, deliberately sequenced *after* this one so it consolidates the final blur-to-close behavior rather than an intermediate one.
- A real logging facility. This change gives failures a user-visible outcome; durable diagnostics is its own change with its own decisions about file location and rotation.
- The TTS button reading the source text. Confirmed intentional; only its label needs work, which belongs with the other polish.
- Persisting popup size/position, per-message copy, regenerate, scroll anchoring.

## Decisions

### 1. Delete the `question` parameter rather than the duplicate append

`chat_send(selected_text, question, history)` becomes `chat_send(selected_text, history)`; `chat_stream` stops appending and sends `[system] + history`.

The narrow fix — drop the append and keep the parameter — leaves two call sites that must agree about who owns the last turn. That is exactly the arrangement that produced this bug. Removing the parameter makes the invariant enforced by the type signature: there is only one place the question can come from.

*Alternative considered:* keep `question` and have the backend own the append, with the frontend not pushing until the response completes. Rejected — the frontend needs the user bubble on screen immediately, and it already owns history. Splitting ownership by timing is what went wrong.

**Consequence:** `chat_stream`'s `question` argument goes away too, so its `messages` assembly gets simpler. The system prompt still depends on `selected_text`, which stays a parameter.

### 2. Cancellation via a label-keyed flag registry, not a token library or a liveness probe

New state in `api.rs`, managed like the existing `HttpClient`:

```
StreamRegistry(Mutex<HashMap<String, Arc<AtomicBool>>>)
  register(label) -> Arc<AtomicBool>   // cancels+replaces any existing entry
  cancel(label)                        // sets the flag, removes the entry
```

`stream_completion` takes the `Arc<AtomicBool>` and checks it once per loop iteration, immediately after each read returns. On cancel it drops the response (killing the connection) and returns without emitting.

This single mechanism covers both ways a stream becomes pointless:
- **window closed** — an `on_window_event` handler for `Destroyed` calls `cancel(label)`
- **window replaced** — `register` cancels the prior entry, so a second hotkey press retires the first stream

The replace case matters and is easy to miss: labels are reused, so without it an old stream would keep emitting into a *new* popup that happens to carry the same label.

*Alternatives considered:*
- `tokio_util::sync::CancellationToken` — the right abstraction, but adding a dependency for one `AtomicBool` fails the project's "lightest option" rule.
- Probing `app.get_webview_window(label).is_some()` each iteration — no new state at all, but it cannot distinguish "closed" from "closed and reopened", so it silently mishandles the replace case.
- Checking whether `emit` failed — does not work; `emit` returns `Ok` for a closed window because events go through the manager.

*Ordering:* `Ordering::Relaxed` is sufficient. This is a single flag with no other memory being published alongside it, and a one-iteration delay in observing it is harmless.

### 3. Errors get their own event with a structured payload

Errors currently ride the chunk event, which is why they cannot be styled, collapsed, or retried. Introduce `translate://error` / `chat://error` carrying:

```
{ summary: String, detail: String, retryable: bool }
```

`summary` is classified from the failure, so the popup shows one readable line:

| Condition | Summary |
|---|---|
| 401 / 403 | authentication failed — check the API key in Settings |
| 429 | rate limited — try again shortly |
| 5xx | the server reported an error |
| connect / transport error | could not reach the endpoint |
| idle timeout | the response timed out |
| other non-2xx | includes the status code |

`detail` keeps the raw status plus response body, truncated (the existing `test_connection` already truncates to 200 chars — reuse that bound) so an unrecognized server error stays diagnosable. The frontend renders `summary` with `detail` behind a disclosure, and a retry control when `retryable`.

The missing-API-key case keeps its current inline text: it is guidance, not a failure, and it must not offer a retry that would fail identically.

### 4. Retry re-issues from each side's existing source of truth

- **Translate:** a `translate_retry` command. The popup already holds the original text (its query string) and the backend already holds the config, so retry needs no new stored state.
- **Chat:** entirely frontend. History already ends with the failed turn's user entry, so retry re-invokes `chat_send` with history unchanged, replacing the errored bubble. Nothing to push, nothing to pop.

### 5. Window chrome becomes an explicit per-window policy

| | translate | chat |
|---|---|---|
| `always_on_top` | true | true |
| `skip_taskbar` | true | **false** |
| blur → close | yes | **no** |
| Esc / close button | yes | yes |

The distinction is recoverability. A lost translation costs one hotkey press; a lost chat session costs a conversation and its screenshots. `skip_taskbar(false)` is what makes "click away" survivable — without it the window is unreachable once it loses focus.

This also repairs `chat://closed` → release captures. That handler is currently reachable by an accidental blur, discarding images the user still wanted; once close is deliberate, releasing on close is correct.

`always_on_top` stays true for chat so it remains visible while the user works in the source application — the screenshot flow depends on it. Flagged as an open question for QA rather than decided from here.

### 6. Trigger feedback is a toast window, positioned at the cursor

A frameless, transparent, non-focusing window near the cursor that closes itself after ~2s.

Positioned at the cursor because that is where the user is looking, and because it matches every other surface in this app. A corner notification for "you haven't selected anything" is a worse answer to a question the user asked with their hands at the cursor.

Message passes via **query string**, not an emit — this is precisely the trap CLAUDE.md documents three shipped instances of.

`focused(false)` plus `skip_taskbar(true)` is load-bearing: stealing focus from the user's application would be worse than the silence being replaced. It also means no blur-close logic — the only dismissal is the timer.

*Alternative considered:* `tauri-plugin-notification` for native Windows toasts. No UI code, but it adds a dependency, lands in the Action Center where it can be delayed or missed, and appears in the wrong corner of the wrong monitor for a cursor-anchored app.

**Reuses the existing DPI-safe path:** the toast is positioned with the same build-hidden → `set_position(PhysicalPosition)` → `show()` sequence as both popups, so it inherits the multi-monitor and scale-factor handling instead of re-deriving it.

### 7. Clean-code constraints for this change

The user asked specifically for clean code, so these are commitments, not aspirations:

- The window-chrome table above is expressed as **data**, not as two divergent builder chains. `windows.rs` currently has four near-identical builder blocks; this change consolidates the popup ones behind one helper parameterized by the differing fields. Anything beyond the two popups (settings, overlay, toast) stays as-is — folding genuinely different windows into one abstraction would be worse than the duplication.
- `stream_completion` keeps one exit path for cancellation. No cancel check scattered through the parse loop.
- Error classification lives in exactly one function, shared by both flows.
- No new comments restating what the code does. The cancellation flag and the toast's `focused(false)` get one line each, because both encode a non-obvious *why*.
- Delete `question` everywhere rather than leaving it unused with an underscore prefix.

## Risks / Trade-offs

- **A chat popup left open indefinitely holds its screenshots in RAM.** → Already bounded to 2 images by `MAX_IMAGES`. Removing blur-close makes long-lived sessions more likely, so the existing RSS check in the QA checklist becomes more meaningful, not less. Not adding a timeout: silently discarding a user's context is the behavior being removed.
- **`always_on_top` chat may feel intrusive now that it persists.** → One-line change if QA says so. Recorded as an open question rather than pre-emptively decided.
- **Cancellation could fire against the wrong stream if labels were ever generated dynamically.** → They are fixed constants. If that changes, `register`'s cancel-and-replace is the single place that needs revisiting.
- **The toast cannot report a window-creation failure**, since it is itself a window. → Accepted. A failure to create any window is a different class of problem, and the durable-logging change is where it gets addressed.
- **Removing the `question` parameter breaks the frontend/backend contract.** → Internal IPC only, both sides in this repo, changed in the same commit. Compiler catches the Rust side; the JS side is a single call site.
- **`translate://error` is a new event at a window that may still be starting up.** → Errors can only occur after `popup://ready` has released the stream, so the listener is provably attached. This is the one case where emitting is safe, and the reason is worth stating in the spec rather than the code.

## Open Questions

- **OQ1:** Should the chat popup keep `always_on_top` now that it persists and appears in the taskbar? Resolve during Windows QA by using it over a real editor for a few minutes.
- **OQ2:** Is ~2s the right toast duration for "nothing selected"? Long enough to read, short enough not to linger over the user's work. Tune during QA.
