# chat-hotkey Specification

## Purpose
TBD - created by archiving change stage2-chat-popup. Update Purpose after archive.
## Requirements
### Requirement: Ctrl+C+Space triggers chat

The application SHALL detect the combo Ctrl+C followed by Space (Space pressed while Ctrl is held, within the same arm window used by the translate double-tap) via the existing raw global keyboard hook, and use it to trigger the chat flow. This combo MUST share the single `rdev::listen` thread and arm-window/debounce state machine with the Ctrl+C+C translate trigger, matching the Python `hotkeys.py` behavior. The Tauri global-shortcut plugin MUST NOT be used.

#### Scenario: Ctrl+C then Space within the arm window

- **WHEN** the user presses Ctrl+C, then presses Space while Ctrl is still held within 0.6 seconds
- **THEN** the chat flow is triggered exactly once for that pair
- **AND** because the initial Ctrl+C is a real OS copy, the current selection has been copied to the clipboard by the time the flow reads it

#### Scenario: Space without a prior armed Ctrl+C

- **WHEN** Space is pressed while Ctrl is held but no Ctrl+C armed the window (or the 0.6s window has expired)
- **THEN** the chat flow is NOT triggered and the armed state is cleared

#### Scenario: Chat and translate share one arm window

- **WHEN** the user presses Ctrl+C once
- **THEN** a following Ctrl+C within the window triggers translate, OR a following Ctrl+Space within the window triggers chat — whichever key arrives first, and only one trigger fires

#### Scenario: Debounce applies across both triggers

- **WHEN** a chat or translate trigger has just fired
- **THEN** any key event within 0.4 seconds of that trigger is ignored for arming or firing another trigger

### Requirement: Clipboard capture for chat

When the chat flow fires, the application SHALL read the freshly copied selection from the clipboard using the same `get_clipboard_after_copy` polling behavior as the translate flow.

#### Scenario: Selection captured as chat context

- **WHEN** the chat flow reads the clipboard after the Ctrl+C copy
- **THEN** the resolved (trimmed) clipboard text is passed to the chat popup as the selected-text context

#### Scenario: Empty selection still opens chat

- **WHEN** the resolved clipboard text is empty
- **THEN** the chat popup still opens in free-chat mode (no selected-text context strip), since chat does not require a selection to be useful

