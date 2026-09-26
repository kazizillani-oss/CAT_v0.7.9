# Change Log

All notable changes to the "cat-cli" extension will be documented in this file.

## [0.8.6] - 2026-09-24

### Fixed
- TUI & GUI Stability & Glitch Fixes:
  - Fixed sidebar collapse button border-bleed / vertical divider protrusion artifact where `cct-ctrl` styles previously forced tall borders pushing the button across the vertical boundary into the chat panel.
  - Added dedicated sidebar expand toggle in chat navigation bar when collapsed, providing smooth one-click collapse/restore and layout synchronization.
  - Fixed dashboard ASCII art downgrade: restored iconic hero CAT ASCII art banner across normal terminal heights (>= 8 rows), resolving premature reduction to 2-row mini cat face.
  - Fixed double icon glitch in permission dropdown: cleaned mode labels to eliminate duplicate indicator emojis (`🟡 🟡 Restricted` -> `🟡 Restricted`) and redundant menu row bullets.
- CLI Integration & Version Sync:
  - Updated core CLI version target to `0.8.ab` [final version].
  - Updated `.vsix` extension package to `0.8.6`.

## [0.8.5] - 2026-09-24

### Changed
- CLI Command-Safety & Automation Contract:
  - Enforced a centralized, testable boundary between read-only automation (`--version`, `-v`, `version`, `--debug`, `debug`, `update --check`) and state-changing maintenance commands (`update`, `rollback`, `repair`).
  - Read-only commands guarantee zero filesystem, configuration, or state mutation.
  - State-changing commands are explicitly classified and disabled in public CLI builds to prevent unintended unattended modifications, returning a clean non-zero exit code (1) and guiding users to `update --check` or `--doctor`.
  - Added deterministic `--debug` read-only diagnostics reporting versions, paths, platforms, and scripts.
  - Added read-only `update --check` fetching release metadata from the official repository with complete network/HTTP/format resilience.
  - Routed maintenance commands ahead of positional workspace paths to prevent directory collisions.
- Marketplace & Extensions Discovery Overhaul:
  - Added primary "AI" and "Chat" categories for top ranking in VS Code Extensions search.
  - Added top-ranking discovery keywords (copilot, deepseek, ollama, claude, gpt, chat).
  - Integrated official version and license badges.
  - Synchronized with CAT CLI v0.7.9.6 ultra-smooth 3D skeuomorphic and anti-flicker updates.

## [0.8.4] - 2026-09-23

### Changed
- Official GitHub Installation Flow:
  - Replaced all legacy PyPI commands (`pip install cct-ai-ide`, `cct-ai-ide==0.7.8.45`) with official GitHub source workflow:
    `git clone https://github.com/kazizillani-oss/CAT_v0.7.9.git`, `cd CAT_v0.7.9`, `python -m pip install -e .`, `cat`.
  - Structured the user-initiated installation flow in exact logical order:
    1. Clone CAT
    2. Enter CAT directory
    3. Install CAT locally
    4. Run CAT
  - Consistently identifies the product as **CAT — Coding Agent Terminal** across display name, notifications, output channels, and setup guidance.

### Fixed
- Windows PowerShell Compatibility:
  - Addressed PowerShell's built-in `cat -> Get-Content` alias collision that prompted for `Path[0]:`, `Path[1]:` on other Windows devices.
  - Automatically resolves `cat.exe` or `<python> -m calc_terminal` rather than bare `cat` when launching in Windows PowerShell terminals.

## [v0.8.b] (`0.8.3`) - 2026-09-21

### Changed
- Marketplace discoverability only (no functional changes):
  - Display name: "CAT CLI — AI Coding Agent & Terminal Assistant".
  - Search-oriented description, 30 relevant keywords, and categories
    (Programming Languages, Machine Learning, Data Science, Education, Other).
  - README: searchable opening section plus official Marketplace link and
    "Install CAT CLI for VS Code" instructions.
- All existing commands (`kazizillani.cat.open`, `kazizillani.cat.restart`,
  `kazizillani.cat.close`, `kazizillani.cat.checkInstallation`), settings,
  activation behavior, and UI are unchanged.
- Open VSX packaging support (no functional changes): `ovsx` devDependency plus
  `package:openvsx` / `publish:openvsx` scripts so the same `KaziZillani.cat-cli`
  VSIX can be published to Open VSX for Cursor/Antigravity/Windsurf. Not yet published.

## [0.7.9] - 2026-09-20

### Added
- First-class VS Code Workbench integration:
  - CAT activity bar container (`cat`) with monochrome CAT icon
    (`media/activity-icon.svg`).
  - CAT sidebar webview view (`cat.sidebar`) using VS Code theme
    variables and codicons — chat, agent mode, modes, provider/model
    switching, and chat history, all backed by the CAT CLI backend.
  - `cat.open` editor/title action in the `navigation` group with a CAT
    editor icon, plus a status bar entry.
- Commands: `cat.open`, `cat.newChat`, `cat.openTerminal`, `cat.runAgent`,
  `cat.settings` (all registered in `extension.js` with matching ids).
- `catBackend.js`: bridge to the existing CAT CLI FastAPI backend
  (`cat server`) — health, status, modes, chat streaming (SSE), agent,
  chats, providers, models. Cross-platform `cat` CLI resolution
  (Windows/macOS/Linux) and clear, actionable failure messaging.
- Settings: `cat.serverHost`, `cat.serverPort`, `cat.cliPath`,
  `cat.workspaceScope`.

### Fixed
- Extension previously only shipped the scaffold `helloWorld` command;
  no CAT UI was contributed and none of the declared commands worked.
- Packaging script now uses the locally installed `@vscode/vsce`.
