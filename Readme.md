# Quick Translator

Lightweight desktop translator & AI chat assistant. Highlight any text, press a hotkey, get results instantly.

Built with Rust + Tauri 2.x. Source under `src-tauri/` (backend) and `frontend/` (static HTML/CSS/JS), built by CI in `.github/workflows/build.yml`.

## Features

- **Ctrl+C+C** — Translate selected text in a popup near your cursor
- **Ctrl+C+Space** — Open a chat window to ask questions about selected text
- **Custom translation prompt** — Fully customizable system prompt with `{target_language}` placeholder
- **Markdown rendering** — AI responses render bold, italic, code blocks, headings, and lists
- **System tray** — Runs silently; right-click the tray icon for Settings or Quit
- **Dark theme** — GitHub-dark palette with hover effects throughout

## Setup

Prerequisites: a stable Rust toolchain and the Tauri CLI (`cargo install tauri-cli`), plus the [Tauri platform dependencies](https://tauri.app/start/prerequisites/).

```bash
cargo tauri dev --config src-tauri/tauri.conf.json
```

> **Note:** On Windows, run as Administrator — global hotkeys require elevated privileges (the app manifest requests elevation for packaged builds).

On first launch, the Settings window opens automatically so you can enter your API key.

## Settings (right-click tray icon → Settings)

| Field | Example |
|---|---|
| API Key | `sk-...` |
| Base URL | `https://api.openai.com/v1` (default) |
| | `https://openrouter.ai/api/v1` |
| | `http://localhost:11434/v1` (Ollama) |
| Model | `gpt-4o-mini` (default) |
| Target Language | `Vietnamese`, `French`, `Japanese`, etc. |
| Custom Prompt | `Translate to {target_language}. Reply with ONLY the translation.` |

Settings are saved to `~/.quicktranslator_config.json` and applied immediately — no restart needed.

## Build

```bash
cargo tauri build --config src-tauri/tauri.conf.json
```

This produces a standalone `.exe` (`src-tauri/target/release/quick-translator.exe`) and an NSIS installer (`src-tauri/target/release/bundle/nsis/`). The GitHub Actions workflow (`.github/workflows/build.yml`) runs the same build on `windows-latest` and uploads both artifacts.

## How it works

- Runs silently in the system tray
- **Ctrl+C+C**: Listens for two Ctrl+C presses within 500ms → reads clipboard → sends to OpenAI-compatible API → shows translation popup with a loading indicator
- **Ctrl+C+Space**: Same trigger but opens a chat window for follow-up questions about the selected text
- Translation text is selectable; press **Ctrl+C** to copy selection or click **Copy** for the full result
- Press **Escape** or click outside to dismiss
