## 1. Backend TTS Module

- [x] 1.1 Add `tts` crate to `Cargo.toml` dependencies
- [x] 1.2 Create `src-tauri/src/tts.rs`: `TtsHandle` struct wrapping `mpsc::Sender<TtsCommand>`, spawn dedicated thread owning `tts::Tts` instance, commands: `Speak(String)`, `Stop`, `Shutdown`
- [x] 1.3 Handle init failure gracefully: if `Tts::new()` fails, `TtsHandle` holds `None` sender; speak/stop become no-ops

## 2. Tauri Commands

- [x] 2.1 Register `tts_speak` and `tts_stop` Tauri commands in `main.rs`
- [x] 2.2 Store `TtsHandle` as Tauri managed state, commands send to the TTS thread

## 3. Frontend Integration

- [x] 3.1 Add speaker button in `popup.html` footer (uses existing `#ic-volume` icon), positioned left of the hint text
- [x] 3.2 In `popup.js`: on speaker click, invoke `tts_speak` with the source text; on popup close (Esc/blur/close-btn), invoke `tts_stop`

## 4. Verification

- [ ] 4.1 `cargo build` passes (verify in CI — no local Rust toolchain)
