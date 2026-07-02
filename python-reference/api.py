"""OpenAI API helpers for Quick Translator."""

from openai import OpenAI

from config import get_config, DEFAULT_PROMPT

_client: OpenAI | None = None
_client_key: tuple | None = None  # (api_key, base_url) used to create _client


def get_client(cfg: dict) -> OpenAI:
    """Return a reusable OpenAI client, recreated only when credentials change."""
    global _client, _client_key
    key = (cfg["api_key"], cfg["base_url"] or "https://api.openai.com/v1")
    if _client is None or _client_key != key:
        if _client is not None:
            try:
                _client.close()
            except Exception:
                pass
        _client = OpenAI(api_key=key[0], base_url=key[1])
        _client_key = key
    return _client


def close_client() -> None:
    """Close the OpenAI client if it exists. Used during graceful shutdown."""
    global _client, _client_key
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
        _client = None
        _client_key = None


def translate_stream(text: str):
    """Yield translation chunks. Yields strings; first may be an error."""
    cfg = get_config()
    if not cfg["api_key"]:
        yield "⚠ No API key set.\nRight-click the tray icon → Settings."
        return
    try:
        prompt = cfg.get("custom_prompt", DEFAULT_PROMPT)
        try:
            system_content = prompt.format(target_language=cfg["target_language"])
        except (KeyError, ValueError):
            system_content = prompt
        stream = get_client(cfg).chat.completions.create(
            model=cfg["model"],
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": text},
            ],
            max_completion_tokens=1000,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta
    except Exception as e:
        yield f"⚠ Error: {e}"


def chat_with_context_stream(selected_text: str, user_question: str, history: list):
    """Yield chat response chunks as strings."""
    cfg = get_config()
    if not cfg["api_key"]:
        yield "⚠ No API key set.\nRight-click the tray icon → Settings."
        return
    try:
        if selected_text:
            system = (
                "You are a helpful assistant. The user has selected the following text:\n\n"
                f"---\n{selected_text}\n---\n\n"
                "Answer the user's questions about it concisely and clearly. "
                "You may use Markdown formatting (bold, italic, code blocks, lists) "
                "where it helps readability."
            )
        else:
            system = (
                "You are a helpful assistant. Answer concisely and clearly. "
                "You may use Markdown formatting (bold, italic, code blocks, lists) "
                "where it helps readability."
            )
        messages = [{"role": "system", "content": system}] + history + [
            {"role": "user", "content": user_question}
        ]
        stream = get_client(cfg).chat.completions.create(
            model=cfg["model"],
            messages=messages,
            max_completion_tokens=1000,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta
    except Exception as e:
        yield f"⚠ Error: {e}"
