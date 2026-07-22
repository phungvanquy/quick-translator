# chat-streaming Specification

## Purpose
TBD - created by archiving change stage2-chat-popup. Update Purpose after archive.
## Requirements
### Requirement: Chat request with context and history

The backend SHALL provide a streaming chat request that POSTs to `<base_url>/chat/completions` with `stream: true`, mirroring the Python `chat_with_context_stream`. The request messages SHALL be: a system prompt, then the prior conversation history, then the new user question.

#### Scenario: System prompt varies by selected text

- **WHEN** a chat request is issued with non-empty selected text
- **THEN** the system prompt instructs the assistant that the user has selected that text (embedded in the prompt) and to answer questions about it concisely, permitting Markdown formatting
- **WHEN** selected text is empty (free chat)
- **THEN** the system prompt is the general concise-assistant prompt permitting Markdown, with no embedded selection

#### Scenario: History is included as context

- **WHEN** a chat request is issued and prior turns exist
- **THEN** those prior user/assistant messages are sent between the system prompt and the new question, so the assistant has conversational context

#### Scenario: Model and credentials from config

- **WHEN** a chat request is issued
- **THEN** it uses the `model`, `api_key`, and `base_url` from the current config, consistent with the translate flow

#### Scenario: Missing API key

- **WHEN** a chat request is issued but no API key is configured
- **THEN** no network request is made and the popup shows a message directing the user to set an API key in Settings

### Requirement: Streaming assistant response to the popup

The chat request SHALL stream assistant tokens to the popup as they arrive, using the same SSE parsing approach as the translate flow, and signal completion.

#### Scenario: Tokens stream into the bubble

- **WHEN** the assistant response is being generated
- **THEN** each content delta is delivered to the popup and appended to the current assistant bubble as it arrives

#### Scenario: Completion and error signaling

- **WHEN** the stream ends normally
- **THEN** a completion signal is delivered so the popup can finalize the bubble (e.g. render markdown) and re-enable Send
- **WHEN** the request fails or the stream errors
- **THEN** an error message is delivered to the popup rather than leaving the bubble hanging indefinitely

### Requirement: Conversation history is bounded

The chat session SHALL retain history across turns within the popup's lifetime and cap it to prevent unbounded growth, matching the Python cap of the last 50 messages.

#### Scenario: History capped at 50 messages

- **WHEN** appending a completed user/assistant turn causes the history to exceed 50 messages
- **THEN** the oldest messages are dropped so at most the last 50 remain

#### Scenario: Clearing context resets history

- **WHEN** the user clears the selected-text context
- **THEN** the conversation history is also cleared and subsequent turns start fresh in free-chat mode

