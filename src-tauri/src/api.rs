//! Streaming translation — parity with api.py translate_stream
//!
//! POSTs to <base_url>/chat/completions with stream:true, parses SSE,
//! and emits Tauri events to the popup window:
//!   "translate://chunk"  — payload: String delta
//!   "translate://done"   — payload: null / empty string

use reqwest::header::{AUTHORIZATION, CONTENT_TYPE};
use serde::Deserialize;
use std::time::Duration;
use tauri::{Emitter, WebviewWindow};

use crate::config::Config;

// Connection must establish within this window, or we surface an error instead
// of spinning forever. The overall request is NOT capped (streaming responses
// are long-lived); instead each stream read is bounded by STREAM_IDLE_TIMEOUT.
const CONNECT_TIMEOUT: Duration = Duration::from_secs(15);
// Max gap between streamed chunks before we treat the connection as hung.
const STREAM_IDLE_TIMEOUT: Duration = Duration::from_secs(60);

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

// ── Main translation function ─────────────────────────────────────────────────

/// Run streaming translation and emit events to `window`.
///
/// Called from the async runtime (tokio), spawned by handle_translate_trigger.
pub async fn translate_stream(text: String, cfg: Config, window: WebviewWindow) {
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

    // Build request body
    let base_url = if cfg.base_url.trim().is_empty() {
        "https://api.openai.com/v1".to_string()
    } else {
        cfg.base_url.trim_end_matches('/').to_string()
    };
    let url = format!("{}/chat/completions", base_url);

    let body = serde_json::json!({
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user",   "content": text}
        ],
        "max_completion_tokens": 1000,
        "stream": true
    });

    // Send request
    let client = match reqwest::Client::builder()
        .use_rustls_tls()
        .connect_timeout(CONNECT_TIMEOUT)
        .build()
    {
        Ok(c) => c,
        Err(e) => {
            let _ = window.emit("translate://chunk", format!("⚠ Error: {e}"));
            let _ = window.emit("translate://done", "");
            return;
        }
    };

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
                    "translate://chunk",
                    format!("⚠ Error: HTTP {status} — {body_text}"),
                );
                let _ = window.emit("translate://done", "");
                return;
            }
            r
        }
        Err(e) => {
            let _ = window.emit("translate://chunk", format!("⚠ Error: {e}"));
            let _ = window.emit("translate://done", "");
            return;
        }
    };

    // Stream body — buffer partial lines, parse SSE
    use futures_util::StreamExt;
    let mut stream = resp.bytes_stream();
    let mut line_buf = String::new();

    while let Some(chunk_result) =
        match tokio::time::timeout(STREAM_IDLE_TIMEOUT, stream.next()).await {
            Ok(next) => next,
            Err(_) => {
                let _ = window.emit(
                    "translate://chunk",
                    "⚠ Error: response timed out (no data for 60s)",
                );
                break;
            }
        }
    {
        let bytes = match chunk_result {
            Ok(b) => b,
            Err(e) => {
                let _ = window.emit("translate://chunk", format!("⚠ Error: {e}"));
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
                    let _ = window.emit("translate://done", "");
                    return;
                }
                // Parse JSON chunk
                if let Ok(chunk) = serde_json::from_str::<SseChunk>(data) {
                    if let Some(choices) = chunk.choices {
                        if let Some(choice) = choices.into_iter().next() {
                            if let Some(delta) = choice.delta.content {
                                if !delta.is_empty() {
                                    let _ = window.emit("translate://chunk", &delta);
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // Stream ended without [DONE]
    let _ = window.emit("translate://done", "");
}
