## MODIFIED Requirements

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
