## ADDED Requirements

### Requirement: Vision model field

The config SHALL hold a `vision_model` string, optional on read and defaulting to empty. Settings MUST surface it as an editable field.

#### Scenario: Round-trip

- **WHEN** `vision_model` is saved from Settings
- **THEN** it is persisted and reloaded on next start

#### Scenario: Absent in an older config

- **WHEN** an existing config file predates this field
- **THEN** it loads as empty and image requests fall back to the main `model`

#### Scenario: Connection test covers both models

- **WHEN** the user tests the connection with a `vision_model` set
- **THEN** both the main model and the vision model are tested, since either can be misconfigured independently
