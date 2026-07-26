## Context

The app already has a chat popup that streams from an OpenAI-compatible endpoint. This change adds a visual input channel: users select a screen region and ask about it. The backend must send images as base64 in the chat/completions multimodal format, and the frontend must display image context alongside text.

Key existing pieces this builds on:
- `hotkey.rs`: table-driven state machine (after change A) dispatches a `screenshot` action
- `api.rs`: `stream_completion` posts JSON to chat/completions and streams SSE chunks
- `windows.rs`: DPI-safe popup creation (`set_position(PhysicalPosition)` using cursor monitor scale)
- `chat.js`: owns conversation history, drives requests via `chat_send` command
- `main.rs`: `handle_chat_trigger` opens the chat popup with text context

Dependencies: change A (`configurable-hotkeys`) must land first — it provides the hotkey table infrastructure and the `screenshot` action slot.

## Goals / Non-Goals

**Goals:**
- Capture a screen region with minimal latency (freeze-first approach)
- Send the image to a vision-capable model and stream back the response
- Let users attach multiple images in one chat session (cap: 2 in context)
- Keep images in RAM only — never write to disk (privacy)
- Provide a separate `vision_model` config field

**Non-Goals:**
- OCR / local text extraction (may add later as a fast-path optimization)
- Video capture or animated region recording
- Cross-monitor region selection (v1: selection stays within one monitor)
- Image editing / annotation before sending
- Drag-and-drop or clipboard-paste image input (hotkey-only for v1)

## Decisions

### 1. Freeze-first capture, not live-transparent overlay

**Decision:** On hotkey fire, immediately capture all monitors via `xcap::Monitor::all()` → `capture_image()`. Store the full-res `RgbaImage` per monitor in app state. Then open a fullscreen overlay window per monitor displaying the captured image as background. The user drags on a static image.

**Why over transparent overlay:**
- No race between hiding the overlay and capturing (the overlay IS the captured image)
- Captures transient elements (menus, tooltips) that disappear on focus loss
- No need for `.transparent(true)` — avoids the unverified OQ1 about transparency + shadow + always-on-top on Windows
- Simpler rendering: just an `<img>` filling the viewport

**Tradeoff:** ~50-150ms freeze latency (xcap capture time). Acceptable because the screen content is already "frozen" from the user's perspective the moment they decide to screenshot.

### 2. One overlay window per monitor, no cross-monitor drag

**Decision:** Create one borderless fullscreen window per monitor, each showing that monitor's captured image. Selection is confined to the monitor where the drag started.

**Why:** A single window spanning the virtual desktop has one `devicePixelRatio` but monitors may differ. CSS pixel → physical pixel conversion would be wrong for non-primary monitors. Per-monitor windows each have the correct DPI, and coordinate math stays simple.

**Future extension:** cross-monitor could be added by stitching captures, but it's a rare use case.

### 3. Overlay UI: dark tint + crosshair + selection rectangle

**Decision:** The overlay shows the frozen screenshot at full brightness, with a semi-transparent dark layer on top. As the user drags, the selected region is "cut out" (full brightness), creating a spotlight effect. Cursor is crosshair. Esc or right-click cancels.

```
┌──────────────────────────────────────────────┐
│ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
│ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
│ ░░░░░░┌─────────────────┐░░░░░░░░░░░░░░░░░░░ │
│ ░░░░░░│  SELECTED AREA  │░░░░░░░░░░░░░░░░░░░ │
│ ░░░░░░│  (full bright)  │░░░░░░░░░░░░░░░░░░░ │
│ ░░░░░░└─────────────────┘░░░░░░░░░░░░░░░░░░░ │
│ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
│     ░ = dimmed (rgba(0,0,0,0.4) mask)        │
└──────────────────────────────────────────────┘
```

CSS canvas approach: the image is the `<canvas>` background, the dim layer is drawn on top, and `clearRect` cuts out the selection.

### 4. Image processing pipeline

**Decision:**

```
Full-res RgbaImage (in RAM)
    │
    ├─ for overlay display: encode as JPEG q60, data URL → <img> src
    │   (fast encode, lower quality OK for preview)
    │
    └─ for API: crop selection rect → downscale longest edge to ≤1568px
                → JPEG q80 → base64 data URL
                (quality matters, but capped to control token cost)
```

**Why 1568px:** OpenAI's vision models internally tile at 512px. 1568px = 3 tiles wide, which is the sweet spot for detail vs. token cost documented in their API docs. Larger images get downscaled server-side anyway.

**Why JPEG over PNG:** Screenshots of UI are mostly gradients/text — JPEG at q80 is 3-5x smaller than PNG with negligible quality loss for vision model understanding. Keeps the request payload under ~500KB for a typical region.

### 5. ChatMessage.content: String → serde_json::Value

**Decision:** Change `ChatMessage` to:

```rust
pub struct ChatMessage {
    pub role: String,
    pub content: serde_json::Value, // String OR [{"type":"text",...}, {"type":"image_url",...}]
}
```

**Why Value over an enum:** The frontend already sends JSON. With `Value`, text messages stay as `"content": "hello"` (valid JSON string), and image messages use the array format. `serde_json::Value` deserializes both without a custom deserializer. The API endpoint accepts both formats too.

**History handling:** When the frontend sends history to `chat_send`, image entries are passed as the content array. The backend forwards them as-is. No image re-encoding on subsequent turns — the base64 is already in the history object.

### 6. Image cap in history: 2 images, explicit removal

**Decision:** The frontend caps images in the active history at 2. When a third image is attached:
- The oldest image message's content is replaced with `[earlier screenshot removed from context]`
- The context strip shows a grayed-out placeholder for the removed image
- The model receives the text placeholder, so it knows context was lost

**Why 2:** Each image is ~300-500KB base64. With 2 images + text history, a typical request is ~1-1.5MB. Three images push past 2MB and risk timeout on slow connections. Two is enough for "compare these two things" use cases.

**Why explicit over silent:** If the model suddenly can't see an image it previously described, its answers become incoherent. The placeholder text signals the gap both to the model and the user.

### 7. vision_model config field

**Decision:** Add `vision_model: String` to Config (default: empty). When non-empty, screenshot-triggered chat requests use this model instead of the main `model`. Text-only chat always uses `model`.

**Why separate:** Users often configure a cheap/fast model for translation (gpt-4o-mini). Vision requests need a vision-capable model (gpt-4o, gpt-4.1). Forcing a single model means either overpaying for translation or lacking vision capability.

**Test connection:** when `vision_model` is set, "Test connection" sends a minimal request to both models and reports results separately.

### 8. Screenshot state lifecycle

**Decision:** Screenshot data lives in a `Mutex<Option<ScreenshotState>>` managed by Tauri:

```rust
struct ScreenshotState {
    captures: Vec<(MonitorInfo, RgbaImage)>, // one per monitor
}
```

- Set when hotkey fires and capture succeeds
- Read when overlay sends selection rect → crop
- Cleared (dropped) when: chat popup closes, Esc cancels overlay, or a new capture replaces it

**Why Mutex<Option> over lifetime:** The data outlives any single async task (hotkey → overlay → chat popup). Tauri managed state with interior mutability is the established pattern in this codebase.

### 9. Attaching a second image mid-chat

**Decision:** If the user presses the screenshot hotkey while the chat popup is already open:
- New overlay opens (same freeze-first flow)
- On selection, the image is sent to the existing chat popup via a Tauri event (`chat://attach-image`)
- The chat popup adds it to its context and shows a second thumbnail
- The user's next message includes both images in the content array

**Why event over new popup:** Opening a second chat popup would split the conversation. Attaching to the existing one preserves context continuity.

## Open Questions

- **OQ1:** Overlay window creation latency. If `WebviewWindowBuilder` takes >200ms to show the overlay after capture, the user sees a flash of the live desktop between pressing the hotkey and seeing the frozen image. Mitigation: could pre-create hidden overlay windows at startup, but that conflicts with the low-idle-footprint goal. Likely acceptable — the screen is "frozen" in the user's mind from the moment they press the hotkey.
- **OQ2:** `xcap` capture latency on multi-monitor setups with mixed DPI. Untested. If slow (>500ms), fall back to capturing only the monitor under the cursor.
