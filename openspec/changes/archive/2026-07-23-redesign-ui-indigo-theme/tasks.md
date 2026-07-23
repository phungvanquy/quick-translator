## 1. Design tokens & theme foundation

- [x] 1.1 Rewrite `frontend/theme.css` `:root` with the indigo token set (dark defaults): bg/surface/surface-1/surface-2, border, text/subtext/muted, accent/accent-hover/accent-soft/accent-2, success/danger, plus radius (10/8/6px) and shadow tokens.
- [x] 1.2 Add an `@media (prefers-color-scheme: light)` block overriding the same token names with light values (conservative, high-contrast).
- [x] 1.3 Update the base `body`, scrollbar, and any global rules to reference only tokens; remove GitHub-dark-specific literals.
- [x] 1.4 Sanity-check every `frontend/*.css` for stray hard-coded hex values and replace with tokens.

## 2. Shared SVG icon set

- [x] 2.1 Author the icon set as an inline SVG `<symbol>` sprite (close, arrow-right, chat, spinner, volume, copy, refresh; +check) with ~1.5px strokes and `stroke="currentColor"`; paths adapted from MIT Lucide.
- [x] 2.2 Decide sprite delivery (OQ2): resolved — shared `frontend/icons.js` injector, included as the first `<body>` element so it paints before controls.
- [x] 2.3 Add a `.ic` helper class in `theme.css` (size, vertical-align, `fill:none; stroke:currentColor`) + `.ic-spin` keyframes.

## 3. Translate popup

- [x] 3.1 `popup.html`: replaced `✕`, `⟶`, spinner `⠋`, and the Copy glyph with `<use>` SVG icons; sprite included.
- [x] 3.2 `popup.css`: rounded corners + shadow + layered elevation (header/body/footer), looser padding, token-based close/copy buttons and vector spinner.
- [ ] 3.3 Verify streaming, resize, tooltip-on-truncation, Esc/blur close, and copy states (disabled→Copied) still work after markup changes. *(needs a Windows run — deferred to manual QA)*

## 4. Chat popup

- [x] 4.1 `chat.html`: replaced `💬`, close `✕`, and context-clear `✕` with SVG icons; sprite included.
- [x] 4.2 `chat.css`: rounded corners + shadow + elevation; user bubble uses accent-soft tint (assistant neutral surface); indigo input focus ring + send button; typing dots tinted from accent.
- [ ] 4.3 Verify send (Enter / Ctrl+Enter / Shift+Enter newline), IME-confirm-does-not-send, transcript autoscroll, context strip, and close behaviors still work. *(needs a Windows run — deferred to manual QA)*

## 5. Settings window

- [x] 5.1 `settings.css`: dropped the ALL-CAPS letter-spaced `.label` for sentence-case `font-weight:600`; indigo focus ring, primary button, and link colors via tokens; looser spacing; migrated stale `--green/--red/--yellow/--blue` tokens.
- [x] 5.2 `settings.html`: added SVG refresh icon to the reset-prompt link; removed `✓` status glyphs; no emoji remain.
- [ ] 5.3 Verify save / test-connection / reset-to-default / validation states render correctly in both themes. *(needs a Windows run — deferred to manual QA)*

## 6. Window transparency for real rounded corners

- [x] 6.1 In `src-tauri/src/windows.rs`, enabled `.transparent(true)` on the translate and chat `WebviewWindowBuilder`s; Settings left decorated/unchanged.
- [ ] 6.2 On a Windows build, verify shadow + always-on-top + positioning still work (OQ1). If broken, revert to opaque and rely on CSS `border-radius` (fallback); record the decision in CLAUDE.md. *(needs a Windows run — deferred to manual QA)*

## 7. App icon

- [x] 7.1 Authored the brand SVG (`icons/brand.svg`): two-arrows ⇄ glyph, white, on an indigo gradient (`#7C6BFF`→`#6D5AE6`), rounded background.
- [x] 7.2 Added committed generator `icons/generate_icon.py` (Python+Pillow) that rasterizes to `icon.png` (512×512) and multi-size `icon.ico` (16/32/48/64/128/256).
- [x] 7.3 Regenerated `src-tauri/icons/icon.png` + `icon.ico`; bundle config references them and the tray uses `default_window_icon()` (bundle icon).

## 8. Verification & docs

- [ ] 8.1 `cargo build` (and `cargo tauri build` on the Windows target) passes. *(no Rust toolchain in this env — JS syntax-checked with `node --check`; Rust build deferred to CI/Windows)*
- [ ] 8.2 Manually verify both dark and light themes across all three windows; confirm no emoji remain as controls and icons re-tint per theme. *(needs a Windows run — deferred to manual QA; static sweep confirms no emoji controls + all CSS tokens defined)*
- [x] 8.3 Update CLAUDE.md: note the indigo theme + light-mode support, the SVG icon set, the transparency decision (OQ1 pending), and add light-theme checks to the pre-release manual QA checklist.
