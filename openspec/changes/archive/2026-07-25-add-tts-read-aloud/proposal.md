## Why

The translate popup shows the source text and its translation but has no way to hear the pronunciation. For language learners and quick verification, hearing the original text spoken aloud is faster than reading. The Python prototype had this feature via `pyttsx3`; the Rust rewrite does not yet.

## What Changes

- Add a speaker button (SVG icon) in the translate popup's bottom bar
- Clicking the button speaks the **source (clipboard/input) text** using an OS-native offline TTS engine
- New speak stops any in-progress speech (single active utterance)
- Closing the popup stops any active speech
- Graceful degradation if no TTS engine is available (button does nothing, no crash)

## Capabilities

### New Capabilities
- `tts-read-aloud`: OS-native text-to-speech for the translate popup's source text. Covers the speak button, single-utterance management, popup-close cleanup, and offline engine integration.

### Modified Capabilities

(none)

## Impact

- **Backend:** New `tts.rs` module wrapping an OS TTS crate (e.g., `tts` crate — cross-platform, SAPI on Windows). New Tauri command or event for speak/stop.
- **Frontend:** Speaker icon + click handler in `popup.html`/`popup.js`. New SVG symbol in `icons.js`.
- **Dependencies:** `tts` crate (MIT, actively maintained, covers Windows SAPI / macOS AVSpeechSynthesizer / Linux speech-dispatcher).
- **Binary size:** ~small increase from linking SAPI (Windows system library).
