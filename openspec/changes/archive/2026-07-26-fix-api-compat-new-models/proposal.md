## Why

GPT-5 series models (gpt-5, gpt-5.1, gpt-5.4, etc.) reject API requests that don't account for their internal reasoning token budget. The app's `test_connection` sends `max_completion_tokens: 1`, which is too low for reasoning models and returns a 400 error. Additionally, `translate_stream` and `chat_stream` use only 1000 tokens — reasoning can consume most of that budget invisibly, truncating output.

## What Changes

- Raise `max_completion_tokens` in `test_connection` from 1 → 50 (enough for reasoning overhead)
- Raise `max_completion_tokens` in `translate_stream` and `chat_stream` from 1000 → 4096 (room for reasoning + visible output)
- Add `reasoning_effort: "none"` to `translate_stream` requests when the configured model is a reasoning model (GPT-5/o-series) — translation doesn't need chain-of-thought, so all tokens go to visible output
- Keep reasoning enabled for `chat_stream` (free-form Q&A benefits from reasoning)
- Only inject reasoning parameters when the model name indicates support (prefix match: `gpt-5`, `o1`, `o3`) — providers that don't support it won't receive it

## Capabilities

### New Capabilities
- `reasoning-aware-api`: Conditional reasoning parameter injection and token budget adjustments for GPT-5/o-series model compatibility

### Modified Capabilities

## Impact

- `src-tauri/src/api.rs`: all three request builders (`test_connection`, `translate_stream`, `chat_stream`) modified
- No new dependencies, no UI changes, no config schema changes
- Backwards-compatible: non-reasoning models and third-party providers see no new parameters
