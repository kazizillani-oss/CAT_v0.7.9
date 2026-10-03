# FATTY CAT OS — architecture and redesign plan

## Product rule

FATTY CAT is a visual workspace over CAT Core. The web client must call the same runtime, command, provider, permission, and workspace services as CAT CLI. It must not maintain its own provider catalog, agent executor, credential store, or command semantics.

```text
FATTY CAT web ─┐
               ├─ CAT web API / CAT Runtime ─ CAT Core ─ Provider Fabric ─ models
CAT CLI ───────┘                       ├──── permissions / tools / workspace
                                       ├──── modes / agent loop / failover
Fomoji identity ──────────────────────┴──── authentication state
```

## Existing implementation map

| Capability | Existing source of truth | Web integration |
| --- | --- | --- |
| CLI commands | `commands_data.py`, CAT command handlers | `/api/commands`, `/api/command/dispatch`, `web/cat_runtime.py` |
| Chat and streaming | `aicore.py`, `ai_modes.py` | `/api/chat`, `/api/chat/stream`, `/api/agent`; `web/cat_runtime.py` |
| Default modes / custom Kitties | `ai_modes.py` and mode registry | `/api/modes`, `/api/modes/switch`, `/api/modes/custom` |
| Providers and models | `providers/providers.json`, `models/manager.py`, `providers/provider_manager.py` | `/api/providers/center`, `/api/models`, `/api/models/switch` |
| Backup chain and failover | `providers/provider_manager.py`, `aicore.py`, `resilience/failover_engine.py` | `/api/backup-providers`; stream events include failover callbacks |
| Workspace and editor | `workspace.py`, `projects.py`, CAT workspace services | `/api/workspace/*`, `/api/file`, `/api/command` |
| Activities | CAT event bus and activity store | `/api/activities`, `/api/events/stream` |
| MCP and extensions | CAT `mcp` and `extensions` modules | `/api/mcp/*`, `/api/extensions/*` |
| Identity | `fomoji_auth.py`; Fomoji server/connector | `/api/auth/status`, `/api/auth/logout`, profile API |
| Science / notebooks | CAT science and session notebook modules | `/api/science/*`, `/api/session/notebooks/*` |

The bundled provider registry currently contains **162 providers**. Keep the count catalog-derived in UI. Do not describe it as 166+ until the shared CAT catalog actually reaches that size.

## Current redesign work

- Reworked the home screen into a focused workspace landing page with a custom, lightweight CSS Kitty mark, live CAT provider/mode state, workspace actions, recents, and Kitty cards.
- Made home Kitty cards render from `/api/modes`, so user-created modes appear without maintaining a second hard-coded list.
- Added real Fomoji connection-state display and browser device authorization. The web app reuses CAT's existing Fomoji device protocol and protected token store; raw connector tokens never enter the browser.
- Added keyboard-operable navigation and a narrow-screen workspace drawer. Motion follows `prefers-reduced-motion`; pointer parallax is frame-throttled and limited to the home illustration.
- The web shell continues to use CAT Runtime and existing API routes. Provider metadata remains sourced from CAT's catalog.

## Migration sequence

1. **Web shell and navigation:** establish the new responsive design system while retaining existing action handlers and server-backed menus.
2. **Workflow reliability:** audit each visible control against API routes; add real loading, empty, offline, and actionable error states.
3. **Kitty lifecycle:** evolve custom modes into persisted agents with tools, permission sets, model preferences, memory, and task state. The current custom-mode API stores identity and system instructions only; it is not yet a full agent builder.
4. **Provider UX:** continue using CAT's provider/model managers; surface actual status and the existing configured failover chain. Keep secrets out of rendered DOM and logs.
5. **IDE and documents:** connect the web editor and preview to CAT file services; integrate registered CAT viewers for PDF, DOCX, and other supported formats.
6. **Fomoji identity:** the browser device flow now reuses CAT's existing pairing protocol. Further work should formalize a public auth service API and exercise approval, denial, expiry, and server-offline paths end-to-end.
7. **Quantum and benchmarks:** expose CAT science/benchmark engines where APIs exist. Quantum backends and unsupported web workflows must stay labeled Experimental or Backend Required.
8. **Verification:** exercise CLI command parity, provider fallback, modes, auth, workspace safety, responsive layouts, reduced motion, and accessibility before calling the redesign complete.

## Explicit current gaps

- The custom Kitty web form presently maps to CAT custom modes: name, icon, accent, purpose, and system prompt. Tools, permissions, preferred/backup providers, memory policy, and independent task graphs need a shared CAT data model before the UI can truthfully offer them.
- Fomoji currently authenticates the local CAT installation. A multi-user hosted Fatty Cat deployment still needs a separate server-session and tenant authorization model.
- CAT has file viewers, benchmarks, and science modules, but the web API does not currently expose a complete document viewer, benchmark studio, or quantum-circuit backend.
- The integrated web code editor is a lightweight editor surface. It does not yet provide IDE-grade language services, diagnostics, or robust multi-file diffs.

These gaps are product work items, not simulated features. Keep controls hidden or visibly marked until their backing workflow exists.
