## Why

After a translation completes, the only way to reuse the result is to manually select the text and press Ctrl+C — the most common action post-translate has the most friction. The popup is also locked at 460×220 (`resizable(false)`), so long translations scroll inside a tiny box, and the truncated source text (~120 chars) offers no way to see the full original. These are three small, independent frictions in the single most-used flow.

## What Changes

- Add a **Copy button** to the translate popup that copies the full translation result to the clipboard, with brief visual confirmation. Available once the stream completes.
- Make the translate popup **resizable** (parity with the chat popup, which already sets `resizable(true)` + `min_inner_size`), so long results can be read comfortably.
- Add a **tooltip (`title`) on the truncated source text** so hovering the original line reveals the full captured text.

No breaking changes. All existing popup behaviors are preserved: `popup://ready` handshake, Esc / blur-to-close, draggable header, markdown rendering, and DPI-safe cursor positioning.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `translation-popup`: adds a copy-result affordance, makes the window resizable, and requires the full original text to be discoverable from the truncated display.

## Impact

- `frontend/popup.html` — Copy button element in header/footer; `title` attribute wiring on the original-text element.
- `frontend/popup.css` — Copy button styling + confirmation state.
- `frontend/popup.js` — copy handler (uses the accumulated `fullText`), sets `title` to the full original, manages the button enabled/confirmed states across stream lifecycle.
- `src-tauri/src/windows.rs` — `show_translate_popup`: `resizable(true)` + a `min_inner_size`.
- Tauri ACL: verify clipboard-write capability. If the frontend writes via the browser Clipboard API in the focused webview no ACL change is needed; if it uses the Tauri clipboard plugin, `capabilities/default.json` must grant the write permission (see design.md).
- No config format change; no dependency additions expected.
