# v0.7.2 — Chat Context Menu & Clear Recent Projects

Implements the two items CHANGELOG_v0.7.2_galvin_fixes.md explicitly
deferred to their own slice ("Right-click context menus... a real,
separate feature... deserves its own slice") plus the standalone
Clear Recent Projects request. Verified by code reading + `py_compile`
across the whole package; no network access in this environment to
install `textual` and confirm any of this on an actual running
terminal — same disclosed limitation every prior v0.7.x changelog in
this project has flagged, not new to this pass.

## 1. Chat Context Menu & Conversation Actions (CRITICAL)

### New: `calc_terminal/ui/context_menu.py`

`MessageContextMenu` — one reusable `Screen`, built from a plain
`(action, label)` list, opened beside the click instead of centered
(clamped so it never renders off the right/bottom edge). Same
real-Screen-push pattern this package already uses for
`PermissionModeMenu` (`ui/header.py`) and `_AttachPrompt`/`_PathPrompt`
(`ui/app.py`) — there's a standing rule here against floating popup
windows, so a positioned Screen push is how "context menu" is done
without breaking that. Keyboard nav (Up/Down/Tab/Shift+Tab/Enter),
Esc closes, click-outside-the-box closes, hover + keyboard-selected
row highlighting. Only one can ever be open at once for free, since
Textual's screen stack only accepts input for the top screen.

**Honest note on the animation requirement**: the spec asks for
"fade + scale". Textual's CSS `transition` only animates
opacity/offset/size-style properties — there's no real transform-scale
primitive to animate. This uses opacity + a small upward `offset`
(180ms), the identical tradeoff `PermissionModeMenu` already made and
disclosed in its own comments — not a silent shortcut new to this
pass.

### `calc_terminal/ui/conversation.py`

`ConversationItem.on_click` opens the menu on right-click (`event.button
== 3`) for user/assistant bubbles (not system notes, which the spec
doesn't define a menu for) and resolves a screen coordinate for the
click defensively (tries `screen_x`/`screen_y`, then `screen_offset`,
then falls back to this widget's own on-screen `region` + the event's
local offset) since the exact attribute name isn't something I could
verify against a real Textual install here.

**Copy Text** is handled entirely inside `ConversationItem` rather
than round-tripping through an event — it needs no cross-component
coordination. It calls the *existing, real*
`code_editor.copy_to_clipboard()` (the same function `/copycode` and
the code pad's `:copy` already use — pyperclip, then
clip/pbcopy/xclip/xsel/wl-copy) and shows a real "✓ Copied" /
"✗ Copy failed" confirmation by reusing this widget's own
`update()`/`styles.animate()` — the same mechanism `append_chunk`/
`finalize` already use — rather than mounting a second overlay widget
into a `Static`, which isn't normally a child-hosting container.

Every other menu choice posts the new `events.MessageContextAction`
and is handled centrally in `CCTApp` (module convention: components
never call each other directly — see `ui/events.py`'s docstring).

Also added `ConversationView.remove_from(turn_id)` for Revert: removes
a turn's row and everything mounted after it (including non-turn cards
like `PermissionCard`), using the fact this view only ever appends in
chronological order, so index position already matches conversation
order.

### `calc_terminal/session.py`

Added the "Conversation Architecture" metadata the spec calls for:
- `Turn.parent_turn_id` — for an assistant turn, the id of the user
  turn that prompted it. This is the actual fix that makes "Try Again"
  reliable: it looks the original prompt up by id instead of guessing
  from list position, which breaks the moment a turn is removed
  (Revert) or the transcript is forked.
- `ChatSession.index_of(turn_id)` — used by Revert.
- `ChatSession.fork_upto(turn_id)` — returns a brand-new `ChatSession`
  carrying a copy of every turn up to and including `turn_id`, plus
  the same workspace/model/summary state, leaving the original
  session object completely untouched. This is what makes Fork a real
  fork and not a rename of the current conversation.

### `calc_terminal/ui/app.py`

`on_message_context_action` dispatches to five real handlers:

- **New Chat Session** — reuses the exact `conversation.clear()` +
  `session.clear()` pair `/clear` already does. Never touches
  `self._workspace_shell`/`self._workspace_root`, so the open project
  and its Editor tabs are left alone, per spec.
- **Try Again in Build/Plan/Notebook/Agent Mode** — looks up the
  original prompt via `turn.parent_turn_id`, switches the active AI
  mode the same way `/build`/`/plan`/`/notebook`/`/agent` already do
  (`_switch_mode_command`), and re-runs it through the same
  permission-gated path (`_maybe_gate_then_run`) normal messages use —
  so a "Try Again" that happens to ask for a simulation still hits the
  same execute-python confirmation card instead of silently
  bypassing it. Appends a brand-new assistant turn; the old reply
  stays exactly where it is. `_begin_assistant_turn` and
  `_maybe_gate_then_run` both gained an explicit `parent_turn_id`
  parameter (threaded through the permission-gate's pending-request
  tuple too) specifically so a *second* "Try Again" on the newly
  generated reply still has a real parent to look up — the previous
  "last turn was a user turn" heuristic alone would've gone stale the
  moment the last turn in the transcript was an assistant reply
  instead.
- **Rewrite** — loads the original text into the composer
  (`ComposerInput`) and focuses it; does not send.
- **Revert** — truncates `session.turns` to strictly before the
  selected prompt and calls the new `remove_from()`; never touches
  workspace/project state.
- **Fork Conversation** — calls `session.fork_upto()`, swaps the
  active session to the fork, and re-renders the conversation view
  from the fork's turns.

  **Scope limit, stated plainly rather than faked**: this package has
  exactly one scrollable conversation region
  (`ui/conversation.py`'s own module docstring: "the ONLY scrollable
  region in the primary UI") and no multi-tab/multi-conversation
  switcher UI. Fork *is* real — a genuine second `ChatSession` object
  exists in memory, independent of the original, matching the spec's
  "original conversation remains unchanged" — but there is currently
  no in-app control to switch back to the pre-fork conversation; it's
  kept on `self._forked_from` for a future conversation switcher, and
  the system note tells the user `/clear` is the only way to start
  over today. A real conversation list/tab bar to browse forks is a
  separate, larger feature and is explicitly out of scope for this
  slice — not something to bolt on as a button that quietly does
  nothing.

## 2. Clear Recent Projects (MINOR)

### `calc_terminal/projects.py`

`clear_recent()` — empties `recent`, leaves `pinned` untouched, never
touches any file/folder on disk (it only rewrites the small JSON store
at `projects.STORE_PATH`, same as every other function in this file).

### `calc_terminal/ui/sidebar.py`

- `_ConfirmClearRecent` — a real confirmation dialog (same Screen-push
  pattern as `_ConfirmClearRecent`'s siblings elsewhere in this
  package), showing the exact copy the spec asked for and a
  Cancel/Clear button pair.
- `_ClearRecentRow` — the clickable "🗑 Clear Recent Projects" link,
  shown at the bottom of the Recent Projects list only when that list
  isn't already empty.
- `Explorer._render_projects` refactored to build the Pinned/Recent
  block inside its own `#cct-sidebar-projects` container (previously
  it shared a CSS class with the open-folder header, so there was no
  way to redraw just the Recent list without also tearing down
  whichever project is currently open). Clearing now redraws in place;
  the active workspace and open folder are completely unaffected.

**Menu location**: implemented under Explorer ▸ Open Folder ▸ Recent
Projects (the spec's first listed location). The spec's second
alternative — "Hamburger Menu ▸ Workspace ▸ Clear Recent Projects" —
isn't implemented: the hamburger glyph in this codebase
(`SidebarToggleGlyph`, `ui/header.py`) is a plain sidebar-visibility
toggle with no submenu structure today, and building a second, parallel
hamburger-dropdown menu system just to duplicate this one action felt
like scope creep beyond "add Clear Recent Projects" — flagging it here
rather than silently only doing half of what a literal reading of the
spec's "or" asked for.

## Fix (post-release): DuplicateIds crash on Open Folder

The first version of this pass gave the Pinned/Recent container a
fixed `id="cct-sidebar-projects"`. `open_folder()` clears the sidebar
body and then calls `_render_projects()` again in the same
synchronous call stack — but `Widget.remove()` in Textual is
scheduled through the message pump, not instant, so the old container
wasn't actually unregistered yet when the new one tried to mount with
the same id, and Textual raised `DuplicateIds`. Fixed by tracking the
container by direct object reference (`self._projects_container`)
instead of a re-used fixed id, and mounting each redraw as a plain
widget with only a CSS class (`cct-sidebar-projects`) — removal is
now best-effort (wrapped in try/except, since the container may
already be gone if `open_folder()`/`close_folder()` just wiped the
whole sidebar body) and never depends on the old widget having
finished unmounting first. CSS selector in `_COMPONENT_CSS` updated to
match (`#cct-sidebar-projects` → `.cct-sidebar-projects`). Confirmed
by an actual run on Windows (thank you for the traceback) — this is
the first part of this changelog that's had real runtime
confirmation rather than only `py_compile`.



- A real conversation switcher/tab bar for browsing forks (see Fork
  Conversation above).
- Nothing here was exercised against a running instance — still no
  network access in this container to install `textual`. Treat every
  fix as logically sound (traced through the actual call paths) but
  functionally unconfirmed until it's run for real in a terminal.

## Fix (post-release 2): Rewrite & Try Again duplicated messages instead of replacing them

Reported as a follow-up minor bug: Rewrite (after editing + Enter) and
every "Try Again in <mode>" appended a brand-new user/assistant turn
instead of updating the existing one, cluttering the conversation with
duplicates. Fixed by making both regenerate an existing turn *in
place* instead of calling the normal append path:

- **`ui/conversation.py`**: added `ConversationItem.set_text()` (used
  by Rewrite to update the edited USER bubble's own text) and
  `.reset_for_regenerate()` (resets an ASSISTANT bubble back to an
  empty streaming state in place, reusing its mode-snapshot coloring
  logic instead of recomputing it live). `ConversationView` gained
  matching `set_text()`, `reset_for_regenerate()`, and `has_item()`.
- **`ui/app.py`**: `on_message_started` — the one place a turn's
  bubble gets created — now checks `has_item(turn_id)` first: an
  unseen turn_id still mounts a brand-new bubble (the normal path
  every plain message takes); an already-mounted turn_id (Try
  Again/Rewrite) gets reset in place instead. New `_regenerate_turn()`
  is the shared helper both features call — it mutates the existing
  session `Turn` and re-runs `_stream_worker` pointed at the same
  `turn_id`, so `MessageChunk`/`MessageFinished` naturally repaint the
  existing bubble instead of a new one. `_retry_in_mode` and the
  permission-gate path (`_maybe_gate_then_run`, `_pending_permissions`)
  were updated to thread a `replace_turn_id` through, so a Try Again
  that also happens to trip the execute-python confirmation card still
  replaces in place once granted, instead of silently falling back to
  append.
- **`ui/composer.py` + `ui/events.py`**: Rewrite now puts the composer
  into a real, visible edit mode (`StickyComposer.start_edit` — a new
  "✏️ Editing message — Enter to save, Esc to cancel" banner, Esc
  cancels via `cancel_edit`) instead of just prefilling text for a
  normal send. Submitting in edit mode posts a new `MessageRewritten`
  event (handled by `on_message_rewritten`) instead of the usual
  `MessageSubmitted`, since the two trigger genuinely different
  behavior (replace vs. append) rather than being distinguished by an
  if-branch buried in one shared handler.

**Not implemented — the spec's own named "Optional Enhancement"**:
"Generate Alternative" (a way to intentionally keep the old response
and add another instead of replacing it) is explicitly called out as
optional. Skipped this pass to stay scoped to the required "replace"
behavior; the underlying plumbing (append via `_begin_assistant_turn`
vs. replace via `_regenerate_turn`) already exists side by side, so
that would be a small follow-up, not a redesign.

## Noted, not started: "Future Major Features" roadmap

The accompanying roadmap document (Multi-Agent Collaboration, AI Todo
List, Smart Terminal, Project Dashboard, plus a
`MultiAgentManager`/`TodoManager`/`SmartTerminalManager`/
`DashboardManager`/`WorkspaceManager`/`ConversationManager`/`EventBus`
architecture) is explicitly framed as future-release design guidance
("should be designed with modular architecture so they can be
expanded in future releases"), not a request to build in this pass —
and each item on it is independently large enough to warrant its own
slice, the same reasoning `CHANGELOG_v0.7.2_galvin_fixes.md` already
used to defer the context-menu work that later became this file. No
code for any of it is in this drop. Worth a project-level design doc
before the first of those four gets picked up, given how directly it
calls for an event-bus-style architecture that doesn't exist yet
(today's `ui/events.py` is a flat list of Textual `Message` subclasses
handled ad hoc by `CCTApp`, not a real pub/sub bus multiple managers
could hang off of).

## v0.7.2 "Next Generation IDE Features" — EventBus, Timeline, AI Todo, Dashboard, LaTeX extensions

Scoped down from the full 8-item roadmap doc after checking with the
user: built for real — EventBus, Session Timeline, AI Todo Manager,
Project & Workspace Dashboard, LaTeX engine extensions. Design doc
only (no code) for Multi-Agent Collaboration — see
`DESIGN_multi_agent_collaboration.md`. Explicitly NOT attempted this
pass: the AI Terminal (natural-language-to-shell-command execution) —
that's a security-sensitive feature that deserves its own dedicated
design conversation, the same reasoning applied to Multi-Agent.

### New: `calc_terminal/eventbus.py`

A real, plain-Python pub/sub bus (`eventbus.bus.publish(topic, **data)`
/ `.subscribe(topic, callback)`), separate from `ui/events.py`'s
Textual `Message` classes (which are untouched — this isn't a rewrite
of the working UI-message architecture). Every backend module below
publishes to it; `CCTApp` is the only place that bridges bus topics
into UI updates, and does so only from confirmed UI-thread call sites
(`on_message_finished`, `on_file_saved`, `_open_folder`) — the one
exception is `AI_FILE_EDIT`, published directly from the
`@work(thread=True)` streaming worker thread, which is safe only
because its one subscriber (Timeline) does nothing but append to a
plain list.

### New: `calc_terminal/timeline.py` + `ui/timeline_panel.py` (Session Timeline)

In-memory (capped at 500), auto-populated via `wire_to_bus()` — every
`eventbus.bus.publish()` anywhere in the app becomes a timeline entry
without the caller needing to know Timeline exists. Panel (`/timeline`)
has live search and click-to-open-file. Honest gaps: no persistence
across restarts (the roadmap itself marks "Restore previous state" as
a future item), and Git Commits as an event type is defined but never
published — nothing in this codebase shells out to git or watches
`.git/` for new commits.

### New: `calc_terminal/todos.py` + `ui/todo_panel.py` (AI Todo Manager)

JSON-persisted (mirrors `projects.py`'s store pattern exactly),
per-workspace. Manual add/complete/delete/priority-cycle/search/filter,
progress bar, all real. AI detection
(`todos.detect_ai_todos`) is a real regex scanner over an assistant
reply's own text — Markdown checkboxes and TODO/FIXME lines — wired
into `on_message_finished` so it runs automatically after every reply,
tagged `source="ai"`, deduped against existing todos. Documented
plainly as narrower than a dedicated LLM extraction call, which is a
materially different (and heavier) feature this isn't.

No literal "Main Menu" (Workspace/Recent Projects/AI Todo/Settings/
Extensions/Documentation) exists anywhere in this codebase — the
hamburger glyph is a plain sidebar toggle, and Settings/Extensions/
Documentation aren't panels here either. Exposed via `/todo` instead,
same pattern as every other panel.

### New: `calc_terminal/project_stats.py` + extended `ui/dashboard.py` (Project & Workspace Dashboard)

Real, bounded (capped at 20k files scanned) computation: project
size/file count/language histogram from one `os.walk` pass, git branch
from reading `.git/HEAD` directly (no subprocess dependency),
dependencies parsed from whichever of requirements.txt/package.json/
pyproject.toml actually exists, last-modified, process memory via
stdlib `resource` (POSIX only). `WelcomeDashboard` gained a
`workspace_root` param and a `refresh_stats()` that updates just the
stats column in place — wired to fire after a file save, after an AI
reply finishes, and after opening a folder. Also fixed existing
behavior: opening a folder used to permanently hide the dashboard even
if no chat had started; it now re-shows (with live project stats)
instead, matching the roadmap's "main landing page whenever no chat is
active".

Honest gaps, not fabricated: CPU% and "Indexed Status" report as
unavailable — no `psutil`, no continuous sampling anywhere in this
app, and no separate file-index system to report on (Explorer's
DirectoryTree reads the filesystem directly). "Terminal Status" isn't
shown at all — there's no persistent embedded terminal in this app to
have a status.

### LaTeX engine extensions (`calc_terminal/mathtext.py` + `ui/conversation.py` + `ui/composer.py`)

This codebase already had a genuinely solid LaTeX→Unicode terminal
renderer (v0.6.2) wired into every assistant bubble — extended rather
than rebuilt:

- Added `\sum \prod \int \iint \iiint \oint`, quantum/set notation
  (`\langle \rangle \hbar \otimes \oplus \dagger \forall \exists \in
  \subset \cup \cap` etc.) to the symbol table. Verified there were no
  substring-collision bugs in the final table with a script (`.replace()`
  is literal and order-dependent) and caught/fixed two real ones before
  shipping: `\subset` is a literal prefix of `\subseteq` (needed
  reordering) and `\to` is a literal prefix of `\top` (dropped `\top`/
  `\bot` rather than risk it for two rarely-needed lattice symbols).
- `find_latex_errors()` — real, narrow error-highlighting: unbalanced
  braces after `\frac`/`\sqrt`, unclosed `\begin{...}` environments.
  Surfaced as a meta line under a finished assistant reply. Does not
  validate arbitrary macro names (this module's existing, deliberate
  design: unknown macros pass through as plain text rather than
  producing warning noise).
- Live preview strip in the composer (`_update_latex_preview`, runs on
  every keystroke, whole-message scope — no per-span cursor tracking
  exists to preview just the equation being typed).
- "Copy rendered equation": Copy Text on an assistant bubble now
  copies the Unicode-rendered form, not the raw LaTeX source. Also
  whole-message scope — no per-equation click target exists inside one
  Static's rendered content.
- User messages now also get inline math rendering (Greek/sub-sup/
  symbols), via a new `render_inline()`-only path — NOT the full
  `render_math()` assistant bubbles get, since user bubbles are plain
  Rich `Text`, not Markdown, and `render_math()` can produce fenced
  code blocks (for fractions/matrices) that would show their literal
  ```` ``` ```` marks instead of rendering.

**Not implementable, stated plainly rather than faked**: KaTeX/MathJax-
grade rendering, SVG/PNG/PDF export, and zoom are not achievable in a
terminal UI — a terminal renders monospace text/ANSI, not raster or
vector graphics, and this app has no embedded browser engine. Also
noted as a pre-existing (not newly introduced) limitation while
testing the extensions: the sub/superscript converter only recognizes
ASCII alphanumeric bound content, so `\sum_{i=1}^{n}` renders bounds
next to the sigma but a symbolic bound like `\int_0^\infty` keeps a
visible `^` before the ∞ instead of true superscripting — this was
true before this pass for Greek-letter bounds too, not a regression.

### Design doc only: `DESIGN_multi_agent_collaboration.md`

Splits the roadmap's "Multi-Agent Collaboration" into (A) sequential
agent hand-off — cheap, builds directly on modes/turns/Fork that
already exist — and (B) true parallel execution — a materially
different system (concurrent file-write locking, multi-stream UI,
linear cost multiplication) recommended to design later, informed by
real usage of (A), rather than build blind. Lists open product
questions (auto-advance vs. confirm-per-step, failure handling,
cost visibility) that need answers before any code should start.

### Explicitly not started this pass

- AI Terminal (natural-language → shell command execution) — held back
  per the user's own choice in this conversation; deserves a dedicated
  security-focused design pass given it's asking to grant an LLM real
  shell access.
- Smart Terminal upgrades (tabs/split/history/autocomplete) — no
  embedded terminal exists in this app at all yet (confirmed while
  scoping the Dashboard's "Terminal Status" field above), so this
  would need to start from an actual terminal widget, not an upgrade
  of one.
- Multi-Agent Collaboration code (design doc only, see above).

### Verification

`py_compile` across the entire package (clean) plus targeted
standalone tests outside Textual for the parts that don't need
it — `mathtext.render_math`/`find_latex_errors` against several real
LaTeX strings, and a script asserting no substring-collision bugs
across the full symbol table. No `textual` install available in this
environment (network access is disabled here), so none of the new
Screens/panels have been run in a real terminal — same disclosed
limitation as every prior slice in this file.
