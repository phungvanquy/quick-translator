## MODIFIED Requirements

### Requirement: Error and missing-key handling

The application SHALL surface API problems as user-visible text. Because the popup is small and appears over whatever the user was doing, a failure SHALL be presented as one short readable line, with the underlying raw detail retained and reachable on demand rather than rendered inline. The user SHALL be able to retry without re-selecting the source text.

#### Scenario: No API key configured

- **WHEN** a translation is requested and the configured `api_key` is empty
- **THEN** no HTTP request is made
- **AND** the popup displays `⚠ No API key set.` followed by a line instructing the user to open Settings from the tray icon

#### Scenario: Failure shows a readable summary, not a raw dump

- **WHEN** the HTTP request fails, returns a non-success status, or the stream errors
- **THEN** the popup shows a short summary naming the kind of failure (for example an authentication problem, a rate limit, a connection problem, or a timeout) rather than a raw status line concatenated with the response body
- **AND** the response body is not rendered inline where it would fill the popup

#### Scenario: Raw detail remains available

- **WHEN** a failure summary is shown and the user asks to see the detail
- **THEN** the underlying status and response body are shown, so an unrecognized server error is still diagnosable

#### Scenario: Retry without re-selecting

- **WHEN** a translation has failed
- **THEN** the popup offers a retry control that re-issues the same translation for the same captured text
- **AND** retrying returns the popup to its loading state and streams into the same window

#### Scenario: Cancellation is not reported as failure

- **WHEN** the stream stops because the popup was closed
- **THEN** no error is produced, since there is no window remaining to display it and the user's own action ended it
