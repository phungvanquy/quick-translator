// settings.js — Settings window logic
// Loads config via Tauri command, saves via update_config command

const { invoke } = window.__TAURI__.core;

// Default translator prompt — mirrors DEFAULT_PROMPT in config.rs / config.py
const DEFAULT_PROMPT =
  "You are a translator. Translate the user's text to {target_language}. " +
  "Reply with ONLY the translation — no explanations, no notes.";

// ── DOM refs ──────────────────────────────────────────────────────────────────
const apiKeyInput     = document.getElementById('api-key');
const baseUrlInput    = document.getElementById('base-url');
const modelInput      = document.getElementById('model');
const targetLangInput = document.getElementById('target-lang');
const promptInput     = document.getElementById('custom-prompt');
const resetPromptBtn  = document.getElementById('reset-prompt-btn');
const saveBtn         = document.getElementById('save-btn');
const testBtn         = document.getElementById('test-btn');
const saveStatus      = document.getElementById('save-status');
const form            = document.getElementById('settings-form');

// ── base_url validation ─────────────────────────────────────────────────────
// Empty is valid (backend defaults to the OpenAI endpoint). Non-empty must be a
// well-formed http/https URL.
function baseUrlError(value) {
  if (!value) return null;
  let u;
  try {
    u = new URL(value);
  } catch (_e) {
    return 'Base URL is not a valid URL (include http:// or https://).';
  }
  if (u.protocol !== 'http:' && u.protocol !== 'https:') {
    return 'Base URL must start with http:// or https://.';
  }
  return null;
}

// ── Load current config ───────────────────────────────────────────────────────
async function loadConfig() {
  try {
    const cfg = await invoke('get_config');
    apiKeyInput.value     = cfg.api_key          || '';
    baseUrlInput.value    = cfg.base_url         || '';
    modelInput.value      = cfg.model            || '';
    targetLangInput.value = cfg.target_language  || '';
    promptInput.value     = cfg.custom_prompt    || DEFAULT_PROMPT;
  } catch (e) {
    showStatus('Failed to load config: ' + e, true);
  }
}

// ── Save config ───────────────────────────────────────────────────────────────
async function saveConfig(e) {
  e.preventDefault();

  const apiKey  = apiKeyInput.value.trim();
  const baseUrl = baseUrlInput.value.trim();

  // Block a clearly-malformed base_url before saving.
  const urlErr = baseUrlError(baseUrl);
  if (urlErr) {
    showStatus(urlErr, 'error');
    return;
  }

  // Blank prompt falls back to the default template (parity with settings.py)
  const promptVal = promptInput.value.trim() || DEFAULT_PROMPT;

  const update = {
    api_key:         apiKey,
    base_url:        baseUrl,
    model:           modelInput.value.trim(),
    target_language: targetLangInput.value.trim(),
    custom_prompt:   promptVal,
  };

  try {
    await invoke('update_config', { update });
    // Empty API key is allowed but translate/chat won't work — warn, don't block.
    if (!apiKey) {
      showStatus('Saved — but set an API key to enable translation.', 'warn');
    } else {
      showStatus('Saved', false);
    }
  } catch (err) {
    showStatus('Error: ' + err, 'error');
  }
}

// ── Test connection ─────────────────────────────────────────────────────────
async function testConnection() {
  const urlErr = baseUrlError(baseUrlInput.value.trim());
  if (urlErr) {
    showStatus(urlErr, 'error');
    return;
  }
  if (!apiKeyInput.value.trim()) {
    showStatus('Set an API key before testing.', 'warn');
    return;
  }

  testBtn.disabled = true;
  showStatus('Testing…', false);
  try {
    // Uses current form values (not last-saved config) so the user can test first.
    const msg = await invoke('test_connection', {
      baseUrl: baseUrlInput.value.trim(),
      apiKey:  apiKeyInput.value.trim(),
      model:   modelInput.value.trim(),
    });
    showStatus('Connection OK ' + (msg || ''), false);
  } catch (err) {
    showStatus('Test failed: ' + err, 'error');
  } finally {
    testBtn.disabled = false;
  }
}

// ── Status message ────────────────────────────────────────────────────────────
let statusTimer = null;

// `variant` is 'error', 'warn', or falsy (success/neutral). Kept back-compatible
// with the old boolean isError argument (true → 'error').
function showStatus(msg, variant) {
  const cls = variant === true ? 'error' : (variant || '');
  saveStatus.textContent = msg;
  saveStatus.className = 'save-status' + (cls ? ' ' + cls : '');
  if (statusTimer) clearTimeout(statusTimer);
  statusTimer = setTimeout(() => {
    saveStatus.textContent = '';
    saveStatus.className = 'save-status';
  }, 4000);
}

// ── Init ──────────────────────────────────────────────────────────────────────
form.addEventListener('submit', saveConfig);
testBtn.addEventListener('click', testConnection);
resetPromptBtn.addEventListener('click', () => {
  promptInput.value = DEFAULT_PROMPT;
});
loadConfig().catch(console.error);
