## Why

Users encounter text and UI elements they want to translate or ask about that cannot be selected/copied — game interfaces, image-based PDFs, error dialogs, charts, foreign-language screenshots. The only way to query an AI about visual content is to manually screenshot, open a browser, paste, and ask. Quick Translator can collapse that to: press hotkey → drag region → ask.

This change adds two capabilities in one: (1) a screen-region capture flow with an in-app overlay, and (2) multimodal (vision) chat that sends the captured image alongside the user's question. Together they let users point at anything on screen and get an AI answer in one interaction.

## What Changes

- **Screen capture:** hotkey (default: RCtrl+RCtrl, configurable via change A) → `xcap` captures all monitors instantly (freeze) → fullscreen overlay per monitor displays the frozen image → user drags to select a region → overlay closes → backend crops the selection from the full-res image in RAM
- **Vision chat popup:** after region selection, the chat popup opens with an image thumbnail in the context strip and an empty input field. User types a question, sends → the message goes to the API as a multimodal content array (text + base64 image). Streaming response renders as normal.
- **Multiple images per session:** user can press the screenshot hotkey again while chat is open → second image attaches to the current session. History retains up to 2 images; oldest is replaced with `[earlier screenshot removed from context]` and the UI shows a placeholder.
- **`vision_model` config field:** separate model for vision requests (empty = use main `model`). Surfaced in Settings UI. "Test connection" tests both models if vision_model is set.
- **API layer:** `ChatMessage.content` changes from `String` to `serde_json::Value` (accepts both plain string and content-parts array). Backward-compatible — text-only history stays as strings.
- **Privacy:** images never written to disk; held in RAM, dropped when chat popup closes. User always sees a thumbnail of exactly what will be sent before typing.

## Capabilities

### New Capabilities
- `screenshot-capture`: Freeze-first screen capture with per-monitor overlay and region selection
- `vision-chat`: Multimodal chat with image context, 2-image cap, and vision_model routing

### Modified Capabilities
- `chat-popup`: context strip supports image thumbnails; second image attaches to open session
- `chat-streaming`: content field becomes Value (string or array); vision_model routing
- `config-store`: adds `vision_model` field
- `hotkey-config`: adds `screenshot` action entry (default: RCtrl+RCtrl)

## Impact

- **New files:** `src-tauri/src/screenshot.rs` (capture + crop + base64 encode), `frontend/overlay.html` + `overlay.js` + `overlay.css` (fullscreen selection UI)
- **Modified:** `src-tauri/src/api.rs` (ChatMessage content type, vision_model routing), `src-tauri/src/main.rs` (screenshot trigger handler, overlay window creation, manage screenshot state), `src-tauri/src/config.rs` (vision_model field), `src-tauri/src/windows.rs` (overlay window builder), `frontend/chat.js` (image in history, thumbnail rendering, attach second image), `frontend/chat.html`/`chat.css` (thumbnail strip), `frontend/settings.html`/`settings.js` (vision_model field)
- **New crates:** `xcap` (0.9.7, screen capture), `base64` (encoding for data URLs); `image` comes transitively via xcap
- **Capability ACL:** overlay window needs `core:window:allow-close`; no other new permissions (screenshot uses no Tauri plugin, just native capture via xcap + Win32)
- **Backwards-compatible:** missing `vision_model` → empty → uses `model`; existing text-only chat history works unchanged since `serde_json::Value` deserializes strings directly
