## ADDED Requirements

### Requirement: Double Ctrl+C triggers translation

The application SHALL detect a double press of Ctrl+C (two Ctrl+C presses within a short window) via a raw global keyboard hook and use it to trigger the translate flow. The Tauri global-shortcut plugin MUST NOT be used for this, because it cannot detect a double-tap of an existing OS shortcut (Ctrl+C).

#### Scenario: Two Ctrl+C presses within the arm window

- **WHEN** the user presses Ctrl+C, then presses Ctrl+C again within 0.6 seconds
- **THEN** the translate flow is triggered exactly once for that pair
- **AND** because each Ctrl+C is a real OS copy, the current selection has been copied to the clipboard by the time the flow reads it

#### Scenario: Single Ctrl+C does not trigger

- **WHEN** the user presses Ctrl+C once and does not press it again within 0.6 seconds
- **THEN** the translate flow is NOT triggered
- **AND** the armed state resets so the next Ctrl+C starts a fresh window

#### Scenario: Debounce between triggers

- **WHEN** a translate trigger has just fired
- **THEN** any key event occurring within 0.4 seconds of that trigger is ignored for the purpose of arming or firing another trigger

#### Scenario: Interrupting key resets the armed state

- **WHEN** the arm window is active (one Ctrl+C seen) and the user presses a key other than a modifier (ctrl/shift/alt) or the awaited combo key
- **THEN** the armed state is cleared and no trigger fires

### Requirement: Clipboard capture after copy

When the translate flow fires, the application SHALL read the freshly copied selection from the clipboard, reproducing the Python `get_clipboard_after_copy` polling behavior using the `arboard` crate.

#### Scenario: Clipboard updates within the poll window

- **WHEN** the translate flow reads the clipboard after a Ctrl+C copy
- **THEN** it polls up to 10 times at 50ms intervals, and returns the new clipboard text (trimmed) as soon as the content differs from the value captured before the copy

#### Scenario: Clipboard does not change

- **WHEN** the clipboard content never changes during the poll window
- **THEN** the previously captured clipboard text (trimmed) is returned as a fallback

#### Scenario: Empty selection

- **WHEN** the resolved clipboard text is empty
- **THEN** the translate flow does not open a popup or issue an API request
