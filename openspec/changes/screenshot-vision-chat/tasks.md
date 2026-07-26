## 1. Screen Capture Module

- [x] 1.1 Add `xcap` and `base64` crates to `Cargo.toml`
- [x] 1.2 Create `src-tauri/src/screenshot.rs`: `capture_all_monitors() -> Vec<(MonitorInfo, RgbaImage)>` using `xcap::Monitor::all()` + `capture_image()`
- [x] 1.3 Add `crop_region(image: &RgbaImage, rect: PhysicalRect) -> RgbaImage` — extracts selection from full-res capture
- [x] 1.4 Add `prepare_for_api(cropped: &RgbaImage) -> String` — downscale longest edge ≤1568px, encode JPEG q80, return `data:image/jpeg;base64,...` URL
- [x] 1.5 Add `prepare_preview(image: &RgbaImage) -> String` — encode full image as JPEG q60 data URL (for overlay display)
- [x] 1.6 Define `ScreenshotState` struct and register as `Mutex<Option<ScreenshotState>>` in Tauri managed state

## 2. Overlay Window

- [x] 2.1 Create `frontend/overlay.html`: fullscreen page with a `<canvas>` element, no decorations
- [x] 2.2 Create `frontend/overlay.css`: body fills viewport, cursor crosshair, no scrollbars, no margin
- [x] 2.3 Create `frontend/overlay.js`: receive screenshot preview via query param or Tauri event → draw as canvas background; implement drag-to-select with dimmed mask + bright cutout; Esc/right-click → cancel (close window); mouseup → emit `overlay://select` event with `{x, y, width, height, dpr}` to backend
- [x] 2.4 Add `show_overlay_windows` to `windows.rs`: create one borderless fullscreen always-on-top window per monitor, positioned at monitor origin, sized to monitor dimensions; skip taskbar; label `overlay-{index}`
- [x] 2.5 Wire overlay windows: on hotkey fire → `capture_all_monitors()` → store in state → for each monitor, encode preview → pass to overlay window via query string or event → show

## 3. Screenshot Trigger Flow

- [x] 3.1 Add `handle_screenshot_trigger(app: AppHandle)` in `main.rs`: calls capture, opens overlays
- [x] 3.2 Wire `Action::Screenshot` in `hotkey.rs` dispatch (table-driven from change A) to spawn `handle_screenshot_trigger`
- [x] 3.3 Handle `overlay://select` event in backend: read rect + monitor index → crop from stored full-res image → `prepare_for_api()` → store base64 in state → close all overlay windows → open or signal chat popup
- [x] 3.4 Handle `overlay://cancel` event: close all overlay windows, clear screenshot state

## 4. Vision Chat Integration

- [x] 4.1 Change `ChatMessage.content` from `String` to `serde_json::Value` in `api.rs`; update `chat_stream` to forward content as-is (no `.as_str()` assumption)
- [x] 4.2 Update `chat_send` command signature: `history: Vec<ChatMessage>` still works (serde deserializes both string and array content from JSON)
- [x] 4.3 Add `vision_model` field to `Config` (default: empty string); add `default_vision_model()` fn
- [x] 4.4 In `chat_stream`: if any message in the request contains image content, use `vision_model` (or fallback to `model`) for the request's `model` field
- [x] 4.5 Apply `is_reasoning_model()` check to `vision_model` too — inject `reasoning_effort` when applicable

## 5. Chat Popup — Image Context

- [x] 5.1 Update `chat.js`: accept image data URL from backend (via event `chat://attach-image` or initial param); store in local state
- [x] 5.2 Render image thumbnail in context strip (max-height ~80px, click to expand in a modal or larger view)
- [x] 5.3 When sending a message with image context: build `content` as array `[{type:"text", text:question}, {type:"image_url", image_url:{url:dataUrl}}]`; subsequent turns (no new image) send plain string content
- [x] 5.4 Support second image: on `chat://attach-image` when one image already exists, add second thumbnail; update history-building logic to include both images in the next message
- [x] 5.5 Image cap enforcement: when third image arrives, replace oldest image message content with `"[earlier screenshot removed from context]"`, update context strip to show grayed placeholder
- [x] 5.6 On chat popup close: emit event to backend → backend clears `ScreenshotState` (drops images from RAM)

## 6. Attach Image to Open Chat

- [x] 6.1 In `handle_screenshot_trigger`: if chat popup is already open, after crop → emit `chat://attach-image` with the data URL instead of opening a new popup
- [x] 6.2 If chat popup is NOT open: after crop → open chat popup with image context (similar to text context but with image)

## 7. Settings UI — Vision Model

- [x] 7.1 Add "Vision Model" field to `settings.html` below the Model field, with hint "Leave empty to use the main model for vision"
- [x] 7.2 Wire save/load for `vision_model` in `settings.js`
- [x] 7.3 "Test connection": when `vision_model` is non-empty, run a second test request with that model and report both results

## 8. Verification

- [x] 8.1 `cargo build` passes
- [x] 8.2 `cargo clippy` passes
- [x] 8.3 Manual test: hotkey → overlay appears on all monitors showing frozen screen; drag selects region; Esc cancels
- [x] 8.4 Manual test: after region select → chat popup opens with thumbnail; type question → vision model responds
- [x] 8.5 Manual test: press hotkey again with chat open → second image attaches; both thumbnails visible
- [x] 8.6 Manual test: attach third image → oldest removed, placeholder shown, model told context was lost
- [x] 8.7 Manual test: close chat popup → verify no image files on disk, RAM freed
- [x] 8.8 Manual test: leave vision_model empty → screenshot chat uses main model; set vision_model → uses that instead
