# Proposal

> **Parked.** Only the proposal is written. Specs, design and tasks come when this change is picked up, before the Tauri desktop app needs it.

## Why

The desktop app will run the Python backend as a Tauri sidecar: one executable per OS, no Python install needed. Freezing this backend has known risks (a bundled native Codex CLI, native calls for copy-on-write, system tools like `hdiutil`), and they are cheaper to find now than when the desktop app is waiting on them.

## What Changes

- `make build-backend`: freeze the backend into a **one-folder** executable (PyInstaller or Nuitka; one-file mode would unpack about 300 MB on every launch).
- A GitHub Actions job that builds it per OS and CPU (macOS arm64 and x64, Linux; Windows later) and smoke-tests the built executable: boot, `GET /features`, one mock-harness add.
- **The Codex CLI is not bundled.** It is about 292 MB per platform (`codex` 248 MB plus `codex-code-mode-host` 44 MB) and must match the SDK's version exactly. Instead, the app **downloads the pinned version on first use** into its app data folder, and the harness passes that path to the SDK (`CodexConfig(codex_bin=...)`). A setting lets a user point at a CLI they already have. Other harnesses (for example Claude Code) can follow the same pattern.
- macOS signing and notarization of the executable and anything it launches, in step with Tauri's sidecar signing.

## Capabilities

### New Capabilities

- `backend-packaging`: how the backend is built, what it ships with, and how it obtains harness CLIs at runtime.

### Modified Capabilities

None.

## Impact

- New: build configuration, `make build-backend`, `.github/workflows/package.yml`, CLI download and verification code in the harness layer.
- Changed: the Codex harness (explicit `codex_bin`), settings (CLI location override).
- Needs: signing credentials for macOS in CI; network access on first use of a harness.
- Risks to settle in design: version pinning and checksum verification of the downloaded CLI, offline first launch, per-architecture builds.
