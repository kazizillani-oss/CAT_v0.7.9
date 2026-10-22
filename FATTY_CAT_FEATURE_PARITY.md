# Fatty Cat / CAT CLI Feature Parity & Vercel Cloud IDE Architecture

Audit date: 2026-10-22. Updated for full CAT CLI v0.8.0b1 & `cat-cli` v0.8.6 parity and Vercel Serverless deployment.

| Capability | CAT CLI (`calc_terminal`) | Fatty Cat Web & Cloud IDE | Status |
|---|---|---|---|
| Vercel Serverless Deployment | Local Python / Textual package | `vercel.json`, `api/index.py`, `app.py`, `index.py`, root `requirements.txt`, automatic `/tmp/cat_home` & `/tmp/cat_workspace` redirection on read-only serverless filesystems | **Complete** (`500 FUNCTION_INVOCATION_FAILED` resolved) |
| Core AI & Provider Selection | Shared `aicore`, provider manager, models, failover | `/api/chat`, `/api/chat/stream`, `/api/agent`, Provider & Model Center (160+ providers) | **Complete** |
| Permission Controls | CAT permission manager (`ask`/`restricted`/`full`) | `/api/permissions/*`; composer & settings controls | **Complete** |
| Modes & Custom Kitties | CLI agent modes and custom modes | `/api/modes`, `/api/modes/custom`; six core modes + custom Kitty creation | **Complete** |
| Agent Catalog & Lifecycle | 13 built-in `AgentSpec`s + custom registry, search, status, enable/disable, duplicate, run, import/export, memory | `/api/agents`, `/api/agents/search`, `/api/agents/{id}/status`, `/enable`, `/disable`, `/duplicate`, `/run`, `/export`, `/import`, `/memory` + sidebar manager | **Complete** |
| Multi-Agent Orchestration | `agents/orchestration.py` (`AgentOrchestrationEngine`) | `/api/agents/orchestrate` + UI **Team Run** (`cat-planner` → `cat-coder` → `cat-tester` → `cat-reviewer`) | **Complete** |
| Missions & Checkpoints | `cat mission` (`list`, `create`, `open`, `pause`, `resume`, `complete`, `delete`, `export`, `import`) | `/api/missions/*` + **🎯 Missions** sidebar tab | **Complete** |
| Background Task Scheduler | `cat schedule` / `cat tasks` (`list`, `add`, `run`, `pause`, `resume`, `cancel`) | `/api/schedule/*` + Scheduled Tasks manager in **🎯 Missions** tab | **Complete** |
| CAT Lab & Benchmark Studio | `cat lab`, `cat benchmark`, `cat model`, `cat dataset`, `cat experiment`, `cat hardware` | `/api/lab/overview`, `/api/lab/benchmarks`, `/api/lab/models`, `/api/lab/datasets`, `/api/lab/experiments`, `/api/lab/hardware` + **🧪 CAT Lab** Studio | **Complete** |
| Cloud IDE & Live Web Preview | Local preview server + editor | Multi-tab editor, New File/Folder, Upload, Download Workspace ZIP (`/api/workspace/{id}/download-zip`), serverless HTTP preview (`/api/preview/serve/{ws}/{path}`) | **Complete** |
| Integrated CAT CLI Terminal | Native interactive CLI & subcommands | `/api/cli/exec` + `/api/command` + **Integrated CAT CLI Terminal Drawer** (`#cct-ide-terminal-drawer`) inside Fatty Cat IDE | **Complete** |
| Storage, Backup & `.cat` Format | `cat storage`, `cat backup`, `cat restore`, `cat import`, `cat export` | `/api/storage/status`, `/api/storage/clean`, `/api/backup/create`, `/api/backup/download`, `/api/cat-file/import`, `/api/chats/import` | **Complete** |
| Integrations, Skills & Catalogue | `cat integrations`, `cat skills`, `cat commands`, `cat extensions catalogue` | `/api/integrations/*`, `/api/skills/*`, `/api/custom-commands`, `/api/extensions/catalogue` | **Complete** |
| VS Code `cat-cli` Bridge | `cat-cli/` VS Code extension (v0.8.6) | `/api/cat-cli/status` & `/api/cat-cli/vsix` download + launcher diagnostics | **Complete** |
