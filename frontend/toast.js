// toast.js — transient notice that closes itself.
//
// The message arrives in the query string, not an event: this window is created
// and immediately written to, and a backend emit timed against WebView2 startup
// would be dropped (Tauri events are not buffered).

const { getCurrentWindow } = window.__TAURI__.window;

const DISMISS_MS = 2000;

const params = new URLSearchParams(window.location.search);
document.getElementById('toast-message').textContent = params.get('message') || '';

// The only dismissal path — this window never takes focus, so there is no blur
// to close on and no key events to receive.
setTimeout(() => {
  getCurrentWindow().close().catch(() => {});
}, DISMISS_MS);
