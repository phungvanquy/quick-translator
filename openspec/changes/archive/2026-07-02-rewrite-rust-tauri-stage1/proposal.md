## Why

Quick Translator today is a Python/Tkinter app bundled with a full Python runtime via PyInstaller. The user wants a leaner, more robust distribution: a small self-contained native binary with a modern web-rendered UI, lower idle footprint, and compile-time safety. Rewriting to Rust + Tauri delivers that. Because the app is a Windows GUI that cannot be built or run on the current Linux dev box, correctness for this rewrite rides entirely on CI compilation — so we prove the architecture end-to-end with a **vertical slice (Stage 1)** before porting the remaining features.

## What Changes

- **NEW**: A Rust + Tauri 2.x application implementing a vertical slice of the translate flow with behavior parity to the Python app:
  - System tray icon with a menu (Settings, Quit) and graceful shutdown.
  - Global hotkey **Ctrl+C+C** (double Ctrl+C) via a raw `rdev` keyboard hook, reproducing the exact state machine from `hotkeys.py` (0.6s arm window, 0.4s debounce). The Tauri global-shortcut plugin cannot detect a double-tap of an existing shortcut, so a raw hook is required.
  - Clipboard capture reproducing `get_clipboard_after_copy` (poll ≤10× at 50ms for changed content, fall back to previous) via `arboard`.
  - A frameless, always-on-top translation popup webview positioned near the cursor, showing truncated original text plus streaming translation; Esc + click-outside (blur) to close; draggable header; GitHub-dark palette from `constants.py`.
  - Streaming translation against an OpenAI-compatible `chat/completions` endpoint via `reqwest` + SSE parsing on `tokio` (not `async-openai`, to retain full control over arbitrary `base_url`). Chunks pushed to the webview via Tauri events.
  - A minimal Settings webview to view/edit `api_key`, `base_url`, `model`, `target_language`.
  - Windows admin elevation via the Tauri Windows manifest (`requireAdministrator`), replacing PyInstaller's `--uac-admin`.
- **CHANGED**: `.github/workflows/build.yml` is rewritten to build the Tauri app on `windows-latest` (Rust toolchain + Tauri build), producing a Windows `.exe` and NSIS installer as artifacts (30-day retention). PyInstaller and Inno Setup steps are removed. CI is the sole correctness gate and must actually compile the Rust code.
- **CHANGED**: `CLAUDE.md` gains a note describing the Rust/Tauri Stage-1 architecture and the staged rewrite plan.
- **Config compatibility (non-breaking)**: The Rust app reads/writes the same `~/.quicktranslator_config.json` with an identical schema and defaults, so an existing Python user's config keeps working unchanged.

### Non-Goals (deferred to later stages)

Chat popup, Ctrl+C+Space chat hotkey, markdown rendering, TTS/read-aloud, full-featured settings UI beyond the 4 fields, language auto-detect, and history/log are explicitly **out of scope** for Stage 1.

### Explicitly preserved

All existing Python source files remain untouched in the repo — they are the reference implementation for Stages 2–3. The only existing files this change modifies are `.github/workflows/build.yml` and `CLAUDE.md`. Everything else is new Rust/Tauri files.

## Capabilities

### New Capabilities

- `tray-lifecycle`: System tray icon, menu (Settings, Quit), app startup, and graceful shutdown of the Rust/Tauri app.
- `translate-hotkey`: Global Ctrl+C+C double-tap detection via raw keyboard hook, with the arm-window/debounce state machine and clipboard capture that feed the translate flow.
- `translation-streaming`: OpenAI-compatible streaming translation (request shaping, SSE parsing, error/no-key handling) delivered to the UI.
- `translation-popup`: The frameless, near-cursor, always-on-top popup window that renders original text and the streaming translation with its close/drag behavior.
- `config-store`: Load/save of `~/.quicktranslator_config.json` with schema and defaults compatible with the existing Python config, plus the minimal Settings UI over it.
- `windows-tauri-build`: The GitHub Actions workflow and Tauri bundle configuration that compile the app on `windows-latest` into a `.exe` + installer.

### Modified Capabilities

<!-- None — no existing OpenSpec specs exist in openspec/specs/. This is the first OpenSpec change in the repo. -->

## Impact

- **New files**: A `src-tauri/` directory (Rust crate: `Cargo.toml`, `src/main.rs` + modules for config, hotkey, clipboard, api, tray, windows; `tauri.conf.json`; Windows manifest; icons) and a frontend directory (HTML/CSS/JS for the translate popup and settings). Exact layout defined in design.md.
- **Modified files**: `.github/workflows/build.yml` (PyInstaller → Tauri build), `CLAUDE.md` (architecture note).
- **New dependencies (Rust crates)**: `tauri` 2.x, `rdev`, `arboard`, `reqwest`, `tokio`, `serde`/`serde_json`, `dirs`, plus SSE handling. Frontend has no build-step dependencies (plain HTML/CSS/JS).
- **Runtime/behavior**: New binary must reproduce Python behavior for the translate path; existing config file format is preserved (interoperable with the Python app).
- **CI**: Build now requires a Rust toolchain and Tauri prerequisites on `windows-latest`; artifact names/paths change to the Tauri outputs.
- **Unverifiable locally**: This is a Windows GUI app on a Linux dev box — runtime correctness is validated only by the CI compile + produced artifacts; manual runtime testing is the user's responsibility on Windows.
