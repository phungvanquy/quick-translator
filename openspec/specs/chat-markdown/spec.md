# chat-markdown Specification

## Purpose
TBD - created by archiving change stage2-chat-popup. Update Purpose after archive.
## Requirements
### Requirement: Markdown rendering in assistant messages

Assistant messages SHALL render Markdown, reproducing the formatting the Python `render_markdown_to_text` supported: bold, italic, combined bold+italic, inline code, fenced code blocks, headings (h1–h3), and bullet / ordered lists. Because the popup is a webview, rendering produces styled HTML rather than tk.Text tags.

#### Scenario: Inline formatting

- **WHEN** an assistant message contains bold, italic, bold+italic, or inline-code spans
- **THEN** each is rendered with the corresponding visual style in the message bubble

#### Scenario: Block formatting

- **WHEN** an assistant message contains headings, fenced code blocks, or bullet/ordered lists
- **THEN** headings render at their level, code blocks render in a monospaced block with distinct background, and lists render with appropriate markers and indentation

#### Scenario: Rendering finalized on completion

- **WHEN** a response is still streaming
- **THEN** partial content is shown as it arrives (may be plain/interim text)
- **WHEN** the response completes
- **THEN** the full message is rendered with final Markdown formatting

#### Scenario: Untrusted content is not executable

- **WHEN** assistant output contains HTML-like or script-like text
- **THEN** it is rendered as text/markdown and NOT executed as live HTML/script in the webview

