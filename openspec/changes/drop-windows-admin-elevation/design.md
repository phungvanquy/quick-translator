## Context

`src-tauri/app.manifest` declares `<requestedExecutionLevel level="requireAdministrator" />`, embedded into the exe via `build.rs` (`tauri_build::WindowsAttributes::app_manifest`). This elevation was carried over verbatim from the Python prototype's `--uac-admin` flag when the app was rewritten in Rust/Tauri (change `rewrite-rust-tauri-stage1`). The archived design (D9) notes the rationale only tentatively: "rdev on Windows *may* need admin to see elevated windows' input" — never verified against the Rust build.

The app's hotkey engine (`hotkey.rs`) uses `rdev::listen`, a passive `WH_KEYBOARD_LL` low-level hook. On Windows, UIPI (User Interface Privilege Isolation) prevents a medium-integrity process's low-level hook from receiving input **only while the foreground window is a higher-integrity (elevated) process**. All non-elevated foreground windows deliver input to the hook normally.

## Goals / Non-Goals

**Goals:**
- Remove the always-on UAC prompt and full-admin runtime by switching the manifest to `asInvoker`.
- Preserve all hotkey/clipboard/popup behavior for the common (non-elevated foreground) case.
- Keep the spec, Readme, and CLAUDE.md truthful about the new behavior and its one limitation.

**Non-Goals:**
- No "Restart as admin" button or `highestAvailable` auto-elevation (Options B/D from exploration) — deferred; this change is the minimal asInvoker switch.
- No changes to Rust logic, CI, or bundle config beyond the manifest execution level.

## Decisions

**D1: Use `asInvoker`, not `highestAvailable`.**
`asInvoker` runs at the caller's integrity (medium for a normal launch) with zero UAC prompt and predictable behavior on every machine. `highestAvailable` would elevate whenever the user is an admin, reintroducing the UAC prompt for admin users and producing inconsistent behavior across machines — harder to support. Rejected.

**D2: Keep the manifest file; change only the execution-level line.**
The manifest also carries the ComCtl32 v6 dependency and `supportedOS` block (added in `f1f89fa`), which must stay. Editing the single `level=` attribute is the smallest correct change; deleting the manifest would drop those and revert to Tauri's default.

**D3: Document "Run as administrator" as the manual workaround.**
For the rare case of translating text inside an elevated foreground window, right-click → Run as administrator restores the hook for that session. This is a documented instruction, not code.

## Risks / Trade-offs

- **Hotkey silently inactive over an elevated foreground window** → Documented in Readme + the elevation spec; manual "Run as administrator" restores it. Acceptable because it is a narrow, self-explanatory case (the hotkey simply does nothing while such a window is focused).
- **Cannot verify on the Linux dev environment** → Behavior rests on documented Windows UIPI semantics; the Windows CI build is the compile gate, and the manual QA checklist (a real Windows run) is where the no-UAC-prompt and hotkey behavior get confirmed before release.
- **Existing users accustomed to the UAC prompt** → Non-issue; removing a prompt is strictly less friction. Auto-start via the Startup folder now works where it previously required a Task Scheduler workaround.
