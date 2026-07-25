## Context

The translate popup shows source text and its streaming translation. The Python prototype had `pyttsx3` TTS for reading the source text aloud. The Rust rewrite has no TTS yet. The `#ic-volume` icon is already in the SVG sprite. Target is Windows primarily (SAPI5), but the chosen crate also supports macOS/Linux.

User requirement: TTS only reads the **input/clipboard text** (source), never the translated output.

## Goals / Non-Goals

**Goals:**
- Speaker button in translate popup footer that reads source text aloud
- OS-native offline speech (no network dependency)
- Single active utterance (new speak cancels in-progress)
- Speech stops when popup closes
- Graceful failure if no TTS engine available

**Non-Goals:**
- Reading the translated text aloud
- TTS in the chat popup
- User-configurable voice, rate, or volume (hardcode sensible defaults)
- Language auto-detection for voice selection (use system default voice)

## Decisions

### D1: Use the `tts` crate

**Choice:** [`tts`](https://crates.io/crates/tts) (MIT, actively maintained)

**Why over alternatives:**
- `windows-rs` + raw SAPI COM: more control but massive boilerplate, Windows-only
- `speech-dispatcher-sys`: Linux-only
- `tts` crate wraps SAPI (Windows), AVSpeechSynthesizer (macOS), speech-dispatcher (Linux) behind a unified API. Matches the "cross-platform crate" preference in CLAUDE.md.

**Trade-off:** Pulls in platform-specific linking (SAPI is a system lib, no extra DLL). Binary size increase is minimal.

### D2: Synchronous blocking TTS on a dedicated thread

**Choice:** Run `tts::Tts` on a dedicated `std::thread` (not tokio), communicate via `mpsc::Sender<TtsCommand>`.

**Why:**
- The `tts` crate is NOT `Send` on all platforms (COM thread affinity on Windows).
- A single dedicated thread owns the `Tts` instance for its lifetime.
- Commands: `Speak(String)`, `Stop`, `Shutdown`.
- The thread lives for the app's lifetime (spawned at startup alongside the rdev listener).

### D3: Tauri command for speak/stop

**Choice:** Two Tauri commands: `tts_speak(text: String)` and `tts_stop()`. Frontend calls them directly from the popup JS.

**Why over events:**
- Simpler than a bidirectional event protocol
- No response needed (fire-and-forget from frontend)
- Commands can access the `TtsHandle` via Tauri managed state

### D4: Button placement

**Choice:** In the popup footer, left of the "Esc to close" hint (before the copy button area).

**Why:** Follows reading order (action → hint → copy). Doesn't compete with copy button attention.

## Risks / Trade-offs

- **[Platform voice quality]** → System default voice varies. Acceptable — mirrors pyttsx3 behavior.
- **[No voice installed]** → `tts::Tts::new()` could fail on minimal Windows installs. Mitigation: if init fails, the `TtsHandle` sender is `None`, button click does nothing, no crash.
- **[Speech language mismatch]** → System voice may not match source text language. Non-goal for now; user can change their Windows default voice.
- **[`tts` crate maintenance]** → Widely used (200k+ downloads), MIT. If abandoned, the SAPI wrapper is thin enough to inline later.
