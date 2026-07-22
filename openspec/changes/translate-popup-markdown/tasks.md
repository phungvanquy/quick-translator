## 1. Wire the renderer into the popup

- [x] 1.1 Add `<script src="markdown.js"></script>` before `popup.js` in `frontend/popup.html`
- [x] 1.2 In `frontend/popup.js`, accumulate streamed chunks into a running string (e.g. `fullText`) in addition to appending them as plain `textContent` while streaming
- [x] 1.3 On `translate://done`, set `translationText.innerHTML = renderMarkdown(fullText)` instead of leaving the plain text
- [x] 1.4 Guard the empty/no-chunk case (done fires with no chunks) so an empty render is harmless

## 2. Style the rendered Markdown

- [x] 2.1 In `frontend/popup.css`, add styles scoped to the translation result for `h1–h3`, `p`, `ul/ol/li`, `strong`, `em`, `code`, and `pre` using `theme.css` variables, matching the chat popup's look
- [x] 2.2 Ensure code blocks use a monospaced font with a distinct background and that inline `code` is visually distinct

## 3. Verify

- [ ] 3.1 Build the app (`cargo tauri build` or dev) and trigger a translation whose output contains bold, italic, inline code, a fenced code block, a heading, and a bullet/ordered list; confirm each renders correctly _(renderer output verified via Node unit test; live GUI build/trigger not runnable in this Linux env — needs a Windows run)_
- [ ] 3.2 Confirm streaming still shows plain text with the spinner-until-first-chunk behavior, and that the rendered result appears on completion _(needs Windows GUI run)_
- [x] 3.3 Confirm HTML/script-like content in the translation is escaped and not executed (XSS check) _(verified: renderMarkdown escapes `<script>`/`<img>` to inert text; no live tags emitted)_
- [ ] 3.4 Confirm Escape, blur-to-close, drag, and close-button behavior are unchanged, and the rendered result is still selectable _(unchanged code paths; needs Windows GUI run to confirm)_
