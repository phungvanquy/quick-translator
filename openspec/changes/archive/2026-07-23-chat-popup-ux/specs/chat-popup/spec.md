## ADDED Requirements

### Requirement: Pending-response typing indicator

The popup SHALL show a typing indicator in the assistant bubble from the moment a message is sent until the first response chunk arrives.

#### Scenario: Indicator shown while waiting

- **WHEN** the user sends a question and the assistant bubble is created
- **THEN** the bubble shows a typing indicator until the first `chat://chunk` is received

#### Scenario: Indicator replaced by content

- **WHEN** the first response chunk arrives
- **THEN** the typing indicator is removed and streamed text takes its place

## MODIFIED Requirements

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
