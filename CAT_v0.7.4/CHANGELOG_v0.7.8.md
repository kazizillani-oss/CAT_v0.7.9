# v0.7.8 — Professional IDE Experience

The v0.7.8 build turns CCT's remaining single-provider / placeholder
gaps into real, working IDE features — without removing a single thing
that worked in v0.7.7:

- Backup Providers: a real failover chain that keeps conversations
  alive when the primary provider quota-times out or errors.
- MCP Servers: a real Model Context Protocol client (JSON-RPC 2.0) for
  local stdio and remote HTTP servers, with a live status panel.
- AI Personalization: named profiles with tone, temperature and style
  rules merged into every system prompt.
- A redesigned Attach panel, a Settings Center with an Integrations
  section, a Workspace Menu, a one-time Welcome modal, per-mode
  gradient badges, and editor upgrades (word wrap + live preview).
- Honest bug fixes: sidebar "Recent Workspaces" terminology, the
  stale version string in the UI, and the re-open-folder UX.

Backward compatibility: all v0.7.7 and earlier behavior is unchanged;
every new feature defaults to off or unobtrusive.

---

## 1. Backup Providers — Failover Chain

`calc_terminal/aicore.py` was rewritten so `query_ai()` and
`stream_ai()` are no longer single-provider one-shots:

- `_query_ai_once` / `_stream_once` handle one provider attempt.
- `_should_failover(status, error, attempts)` decides whether a failed
  attempt is worth a backup (HTTP 401/403/429, 5xx, timeouts and
  network errors qualify; a cancelled stream never does).
- `_backup_chain()` walks the saved backup provider configs in order
  and stops at the first one that answers; each backup used is marked
  via `provider_manager.mark_backup_used()` so the panel can show
  honest "used on 2026-…" history.
- `set_failover_hook()` lets the UI learn when a failover happened
  (the app shows a system note, e.g. "primary provider timed out —
  answered by backup Anthropic").

New `calc_terminal/providers/provider_manager.py` API:
`load_backup_providers()` / `save_backup_providers()` (JSON dotfile),
`backup_configs()`, `mark_backup_used()`.

UI: `calc_terminal/ui/backup_panel.py` — a real panel (Main Menu →
Backup Providers) listing each backup in order with kind/name, a
status dot, and the "used" badge; Add / Remove / Move Up / Move Down /
Test (live ping) / Save / Apply / Cancel. The chain only engages
through the normal AI flow — nothing changes when no backups are
configured.

## 2. MCP Servers — Real Client + Panel

New `calc_terminal/mcp.py` — a genuine Model Context Protocol client
(JSON-RPC 2.0, protocol version 2024-11-05):

- `_LocalTransport` spawns a server as a child process and speaks
  stdio JSON-RPC (for Claude-Code-style local servers).
- `_RemoteTransport` posts JSON-RPC over HTTP(S) (for remote MCP
  servers).
- `McpSession` handles connect / disconnect / `tools/list` /
  `tools/call`, and reports the server's negotiated protocol version,
  measured latency and its real tool list.
- Persistence in `~/.cct_mcp_servers.json`; `get_session()` /
  `connect_server()` / `server_status()` are the panel's API.

UI: `calc_terminal/ui/mcp_panel.py` — Main Menu → MCP Servers: a live
row per server (name · kind · status/version · latency · tool count),
Connect (background thread, status updated via `call_from_thread`),
Add (with Remote / Local toggle), Remove. Connection failures surface
as honest per-row error text, never a crash.

## 3. AI Personalization

New `calc_terminal/ai_personalization.py` — profiles stored in
`~/.cct_profiles.json`:

- Five built-in tones (`balanced` / `concise` / `detailed` / `playful`
  / `formal`), each mapped to a directive and a temperature hint.
- `personalize_system_prompt()` appends a `<Personal style>` block to
  any system prompt; `request_config()` returns a temperature (and
  model) override for the active profile.
- CRUD + `set_active()`; escape hatch env var `CCT_DISABLE_PERSONALIZATION`
  turns it all off.
- Integrated at both AI call sites: `ai_modes.system_prompt_for()`
  and `agent.run_agent()`; the UI's streaming worker merges the
  profile temperature into a copy of the live config before each
  request — the stored config file is never rewritten.

UI: `calc_terminal/ui/personalization_panel.py` (Main Menu → Customize
AI) — profile list, tone picker, temperature / model / extra rules
fields, New / Duplicate / Delete / Set Active / Save.

## 4. Attach Panel Redesign

`calc_terminal/ui/attach_panel.py` was rebuilt (behavior preserved,
looks extended):

- Tool cards: File / Folder / Recent, with a path entry that validates
  live — shows the real kind, size and an honest AI-stage badge
  (Plan / Research / Build / Verify) for what the attachment will be
  used for.
- Recent mode lists actual recently attached paths with multi-pick.
- `attachments.py` `AttachmentBar.add_file()` now renders icon + kind
  + size chips; the recents list is updated from `app.py`
  (`_recent_attachments`).

## 5. Settings Center + Integrations

`calc_terminal/ui/nav_screens.py` `SettingsPanel` grew two sections:

- Personalization → opens the AI Personalization panel.
- Integrations → Backup Providers and MCP Servers.

The theme list now comes from `theme.theme_names()` (the single
palette source) instead of a second hardcoded dark/light pair, and the
panel's live values include the active profile name and the counts of
configured backups/MCP servers.

## 6. Workspace Menu + Folder-Reopen Fix

`calc_terminal/ui/header.py` `NAV_ITEMS` gained a Workspace menu:

- New Workspace — creates `~/cct_workspace/cct-workspace-<timestamp>`
  and opens it.
- Save Workspace — records the current folder in recent history.
- Close Workspace — collapses the Explorer, clears the active project,
  returns to the dashboard (nothing on disk is touched).

The reported reopen bug: clicking Open Folder on the folder that's
already open rebuilt the whole shell. Fixed — `_open_folder` now
recognizes the same folder, just re-indexes, and keeps the same
WorkspaceShell instance.

## 7. Welcome Modal

`calc_terminal/ui/welcome_modal.py` — a one-time "What's new in
v0.7.8" screen with a dismissible highlights list (backup failover,
MCP client, personalization, attach redesign, settings center,
workspace menu). Persisted once per version via `~/.cct_welcome_seen`
(integer-tuple comparison, so future 0.7.x/0.8.x versions re-show
correctly); any dismissal marks the version seen. Shown after the
first frames settle in `CCTApp.on_mount` so it never races the
dashboard.

## 8. Per-Mode Gradient Badges + Unified Theme Source

- `theme.py`: `available_themes()`, `theme_names()`, `theme_label()`,
  `is_light()`, `blend()`; rebuilt light palette; `ai_modes.gradient()`
  returns each mode's gradient; `theme_css.py` exposes
  `accent-gradient-start/end` and `gradient_hex()`.
- `footer.py` `_mode_badge_markup()` renders the active AI mode as a
  four-segment gradient bar (`▮▮▮▮`) blended per mode, icon in start
  color, label in end color (local `_hex_blend` helper — `theme.blend`
  stays RGB-tuple based).

## 9. Bug Fixes

- Sidebar terminology unified: "Pinned/Recent Projects" →
  "Pinned/Recent Workspaces" (matching the Main Menu's "Recent
  Workspaces"), including the clear-recent confirm dialog
  (`sidebar.py`).
- The UI version string was stale: it read `repl.VERSION`, but the
  classic `App` never exposed it, so the header/status/about showed a
  hardcoded `0.7.0`. `App.VERSION/EDITION` are now real class
  attributes and `CCTApp._version()` falls back to
  `calc_terminal.app.VERSION`.
- JSON-protocol leakage in agent responses: `clean_final_text()` (+
  `_balanced_json_spans`, `_extract_protocol_text`, `_is_protocol_blob`)
  strips tool-call JSON blobs from the final answer and is applied in
  `app.py.on_message_finished`.
- Every cancel button in the new panels and dialogs was re-verified
  wired (Escape / Cancel / outside-click all dismiss; nothing
  dead-ends).

## 10. Editor Upgrades

`calc_terminal/ui/editor.py`:

- **Word wrap** — the toolbar's `Wrap: On/Off` pill flips the active
  TextArea's real `soft_wrap` (code_editor areas default to off).
- **Live Preview** — the toolbar's `Preview` pill toggles a bottom
  split that renders Markdown live via Rich's Markdown renderer
  (updates on every keystroke); non-Markdown tabs get an honest
  "renders Markdown files" note instead of fake output. Layout stays
  full-screen when both are off.

## 11. Version Bump

- `VERSION = "0.7.8"`, `EDITION = "Professional IDE Experience"`
  (`calc_terminal/app.py`), visible in the classic banner, the UI
  header/status line and `/about`.

---

## Files

- new: `calc_terminal/mcp.py`, `calc_terminal/ai_personalization.py`,
  `calc_terminal/ui/backup_panel.py`, `calc_terminal/ui/mcp_panel.py`,
  `calc_terminal/ui/personalization_panel.py`,
  `calc_terminal/ui/welcome_modal.py`
- rebuilt: `calc_terminal/aicore.py` (failover),
  `calc_terminal/ui/attach_panel.py`
- extended: `calc_terminal/providers/provider_manager.py`,
  `calc_terminal/ai_modes.py`, `calc_terminal/theme.py`,
  `calc_terminal/ui/theme_css.py`, `calc_terminal/ui/footer.py`,
  `calc_terminal/ui/header.py` (nav), `calc_terminal/ui/nav_screens.py`
  (Settings Center), `calc_terminal/ui/sidebar.py` (terminology),
  `calc_terminal/ui/editor.py` (wrap + preview), `calc_terminal/app.py`
  (version), `calc_terminal/ui/app.py` (wiring, version fallback,
  welcome modal, workspace menu, recents)

## Verified

- `python -m py_compile` clean across all touched modules.
- Pilot tests: all four new panels open from the Main Menu and
  Escape-closes; attach flow adds chips and populates recents;
  backup-provider config round-trips and mocked failover switches
  providers; MCP server add/status/connect(fails cleanly)/remove;
  personalization directive + temperature merge; editor wrap toggle
  and markdown preview; welcome modal shows once then stays hidden;
  workspace new/save/close/reopen-keeps-same-shell.
- No pre-existing behavior removed; no new dependencies.
