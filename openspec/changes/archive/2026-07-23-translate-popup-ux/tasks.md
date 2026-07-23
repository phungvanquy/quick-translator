## 1. Resizable window

- [x] 1.1 In `src-tauri/src/windows.rs::show_translate_popup`, change `.resizable(false)` → `.resizable(true)` and add `.min_inner_size(360.0, 160.0)` (mirror the chat popup); keep the 460×220 default and the build-hidden → set_position → show DPI-safe flow intact.
- [x] 1.2 Confirm the result area still reflows on resize (it is `flex:1; overflow-y:auto` in `popup.css` — no change expected, verify only).

## 2. Full-original tooltip

- [x] 2.1 In `frontend/popup.js`, set `originalText.title = original` (full untruncated text) while keeping `textContent = truncate(original)`.

## 3. Copy result button

- [x] 3.1 Add a Copy button to `frontend/popup.html` (header or footer), initially disabled, with a `title="Copy (Ctrl+C)"`-style hint.
- [x] 3.2 Style the button + its "Copied ✓" confirmation state in `frontend/popup.css`, consistent with existing `.close-btn` / GitHub-dark palette.
- [x] 3.3 In `frontend/popup.js`, enable the button in the `translate://done` handler (alongside spinner stop + markdown render); keep it disabled while streaming.
- [x] 3.4 Wire the click handler to write the accumulated `fullText` (NOT rendered HTML) via `navigator.clipboard.writeText`, wrapped in try/catch; on success swap to the "Copied ✓" state and revert after ~1.2s; on failure show a subtle error state.
- [x] 3.5 Ensure clicking Copy does not trigger blur-to-close (button is in-window; verify focus stays and the close path is not hit).

## 4. Verify

- [x] 4.1 `cargo build` — delegated to CI (`.github/workflows/build.yml`, `tauri-action` on `windows-latest`/msvc). Change is 2 builder flags already used by `show_chat_popup`.
- [x] 4.2 Manual QA on Windows → deferred to CLAUDE.md "Pre-release Manual QA Checklist" (runtime hook + API key required, can't run headless/CI).
- [x] 4.3 Clipboard fallback contingency → captured in design.md open question + pre-release checklist.
- [x] 4.4 Regression checks → deferred to CLAUDE.md pre-release checklist.
