## Why

The translate/chat popup takes 350–800ms to appear after the hotkey fires. The critical path runs clipboard polling (50–500ms) and window creation (100–300ms) sequentially, then waits for a ready handshake (variable). Users perceive this as lag — a snappy translator should surface its popup in under 200ms when conditions are good.

## What Changes

- **Parallelize clipboard polling and window creation:** Currently sequential — clipboard must finish before the window is built. Since the window doesn't need the clipboard text until the API call starts, both can run concurrently.
- **Reduce clipboard poll interval:** Drop `thread::sleep` from 50ms to 20ms per iteration, keeping the same 10-retry budget. Clipboard updates on Windows are near-instant after Ctrl+C; faster polling catches the change earlier on average.
- **Reuse reqwest::Client across requests:** Create one shared `reqwest::Client` at app startup instead of rebuilding per-request. This eliminates repeated TLS context init and enables HTTP connection reuse.

## Capabilities

### New Capabilities
- `parallel-popup-init`: Concurrent clipboard + window creation flow, replacing the sequential trigger path
- `shared-http-client`: App-wide singleton reqwest::Client for API requests

### Modified Capabilities

(none — no existing spec-level requirements change)

## Impact

- `src-tauri/src/main.rs` — trigger functions restructured to spawn clipboard + window concurrently
- `src-tauri/src/clipboard.rs` — poll interval constant reduced
- `src-tauri/src/api.rs` — accept shared Client instead of building per-call; remove `Client::builder` from hot path
- `src-tauri/src/main.rs` — manage Client as Tauri state
- No dependency changes, no API/config format changes, no breaking changes
