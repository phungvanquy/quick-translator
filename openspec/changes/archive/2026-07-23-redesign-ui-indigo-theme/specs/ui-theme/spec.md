## ADDED Requirements

### Requirement: Brand color system

The application SHALL present a single indigo/violet brand accent used consistently for primary buttons, links, active/focus states, and heading accents across all windows. All colors SHALL be defined as shared design tokens (CSS custom properties) rather than per-component literal values, so that a single token set drives every surface.

#### Scenario: Accent applied consistently

- **WHEN** any window renders an interactive primary control, a link, a focused input, or a Markdown heading
- **THEN** it uses the shared indigo brand accent token (not the previous GitHub green/blue)

#### Scenario: Components read tokens only

- **WHEN** a component needs a color
- **THEN** it references a shared token (e.g. accent, surface, text, border) and never a hard-coded hex value

### Requirement: Dark and light themes follow the OS

The application SHALL provide both a dark and a light theme and SHALL switch between them automatically according to the operating system color-scheme preference, with no in-app toggle required.

#### Scenario: Dark preference

- **WHEN** the OS color-scheme preference is dark (or unspecified)
- **THEN** all windows render with the dark token values

#### Scenario: Light preference

- **WHEN** the OS color-scheme preference is light
- **THEN** all windows render with the light token values, preserving legible contrast and the same layout

#### Scenario: Same token names across themes

- **WHEN** the theme changes between light and dark
- **THEN** only token values change; component markup and class names are unaffected

### Requirement: Consistent SVG icon set

The application SHALL use a single consistent set of vector (SVG) line icons for all UI glyphs — close, language-direction arrow, chat, loading spinner, text-to-speech, copy, and reset — replacing all emoji used as controls. Icons SHALL inherit the current text color so they re-tint automatically with the theme.

#### Scenario: No emoji as controls

- **WHEN** any window renders its controls and indicators
- **THEN** each glyph is an SVG icon from the shared set, and no emoji character is used as a UI control or status indicator

#### Scenario: Icons re-tint with theme and state

- **WHEN** the theme switches or an icon's control changes color on hover/disabled
- **THEN** the icon color follows the control's current color without needing a separate asset

#### Scenario: Loading spinner is a vector animation

- **WHEN** a window is waiting for the first streamed chunk
- **THEN** the loading indicator is an animated SVG/CSS spinner (not an emoji or text glyph)

### Requirement: Depth and elevation

Windows SHALL present real rounded corners, a soft drop shadow, and layered elevation distinguishing the window body, headers/bars, and message bubbles — rather than flat rectangles with faux 1px borders.

#### Scenario: Rounded, shadowed window

- **WHEN** a popup window is shown
- **THEN** it appears with rounded corners and a drop shadow separating it from the desktop behind it

#### Scenario: Layered surfaces

- **WHEN** a window contains a header/input bar and a content area
- **THEN** those regions are visually distinguished by elevation (surface vs. background tokens), not solely by a hairline border

### Requirement: Brand app icon

The application icon (`icons/icon.png` and `icons/icon.ico`) SHALL depict the brand mark — a two-arrows exchange glyph on an indigo gradient — and SHALL be provided at the sizes required for the system tray and the installer.

#### Scenario: Tray and installer use the brand icon

- **WHEN** the app runs (tray) or is installed
- **THEN** the displayed icon is the two-arrows indigo brand mark

#### Scenario: Multi-size ICO

- **WHEN** the packaged `.ico` is produced
- **THEN** it contains the standard icon sizes (e.g. 16/32/48/256 px) so it renders crisply in the tray and installer
