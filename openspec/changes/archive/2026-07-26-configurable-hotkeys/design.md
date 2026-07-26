## Context

The app currently has a single `rdev::listen` thread with a hardcoded state machine that recognizes exactly two sequences: Ctrl+C → C (translate) and Ctrl+C → Space (chat). Adding configurable hotkeys means this state machine must become data-driven while preserving the properties that make it safe under the Windows low-level keyboard hook budget (~300ms LowLevelHooksTimeout).

Key constraints carried forward:
- `rdev::listen` can only be called **once per process** — the listener thread cannot be restarted
- The LL hook callback must be allocation-free and fast — no per-press heap allocation, no blocking I/O
- rdev is passive/non-suppressing — all keys leak to the foreground app regardless
- Left/Right Ctrl are distinguishable (`Key::ControlLeft` / `Key::ControlRight`)
- `GetAsyncKeyState` is used for live modifier queries (avoids stuck-key desync)

## Goals / Non-Goals

**Goals:**
- Let users configure hotkeys for all three actions (translate, chat, screenshot) via the Settings UI
- Hot-swap the hotkey table when config saves (no app restart needed)
- Prevent users from choosing combos that will damage their workflow (prefix whitelist + side-effect warnings)
- Fail safely: invalid config → fall back to defaults
- Support double-tap as a first-class pattern (prefix == then)

**Non-Goals:**
- One-step hotkeys (too dangerous with a non-suppressing hook)
- Hotkeys with more than two steps (unnecessary complexity)
- Suppressing the leaked keypress in the foreground app (requires a low-level hook rewrite to use `SetWindowsHookEx` with `CallNextHookEx` suppression, which is a different project)
- Per-application hotkey profiles
- Modifier-only combos beyond the whitelisted prefixes (e.g. triple-tap Alt)

## Decisions

### 1. Hotkey model: two-step sequence only

**Decision:** Every hotkey is `(prefix, then, window_ms)`. Double-tap is `prefix == then`. No one-step hotkeys.

**Why:** rdev cannot suppress. A one-step combo like Ctrl+Alt+S fires the action AND triggers whatever Ctrl+Alt+S does in the focused app. Two-step sequences work because the first step is chosen to be idempotent/harmless, and the second step only has meaning within the arm window. This is the same insight that makes Ctrl+C+C safe today.

**Alternative rejected — allow one-step with a warning:** Users will ignore warnings. The damage (unexpected saves, lost text, closed windows) is immediate and hard to undo.

### 2. Prefix whitelist

**Decision:** The Settings UI restricts prefix to a fixed set of safe options:

| Prefix | Why safe |
|--------|----------|
| `Ctrl+C` | Copy — idempotent, already used |
| `Ctrl+Insert` | Copy — idempotent, alternative |
| `RCtrl` | Solo Right Ctrl press = no-op in all mainstream apps |
| `RShift` | Solo Right Shift press = no-op |

**Why whitelist over blacklist:** The set of dangerous prefixes is unbounded (any Ctrl+letter is dangerous). The set of safe prefixes is small and known. Whitelist eliminates the class of error.

**Extension point:** new prefixes can be added to the whitelist in future versions without schema changes.

### 3. `then` key: free choice with warnings

**Decision:** The second key can be any single key (letter, number, function key, symbol, Space). The UI shows an inline warning if prefix+then matches a known Windows shortcut (e.g. `Ctrl+C → S` warns "Ctrl+S = Save will trigger in the active app").

**Why not whitelist `then` too:** The `then` key fires AFTER the prefix, within a sub-second arm window. The prefix already leaked (and was harmless). The `then` key also leaks, but since Ctrl is still held from the prefix, the leak is `Ctrl+<then>`. This CAN be dangerous (Ctrl+S = Save), hence warnings. But restricting `then` to a tiny set kills usability.

### 4. State held in `ArcSwap<ParsedHotkeys>`

**Decision:** The parsed hotkey table lives in an `ArcSwap` (or `RwLock` — see tradeoff below), separate from `ConfigState`. The rdev callback reads it with `load()` (no lock contention). Settings save swaps the entire table atomically.

**Why not read ConfigState in the hook:** ConfigState is behind a `Mutex`. Locking a mutex in the LL hook callback risks blocking beyond LowLevelHooksTimeout if another thread holds it (e.g. during save). `ArcSwap::load` is wait-free.

**`ArcSwap` vs `RwLock`:** `ArcSwap` is a new dependency but gives wait-free reads with zero contention. `RwLock` is stdlib but read-locks can still block briefly during a write. Given the hook runs on every keypress system-wide, wait-free wins. `arc-swap` is 0-dep, 300 LOC, widely used.

**Alternative rejected — channel from save to listener:** Over-engineered. The listener would need to poll the channel on every key event (adds latency) or use a separate thread (unnecessary).

### 5. Key-repeat filtering for double-tap

**Decision:** For prefixes where `prefix == then` (double-tap), the state machine requires seeing a KeyRelease between the two KeyPress events. Without this, holding RCtrl generates repeated KeyPress events that look like rapid double-taps.

**Implementation:** Track `prefix_released: bool` in state. Set true on KeyRelease of the prefix key. Only count a second KeyPress as the "then" tap if `prefix_released` is true.

### 6. Fail-safe on invalid config

**Decision:** At startup and on each save, validate the hotkey config. If invalid (missing actions, conflicting entries, unknown prefix), replace with defaults and log a warning. Never leave the app without working hotkeys.

**What counts as invalid:**
- A prefix not in the whitelist
- Two actions with identical (prefix, then) pair
- Missing action entry
- `window_ms` outside [200, 1000]

### 7. Settings UI: capture widget

**Decision:** Each action gets a two-part capture widget:

```
 Translate   [ Ctrl+C      ▾ ] → [ C          🎯 ]
 Chat        [ Ctrl+C      ▾ ] → [ Space      🎯 ]
 Screenshot  [ RCtrl       ▾ ] → [ RCtrl      🎯 ]
                                   ↑ click to capture
```

- Prefix: dropdown from whitelist (not free text)
- Then: focus the field, press the key → recorded via `keydown` event (`event.code` distinguishes L/R modifiers)
- Inline badge: "⚠ Ctrl+S = Save in most apps" when prefix+then has a known side effect
- Conflict badge: "⚠ Same as Chat" when two actions share a combo

**Why dropdown for prefix:** Prevents typos, enforces whitelist, avoids the need to capture modifier-only keys (which is awkward in webview — releasing Ctrl fires `keyup`, but there's no clean `keypress` for a modifier alone).

### 8. Config schema

```json
{
  "hotkeys": {
    "translate":  { "prefix": "Ctrl+C", "then": "C",     "window_ms": 600 },
    "chat":       { "prefix": "Ctrl+C", "then": "Space", "window_ms": 600 },
    "screenshot": { "prefix": "RCtrl",  "then": "RCtrl", "window_ms": 400 }
  }
}
```

Stored in `~/.quicktranslator_config.json` alongside existing fields. Missing `hotkeys` key → defaults above. Each action's default matches current hardcoded behavior (screenshot default is new, pre-wired for change B).

### 9. `is_modifier_or_combo` must become dynamic

**Decision:** Currently `is_modifier_or_combo` hardcodes `Key::KeyC` so that Ctrl+C doesn't reset the armed state. With configurable hotkeys, the "don't reset" set must include whatever keys appear as prefix components or `then` keys of all configured hotkeys. Rebuild this set on each config swap.

## Open Questions

- **OQ1:** Does `arc-swap` compile cleanly on the MSVC target with the existing Rust edition? Need to verify — fallback is `parking_lot::RwLock` which has similar read performance.
- **OQ2:** Can WebView2 `keydown` reliably distinguish `ControlRight` via `event.location === 2`? Need to test on real Windows. Fallback: label RCtrl entries as "Right Ctrl (detected by location)" and show a test-press confirmation.
