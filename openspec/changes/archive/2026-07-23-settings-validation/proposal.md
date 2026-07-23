## Why

Settings saves whatever you type with no feedback: a malformed `base_url` (missing scheme, typo) or a blank `api_key` only surfaces later as an opaque failure inside the translate/chat popup — far from where the mistake was made. There is no way to confirm the endpoint + key + model actually work without triggering a real translation and hoping.

## What Changes

- Add **client-side validation** on save: `base_url` must be a well-formed `http(s)://` URL (empty is allowed → backend defaults to the OpenAI URL), and an **empty `api_key` shows a non-blocking warning** (the app is usable but won't translate).
- Add a **"Test connection" button** that performs a minimal live request against the configured `base_url` / `api_key` / `model` and reports success or a clear error (HTTP status / network / auth), without opening a popup.
- Surface validation and test results inline near the fields / actions, reusing the existing `save-status` styling pattern.

No breaking changes. Config schema and file format are unchanged (Python-interop preserved). Saving remains possible; validation blocks only clearly-malformed `base_url` and otherwise warns rather than prevents.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `config-store`: the Settings window gains input validation on save and a connection-test affordance. (Config location/schema/load/save requirements are unchanged.)

## Impact

- `frontend/settings.html` — a "Test connection" button + a result/validation message area.
- `frontend/settings.css` — styling for validation/error/warning/success states.
- `frontend/settings.js` — validate `base_url` (URL parse) and warn on empty `api_key` before `update_config`; wire the test button to a new backend command.
- `src-tauri/src/main.rs` + `src-tauri/src/api.rs` — new `#[tauri::command] test_connection` that issues a minimal, short-timeout, non-streaming request (or a `/models`-style probe) using the current-form values and returns Ok / a human-readable error.
- Reuses existing `reqwest` client + `CONNECT_TIMEOUT` pattern in `api.rs`; no new dependencies. No config format change.
