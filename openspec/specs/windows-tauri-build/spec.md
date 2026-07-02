# windows-tauri-build Specification

## Purpose
TBD - created by archiving change rewrite-rust-tauri-stage1. Update Purpose after archive.
## Requirements
### Requirement: Windows CI build produces artifacts

The GitHub Actions workflow SHALL build the Tauri application on `windows-latest` and upload the resulting Windows executable and installer as artifacts. Because the app cannot be built or run on the Linux dev environment, this CI build is the sole correctness gate and MUST actually compile the Rust code.

#### Scenario: Workflow triggers

- **WHEN** code is pushed to `main` or `master`, or the workflow is manually dispatched
- **THEN** the build job runs on `windows-latest`

#### Scenario: Rust compilation gate

- **WHEN** the build job runs
- **THEN** it installs a Rust toolchain and the Tauri build prerequisites, and compiles the `src-tauri` Rust crate in release mode
- **AND** the job fails if the Rust code does not compile

#### Scenario: Artifacts uploaded

- **WHEN** the Tauri build completes successfully
- **THEN** the produced `.exe` and the installer (NSIS bundle) are uploaded as workflow artifacts with 30-day retention

#### Scenario: PyInstaller path removed

- **WHEN** the workflow runs
- **THEN** it does NOT invoke PyInstaller or Inno Setup (those steps are removed) — the build is entirely Tauri-based

### Requirement: Windows admin elevation

The Tauri bundle SHALL request administrator elevation on Windows, replacing PyInstaller's `--uac-admin`, so the global keyboard hook can observe input directed at elevated windows.

#### Scenario: Elevation manifest

- **WHEN** the Windows executable is produced by the Tauri build
- **THEN** its embedded manifest requests `requireAdministrator` execution level

### Requirement: Tauri bundle configuration

The application SHALL be configured to bundle the frontend assets and the app icon without a JavaScript build step.

#### Scenario: Frontend bundled

- **WHEN** the app is built
- **THEN** the plain HTML/CSS/JS frontend assets and the app icon are bundled into the binary/installer, with no npm/node build step required

