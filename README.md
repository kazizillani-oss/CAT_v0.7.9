# 🐈 Coding Agent Terminal (CAT)
<div align="center">

> **“A coding agent that keeps coding when rate limits get in the way.”**
>
> — **CAT · Coding Agent Terminal**

*Powered by Backup Providers.*

</div>
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
### A terminal-first AI coding environment for developers who live in the command line.
[![Version](https://img.shields.io/badge/version-0.8.ab-blue.svg)](https://github.com/kazizillani-oss/CAT_v0.7.9)
[![VS Code](https://img.shields.io/badge/VS%20Code-0.8.6-007ACC.svg)](https://marketplace.visualstudio.com/items?itemName=KaziZillani.cat-cli)
[![Python](https://img.shields.io/badge/Python-3.10%2B-yellow.svg)](https://www.python.org/)
[![Textual](https://img.shields.io/badge/UI-Textual-purple.svg)](https://textual.textualize.io/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](https://github.com/kazizillani-oss/CAT_v0.7.9)
[![GitHub Stars](https://img.shields.io/github/stars/kazizillani-oss/CAT_v0.7.9?style=flat)](https://github.com/kazizillani-oss/CAT_v0.7.9/stargazers)
[![GitHub Issues](https://img.shields.io/github/issues/kazizillani-oss/CAT_v0.7.9?style=flat)](https://github.com/kazizillani-oss/CAT_v0.7.9/issues)
<br>
<img width="2778" height="1284" alt="CAT Terminal Interface" src="https://github.com/user-attachments/assets/7eb60f01-fcaa-427b-ab8b-dcbfe7be4b79" />
<br>

**Terminal AI · Coding Agent · Workspace Tools · Science Utilities · Multi-Provider AI**

<br>

[🚀 Get CAT](#-installation) ·
[✨ Features](#-features) ·
[⌨️ Commands](#%EF%B8%8F-cli-commands) ·
[🧪 Testing](#-testing) ·
[📖 Documentation](#-documentation)

</div>

---

## 🐈 What is CAT?

**CAT (Coding Agent Terminal)** is a terminal-first AI development environment built for developers who want AI assistance without leaving their workspace.

CAT combines an interactive terminal UI, AI coding workflows, workspace awareness, multiple AI providers, diagnostics, developer utilities, and optional scientific-computing tools into one environment.

It is designed around a simple idea:

> **Your terminal should be a place where you can build, explore, debug, and work with AI — without unnecessary friction.**

CAT is inspired by the workflow patterns of modern AI coding tools while maintaining its own terminal-native architecture and interface.

### Built by one developer

CAT is currently developed and maintained as a **solo open-source project by Kazi Zillani**.

---

# ✨ Features

<table>
<tr>
<td width="50%">

### 🤖 AI Development

* Interactive AI coding workflows
* Multi-provider AI orchestration
* OpenAI, Anthropic, Gemini, Groq, OpenRouter, Ollama and more
* Tool execution and workspace interaction
* Backup-provider architecture
* Multiple AI operating modes

</td>
<td width="50%">

### 💻 Terminal Experience

* Fast Textual-based terminal UI
* Split-pane workspace interface
* Rich ANSI rendering
* Keyboard-first workflow
* Git/workspace detection
* Cross-platform terminal support

</td>
</tr>

<tr>
<td width="50%">

### 🧪 Science & Computation

* Symbolic formula utilities
* Scientific calculations
* 2D/3D graphing
* Physics and chemistry utilities
* Optional science extensions
* Future-ready research integrations

</td>
<td width="50%">

### 🧩 Extensibility

* `.cat` workspace/chat data
* `.catxt` extension ecosystem
* Optional browser integration
* Fomoji integration
* Modular provider architecture
* Extensible runtime system

</td>
</tr>
</table>

---

# 🚀 Installation

CAT can be used through several distribution channels.

## 1. 🐍 PyPI

> **Release status:** The `cct-cli` distribution has been built and locally validated.
> PyPI installation becomes available after the public package has been successfully published.

The package name and command are intentionally different:

```text
PyPI package → cct-cli
CLI command  → cat
Aliases      → catx / cct
```

After publication:

```powershell
pip install cct-cli
```

Then:

```powershell
cat --version
cat
```

### Optional extras

```powershell
pip install "cct-cli[web]"
pip install "cct-cli[science]"
pip install "cct-cli[browser]"
pip install "cct-cli[all]"
```

### Python requirement

```text
Python 3.10+
Tested on Python 3.10 – 3.13
```

### Command aliases

| Command | Purpose                             |
| ------- | ----------------------------------- |
| `cat`   | Canonical CAT command               |
| `catx`  | Collision-free alternative to `cat` |
| `cct`   | Legacy / compatibility alias        |

> **Windows note:** PowerShell may resolve `cat` to its built-in `Get-Content` alias. Use `cat.exe` or `catx` when necessary.

---

## 2. 🪟 Windows Installer

Download the latest Windows installer from:

**[CAT Releases](https://github.com/kazizillani-oss/CAT_v0.7.9/blob/main/cat-cli/README.md)**

The native installer is designed for per-user installation and does not require administrator privileges.

Expected installation location:

```text
%LOCALAPPDATA%\Programs\CAT
```

After installation, CAT provides:

```text
cat
catx
cct
```

---

## 3. 🛠️ Install From Source

For development or testing the latest source:

```bash
git clone https://github.com/kazizillani-oss/CAT_v0.7.9.git
cd CAT_v0.7.9

python -m pip install -e .

cat
```

### Development dependencies

```bash
pip install -e ".[web,science]"
pip install build twine pytest
```

Build the distribution:

```bash
python -m build
```

Validate the distribution:

```bash
python -m twine check dist/*
```

---

## 4. 🧩 VS Code Extension

Install **CAT — Coding Agent Terminal** from the VS Code Marketplace.

**Marketplace:**
https://marketplace.visualstudio.com/items?itemName=KaziZillani.cat-cli

Current extension release:

```text
v0.8.6
```

Or install a packaged VSIX:

```bash
code --install-extension cat-cli/cat-cli-0.8.6.vsix
```

---

# ⌨️ CLI Commands

| Command              | Description                              | Safety            |
| -------------------- | ---------------------------------------- | ----------------- |
| `cat`                | Launch CAT                               | Interactive       |
| `catx`               | Launch CAT without `cat` collision       | Interactive       |
| `cct`                | Compatibility alias                      | Interactive       |
| `cat --version`      | Show installed version                   | 🟢 Read-only      |
| `cat --debug`        | Show environment and runtime diagnostics | 🟢 Read-only      |
| `cat update --check` | Check for available updates              | 🟢 Read-only      |
| `cat --doctor`       | Run CAT health diagnostics               | 🟡 Diagnostic     |
| `cat update`         | Update CAT                               | 🔴 State-changing |
| `cat rollback`       | Roll back CAT                            | 🔴 State-changing |
| `cat repair`         | Attempt self-repair                      | 🔴 State-changing |

---

# 🛡️ Automation Safety Contract

CAT explicitly separates **inspection** from **state-changing operations**.

### 🟢 Read-only

The following commands are designed to avoid filesystem, configuration, or state mutation:

```bash
cat --version
cat --debug
cat update --check
```

These commands are suitable for:

* CI/CD checks
* environment diagnostics
* automated inspection
* debugging scripts

### 🔴 State-changing

The following operations can modify the local CAT environment:

```bash
cat update
cat rollback
cat repair
```

They require explicit control and are **not intended for silent unattended execution**.

> CAT's goal is to make the boundary between **safe inspection** and **mutation** clear to both developers and automation systems.

---

# 🧠 AI Architecture

CAT is designed around a provider-independent AI layer.

```text
                    ┌─────────────────────┐
                    │       CAT UI        │
                    │   Terminal / TUI    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │    AI Orchestrator  │
                    └──────────┬──────────┘
                               │
             ┌─────────────────┼─────────────────┐
             ▼                 ▼                 ▼
        ┌─────────┐       ┌──────────┐      ┌─────────┐
        │ Primary │       │ Backup   │      │ Local   │
        │ Provider│       │ Provider │      │ Models  │
        └─────────┘       └──────────┘      └─────────┘
             │                 │                 │
             └─────────────────┼─────────────────┘
                               ▼
                    ┌─────────────────────┐
                    │ Workspace / Tools   │
                    │ Files · Git · CLI   │
                    └─────────────────────┘
```

CAT is intentionally designed so that users are not locked into a single AI provider.

Supported provider integrations include providers such as:

* OpenAI
* Anthropic
* Google Gemini
* Groq
* OpenRouter
* Ollama
* Additional compatible providers

Provider availability can vary by release and configuration.

---

# 🔄 Backup Provider System

One of CAT's core architectural concepts is **provider fallback**.

Instead of depending entirely on a single AI service, CAT can be configured around primary and backup providers.

```text
Primary AI
    │
    ├── Available ────────► Continue
    │
    └── Unavailable
            │
            ▼
      Backup Provider
            │
            └──────────────► Continue
```

This can help reduce interruptions caused by:

* provider outages
* temporary API failures
* rate limits
* model availability
* local/remote provider differences

---

# 🖥️ Terminal Interface

CAT uses a terminal-native interface built with **Textual** and **Rich**.

The interface is designed around:

* responsive terminal layouts
* workspace navigation
* AI conversation
* code interaction
* diagnostics
* keyboard-driven workflows
* terminal-native rendering

### Design direction

```text
Minimal
   ↓
Fast
   ↓
Responsive
   ↓
Keyboard-first
   ↓
Developer-focused
```

CAT's visual identity currently follows a dark terminal aesthetic inspired by modern developer environments and the **Tokyo Night** style.

---

# 🧪 Science & Computation

CAT also includes optional computation-oriented capabilities.

Examples include:

* symbolic formulas
* scientific calculations
* graphing
* chemistry utilities
* physics utilities
* orbital/quantum visualizations
* export functionality

These capabilities are intentionally modular so the core terminal experience does not need to depend on every optional feature.

Install science functionality with:

```bash
pip install "cct-cli[science]"
```

---

# 📦 Distribution Architecture

CAT's distribution system is designed around separating public launchers from runtime components.

### Architecture goals

```text
                CAT CLI
                   │
                   ▼
          Lightweight Launcher
                   │
                   ▼
          Release Manifest
                   │
                   ▼
          Runtime Artifact
                   │
          ┌────────┴────────┐
          ▼                 ▼
       Verify            Install
       SHA-256           Runtime
```

The distribution architecture is designed to support:

* lightweight public launchers
* runtime separation
* SHA-256 verification
* controlled releases
* atomic updates
* rollback snapshots
* command collision handling

More information:

* [Distribution Architecture](docs/DISTRIBUTION.md)
* [Maintainer Releasing Guide](docs/RELEASING.md)

---

# 🧪 Testing & Verification

CAT includes release and distribution verification tooling.

### Release verification

```bash
python scripts/verify_release.py
```

### Distribution tests

```bash
python scripts/test_distribution.py
```

### Runtime builder dry run

```bash
python scripts/build_runtime.py --dry-run
```

### Package validation

```bash
python -m build
python -m twine check dist/*
```

---

# 🗂️ Project Structure

```text
CAT_v0.7.9/
│
├── .github/
│   └── workflows/
│       └── ci.yml
│
├── cat-cli/
│   └── CAT application/runtime
│
├── docs/
│   ├── DISTRIBUTION.md
│   └── RELEASING.md
│
├── scripts/
│   ├── verify_release.py
│   ├── test_distribution.py
│   └── build_runtime.py
│
├── dist/
│   └── release packages
│
├── release/
│   └── distribution metadata
│
├── setup.py
├── LICENSE
└── README.md
```

---

# 🗺️ Roadmap

CAT is evolving toward a broader developer environment while keeping the terminal as its foundation.

### Current

* [x] Terminal-first AI workflow
* [x] Multi-provider architecture
* [x] Backup provider support
* [x] Workspace tooling
* [x] Diagnostics
* [x] Science utilities
* [x] Cross-platform architecture
* [x] VS Code extension
* [x] Public `v0.8.ab` release

### Future direction

* [ ] Expanded AI provider ecosystem
* [ ] Improved coding-agent workflows
* [ ] Richer extension ecosystem
* [ ] Screen-sharing coding workflows
* [ ] Research/developer integrations
* [ ] Deeper GitHub/GitLab workflows
* [ ] Notebook and scientific-computing integrations
* [ ] Additional CAT extensions

> Roadmap items are directional and may change as development continues.

---

# 🤝 Contributing

CAT is an open-source project and contributions are welcome.

Before opening a pull request:

```bash
git clone https://github.com/kazizillani-oss/CAT_v0.7.9.git
cd CAT_v0.7.9

python -m pip install -e .
pip install pytest

pytest
```

Please keep contributions focused, reproducible, and compatible with CAT's terminal-first architecture.

---

# 🐛 Issues & Feedback

Found a bug?

Please open an issue:

**https://github.com/kazizillani-oss/CAT_v0.7.9/issues**

When reporting a problem, include:

* CAT version
* operating system
* Python version
* terminal/shell
* provider/model
* reproduction steps
* relevant error output

For diagnostic information:

```bash
cat --debug
```

---

# 📚 Documentation

| Resource                                                                                       | Description                            |
| ---------------------------------------------------------------------------------------------- | -------------------------------------- |
| [Distribution Architecture](docs/DISTRIBUTION.md)                                              | CAT packaging and runtime architecture |
| [Release Guide](docs/RELEASING.md)                                                             | Maintainer release workflow            |
| [GitHub Repository](https://github.com/kazizillani-oss/CAT_v0.7.9)                             | Source code and development            |
| [GitHub Releases](https://github.com/kazizillani-oss/CAT_v0.7.9/releases)                      | Published releases                     |
| [VS Code Marketplace](https://marketplace.visualstudio.com/items?itemName=KaziZillani.cat-cli) | CAT VS Code extension                  |

---

# 📜 License

CAT is released under the **MIT License**.

```text
MIT © Kazi Zillani
```

See [LICENSE](LICENSE) for the complete license text.

---

<div align="center">

```text
╭──────────────────────────────────────────────╮
│                                              │
│        C A T   ·   C O D I N G   A G E N T   │
│                         T E R M I N A L      │
│             Built for the terminal.          │
│            Created by kazi Zillani.          │
│             Built by one developer.          │
│                                              │
╰──────────────────────────────────────────────╯
```

### 🐈 CAT v0.8.ab

**Coding Agent Terminal**

[GitHub](https://github.com/kazizillani-oss/CAT_v0.7.9) ·
[Issues](https://github.com/kazizillani-oss/CAT_v0.7.9/issues) ·
[Releases](https://github.com/kazizillani-oss/CAT_v0.7.9/releases)

**MIT Licensed · Open Source**

</div>
