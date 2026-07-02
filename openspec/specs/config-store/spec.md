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

The application SHALL provide a Settings window to view and edit the core credentials/target fields and persist them to the config file.

#### Scenario: Edit and save

- **WHEN** the user opens Settings, edits `api_key`, `base_url`, `model`, and/or `target_language`, and saves
- **THEN** the values are written to `~/.quicktranslator_config.json` in the save format above
- **AND** subsequent translations use the updated values (a new API client/credentials take effect without restarting the app)

