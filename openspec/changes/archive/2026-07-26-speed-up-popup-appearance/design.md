## Context

The translate/chat trigger path runs three phases sequentially: clipboard poll → window build → ready handshake → stream. Clipboard polling (`thread::sleep` in a loop) and window creation (WebView2 init + HTML parse) are the two heaviest phases, together accounting for 150–800ms of perceived latency. Additionally, `reqwest::Client` is rebuilt on every API call, discarding TLS sessions and connection pools.

The backend is async (tokio), so running clipboard and window creation concurrently is structurally straightforward — the window doesn't need clipboard text until the streaming API call begins.

## Goals / Non-Goals

**Goals:**
- Reduce hotkey-to-visible-popup latency by running clipboard + window creation concurrently
- Catch clipboard changes faster via tighter poll interval
- Eliminate per-request `reqwest::Client` overhead
- Keep changes minimal and safe — no window lifecycle changes, no new crates

**Non-Goals:**
- Window pooling / reuse (deferred — higher complexity, separate change)
- Removing the `popup://ready` handshake (still needed since we create a fresh window each time)
- Changing the hotkey detection path (already allocation-free, sub-ms)
- Reducing the ready-handshake timeout (2s is already a generous fallback)

## Decisions

### 1. Parallel clipboard + window via `tokio::join!`

**Decision:** Spawn clipboard polling (`spawn_blocking`) and window creation concurrently using `tokio::join!`, gate on both completing before starting the API stream.

**Why over sequential:** Shaves the shorter of the two durations off the critical path (typically 100-300ms). No ordering dependency exists — the window needs text only for the API call, not for building the WebView.

**Why not `select!`:** Both results are needed. `join!` is correct — we need the clipboard text AND the window to be ready.

**Alternative rejected — clipboard on a separate pre-fired channel:** Over-engineering for a poll that completes in 20-200ms.

### 2. Clipboard poll interval: 50ms → 20ms

**Decision:** Reduce `thread::sleep(50ms)` to `thread::sleep(20ms)`, keeping 10 iterations (total budget 200ms instead of 500ms).

**Why 20ms:** Windows clipboard propagation is typically <10ms after a Ctrl+C. Polling at 20ms hits the sweet spot: fast enough to catch immediate changes, slow enough to avoid busy-looping. The 200ms total budget still covers slow applications (Office, browsers with large selections).

**Alternative rejected — 10ms interval:** Aggressive; would thrash arboard's Win32 clipboard calls on underpowered machines. Marginal gain over 20ms.

**Alternative rejected — WM_CLIPBOARDUPDATE subscription:** Would eliminate polling entirely but requires a hidden HWND + message loop integration with Tauri's event loop — invasive change for a ~30ms average improvement over 20ms polling.

### 3. Shared `reqwest::Client` as Tauri managed state

**Decision:** Build one `Client` at app startup, store as `app.manage(HttpClient(client))`, pass into `stream_completion` / `test_connection`.

**Why:** `reqwest::Client` is designed to be reused — it pools connections, caches DNS, reuses TLS sessions. Building per-request pays ~5-20ms in TLS context setup and discards warm connections.

**Why Tauri state over `once_cell`:** Consistent with existing patterns (`ConfigState` is already managed state). Testable, no global mutable.

## Risks / Trade-offs

- **[Shorter clipboard budget]** Total poll window shrinks from 500ms to 200ms. Risk: very slow clipboard producers (remote desktop forwarding, old-gen anti-malware hooking clipboard) might not propagate in time. → Mitigation: 200ms is still generous; the old Python app used ~300ms budget and never hit issues. If regression reports surface, bump to 15 iterations (300ms).

- **[Parallel ordering edge case]** If window creation finishes but clipboard returns empty, we've created a window for nothing and must close it. → Mitigation: already handled — `handle_translate_trigger` returns early on empty text, and a created-but-unused popup with no streaming just gets closed on next trigger or blur.

- **[Client lifetime]** A long-lived `reqwest::Client` may hold stale DNS or idle connections to a changed `base_url`. → Mitigation: `reqwest` already expires idle connections; changing `base_url` in Settings is rare and the next request re-resolves DNS regardless of pool state.
