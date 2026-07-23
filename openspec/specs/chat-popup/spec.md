# chat-popup Specification

## Purpose
TBD - created by archiving change stage2-chat-popup. Update Purpose after archive.
## Requirements
### Requirement: Chat popup window

The application SHALL open a frameless, always-on-top chat popup window anchored near the cursor when the chat flow triggers, mirroring the Python `show_chat_popup` layout: a draggable header (the only draggable zone), an optional selected-text context strip, a scrollable message transcript, and a text input bar pinned to the bottom.

#### Scenario: Popup opens near cursor, DPI-safe

- **WHEN** the chat flow opens the popup
- **THEN** the window appears near the current cursor position, clamped to the monitor under the cursor
- **AND** positioning uses physical-pixel placement with the cursor monitor's scale factor (the same DPI-safe approach as the translate popup), never passing raw rdev coordinates to the builder's logical `position()`

#### Scenario: Only the header is draggable

- **WHEN** the user drags the header bar
- **THEN** the window moves
- **AND** dragging within the message transcript or input area does NOT move the window (it allows text selection / scrolling instead)

#### Scenario: Context strip reflects selection

- **WHEN** the popup opens with non-empty selected text
- **THEN** a context strip shows a truncated preview of the selection and the header reads "Chat"
- **WHEN** the popup opens with empty selected text, OR the user clears the context
- **THEN** the context strip is hidden and the header reads "Free Chat", and subsequent requests send no selected-text context

#### Scenario: Close behaviors

- **WHEN** the user presses Esc, clicks the close button, or the window loses focus by clicking outside it
- **THEN** the popup closes
- **AND** blur-to-close only takes effect after the window has gained focus at least once (same guard as the translate popup)

### Requirement: Sending a chat message

The popup SHALL let the user type a question in a multi-line input and send it, appending a user bubble and then a streaming assistant bubble to the transcript. The input SHALL be a text area supporting multiple lines that grows with content up to a capped height, after which it scrolls.

#### Scenario: Send via button or Enter

- **WHEN** the user types a non-empty question and presses Enter (without Shift) or clicks Send
- **THEN** the input clears and resets to its single-line height, a user message bubble is appended, the Send control shows a busy state, and an assistant bubble begins streaming
- **WHEN** the input is empty or contains only whitespace
- **THEN** Send does nothing

#### Scenario: Newline without sending

- **WHEN** the user presses Shift+Enter in the input
- **THEN** a newline is inserted and the message is NOT sent
- **AND** the text area grows to fit the added line, up to its capped height

#### Scenario: Ctrl+Enter also sends

- **WHEN** the user presses Ctrl+Enter with a non-empty question
- **THEN** the message is sent, identically to pressing Enter

#### Scenario: Transcript scrolls with new content

- **WHEN** new message content is appended and exceeds the visible area
- **THEN** the transcript is scrollable and follows the newest content to the bottom

#### Scenario: Send re-enabled after completion

- **WHEN** an assistant response finishes streaming
- **THEN** the Send control returns to its normal enabled state, ready for the next turn

### Requirement: Pending-response typing indicator

The popup SHALL show a typing indicator in the assistant bubble from the moment a message is sent until the first response chunk arrives.

#### Scenario: Indicator shown while waiting

- **WHEN** the user sends a question and the assistant bubble is created
- **THEN** the bubble shows a typing indicator until the first `chat://chunk` is received

#### Scenario: Indicator replaced by content

- **WHEN** the first response chunk arrives
- **THEN** the typing indicator is removed and streamed text takes its place

