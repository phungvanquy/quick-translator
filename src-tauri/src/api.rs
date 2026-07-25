//! Streaming translation & chat — parity with api.py translate_stream /
//! chat_with_context_stream.
//!
//! POSTs to <base_url>/chat/completions with stream:true, parses SSE, and emits
//! Tauri events to the target window:
//!   "translate://chunk" / "chat://chunk" — payload: String delta
//!   "translate://done"  / "chat://done"  — payload: null / empty string

use reqwest::header::{AUTHORIZATION, CONTENT_TYPE};
use serde::Deserialize;
use std::time::Duration;
use tauri::{Emitter, WebviewWindow};

use serde::Serialize;

use crate::config::Config;

const CONNECT_TIMEOUT: Duration = Duration::from_secs(15);
const STREAM_IDLE_TIMEOUT: Duration = Duration::from_secs(60);

/// App-wide shared HTTP client. Built once at startup, reuses connections and TLS sessions.
pub struct HttpClient(pub reqwest::Client);

impl HttpClient {
    pub fn new() -> Self {
        let client = reqwest::Client::builder()
            .use_rustls_tls()
            .connect_timeout(CONNECT_TIMEOUT)
            .build()
            .expect("failed to build reqwest client");
        HttpClient(client)
    }
}

// ── Model detection ──────────────────────────────────────────────────────────

fn is_reasoning_model(model: &str) -> bool {
    let m = model.to_ascii_lowercase();
    m.starts_with("gpt-5") || m.starts_with("o1-") || m.starts_with("o3-")
}

// ── SSE parsing helpers ───────────────────────────────────────────────────────

/// Minimal deserialisation of one SSE data payload from chat/completions.
#[derive(Deserialize, Debug)]
struct SseDelta {
    content: Option<String>,
}

#[derive(Deserialize, Debug)]
struct SseChoice {
    delta: SseDelta,
}

#[derive(Deserialize, Debug)]
struct SseChunk {
    choices: Option<Vec<SseChoice>>,
}

// ── Chat message (frontend ↔ backend) ─────────────────────────────────────────

/// One conversation turn passed from the chat frontend and forwarded to the API.
#[derive(Debug, Clone, Serialize, serde::Deserialize)]
pub struct ChatMessage {
    pub role: String,
    pub content: String,
}

// ── Base URL helper ─────────────────────────────────────────────────────────

fn resolve_base_url(cfg: &Config) -> String {
    if cfg.base_url.trim().is_empty() {
        "https://api.openai.com/v1".to_string()
    } else {
        cfg.base_url.trim_end_matches('/').to_string()
    }
}

// ── Shared streaming core ─────────────────────────────────────────────────────

/// POST a chat/completions request and stream deltas to `window` via the given
/// event names. `chunk_event` receives each content delta (String); `done_event`
/// fires once when the stream ends or errors. Errors are surfaced as a chunk on
/// `chunk_event` followed by `done_event`, so the popup never hangs.
async fn stream_completion(
    body: serde_json::Value,
    cfg: &Config,
    client: &reqwest::Client,
    window: &WebviewWindow,
    chunk_event: &str,
    done_event: &str,
) {
    let url = format!("{}/chat/completions", resolve_base_url(cfg));

    let response = client
        .post(&url)
        .header(AUTHORIZATION, format!("Bearer {}", cfg.api_key))
        .header(CONTENT_TYPE, "application/json")
        .json(&body)
        .send()
        .await;

    let resp = match response {
        Ok(r) => {
            if !r.status().is_success() {
                let status = r.status();
                let body_text = r.text().await.unwrap_or_default();
                let _ = window.emit(
                    chunk_event,
                    format!("⚠ Error: HTTP {status} — {body_text}"),
                );
                let _ = window.emit(done_event, "");
                return;
            }
            r
        }
        Err(e) => {
            let _ = window.emit(chunk_event, format!("⚠ Error: {e}"));
            let _ = window.emit(done_event, "");
            return;
        }
    };

    // Stream body — buffer partial lines, parse SSE
    use futures_util::StreamExt;
    let mut stream = resp.bytes_stream();
    let mut line_buf = String::new();

    loop {
        // Bound each read: if no data arrives within the idle window, treat the
        // connection as hung and surface an error instead of spinning forever.
        let next = match tokio::time::timeout(STREAM_IDLE_TIMEOUT, stream.next()).await {
            Ok(next) => next,
            Err(_) => {
                let _ = window.emit(chunk_event, "⚠ Error: response timed out (no data for 60s)");
                break;
            }
        };

        let chunk_result = match next {
            Some(c) => c,
            None => break, // stream ended
        };

        let bytes = match chunk_result {
            Ok(b) => b,
            Err(e) => {
                let _ = window.emit(chunk_event, format!("⚠ Error: {e}"));
                break;
            }
        };

        let text_piece = match std::str::from_utf8(&bytes) {
            Ok(s) => s.to_string(),
            Err(_) => String::from_utf8_lossy(&bytes).to_string(),
        };

        line_buf.push_str(&text_piece);

        // Process complete lines
        while let Some(newline_pos) = line_buf.find('\n') {
            let line: String = line_buf.drain(..=newline_pos).collect();
            let line = line.trim_end_matches('\n').trim_end_matches('\r');

            if line.is_empty() {
                continue; // blank / keep-alive line
            }

            if let Some(data) = line.strip_prefix("data: ") {
                let data = data.trim();
                if data == "[DONE]" {
                    let _ = window.emit(done_event, "");
                    return;
                }
                // Parse JSON chunk
                if let Ok(chunk) = serde_json::from_str::<SseChunk>(data) {
                    if let Some(choices) = chunk.choices {
                        if let Some(choice) = choices.into_iter().next() {
                            if let Some(delta) = choice.delta.content {
                                if !delta.is_empty() {
                                    let _ = window.emit(chunk_event, &delta);
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // Stream ended without [DONE]
    let _ = window.emit(done_event, "");
}

// ── Connection test ───────────────────────────────────────────────────────────

// A test probe is a short-lived, non-streaming request, so unlike the streaming
// path it is safe to bound the WHOLE request with a total timeout.
const TEST_TOTAL_TIMEOUT: Duration = Duration::from_secs(15);

pub async fn test_connection(client: &reqwest::Client, base_url: String, api_key: String, model: String) -> Result<String, String> {
    if api_key.trim().is_empty() {
        return Err("No API key set.".to_string());
    }

    let base = if base_url.trim().is_empty() {
        "https://api.openai.com/v1".to_string()
    } else {
        base_url.trim_end_matches('/').to_string()
    };
    let url = format!("{base}/chat/completions");

    let body = serde_json::json!({
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_completion_tokens": 50,
        "stream": false
    });

    let resp = client
        .post(&url)
        .header(AUTHORIZATION, format!("Bearer {api_key}"))
        .header(CONTENT_TYPE, "application/json")
        .timeout(TEST_TOTAL_TIMEOUT)
        .json(&body)
        .send()
        .await
        .map_err(|e| format!("connection error: {e}"))?;

    let status = resp.status();
    if status.is_success() {
        Ok(format!("OK ({status})"))
    } else {
        let body_text = resp.text().await.unwrap_or_default();
        let snippet: String = body_text.chars().take(200).collect();
        Err(format!("HTTP {status} — {snippet}"))
    }
}

// ── Main translation function ─────────────────────────────────────────────────

/// Run streaming translation and emit events to `window`.
///
/// Called from the async runtime (tokio), spawned by handle_translate_trigger.
pub async fn translate_stream(text: String, cfg: Config, client: &reqwest::Client, window: WebviewWindow) {
    // No API key → emit message and stop, no HTTP call
    if cfg.api_key.trim().is_empty() {
        let msg = "⚠ No API key set.\nRight-click the tray icon → Settings.";
        let _ = window.emit("translate://chunk", msg);
        let _ = window.emit("translate://done", "");
        return;
    }

    // Build system prompt — substitute {target_language}; fallback to raw on failure
    // Mirrors the Python: try prompt.format(target_language=...) except → use raw
    let system_content = if cfg.custom_prompt.contains("{target_language}") {
        cfg.custom_prompt
            .replace("{target_language}", &cfg.target_language)
    } else {
        cfg.custom_prompt.clone()
    };

    let mut body = serde_json::json!({
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user",   "content": text}
        ],
        "max_completion_tokens": 4096,
        "stream": true
    });

    if is_reasoning_model(&cfg.model) {
        body["reasoning_effort"] = serde_json::json!("none");
    }

    stream_completion(body, &cfg, client, &window, "translate://chunk", "translate://done").await;
}

// ── Chat function ───────────────────────────────────────────────────────────

/// Run a streaming chat request and emit events to the chat `window`.
///
/// Messages = system prompt (varies on selected text) + prior history + question,
/// mirroring api.py chat_with_context_stream.
pub async fn chat_stream(
    selected_text: String,
    question: String,
    history: Vec<ChatMessage>,
    cfg: Config,
    client: &reqwest::Client,
    window: WebviewWindow,
) {
    // No API key → emit message and stop, no HTTP call
    if cfg.api_key.trim().is_empty() {
        let msg = "⚠ No API key set.\nRight-click the tray icon → Settings.";
        let _ = window.emit("chat://chunk", msg);
        let _ = window.emit("chat://done", "");
        return;
    }

    let system_content = if selected_text.trim().is_empty() {
        "You are a helpful assistant. Answer concisely and clearly. \
         You may use Markdown formatting (bold, italic, code blocks, lists) \
         where it helps readability."
            .to_string()
    } else {
        format!(
            "You are a helpful assistant. The user has selected the following text:\n\n\
             ---\n{selected_text}\n---\n\n\
             Answer the user's questions about it concisely and clearly. \
             You may use Markdown formatting (bold, italic, code blocks, lists) \
             where it helps readability."
        )
    };

    // messages = [system] + history + [user question]
    let mut messages: Vec<serde_json::Value> =
        vec![serde_json::json!({"role": "system", "content": system_content})];
    for m in &history {
        messages.push(serde_json::json!({"role": m.role, "content": m.content}));
    }
    messages.push(serde_json::json!({"role": "user", "content": question}));

    let body = serde_json::json!({
        "model": cfg.model,
        "messages": messages,
        "max_completion_tokens": 4096,
        "stream": true
    });

    stream_completion(body, &cfg, client, &window, "chat://chunk", "chat://done").await;
}
