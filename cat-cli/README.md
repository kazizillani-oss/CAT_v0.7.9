# CAT — Coding Agent Terminal for VS Code

[![Version](https://img.shields.io/badge/version-0.8.6-blue.svg)](https://marketplace.visualstudio.com/items?itemName=KaziZillani.cat-cli)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://github.com/kazizillani-oss/CAT_v0.7.9/blob/main/LICENSE)
[![VS Code Marketplace](https://img.shields.io/badge/VS%20Code-Marketplace-blue.svg)](https://marketplace.visualstudio.com/items?itemName=KaziZillani.cat-cli)

**CAT — Coding Agent Terminal for VS Code** (also known as **CCT**) is an **AI CLI** and **AI coding assistant** for **VS Code**: an **AI coding agent** and **terminal AI** developer tool that launches the real CAT command-line AI assistant inside the VS Code integrated terminal — one click, correct workspace, zero re-implementation.

> Marketplace: [CAT — Coding Agent Terminal](https://marketplace.visualstudio.com/items?itemName=KaziZillani.cat-cli)

## Install CAT — Coding Agent Terminal for VS Code

Install **CAT — Coding Agent Terminal for VS Code** from the official Marketplace page:

**https://marketplace.visualstudio.com/items?itemName=KaziZillani.cat-cli**

Or inside VS Code:

1. Open the Extensions view (`Ctrl+Shift+X`).
2. Search for `CAT CLI` or `CAT — Coding Agent Terminal`.
3. Click **Install** on **CAT — Coding Agent Terminal** by **KaziZillani**.

From the command line:

```bash
code --install-extension KaziZillani.cat-cli
```

### Cursor / Antigravity / Windsurf (Open VSX)

These VS Code-compatible editors do **not** use the Microsoft Marketplace for extension search —
they resolve extensions through the [Open VSX Registry](https://open-vsx.org/) (or their own mirror of it).
Publishing to the Microsoft Marketplace alone does not make an extension appear in their search.

CAT is packaged so the **same** extension (`KaziZillani.cat-cli`, no fork, no rename) can be
published to Open VSX. Planned listing (pending publication — not searchable there yet):

**https://open-vsx.org/extension/KaziZillani/cat-cli**

Until the Open VSX listing is live and verified, install manually from the VSIX in those editors:

```bash
cursor --install-extension cat-cli-0.8.6.vsix
```

(or use *Extensions → … → Install from VSIX* in the editor, then reload).
Availability depends on each editor's extension registry and supported VS Code APIs —
publication to Open VSX does not automatically guarantee every editor lists or runs it.

## Install CAT CLI (GitHub Source Installation)

You also need CAT — Coding Agent Terminal itself (the extension is a launcher bridge — it runs the real terminal-based CAT CLI):

```bash
# 1. Clone CAT
git clone https://github.com/kazizillani-oss/CAT_v0.7.9.git

# 2. Enter the CAT directory
cd CAT_v0.7.9

# 3. Install CAT locally
python -m pip install -e .

# 4. Run CAT
cat
```

> **Windows PowerShell compatibility**: Windows PowerShell includes a built-in alias `cat -> Get-Content`. If typing `cat` in PowerShell prompts for `Path[0]:`, launch CAT with `cat.exe` or `python -m calc_terminal` to run the CAT executable directly without triggering PowerShell's alias.

This extension is a **launcher and integration bridge only**. CAT itself is the terminal CLI application (`calc_terminal`). Nothing is re-implemented, no fake webview UI is opened, and nothing is executed without a visible terminal showing it.

## What you get

- **No Activity Bar container in this build** — the manifest contributes no
  `viewsContainers`/`views`, so there is no CAT Activity Bar entry; CAT is
  launched via the Command Palette, editor title button, and status bar item below.
- **`CAT: Open`** in the Command Palette (also bound to <kbd>Ctrl+Alt+C</kbd>, <kbd>Ctrl+Cmd+C</kbd> on macOS).
- **Editor title action** — a CAT button on every open editor.
- **Status bar item** — a `$(terminal) CAT` shortcut in the bottom right (see `extension.js`).
- **Integrated terminal launch** — CAT runs in a terminal named `CAT`, created in the current workspace folder.
- **Terminal reuse** — clicking again focuses the existing CAT terminal instead of stacking new ones.
- **Python environment detection** — workspace `.venv` / `venv` / `env`, conda, Poetry, VS Code's selected
  interpreter, Windows `py`/`python`, macOS/Linux `python3`/`python`.
- **Human-readable failures** — missing Python or CAT produce a clear notification with
  *Install CAT · Open Documentation · Cancel*. Nothing installs without your explicit click; the install
  command is typed into a visible terminal so you can see (and edit) it before it runs.

## Requirements

- [CAT — Coding Agent Terminal](https://github.com/kazizillani-oss/CAT_v0.7.9) installed from the official repository:
  ```bash
  git clone https://github.com/kazizillani-oss/CAT_v0.7.9.git
  cd CAT_v0.7.9
  python -m pip install -e .
  cat
  ```
  If it is missing, the extension detects it and offers safe one-click setup.

## How CAT is launched

The extension resolves, in order (no invented flags — these are the repository's real entry points):

1. `cat.executable` if you set it explicitly (e.g. `"python -m calc_terminal"` or `"cat.exe"`); `{workspace}` expands to the
   current workspace folder.
2. The verified Python environment's own launcher: `…\.venv\Scripts\cat.exe`, Python's `Scripts\cat.exe`, or `cat.exe` on PATH (Windows) /
   `catx`/`cct` (macOS/Linux — bare `cat` is GNU coreutils there and is deliberately not used). On Windows PowerShell, the extension resolves
   the actual executable path or `cat.exe` rather than bare `cat` to prevent collision with PowerShell's built-in `Get-Content` alias.
3. Fallback: `<python> -m calc_terminal <workspace>` (the package's `__main__.py` entry point).

The workspace is passed as CAT's documented positional path argument (`cat <path>` opens that project), and the
terminal's `cwd` is the workspace folder, so CAT auto-detects your project either way.

## Extension Settings

| Setting | Default | Description |
| --- | --- | --- |
| `cat.executable` | `cat` | Launcher command. Bare `cat` or `cat.exe` = auto-detect; a full command string is used as-is. Supports `{workspace}`. |
| `cat.launchArguments` | `[]` | Additional arguments to pass to CAT when launching. |
| `cat.pythonPath` | `""` | Python interpreter to use. Empty = auto-detect. |
| `cat.autoDetectPython` | `true` | Auto-detect the Python environment (venv/conda/poetry/system). |
| `cat.reuseTerminal` | `true` | Reuse the existing CAT terminal instead of opening a new one per click. |
| `cat.autoStart` | `false` | Automatically start CAT when VS Code opens. |

## Commands

| Command | Title |
| --- | --- |
| `kazizillani.cat.open` | `CAT: Open` |
| `kazizillani.cat.restart` | `CAT: Restart` |
| `kazizillani.cat.close` | `CAT: Close` |
| `kazizillani.cat.checkInstallation` | `CAT: Check Installation` |

## Command-Safety & Automation Contract

When invoking or automating CAT/CCT from scripts, VS Code tasks, or external tools:

- **Read-Only (Safe to automate)**:
  - `cat --version` / `cct --version`: Current installed CAT version.
  - `cat --debug` / `cct --debug`: Deterministic runtime environment, platform, and path diagnostics.
  - `cat update --check` / `cct update --check`: Check for newer releases from GitHub without installing or modifying files.
  - Guarantees: Never modifies workspaces, configurations, PATH, or installed packages.

- **State-Changing (Unattended automation disabled)**:
  - `cat update` / `cct update`: Updates binaries and installation files.
  - `cat rollback` / `cct rollback`: Reverts workspace or version snapshots.
  - `cat repair` / `cct repair`: Self-heals configurations and file permissions.
  - In public CLI builds, state-changing commands return a clear non-zero exit code with directions to `update --check` or `--doctor` to prevent accidental unattended mutations.

## Security

- Only official VS Code APIs are used; the workbench DOM is never touched.
- No process is started in the background — CAT is visible in its terminal.
- Verification only runs `python -c "import calc_terminal"` against candidate interpreters (array argv,
  `shell: false`). Workspace files, `package.json` scripts and AI output are never executed.
- No downloads, no silent installs. Installation happens only after you click **Install CAT**.

## Release Notes

### 0.8.6

- Fixed sidebar collapse button border bleed and divider collision artifact in terminal TUI.
- Added dedicated sidebar expand toggle button when sidebar is collapsed.
- Restored iconic hero CAT ASCII art banner across normal terminal heights (>= 8 rows).
- Fixed double icon bug in permission dropdown (clean single icon + checkmarks).
- Updated core CLI version target to `0.8.ab` [final version].

### 0.8.4

- Updated all installation instructions and setup guidance to use the official GitHub repository (`https://github.com/kazizillani-oss/CAT_v0.7.9.git`).
- Removed all legacy PyPI (`cct-ai-ide`) references.
- Consistently identifies CAT as **CAT — Coding Agent Terminal**.
- Fixed Windows PowerShell compatibility: prevented execution of PowerShell's built-in `cat -> Get-Content` alias that prompted for `Path[0]:` on other devices by resolving `cat.exe` or Python module entry points.
- Improved terminal installation flow: Clone CAT, Enter CAT directory, Install CAT locally, Run CAT.

### v0.8.b (`0.8.3`)

- Marketplace discoverability: search-oriented display name, description, keywords, categories, and README.

### 0.7.9

- Rewritten as a lightweight launcher bridge: real terminal reuse, cwd-aware launching,
  Python environment detection, and safe install path.

## Development

```bash
cd cat-cli
npm install
npm run compile      # plain-JS extension: no "compile" script (pre-existing); syntax is checked via node --check / eslint
npx vsce package     # Microsoft Marketplace VSIX (do not publish unless explicitly requested)
npm run package:openvsx  # same registry-agnostic VSIX (ovsx 1.2.0 has no standalone packager; it packages implicitly during publish)
npm run publish:openvsx  # requires OVSX_PAT + claimed "KaziZillani" namespace; do NOT run until explicitly requested
```

---

MIT © [Kazi Zillani](https://github.com/kazizillani-oss)
