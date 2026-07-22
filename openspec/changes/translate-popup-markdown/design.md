## Context

The translate popup (`frontend/popup.js`, `popup.html`, `popup.css`) is the Stage 1 vertical slice. It appends streamed chunks with `translationText.textContent += payload` and never post-processes them, so Markdown in the result is shown as literal source characters.

The Stage 2 chat popup already solved the identical problem. `frontend/markdown.js` exposes `window.renderMarkdown(src)` — a self-contained, XSS-safe Markdown→HTML renderer (escapes first, only emits self-generated tags). `chat.js` uses the pattern: show plain text while streaming (`aiEl.textContent = full`), then `aiEl.innerHTML = renderMarkdown(full)` once complete.

This change applies the same, already-trusted approach to the translate popup. The backend, its streamed payload, and the `translate://chunk` / `translate://done` events are unchanged.

## Goals / Non-Goals

**Goals:**
- Render the completed translation as Markdown in the translate popup, reusing `renderMarkdown` unchanged.
- Keep the existing UX: spinner until first chunk, plain-text streaming, then render on completion.
- Style rendered elements consistently with the chat popup and the shared GitHub-dark theme.

**Non-Goals:**
- No backend changes.
- No new Markdown features beyond what `markdown.js` already supports.
- No live/incremental Markdown rendering mid-stream (render happens once, on completion).
- No changes to the chat popup.

## Decisions

**Reuse `frontend/markdown.js` rather than adding a Markdown library.** It already covers the required subset, is XSS-safe by construction, and is proven in the chat popup. Adding a dependency (e.g. marked, markdown-it) would increase bundle size and introduce sanitization concerns for no functional gain. Alternative considered: inline a second renderer in `popup.js` — rejected as duplication.

**Render on completion, stream plain.** Matching `chat.js`, chunks append as `textContent` while streaming (partial Markdown renders poorly — unclosed fences, half lists), then a single `innerHTML = renderMarkdown(accumulated)` on `translate://done`. This avoids flicker and mis-rendered partial syntax. Alternative considered: re-render on every chunk — rejected for flicker and wasted work.

**Track the accumulated raw text.** Because `textContent +=` loses the raw source once we'd want to render, `popup.js` will keep the running string in a variable (as chat.js does with `full`) and pass it to `renderMarkdown` on completion.

**Styling reuses chat bubble CSS conventions.** Add rules to `popup.css` for the rendered element tags (`h1–h3`, `p`, `ul/ol/li`, `code`, `pre`, `strong`, `em`) scoped under the translation result container, mirroring the chat popup's look via the shared `theme.css` variables.

## Risks / Trade-offs

- [Selection/copy behavior changes when text becomes structured HTML] → The spec keeps the result selectable; verify copy still yields readable text after render.
- [Long rendered content could overflow the fixed popup height] → Out of scope here (existing improvement #15 tracks popup scrolling); rendering does not make this worse than plain text and the result area already handles overflow the same way.
- [A future edit to `markdown.js` for chat could affect the translate popup] → Acceptable and intended: one shared renderer is the point. Any change is covered by the shared XSS-safe contract.
