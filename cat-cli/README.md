# CAT CLI for VS Code

[![Version](https://img.shields.io/badge/version-0.7.9-blue.svg)](https://github.com/kazizillani-oss/CAT_v0.7.9)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://github.com/kazizillani-oss/CAT_v0.7.9/blob/main/LICENSE)

Launch the **real CAT terminal app** (Python + Textual) inside the VS Code integrated terminal — one click, correct workspace, zero re-implementation.

This extension is a **launcher and integration bridge only**. CAT itself is the existing `cat` command from the
[cct-ai-ide](https://pypi.org/project/cct-ai-ide/) Python package (`calc_terminal`). Nothing is re-implemented,
no fake webview UI is opened, and nothing is executed without a visible terminal showing it.

## What you get

- **CAT entry in the Activity Bar** — the CAT icon opens a small launcher view
  (Open CAT CLI · New CAT Terminal · detection status).
- **`CAT: Open CAT CLI`** in the Command Palette (also bound to <kbd>Ctrl+Alt+C</kbd>, <kbd>Ctrl+Cmd+C</kbd> on macOS).
- **Editor title action** — a CAT button on every open editor.
- **Status bar item** — a `⌨ CAT` shortcut in the bottom right.
- **Integrated terminal launch** — CAT runs in a terminal named `CAT CLI`, created in the current workspace folder.
- **Terminal reuse** — clicking again focuses the existing CAT terminal instead of stacking new ones
  (`CAT: New Terminal` forces a fresh one).
- **Python environment detection** — workspace `.venv` / `venv` / `env`, conda, Poetry, VS Code's selected
  interpreter, Windows `py`/`python`, macOS/Linux `python3`/`python`.
- **Human-readable failures** — missing Python or CAT produce a clear notification with
  *Install CAT · Open Documentation · Cancel*. Nothing installs without your explicit click; the install
  command is typed into a visible terminal so you can see (and edit) it before it runs.

## Requirements

- [CAT CLI](https://github.com/kazizillani-oss/CAT_v0.7.9) installed:
  `pip install cct-ai-ide` (or `pip install -e .` from a source checkout).
  If it is missing, the extension tells you and offers safe next steps.

## How CAT is launched

The extension resolves, in order (no invented flags — these are the repository's real entry points):

1. `cat.cli.command` if you set it explicitly (e.g. `"python -m calc_terminal"`); `{workspace}` expands to the
   current workspace folder.
2. The verified Python environment's own launcher: `…\.venv\Scripts\cat.exe`, then `cat` on PATH (Windows) /
   `catx`/`cct` (macOS/Linux — bare `cat` is GNU coreutils there and is deliberately not used).
3. Fallback: `<python> -m calc_terminal <workspace>` (the package's `__main__.py` entry point).

The workspace is passed as CAT's documented positional path argument (`cat <path>` opens that project), and the
terminal's `cwd` is the workspace folder, so CAT auto-detects your project either way.

## Extension Settings

| Setting | Default | Description |
| --- | --- | --- |
| `cat.cli.command` | `cat` | Launcher command. Bare `cat` = auto-detect; a full command string is used as-is. Supports `{workspace}`. |
| `cat.cli.pythonPath` | `""` | Python interpreter to use. Empty = auto-detect. |
| `cat.cli.autoDetectPython` | `true` | Auto-detect the Python environment (venv/conda/poetry/system). |
| `cat.cli.reuseTerminal` | `true` | Reuse the existing CAT terminal instead of opening a new one per click. |
| `cat.cli.terminalName` | `CAT CLI` | Name of the integrated terminal created for CAT. |

## Commands

| Command | Title |
| --- | --- |
| `kazizillani.cat-cli.open` | `CAT: Open CAT CLI` |
| `kazizillani.cat-cli.newTerminal` | `CAT: New Terminal` |
| `kazizillani.cat-cli.reinstall` | `CAT: Reinstall / Setup` |

## Security

- Only official VS Code APIs are used; the workbench DOM is never touched.
- No process is started in the background — CAT is visible in its terminal.
- Verification only runs `python -c "import calc_terminal"` against candidate interpreters (array argv,
  `shell: false`). Workspace files, `package.json` scripts and AI output are never executed.
- No downloads, no silent installs. Installation happens only after you click **Install CAT**.

## Release Notes

### 0.7.9

- Rewritten as a lightweight launcher bridge: commands renamed to `kazizillani.cat-cli.*`,
  webview sidebar replaced by a native tree launcher view, real terminal reuse, cwd-aware launching,
  Python environment detection, and safe install path.

## Development

```bash
cd cat-cli
npm install
npm test          # lint + unit tests + integration tests (VS Code 1.138)
npx vsce package  # build the .vsix
```

---

MIT © [Kazi Zillani](https://github.com/kazizillani-oss)
