# CCT Architecture Review — v0.7.4 (marsEdition)

Audit of the current codebase against the CCT Vision (modular plugin-based
scientific AI OS, enterprise code quality, AI-first multi-provider, agent
orchestration). Produced 2026-07-31. All line references verified against
the shipped tree.

---

## 1. Executive summary

CCT v0.7.4 is in better shape than the version numbers suggest. It already
has the skeleton of the vision: a real multi-provider SDK, a command
registry, an event bus, a session model with forks, a permission system, an
agentic tool-loop, and a clean one-way dependency direction (`ui → backend
→ leaf utilities`). The codebase is honest — module docstrings document
known limitations and intentional duplication.

The gaps are not in *what exists* but in **two half-built generations
layered on top of each other**:

1. **A dead provider SDK.** `providers/provider_manager.py` and
   `providers/lifecycle.py` implement a modern provider abstraction
   (`chat`, `stream`, `validate_and_chat`, `validate_and_stream` — verified
   at `provider_manager.py:729,748` and `lifecycle.py:479,534,731,736`)
   that **nothing calls**. Every real chat flow goes through legacy
   `aicore.py`, which carries its own stale hardcoded provider dict
   (`aicore.py:55-87`) duplicating `providers/providers.json`.
2. **Two god-classes that cannot be tested or swapped.** `app.py` (2409
   lines, ~48 `cmd_*` methods, ~28 imports) and `ui/app.py` (1760 lines,
   policy logic embedded in the UI). Both are singletons-bound and
   zero unit-test coverage exists.

Everything else follows from these two facts.

---

## 2. What already aligns with the vision (keep, do not rebuild)

| Vision principle | Where CCT already delivers |
|---|---|
| Multi-provider AI abstraction | `providers/base_provider.py:49-54` defines `chat`/`stream`; `openai_provider.py:118,142`, `anthropic_provider.py:68,89`, `gemini_provider.py:70,91` implement it; `providers.json` drives 109 providers data-driven |
| Centralized command knowledge | `registry.py` — `CommandSpec` (30-43), categories, aliases (147-158), search (199-209), `bootstrap()` (233-253) |
| Decoupled eventing | `eventbus.py` pub/sub singleton (56-99), 13 declared topics, subscriber exception isolation (90-96) |
| Immutable conversation state | `session.py` — `Turn` with frozen `mode_snapshot` (88-89), real session fork `fork_upto` (171-190), injected summarizer (239-277) |
| Permission-gated agent actions | `permissions.py` modes ask/restricted/full (75), `agent.py` `_check_permission` with callback injection (1223-1246) |
| Lazy loading + graceful degradation | House pattern: `try: import X except ImportError` with `pip install` hints in every optional dep (solver.py:17-22, scires.py:38-48, report.py:15-25, aicore.py:20-25, sandbox.py:25-40) |
| Modular scientific functions | `solver.py`, `generators.py`, `atomsim.py`, `graphs.py`, `reactionsim.py`, `mathtext.py` are pure, state-free libraries |
| Error recovery UX | `errors.py` `error_card` with Retry/Details + honest `WIRED_INTO` audit (113-119) |
| Single-sourced UI theme | `theme.py` + `ui/theme_css.py` bridge (the only place theme → CSS vars) |
| Multi-agent design thinking | `DESIGN_multi_agent_collaboration.md` — sound Phase A/B analysis, confirm-each-step default, cost visibility |
| Safety-first execution | `security_scanner.py` AST scanning + `sandbox.py` rlimits + workspace-confined agent writes via `workspace.resolve_writable_path` (agent.py:375-744) |

---

## 3. Critical gaps (ordered by severity)

### G1 — Dead duplicate AI layer (highest priority)

The provider SDK (`provider_manager.chat/stream`, `lifecycle.validate_and_chat/
validate_and_stream`) has **zero call sites** — verified by full-tree search.
All chat flows go through `aicore.query_ai` (656-768) / `aicore.stream_ai`
(771-1002), which:
- carries its own hardcoded provider table (`aicore.py:55-87`) that *stale-
  duplicates* `providers/providers.json` (extras for openrouter/groq/ollama
  are hardcoded again),
- parses SSE with per-provider regexes (legacy style),
- while the SDK's streaming generators sit unused.

**Consequence:** two sources of truth for "how to talk to a provider". Any
new provider work (DeepSeek, GLM, Qwen, Kimi, Grok…) has to be done twice,
or the SDK is abandoned. This directly violates the vision's "one
abstraction layer".

### G2 — No dependency injection, no composition root

The codebase is module-singletons by convention: `eventbus.bus`
(eventbus.py:99), `permissions.manager` (permissions.py:193),
`registry._registry` (registry.py:256), `config._cached` (config.py:132),
`ai_modes._current` (ai_modes.py:69), theme globals (theme.py:478-483),
aicore module state. Only ~4 ad-hoc injection points exist
(`CCTApp(repl, history, stats)`, `agent.run_agent(permission_callback=...)`,
`session.summarize_older_turns(summarizer)`, `errors.error_card(retry=...)`).

**Consequence:** nothing can be tested in isolation; no way to swap a
provider strategy, mock the LLM, or run two isolated app instances
(required later for parallel agents — each needs its own session/permission
state, not shared singletons).

### G3 — God-classes in both frontends

- `app.py` (2409 lines): 48 `cmd_*` methods, ~28 top-level imports,
  dispatch is a **half-migrated hybrid** — registry dispatch covers only
  no-arg + `split_optional` commands; arg-taking commands (`/derive <t>`,
  `/bonding <m>`, `/bloch a b`) still live in the elif chain (app.py:390-427).
  Registry fields `spec.permissions` / `spec.ai_modes` are defined but
  unused.
- `ui/app.py` (1760 lines): embeds policy — mode routing ("agent mode OR
  workspace open → tool loop", 1256-1273), trigger-word permission gating
  (980-1010), AI-todo detection (1190-1207), tool-step→diff mapping
  (761-787), usage bookkeeping (1181-1183). The declared layering rule
  ("ui renders, backend decides", ui/__init__.py) is only partially true.

### G4 — No async-native AI pipeline

Agent mode is a blocking `run_agent` loop executed in a `thread(True)`
Textual worker; permission prompts block the worker on a `threading.Event`
(ui/app.py:1051-1078); agent mode cannot stream token-by-token (delivered
as one chunk, honestly documented at ui/app.py:1276-1290). The vision's
"async-first + streaming everywhere" is not met. (This is partly a Textual
limitation, but the new SDK's generators exist precisely to fix it.)

### G5 — Zero test coverage

No `tests/` directory exists; the only test artifact is the root
`test_script.py` smoke script. No pytest, no CI. The vision demands unit
tests; the pure modules (solver, mathtext, reactionsim, session,
permissions, registry, memory, todos) are trivially testable right now
with zero refactoring.

### G6 — Fragmented configuration

Eight parallel JSON stores in `~`: `.cct_config.json`, `.cct_ai_config.json`,
`.cct_theme.json`, `.cct_memory.json`, `.cct_todos.json`,
`.cct_recent_projects.json`, `.cct_providers.json`, plus package data
`providers/providers.json` + `models/model_metadata.json`. `config.py:13-16`
admits aicore/theme persistence were never migrated. The vision's "Research
Memory / Project Timeline" features need a coherent settings + data layer.

### G7 — No plugin architecture

Every module is statically imported. There is no discovery mechanism
(entry points / directory scan), no module manifest, no capability
declaration, no way to load/remove/upgrade a module at runtime. The vision's
"everything must be plugin-based" is unimplemented — this is a
pre-requisite for the Plugin Marketplace and for HPC/cloud execution backends.

### G8 — Multi-agent orchestration not built

Only a single `run_agent` loop exists, plus a `/team` mode calling
`run_multi_agent` (app.py:1681). `DESIGN_multi_agent_collaboration.md`
specifies Phase A (sequential AgentManager pipeline) — designed, not
implemented. The vision's Planner → Scientist → Reviewer orchestration
does not exist.

### G9 — Hygiene debts

- **Version drift:** `__version__ = "0.7.0"` (`__init__.py:1`), `VERSION =
  "0.7.0"` (`app.py:43`) vs. folder `v0.7.4`.
- **Dead eventbus topics:** `FILE_CREATED/DELETED/RENAMED`,
  `TERMINAL_COMMAND`, `WORKSPACE_CLOSED` declared but never published
  (eventbus.py:41-53).
- **Unwired workspace categories:** `calculations/`, `images/`, `projects/`,
  `research/` have no producers (`workspace.py:68-75` `WIRED_INTO`); the
  REPL `/research` command prints a panel but never saves its output
  (app.py:2095-2113); `code_editor` writes to `~/cct_files`, not
  workspace `scripts/`.
- **Cross-root import:** `ui/app.py:1445` imports `model.py` (a root-level
  script); the wizard belongs inside the package.
- **Windows sandbox** is timeout-only (honest, sandbox.py:25-40) — a real
  limitation for the "Local Execution" vision.

---

## 4. Migration roadmap

Ordered by (impact × risk), each phase is independently shippable and
reversible. Phases 0-2 restore engineering credibility; 3-4 unlock the
vision features.

### Phase 0 — Truth & hygiene (1-2 sessions, no behavior change)

1. Single `VERSION` source (module-level, imported by app.py / main.py /
   ui), bump to 0.7.4.
2. Delete or wire the 5 dead eventbus topics; delete dead
   `git_commit` timeline type.
3. Wire `/research` to save into `workspace.category_dir("research")`.
4. Add `pytest` + `tests/` scaffolding; land tests for the pure modules
   first (solver, mathtext, reactionsim, session, permissions, registry,
   memory, todos, workspace) — these pass with zero refactoring and start
   the regression safety net before any migration.
5. **Decision gate (G1):** either (a) retire the SDK's unused
   chat/stream/validate methods, or (b) route aicore through them. Option
   (b) is recommended — the SDK is the better design; aicore's regex-SSE
   is the legacy — but do it in Phase 2 behind a flag, not here.

### Phase 1 — Composition root & testability (core value)

1. Introduce a lightweight composition root (no framework needed — a
   `calc_terminal/core/container.py` with explicit registrations; add
   `dependency-injector` later if it proves out).
2. Convert singletons to instances owned by the container, exposed through
   compatibility shims (existing `from . import eventbus; eventbus.bus`
   stays working while internal callers migrate to injected instances).
   Priority: `permissions.manager`, `config`, `ai_modes`, then
   `session`, `memory`, `workspace` (the ones parallel agents will need
   per-instance).
3. Extract `AgentService` (owns run_agent + streaming), `ChatService`
   (owns query_ai/stream_ai), `CommandDispatcher` (owns registry dispatch +
   the remaining elif-chain commands) out of `App`; `App` becomes a thin
   REPL shell. Same for `ui/app.py`: move the four policy blocks
   (mode routing, permission gating, todo detection, diff mapping) into
   backend services with the UI calling them.
4. Add the missing `spec.permissions` / `spec.ai_modes` enforcement in the
   dispatcher (fields already exist in registry.py — finish the migration,
   then delete the remaining elif branches).

### Phase 2 — Unify the AI stack (G1 + G4)

1. Make `provider_manager.stream` / `lifecycle.validate_and_stream` the
   single chat path; implement `aicore` as a thin facade over the SDK
   (keep `aicore.query_ai` as the public API so `agent.py`, `app.py`,
   `ui/app.py`, `code_editor.py`, `model.py` don't churn in one commit).
2. Delete the stale hardcoded provider dict (`aicore.py:55-87`).
3. Convert `run_agent` to a generator that yields tool-progress events +
   tokens (`run_agent_stream`), so Agent mode streams like Notebook/Build/
   Plan modes; update `_stream_worker` to consume it. This unblocks
   cancellable agent runs (escape already cancels the worker) and live
   per-step rendering.
4. Add DeepSeek/GLM/Qwen/Kimi/Grok providers to `providers.json` +
   `model_metadata.json` as pure data (no code) — the SDK's `api_style`
   dispatch handles them.

### Phase 3 — Multi-agent orchestration (vision core)

Implement `DESIGN_multi_agent_collaboration.md` Phase A exactly as written:
- `calc_terminal/agent_manager.py` — sequential pipeline
  `[Notebook → Plan → Build → Agent → Review]`, `pause/resume/stop/status`,
  built on the proven `_begin_assistant_turn` mechanism.
- New eventbus topics `agent_step_started/finished/pipeline_completed`
  (timeline picks them up for free).
- Todo `assigned_agent` field + "run through Build agent" action
  (todos.py schema addition).
- Confirm-each-step default; cost estimate before a pipeline starts.

### Phase 4 — Plugin architecture (vision end-state)

1. Plugin manifest schema (`id`, `version`, `capabilities`, `entry_point`)
   + discovery: scan `plugins/` dir + PEP 723 entry points; registry of
   capabilities (tool contributions, command contributions, panel
   contributions).
2. Extract the first candidate modules behind the plugin interface
   (e.g. simulations, research, code execution) proving removable/
   replaceable without touching the core.
3. Per-plugin settings + storage namespaces (feeds G6's unified data layer).
4. Later: marketplace manifest, remote/cloud/HPC execution backends as
   transport plugins.

---

## 5. Suggested immediate next step

**Phase 0, items 1-4** — version truth, dead-topic cleanup, research
saving, and the initial pytest suite. It is low-risk (no behavior change),
starts the regression net, and every later phase leans on it. The pure
modules can be tested the same day with no refactoring.
