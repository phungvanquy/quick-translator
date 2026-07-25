## ADDED Requirements

### Requirement: Read-aloud button in translate popup

The translate popup SHALL present a read-aloud control (speaker icon) in its footer bar that speaks the popup's **source** (original/clipboard) text aloud. The control MUST NOT read the translated result.

#### Scenario: User triggers read-aloud
- **WHEN** the translate popup is showing and the user clicks the speaker button
- **THEN** the system speaks the original source text aloud using an OS-native TTS engine
- **AND** playback begins without blocking the UI (the popup stays interactive)

#### Scenario: Empty source text
- **WHEN** the source text is empty or whitespace only
- **THEN** the button performs no speech and does not error

### Requirement: Single active utterance

A new speak request SHALL stop any speech already in progress before starting the new one, so overlapping utterances never play simultaneously.

#### Scenario: Rapid re-trigger
- **WHEN** speech is already playing and the user clicks the speaker button again
- **THEN** the system stops the in-progress speech first
- **AND** then starts speaking from the beginning

### Requirement: Speech stops when popup closes

Closing the translate popup (via Esc, the close button, or click-outside) SHALL immediately stop any in-progress speech.

#### Scenario: Close during playback
- **WHEN** speech is playing and the popup is closed by any means
- **THEN** speech stops immediately and no audio continues after the popup is gone

### Requirement: OS-native offline speech

Speech SHALL use an OS-native / offline TTS engine (no network round-trip). The implementation SHALL target a moderate speaking rate (~160 wpm) and near-full volume (~0.9) as defaults.

#### Scenario: Offline availability
- **WHEN** the machine has no network connection
- **THEN** read-aloud still functions using the local speech engine

#### Scenario: Engine unavailable
- **WHEN** no usable TTS engine is available on the host
- **THEN** the failure is handled gracefully (no crash, button does nothing)
- **AND** the rest of the popup keeps working normally

### Requirement: TTS initialization resilience

The TTS subsystem SHALL initialize at app startup. If initialization fails, the app SHALL continue running without TTS capability.

#### Scenario: TTS init failure
- **WHEN** the TTS engine cannot be initialized (e.g., no SAPI voices installed)
- **THEN** the app starts normally
- **AND** the speaker button is non-functional but does not crash the app
