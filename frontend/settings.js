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
const visionModelInput = document.getElementById('vision-model');
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

// True when base_url is a well-formed http:// (not https://) URL — the API key
// would be sent unencrypted. Empty / https:// / malformed all return false.
function isInsecureHttp(value) {
  if (!value) return false;
  try {
    return new URL(value).protocol === 'http:';
  } catch (_e) {
    return false;
  }
}

// ── Load current config ───────────────────────────────────────────────────────
async function loadConfig() {
  try {
    const cfg = await invoke('get_config');
    apiKeyInput.value     = cfg.api_key          || '';
    baseUrlInput.value    = cfg.base_url         || '';
    modelInput.value      = cfg.model            || '';
    visionModelInput.value = cfg.vision_model    || '';
    targetLangInput.value = cfg.target_language  || '';
    promptInput.value     = cfg.custom_prompt    || DEFAULT_PROMPT;
    populateHotkeys(cfg.hotkeys);
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

  // Validate hotkeys — block save on conflicts
  const hotkeys = getHotkeyValues();
  const hasConflict = !validateHotkeys();
  const hasMissing = Object.values(hotkeys).some(h => !h.then);
  if (hasConflict) {
    showStatus('Fix hotkey conflicts before saving.', 'error');
    return;
  }
  if (hasMissing) {
    showStatus('All hotkeys must have a trigger key set.', 'error');
    return;
  }

  // Blank prompt falls back to the default template (parity with settings.py)
  const promptVal = promptInput.value.trim() || DEFAULT_PROMPT;

  const update = {
    api_key:         apiKey,
    base_url:        baseUrl,
    model:           modelInput.value.trim(),
    vision_model:    visionModelInput.value.trim(),
    target_language: targetLangInput.value.trim(),
    custom_prompt:   promptVal,
    hotkeys,
  };

  try {
    await invoke('update_config', { update });
    // Non-blocking warnings, in priority order: no key (won't work at all) then
    // insecure http:// (works, but the key travels unencrypted).
    if (!apiKey) {
      showStatus('Saved — but set an API key to enable translation.', 'warn');
    } else if (isInsecureHttp(baseUrl)) {
      showStatus('Saved — warning: http:// sends your API key unencrypted.', 'warn');
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

    const visionModel = visionModelInput.value.trim();
    if (visionModel) {
      const msg2 = await invoke('test_connection', {
        baseUrl: baseUrlInput.value.trim(),
        apiKey:  apiKeyInput.value.trim(),
        model:   visionModel,
      });
      showStatus(`Model OK (${msg}) · Vision OK (${msg2})`, false);
    } else {
      showStatus('Connection OK ' + (msg || ''), false);
    }
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

// ── Hotkeys section ──────────────────────────────────────────────────────────

const HOTKEY_DEFAULTS = {
  translate:  { prefix: 'Ctrl+C', then: 'C',     window_ms: 600 },
  chat:       { prefix: 'Ctrl+C', then: 'Space', window_ms: 600 },
  screenshot: { prefix: 'RCtrl',  then: 'RCtrl', window_ms: 400 },
};

// Known dangerous combos when Ctrl is held (prefix is Ctrl+C/Ctrl+Insert)
const DANGEROUS_CTRL_COMBOS = {
  S: 'Ctrl+S = Save in most apps',
  W: 'Ctrl+W = Close tab/window',
  Q: 'Ctrl+Q = Quit in some apps',
  Z: 'Ctrl+Z = Undo',
  A: 'Ctrl+A = Select all',
  V: 'Ctrl+V = Paste',
  X: 'Ctrl+X = Cut',
  N: 'Ctrl+N = New window',
  T: 'Ctrl+T = New tab',
  F: 'Ctrl+F = Find',
};

const hotkeyRows = document.querySelectorAll('.hotkey-row');
const resetHotkeysBtn = document.getElementById('reset-hotkeys-btn');

// Maps event.code to a display label and a config key name
function codeToKey(code, location) {
  if (code === 'ControlRight') return { label: 'RCtrl', key: 'RCtrl' };
  if (code === 'ControlLeft') return { label: 'LCtrl', key: 'LCtrl' };
  if (code === 'ShiftRight') return { label: 'RShift', key: 'RShift' };
  if (code === 'ShiftLeft') return { label: 'LShift', key: 'LShift' };
  if (code === 'Space') return { label: 'Space', key: 'Space' };
  if (code === 'Insert') return { label: 'Insert', key: 'Insert' };
  if (code.startsWith('Key')) return { label: code.slice(3), key: code.slice(3) };
  if (code.startsWith('Digit')) return { label: code.slice(5), key: code.slice(5) };
  if (code.startsWith('Numpad')) return { label: 'Num' + code.slice(6), key: 'Num' + code.slice(6) };
  if (code.startsWith('F') && /^F\d+$/.test(code)) return { label: code, key: code };
  return { label: code, key: code };
}

// Keys the backend engine can actually map (hotkey.rs map_then_key). RCtrl and
// RShift are in here because a double-tap hotkey uses a modifier as its "then" —
// the default screenshot binding is RCtrl → RCtrl.
const SUPPORTED_THEN = new Set([
  'RCtrl', 'RShift', 'Space', 'Insert',
  ...'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
  ...'0123456789',
  ...Array.from({ length: 12 }, (_, i) => 'F' + (i + 1)),
]);

// Set up capture on each "then" button
hotkeyRows.forEach(row => {
  const btn = row.querySelector('.hotkey-then');
  btn.addEventListener('focus', () => {
    btn.classList.add('capturing');
    btn.textContent = 'Press key…';
  });
  btn.addEventListener('blur', () => {
    btn.classList.remove('capturing');
    const key = btn.dataset.key;
    btn.textContent = key || '…';
  });
  btn.addEventListener('keydown', (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.key === 'Escape') {
      btn.blur();
      return;
    }
    const { label, key } = codeToKey(e.code, e.location);
    // Ignore a key the engine can't map rather than storing it: the config would
    // save and then never fire. Stay in capture mode so the user can try another.
    if (!SUPPORTED_THEN.has(key)) {
      btn.textContent = 'Unsupported — try another';
      return;
    }
    btn.dataset.key = key;
    btn.textContent = label;
    btn.classList.remove('capturing');
    btn.blur();
    validateHotkeys();
  });

  // Prefix change also triggers validation
  const select = row.querySelector('.hotkey-prefix');
  select.addEventListener('change', validateHotkeys);
});

function getHotkeyValues() {
  const result = {};
  hotkeyRows.forEach(row => {
    const action = row.dataset.action;
    const prefix = row.querySelector('.hotkey-prefix').value;
    const thenKey = row.querySelector('.hotkey-then').dataset.key;
    result[action] = { prefix, then: thenKey || '', window_ms: HOTKEY_DEFAULTS[action].window_ms };
  });
  return result;
}

function validateHotkeys() {
  const values = getHotkeyValues();
  const actions = Object.keys(values);
  const combos = actions.map(a => values[a].prefix + '+' + values[a].then);

  hotkeyRows.forEach(row => {
    const action = row.dataset.action;
    const warn = row.querySelector('.hotkey-warn');
    const entry = values[action];
    const warnings = [];

    // Check for side-effect warning
    if ((entry.prefix === 'Ctrl+C' || entry.prefix === 'Ctrl+Insert') && DANGEROUS_CTRL_COMBOS[entry.then]) {
      warnings.push(DANGEROUS_CTRL_COMBOS[entry.then]);
    }

    // Check for conflicts with other actions
    const myCombo = entry.prefix + '+' + entry.then;
    for (const other of actions) {
      if (other === action) continue;
      const otherCombo = values[other].prefix + '+' + values[other].then;
      if (myCombo === otherCombo && entry.then) {
        warnings.push('Same combo as ' + other.charAt(0).toUpperCase() + other.slice(1));
      }
    }

    warn.textContent = warnings.length ? '⚠ ' + warnings.join(' · ') : '';
  });

  return !combos.some((c, i) => combos.indexOf(c) !== i && values[actions[i]].then);
}

function populateHotkeys(hotkeys) {
  const cfg = hotkeys || HOTKEY_DEFAULTS;
  hotkeyRows.forEach(row => {
    const action = row.dataset.action;
    const entry = cfg[action] || HOTKEY_DEFAULTS[action];
    row.querySelector('.hotkey-prefix').value = entry.prefix;
    const btn = row.querySelector('.hotkey-then');
    btn.dataset.key = entry.then;
    btn.textContent = entry.then || '…';
  });
  validateHotkeys();
}

resetHotkeysBtn.addEventListener('click', () => {
  populateHotkeys(HOTKEY_DEFAULTS);
});

loadConfig().catch(console.error);
