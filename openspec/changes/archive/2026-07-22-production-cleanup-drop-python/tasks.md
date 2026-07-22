## 1. Delete Python reference

- [x] 1.1 Delete the `python-reference/` directory in full (all `.py` sources, `icon.ico`, `icon.png`, `installer.iss`, `requirements.txt`)
- [x] 1.2 Remove the `*.py[cod]` line from `.gitignore` (also removed now-dead `__pycache__/`, `build/`, `dist/`, `*.spec` PyInstaller lines)
- [x] 1.3 Grep the repo for stray Python references (`python-reference`, `pyinstaller`, `requirements.txt`, `\.py\b`) outside `openspec/` and confirm none remain in build/config/docs (docs clean; remaining mentions are intentional historical/design context. NOTE: source-code parity comments like `// parity with api.py` in `src-tauri/src/*.rs` + `frontend/*.js` still reference deleted files — left as optional follow-up, outside build/config/docs scope)

## 2. Rewrite CLAUDE.md

- [x] 2.1 Remove the entire "Python Reference Implementation" section and the "Python Build Notes" section
- [x] 2.2 Update the Overview line so it no longer calls Python the "reference implementation"
- [x] 2.3 In the staged-rewrite table, mark Stage 2 as **Implemented** and redefine Stage 3 as "TTS read-aloud + roadmap ideas (history/log, language auto-detect)"
- [x] 2.4 Trim the "Identified Improvements" list to items still relevant to the Rust app; drop Python-file-specific ones (e.g. `os._exit` in `tray.py`, `main.py` split)
- [x] 2.5 Keep the Rust/Tauri architecture + key-design-decisions sections intact (do not remove Rust context)

## 3. Rewrite Readme.md

- [x] 3.1 Remove the "Setup (Python reference)" section
- [x] 3.2 Remove the "Build as .exe (Python reference)" section and the Inno Setup note
- [x] 3.3 Rewrite the intro/Note so Rust + Tauri is presented as the only implementation (drop the "being rewritten / behavioral reference" framing)
- [x] 3.4 Ensure setup/build instructions point at the Tauri flow (`cargo tauri build`, CI in `.github/workflows/build.yml`)

## 4. Capture deferred TTS + roadmap

- [x] 4.1 Confirm the `tts-read-aloud` spec is present in this change and reads correctly (source-text, stop-in-progress, stop-on-close, offline engine)
- [x] 4.2 Add a short "Stage 3 roadmap" note to CLAUDE.md: TTS (spec'd), history/log (idea), language auto-detect (idea)

## 5. Archive stage2-chat-popup

- [x] 5.1 Move the 5 open verification tasks (8.1, 8.2, 8.4, 8.5, and 1.3) into a pre-release manual QA checklist (in CLAUDE.md or release notes) so they aren't lost
- [x] 5.2 Archive the `stage2-chat-popup` change via the archive workflow

## 6. Verify

- [x] 6.1 Confirm `python-reference/` is gone and `git status` shows the deletions staged/clean
- [x] 6.2 Re-read CLAUDE.md and Readme.md end-to-end for any dangling Python references or contradictions
- [x] 6.3 Confirm the Rust/Tauri build config (`src-tauri/tauri.conf.json`, `.github/workflows/build.yml`) is untouched by this change
