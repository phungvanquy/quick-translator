## Context

The app has three frontend surfaces — the translate popup, the chat popup (both frameless `WebviewWindow`s built in `src-tauri/src/windows.rs`), and the decorated Settings window. All share `frontend/theme.css`, which today hard-codes a single GitHub-dark palette (`:root` custom properties). Icons are literal emoji in the HTML; window "borders" and corners are faked with `1px` borders and a body-background trick because the windows are opaque rectangles. There is no JS build step — CSS/HTML/JS are static files served from `frontend/`.

The redesign is purely presentational: no window behavior, no Tauri command, no config-format change. The constraint is to keep the "no JS build step / lean runtime" spirit while modernizing the look. The project dependency rule was just relaxed: safe, pinned, well-maintained deps are allowed when they help (relevant only for icon *generation*, a build-time concern).

## Goals / Non-Goals

**Goals:**
- One shared token system in `theme.css` driving both a dark and a light theme, switched automatically by `prefers-color-scheme`.
- Indigo/violet brand accent replacing GitHub green/blue across buttons, links, focus rings, headings.
- A single consistent inline-SVG icon set replacing every emoji, inheriting `currentColor` so icons re-tint per theme with no duplicate assets.
- Real rounded corners, drop shadow, and layered elevation.
- A new brand app icon (`icon.png` + `icon.ico`).

**Non-Goals:**
- No change to hotkeys, streaming, dismissal, copy, validation, or any backend command.
- No in-app theme toggle/setting — theme follows the OS only (keeps Settings unchanged and scope small).
- No CSS framework, icon font, or frontend build tooling.
- No config-format change.

## Decisions

### D1: Dark + light via `prefers-color-scheme`, one token set
Define all colors as CSS custom properties under `:root` (dark defaults, since the app is dark-first), then override the same properties inside `@media (prefers-color-scheme: light)`. Every component reads only tokens (`var(--accent)`, `var(--surface)`, …), never a literal hex. This is why light theme is "free" per component: one media block flips the values.
- *Alternative considered:* a `data-theme` attribute toggled in JS. Rejected — requires wiring every window + a setting, and the user asked for automatic OS-following, not a manual switch.

### D2: Inline SVG `<symbol>` sprite + `<use>`, `currentColor`
Put the icon set once as a hidden `<svg><symbol id="ic-close">…</symbol>…</svg>` block (or a tiny shared `icons.svg.js` that injects it) at the top of each window body, and reference icons with `<svg class="ic"><use href="#ic-close"/></svg>`. Strokes use `stroke="currentColor"`, so `color:` on the button controls the icon tint and theme-switching is automatic. Paths may be adapted from MIT-licensed Lucide/Feather.
- Icon set: `close` (✕), `arrow-right` (⟶ language), `chat` (💬), `spinner` (⠋ → CSS-animated 3/4 ring), `volume` (🔊 TTS, for the spec'd Stage-3 button), `copy` (Copy label → glyph + text), `refresh` (🔄 reset-prompt).
- *Alternative considered:* an icon font or per-file inline `<svg>` duplicated in each HTML. Rejected — a font is a runtime dep and blurs at small sizes; duplicating raw SVG per file makes stroke-weight drift likely. A shared symbol sprite keeps one source of truth.

### D3: Real rounded corners — `transparent: true` with an opaque-CSS fallback
To round the *actual* window (not just inner content) the frameless popup must be transparent so the rounded CSS surface can sit on a clear background. Enable `.transparent(true)` on the translate + chat `WebviewWindowBuilder`s and draw the rounded surface + shadow in CSS. Settings stays decorated/native (unchanged).
- *Risk & fallback in Risks section.* If transparency misbehaves on the Windows CI/runtime target, fall back to an opaque window with CSS `border-radius` (leaves tiny square corners) — acceptable, ships either way.

### D4: Elevation & spacing conventions
Three layers: window/body = `--bg`; header + assistant bubble + input bar = `--surface`; hover/user-bubble = `--surface-1`/`--accent-soft`. One shadow token for the window; no per-element shadows. Radius tokens: `10px` window, `8px` cards/buttons, `6px` inputs. Bump padding (header `10–12px`, body `14–18px`) and drop the ALL-CAPS `letter-spacing` label style in Settings for `font-weight:600` sentence-case.

### D5: App icon generation (build-time)
Author the ⇄-on-indigo-gradient artwork once as an SVG, then rasterize to `icon.png` (512×512) and a multi-size `icon.ico` (16/32/48/256). Generate with a small script — Python + Pillow, or Rust `image` + `resvg`/`ico` crates — run once by the developer; the generated binaries are committed. No runtime dependency is added to the app.
- *Alternative considered:* hand-export from a design tool. Rejected — a committed generator script is reproducible and reviewable.

## Risks / Trade-offs

- **`transparent: true` breaks shadow / always-on-top / click-through on the Windows target** → Fallback D3: opaque window + CSS radius. Decide during implementation on the real Windows build; record the outcome in CLAUDE.md.
- **Light theme is under-tested** (the app is used dark-first; CI is headless and can't verify either theme visually) → Keep light values conservative (high contrast, same token names), and add light-theme checks to the manual QA checklist rather than claiming visual correctness from CI.
- **SVG symbol sprite must load before first paint** or icons flash empty → inject the sprite synchronously at the top of `<body>` (inline, not fetched), so it's present before controls render.
- **Icon-generation dep (Pillow/image crate)** is new tooling → it's build-time only, pinned, and never shipped in the binary; committed PNG/ICO are the actual artifacts.
- **Accent contrast in light theme** — `#6D5AE6` on white for small text must meet WCAG AA → use it for large text/buttons/borders; keep body text on `--text`, not the accent.

## Open Questions

- **OQ1:** Does `transparent: true` on the two popups keep the drop shadow and always-on-top behavior on the Windows CI/runtime target, or do we take the opaque-CSS fallback? (Resolve on the first Windows build — this is the one thing headless dev can't answer.)
- **OQ2:** Sprite delivery — a static inline `<svg>` block pasted into each HTML, or a shared `icons.js` that injects it? (Lean toward a shared JS injector so the icon set has a single source; confirm it paints before controls.)
- **OQ3:** Icon generator toolchain — Python+Pillow vs. Rust `image`+`resvg`. (Pick whichever is already available in the dev/CI environment.)
