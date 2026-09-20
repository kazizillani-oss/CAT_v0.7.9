# Change Log

All notable changes to the "cat-cli" extension will be documented in this file.

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
