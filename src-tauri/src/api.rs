//! Streaming translation & chat — parity with api.py translate_stream /
//! chat_with_context_stream.
//!
//! POSTs to <base_url>/chat/completions with stream:true, parses SSE, and emits
//! Tauri events to the target window:
//!   "translate://chunk" / "chat://chunk" — payload: String delta
//!   "translate://done"  / "chat://done"  — payload: null / empty string

use reqwest::header::{AUTHORIZATION, CONTENT_TYPE};
use serde::Deserialize;
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
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

// ── Stream cancellation ───────────────────────────────────────────────────────

/// Cancellation flags for in-flight streams, one per popup window.
///
/// The flag is owned by the *window*, not by the stream: `claim` hands it out
/// when a window is built and the window's close handler is the only thing that
/// sets it. Streams merely read whichever flag currently belongs to their target.
///
/// This is what makes label reuse safe. Popup labels are fixed constants, so a
/// second hotkey press closes and rebuilds the same label. Had cancellation been
/// keyed only by label, the old window's late `Destroyed` event could cancel the
/// stream that had already started for the *new* window. Instead the old handler
/// holds its own now-orphaned flag, which no stream reads.
#[derive(Default)]
pub struct StreamRegistry(Mutex<HashMap<String, Arc<AtomicBool>>>);

impl StreamRegistry {
    pub fn new() -> Self {
        Self::default()
    }

    /// Issue a fresh flag for a newly built window, cancelling the stream that
    /// belonged to the window it replaces.
    pub fn claim(&self, label: &str) -> Arc<AtomicBool> {
        let flag = Arc::new(AtomicBool::new(false));
        if let Some(prev) = self.lock().insert(label.to_string(), flag.clone()) {
            prev.store(true, Ordering::Relaxed);
        }
        flag
    }

    /// The flag a stream targeting `label` must watch.
    pub fn current(&self, label: &str) -> Arc<AtomicBool> {
        self.lock()
            .get(label)
            .cloned()
            // No live window claimed this label, so there is nothing to cancel.
            .unwrap_or_else(|| Arc::new(AtomicBool::new(false)))
    }

    /// A transient panic elsewhere must not permanently break cancellation.
    fn lock(&self) -> std::sync::MutexGuard<'_, HashMap<String, Arc<AtomicBool>>> {
        self.0.lock().unwrap_or_else(|e| e.into_inner())
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
/// `content` is serde_json::Value to support both plain strings and multimodal
/// content arrays (text + image_url) for vision.
#[derive(Debug, Clone, Serialize, serde::Deserialize)]
pub struct ChatMessage {
    pub role: String,
    pub content: serde_json::Value,
}

// ── Base URL helper ─────────────────────────────────────────────────────────

fn resolve_base_url(cfg: &Config) -> String {
    if cfg.base_url.trim().is_empty() {
        "https://api.openai.com/v1".to_string()
    } else {
        cfg.base_url.trim_end_matches('/').to_string()
    }
}

// ── Error reporting ───────────────────────────────────────────────────────────

/// A failed request, split so the popup can show one readable line and keep the
/// raw server response behind a disclosure instead of filling itself with JSON.
#[derive(Serialize, Clone)]
struct StreamError {
    summary: String,
    detail: String,
    retryable: bool,
}

/// Longest raw detail worth keeping — matches the bound `test_connection` uses.
const DETAIL_MAX: usize = 200;

fn truncate_detail(s: &str) -> String {
    s.chars().take(DETAIL_MAX).collect()
}

fn classify_status(status: reqwest::StatusCode, body: &str) -> StreamError {
    let summary = match status.as_u16() {
        401 | 403 => "Authentication failed — check your API key in Settings.",
        429 => "Rate limited — try again in a moment.",
        404 => "Endpoint not found — check the Base URL in Settings.",
        500..=599 => "The server reported an error.",
        _ => "The request was rejected.",
    };
    StreamError {
        summary: format!("{summary} (HTTP {})", status.as_u16()),
        detail: truncate_detail(body),
        // Auth and a wrong URL will fail identically until the user fixes
        // Settings, so offering a retry there would just waste a click.
        retryable: !matches!(status.as_u16(), 401 | 403 | 404),
    }
}

fn classify_transport(e: &reqwest::Error) -> StreamError {
    let summary = if e.is_connect() {
        "Could not reach the endpoint — check your connection and Base URL."
    } else if e.is_timeout() {
        "The request timed out."
    } else {
        "The request failed."
    };
    StreamError {
        summary: summary.to_string(),
        detail: truncate_detail(&e.to_string()),
        retryable: true,
    }
}

// ── Shared streaming core ─────────────────────────────────────────────────────

/// POST a chat/completions request and stream deltas to `window`.
///
/// `flow` is the event namespace (`"translate"` or `"chat"`): deltas go to
/// `<flow>://chunk`, failures to `<flow>://error`, and `<flow>://done` always
/// fires last so the popup never hangs. Errors ride their own event rather than
/// the chunk event so they can't be mistaken for model output.
async fn stream_completion(
    body: serde_json::Value,
    cfg: &Config,
    client: &reqwest::Client,
    window: &WebviewWindow,
    flow: &str,
    cancelled: &AtomicBool,
) {
    let chunk_event = format!("{flow}://chunk");
    let done_event = format!("{flow}://done");
    let error_event = format!("{flow}://error");
    let url = format!("{}/chat/completions", resolve_base_url(cfg));

    let response = client
        .post(&url)
        .header(AUTHORIZATION, format!("Bearer {}", cfg.api_key))
        .header(CONTENT_TYPE, "application/json")
        .json(&body)
        .send()
        .await;

    if cancelled.load(Ordering::Relaxed) {
        return;
    }

    let resp = match response {
        Ok(r) => {
            if !r.status().is_success() {
                let status = r.status();
                let body_text = r.text().await.unwrap_or_default();
                let _ = window.emit(&error_event, classify_status(status, &body_text));
                let _ = window.emit(&done_event, "");
                return;
            }
            r
        }
        Err(e) => {
            let _ = window.emit(&error_event, classify_transport(&e));
            let _ = window.emit(&done_event, "");
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
                let _ = window.emit(
                    &error_event,
                    StreamError {
                        summary: "The response stalled and timed out.".to_string(),
                        detail: format!(
                            "No data received for {}s.",
                            STREAM_IDLE_TIMEOUT.as_secs()
                        ),
                        retryable: true,
                    },
                );
                break;
            }
        };

        // Checked between reads rather than mid-parse, so a partially buffered
        // SSE line is never treated as complete. Returning drops the stream,
        // which closes the connection instead of draining the rest of the body.
        if cancelled.load(Ordering::Relaxed) {
            return;
        }

        let chunk_result = match next {
            Some(c) => c,
            None => break, // stream ended
        };

        let bytes = match chunk_result {
            Ok(b) => b,
            Err(e) => {
                let _ = window.emit(&error_event, classify_transport(&e));
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
                    let _ = window.emit(&done_event, "");
                    return;
                }
                // Parse JSON chunk
                if let Ok(chunk) = serde_json::from_str::<SseChunk>(data) {
                    if let Some(choices) = chunk.choices {
                        if let Some(choice) = choices.into_iter().next() {
                            if let Some(delta) = choice.delta.content {
                                if !delta.is_empty() {
                                    let _ = window.emit(&chunk_event, &delta);
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // Stream ended without [DONE]
    let _ = window.emit(&done_event, "");
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
pub async fn translate_stream(
    text: String,
    cfg: Config,
    client: &reqwest::Client,
    window: WebviewWindow,
    registry: &StreamRegistry,
) {
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

    let cancelled = registry.current(window.label());
    stream_completion(body, &cfg, client, &window, "translate", &cancelled).await;
}

// ── Chat function ───────────────────────────────────────────────────────────

/// Run a streaming chat request and emit events to the chat `window`.
///
/// Messages = system prompt (varies on selected text) + history. The frontend
/// owns the history and its last entry IS the question being asked, so appending
/// a question here would send it twice — and, for an image turn, twice with
/// differing content.
pub async fn chat_stream(
    selected_text: String,
    history: Vec<ChatMessage>,
    cfg: Config,
    client: &reqwest::Client,
    window: WebviewWindow,
    registry: &StreamRegistry,
) {
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

    let mut messages: Vec<serde_json::Value> =
        vec![serde_json::json!({"role": "system", "content": system_content})];
    for m in &history {
        messages.push(serde_json::json!({"role": m.role, "content": &m.content}));
    }

    // Detect if any message contains image content → use vision model
    let has_image = history.iter().any(|m| {
        if let serde_json::Value::Array(parts) = &m.content {
            parts.iter().any(|p| p.get("type").and_then(|t| t.as_str()) == Some("image_url"))
        } else {
            false
        }
    });

    let model = if has_image && !cfg.vision_model.trim().is_empty() {
        &cfg.vision_model
    } else {
        &cfg.model
    };

    let mut body = serde_json::json!({
        "model": model,
        "messages": messages,
        "max_completion_tokens": 4096,
        "stream": true
    });

    if is_reasoning_model(model) {
        body["reasoning_effort"] = serde_json::json!("none");
    }

    let cancelled = registry.current(window.label());
    stream_completion(body, &cfg, client, &window, "chat", &cancelled).await;
}
