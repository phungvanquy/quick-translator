## Why

The current UI reads as a "developer tool," not a commercial product: it uses the stock GitHub-dark palette (green GitHub-primary buttons, blue links), emoji as UI icons (✕, ⟶, 💬, ⠋, 🔊), flat square windows with fake 1px borders, and cramped spacing. Emoji render inconsistently across machines and feel toy-like; the palette and lack of depth undercut trust. This change gives the app a distinct, harmonious brand identity and the polish expected of a paid app.

## What Changes

- Introduce an **indigo/violet brand color** (accent `#7C6BFF` dark / `#6D5AE6` light) replacing the GitHub green/blue as the primary/link/focus color.
- Add a **light theme** alongside dark, switching automatically with the OS via `prefers-color-scheme`. All colors move to a shared token set with two value sets.
- Replace **all emoji icons** (close, language arrow, chat, spinner, TTS, copy, reset) with a consistent set of **inline SVG line icons** (single stroke weight, `currentColor`). No icon-font or runtime dependency.
- Add **visual depth**: real rounded window corners, a soft drop shadow, and layered elevation (header vs. body vs. bubbles) — replacing the 1px fake-border trick.
- **Loosen spacing** and typography: more padding/breathing room, and drop the ALL-CAPS letter-spaced field labels in Settings for a softer, more consumer feel.
- Chat: the **user bubble** uses an accent-soft tint (not neutral gray) to clearly distinguish user vs. assistant.
- Redesign the **app icon** (`icons/icon.png` 512px + `icons/icon.ico` multi-size) as a two-arrows ⇄ glyph on an indigo gradient, matching the brand color (used by the tray and installer).

Not changing: the *behavior* of any window (triggers, streaming, dismissal, copy, validation). This is a visual/branding redesign only.

## Capabilities

### New Capabilities
- `ui-theme`: The app-wide visual design system — brand color tokens, dark+light theme with automatic OS-preference switching, the shared inline SVG icon set, elevation/shadow/radius conventions, and the app icon artwork.

### Modified Capabilities
- `translation-popup`: The appearance requirement that pins the popup to "the GitHub-dark palette" changes to "the app theme (dark+light)"; emoji controls become SVG icons; rounded corners + shadow.
- `chat-popup`: Same theme/icon change; the user message bubble adopts the accent-soft tint.

## Impact

- **Frontend**: `frontend/theme.css` (rewritten — dark+light tokens, radius, shadow, and shared SVG symbol/definitions), `frontend/popup.{html,css,js}`, `frontend/chat.{html,css,js}`, `frontend/settings.{html,css,js}`.
- **Backend**: `src-tauri/src/windows.rs` — may enable `transparent: true` on the two popup windows so corners can be truly rounded (see design.md open question for the Windows shadow/always-on-top fallback).
- **Assets**: `src-tauri/icons/icon.png` + `src-tauri/icons/icon.ico` regenerated.
- **Dependencies**: possibly a small dev-time image tool (e.g. Python + Pillow, or the Rust `image` crate) to generate the icon PNG/ICO; SVG icon paths may be adapted from MIT-licensed sets (Lucide/Feather) — copied as inline paths, no runtime dep added. Allowed under the updated project dependency rule.
- **No behavioral/API changes**; config format unchanged.
