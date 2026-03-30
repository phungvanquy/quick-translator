# Quick Translator

Lightweight desktop translator & AI chat assistant. Highlight any text, press a hotkey, get results instantly.

## Features

- **Ctrl+C+C** — Translate selected text in a popup near your cursor
- **Ctrl+C+Space** — Open a chat window to ask questions about selected text
- **Custom translation prompt** — Fully customizable system prompt with `{target_language}` placeholder
- **Markdown rendering** — AI responses render bold, italic, code blocks, headings, and lists
- **System tray** — Runs silently; right-click the tray icon for Settings or Quit
- **Dark theme** — Catppuccin Mocha palette with hover effects throughout

## Setup

```bash
pip install -r requirements.txt
python main.py
```

> **Note:** On Windows, run as Administrator — the `keyboard` library requires elevated privileges for global hotkeys.

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

## Build as .exe

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --uac-admin --name QuickTranslator --hidden-import pystray._win32 --hidden-import mistune --add-data "constants.py;." --add-data "chat_popup.py;." main.py
```

The `.exe` will be in the `dist/` folder.

### Windows Installer

An Inno Setup script (`installer.iss`) is included to build a proper Windows installer with:
- Start Menu & Desktop shortcuts
- Optional auto-start with Windows
- Admin elevation (required for global hotkeys)
- Uninstaller

The GitHub Actions workflow builds both the standalone `.exe` and the installer automatically on push.

## How it works

- Runs silently in the system tray
- **Ctrl+C+C**: Listens for two Ctrl+C presses within 500ms → reads clipboard → sends to OpenAI-compatible API → shows translation popup with a loading indicator
- **Ctrl+C+Space**: Same trigger but opens a chat window for follow-up questions about the selected text
- Translation text is selectable; press **Ctrl+C** to copy selection or click **Copy** for the full result
- Press **Escape** or click outside to dismiss
