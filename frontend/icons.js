// icons.js — Shared inline SVG icon sprite.
// Single source of truth for all UI glyphs (replaces emoji). Injects a hidden
// <symbol> sprite at the top of <body>; reference an icon with:
//   <svg class="ic"><use href="#ic-close"/></svg>
// Strokes use currentColor (see .ic in theme.css) so icons tint per theme.
// Paths adapted from the MIT-licensed Lucide icon set (24x24 viewBox).
//
// This script is included as the FIRST element inside <body> so the sprite is
// present before the markup that references it renders.
(function () {
  var SPRITE = [
    '<svg class="ic-sprite" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">',
    // close (x)
    '<symbol id="ic-close" viewBox="0 0 24 24"><path d="M18 6 6 18M6 6l12 12"/></symbol>',
    // arrow-right (language direction)
    '<symbol id="ic-arrow-right" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></symbol>',
    // chat bubble
    '<symbol id="ic-chat" viewBox="0 0 24 24"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></symbol>',
    // spinner (3/4 ring — spun via .ic-spin)
    '<symbol id="ic-spinner" viewBox="0 0 24 24"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></symbol>',
    // volume (TTS)
    '<symbol id="ic-volume" viewBox="0 0 24 24"><path d="M11 5 6 9H2v6h4l5 4V5z"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07M19.07 4.93a10 10 0 0 1 0 14.14"/></symbol>',
    // copy (two stacked cards)
    '<symbol id="ic-copy" viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></symbol>',
    // check (copied confirmation)
    '<symbol id="ic-check" viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5"/></symbol>',
    // refresh / reset (rotate)
    '<symbol id="ic-refresh" viewBox="0 0 24 24"><path d="M23 4v6h-6M1 20v-6h6"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></symbol>',
    '</svg>',
  ].join('');

  function inject() {
    if (document.getElementById('ic-sprite-root')) return;
    var holder = document.createElement('div');
    holder.id = 'ic-sprite-root';
    holder.style.display = 'none';
    holder.innerHTML = SPRITE;
    document.body.insertBefore(holder, document.body.firstChild);
  }

  if (document.body) {
    inject();
  } else {
    document.addEventListener('DOMContentLoaded', inject);
  }
})();
