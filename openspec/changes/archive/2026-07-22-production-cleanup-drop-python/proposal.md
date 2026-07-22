## Why

The project has fully moved to Rust + Tauri: Stages 1 and 2 (translate flow + chat popup) are implemented in `src-tauri/` + `frontend/`, and CI builds only the Tauri app. The `python-reference/` tree is now dead weight — it ships nothing, confuses the "what's the real build" story, and its docs (CLAUDE.md marking Stage 2 "Pending", Readme's Python setup/build sections) have drifted out of sync with reality. Before deleting it we must capture the one behavior it still uniquely defines: the TTS read-aloud button.

## What Changes

- Capture the TTS read-aloud behavior (the 🔊 button in the translate popup) as a first-class spec so it survives the Python deletion and becomes the concrete Stage 3 kickoff task.
- **BREAKING (repo layout)**: Delete `python-reference/` in full — all `.py` sources, `icon.ico`/`icon.png`, `installer.iss`, `requirements.txt`.
- Drop the `*.py[cod]` line from `.gitignore` (no Python left to ignore).
- Rewrite CLAUDE.md: remove all Python-reference sections and the Python build notes; mark Stage 2 as implemented; redefine Stage 3 as "TTS read-aloud + roadmap ideas (history/log, language auto-detect)".
- Rewrite Readme.md: remove "Setup (Python reference)" and "Build as .exe (Python reference)" sections; Rust/Tauri becomes the only build story.
- Archive the `stage2-chat-popup` change — its 5 open tasks are all Windows-run verification (no code work); those move to a pre-release manual checklist.

Note: history/log and language auto-detect were never implemented in Python (they are wishlist items in CLAUDE.md), so nothing is lost by deleting Python — they remain future roadmap ideas.

## Capabilities

### New Capabilities
- `tts-read-aloud`: Speak the popup's source text aloud via an OS-native TTS engine, triggered by a 🔊 button in the translate popup; a new speak request stops any in-progress speech. Ports the Python `tts.py` behavior (rate 160, volume 0.9, non-blocking) to Rust/Tauri.

### Modified Capabilities
<!-- None: no existing spec's requirements change. The translate-popup spec gains a button via the new tts-read-aloud capability, but its own requirements are unchanged. Docs/cleanup are not spec-governed behavior. -->

## Impact

- **Deleted**: `python-reference/` (14 files), `.gitignore` Python line.
- **Docs**: `CLAUDE.md`, `Readme.md` rewritten to a Rust-only narrative.
- **OpenSpec**: new `tts-read-aloud` spec; `stage2-chat-popup` change archived.
- **Future code** (deferred, not in this change): a Rust TTS implementation in `src-tauri/` + a 🔊 button in `frontend/popup.*`, guided by the new spec.
- No change to the shipping Rust/Tauri build or CI in this cleanup.
