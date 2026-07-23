fn main() {
    // On Windows, feed our app.manifest (asInvoker execution level) into
    // Tauri's own resource compilation instead of embedding a second resource
    // via winres — two resource compilers both emit a VERSION resource, which
    // makes link.exe fail with CVT1100 "duplicate resource".
    #[cfg(target_os = "windows")]
    {
        let windows = tauri_build::WindowsAttributes::new()
            .app_manifest(include_str!("app.manifest"));
        let attributes = tauri_build::Attributes::new().windows_attributes(windows);
        tauri_build::try_build(attributes).expect("failed to run tauri-build");
    }

    #[cfg(not(target_os = "windows"))]
    tauri_build::build();
}
