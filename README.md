# Coding Agent Terminal (CAT)

<div align="center">

```
  ██████╗ █████╗ ████████╗
 ██╔════╝██╔══██╗╚══██╔══╝
 ██║     ███████║   ██║   
 ██║     ██╔══██║   ██║   
 ╚██████╗██║  ██║   ██║   
  ╚═════╝╚═╝  ╚═╝   ╚═╝   

CODING AGENT TERMINAL · v0.7.9.0
```

[![CI](https://github.com/kazizillani-oss/CAT_v0.7.9/actions/workflows/ci.yml/badge.svg)](https://github.com/kazizillani-oss/CAT_v0.7.9/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-0.7.9.0-blue.svg)](https://github.com/kazizillani-oss/CAT_v0.7.9)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platforms](https://img.shields.io/badge/platforms-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()

*An autonomous AI developer terminal and chemical computation environment styled like OpenCode, Claude Code, and Warp in the Tokyo Night theme.*

</div>

---

## ⚡ Quick Install

CAT is distributed across multiple channels. Choose the method that best fits your workflow:

### Option 1: Windows Installer (Recommended for Windows)
Download and run the native installer:
- **`CAT-Setup.exe`** from [Latest Releases](https://github.com/kazizillani-oss/CAT_v0.7.9/releases/latest).
- Per-user installation to `%LOCALAPPDATA%\Programs\CAT` (no administrator privileges required).
- Automatically adds `cat`, `catx`, and `cct` to your `PATH` and configures PowerShell aliases cleanly.

Or via PowerShell:
```powershell
powershell -ExecutionPolicy Bypass -File installer/windows/scripts/install.ps1 -Install
```

### Option 2: Local Development / Editable Install
If you are developing or running from source:
```bash
git clone https://github.com/kazizillani-oss/CAT_v0.7.9.git
cd CAT_v0.7.9
python -m pip install -e .
cat
```

---

## 🚀 CLI Commands & Subcommands

| Command | Purpose |
| :--- | :--- |
| `cat` / `catx` / `cct` | Launch the interactive CAT terminal & UI. |
| `cat update` | Check for and install the latest CAT version from GitHub Releases. |
| `cat update --check` | Check if a newer version is available without installing. |
| `cat rollback` | Roll back to the previously installed version. |
| `cat repair` | Self-heal corrupted configurations, repair directory structures and file permissions. |
| `cat --debug` | Display detailed environment, paths, platform, and runtime debugging information. |
| `cat --doctor` | Run diagnostic health checks across Python, terminal capabilities, and AI providers. |
| `cat --version` | Display the current installed CAT version. |

---

## 🛠️ Key Features

- **Tokyo Night Terminal UI**: Rich ASCII styling, 24-bit ANSI colors, split-pane Textual layout, animated spinners, and sound effects.
- **Autonomous Development & Workspace Management**: Detects git roots, VS Code workspaces, parses manifests, and indexes files with live progress indicators.
- **Universal Formula & Science Calculator**: 39+ symbolic formulas, 2D/3D animated graphs, and live Bohr/quantum orbital simulations.
- **Multi-Provider AI Orchestrator**: Supports OpenAI, Anthropic, Gemini, Groq, OpenRouter, and Ollama with automatic failover and tool execution.
- **Extensible Architecture**: `.cat` chats store and `.catxt` extension registry for custom modules and extensions.
- **Fomoji Server Integration**: Optional bundled local web services with automated lifecycle management.

---

## 📦 Universal Distribution Architecture

CAT's distribution system decouples lightweight public launchers from private source code:
- **Zero Source Leakage**: npm and PyPI packages contain strictly minimal launchers (~4 kB) that pull platform-native binaries verified by SHA256 checksums from `release/manifest/releases.json`.
- **Atomic Updates & Rollbacks**: Update artifacts are validated against signed manifests before replacing running binaries, with automated snapshotting into `~/.cat/versions/`.
- **Command Collision Prevention**: Provides both `cat` and `catx` commands to prevent collisions with GNU coreutils `cat` on Unix and handles PowerShell's built-in `Get-Content` alias automatically.

For detailed documentation:
- [Distribution Architecture](docs/DISTRIBUTION.md)
- [Maintainer Releasing Guide](docs/RELEASING.md)

---

## 🧪 Testing & Verification

Run the test suite locally:

```bash
# Verify release isolation, security, and version sync
python scripts/verify_release.py

# Run distribution integration unit tests
python scripts/test_distribution.py

# Test runtime builder in dry-run mode
python scripts/build_runtime.py --dry-run
```

---

## 📄 License

MIT © [Kazi Zillani](https://github.com/kazizillani-oss)


