//! Screen capture + image processing for the screenshot-vision flow.
//!
//! Captures all monitors via xcap, crops a user-selected region, and encodes
//! the result as a JPEG base64 data URL for the vision API.

use base64::Engine;
use image::codecs::jpeg::JpegEncoder;
use image::{DynamicImage, GenericImageView, RgbaImage};
use std::io::Cursor;
use std::sync::Mutex;

// ── Types ────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct MonitorInfo {
    pub x: i32,
    pub y: i32,
    pub width: u32,
    pub height: u32,
    pub scale_factor: f32,
}

/// Physical-pixel rectangle from the overlay selection.
#[derive(Debug, Clone)]
pub struct PhysicalRect {
    pub x: u32,
    pub y: u32,
    pub width: u32,
    pub height: u32,
}

/// Holds captured screenshots in RAM until the chat popup closes.
pub struct ScreenshotState {
    pub captures: Vec<(MonitorInfo, RgbaImage)>,
    pub prepared_image: Option<String>, // base64 data URL ready for API
}

impl ScreenshotState {
    pub fn new(captures: Vec<(MonitorInfo, RgbaImage)>) -> Self {
        ScreenshotState { captures, prepared_image: None }
    }
}

/// Tauri-managed wrapper.
pub struct ScreenshotStore(pub Mutex<Option<ScreenshotState>>);

impl ScreenshotStore {
    pub fn new() -> Self {
        ScreenshotStore(Mutex::new(None))
    }
}

// PLACEHOLDER_FUNCTIONS

// ── Capture ──────────────────────────────────────────────────────────────────

/// Capture all monitors. Returns one (info, image) pair per monitor.
/// Called on the async runtime; xcap internally uses platform APIs.
#[cfg(target_os = "windows")]
pub fn capture_all_monitors() -> Result<Vec<(MonitorInfo, RgbaImage)>, String> {
    let monitors = xcap::Monitor::all().map_err(|e| format!("monitor enumeration failed: {e}"))?;
    let mut results = Vec::with_capacity(monitors.len());

    for mon in monitors {
        let info = MonitorInfo {
            x: mon.x(),
            y: mon.y(),
            width: mon.width(),
            height: mon.height(),
            scale_factor: mon.scale_factor(),
        };
        let img = mon.capture_image()
            .map_err(|e| format!("capture failed on monitor at ({},{}): {e}", info.x, info.y))?;
        results.push((info, img));
    }

    Ok(results)
}

#[cfg(not(target_os = "windows"))]
pub fn capture_all_monitors() -> Result<Vec<(MonitorInfo, RgbaImage)>, String> {
    Err("screen capture is only supported on Windows".into())
}

// ── Crop ─────────────────────────────────────────────────────────────────────

/// Extract a sub-region from a full-res capture.
pub fn crop_region(image: &RgbaImage, rect: &PhysicalRect) -> RgbaImage {
    let (iw, ih) = image.dimensions();
    // Clamp to image bounds
    let x = rect.x.min(iw.saturating_sub(1));
    let y = rect.y.min(ih.saturating_sub(1));
    let w = rect.width.min(iw - x);
    let h = rect.height.min(ih - y);

    let dyn_img = DynamicImage::ImageRgba8(image.clone());
    let cropped = dyn_img.crop_imm(x, y, w, h);
    cropped.to_rgba8()
}

// ── Encode for API ───────────────────────────────────────────────────────────

const MAX_DIMENSION: u32 = 1568;

/// Downscale longest edge to ≤1568px, encode as JPEG q80, return data URL.
pub fn prepare_for_api(cropped: &RgbaImage) -> String {
    let dyn_img = DynamicImage::ImageRgba8(cropped.clone());

    let resized = if dyn_img.width() > MAX_DIMENSION || dyn_img.height() > MAX_DIMENSION {
        dyn_img.resize(MAX_DIMENSION, MAX_DIMENSION, image::imageops::FilterType::Lanczos3)
    } else {
        dyn_img
    };

    let rgb = resized.to_rgb8();
    let mut buf = Cursor::new(Vec::new());
    let encoder = JpegEncoder::new_with_quality(&mut buf, 80);
    rgb.write_with_encoder(encoder).expect("JPEG encode failed");

    let b64 = base64::engine::general_purpose::STANDARD.encode(buf.into_inner());
    format!("data:image/jpeg;base64,{b64}")
}

// ── Encode for overlay preview ───────────────────────────────────────────────

/// Encode full image as JPEG q60 data URL (for overlay display).
pub fn prepare_preview(image: &RgbaImage) -> String {
    let rgb = DynamicImage::ImageRgba8(image.clone()).to_rgb8();
    let mut buf = Cursor::new(Vec::new());
    let encoder = JpegEncoder::new_with_quality(&mut buf, 60);
    rgb.write_with_encoder(encoder).expect("JPEG encode failed");

    let b64 = base64::engine::general_purpose::STANDARD.encode(buf.into_inner());
    format!("data:image/jpeg;base64,{b64}")
}
