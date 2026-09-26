# Coding Agent Terminal (CAT)

<div align="center">

```
  ██████╗ █████╗ ████████╗
 ██╔════╝██╔══██╗╚══██╔══╝
 ██║     ███████║   ██║   
 ██║     ██╔══██║   ██║   
 ╚██████╗██║  ██║   ██║   
  ╚═════╝╚═╝  ╚═╝   ╚═╝   

CODING AGENT TERMINAL · v0.8.ab [final version]
```

[![CI]<img width="2778" height="1284" alt="Image" src="https://github.com/user-attachments/assets/d6c233c6-1d15-49bf-bb9a-5db8420bbf1b" />(https://github.com/kazizillani-oss/CAT_v0.7.9/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-0.8.ab-blue.svg)](https://github.com/kazizillani-oss/CAT_v0.7.9)
[![VS Code Extension](https://img.shields.io/badge/VS%20Code%20Extension-v0.8.6-blue.svg)](https://marketplace.visualstudio.com/items?itemName=KaziZillani.cat-cli)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platforms](https://img.shields.io/badge/platforms-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()

*An autonomous AI developer terminal and chemical computation environment styled like OpenCode, Claude Code, and Warp in the Tokyo Night theme.*

</div>

---

## ⚡ Quick Install

CAT is distributed across multiple channels. Choose the method that best fits your workflow:

### Option 1: Install from PyPI (Recommended for most users)

> **Status: Coming after PyPI release — not yet published.**
> The PyPI distribution `cct-cli` v0.8.ab has been built and validated
> locally (`python -m build`, `twine check dist/*`) but has **not** been
> uploaded to PyPI yet. Do not expect `pip install cct-cli` to work until
> the first successful publish is confirmed. Once published, use:

CAT CLI is distributed as `cct-cli` on PyPI. The PyPI distribution name and the
terminal command are intentionally different:

```text
PyPI package: cct-cli
CLI command:  cat  (plus aliases catx and cct)
```

Install from PyPI (after release):

```powershell
pip install cct-cli
```

CLI launch (after installation):

```powershell
cat --version
cat
```

Notes:

- `cat` is the canonical command. `catx` is provided for Unix systems where
  `cat` collides with GNU coreutils, and for Windows PowerShell where `cat`
  is a built-in alias for `Get-Content` (use `cat.exe` or `catx` if `cat`
  resolves to the alias in your shell).
- `cct` is kept as a historic alias so existing installs and docs keep working.
- Branding is CAT everywhere. Never install anything named `cot-ai-ide`
  (typo) — the only official PyPI distribution is `cct-cli`.
- Optional extras: `pip install "cct-cli[web]"` (Fatty CAT web server),
  `pip install "cct-cli[science]"` (calculator/graph/export features),
  `pip install "cct-cli[browser]"` (embedded browser), or
  `pip install "cct-cli[all]"` for everything.
- Requires Python 3.10 or newer (tested on 3.10–3.13).

### Option 2: Windows Installer (Native Windows experience)

Download and run the native installer:
- **`CAT-Setup.exe`** from [Latest Releases](https://github.com/kazizillani-oss/CAT_v0.7.9/releases/latest).
- Per-user installation to `%LOCALAPPDATA%\Programs\CAT` (no administrator privileges required).
- Automatically adds `cat`, `catx`, and `cct` to your `PATH` and configures PowerShell aliases cleanly.

Or via PowerShell:
```powershell
powershell -ExecutionPolicy Bypass -File installer/windows/scripts/install.ps1 -Install
```

### Option 3: Local Development / Editable Install
If you are developing or running from source:
```bash
git clone https://github.com/kazizillani-oss/CAT_v0.7.9.git
cd CAT_v0.7.9
python -m pip install -e .
cat
```

For contributors, install with test/build tooling:

```bash
pip install -e ".[web,science]"
pip install build twine pytest
python -m build
python -m twine check dist/*
```

### Option 4: VS Code Extension (v0.8.6)

Install the official **CAT — Coding Agent Terminal** extension for VS Code:
- Search `CAT CLI` or `CAT — Coding Agent Terminal` in VS Code Extensions (`Ctrl+Shift+X`).
- Marketplace: [CAT — Coding Agent Terminal](https://marketplace.visualstudio.com/items?itemName=KaziZillani.cat-cli)
- Or install the pre-packaged `.vsix`:
```bash
code --install-extension cat-cli/cat-cli-0.8.6.vsix
```

---

## 🚀 CLI Commands & Subcommands

| Command | Purpose | Automation Safety |
| :--- | :--- | :--- |
| `cat` / `catx` / `cct` | Launch the interactive CAT terminal & UI. | Interactive |
| `cat --version` / `cct --version` | Display the current installed CAT version. | **Read-Only** (Safe to automate) |
| `cat --debug` / `cct --debug` | Display detailed environment, paths, platform, and runtime debugging information. | **Read-Only** (Safe to automate) |
| `cat update --check` / `cct update --check` | Check if a newer version is available from GitHub Releases without installing. | **Read-Only** (Safe to automate) |
| `cat update` / `cct update` | State-changing update operation (disabled in public builds; prompts to use `update --check`). | **State-Changing** (Not for unattended scripts) |
| `cat rollback` / `cct rollback` | State-changing rollback to previous snapshot (disabled in public builds to prevent accidental loss). | **State-Changing** (Not for unattended scripts) |
| `cat repair` / `cct repair` | State-changing self-heal operation (disabled in public builds; prompts to use `cat --doctor`). | **State-Changing** (Not for unattended scripts) |
| `cat --doctor` / `cct --doctor` | Run diagnostic health checks across Python, terminal capabilities, and AI providers. | Interactive / Diagnostic |

> **Automation Safety Contract**:
> Read-only commands (`--version`, `--debug`, `update --check`) guarantee zero filesystem, configuration, or state mutations and are safe for CI/CD and automation scripts. State-changing commands (`update`, `rollback`, `repair`) require explicit control and will never execute silently or unattended.

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


