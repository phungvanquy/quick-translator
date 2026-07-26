// chat.js — Chat popup logic
// Owns conversation history + selected-text context; drives requests via the
// chat_send command and renders streamed chat:// events. XSS-safe markdown via
// renderMarkdown (markdown.js).

const { invoke } = window.__TAURI__.core;
const { getCurrentWindow } = window.__TAURI__.window;
const { listen, emit } = window.__TAURI__.event;

// ── Parse init params ─────────────────────────────────────────────────────────
function getParams() {
  const params = new URLSearchParams(window.location.search);
  return { selected: params.get('selected') || '' };
}

// ── DOM refs ──────────────────────────────────────────────────────────────────
const headerLabel  = document.getElementById('header-label');
const contextStrip = document.getElementById('context-strip');
const contextText  = document.getElementById('context-text');
const contextClear = document.getElementById('context-clear');
const transcript   = document.getElementById('transcript');
const chatInput    = document.getElementById('chat-input');
const sendBtn      = document.getElementById('send-btn');
const closeBtn     = document.getElementById('close-btn');

// ── State ───────────────────────────────────────────────────────────────────
let selectedText = '';
let history = [];       // [{role, content}, …], capped at 50
let streaming = false;
let imageUrls = [];     // base64 data URLs of attached screenshots (max 2)
const MAX_IMAGES = 2;

// ── Close ─────────────────────────────────────────────────────────────────────
let isClosed = false;
async function closePopup() {
  if (isClosed) return;
  isClosed = true;
  try {
    // Signal backend to clear screenshot state (drops images from RAM)
    await emit('chat://closed', {});
    await getCurrentWindow().close();
  } catch (_e) { /* already closing */ }
}

// ── Transcript helpers ────────────────────────────────────────────────────────
function addUserMessage(text) {
  const el = document.createElement('div');
  el.className = 'msg msg-user';
  el.textContent = text; // user text is plain, never HTML
  transcript.appendChild(el);
  scrollToBottom();
}

function addAiMessage() {
  const el = document.createElement('div');
  el.className = 'msg msg-ai';
  // Seed with a typing indicator until the first chunk arrives.
  el.innerHTML = '<span class="typing"><span></span><span></span><span></span></span>';
  transcript.appendChild(el);
  scrollToBottom();
  return el;
}

// ── Textarea auto-grow ──────────────────────────────────────────────────────
const INPUT_MAX_PX = 120;
function autoGrow() {
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(chatInput.scrollHeight, INPUT_MAX_PX) + 'px';
}
function resetInputHeight() {
  chatInput.style.height = '';
}

function scrollToBottom() {
  transcript.scrollTop = transcript.scrollHeight;
}

// ── Context clear (→ free chat) ───────────────────────────────────────────────
function clearContext() {
  selectedText = '';
  history = [];
  contextStrip.classList.add('hidden');
  headerLabel.textContent = 'Free Chat';
}

// ── Send ──────────────────────────────────────────────────────────────────────
async function send() {
  const question = chatInput.value.trim();
  if (!question || streaming) return;

  chatInput.value = '';
  resetInputHeight();

  // Multimodal content when images are attached, plain text otherwise.
  let userContent = question;
  if (imageUrls.length > 0) {
    const parts = [{ type: 'text', text: question }];
    for (const url of imageUrls) {
      parts.push({ type: 'image_url', image_url: { url } });
    }
    userContent = parts;
  }

  // Recorded BEFORE invoking: the backend sends history verbatim and its last
  // entry is the question, so it must already be in there.
  history.push({ role: 'user', content: userContent });

  addUserMessage(question);
  beginTurn();
  await runTurn();
}

// Create the assistant bubble and the handlers the chat:// listeners drive.
// Retry calls this again for the same history entry, so it must not touch
// `history` — the failed turn's user message is still its last entry.
function beginTurn() {
  const aiEl = addAiMessage();
  let full = '';
  let firstChunk = true;

  streaming = true;
  sendBtn.disabled = true;
  sendBtn.textContent = '…';

  // Ends the turn either way. The attached images are cleared on both paths
  // because they now live in the history entry — leaving them pending would
  // re-attach them to the next message as a second copy.
  const releaseInput = () => {
    imageUrls = [];
    updateImageStrip();
    streaming = false;
    sendBtn.disabled = false;
    sendBtn.textContent = 'Send';
    currentTurn = null;
  };

  currentTurn = {
    el: aiEl,
    failed: false,
    appendInterim(delta) {
      if (firstChunk) {
        aiEl.textContent = ''; // clear the typing indicator before first text
        firstChunk = false;
      }
      full += delta;
      aiEl.textContent = full; // interim: plain text while streaming
      scrollToBottom();
    },
    fail(error) {
      this.failed = true;
      aiEl.textContent = '';
      aiEl.classList.add('msg-error');
      aiEl.appendChild(buildErrorNode(error));
      scrollToBottom();
      releaseInput();
    },
    finish() {
      if (this.failed) return;
      aiEl.innerHTML = renderMarkdown(full); // final: rendered markdown (escaped)
      scrollToBottom();
      // Record the assistant turn and cap history to the last 50 messages
      history.push({ role: 'assistant', content: full.trim() });
      if (history.length > 50) history = history.slice(history.length - 50);
      releaseInput();
    },
  };
}

// Send whatever is already in `history` and stream the reply into the current
// bubble.
async function runTurn() {
  try {
    await invoke('chat_send', { selectedText, history });
  } catch (e) {
    if (currentTurn) {
      currentTurn.fail({
        summary: 'Could not start the request.',
        detail: String(e),
        retryable: true,
      });
    }
  }
}

// Build the failure display for a bubble: summary, collapsed raw detail, and a
// retry that replaces the failed bubble with a fresh attempt.
function buildErrorNode({ summary, detail, retryable }) {
  const box = document.createElement('div');
  box.className = 'error-box';

  const summaryEl = document.createElement('p');
  summaryEl.className = 'error-summary';
  summaryEl.textContent = summary;
  box.appendChild(summaryEl);

  if (detail) {
    const details = document.createElement('details');
    details.className = 'error-details';
    const toggle = document.createElement('summary');
    toggle.className = 'error-details-toggle';
    toggle.textContent = 'Details';
    const pre = document.createElement('pre');
    pre.className = 'error-detail-text';
    pre.textContent = detail;
    details.append(toggle, pre);
    box.appendChild(details);
  }

  if (retryable) {
    const retry = document.createElement('button');
    retry.className = 'btn-retry';
    retry.textContent = 'Retry';
    retry.addEventListener('click', () => {
      if (streaming) return;
      const failedBubble = box.closest('.msg');
      if (failedBubble) failedBubble.remove();
      beginTurn();
      runTurn();
    });
    box.appendChild(retry);
  }

  return box;
}

// The in-flight assistant turn, or null. Set in beginTurn(), driven by the
// chat:// listeners.
let currentTurn = null;

// ── Image handling ──────────────────────────────────────────────────────────

function attachImage(dataUrl) {
  if (imageUrls.length >= MAX_IMAGES) {
    // Enforce cap: remove oldest image from history too
    const oldUrl = imageUrls.shift();
    // Replace old image in history with placeholder
    for (const msg of history) {
      if (Array.isArray(msg.content)) {
        msg.content = msg.content.map(part => {
          if (part.type === 'image_url' && part.image_url && part.image_url.url === oldUrl) {
            return { type: 'text', text: '[earlier screenshot removed from context]' };
          }
          return part;
        });
      }
    }
  }
  imageUrls.push(dataUrl);
  updateImageStrip();
}

function updateImageStrip() {
  // Create or find the image strip container
  let strip = document.getElementById('image-strip');
  if (!strip) {
    strip = document.createElement('div');
    strip.id = 'image-strip';
    strip.className = 'image-strip';
    // Insert after context strip
    const ctx = document.getElementById('context-strip');
    ctx.parentNode.insertBefore(strip, ctx.nextSibling);
  }

  strip.innerHTML = '';
  if (imageUrls.length === 0) {
    strip.classList.add('hidden');
    return;
  }
  strip.classList.remove('hidden');

  for (const url of imageUrls) {
    const thumb = document.createElement('img');
    thumb.className = 'image-thumb';
    thumb.src = url;
    thumb.alt = 'Screenshot';
    strip.appendChild(thumb);
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────
async function init() {
  const { selected } = getParams();
  selectedText = selected;

  if (selectedText.trim()) {
    const short = selectedText.length > 140 ? selectedText.slice(0, 137) + '…' : selectedText;
    contextText.textContent = short;
    headerLabel.textContent = 'Chat';
  } else {
    contextStrip.classList.add('hidden');
    headerLabel.textContent = 'Free Chat';
  }

  await listen('chat://chunk', (event) => {
    if (currentTurn) currentTurn.appendInterim(event.payload);
  });
  await listen('chat://error', (event) => {
    if (currentTurn) currentTurn.fail(event.payload);
  });
  await listen('chat://done', () => {
    if (currentTurn) currentTurn.finish();
  });

  // Image attachments from the screenshot flow arrive two ways:
  //  - event, when this popup was already open at capture time (listeners up)
  //  - pull below, when the capture opened this popup (an emit timed against
  //    webview startup would be dropped — Tauri events are not buffered)
  await listen('chat://attach-image', (event) => {
    attachImage(event.payload);
    // If no text context, switch header to reflect image context
    if (!selectedText.trim()) {
      headerLabel.textContent = 'Chat';
    }
  });

  try {
    const pending = await invoke('take_pending_image');
    if (pending) {
      attachImage(pending);
      if (!selectedText.trim()) headerLabel.textContent = 'Chat';
    }
  } catch (e) {
    console.error('pending image fetch failed', e);
  }

  // Send triggers
  sendBtn.addEventListener('click', send);
  chatInput.addEventListener('input', autoGrow);
  chatInput.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter') return;
    // Don't send while an IME composition is active (Vietnamese/CJK input):
    // Enter there confirms the composition, it must not submit the message.
    if (e.isComposing || e.keyCode === 229) return;
    // Shift+Enter (without Ctrl) inserts a newline — let the textarea handle it.
    if (e.shiftKey && !e.ctrlKey) return;
    // Enter (no Shift) or Ctrl+Enter → send.
    e.preventDefault();
    send();
  });

  // Context clear
  contextClear.addEventListener('click', clearContext);

  // Close only on deliberate action. Unlike the translate popup, this window
  // holds a conversation and attached screenshots that a stray click elsewhere
  // must not destroy — so there is no blur-to-close here.
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closePopup();
  });
  closeBtn.addEventListener('click', () => closePopup());

  chatInput.focus();
}

init().catch(console.error);
