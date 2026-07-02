# tray-lifecycle Specification

## Purpose
TBD - created by archiving change rewrite-rust-tauri-stage1. Update Purpose after archive.
## Requirements
### Requirement: System tray presence

The application SHALL run as a background process with a system tray icon titled "Quick Translator" and no persistent main window.

#### Scenario: App starts and shows tray icon

- **WHEN** the application launches
- **THEN** a tray icon appears using the bundled `icon.ico`/`icon.png`, falling back to a generated placeholder icon only if neither bundled icon can be loaded
- **AND** no visible main window is shown (the app lives in the tray)

#### Scenario: First run without an API key

- **WHEN** the application launches and the loaded config has an empty `api_key`
- **THEN** the Settings window is opened automatically so the user can enter credentials

### Requirement: Tray menu actions

The tray icon SHALL expose a menu with "Settings" and "Quit" items.

#### Scenario: Open settings from tray

- **WHEN** the user selects "Settings" from the tray menu
- **THEN** the Settings window is shown (created if not already open, focused if already open)

#### Scenario: Quit from tray

- **WHEN** the user selects "Quit" from the tray menu
- **THEN** the global keyboard hook is torn down, any open windows are closed, and the process exits cleanly

### Requirement: Graceful shutdown

The application SHALL release its OS-level resources on exit.

#### Scenario: Shutdown releases the keyboard hook

- **WHEN** the application exits (via tray Quit)
- **THEN** the `rdev` keyboard listener thread is stopped or detached so no global hook is left dangling
- **AND** the process terminates without leaving orphaned windows

