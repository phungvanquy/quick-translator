## ADDED Requirements

### Requirement: Copy translation result

The popup SHALL provide a control to copy the full translation result to the system clipboard once the stream has completed.

#### Scenario: Copy after completion

- **WHEN** the translation stream has completed and the user activates the copy control
- **THEN** the full translated text is written to the system clipboard
- **AND** the control briefly indicates success (e.g. a checkmark or "Copied" label) before reverting

#### Scenario: Copy unavailable before completion

- **WHEN** the translation is still streaming or no text has been produced
- **THEN** the copy control is disabled or non-functional so an empty/partial result cannot be copied

## MODIFIED Requirements

### Requirement: Popup appearance and placement

The application SHALL show translation results in a frameless, always-on-top, resizable window positioned near the mouse cursor, styled with the GitHub-dark palette carried over from the Python `constants.py`.

#### Scenario: Popup opens near the cursor

- **WHEN** a translate trigger fires with non-empty captured text
- **THEN** a frameless, always-on-top window appears offset from the current cursor position
- **AND** the window is clamped to remain on-screen if the cursor is near a screen edge

#### Scenario: Original text shown

- **WHEN** the popup opens
- **THEN** it displays the captured original text, truncated with an ellipsis when longer than ~120 characters
- **AND** a header region indicates the target language

#### Scenario: Full original discoverable

- **WHEN** the displayed original text has been truncated
- **THEN** the full untruncated original text is available via the element's tooltip (`title`) on hover

#### Scenario: Popup is resizable

- **WHEN** the user drags the window's edge or corner
- **THEN** the window resizes, down to a sensible minimum size, and the result area reflows to use the available space
