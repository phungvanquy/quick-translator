## ADDED Requirements

### Requirement: Settings input validation

The Settings window SHALL validate inputs before saving and give the user clear, inline feedback for problems, rather than deferring failures to the translate/chat flow.

#### Scenario: Malformed base URL blocked

- **WHEN** the user saves with a non-empty `base_url` that is not a well-formed `http://` or `https://` URL
- **THEN** the save is blocked and an inline error identifies the base URL as the problem

#### Scenario: Empty base URL allowed

- **WHEN** the user saves with an empty `base_url`
- **THEN** the save proceeds (the backend falls back to the default OpenAI endpoint)

#### Scenario: Empty API key warned, not blocked

- **WHEN** the user saves with an empty `api_key`
- **THEN** the save proceeds AND a non-blocking warning notes that translation/chat will not work until a key is set

### Requirement: Connection test

The Settings window SHALL let the user test the configured endpoint, key, and model with a minimal live request and report the outcome inline, without opening a translate or chat popup.

#### Scenario: Successful test

- **WHEN** the user clicks "Test connection" with a reachable endpoint, valid key, and valid model
- **THEN** a minimal request is issued and a success indication is shown

#### Scenario: Failed test reports a clear reason

- **WHEN** the connection test fails (network error, non-success HTTP status, or auth failure)
- **THEN** a human-readable error is shown inline indicating the reason (e.g. the HTTP status or a connection error), and no popup is opened

#### Scenario: Test uses current form values

- **WHEN** the user edits fields and clicks "Test connection" before saving
- **THEN** the test uses the values currently in the form (not only the last-saved config)
