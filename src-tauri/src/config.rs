//! Configuration management — parity with config.py
//! Persists to ~/.quicktranslator_config.json

use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;
use std::sync::Mutex;

// ── Defaults (must match config.py exactly) ───────────────────────────────────

fn default_api_key() -> String {
    String::new()
}

fn default_base_url() -> String {
    "https://api.openai.com/v1".to_string()
}

fn default_target_language() -> String {
    "Vietnamese".to_string()
}

fn default_model() -> String {
    "gpt-4o-mini".to_string()
}

fn default_custom_prompt() -> String {
    "You are a translator. Translate the user's text to {target_language}. \
     Reply with ONLY the translation — no explanations, no notes."
        .to_string()
}

// ── Config struct ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    #[serde(default = "default_api_key")]
    pub api_key: String,

    #[serde(default = "default_base_url")]
    pub base_url: String,

    #[serde(default = "default_target_language")]
    pub target_language: String,

    #[serde(default = "default_model")]
    pub model: String,

    #[serde(default = "default_custom_prompt")]
    pub custom_prompt: String,
}

impl Default for Config {
    fn default() -> Self {
        Config {
            api_key: default_api_key(),
            base_url: default_base_url(),
            target_language: default_target_language(),
            model: default_model(),
            custom_prompt: default_custom_prompt(),
        }
    }
}

// ── File path ─────────────────────────────────────────────────────────────────

pub fn config_path() -> PathBuf {
    dirs::home_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join(".quicktranslator_config.json")
}

// ── Load (mirrors load_config in config.py) ───────────────────────────────────
/// Load config from disk.
/// - If file exists and parses: serde fills missing keys with defaults.
/// - If file is absent: write defaults to disk, return defaults.
/// - If file is malformed: return defaults WITHOUT overwriting.
pub fn load() -> Config {
    let path = config_path();

    if path.exists() {
        match fs::read_to_string(&path) {
            Ok(text) => {
                match serde_json::from_str::<Config>(&text) {
                    Ok(cfg) => return cfg,
                    Err(_) => {
                        // Malformed — return defaults, do NOT overwrite
                        return Config::default();
                    }
                }
            }
            Err(_) => return Config::default(),
        }
    }

    // File absent — write defaults then return them
    let defaults = Config::default();
    let _ = save_to_disk(&defaults); // best-effort; ignore error
    defaults
}

// ── Save (mirrors save_config in config.py) ───────────────────────────────────
/// Write config as pretty-printed, UTF-8, non-ASCII-escaped JSON.
/// serde_json does not \u-escape non-ASCII by default, satisfying ensure_ascii=False.
pub fn save_to_disk(cfg: &Config) -> Result<(), String> {
    let path = config_path();
    let json = serde_json::to_string_pretty(cfg)
        .map_err(|e| format!("serialise error: {e}"))?;
    fs::write(&path, json.as_bytes()).map_err(|e| format!("write error: {e}"))
}

// ── Tauri-managed state ───────────────────────────────────────────────────────

/// Thread-safe config state stored in Tauri's managed state.
pub struct ConfigState(pub Mutex<Config>);

impl ConfigState {
    pub fn new(cfg: Config) -> Self {
        ConfigState(Mutex::new(cfg))
    }

    pub fn get(&self) -> Config {
        self.0.lock().unwrap().clone()
    }

    pub fn update(&self, partial: ConfigUpdate) -> Result<(), String> {
        let mut cfg = self.0.lock().unwrap();
        if let Some(v) = partial.api_key {
            cfg.api_key = v;
        }
        if let Some(v) = partial.base_url {
            cfg.base_url = v;
        }
        if let Some(v) = partial.target_language {
            cfg.target_language = v;
        }
        if let Some(v) = partial.model {
            cfg.model = v;
        }
        if let Some(v) = partial.custom_prompt {
            cfg.custom_prompt = v;
        }
        save_to_disk(&cfg)
    }
}

/// Partial update payload from the Settings UI — all fields optional.
#[derive(Debug, Deserialize)]
pub struct ConfigUpdate {
    pub api_key: Option<String>,
    pub base_url: Option<String>,
    pub target_language: Option<String>,
    pub model: Option<String>,
    pub custom_prompt: Option<String>,
}
