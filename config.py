"""Configuration management for Quick Translator."""

import json
import os
import threading

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".quicktranslator_config.json")
DEFAULT_PROMPT = (
    "You are a translator. Translate the user's text to {target_language}. "
    "Reply with ONLY the translation — no explanations, no notes."
)
DEFAULT_CONFIG = {
    "api_key": "",
    "base_url": "https://api.openai.com/v1",
    "target_language": "Vietnamese",
    "model": "gpt-4o-mini",
    "custom_prompt": DEFAULT_PROMPT,
}

_config_lock = threading.Lock()
_config: dict = {}


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except (json.JSONDecodeError, ValueError, TypeError):
            pass  # fall through to defaults
    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG.copy()


def save_config(cfg: dict) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def get_config() -> dict:
    with _config_lock:
        return dict(_config)


def update_config(partial: dict) -> None:
    with _config_lock:
        _config.update(partial)
        save_config(_config)


_config = load_config()
