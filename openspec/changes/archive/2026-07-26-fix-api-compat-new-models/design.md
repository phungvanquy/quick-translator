## Context

The app constructs raw JSON bodies for OpenAI-compatible `chat/completions` endpoints. It currently sends `max_completion_tokens` (correct parameter name) but with values too low for reasoning models, and without `reasoning_effort` to disable internal chain-of-thought where unnecessary. The app supports arbitrary `base_url`, meaning requests may target OpenAI, Azure, or third-party providers.

## Goals / Non-Goals

**Goals:**
- Fix `test_connection` 400 error on GPT-5 models
- Prevent translation truncation from reasoning token consumption
- Add `reasoning_effort: "none"` for translate (no reasoning needed) on supported models
- Maintain compatibility with older models and third-party providers

**Non-Goals:**
- Adding UI controls for reasoning_effort or max_completion_tokens
- Supporting the Responses API (different endpoint entirely)
- Model-specific token limits or dynamic budget calculation

## Decisions

**1. Model detection via prefix match**

A helper function `is_reasoning_model(model: &str) -> bool` checks if the model name starts with `gpt-5`, `o1`, or `o3` (case-insensitive). This covers all current reasoning models without requiring an exhaustive list.

Rationale: Simple, no external data needed, easy to extend. False negatives (unknown reasoning model) just mean no optimization — still works. False positives are unlikely given naming conventions.

**2. Conditional parameter injection (not unconditional)**

Only add `reasoning_effort` to the JSON body when `is_reasoning_model()` returns true. Non-reasoning models and third-party providers never see the parameter.

Alternative considered: Always send `reasoning_effort: "none"` — rejected because providers like Ollama/LM Studio reject unknown parameters with 400.

**3. Token budget values**

| Function | Current | New |
|----------|---------|-----|
| `test_connection` | 1 | 50 |
| `translate_stream` | 1000 | 4096 |
| `chat_stream` | 1000 | 4096 |

Rationale: 50 is enough for any model to produce at least one visible token. 4096 accommodates reasoning overhead (~600-900 tokens) while leaving ample room for output. Cost is only incurred for tokens actually generated.

**4. `reasoning_effort: "none"` only for translate, not chat**

Translation is a deterministic mapping task — reasoning adds latency and wastes tokens. Chat is free-form Q&A where reasoning can improve quality.

## Risks / Trade-offs

- **[Risk] OpenAI changes model naming** → Mitigation: prefix list is easy to update; worst case is no optimization (still functional)
- **[Risk] GPT-5.4 bug where `reasoning_effort: "none"` + `max_completion_tokens` ignores the flag** → Mitigation: OpenAI patched this April 2026; 4096 budget is large enough that even with some reasoning token consumption, output won't truncate for typical translations
- **[Risk] Third-party provider falsely matches `gpt-5` prefix** → Mitigation: unlikely; if it happens, `reasoning_effort: "none"` is a no-op or rejected (user sees error, can change model name)
- **[Trade-off] Higher token limit means potentially higher cost per request** → Acceptable: tokens are billed on actual usage, not limit; this just raises the ceiling
