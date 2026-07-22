## Why

The Stage 2 chat popup renders assistant replies as formatted Markdown, but the Stage 1 translate popup still shows results as raw plain text. When a translation contains Markdown (headings, bold, lists, code) — which happens whenever the source text or the model's output is structured — the user sees literal `**`, `#`, and backtick characters instead of formatting. The XSS-safe renderer needed to fix this (`frontend/markdown.js`) already exists and is already trusted by the chat popup, so closing this gap is low-risk and brings the translate popup to parity.

## What Changes

- Render the completed translation as Markdown in the translate popup, reusing the existing `renderMarkdown` from `frontend/markdown.js` (the same renderer the chat popup uses).
- Keep streaming chunks as plain text while the response is in flight, then swap to the rendered Markdown on `translate://done` — mirroring the chat popup's stream-plain-then-render-final pattern.
- Style the rendered Markdown elements (headings, code blocks, lists, inline code, bold/italic) in the translate popup using the shared GitHub-dark theme, matching the chat bubble styling.
- Preserve all existing popup behavior: cursor-anchored placement, spinner-until-first-chunk, Escape / blur / drag / close.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `translation-popup`: The "Streaming render" requirement changes so that, on stream completion, the translated text is rendered as Markdown (bold, italic, inline code, fenced code blocks, headings h1–h3, bullet/ordered lists) rather than remaining plain text. In-flight chunks continue to append as plain text; untrusted content is escaped and never executed.

## Impact

- **Frontend**: `frontend/popup.js` (render Markdown on `translate://done`, include `markdown.js`), `frontend/popup.html` (load `markdown.js`), `frontend/popup.css` (styles for rendered Markdown elements). Reuses `frontend/markdown.js` unchanged.
- **Backend**: none — the streamed payload and events (`translate://chunk`, `translate://done`) are unchanged.
- **Dependencies**: none added.
