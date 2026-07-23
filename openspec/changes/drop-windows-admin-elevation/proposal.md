## Why

The app requests `requireAdministrator` on every launch, but this was inherited unverified from the old Python (`--uac-admin`) prototype. On Windows, UIPI only blocks a low-level keyboard hook when the **foreground window is itself elevated** (Task Manager, admin terminal, regedit). For the overwhelming majority of use — translating/chatting on text in browsers, editors, chat apps, PDFs — medium integrity works fine. The elevation costs a UAC prompt on every launch, blocks normal Startup-folder auto-start, and needlessly runs a network-calling, API-key-holding app at full admin.

## What Changes

- **BREAKING** (behavioral): switch `src-tauri/app.manifest` from `requireAdministrator` to `asInvoker`. The produced `.exe` no longer elevates or shows a UAC prompt on launch.
- Accept the tradeoff: the global hotkey will not fire while an elevated window is in the foreground. Document "Run as administrator" as the manual, per-session workaround for that rare case.
- Update the `windows-tauri-build` spec, which currently *mandates* `requireAdministrator`, to require `asInvoker` and describe the documented workaround.
- Update `Readme.md` and `CLAUDE.md` notes that currently tell users elevation is required.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `windows-tauri-build`: the "Windows admin elevation" requirement is replaced — the embedded manifest must request `asInvoker` (no elevation) instead of `requireAdministrator`, with the elevated-foreground-window limitation documented.

## Impact

- **Code/config**: `src-tauri/app.manifest` (execution level line). No Rust logic changes — `build.rs`, `hotkey.rs`, and the rest are unaffected.
- **Docs**: `Readme.md` (the "run as Administrator" note), `CLAUDE.md` (the "Admin elevation via app.manifest" design-decision bullet).
- **Behavior**: no more UAC prompt on launch; normal Startup-folder auto-start now possible; hotkey inactive over elevated foreground windows unless the user manually runs the app elevated.
- **Dependencies**: none.
