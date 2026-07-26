## MODIFIED Requirements

### Requirement: Chat popup window

The application SHALL open a frameless, always-on-top chat popup window anchored near the cursor when the chat flow triggers, mirroring the Python `show_chat_popup` layout: a draggable header (the only draggable zone), an optional selected-text context strip, a scrollable message transcript, and a text input bar pinned to the bottom.

The chat popup SHALL be a **persistent** window rather than an ephemeral one. Unlike the translate popup — whose content can be regenerated in seconds by pressing the hotkey again — a chat session holds conversation history and attached screenshots that cannot be reconstructed. The user must therefore be able to look at other windows without destroying it, and be able to get back to it.

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

#### Scenario: Losing focus does not close the popup

- **WHEN** the user clicks another application while the chat popup is open
- **THEN** the popup stays open with its transcript, pending input text, and attached image thumbnails intact
- **AND** any in-flight response continues streaming into it

#### Scenario: The popup is reachable again after clicking away

- **WHEN** the chat popup no longer has focus
- **THEN** it is listed among the system's switchable windows, so the user can return to it via the taskbar or the window switcher

#### Scenario: Close behaviors

- **WHEN** the user presses Esc or clicks the close button
- **THEN** the popup closes
- **AND** these are the only ways the popup closes, so closing is always a deliberate act

### Requirement: Popup close releases captures

Closing the chat popup SHALL notify the backend so that any retained screen captures are released. Because the popup now closes only on deliberate user action, releasing captures on close cannot discard images the user still wanted.

#### Scenario: Close frees memory

- **WHEN** the user closes the chat popup
- **THEN** the backend drops the stored captures

#### Scenario: Captures survive a focus change

- **WHEN** the user clicks away from the chat popup and then returns to it
- **THEN** the attached captures are still present and still send with the next question
