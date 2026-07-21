## ADDED Requirements

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

The popup SHALL let the user type a question and send it, appending a user bubble and then a streaming assistant bubble to the transcript.

#### Scenario: Send via button or Enter

- **WHEN** the user types a non-empty question and presses Enter or clicks Send
- **THEN** the input clears, a user message bubble is appended, the Send control shows a busy state, and an assistant bubble begins streaming
- **WHEN** the input is empty
- **THEN** Send does nothing

#### Scenario: Transcript scrolls with new content

- **WHEN** new message content is appended and exceeds the visible area
- **THEN** the transcript is scrollable and follows the newest content to the bottom

#### Scenario: Send re-enabled after completion

- **WHEN** an assistant response finishes streaming
- **THEN** the Send control returns to its normal enabled state, ready for the next turn
