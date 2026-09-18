# v0.7.7 — Autonomous Development Preview

CCT grows from an AI coding assistant into an autonomous AI operating
environment. All 15 spec sections below land in this build — real
package installs, smart package research, the five-choice permission
dialog, Build-mode-only installs, automatic mode switching with visible
transitions, a visible AI execution pipeline, live todo statuses, a
task graph, the agent orchestrator, terminal automation, the
installation dashboard, automatic post-install verification, and
responsible device control.

Spec-wide rules honored everywhere below:

- Nothing that worked before this build was removed.
- Installs only ever happen through `calc_terminal/packages.py`, which
  runs the real installer of the detected package manager.
- No import/install/execute happens without permission; Restricted
  mode disables installation entirely (spec section 3).

---

## 1. Autonomous Package Manager

New `calc_terminal/packages.py` — the one place installs run.

- `parse_request()` understands `pip install requests`,
  `install numpy==1.26.0`, `npm i react`, `cargo add serde`,
  `install NodeJS`, bare `requests`, versioned pins, targets
  (`-g`, `--global`), and `--upgrade`.
- `detect_manager()` picks the right manager from known-package tables
  (Python, Node, Rust crates, Go modules, PHP, vcpkg C/C++ libs,
  system tools) or from the command's own words. Managers supported:
  `pip pipx uv conda npm pnpm yarn bun cargo go composer vcpkg
  chocolatey winget apt dnf brew` — each with a real install command
  builder and a real post-install verify command.
- `run_install()` streams honest stage events (resolving → permission
  → download → running → verifying → done/failed/skipped), streams
  live output lines from the child process, and always attempts
  post-install verification (importable / `--version` / registry
  check) with sensible fallbacks when a package can't self-report.
- `manager_available()` detects installed managers via `shutil.which`
  (honest, never fabricated) — the dashboard marks missing managers
  instead of pretending.
- Remembered decisions: `remember_decision` / `forget_decision` /
  `list_remembered` persist Allow/Deny per exact package+manager to
  `~/.cct_package_decisions.json`, so permanently-approved packages
  install without re-asking and permanently-denied ones never do.
- Entry points:
  - classic terminal: `/install <pkg>` and `cmd_install()` (with the
    full permission dialog, dashboard, summary, announce, and mode
    restore);
  - agent: the new `install_packages` tool (`_tool_install_packages`,
    with its own full flow for unknown packages: research card first,
    then approval, then install+verify);
  - Textual UI: install requests typed in chat are auto-routed to the
    pipeline turn and their permission cards appear inline.

## 2. Smart Package Research

New `calc_terminal/package_research.py`:

- `research_package()` looks up PyPI (JSON API), npm (registry API),
  and falls back to a real web search via `aicore.web_search` when
  registries are unreachable or the package is unknown.
- `alternatives_for()` compares the top known packages in a family
  (with `compare_alternatives()`), and `render_card()` renders a
  research card with recommendation, latest version, docs link, and
  alternatives — shown before ANY install of an unknown package, in
  both the classic REPL and the agent flow.

## 3. Package Install Permission (five-choice dialog)

- New permission key `install_packages` in `permissions.py`
  (`PERMISSION_DEFS`, `MUTATING_KEYS`, panel row, `/permissions`).
- Restricted mode → installation is completely disabled
  (`install_flow_state()["allow"] == False`; no code path can install
  silently).
- Full Access → temporarily narrowed to Ask Every Time for the
  duration of the install, restored automatically afterwards
  (`install_flow_state()` / `restore_mode()`, always inside a
  `try/finally` around the install).
- Ask Every Time → unchanged.
- The dialog offers exactly the spec's five choices — **Allow Once /
  Always Allow / Deny / Always Deny / Cancel** — in both UIs:
  - Textual: `PermissionCard` gained an "Always Deny" button and a
    "Cancel" button (second row), posting the new
    `PermissionDenied(remember=True)` / `PermissionCancelled` events;
    `CCTApp.on_permission_denied`/`on_permission_cancelled` relay the
    decisions to the waiting agent thread via `perm.manager.decide()`
    ("always_deny" / "cancel" both refuse; "always_deny" also records
    a session-long refusal).
  - classic: `_cli_install_permission_prompt` with the same five
    options; "Always" choices persist via the remembered-decision
    store.
- The agent's `_check_permission` special-cases `install_packages`:
  always prompts (the temporary mode narrowing), honors remembered
  allow/deny, refuses in Restricted mode.

## 4. Build Mode Integration (installs are Build work)

- `ai_modes.MODE_ORDER` is now `notebook → research → plan → build →
  debugger → agent`; the new modes ship with meta (icon, accent color,
  purpose), system prompts, `alias_for()` (`/research`, `/debug`),
  accent colors, and config entries.
- The `install_packages` tool refuses to install unless Build mode is
  active (`ai_modes.current_mode() == "build"`) and tells the user
  how to switch — the same rule the REPL's `cmd_install` enforces via
  `_ensure_build_mode()` (which auto-switches with a visible mode
  transition).

## 5. Automatic Mode Switching (visible)

New `calc_terminal/mode_detection.py`:

- `classify()` maps message text to a mode; `suggest_mode_change()`
  returns `(target_mode, transition_line)` when a switch is warranted
  (and never suggests switching out of Agent mode).
- Classic REPL: `handle_question()` runs the workflow classifier
  first (install → package manager; pipeline → pipeline; research →
  Research mode) and prints the transition panel on every auto-switch.
- Textual UI: `_route_autonomous()` runs before each turn — install
  requests auto-switch to Build mode, deep-research questions
  auto-switch to Research, big build requests go to the pipeline —
  each with a visible "Auto-switched to … mode" note and the mode
  accent repaint.
- New `/research` and `/debug` commands switch modes natively in the
  Textual UI, and appear in the command palette, footer badge cycle
  (`ai_modes.next_mode`), context-menu "Try Again" list, and the
  registry.

## 6. AI Execution Pipeline (visible workflow)

New `calc_terminal/pipeline.py`:

- `PIPELINE_STAGES`: Planner → Research → Implementation → Testing →
  Verification → Documentation → Completed, with `task_graph()`
  rendering the stage graph with the current stage marked.
- `PipelineRun` runs the whole workflow for one request: planner
  produces a step list, research runs when the request needs it,
  implementation runs the real tool-executing agent loop (with the
  permission callback), testing sandbox-runs generated code, the
  debugger pass scans for risky patterns, verification cross-checks
  the answer, and documentation writes a report. Every transition
  fires plain-Python callbacks (`on_note`, `on_stage`, `on_todo`,
  `on_message`, `on_event`).
- `sync_pipeline_todos()` pushes each stage's todo into the Todo
  Manager with real pipeline statuses.
- Entry points: `/pipeline <request>` in the classic terminal (task
  graph + stage table + live notes + final report), and the Textual
  UI auto-routes "build me a …" requests into a `_pipeline_worker`
  that streams stage lines into the chat (and publishes
  `PIPELINE_STAGE` events to the timeline).

## 7. Live Todo Status

- `calc_terminal/todos.py`: `STATUSES` expanded to
  `pending / running / researching / coding / testing / completed /
  skipped / failed` with `DONE_STATUSES`; `add_todo(status=…)`,
  `set_status()` accepts all of them, and `progress()` counts
  `DONE_STATUSES` so the completion ratio stays honest.
- The pipeline sets these statuses live via `sync_pipeline_todos()`.

## 8. Task Graph

- `task_graph()` / `render_task_graph()` in `pipeline.py` render the
  full stage graph with the current stage highlighted — shown before
  every `/pipeline` run in the classic terminal and echoed as stage
  lines in the Textual UI.

## 9. Agent Orchestrator

New `calc_terminal/orchestrator.py`:

- `SPECIALIST_ROLES` (coordinator, planner, research, coding,
  reviewer, testing, security, documentation, performance, ui,
  architecture) — `run_orchestrated()` has the Coordinator run the
  planner, conditionally insert research, run coding through the real
  agent loop, then testing/security/verification passes, streaming
  `on_agent(key, label, status, summary)` updates.
- Entry points: `/orchestrate <request>` in the classic terminal with
  a live roster log; the pipeline's own roster hooks in internally.

## 10. Terminal Automation

- `/devices terminal run '<command>'` plans, approves, and executes a
  command in your terminal, recording the outcome — via
  `device_control.TerminalProvider`, approval-gated like every other
  device action. The agent's `device_action` tool drives the same
  planner (`plan_action` / `execute_approved`).

## 11. Installation Dashboard

- `/packages` (classic terminal) and the install results panel
  (`dashboard_lines()`, `summarize()`, `announce()`) show supported
  managers with real availability dots, remembered decisions with
  per-entry forget (`/packages forget <pkg>`), and a stage-by-stage
  event timeline of every install with live child-process output.

## 12. Auto Verification

- Every install ends with `verify_package()`: import check for Python
  packages, `--version`/`--list` for runnable tools, registry lookup
  for system managers, honest fallbacks otherwise. The result panel
  and the agent's install answer both report what verification found
  (and the agent is told the verification step ran, honestly).

## 13. Modern Design Language

- New commands carry icons/colors through the existing design system:
  command palette categories (research cyan, debug red, install
  green, pipeline cyan, devices purple), thinking-status stages
  ("Debugging", "Installing Package"), and mode accents for Research
  and Debugger across header/badges/borders via `theme_css`.
- No new UI chrome was invented — everything renders through the
  existing cards, panels, badges, and conversation stream.

## 14. Centralized Command Registry

- `commands_data.py` and `registry.py` gained `/install`, `/packages`,
  `/pipeline`, `/orchestrate`, `/devices`, `/research`, `/debug` with
  descriptions, permissions (`install_packages`, `device_control`),
  AI-mode scopes, examples, and autocomplete keywords; `NATIVE_UI_COMMANDS`
  lists `/research` and `/debug` so they switch modes in-place in the
  Textual UI.

## 15. Responsible Device Control

New `calc_terminal/device_control.py`:

- `DeviceProvider` protocol with `available()`, `plan_action()`,
  `execute()`, `describe_action()`; concrete `TerminalProvider` (real)
  and `SimulationProvider` (test-only), with scaffolded Desktop /
  Android / iOS / Browser providers declared `available() == False`
  honestly (extension points via `register_provider()`).
- Every action is planned, approved (explicit user approval), and
  logged in the session activity log (`log_action`, `activity`) with
  the decision outcome — visible in `/devices`. `device_action`
  agent tool gated on the new `device_control` permission key
  (default off).

---

## Files

- new: `calc_terminal/packages.py`, `package_research.py`,
  `mode_detection.py`, `pipeline.py`, `orchestrator.py`,
  `device_control.py`
- extended: `calc_terminal/permissions.py`, `ai_modes.py`,
  `eventbus.py` (PACKAGE_INSTALLED/PACKAGE_FAILED/PIPELINE_STAGE/
  PIPELINE_COMPLETED/MODE_SWITCHED/DEVICE_ACTION), `timeline.py`,
  `todos.py`, `agent.py`, `app.py`, `config.py`
- UI: `calc_terminal/ui/app.py`, `ui/events.py`,
  `ui/permission_panel.py`, `ui/thinking.py`, `ui/context_menu.py`,
  `ui/command_palette.py`, `ui/footer.py` (no change needed — mode
  badges read `ai_modes.meta()`), `commands_data.py`, `registry.py`

## Verified

- `python -m py_compile` clean across all touched modules.
- Classic REPL: `/install`, `/packages`, `/pipeline`, `/orchestrate`,
  `/devices` dispatch, permission prompts, mode transitions.
- Textual UI: install requests and pipeline requests route through
  `_route_autonomous`; new permission buttons post the new events;
  `/research`/`/debug` switch modes in place.
- No pre-existing behavior removed.
