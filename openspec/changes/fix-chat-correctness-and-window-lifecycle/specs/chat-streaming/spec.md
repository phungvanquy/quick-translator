## MODIFIED Requirements

### Requirement: Chat request with context and history

The backend SHALL provide a streaming chat request that POSTs to `<base_url>/chat/completions` with `stream: true`. The request messages SHALL be a system prompt followed by the conversation history, where the history's final entry is the question being asked. The backend SHALL NOT append the question as a separate message, and SHALL NOT accept the question as a parameter independent of the history — the frontend owns conversation history, so the question reaches the backend exactly once, as part of it.

#### Scenario: The question appears exactly once

- **WHEN** a chat request is issued
- **THEN** the message list is the system prompt followed by the history entries, with nothing appended after them
- **AND** the question the user just asked appears exactly once in the message list

#### Scenario: A multimodal question keeps its attachments

- **WHEN** the question carries attached images, so its history entry is a content array of a text part plus one or more image parts
- **THEN** that single entry is sent as-is
- **AND** no additional text-only copy of the question is sent, so the model never receives the same question twice with differing context

#### Scenario: System prompt varies by selected text

- **WHEN** a chat request is issued with non-empty selected text
- **THEN** the system prompt instructs the assistant that the user has selected that text (embedded in the prompt) and to answer questions about it concisely, permitting Markdown formatting
- **WHEN** selected text is empty (free chat)
- **THEN** the system prompt is the general concise-assistant prompt permitting Markdown, with no embedded selection

#### Scenario: History is included as context

- **WHEN** a chat request is issued and prior turns exist
- **THEN** those prior user/assistant messages are sent between the system prompt and the newest entry, so the assistant has conversational context

#### Scenario: Model and credentials from config

- **WHEN** a chat request is issued
- **THEN** it uses the `model`, `api_key`, and `base_url` from the current config, consistent with the translate flow

#### Scenario: Missing API key

- **WHEN** a chat request is issued but no API key is configured
- **THEN** no network request is made and the popup shows a message directing the user to set an API key in Settings

### Requirement: Streaming assistant response to the popup

The chat request SHALL stream assistant tokens to the popup as they arrive, using the same SSE parsing approach as the translate flow, and signal completion. Failures SHALL be reported in the same readable, retryable form as the translate flow rather than as a raw status-and-body dump.

#### Scenario: Tokens stream into the bubble

- **WHEN** the assistant response is being generated
- **THEN** each content delta is delivered to the popup and appended to the current assistant bubble as it arrives

#### Scenario: Completion signaling

- **WHEN** the stream ends normally
- **THEN** a completion signal is delivered so the popup can finalize the bubble (e.g. render markdown) and re-enable Send

#### Scenario: Failure is readable and retryable

- **WHEN** the request fails, returns a non-success status, or the stream errors
- **THEN** the popup shows a short human-readable summary of what went wrong, with the raw detail available but not shown by default, and offers a way to retry the turn
- **AND** the bubble is finalized rather than left hanging indefinitely, and Send is re-enabled

#### Scenario: Cancellation is not reported as failure

- **WHEN** the stream stops because the chat popup was closed
- **THEN** no error is reported, since the user's own action ended it
