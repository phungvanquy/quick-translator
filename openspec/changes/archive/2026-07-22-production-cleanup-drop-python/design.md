## Context

Quick Translator began as a Python/Tkinter app and is being ported to Rust + Tauri 2.x. Stages 1 (translate flow) and 2 (chat popup) are now fully implemented in `src-tauri/` + `frontend/`, and CI builds only the Tauri app. The `python-reference/` tree was retained as the behavioral reference for the remaining rewrite, but an audit shows its residual reference value has collapsed to a single unported feature — the TTS read-aloud button. The other nominal "Stage 3" items (history/log, language auto-detect) have no Python implementation; they are wishlist entries in CLAUDE.md.

This change is a cleanup: capture the one real behavior as a spec, then delete Python and realign the docs to a Rust-only narrative. It is mostly deletion + documentation with one new spec; a design doc is included because deleting the reference is irreversible-in-spirit (the behavioral source of truth goes away) and we want the capture decision recorded.

## Goals / Non-Goals

**Goals:**
- Preserve the TTS read-aloud behavior as a testable spec before the code that defines it is deleted.
- Remove `python-reference/` and all Python-specific repo cruft.
- Bring CLAUDE.md and Readme.md in line with reality: Rust is the only build; Stage 2 is done; Stage 3 = TTS + roadmap ideas.
- Close out the `stage2-chat-popup` change cleanly.

**Non-Goals:**
- Implementing TTS in Rust. This change only captures the spec; the implementation is a deferred Stage 3 task.
- Implementing history/log or language auto-detect. They remain future roadmap ideas.
- Any change to the shipping Rust/Tauri runtime behavior or CI pipeline.
- Preserving Python git history beyond what `git` already retains (the files remain recoverable from history after deletion).

## Decisions

**Decision: Capture TTS as a full spec, not just a roadmap note.**
The 🔊 button has non-obvious behavior worth pinning down (reads *source* not *translation*; stop-in-progress on re-trigger; stop on close; offline engine). Writing it as `tts-read-aloud/spec.md` makes it a ready-to-build Stage 3 task with acceptance scenarios, so no one has to reverse-engineer `tts.py` from git history later.
- *Alternative considered*: a one-line roadmap note. Rejected — loses the specific behaviors and forces rediscovery.

**Decision: Delete `python-reference/` wholesale rather than trimming it.**
Once TTS is captured, nothing in the tree is a live reference. A partial delete (keep `tts.py` "just in case") would leave an orphaned, un-runnable file and re-muddy the "what's the real build" story. Git history preserves everything if needed.
- *Alternative considered*: keep the directory until TTS is ported in Rust. Rejected in explore — the spec capture replaces the need, and the user chose the roadmap approach.

**Decision: Archive `stage2-chat-popup` now.**
Its 5 open tasks are all "needs a Windows run" verification (8.1, 8.2, 8.4, 8.5) — no code work remains. Blocking the archive on manual QA that can't run in this environment would leave a done feature looking perpetually unfinished. Verification moves to a pre-release manual checklist.
- *Alternative considered*: leave it open until Windows QA. Rejected — conflates "code complete" with "QA signed off"; the checklist captures the QA intent without holding the change hostage.

**Decision (deferred, recorded for the implementer): Rust TTS approach.**
When TTS is built, prefer a lightweight offline engine binding — the `tts` crate (which wraps SAPI on Windows / the platform speech API) or a small Tauri command shelling to the OS speech facility. Keep it non-blocking (spawn on a background task) and expose a stop handle, mirroring `tts.py`'s single-utterance model. This is guidance, not part of this change's implementation.

## Risks / Trade-offs

- **Deleting the behavioral reference before Stage 3 is built** → Mitigated by the `tts-read-aloud` spec capturing the behavior, and by git history retaining the full Python source for recovery.
- **Docs rewrite drops context future contributors relied on** → Mitigated by keeping the Rust architecture/design-decisions sections of CLAUDE.md intact; only Python-specific and stale-status content is removed.
- **Archiving stage2 hides that manual QA never ran** → Mitigated by explicitly moving the 5 verification items into a pre-release checklist (in tasks.md / release notes) rather than silently dropping them.

## Migration Plan

1. Land the `tts-read-aloud` spec (this change).
2. Delete `python-reference/` and the `.gitignore` Python line.
3. Rewrite CLAUDE.md and Readme.md.
4. Archive `stage2-chat-popup`.
5. Rollback strategy: everything is in git — `git revert` the cleanup commit restores Python and docs; the captured spec remains valid regardless.
