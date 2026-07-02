// popup.js — Translation popup logic
// Listens for Tauri events translate://chunk and translate://done
// Handles Escape and blur-to-close

// Access Tauri 2 APIs from the globally injected object (withGlobalTauri: true)
const { getCurrentWindow } = window.__TAURI__.window;
const { listen } = window.__TAURI__.event;

// ── Parse query string parameters ─────────────────────────────────────────────
function getParams() {
  const params = new URLSearchParams(window.location.search);
  return {
    original: params.get('original') || '',
    lang: params.get('lang') || 'Vietnamese',
  };
}

// ── Truncate original text to ~120 chars with ellipsis ───────────────────────
function truncate(text, maxLen = 120) {
  if (text.length <= maxLen) return text;
  return text.slice(0, 117) + '…';
}

// ── DOM refs ──────────────────────────────────────────────────────────────────
const langLabel       = document.getElementById('lang-label');
const originalText    = document.getElementById('original-text');
const spinner         = document.getElementById('spinner');
const translationText = document.getElementById('translation-text');
const closeBtn        = document.getElementById('close-btn');

// ── Spinner frames (braille dots, matching Python constants.py) ───────────────
const SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];
let spinnerIdx = 0;
let spinnerInterval = null;

function startSpinner() {
  const icon = document.getElementById('spinner-icon');
  spinnerInterval = setInterval(() => {
    icon.textContent = SPINNER_FRAMES[spinnerIdx % SPINNER_FRAMES.length];
    spinnerIdx++;
  }, 80);
}

function stopSpinner() {
  if (spinnerInterval !== null) {
    clearInterval(spinnerInterval);
    spinnerInterval = null;
  }
}

// ── Close ─────────────────────────────────────────────────────────────────────
let isClosed = false;

async function closePopup() {
  if (isClosed) return;
  isClosed = true;
  stopSpinner();
  try {
    await getCurrentWindow().close();
  } catch (_e) {
    // window may already be closing
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────
async function init() {
  const { original, lang } = getParams();

  langLabel.textContent = '⟶  ' + lang;
  originalText.textContent = truncate(original);

  startSpinner();

  let streamStarted = false;

  // Listen for translation chunks
  const unlistenChunk = await listen('translate://chunk', (event) => {
    if (!streamStarted) {
      // Hide spinner, show text area on first chunk
      spinner.style.display = 'none';
      translationText.style.display = 'block';
      streamStarted = true;
      stopSpinner();
    }
    translationText.textContent += event.payload;
  });

  // Listen for stream completion
  const unlistenDone = await listen('translate://done', () => {
    stopSpinner();
    if (!streamStarted) {
      spinner.style.display = 'none';
      translationText.style.display = 'block';
    }
    // Clean up event listeners
    unlistenChunk();
    unlistenDone();
  });

  // Escape to close
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closePopup();
    }
  });

  // Click outside (blur) to close — fires when window loses focus
  await getCurrentWindow().onFocusChanged(({ payload: focused }) => {
    if (!focused) {
      closePopup();
    }
  });

  // Close button
  closeBtn.addEventListener('click', () => closePopup());
}

init().catch(console.error);
