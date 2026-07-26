## ADDED Requirements

### Requirement: A hotkey press always produces an observable outcome

Every hotkey trigger SHALL produce something the user can perceive — a window, or a message explaining why no window opened. A trigger that fails silently is indistinguishable from a dead application, which is the worst possible reading for a background tray app whose only entry point is a hotkey.

#### Scenario: Nothing selected when the translate hotkey fires

- **WHEN** the translate hotkey fires and the clipboard yields no usable text (nothing was selected, or the copy did not land)
- **THEN** the user is shown a brief, non-blocking message explaining that no text was selected
- **AND** no translation request is made

#### Scenario: The message does not steal focus or require dismissal

- **WHEN** a no-selection message is shown
- **THEN** it does not take keyboard focus away from the application the user was working in
- **AND** it disappears on its own without the user having to dismiss it

#### Scenario: Screen capture fails

- **WHEN** the screenshot hotkey fires but capturing the monitors fails, or no monitor is captured
- **THEN** the user is shown a message that the capture failed
- **AND** any partially stored capture state is released

#### Scenario: A window cannot be created

- **WHEN** a trigger fires but its popup or overlay window cannot be created
- **THEN** the failure is surfaced to the user rather than only written to a stream no release build can display
- **AND** any state reserved for that window is released

#### Scenario: Successful triggers stay silent

- **WHEN** a trigger succeeds and opens its window
- **THEN** no additional notification is shown, because the window itself is the feedback

### Requirement: Diagnostics survive a release build

Failure paths SHALL NOT rely solely on writing to standard error, which is unreachable in a release build because the executable is built as a Windows subsystem application with no attached console.

#### Scenario: A failure leaves a trace the user can report

- **WHEN** any trigger-path failure occurs in a release build
- **THEN** the user is given at minimum a human-readable indication that it failed, so the problem is reportable rather than invisible
