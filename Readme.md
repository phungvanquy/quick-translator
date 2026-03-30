# Quick Translator

Highlight any text → press **Ctrl+C+C** → instant translation popup.

## Setup

```bash
pip install -r requirements.txt
python main.py
```

On first launch, the Settings window opens automatically so you can enter your API key.

## Settings (right-click tray icon → Settings)

| Field | Example |
|---|---|
| API Key | `sk-...` |
| Base URL | `https://api.openai.com/v1` (default) |
| | `https://openrouter.ai/api/v1` |
| | `http://localhost:11434/v1` (Ollama) |
| Target Language | `Vietnamese`, `French`, `Japanese`, etc. |

Settings are saved to `config.json` next to `main.py` and applied immediately — no restart needed.

## Build as .exe (no Python required on target machine)

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --name QuickTranslator main.py
```

The `.exe` will be in the `dist/` folder.

## How it works

- Runs silently in the system tray
- Listens for two Ctrl+C presses within 500ms
- Reads clipboard, sends to OpenAI-compatible API
- Shows a small popup near your cursor with the translation
- Click **Copy** to copy the result, or press **Escape** to dismiss
