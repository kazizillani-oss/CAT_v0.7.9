# CHANGELOG — CAT v0.7.9.0

**UI / Workspace / Agent Animation / Layout Overhaul**

The application is now branded **CAT (Coding Agent Terminal) v0.7.9.0**
(formerly CCT). This release is three architectural fixes plus the
rebrand: real-time filesystem sync for the File Explorer, a real
split-pane layout with two independent resizable areas, and a CAT Agent
ASCII activity animation driven by actual backend agent state.

---

## 0-octies. HOTFIX — goodbye duplication root cause + CAT CLI terminal identity

### Root cause of the duplicated/corrupted goodbye art

The renderer replaced animation frames with RELATIVE cursor-up moves.
Relative moves assume every printed line occupied exactly one row — but
any line wider than the terminal (center-padding, farewell bars at
narrow widths) WRAPS and silently consumes extra rows. Each frame then
rewound to the wrong place, leaving compounded residue that looked like
"GOOD BYE / GOOD BYE", "CAT / CAT", or giant stacked garbage.

**Fix — wrap-proof single-render pipeline** (`goodbye.py` rewritten):

* No width-based center padding anywhere: art is left-aligned at a
  fixed 2-column indent, so no drawn line can ever exceed its natural
  block width (≤ 34 cells) → wrapping is impossible by construction,
  and cursor-up replacement is always exact.
* Responsive sizing BEFORE drawing: full GOOD BYE block needs ≥ 38
  cols; CAT logo full ≥ 30 / compact half-block ≥ 20 / wordmark below;
  rules and bars clipped to width−1.
* `\x1b[2J\x1b[H` screen clear before the composition so stale Textual
  output can never share the region with the goodbye.
* Exactly one CAT artwork, one GOOD BYE caption, one farewell line in
  the final frame (probe-counted).
* Farewell is generated exactly ONCE per shutdown (cached by
  shutdown_session, passed into the renderer).
* Idempotency re-verified: two exit commands back-to-back render once.

### CAT CLI terminal identity (new centralized title owner)

* `theme.set_terminal_title()` / `set_terminal_title_state()` /
  `restore_terminal_title()` — the ONLY place OSC-0 sequences are
  emitted. Windows Terminal / PowerShell 7 / conhost understand them;
  dumb/piped output is a silent no-op (never prints raw escapes).
* Lifecycle: `cli.bootstrap` sets **"CAT CLI — Starting"**; UI mount
  flips to **"CAT CLI — Ready"**; streaming flips to **Running**;
  `shutdown_session` sets **Exiting**, then pops the xterm title stack
  (`ESC[22t`/`23t`) so PowerShell/CMD get their own label back after
  CAT exits.

### Branding

CLI usage banner now reads "CAT CLI v0.7.9.0"; window title uses the
same identity across Starting/Ready/Running/Exiting states.

**Verification** — `_probe_goodbye.py` extended to **24/24**: wrap-proof
assertions at widths 36 and 80 (no line exceeds the terminal), final-
frame element counts (1 art / 1 caption / 1 farewell), rewind count,
screen-clear presence, idempotency, AI success/hang/error paths, and
title sequence emission/restore/no-op-on-pipe. Startup probe fixed to
wait for the modal's first paint; all other suites still green.

---

## 0-septies. UNIFIED ANIMATED GOODBYE — one shutdown flow, every exit

New `calc_terminal/goodbye.py`. Every normal exit path now routes
through ONE idempotent handler:

```
Ctrl+Q (Textual) · /quit · /exit · EOF · task/session completion
    ↓ shutdown_session(...)            ← idempotent (lock-guarded)
    ↓ generate_session_message(...)    ← shared AI farewell generator
    ↓ render_goodbye(...)              ← animated sequence
    ↓ cleanup (reset SGR · cursor visible · flush)
```

* **Sequence** (~1.3 s animated): small `( o.o )` cat face → the app's
  own CAT block logo with a 6-frame gradient sweep → a matching
  ANSI-shadow **GOOD BYE** block with reverse-direction gradient →
  literal `G O O D   B Y E` caption → farewell line under "CAT AI" →
  session notes. Sessions that completed work use the
  `✓ Task completed` variant header.
* **Shared AI farewell** (`generate_session_message`): routes through
  `aicore.query_ai` — the same provider + backup-failover machinery
  every Textual reply uses — on a daemon thread with a hard ~2.5 s
  join timeout. Success → dynamic line; hang/timeout/error signature/
  no-provider → deterministic local fallback
  ("Session ended successfully. Goodbye from CAT CLI. 🐾").
  Shutdown NEVER blocks on the network and NEVER fails because of AI.
* **Gradient**: per-character theme gradients sweeping between the
  active palette's stops (dark = Tokyo Night pastels; light = its
  darker readable accents). No flashing — smooth phase-shifted frames.
* **Fallbacks**: `NO_COLOR`, `TERM=dumb`, or piped output get a clean,
  fully-readable static composition with zero escape-sequence litter;
  SGR-reset/cursor-show cleanup is TTY-gated for the same reason.
* **Idempotent**: `/quit` pressed right after Ctrl+Q renders nothing
  twice (probe asserts render count == 1 across both invocations).
* **Wiring**: classic REPL `cmd_exit` (covers `/exit` `/quit` `exit`
  `quit` EOF Ctrl+C-at-prompt) and the Textual UI exit path in
  `cli.bootstrap` both call it; reason='task' when the session actually
  completed work.

**Verification** — `_probe_goodbye.py` (14/14): static/animated
composition, gradient frame counts, timing bound (<3 s), cleanup
escapes, AI success/hang/error-signature paths, idempotency, and both
classic exit commands funneling through the single handler. Full
regression sweep still green.

---

## 0-sexies. HOTFIX — launching `cat` from C:\WINDOWS\System32 crashed

**Reported:** `PS C:\WINDOWS\System32> cat` died during startup with
`PermissionError [WinError 5]: 'C:\WINDOWS\System32\simulations'`
inside WelcomeDashboard.compose → workspace.summary → category_dir →
os.makedirs.

**Root causes, all fixed:**

1. **Generated-file directories were created eagerly inside whatever
   directory the shell happened to be in.** PowerShell's default cwd is
   System32 (unwritable), and `workspace.root_dir()`/`category_dir()`
   let `os.makedirs` raise straight through into the dashboard's
   compose. Directory creation is now best-effort: an unwritable root
   degrades to "no generated files yet" instead of killing the app
   (`root_dir`, `category_dir`, `list_category`, `summary` all guarded;
   write tools still fail honestly per-operation if actually used).
2. **Protected-root detection was case-sensitive.** `_BLOCKED_ROOTS`
   lists `C:\Windows`, but the real directory is `C:\WINDOWS` — so
   every startswith() block silently missed it (this also weakened the
   agent write-tool guard!). All protected-path comparisons now go
   through `_norm_ci()` (normcase + normpath): detection refuses
   System32 in any casing, and `resolve_writable_path` blocks it too.
3. **Workspace auto-detection could adopt the protected cwd.**
   `detect_workspace` now filters candidates through the protected-root
   check and falls through to the last opened project instead; a new
   `projects.forget_protected()` purges any bad recent/pinned entries
   recorded by earlier launches (runs once at UI startup).
4. **Startup order**: workspace auto-detection now runs BEFORE the
   dashboard composes, so its generated-files column reads the real
   project on first paint.
5. **Defense-in-depth**: `WelcomeDashboard.compose` wraps all data
   collection (recent projects, generated-file summary, workspace
   stats) in per-section guards — no filesystem failure can ever again
   take down the startup screen.
6. Polish: the `[CAT DEBUG]` launch prints are gated behind
   `CAT_DEBUG=1` (they appeared on every normal start).

**Verification** — `_probe_system32_launch.py` (8/8): injected
makedirs-PermissionError survives summary/list_category;
detect_workspace never adopts System32 (case-insensitive); full
headless launch WITH cwd=System32 composes the dashboard, workspace
root resolves to the real project, AI STATUS renders, nothing is
written into System32; plus 4 new unit tests in test_v079_speed.py
(34 total, OK) and every prior probe/suite still green.

---

## 0-quinquies. STARTUP FLOW — Welcome Screen → Dashboard, every launch

Startup behavior is now centralized and consistently branded.

### One bootstrap (`calc_terminal/cli.py::bootstrap`)

* `python main.py`, the installed **`cct`**/**`cat`** console scripts,
  `python -m calc_terminal`, and the model-wizard's finish path ALL
  funnel through one function (the old `_launch` kept as an alias), so
  no entry point can start a bare REPL/backend while skipping the UI.
* Failure handling: a UI crash/unavailability prints a clear CAT CLI
  message AND logs to `~/.cct_startup.log`; the classic terminal is a
  safe fallback used only when the UI genuinely cannot run.

### Startup sequence (every fresh application launch)

```
Launch → Welcome Screen (pulsing CAT block art + staged boot bar)
       → auto-continues (~0.9 s after "✓ CAT ready"; any key/click skips)
       → Dashboard (primary startup screen, already live underneath)
       → ready for AI interaction
```

* The Welcome modal is no longer once-per-version — it plays on every
  fresh launch per spec, then hands off smoothly into the Dashboard.
* The Dashboard itself now opens with the LARGE CAT BLOCK-ART HERO
  (mode-gradient tint, darkened for light mode) + version + tagline +
  mode-aware ready line + quick actions + real-data columns — the same
  branded centerpiece composition, promoted to the primary screen.
  Responsive: full art → compact half-block → wordmark as the pane
  narrows; re-picked on resize; never overflows.
* `/clear` and New Chat Session restore this dashboard home.
* Duplicate prevention: if the dashboard is already visible it is
  updated IN PLACE — model starts/reloads/provider changes never open
  another welcome screen or second dashboard (object identity verified
  by probe).

### AI STATUS lives inside the Dashboard

New live line: `● AI STATUS — <provider> <model> · Ready` (or
`○ not configured · run /model`). It updates in place: Working… while
a request streams, Ready when done, recomputed after /model or provider
selection — satisfying 'model status appears inside Dashboard' without
any duplicate UI.

### Verification

* `_probe_startup_flow.py` (17/17): welcome-first ordering, CAT art +
  boot bar on the modal, auto-continue, dashboard composition, model
  start/reload reusing the SAME instance, chat hand-off, /clear
  restore, single-instance guarantee, centralized-bootstrap checks.
* All prior suites still green (empty-state 19/19 incl. new AI STATUS
  check, light-mode 21/21, animation/layout/drag/final probes, unit
  tests 30+77+29, formats, fixes).

---

## 0-quater. LIGHT-MODE UI AUDIT — highlighting removed, contrast fixed

A full light-theme pass over every surface. Dark mode is untouched
except where a shared component bug (below) required one fix.

### Root causes found and fixed

* **Textual's built-in component defaults are dark-mode values** —
  `#E0E0E0` button labels, `b reverse` (full inverted block) button
  focus, near-white selection foregrounds, `#E0E0E099` markdown
  headings. In dark these were masked by our own rules; in light they
  leaked through as washed-out labels, glowing selection/focus blocks,
  and invisible heading text.
  Fix: `theme_css.css_variables()` now emits an explicit, contrast-
  correct family of component variables WHEN THE ACTIVE THEME IS LIGHT
  ONLY (dark emits nothing → byte-for-byte unchanged):
  solid subtle selection washes (`#b9d7f8` inputs / `#b3d4fc` screen)
  with dark text, visible cursors, dark button labels, bold-not-
  reverse focus, readable markdown headings, footer key caps, blurred
  borders.
* **Hardcoded Tokyo-Night hex colors in Rich markup** — thinking-stage
  spinner/status colors, command-palette icon colors and the response-
  complete ✓ were fixed pastels (#7aa2f7/#9ece6a/#e0af68/#c0caf5…),
  several below 2:1 contrast on white. All now resolve through ONE new
  semantic role system, `theme.role_hex(role)`, against the CURRENT
  palette at call time: dark keeps its exact values, light gets darker
  WCAG-readable ones. Verified programmatically: every stage/palette
  color ≥3:1 on its theme's surface (history's intentionally muted
  gray excepted by design).
* **The code editor was a hard-coded dark block** — Tokyo Night
  styles (near-black bg, pale selection) applied unconditionally, so
  opening any file in light mode dropped a dark rectangle into the UI.
  New matching GitHub-Light editor palette (white base, #F6F8FA gutter/
  cursor-line, soft #B6D7FF selection that keeps syntax colors, clearly
  visible cursor) selected via `_apply_editor_theme()`; `EditorPane.
  retheme()` re-applies it to all OPEN tabs on a theme switch.
* **Theme switching was incomplete** — /theme, Settings Center and the
  Themes panel each re-painted CSS only; open editor tabs and chat
  bubbles kept the PREVIOUS theme (dark code fences stayed in light).
  One centralized `CCTApp._apply_theme_switch()` now repaints CSS +
  header + open editor tabs + every existing bubble (Markdown pygments
  material ↔ friendly) + the empty-state centerpiece.
* **User bubble label contrast** — white label text on lighter mode
  accents (Notebook blue / Build amber) measured ~2:1 in light mode;
  the freeze step now picks black/white per WCAG luminance of the
  accent, LIGHT MODE ONLY (dark look preserved).
* **Empty-state word art** — mode-gradient end stops tuned for dark
  surfaces washed out on white; light mode blends each line ~25%
  toward black first. Art stays centered/clean and never inherits
  selection backgrounds (it renders as plain styled text, no input
  widget underneath).
* **Button focus blocks (shared fix)** — Textual's default `b reverse`
  focus style painted a large bright block over focused buttons; the
  shared Button:focus rule now forces plain bold (active border already
  marks focus). This is the one change that also touches dark mode, as
  the spec permits for shared-component bugs.

### Verification — `_probe_light_mode.py` (21/21)

WCAG contrast math over both themes' stage/palette/summary colors,
variable-emission assertions for light AND absence-assertions for dark,
editor palette identity per theme, and a live headless round-trip
(light → dark → light) confirming CSS variables follow immediately,
bubbles survive, and no component keeps stale styling.

---

## 0-ter. Startup Chat Centerpiece — `CATChatEmptyState`

The main chat area no longer opens blank. When CAT launches (or the
conversation becomes empty again after `/clear` / New Chat Session),
the chat pane shows an intentional command-center composition:

```
              ██████╗ █████╗ ████████╗
             ██╔════╝██╔══██╗╚══██╔══╝
             ██║     ███████║   ██║
             ██║     ██╔══██║   ██║
             ╚██████╗██║  ██║   ██║
              ╚═════╝╚═╝  ╚═╝   ╚═╝

                  CAT v0.7.9.0
         Chemistry • Coding • Intelligence
                ● CAT Notebook ready
    Create · Analyze · Build · Debug · Research
```

* New `calc_terminal/ui/empty_state.py` (`CATChatEmptyState`) — mounts
  through ConversationView's existing welcome slot, so it is pure UI
  state: never a session turn, never sent to the model, never copyable
  assistant content; removed by the same `hide_welcome()` chokepoint
  that always governed this slot.
* Word art reuses the app's own CAT block glyphs (`app.LOGO`) with a
  restrained top-to-bottom mode-gradient tint.
* Centered inside the CHAT PANE ONLY (`align: center middle`, full-pane
  child of the conversation scroll view) — explorer width, composer
  height and window resizes can't make it overlap anything.
* Responsive: ≥34 cols → full art; ≥22 → compact half-block CAT;
  narrower → text-only wordmark. Never overflows horizontally.
* Mode-aware: the ready line names the ACTUAL persona
  (`● CAT <Mode> ready`) and updates live on mode switches.
* Subtle one-shot entrance (fade + slight rise via class-toggle
  transition) plus an optional slow pulse on the ready line only — the
  word art itself never moves. (A CSS @keyframes variant was rejected:
  infinite animations can hold Textual's wait-for-screen busy state.)
* `/clear` and New Chat Session restore the centerpiece instead of
  printing a stray "Cleared." note; the richer WelcomeDashboard remains
  reachable via nav → Dashboard.

Verified by `_probe_empty_state.py` (18/18): startup presence,
version/ready lines, not-a-message guarantees, first-message teardown,
/clear restoration, pane-only centering before/after layout changes,
header/composer non-overlap, narrow-pane compaction, mode tracking.

---

## 0-bis. v0.7.9.0 SPEED + SMART ROUTING + REAL-TIME ORCHESTRATION

Measured, not guessed: every number below comes from
`scripts/benchmark_cat.py` or `calc_terminal/test_v079_speed.py` on the
real code paths.

### Smart Model Router (`calc_terminal/model_router.py` — new)

* Pure-local request classifier (regex only, **0.01–0.08 ms** per
  message — routing can never be the bottleneck): classifies into
  simple_chat / coding / debugging / research / mathematics /
  long_context / vision / document_analysis / multimodal / planning /
  agentic_execution / multi_agent.
* Picks the pipeline path per message: FAST (simple questions skip
  memory scan, history summarization, agents, tools) → STREAM (plain
  token streaming) → AGENT (tool loop) → VISION (image analysis) →
  MULTI_AI (only genuinely complex tasks, complexity-scored).
* MODEL CAPABILITY REGISTRY (requirement #8): every configured provider
  + backup described up front by `ModelCapabilities(text/vision/tools/
  streaming/reasoning/context_window/latency_score/cost/reliability)`.
  Capabilities are consulted BEFORE a request; never discovered after a
  failure. Builds in ~1 ms, cached 30 s.
* Multimodal fallback (#19): when the active model cannot see images,
  the router finds a vision-capable CONFIGURED model and routes the
  image there instead of replying "model can't see this"; if none is
  configured, that is reported clearly.

### Real image pipeline (`calc_terminal/vision.py` — new)

* validate → decode/normalize → classify → strategy → vision model.
* PNG/JPG/JPEG/WEBP/GIF/BMP/TIFF/TIF/ICO supported; EXIF orientation
  applied; CMYK/palette/alpha handled; oversized images downscaled with
  a high-quality filter and recompressed only as needed (measured:
  3000×2200 PNG → 1568-wide JPEG in ~115 ms, small images pass through
  byte-for-byte identical). Corrupted files raise an honest error.
* Local classifier picks photo/screenshot/scanned_document/chart/
  diagram/code_screenshot/handwritten and attaches a strategy-specific
  comprehensive-extraction prompt (objects, OCR text, tables, charts,
  diagrams, UI elements, verbatim code, math). Optional local OCR
  (pytesseract) is folded in when installed.

### Per-request latency metrics (`calc_terminal/metrics.py` — new)

* Real wall-clock stage timings: memory_retrieval_ms, routing_ms,
  model_first_token_ms (TTFB), tool_execution_ms, agent_loop_ms,
  vision_ms, history_summarize_ms, plus model_calls / tool_calls /
  streamed_chunks per request and rolling session aggregates
  (mean/p95). Thread-safe; recorded from the actual call sites.
* Every finished reply's completion card now shows its REAL timings;
  `/perf` prints measured session totals. Nothing fabricated.

### Unified event bus (`calc_terminal/event_stream.py`)

* Added ROUTE_DECIDED, MODEL_SELECTED, MODEL_REQUEST_STARTED,
  MODEL_FIRST_TOKEN, TEXT_DELTA, AGENT_THINKING, TOOL_DETECTED,
  TOOL_PROGRESS, TOOL_FINISHED, AGENT_CONTINUING, MULTI_AGENT_*,
  IMAGE_ANALYSIS_*, FINAL_RESPONSE, ERROR — all emitted by the actual
  runtime (router, agent loop, aicore transport, orchestrator).
* Buffer bounded (500 events); subscribe/unsubscribe now thread-safe.

### Speed fixes (each verified by benchmark)

* **Blocking sound removed from the hot path** — winsound.Beep blocked
  ~219 ms PER TOOL CALL ('success' = two tones). Sounds now run on a
  daemon thread: calculate tool went 219 ms → **0.30 ms** (~700×).
* Blank-response retry no longer re-sends provider error signatures
  ("AI not configured", quota...) — duplicate doomed network calls gone.
* Memory: relevance-filtered injection (`query=` keyword scoring),
  batched activity writes (one save per turn instead of one per tool
  step), process-wide singleton for the layered SQLite manager
  (previously TWO full initializations per turn).
* History summarization now runs only when the backlog actually needs
  folding — never on fast-path turns.
* Directory-listing cache (`calc_terminal/fs_cache.py`) with TTL +
  mtime probing + instant invalidation from every write/delete/rename
  tool — repeated scans inside one agent run are served from cache,
  stale listings impossible.
* UnicodeEncodeError on legacy cp1252 consoles (verbose agent print /
  trace lines with emoji) killed whole replies; both are now
  encode-safe, and the UI agent path runs quiet (`verbose=False`) since
  it renders its own live activity.

### Multi-AI overhaul (`calc_terminal/collaboration.py`)

* Fixed latent crash: `steps` was referenced before assignment, so
  `run_collaborative()` raised NameError on any planner-bearing roster.
* Fixed dead shared state: role outputs were never written to
  `ctx.agent_findings`, so the planner's plan was silently discarded
  and every run degraded to a generic one-step plan.
* RESEARCHER performs a REAL web search and synthesizes over the actual
  snippets (cited [1]/[2]) instead of pretending.
* Dynamic team (#21): complexity ≤0.35 → planner+coder+finalizer;
  ≤0.6 → +reviewer+tester; above → full gated roster.
* Parallel review (#24): REVIEWER/SECURITY/DEBUGGER/TESTER/ARCHITECT/
  UI_DESIGNER run concurrently on a ThreadPoolExecutor after the coder
  (verified: concurrent wall-clock beats sequential sum in tests).
* MULTI_AGENT_STARTED/PROGRESS/FINISHED events feed the UI; each agent
  start/done is rendered live in the chat bubble.

### Live activity & identity (UI)

* CAT indicator is now MODE-SPECIFIC from real mode state: CAT
  Notebook / CAT Research / CAT Planner / CAT Build / CAT Debug / CAT
  Agent (+ CAT Multi-AI / CAT Vision overrides during those paths).
* Thinking caption animates smoothly through Thinking. .. Thinking....
  inside ONE live component; eye behavior is state-specific (thinking
  blinks, executing stares wide, waiting holds still — no fake motion).
* Router decisions surface as one truthful line in the bubble
  ("Router: VISION … → provider/model"); tool lines keep streaming in
  real time during agent work.

### Decorative highlight cleanup (classic terminal)

* Home-screen status ribbon badges (filled background pills making
  normal labels look selected) replaced with clean typography; removed
  the "█ AGENTIC AI + 3D + GAME MODE ENABLED █" banner and the GAME
  badge chip. Functional selection/focus states untouched.

### Verification

* New suite `calc_terminal/test_v079_speed.py` (30 tests): router
  classification + cost (<5 ms/msg), capability registry, event bus,
  fs-cache invalidation, memory relevance/batching/singleton, vision
  normalization (passthrough byte-identity, resize caps, corruption
  errors), agent instrumentation (real event sequence + counted calls +
  no doomed retries), collaboration (dynamic rosters, findings fix,
  parallel reviewers timing assertion).
* New headless E2E `_probe_v079_e2e.py`: fast question streams in one
  transport call; attached PNG reaches the model as normalized bytes
  with strategy prompt; agent-mode coding writes a REAL file with live
  tool events; multi-AI orchestration completes.
* Regression: test_overhaul (77), test_root_cause_fix (29), test_fixes,
  test_formats — all pass.

---

## 0. HOTFIX — glitched CAT Agent body (rendering root cause)

**Symptom.** The bot rendered with a mutated body:

```
CAT Agent
(0~0)
/[[]_][/]
][[]
```

**Root cause.** The first animation build embedded Rich-markup escape
sequences (`[[`) inside the animated art STRING and rebuilt that string
every tick, so the bot's shape depended on markup-parsing behavior and
could surface escaped/mangled body lines.

**Fix (rendering implementation only — the bot was not redesigned):**

* `CAT_AGENT_TEMPLATE` — an immutable four-line plain-text frame model;
  `{eyes}` is the ONLY substitution slot.
* `VALID_EYES` — controlled set of exactly-3-character frames
  (`o.o 0.0 O.O -.- o~o 0~0 o-o O-o`); `validate_frame()` falls back to
  `o.o`, so malformed eyes can never render.
* `render_cat_agent(eyes)` — every frame generated INDEPENDENTLY from
  the template; nothing is appended to or mutated from prior frames.
* Rendering uses rich.text.Text SPANS (no markup parser anywhere near
  the body); `Static.update()` replaces the whole content each tick, so
  frames cannot accumulate.
* `waiting_permission` (and terminal states) HOLD one stable frame —
  the eye timer pauses instead of pretending to think.
* Regression probe `_probe_cat_anim.py` captures ~78 frames over 4 s of
  live ticking and asserts line 1/3/4 byte-identical in ALL frames,
  only validated eye frames rendered, constant block height/width,
  exactly ONE component, no art leaked into chat history, and clean
  removal on finish/error/cancel with no timers left running.

---

## 1. Branding — CAT v0.7.9.0

* `calc_terminal/app.py`: `VERSION = "0.7.9.0"`, new `EDITION`, and a
  new ASCII **CAT** block LOGO.
* Rebranded every user-facing surface: header wordmark (`⬡ CAT`),
  window title, Welcome Modal ("Welcome to CAT v0.7.9.0",
  "Initializing CAT…", "✓ CAT ready"), Welcome Dashboard hero, `/about`,
  status bar version field fallbacks, classic-terminal boot/home
  screens, error messages (`CAT couldn't…`), AI persona prompts
  ("You are CAT AI …"), memory/packages/code-editor copy, ASCII art
  gallery marks, identity fast-path answers, `[CAT DEBUG]` startup
  logs, and `identity.py` (`APP_NAME = "Coding Agent Terminal"`,
  `SHORT_NAME = "CAT"`; legacy "cct" phrasings still answered).
* Internal identifiers deliberately untouched where they are load-
  bearing: package name `cct-ai-ide` (PyPI collision), widget/CSS ids,
  the `%LOCALAPPDATA%\CCT` data directory, `~/.cct_*` config files, and
  the `GALLERY["CAT"]` key renamed together with its definition.

## 2. CLI — launch with `cat`

* `pyproject.toml` registers **both** console scripts:
  `cat = calc_terminal.cli:main` (new) and `cct = …` (kept as an alias).
* `cat --version` → `CAT v0.7.9.0`; usage banner updated; errors now
  say `cat:`.
* New `calc_terminal/__main__.py`: `python -m calc_terminal` works too.
* Verified in cmd.exe / Windows Terminal (plain `cat`). PowerShell
  note: PS defines its own built-in `cat` alias (Get-Content), so use
  `cat.exe` there or remove the alias in your profile.

## 3. Real-time File Explorer (the big fix)

New `calc_terminal/fs_watcher.py`:

```
REAL FILESYSTEM → watcher → debounced events
    → ui/app.py bridge (call_from_thread)
    → WorkspaceFilesChanged → Explorer tree refresh
```

* watchdog `Observer` when available (added dependency
  `watchdog>=4.0`; installed automatically). Real OS push events on
  Windows via ReadDirectoryChangesW — create/delete/rename/move/
  modify, recursive under the active workspace root.
* Stdlib snapshot-poll fallback (2 s cadence, name+mtime diffing) when
  watchdog isn't importable — throttled by construction, never a busy
  loop, limited to the workspace root.
* Burst coalescing (0.35 s debounce) so one save = one refresh.
* One watcher per app; `start(root)` stops the previous root first
  (new workspace ⇒ stop old watcher ⇒ start new ⇒ reload tree), and it
  is stopped on app exit. No stale roots, no blind polling, no manual
  reopen/restart needed.
* `Explorer.refresh_tree()` uses `DirectoryTree.reload()`, which
  preserves expanded folders and the highlighted row (a bare node-level
  reload raced the tree's internal loader and could repaint stale
  contents — root cause of flaky updates found during testing).

### Explicit agent-tool events (fast path)

* New bus topics: `TOOL_FILE_CREATED / TOOL_FILE_DELETED /
  TOOL_FILE_MOVED / TOOL_DIRECTORY_CHANGED`.
* `CCTApp._notify_tool_fs_change()` fires the topic **and** posts
  `WorkspaceFilesChanged` the moment a mutating tool completes, so
  CAT-created/deleted files appear/disappear during the turn while the
  OS watcher independently confirms disk state.

## 4. Layout architecture — overlap fixed + resizable panes

Root cause of the composer/explorer overlap: the composer was
screen-`dock`ed bottom, spanning the full width underneath the
Explorer column.

* The `StickyComposer` now lives **inside** `WorkspaceShell`'s main
  column (`#cct-workspace-main`), below the chat split — geometrically
  unable to cross into the Explorer column at any window size:
  `dock: bottom` removed from `#cct-composer`.
* New `calc_terminal/ui/resizers.py` with two drag handles built on
  Textual mouse capture (no timers, no busy loops):
  * **Explorer divider** (1-column bar): drag left/right resizes the
    Explorer between 14 cols and 55 % of the shell. Hidden exactly
    when the Explorer is hidden/collapsed.
  * **Composer grip** (subtle `─ · ─ · ─` row): drag up/down resizes
    the composer height between 6 rows and 70 % of the column; the
    chat history always keeps usable space. Height math derives from
    static main-column geometry (reading live composer regions mid-
    relayout caused oscillation — fixed).
* Both sizes persist to `~/.cct_ui_layout.json` and are restored on
  launch; window resizes re-clamp the explorer so nothing ever
  overlaps (verified at 70×26 through 200×50).

## 5. CAT Agent thinking animation

New `calc_terminal/ui/cat_agent.py`:

```
CAT Agent
   (o.o)
   /[_]\
    ] [
Thinking...
```

* Eyes animate through `(o.o) (O.O) (0.0) (o~o) (-.-)` on a 200 ms
  timer (inside the 100–250 ms band; scales with the existing
  `animation_speed` setting; `CAT_AGENT_ANIMATION=0` disables).
* Fixed-width block — the layout never jumps frame-to-frame.
* Driven by REAL backend state, never fake timing:
  * `MessageStarted` → thinking
  * new `AgentActivity` event → `tool_execution` (each tool start),
    back to `thinking` on tool result, `waiting_permission` while a
    permission card blocks, back to `tool_execution`/`thinking` on
    grant/deny/cancel
  * `MessageFinished` → removed (this single chokepoint covers
    success, error AND cancel, since all post MessageFinished)
* Pure UI state: zero model tokens, never part of requests, never a
  conversation message, removed before it could interfere with copying.

## 6. Highlighted-text cleanup

Decorative background fills removed across the interface while keeping
every functional state (text selection, input focus, active buttons,
accessibility focus, syntax highlighting, selected list/tree rows):

* attachment chips & drop target, command-palette selection, menu-btn /
  permission-pill states, sidebar project rows & workspace header
  "glass", Chat/Files switcher, editor toolbar/findbar/warning banner,
  nav menu rows, permission menu rows, context-menu rows, attach /
  personalization / timeline / todo panel rows, recent-workspace rows,
  icon buttons.
* Emphasis now comes from font weight, color, borders and spacing —
  not filled rectangles behind text.

## 7. Verification (all headless, Textual Pilot)

* `_probe_cat_v079.py` — 31 checks: branding, layout structure, no-
  overlap across widths/window sizes, divider/grip visibility &
  clamps, persistence roundtrip, external create/delete/folder
  create/folder delete appearing automatically (~0.6 s), CAT-tool
  create/delete immediate (~0.2 s), animation lifecycle incl. eye
  movement and state labels.
* `_probe_cat_drag.py` — 12 checks: real MouseDown/Move/Up drags on
  both handles (widen/narrow/clamp, grow/shrink composer),
  independence of the two areas, window-resize stability, persistence.
* `_probe_cat_final.py` — 13 checks: identity answers, versions,
  welcome modal text, live end-to-end model request with animation
  appear/animate/stop, submit pipeline intact.
* Regression: `test_fixes.py`, `test_formats.py`,
  `calc_terminal.test_overhaul` (77 tests),
  `calc_terminal.test_root_cause_fix` (29 tests) — all pass.
