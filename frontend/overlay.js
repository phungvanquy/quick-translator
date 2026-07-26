// overlay.js — Screenshot region selection
// Receives a frozen screenshot as background, lets user drag-select a region,
// then emits the selection rectangle to the backend.

const { emit } = window.__TAURI__.event;
const { invoke } = window.__TAURI__.core;

const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');

let img = null;
let dragging = false;
let startX = 0, startY = 0;
let curX = 0, curY = 0;

const DIMMING = 'rgba(0, 0, 0, 0.4)';

// Which monitor this overlay covers — sent back with the selection so the
// backend crops from the matching capture.
const monitorIndex = Number(
  new URLSearchParams(window.location.search).get('monitor') || 0
);

// ── Load the preview image ───────────────────────────────────────────────────
// Pull, don't wait for a push: an emit from the backend would race WebView2
// startup and be dropped (Tauri events are not buffered), leaving a black canvas.

async function init() {
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;

  window.addEventListener('resize', () => {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    if (img) drawBase();
  });

  let src;
  try {
    src = await invoke('get_overlay_preview', { monitorIndex });
  } catch (e) {
    console.error('preview fetch failed', e);
    cancel();
    return;
  }

  img = new Image();
  img.onload = () => drawBase();
  img.onerror = () => cancel();
  img.src = src;
}

// ── Drawing ──────────────────────────────────────────────────────────────────

// Scale from canvas coordinates to screenshot-image pixels. The screenshot is
// captured at physical resolution while the canvas is sized in CSS pixels, so
// these differ on any scaled display. Never reuse a canvas rect as a source
// rect without this factor.
function imageScale() {
  return {
    sx: img.naturalWidth / canvas.width,
    sy: img.naturalHeight / canvas.height,
  };
}

function drawBase() {
  if (!img) return;
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  // Apply dim overlay
  ctx.fillStyle = DIMMING;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
}

function drawSelection() {
  if (!img) return;
  const x = Math.min(startX, curX);
  const y = Math.min(startY, curY);
  const w = Math.abs(curX - startX);
  const h = Math.abs(curY - startY);

  // Redraw base (dimmed)
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  ctx.fillStyle = DIMMING;
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // Cut out selected area (full brightness)
  if (w > 2 && h > 2) {
    const { sx, sy } = imageScale();
    ctx.drawImage(img, x * sx, y * sy, w * sx, h * sy, x, y, w, h);
    // Border
    ctx.strokeStyle = 'rgba(124, 107, 255, 0.8)';
    ctx.lineWidth = 2;
    ctx.strokeRect(x, y, w, h);
  }
}

// ── Mouse events ─────────────────────────────────────────────────────────────

canvas.addEventListener('mousedown', (e) => {
  if (e.button === 2) { cancel(); return; }
  if (e.button !== 0) return;
  if (!img) return; // preview not loaded yet — nothing to select from
  dragging = true;
  startX = e.clientX;
  startY = e.clientY;
  curX = startX;
  curY = startY;
});

canvas.addEventListener('mousemove', (e) => {
  if (!dragging) return;
  curX = e.clientX;
  curY = e.clientY;
  drawSelection();
});

canvas.addEventListener('mouseup', (e) => {
  if (!dragging) return;
  dragging = false;
  curX = e.clientX;
  curY = e.clientY;

  const x = Math.min(startX, curX);
  const y = Math.min(startY, curY);
  const w = Math.abs(curX - startX);
  const h = Math.abs(curY - startY);

  // Require minimum selection size
  if (w < 5 || h < 5) return;

  // Send the canvas size instead of devicePixelRatio: the backend divides its
  // own capture dimensions by this to get the exact CSS→physical factor. DPR
  // can disagree with the monitor's real scale factor (per-monitor DPI), and a
  // factor that is off by even 1.25× crops a smaller region that then gets
  // upscaled — the "zoomed in" symptom.
  emit('overlay://select', {
    x, y, width: w, height: h,
    viewportW: canvas.width,
    viewportH: canvas.height,
    monitor: monitorIndex,
  });
});

// Prevent context menu on right-click
canvas.addEventListener('contextmenu', (e) => e.preventDefault());

// ── Keyboard ─────────────────────────────────────────────────────────────────

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') cancel();
});

function cancel() {
  emit('overlay://cancel', {});
}

// ── Start ────────────────────────────────────────────────────────────────────

init();
