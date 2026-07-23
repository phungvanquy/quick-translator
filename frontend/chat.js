// chat.js — Chat popup logic
// Owns conversation history + selected-text context; drives requests via the
// chat_send command and renders streamed chat:// events. XSS-safe markdown via
// renderMarkdown (markdown.js).

const { invoke } = window.__TAURI__.core;
const { getCurrentWindow } = window.__TAURI__.window;
const { listen } = window.__TAURI__.event;

// ── Parse init params ─────────────────────────────────────────────────────────
function getParams() {
  const params = new URLSearchParams(window.location.search);
  return { selected: params.get('selected') || '' };
}

// ── DOM refs ──────────────────────────────────────────────────────────────────
const headerTitle  = document.getElementById('header-title');
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

// ── Close ─────────────────────────────────────────────────────────────────────
let isClosed = false;
async function closePopup() {
  if (isClosed) return;
  isClosed = true;
  try {
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
  headerTitle.textContent = '💬 Free Chat';
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
      // Record the turn and cap history to the last 50 messages
      history.push({ role: 'user', content: question });
      history.push({ role: 'assistant', content: full.trim() });
      if (history.length > 50) history = history.slice(history.length - 50);
      streaming = false;
      sendBtn.disabled = false;
      sendBtn.textContent = 'Send';
      currentTurn = null;
    },
  };

  try {
    await invoke('chat_send', { selectedText, question, history });
  } catch (e) {
    full += `\n⚠ Error: ${e}`;
    if (currentTurn) currentTurn.finish();
  }
}

// The in-flight assistant turn, or null. Set in send(), consumed by listeners.
let currentTurn = null;

// ── Init ──────────────────────────────────────────────────────────────────────
async function init() {
  const { selected } = getParams();
  selectedText = selected;

  if (selectedText.trim()) {
    const short = selectedText.length > 140 ? selectedText.slice(0, 137) + '…' : selectedText;
    contextText.textContent = short;
    headerTitle.textContent = '💬 Chat';
  } else {
    contextStrip.classList.add('hidden');
    headerTitle.textContent = '💬 Free Chat';
  }

  await listen('chat://chunk', (event) => {
    if (currentTurn) currentTurn.appendInterim(event.payload);
  });
  await listen('chat://done', () => {
    if (currentTurn) currentTurn.finish();
  });

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
