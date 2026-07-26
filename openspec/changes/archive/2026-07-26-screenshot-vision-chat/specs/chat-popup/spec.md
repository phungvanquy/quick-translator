## ADDED Requirements

### Requirement: Image thumbnail strip

The chat popup SHALL display a thumbnail for each attached image above the input area, so the user can see what will be sent before sending it.

#### Scenario: Thumbnail shown on attach

- **WHEN** an image is attached to the session
- **THEN** a thumbnail of it appears in the popup

#### Scenario: Header reflects image context

- **WHEN** an image is attached to a session that has no selected-text context
- **THEN** the popup is no longer labelled as free chat

#### Scenario: Thumbnails cleared after send

- **WHEN** a question with attached images is sent
- **THEN** the strip clears, since those images now belong to the conversation history rather than the pending input

### Requirement: Popup close releases captures

Closing the chat popup SHALL notify the backend so that any retained screen captures are released.

#### Scenario: Close frees memory

- **WHEN** the user closes the chat popup
- **THEN** the backend drops the stored captures
