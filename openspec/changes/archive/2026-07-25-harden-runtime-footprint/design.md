## Context

The hotkey engine is a single `rdev::listen` thread (`hotkey.rs`) that, on Windows, installs both a `WH_KEYBOARD_LL` and a `WH_MOUSE_LL` low-level hook. Every keyboard and mouse event on the machine is dispatched to this process's callback before continuing. This is the price of passive double-tap detection (the Tauri global-shortcut plugin cannot express `Ctrl+C` twice — see `translate-hotkey` spec) and is not being removed here. What this change removes is the *avoidable* per-event cost and the fragility layered on top of that hook.

Windows enforces `LowLevelHooksTimeout` (default ~300 ms, `HKCU\Control Panel\Desktop`): if a low-level hook callback does not return within that budget, the OS may skip the callback for that event or silently unhook it. Anything slow or blocking in the callback path therefore risks both system-wide input latency and losing the hotkey entirely.

## Goals / Non-Goals

**Goals**
- Cut the mouse-move hot path (mutex lock per move) out of the system-wide event dispatch.
- Keep the hook callback cheap: no thread spawns, no blocking, no panics that can poison shared state.
- Prevent a second instance from installing a duplicate hook set.
- Preserve exactly the observable behavior: hotkey timing, popup position near the cursor, translate/chat/streaming flows.

**Non-Goals**
- Removing the mouse LL hook itself (requires replacing `rdev::listen`).
- Restoring the user's clipboard.
- Encrypting the stored API key.

## Decisions

**D1: Sample the cursor on demand, delete `LAST_CURSOR_POS`.**
The cursor coordinate is consumed only in `handle_translate_trigger` / `handle_chat_trigger`, once per fire. Continuously mirroring it on every `MouseMove` is pure overhead on a system-wide hot path. Replace with a `cursor_pos()` that calls `GetCursorPos` at trigger time. `MouseMove` is then dropped from the callback match, leaving only `KeyPress` processing.

**D2: Delete the 600 ms reset thread; rely on lazy arm expiry.**
Every path that *fires* already gates on `now.duration_since(last_ctrl_c_time) < 600ms` (`hotkey.rs:130` for translate, `:167` for chat). So even if `armed` stays `true` indefinitely, a later `Ctrl+C` outside the window simply re-arms with a fresh timestamp and cannot mis-fire. The thread that flips `armed=false` after sleeping 600 ms is therefore redundant *and* is the worst offender for "work spawned from the hook callback." Removing it makes the callback allocation-free on the common path.

**D3: Single instance via the official plugin.**
`tauri-plugin-single-instance` (Tauri-maintained, v2 line, matches our `tauri = "2"`) is the least-surprising, well-vetted option (satisfies the CLAUDE.md dependency policy: maintained, widely used, trusted source, pinned major). On a second launch its callback runs in the primary instance; we use it to surface Settings (there is no main window to focus). This prevents the concrete harm — two hook sets, double-fire, doubled system-wide hook cost.

**D4: Recover a poisoned lock instead of unwrapping.**
Replace `state.lock().unwrap()` in the hook thread with `lock().unwrap_or_else(|e| e.into_inner())`. The protected data (`armed`, timestamps) is plain `Copy` state with no invariant that a mid-panic write could corrupt in a dangerous way, so proceeding with the recovered guard is safe and strictly better than letting one panic permanently kill the global hook.

**D5: `http://` is a warning, not a block.**
`settings-validation` already blocks a malformed/scheme-less `base_url` and allows empty. `http://` is well-formed and occasionally legitimate (localhost, a LAN proxy, a self-hosted gateway), so blocking it would be wrong. A non-blocking warning ("API key will be sent unencrypted over http://") matches the existing empty-api-key warning pattern and keeps the user in control.

## Rejected / Deferred

**R1: Restore the pre-copy clipboard (was proposal item "D").**
The app only *reads* the clipboard; it is the user's own two `Ctrl+C` presses that overwrite it. To restore the prior contents we would have to know them, i.e. snapshot the clipboard *before* the user copied — which requires either continuous clipboard monitoring (heavy, and a second system-wide watcher) or reading the clipboard inside the hotkey path *before* the copy lands (racy, and it adds a blocking clipboard read to the hook path we are trying to keep light). The cost/complexity outweighs the benefit; rejected. Revisit only if users report clipboard clobbering as a real pain point.

**R2: Remove the low-level mouse hook entirely.**
`rdev::listen` installs keyboard + mouse hooks together with no opt-out. Dropping `MouseMove` handling (D1) removes our per-event *work* but the mouse hook is still installed by rdev, so the OS still dispatches mouse events to it as a no-op. Fully removing it means replacing `rdev::listen` with a direct `SetWindowsHookEx(WH_KEYBOARD_LL)` or a keyboard-only crate — a larger, riskier swap of the core input path. Deferred; recorded here so the option is not lost.

## Risks / Trade-offs

- **`GetCursorPos` returns physical or logical pixels?** `GetCursorPos` returns physical screen coordinates when the process is per-monitor DPI-aware — the same space `rdev` currently reports, which `position_at_cursor` already treats as physical (`windows.rs:119`). **OQ1 (verify on a real Windows build):** confirm the popup still anchors correctly at the cursor on a high-DPI / multi-monitor setup after the switch. If it is off, the fix is to mark the process per-monitor-DPI-aware (manifest) or convert explicitly; record the outcome in CLAUDE.md.
- **Single-instance plugin adds a dependency.** Small, official, pinned — within the CLAUDE.md dependency policy. Trade-off accepted for correctness (no duplicate global hooks).
- **Cannot be verified in headless CI.** All of this rests on a real Windows run with the global hook active; the Windows CI build is only the compile gate. The manual QA checklist in CLAUDE.md is where cursor positioning, single-instance, and no-double-fire get confirmed before a release tag.
