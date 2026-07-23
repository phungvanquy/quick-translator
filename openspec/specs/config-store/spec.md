# config-store Specification

## Purpose
TBD - created by archiving change rewrite-rust-tauri-stage1. Update Purpose after archive.
## Requirements
### Requirement: Config file location and schema

The application SHALL persist configuration at `~/.quicktranslator_config.json` using a schema and defaults identical to the Python `config.py`, so that an existing Python user's config file remains valid and interoperable.

#### Scenario: Schema and defaults

- **WHEN** configuration is represented in memory or written to disk
- **THEN** it contains exactly these keys with these defaults: `api_key` (""), `base_url` ("https://api.openai.com/v1"), `target_language` ("Vietnamese"), `model` ("gpt-4o-mini"), `custom_prompt` (the translator template containing the `{target_language}` placeholder, matching `DEFAULT_PROMPT` in `config.py`)

#### Scenario: Existing Python config keeps working

- **WHEN** a config file previously written by the Python app is loaded
- **THEN** it loads without error and all previously stored values are preserved

### Requirement: Config load behavior

Loading SHALL merge file contents over the defaults so missing keys fall back to defaults.

#### Scenario: Partial config file

- **WHEN** the config file exists but is missing some keys
- **THEN** the missing keys take their default values and the present keys are used as stored

#### Scenario: Missing or malformed config file

- **WHEN** the config file does not exist, or exists but cannot be parsed as JSON
- **THEN** the in-memory config falls back to the full defaults
- **AND** when the file was simply absent, a default config file is written to disk

### Requirement: Config save behavior

Saving SHALL write pretty-printed, UTF-8, non-ASCII-escaped JSON.

#### Scenario: Save format

- **WHEN** configuration is saved
- **THEN** the file is written as JSON indented for readability, encoded UTF-8, with non-ASCII characters preserved literally (not `\uXXXX`-escaped)

### Requirement: Settings window

The application SHALL provide a Settings window to view and edit the core credentials/target fields AND the `custom_prompt` field, and persist them to the config file. The `custom_prompt` field is already stored in config and used by the backend translate flow; the settings UI SHALL surface it so it is user-editable.

#### Scenario: Edit and save

- **WHEN** the user opens Settings, edits `api_key`, `base_url`, `model`, and/or `target_language`, and saves
- **THEN** the values are written to `~/.quicktranslator_config.json` in the save format above
- **AND** subsequent translations use the updated values (a new API client/credentials take effect without restarting the app)

#### Scenario: Edit custom prompt

- **WHEN** the user opens Settings, edits the custom prompt in a multi-line field, and saves
- **THEN** the `custom_prompt` value is written to `~/.quicktranslator_config.json`
- **AND** subsequent translations use the updated prompt (with `{target_language}` substituted where present)

#### Scenario: Reset custom prompt to default

- **WHEN** the user clicks the reset-to-default control for the custom prompt
- **THEN** the field is repopulated with the default translator template
- **WHEN** the user saves with the custom prompt left blank
- **THEN** the stored `custom_prompt` falls back to the default template rather than an empty string

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

