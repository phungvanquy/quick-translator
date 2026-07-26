## MODIFIED Requirements

### Requirement: Ctrl+C+Space triggers chat

The chat action SHALL be triggered by the two-step sequence stored in the `hotkeys.chat` config entry, defaulting to `Ctrl+C` → `Space` within 600ms. It MUST NOT be hardcoded — Ctrl+C+Space is now the default binding rather than the only one.

#### Scenario: Default binding preserves prior behavior

- **WHEN** no hotkey config has been saved
- **THEN** Ctrl+C followed by Space within 600ms triggers chat, matching the behavior before hotkeys became configurable

#### Scenario: Rebound trigger

- **WHEN** the user rebinds chat and saves
- **THEN** the new sequence triggers chat and the previous one no longer does

#### Scenario: Shared arm window across actions

- **WHEN** two actions share the same prefix and the user presses that prefix once
- **THEN** whichever configured `then` key arrives first within the window decides the action, and only one action fires

#### Scenario: Empty selection still opens chat

- **WHEN** the resolved clipboard text is empty
- **THEN** the chat popup still opens in free-chat mode
