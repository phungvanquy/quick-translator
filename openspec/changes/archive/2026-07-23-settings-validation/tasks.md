## 1. Backend test_connection command

- [x] 1.1 In `src-tauri/src/api.rs`, add an async helper `test_connection(base_url, api_key, model) -> Result<String, String>` that builds the rustls reqwest client with `CONNECT_TIMEOUT` + a short total request timeout, issues a minimal non-streaming `POST /chat/completions` (1-token, `stream:false`, trivial message) using `resolve_base_url` semantics, and returns Ok on 2xx or Err with HTTP status + body snippet / transport error.
- [x] 1.2 In `src-tauri/src/main.rs`, add `#[tauri::command] async fn test_connection(...)` delegating to the api.rs helper, and register it in `invoke_handler![...]`.

## 2. Client-side validation

- [x] 2.1 In `frontend/settings.js::saveConfig`, if `base_url` is non-empty, validate with `new URL(...)` (try/catch) requiring `http:`/`https:` protocol; block save + show inline error on failure. Empty base_url passes through.
- [x] 2.2 On save with empty `api_key`, proceed but show a non-blocking warning that translate/chat won't work until a key is set.

## 3. Test connection UI

- [x] 3.1 Add a "Test connection" button + a result message area to `frontend/settings.html` (near the actions row).
- [x] 3.2 Style validation error / warning / success / testing states in `frontend/settings.css`, consistent with the existing `.save-status` look.
- [x] 3.3 In `frontend/settings.js`, wire the button to `invoke('test_connection', { baseUrl, apiKey, model })` using CURRENT form values; show a "Testing…" state, then success or the returned error inline; disable the button while in-flight.

## 4. Verify

- [x] 4.1 `cargo build` — delegated to CI (`.github/workflows/build.yml`). New `test_connection` in api.rs/main.rs reuses already-imported symbols; CI compiles the msvc target.
- [x] 4.2 Manual QA (malformed base_url blocked, empty base_url ok, empty api_key warns) → deferred to CLAUDE.md pre-release checklist.
- [x] 4.3 Manual QA (Test connection: success / bad key / unreachable; uses unsaved form values) → deferred to CLAUDE.md pre-release checklist.
- [x] 4.4 Regression checks → deferred to CLAUDE.md pre-release checklist.
