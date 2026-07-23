## Context

`settings.js::saveConfig` trims and forwards every field to `update_config` with no validation. `api.rs::resolve_base_url` already treats an empty `base_url` as the OpenAI default and trims a trailing slash — so "empty is valid" is existing behavior we must not break. The only test framework in-repo is a Node unit test for the markdown renderer; Rust core logic is untested. The reqwest client + `CONNECT_TIMEOUT` (15s) pattern lives in `api.rs::stream_completion`.

Constraints:
- Config schema/format is Python-interoperable and must not change.
- New backend commands must be added to `invoke_handler![...]` in `main.rs` (currently: `get_config, update_config, open_settings_cmd, chat_send`).
- Custom `#[tauri::command]`s are NOT ACL-gated (per CLAUDE.md), so no `capabilities/default.json` change is needed for a new command.

## Goals / Non-Goals

**Goals:**
- Catch a malformed `base_url` and an empty `api_key` at save time, inline.
- Let the user verify endpoint + key + model with one click, using current form values.
- Reuse existing reqwest/timeout patterns; no new dependencies.

**Non-Goals:**
- Validating `model` or `target_language` strings (free-form; server rejects unknowns — the connection test covers real reachability).
- Auto-testing on every save (explicit button only).
- Streaming during the test; the probe is a minimal non-streaming call.
- Changing config schema, defaults, or file format.

## Decisions

### Decision: `base_url` validated with the browser `URL` parser
In `settings.js`, before calling `update_config`: if `base_url` is non-empty, `new URL(base_url)` inside try/catch and require `protocol` ∈ {`http:`,`https:`}. On failure, block save and show an inline error tied to the base-url field. Empty passes through (matches `resolve_base_url` default).
- **Alternative considered**: a regex — rejected, `URL` is built-in and more correct.

### Decision: Empty `api_key` warns but does not block
Saving with no key is legitimate (user may fill it later; first-run opens Settings with an empty key). So: proceed with the save, then show a warning-styled status noting translate/chat won't work yet. This matches the backend, which already emits a "No API key set" message instead of erroring.

### Decision: `test_connection` is a new backend command doing a minimal non-streaming probe
Add `#[tauri::command] async fn test_connection(base_url, api_key, model) -> Result<String, String>` in `main.rs` (thin) delegating to a helper in `api.rs`. The helper:
- reuses `resolve_base_url` semantics,
- builds the same rustls reqwest client with `CONNECT_TIMEOUT`, plus a short overall request timeout (this call is NOT long-lived streaming, so a total timeout ~15s is safe and prevents a hung spinner),
- issues a minimal `POST /chat/completions` with the given `model`, a 1-token `max_completion_tokens`, `stream:false`, and a trivial message — OR a `GET /models` probe. **Prefer the chat/completions probe** because it exercises the exact path translate/chat use (model access + auth), whereas `/models` may be permitted even when the model isn't.
- returns `Ok("...")` on 2xx, else `Err` with the HTTP status + a snippet of the body, or the transport error string.

Passing the values as command args (not reading saved config) satisfies "test uses current form values" without forcing a save first.
- **Alternative considered**: reuse `stream_completion` with `stream:false` — rejected, that function is wired to emit window events; a small dedicated helper is cleaner and returns a value directly.

### Decision: Inline feedback reuses the `save-status` pattern
Extend the existing `showStatus(msg, isError)` mechanism (or add a sibling for warning/success variants) and a dedicated result line near the actions row, styled in `settings.css`. Keep the 3s auto-clear for transient messages; the test result can persist until the next action.

## Risks / Trade-offs

- **A probe request costs a token / hits rate limits** → Mitigation: cap at 1 completion token and only run on explicit click; it is far cheaper than the real translate the user would otherwise do to "test".
- **Some OpenAI-compatible servers reject `max_completion_tokens`** (older `max_tokens` naming) → Mitigation: the app already standardizes on `max_completion_tokens` in `api.rs`, so the probe matches real behavior; if the server errors on it, that is the same failure the real flow would hit and is worth surfacing.
- **Test button focus/blur** → Settings is a normal decorated window (not blur-to-close), so no dismissal risk from clicking the button.
- **No automated test for the new Rust helper** → Mitigation: keep the helper small and pure-ish (takes explicit args, returns Result); manual QA in the checklist. A unit test can stub via a local mock server later but is out of scope here.
