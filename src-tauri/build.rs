fn main() {
    // Embed the Windows application manifest (requireAdministrator elevation).
    // Only compiled when targeting Windows.
    #[cfg(target_os = "windows")]
    embed_manifest();

    tauri_build::build()
}

#[cfg(target_os = "windows")]
fn embed_manifest() {
    let mut res = winres::WindowsResource::new();
    res.set_manifest_file("app.manifest");
    if let Err(e) = res.compile() {
        // Non-fatal: manifest embedding failure won't break the build,
        // but elevation won't work without it.
        eprintln!("cargo:warning=Could not embed app.manifest: {e}");
    }
}
