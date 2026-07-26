## ADDED Requirements

### Requirement: In-flight streams are cancelled when their target window closes

A streaming request SHALL be abandoned as soon as the window that requested it is gone. The stream exists only to fill that window, so once the window closes the remaining work produces nothing observable while still consuming tokens and a connection.

#### Scenario: Closing the popup mid-stream stops the request

- **WHEN** a translate or chat stream is in progress and the user closes the target window (Esc, close button, or blur where blur-to-close applies)
- **THEN** the stream stops reading the response body and the underlying HTTP request is dropped rather than drained to completion
- **AND** no further chunk or completion signals are emitted for that request

#### Scenario: Cancellation is bounded by the read cadence

- **WHEN** a stream has been cancelled
- **THEN** it stops at the next boundary between reads rather than mid-parse, so a partially buffered SSE line is never treated as a complete one

#### Scenario: A new request is not affected by a previous cancellation

- **WHEN** a stream is cancelled and the user then triggers a new translate or chat request
- **THEN** the new request streams normally, unaffected by the earlier cancellation

#### Scenario: Cancellation is not an error

- **WHEN** a stream is cancelled because its window closed
- **THEN** no error text is produced anywhere, since the user's own action caused it and there is no window left to show it in

### Requirement: Each window's cancellation is independent

Cancellation SHALL be scoped to the window whose stream it belongs to, so that closing one popup cannot terminate a stream feeding another.

#### Scenario: Closing the translate popup leaves a chat stream running

- **WHEN** a chat stream is in progress and a separate translate popup is closed
- **THEN** the chat stream continues uninterrupted and its response still renders in the chat popup
