## 1. Shared HTTP Client

- [x] 1.1 Create `HttpClient` newtype wrapper struct in `api.rs`, construct a `reqwest::Client` with rustls + 15s connect timeout
- [x] 1.2 Register `HttpClient` as Tauri managed state in `main.rs` (build once at startup, pass to `app.manage()`)
- [x] 1.3 Update `stream_completion` to accept `&reqwest::Client` parameter instead of building its own
- [x] 1.4 Update `translate_stream` and `chat_stream` to accept and forward the shared client
- [x] 1.5 Update `test_connection` to accept a shared client reference and apply per-request total timeout
- [x] 1.6 Update `chat_send` and `handle_translate_trigger` call sites to extract client from Tauri state and pass it through

## 2. Reduce Clipboard Poll Interval

- [x] 2.1 Change `thread::sleep(Duration::from_millis(50))` to `thread::sleep(Duration::from_millis(20))` in `clipboard.rs`

## 3. Parallelize Clipboard + Window Creation

- [x] 3.1 Refactor `handle_translate_trigger`: spawn clipboard polling (`spawn_blocking`) and window creation concurrently via `tokio::join!`, then gate on both results before proceeding to the ready handshake + stream
- [x] 3.2 Refactor `handle_chat_trigger`: same concurrent pattern — clipboard + chat window creation run in parallel, show window after both complete
- [x] 3.3 Verify that the "clipboard empty → early return" path still correctly avoids showing an unused popup window

## 4. Verification

- [ ] 4.1 `cargo build` passes with no warnings (no Rust toolchain in current env — verify locally)
- [ ] 4.2 `cargo clippy` passes (no Rust toolchain in current env — verify locally)
