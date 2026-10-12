# Fatty Cat / CAT CLI feature parity audit

Audit date: 2026-10-09. Status is based on this checkout’s source, not product claims.

| Capability | CAT CLI today | Fatty Cat today | Gap / decision | Validation |
|---|---|---|---|---|
| Core AI and provider selection | Shared `aicore`, provider manager, models, failover | `/api/chat`, `/api/agent`, provider/model center use CAT core | Core is shared; account credentials and provider availability remain environment-dependent | Web API integration tests + provider tests |
| Permission controls | CAT permission manager and ask/restricted/full workflows | `/api/permissions/*`; composer and settings controls | Existing parity retained | Permission route tests and browser actions |
| Modes | CLI agent modes and command workflows | `/api/modes`; six web modes (`build`, `plan`, `research`, `debugger`, `agent`, `notebook`) | Modes are not the same thing as agent definitions; preserve six UI modes | `/api/modes` response and mode-switch tests |
| Agent catalog | 13 built-in `AgentSpec`s plus local custom-agent registry, CRUD/import/export/status | New `/api/agents` catalog and sidebar manager list/create/delete definitions in the shared registry | Web UI currently edits custom definition basics only; import/export, detailed editing, status, and runtime execution remain absent | Shell checks + web route CRUD tests |
| Multi-agent execution | `agent.py` team flow and `agents/orchestration.py` sequential engine | No web orchestration route found | Existing orchestration engine calls AI but has no demonstrated web tool/permission integration; do not expose as safe code-writing automation until its permission boundary is enforced | Orchestration and permission tests required |
| Workspace and files | Workspace discovery and file operations | Workspace/recent/tree/files APIs, open folder, explorer | Broad overlap; web filesystem scope still requires security tests | API tests for traversal, read/write/delete and workspace switch |
| IDE/editor | Terminal and VS Code extension workflows | Browser editor, tabs, save, formatting, file tree | Current editor is a textarea-based editor; syntax intelligence, diagnostics, diff and code navigation parity are incomplete | Browser coverage and editor-specific tests |
| Terminal and commands | Native interactive CLI, subcommands, shell commands | `/api/command`, preview service and browser workspace | Web command execution is not a persistent interactive PTY equivalent to CAT CLI | Command permission and process lifecycle tests |
| Preview/browser | Browser extras and local preview workflows | `/api/preview/*` and embedded preview frame | Local preview is present; verify supported project types and cleanup | Preview start/stop/reload tests |
| Git and GitHub | CLI includes GitHub push/publish and release update commands; capability discovery recognizes `gh`/tokens | `/api/git` and workspace Git status are local Git operations | No authenticated GitHub API/PR/issue/repo web integration found; local Git is not GitHub parity | Git route tests; OAuth/token integration tests still needed |
| Chat history | `.cat` chat storage, export/import | `/api/chats` list/create/rename/delete/export | Web exposes session operations; verify import parity | Chat persistence/export tests |
| MCP/extensions | CLI integration and extension management | MCP server and extension APIs + UI | Existing local management paths; broad compatibility needs integration tests | MCP/extension API tests |
| Backup and recovery | CLI backup/restore commands | Backup-provider API and settings | Web provider configuration exists; full restore/recovery flow not verified | Backup round-trip test |
| Planner/activity | CLI missions and agent planner; activity bus | Activity stream/summary and planner mode | No task calendar, scheduling, or planner persistence interface found | Activity tests; planner/calendar feature tests required |
| Sharing/collaboration | No verified general web share flow | No share API routes found | Not implemented in web app | Authenticated sharing tests required |
| Cross-device | Local CLI and optional services | Browser app served by the local CAT web process | No synchronized hosted service or device pairing workflow found | Multi-device deployment/integration tests required |
| Appearance/navigation | Terminal themes | Named CAT palettes; now separate System/Light/Dark choice, responsive rail/drawer | New appearance preference is browser-local; palettes remain CAT theme API-backed | JS checks + manual browser responsive/theme QA |
| SDK | Python package exposes CAT modules/CLI entry points | No distinct Fatty Cat SDK surface found | No separately versioned web SDK/API contract found | SDK contract tests required |

## Source anchors

- CLI overview and commands: `README.md`, `calc_terminal/cli.py`, `calc_terminal/cli_commands.py`.
- Web routes: `CAT_v0.7.4/calc_terminal/web/server.py`.
- Shared agent model/registry/engine: `CAT_v0.7.4/calc_terminal/agents/agent_model.py`, `registry.py`, and `orchestration.py`.
- Web client and interface: `CAT_v0.7.4/calc_terminal/web/static/index.html`, `js/app.js`, `css/app.css`.

This redesign intentionally keeps the existing CAT API-backed features and labels missing integrations as missing. In particular, it does not present local Git as GitHub OAuth, a planner mode as a calendar, or sequential model passes as permission-safe code-writing collaboration.
