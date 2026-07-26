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
  streaming = true;
  sendBtn.disabled = true;
  sendBtn.textContent = '…';

  addUserMessage(question);
  const aiEl = addAiMessage();
  let full = '';
  let firstChunk = true;

  // Chunk/done listeners are attached once in init(); they update `aiEl` via
  // the shared closure below.
  currentTurn = {
    el: aiEl,
    appendInterim(delta) {
      if (firstChunk) {
        aiEl.textContent = ''; // clear the typing indicator before first text
        firstChunk = false;
      }
      full += delta;
      aiEl.textContent = full; // interim: plain text while streaming
      scrollToBottom();
    },
    finish() {
      aiEl.innerHTML = renderMarkdown(full); // final: rendered markdown (escaped)
      scrollToBottom();
      // Record the assistant turn and cap history to the last 50 messages
      history.push({ role: 'assistant', content: full.trim() });
      if (history.length > 50) history = history.slice(history.length - 50);
      // After first send with images, clear image URLs so subsequent
      // messages don't re-attach them (they're already in history)
      imageUrls = [];
      updateImageStrip();
      streaming = false;
      sendBtn.disabled = false;
      sendBtn.textContent = 'Send';
      currentTurn = null;
    },
  };

  try {
    // Build the current message content — multimodal if images are attached
    let userContent = question;
    if (imageUrls.length > 0) {
      const parts = [{ type: 'text', text: question }];
      for (const url of imageUrls) {
        parts.push({ type: 'image_url', image_url: { url } });
      }
      userContent = parts;
    }

    // Record user turn with the appropriate content type
    history.push({ role: 'user', content: userContent });

    await invoke('chat_send', { selectedText, question, history });
  } catch (e) {
    full += `\n⚠ Error: ${e}`;
    if (currentTurn) currentTurn.finish();
  }
}

// The in-flight assistant turn, or null. Set in send(), consumed by listeners.
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

  // Close: Esc, button
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closePopup();
  });
  closeBtn.addEventListener('click', () => closePopup());

  // Blur-to-close, guarded until the window has focused once (parity with popup)
  let hasFocused = false;
  await getCurrentWindow().onFocusChanged(({ payload: focused }) => {
    if (focused) {
      hasFocused = true;
    } else if (hasFocused) {
      closePopup();
    }
  });

  chatInput.focus();
}

init().catch(console.error);
