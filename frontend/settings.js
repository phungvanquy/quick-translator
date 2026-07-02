// settings.js — Settings window logic
// Loads config via Tauri command, saves via update_config command

const { invoke } = window.__TAURI__.core;

// ── DOM refs ──────────────────────────────────────────────────────────────────
const apiKeyInput     = document.getElementById('api-key');
const baseUrlInput    = document.getElementById('base-url');
const modelInput      = document.getElementById('model');
const targetLangInput = document.getElementById('target-lang');
const saveBtn         = document.getElementById('save-btn');
const saveStatus      = document.getElementById('save-status');
const form            = document.getElementById('settings-form');

// ── Load current config ───────────────────────────────────────────────────────
async function loadConfig() {
  try {
    const cfg = await invoke('get_config');
    apiKeyInput.value     = cfg.api_key          || '';
    baseUrlInput.value    = cfg.base_url         || '';
    modelInput.value      = cfg.model            || '';
    targetLangInput.value = cfg.target_language  || '';
  } catch (e) {
    showStatus('Failed to load config: ' + e, true);
  }
}

// ── Save config ───────────────────────────────────────────────────────────────
async function saveConfig(e) {
  e.preventDefault();

  const update = {
    api_key:         apiKeyInput.value.trim(),
    base_url:        baseUrlInput.value.trim(),
    model:           modelInput.value.trim(),
    target_language: targetLangInput.value.trim(),
  };

  try {
    await invoke('update_config', { update });
    showStatus('Saved ✓', false);
  } catch (err) {
    showStatus('Error: ' + err, true);
  }
}

// ── Status message ────────────────────────────────────────────────────────────
let statusTimer = null;

function showStatus(msg, isError) {
  saveStatus.textContent = msg;
  saveStatus.className = 'save-status' + (isError ? ' error' : '');
  if (statusTimer) clearTimeout(statusTimer);
  statusTimer = setTimeout(() => {
    saveStatus.textContent = '';
    saveStatus.className = 'save-status';
  }, 3000);
}

// ── Init ──────────────────────────────────────────────────────────────────────
form.addEventListener('submit', saveConfig);
loadConfig().catch(console.error);
