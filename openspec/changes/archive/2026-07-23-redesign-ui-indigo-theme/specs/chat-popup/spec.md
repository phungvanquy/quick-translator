## MODIFIED Requirements

### Requirement: Chat popup window

The application SHALL open a frameless, always-on-top chat popup window anchored near the cursor when the chat flow triggers: a draggable header (the only draggable zone), an optional selected-text context strip, a scrollable message transcript, and a text input bar pinned to the bottom. The window SHALL be styled with the app theme (dark and light, following the OS preference) and the indigo brand accent, presenting rounded corners, a drop shadow, and layered elevation, with all controls using the shared SVG icon set (no emoji).

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

#### Scenario: Themed appearance with SVG controls

- **WHEN** the OS color-scheme preference is dark or light
- **THEN** the popup renders in the corresponding theme, and the header chat glyph, close, and context-clear controls are SVG icons that tint to match

### Requirement: Sending a chat message

The popup SHALL let the user type a question in a multi-line input and send it, appending a user bubble and then a streaming assistant bubble to the transcript. The user bubble SHALL be visually distinguished from the assistant bubble by an accent-soft tint. The input SHALL be a text area supporting multiple lines that grows with content up to a capped height, after which it scrolls.

#### Scenario: Send via button or Enter

- **WHEN** the user types a non-empty question and presses Enter (without Shift) or clicks Send
- **THEN** the input clears and resets to its single-line height, a user message bubble is appended, the Send control shows a busy state, and an assistant bubble begins streaming

#### Scenario: User and assistant bubbles are distinguishable

- **WHEN** a user message and an assistant message are shown in the transcript
- **THEN** the user bubble uses the accent-soft tint and the assistant bubble uses a neutral surface, so the two roles are visually distinct

#### Scenario: Empty input does nothing

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
