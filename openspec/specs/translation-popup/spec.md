# translation-popup Specification

## Purpose
TBD - created by archiving change rewrite-rust-tauri-stage1. Update Purpose after archive.
## Requirements
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

### Requirement: Streaming render

The popup SHALL render translation chunks as they arrive.

#### Scenario: Chunks appended live

- **WHEN** translation chunks are received from the backend
- **THEN** a loading indicator is shown until the first chunk arrives, after which chunks are appended to the result area in order as plain text

#### Scenario: Stream completion

- **WHEN** the stream completes
- **THEN** the loading indicator is no longer shown and the full translated text remains visible and selectable

### Requirement: Popup dismissal

The popup SHALL be dismissible by keyboard, by losing focus, and be repositionable.

#### Scenario: Escape closes

- **WHEN** the popup has focus and the user presses Escape
- **THEN** the popup closes

#### Scenario: Click outside closes

- **WHEN** the popup loses focus (the user clicks outside it)
- **THEN** the popup closes

#### Scenario: Draggable header

- **WHEN** the user presses and drags on the popup's header region
- **THEN** the window moves with the cursor

### Requirement: Copy translation result

The popup SHALL provide a control to copy the full translation result to the system clipboard once the stream has completed.

#### Scenario: Copy after completion

- **WHEN** the translation stream has completed and the user activates the copy control
- **THEN** the full translated text is written to the system clipboard
- **AND** the control briefly indicates success (e.g. a checkmark or "Copied" label) before reverting

#### Scenario: Copy unavailable before completion

- **WHEN** the translation is still streaming or no text has been produced
- **THEN** the copy control is disabled or non-functional so an empty/partial result cannot be copied

