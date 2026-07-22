## MODIFIED Requirements

### Requirement: Streaming render

The popup SHALL render translation chunks as they arrive, and SHALL render the completed translation as Markdown.

Markdown rendering MUST reproduce the subset supported by the shared renderer (`frontend/markdown.js`): bold, italic, combined bold+italic, inline code, fenced code blocks, headings (h1–h3), and bullet / ordered lists. Because the popup is a webview, rendering produces styled HTML rather than plain text.

#### Scenario: Chunks appended live

- **WHEN** translation chunks are received from the backend
- **THEN** a loading indicator is shown until the first chunk arrives, after which chunks are appended to the result area in order as plain text

#### Scenario: Markdown rendered on completion

- **WHEN** the stream completes
- **THEN** the loading indicator is no longer shown
- **AND** the accumulated translated text is rendered as Markdown, so bold, italic, bold+italic, and inline-code spans display with their visual style, and headings, fenced code blocks, and bullet/ordered lists render at their level / marker with a monospaced, distinctly-backgrounded block for code
- **AND** the rendered result remains visible and selectable

#### Scenario: Untrusted content is not executable

- **WHEN** the translated text contains HTML-like or script-like content
- **THEN** it is escaped and rendered as text/Markdown and NOT executed as live HTML/script in the webview
