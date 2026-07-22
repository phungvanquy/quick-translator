## ADDED Requirements

### Requirement: Read-aloud button in translate popup

The translate popup SHALL present a read-aloud control (🔊) in its bottom bar that speaks the popup's **source** (original) text aloud. The control MUST NOT read the translated result — parity with the Python reference, where the button reads the input the user copied.

#### Scenario: User triggers read-aloud

- **WHEN** the translate popup is showing and the user clicks the 🔊 button
- **THEN** the system speaks the original source text aloud using an OS-native TTS engine
- **AND** playback begins without blocking the UI (the popup stays interactive)

#### Scenario: Empty source text

- **WHEN** the source text is empty or whitespace only
- **THEN** the button performs no speech and does not error

### Requirement: Single active utterance

A new speak request SHALL stop any speech already in progress before starting the new one, so overlapping utterances never play simultaneously.

#### Scenario: Rapid re-trigger

- **WHEN** speech is already playing and the user clicks 🔊 again
- **THEN** the system stops the in-progress speech first
- **AND** then starts speaking from the beginning

### Requirement: Speech stops when popup closes

Closing the translate popup (via Esc, the close button, or click-outside) SHALL immediately stop any in-progress speech.

#### Scenario: Close during playback

- **WHEN** speech is playing and the popup is closed by any means
- **THEN** speech stops immediately and no audio continues after the popup is gone

### Requirement: OS-native offline speech

Speech SHALL use an OS-native / offline TTS engine (no network round-trip), matching the Python `pyttsx3` behavior. The implementation SHOULD target a moderate speaking rate (~160 wpm) and near-full volume (~0.9) as sensible defaults.

#### Scenario: Offline availability

- **WHEN** the machine has no network connection
- **THEN** read-aloud still functions using the local speech engine

#### Scenario: Engine unavailable

- **WHEN** no usable TTS engine is available on the host
- **THEN** the failure is handled gracefully (no crash); the rest of the popup keeps working
