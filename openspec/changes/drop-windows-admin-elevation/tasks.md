## 1. Manifest change

- [x] 1.1 In `src-tauri/app.manifest`, change `<requestedExecutionLevel level="requireAdministrator" uiAccess="false" />` to `level="asInvoker"`, leaving the ComCtl32 v6 dependency and `supportedOS`/`compatibility` blocks intact
- [x] 1.2 Confirm `src-tauri/build.rs` still embeds the manifest unchanged (no code change expected — verify only)

## 2. Documentation

- [x] 2.1 Update `Readme.md`: replace the "run as Administrator — global hotkeys require elevated privileges" note with the new behavior (no elevation needed; hotkey inactive over elevated foreground windows; run as admin as the manual workaround)
- [x] 2.2 Update `CLAUDE.md`: revise the "Admin elevation via app.manifest (requireAdministrator)" design-decision bullet to reflect `asInvoker` and the documented UIPI limitation

## 3. Verification

- [x] 3.1 Sanity-check the manifest XML is well-formed (single `requestedExecutionLevel`, `asInvoker`)
- [x] 3.2 Add to the pre-release manual QA checklist (Windows run): launch shows NO UAC prompt; Ctrl+C+C / Ctrl+C+Space work over normal windows; hotkey confirmed inactive over an elevated foreground window unless the app itself is run as admin
