## MODIFIED Requirements

### Requirement: Windows admin elevation

The Tauri bundle SHALL NOT request administrator elevation on Windows. The embedded manifest SHALL request the `asInvoker` execution level so the app launches at the caller's integrity level with no UAC prompt. The documentation SHALL note that, due to Windows UIPI, the global keyboard hook will not observe input while an elevated window is in the foreground, and that running the app as administrator is the manual workaround for that case.

#### Scenario: No-elevation manifest

- **WHEN** the Windows executable is produced by the Tauri build
- **THEN** its embedded manifest requests the `asInvoker` execution level
- **AND** launching the executable does NOT trigger a UAC elevation prompt

#### Scenario: Elevated-foreground-window limitation documented

- **WHEN** the user reads the app documentation about hotkeys
- **THEN** it states that the hotkey will not fire while an elevated window is the foreground window
- **AND** it describes running the app as administrator as the manual workaround
