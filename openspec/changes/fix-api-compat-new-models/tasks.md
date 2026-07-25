## 1. Model Detection Helper

- [x] 1.1 Add `fn is_reasoning_model(model: &str) -> bool` in `api.rs` — case-insensitive prefix match for `gpt-5`, `o1-`, `o3-`

## 2. Fix Token Budgets

- [x] 2.1 Change `max_completion_tokens` from 1 to 50 in `test_connection`
- [x] 2.2 Change `max_completion_tokens` from 1000 to 4096 in `translate_stream`
- [x] 2.3 Change `max_completion_tokens` from 1000 to 4096 in `chat_stream`

## 3. Conditional Reasoning Effort

- [x] 3.1 In `translate_stream`, conditionally insert `"reasoning_effort": "none"` into the request body when `is_reasoning_model(&cfg.model)` is true
- [x] 3.2 Verify `chat_stream` does NOT include `reasoning_effort` (no change needed, just confirm)

## 4. Verification

- [ ] 4.1 `cargo build` passes (verify in CI — no local Rust toolchain)
