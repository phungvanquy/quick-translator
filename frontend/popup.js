// popup.js — Translation popup logic
// Listens for Tauri events translate://chunk and translate://done
// Handles Escape and blur-to-close

// Access Tauri 2 APIs from the globally injected object (withGlobalTauri: true)
const { getCurrentWindow } = window.__TAURI__.window;
const { listen, emit } = window.__TAURI__.event;

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
const langName        = document.getElementById('lang-name');
const originalText    = document.getElementById('original-text');
const spinner         = document.getElementById('spinner');
const translationText = document.getElementById('translation-text');
const closeBtn        = document.getElementById('close-btn');
const copyBtn         = document.getElementById('copy-btn');
const copyLabel       = copyBtn.querySelector('.copy-label');

// ── Close ─────────────────────────────────────────────────────────────────────
let isClosed = false;

async function closePopup() {
  if (isClosed) return;
  isClosed = true;
  try {
    await getCurrentWindow().close();
  } catch (_e) {
    // window may already be closing
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────
async function init() {
  const { original, lang } = getParams();

  langName.textContent = lang;
  originalText.textContent = truncate(original);
  originalText.title = original; // full untruncated text on hover

  let streamStarted = false;
  let fullText = '';

  // Listen for translation chunks
  const unlistenChunk = await listen('translate://chunk', (event) => {
    if (!streamStarted) {
      // Hide spinner, show text area on first chunk
      spinner.style.display = 'none';
      translationText.style.display = 'block';
      streamStarted = true;
    }
    // Keep the raw source for final Markdown rendering, and show plain text
    // while streaming (partial Markdown renders poorly).
    fullText += event.payload;
    translationText.textContent = fullText;
  });

  // Listen for stream completion
  const unlistenDone = await listen('translate://done', () => {
    if (!streamStarted) {
      spinner.style.display = 'none';
      translationText.style.display = 'block';
    }
    // Render the accumulated text as Markdown. renderMarkdown escapes its
    // input first, so any HTML/script in the translation is inert. Empty
    // input renders to an empty string, which is harmless.
    translationText.innerHTML = renderMarkdown(fullText);
    translationText.classList.add('rendered');
    // Enable copy now that the full result is available (disabled while streaming)
    if (fullText.trim()) copyBtn.disabled = false;
    // Clean up event listeners
    unlistenChunk();
    unlistenDone();
  });

  // Copy the raw accumulated translation (not rendered HTML) to the clipboard.
  let copyResetTimer = null;
  const copyIcon = copyBtn.querySelector('use');
  copyBtn.addEventListener('click', async () => {
    if (copyBtn.disabled) return;
    try {
      await navigator.clipboard.writeText(fullText);
      copyBtn.classList.remove('copy-error');
      copyBtn.classList.add('copied');
      copyLabel.textContent = 'Copied';
      copyIcon.setAttribute('href', '#ic-check');
    } catch (_e) {
      copyBtn.classList.remove('copied');
      copyBtn.classList.add('copy-error');
      copyLabel.textContent = 'Copy failed';
    }
    if (copyResetTimer) clearTimeout(copyResetTimer);
    copyResetTimer = setTimeout(() => {
      copyBtn.classList.remove('copied', 'copy-error');
      copyLabel.textContent = 'Copy';
      copyIcon.setAttribute('href', '#ic-copy');
    }, 1200);
  });

  // Escape to close
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closePopup();
    }
  });

  // Click outside (blur) to close — but only after the popup has actually
  // gained focus at least once. Otherwise a window that never grabbed focus
  // (or a spurious initial "unfocused" event) would close the popup instantly.
  let hasFocused = false;
  await getCurrentWindow().onFocusChanged(({ payload: focused }) => {
    if (focused) {
      hasFocused = true;
    } else if (hasFocused) {
      closePopup();
    }
  });

  // Close button
  closeBtn.addEventListener('click', () => closePopup());

  // Signal the backend that our listeners are attached and it may start
  // streaming. Tauri events are not buffered, so the backend waits for this
  // before emitting translate://chunk (see handle_translate_trigger).
  await emit('popup://ready');
}

init().catch(console.error);
