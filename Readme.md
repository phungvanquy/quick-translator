# Quick Translator

Lightweight desktop translator & AI chat assistant. Highlight any text, press a hotkey, get results instantly. Built with Rust + Tauri 2.x (`src-tauri/` backend, `frontend/` static HTML/CSS/JS; CI in `.github/workflows/build.yml`).

## Features
- **Ctrl+C+C** — translate the selection in a popup near your cursor
- **Ctrl+C+Space** — open a chat window about the selection
- **Custom prompt** — with a `{target_language}` placeholder
- **Markdown rendering** in AI responses
- **System tray** — runs silently; right-click for Settings / Quit
- **Dark + light theme** — follows your OS color-scheme preference

## Setup
Prerequisites: a stable Rust toolchain, the Tauri CLI (`cargo install tauri-cli`), and the [Tauri platform dependencies](https://tauri.app/start/prerequisites/).

```bash
cargo tauri dev --config src-tauri/tauri.conf.json
```

Runs without elevation (no UAC prompt). Because of Windows UIPI, the global hotkey won't fire while an **elevated** window is foreground (Task Manager, admin terminal, regedit) — right-click the app → **Run as administrator** for that session. On first launch, Settings opens so you can enter your API key.

## Settings (tray icon → Settings)

| Field | Example |
|---|---|
| API Key | `sk-...` |
| Base URL | `https://api.openai.com/v1` (default) · `https://openrouter.ai/api/v1` · `http://localhost:11434/v1` (Ollama) |
| Model | `gpt-4o-mini` (default) |
| Target Language | `Vietnamese`, `French`, `Japanese`, … |
| Custom Prompt | `Translate to {target_language}. Reply with ONLY the translation.` |

Saved to `~/.quicktranslator_config.json` and applied immediately — no restart.

## Build

```bash
cargo tauri build --config src-tauri/tauri.conf.json
```

Produces a standalone `.exe` and an NSIS installer under `src-tauri/target/release/`. The GitHub Actions workflow runs the same build on `windows-latest`.
