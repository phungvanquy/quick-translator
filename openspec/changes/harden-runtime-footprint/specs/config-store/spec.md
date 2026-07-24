## MODIFIED Requirements

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

#### Scenario: Insecure http base URL warned, not blocked

- **WHEN** the user saves with a well-formed `base_url` that uses the `http://` scheme (not `https://`)
- **THEN** the save proceeds AND a non-blocking warning notes that the API key will be sent unencrypted over `http://`
- **AND** an `https://` or empty `base_url` produces no such warning
