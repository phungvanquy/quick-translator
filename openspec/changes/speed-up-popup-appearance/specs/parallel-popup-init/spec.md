## ADDED Requirements

### Requirement: Clipboard polling and window creation run concurrently
The translate trigger path SHALL spawn clipboard polling and window creation as concurrent tasks, joining both before starting the API stream. The window creation MUST NOT depend on the clipboard result to begin.

#### Scenario: Normal translate trigger
- **WHEN** Ctrl+C+C fires and clipboard text is available within the poll budget
- **THEN** the popup window is already built (hidden) by the time clipboard polling completes, and the combined latency is max(clipboard_time, window_time) rather than clipboard_time + window_time

#### Scenario: Clipboard returns empty
- **WHEN** Ctrl+C+C fires but clipboard polling returns an empty string
- **THEN** the trigger path returns early without starting a stream, and any pre-built window is either not shown or closed on the next trigger

### Requirement: Clipboard polling and window creation run concurrently for chat
The chat trigger path SHALL apply the same concurrent pattern: clipboard polling and chat window creation run in parallel.

#### Scenario: Normal chat trigger
- **WHEN** Ctrl+C+Space fires and clipboard text is available
- **THEN** the chat popup is already built by the time clipboard completes, and both results are available before showing the window

#### Scenario: Chat with empty selection
- **WHEN** Ctrl+C+Space fires but clipboard returns empty
- **THEN** the chat popup still opens in free-chat mode (empty selection is valid for chat)

### Requirement: Clipboard poll interval is 20ms
The clipboard polling loop SHALL sleep 20ms between attempts, with a maximum of 10 attempts (200ms total budget).

#### Scenario: Fast clipboard update
- **WHEN** the clipboard text changes within 20ms of the copy
- **THEN** polling detects the change on the first or second iteration (~20-40ms)

#### Scenario: Slow clipboard producer
- **WHEN** the clipboard text takes 150ms to propagate
- **THEN** polling still catches it within the 200ms budget (iterations 7-8)

#### Scenario: Clipboard never updates
- **WHEN** the clipboard does not change within 200ms
- **THEN** the fallback (previous clipboard content) is returned after 10 iterations
