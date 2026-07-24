## ADDED Requirements

### Requirement: Single running instance

The application SHALL run as a single instance so that only one global input hook set is installed at a time. Launching the application while an instance is already running MUST NOT start a second background process, install a second keyboard/mouse hook, or cause hotkeys to fire more than once.

#### Scenario: Second launch does not duplicate the app

- **WHEN** the application is already running in the tray and the user launches the executable again
- **THEN** no second instance starts and no second global hook is installed
- **AND** exactly one popup / one API request results from a single hotkey trigger
- **AND** the already-running instance surfaces the Settings window so the user sees the app is alive

### Requirement: Global input listener resilience

The global input listener SHALL be robust enough to remain installed and responsive for the life of the process. It MUST NOT perform blocking work or spawn threads from within the low-level hook callback, and a transient panic while holding the listener's internal lock MUST NOT permanently disable the hotkeys.

#### Scenario: Hook callback stays lightweight

- **WHEN** the user moves the mouse or types while the app is running
- **THEN** the hook callback does no per-event blocking work and spawns no per-event threads
- **AND** the cursor position used to place a popup is sampled on demand at the moment a hotkey fires, not tracked on every mouse move

#### Scenario: Transient lock poisoning does not kill the hotkey

- **WHEN** a panic occurs while the listener's internal state lock is held
- **THEN** subsequent key events recover the lock and continue to be processed
- **AND** the global hotkey keeps working without requiring an application restart
