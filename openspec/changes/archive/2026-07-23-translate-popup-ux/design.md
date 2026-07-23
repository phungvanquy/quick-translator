## Context

The translate popup (`frontend/popup.{html,css,js}` + `src-tauri/src/windows.rs::show_translate_popup`) is the most-used surface in the app. Three independent frictions are being addressed: no quick copy, fixed non-resizable window, and no way to see the full truncated original. The chat popup already demonstrates the resizable pattern (`resizable(true)` + `min_inner_size(380, 320)` in `show_chat_popup`), so the resize change is proven in-repo.

Key constraints to preserve:
- The `popup://ready` handshake — `popup.js` emits it after listeners attach; `windows.rs`/`main.rs` wait for it before streaming. New init code must not delay or bypass this.
- Blur-to-close fires only after the window has focused once. A copy action that momentarily shifts focus must not trigger an unwanted close.
- Markdown is rendered into `translation-text` on `translate://done`; the raw accumulated `fullText` is the source of truth for what to copy (copy plain text, not rendered HTML).
- DPI-safe positioning in `windows.rs` (build hidden → `set_position(PhysicalPosition)` → show) must stay intact; only window flags change.

## Goals / Non-Goals

**Goals:**
- One-click copy of the completed translation result with brief visual confirmation.
- Resizable translate popup with a minimum size, matching the chat popup pattern.
- Full original text reachable via hover tooltip on the truncated source line.

**Non-Goals:**
- Auto-copy on completion (explicit user action only — avoids clobbering clipboard the user may be using elsewhere).
- Copying rendered markdown/HTML; copy is plain text.
- Read-aloud / TTS (that is the separate Stage 3 roadmap item).
- Persisting window size across popups (each popup is freshly built; out of scope).

## Decisions

### Decision: Copy uses the accumulated `fullText`, not the DOM
`popup.js` already keeps `fullText` (the raw streamed text) separate from the markdown-rendered `innerHTML`. The copy handler writes `fullText` so the user gets clean source text, not HTML tags or markdown artifacts pulled from `textContent`.
- **Alternative considered**: read `translationText.textContent` after render — rejected because rendered markdown can drop/alter whitespace and list markers.

### Decision: Clipboard write mechanism — prefer Tauri clipboard, fall back to browser API
Two options to write the clipboard from the webview:
1. **Browser `navigator.clipboard.writeText`** — zero backend/ACL change, but requires a secure context + focused document; can throw in some webview configs.
2. **Tauri clipboard-manager plugin** — reliable inside Tauri, but requires adding the plugin dependency + an ACL permission in `capabilities/default.json` (parity with how `core:window:allow-close` had to be explicitly granted per CLAUDE.md).

Decision: attempt `navigator.clipboard.writeText` first (the popup is focused when the button is clicked, so the secure-context requirement is normally met); this keeps the change frontend-only. If manual testing on the Windows webview shows it failing, escalate to the Tauri clipboard plugin and add the ACL grant. This is flagged as the primary open question to resolve during implementation testing.

### Decision: Copy control lifecycle mirrors the spinner lifecycle
The button starts disabled, becomes enabled on `translate://done` (same event that stops the spinner and renders markdown). On click: write clipboard → swap label to a "Copied ✓" state → revert after ~1.2s via `setTimeout`. Disabled state prevents copying an empty/partial result (satisfies the "copy unavailable before completion" scenario).

### Decision: Resize via window flags only
In `show_translate_popup`, change `.resizable(false)` → `.resizable(true)` and add `.min_inner_size(...)` (e.g. 360×160). The result area is already `flex:1; overflow-y:auto`, so it reflows for free — no layout rewrite needed. Initial 460×220 stays as the default size.

### Decision: Tooltip is a plain `title` attribute
Set `originalText.title = original` (full text) while `textContent` stays truncated. Native tooltip, no CSS/JS tooltip component. Escaping is a non-issue since `title` is set as a DOM property, not interpolated into HTML.

## Risks / Trade-offs

- **`navigator.clipboard` unavailable/throws in the Windows webview** → Mitigation: wrap in try/catch and surface a subtle failure state on the button; if it proves unreliable in manual QA, switch to the Tauri clipboard plugin (documented above). Must be verified on Windows since it can't be tested headless/CI.
- **Copy button click shifts focus and triggers blur-to-close** → Mitigation: the button lives inside the popup window, so clicking it does not blur the window (focus stays within the same webview). Verify in manual QA; if needed, guard the copy click against the close path.
- **Resizable frameless window edge-grab ergonomics** → Mitigation: chat popup already ships this exact pattern, so behavior is known-good; reuse the same flags/min-size approach.
- **Larger min/resized window could overflow a small monitor** → Mitigation: existing `position_at_cursor` clamps position to the monitor; keep min size modest (≤360 wide).
