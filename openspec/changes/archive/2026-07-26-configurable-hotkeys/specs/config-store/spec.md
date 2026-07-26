## ADDED Requirements

### Requirement: Hotkeys stored in config

The config file SHALL hold a `hotkeys` object with one entry per action (`translate`, `chat`, `screenshot`), each carrying `prefix`, `then`, and `window_ms`. The object and each of its entries MUST be optional on read, defaulting to the built-in table when absent.

#### Scenario: Round-trip

- **WHEN** hotkeys are saved from Settings
- **THEN** they are written to `~/.quicktranslator_config.json` and reloaded on next start

#### Scenario: Partial hotkey block

- **WHEN** the stored `hotkeys` object names only some actions
- **THEN** the missing actions fall back to their defaults rather than failing the whole load

#### Scenario: Invalid table rejected on write

- **WHEN** Settings submits a hotkey table that fails validation
- **THEN** the save is rejected with the validation errors and the previously stored table is left intact
