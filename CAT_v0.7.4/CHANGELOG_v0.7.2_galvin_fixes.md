# v0.7.2 "Galvin Edition" — First fix slice

## A note on scope before anything else

The two review docs list six items (file explorer scrolling, AI
workspace permissions, sidebar/Open Folder merge, editor not opening
files, right-click context menus, plus a later note on hardcoded
workspace paths). That's several genuinely separate subsystems, not
one bug — consistent with this project's standing rule (see
CHANGELOG_v0.7.1_ui_fixes.md), this pass fixes concrete, verified
bugs rather than re-touching everything in one sweep.

**Version mismatch, worth flagging directly:** the screenshots are
timestamped against a running build labeled `v0.8.1` (header text,
window title). The source in `CCT_project_v0_7_1_ui_fixes.zip` is
`v0.7.0_quantum_ide` / `v0.7.1`. Those are not the same build. Two of
the six reported symptoms — the sidebar already being one collapsible
component (`ui/sidebar.py`), and the editor already having a real
open-file/tabs/syntax-highlighting implementation (`ui/editor.py`,
`ui/workspace.py`) that switches to the Editor tab automatically on
file click — already appear to be implemented correctly in *this*
source. Either v0.8.1 regressed something v0.7.1 already had, or
v0.8.1 is a divergent branch that never got this v0.7.1 work merged
in. Worth checking which, since otherwise the same bug may get "fixed"
twice in two different codebases.

## Fixed this pass (verified by code reading + `py_compile`; no
network access in this environment to install `textual` and actually
run the app, so nothing here is confirmed by an on-screen test)

### 1. File Explorer clipped long filenames (spec section 1, highest priority)

`#cct-sidebar-body` (`ui/app.py` CSS) had no `overflow-x` rule, and was
built as a Textual `VerticalScroll` (`ui/sidebar.py`), which is
vertical-only by design. Every filename wider than the sidebar just got
clipped with no way to reach the rest of it — exactly the
`CCT_project_v0.8.1_home_dashboard...` truncation in the screenshot.

Fix:
- `ui/sidebar.py`: `cct-sidebar-body` is now a `ScrollableContainer`
  (both axes) instead of `VerticalScroll`.
- `ui/app.py` CSS: added `overflow-x: auto` on `#cct-sidebar-body`, and
  `width: auto` on `.cct-filetree` / `.cct-sidebar-section` /
  `.cct-sidebar-project` so their virtual width reflects the actual
  content instead of being force-fit to the visible column.
- Textual's `Tree`/`DirectoryTree` already handles Shift+wheel and
  click-drag horizontal scrolling natively once its scrollable ancestor
  allows `overflow-x` — no custom scroll-event code was added, since
  none should be needed once clipping isn't forced. **Unverified**: I
  can't confirm the on-screen result without running Textual.

### 2. AI refusing file operations outside Agent mode (spec section 2, "most important")

`ui/app.py`'s `_stream_worker` only routed through the real
tool-executing loop (`agent.run_agent`, which already had working
`write_file`/`create_folder`/`delete_file`/`rename_file`/`read_file`/
`list_directory` tools and a permission gate as of
CHANGELOG_v0.7.1_agent_file_tools.md) when the UI's AI-persona mode was
literally `"agent"`. The screenshot shows the user in the default
**Notebook** mode — every other mode (Notebook/Plan/Build) went through
plain `aicore.stream_ai`, a no-tool text completion, which is why the
model could only ever say "I cannot access your filesystem."

Fix: the tool loop now also runs whenever a project folder is open
(`self._workspace_shell is not None`), regardless of which persona mode
is selected — matching the spec's own wording ("When Workspace mode is
enabled ... the AI should directly perform actions"), which conditions
this on workspace state, not on mode. Non-agent modes keep their
existing shorter/conversational persona (`AI_SYSTEM_PROMPT`) rather than
switching to Agent's notebook-style verbose format — same tools, same
permission gate, different voice. Permission mode (Read Only/Ask/Full)
still gates each individual mutating call exactly as it already did;
this change only affects whether the tool loop is *attempted* at all.

### 3. AI writing to a hardcoded folder instead of the open project

Reported directly (not from the screenshots): `agent.py`'s file tools
resolve relative paths via `workspace.root_dir()`, which always read
`config.workspace_directory` (`~/cct_workspace` by default) — a fixed
setting completely disconnected from whichever folder was open in the
Explorer. A file created with a relative name landed outside the
visible project and never appeared in the tree.

Fix: `calc_terminal/workspace.py` gained `set_active_project()`/
`active_project()`; `root_dir()` now prefers the active project over
the config fallback. `ui/app.py._open_folder()` calls
`ws_paths.set_active_project(path)` the moment a folder is opened, so
the Explorer, Editor, and AI file tools all agree on one root. No
project open (including the classic non-UI REPL, which never calls
this) → falls back to the old `config.workspace_directory` behavior
exactly as before, so nothing regresses for that path.

## Second slice (v0.7.2, follow-up): Explorer/Editor sync after AI file ops

### Fixed: newly created files not appearing in the Explorer

Confirmed real: `agent.py`'s `write_file`/`create_folder`/`delete_file`/
`rename_file` tools touch disk directly but had no way to tell the
running Explorer's `DirectoryTree` to re-scan — so a file the AI just
created stayed invisible until the user reopened the folder.

Fix (new `WorkspaceFilesChanged` event in `ui/events.py`):
- After `run_agent()` returns, `ui/app.py._stream_worker` scans the
  executed tool steps for the four mutating file tools, filters out
  ones whose observation string matches a known failure/refusal shape
  ("Refused:", "already exists", "does not exist", etc. — a
  string-prefix heuristic, not a structured success flag, since the
  tools return human-readable text, not typed results), and collects
  the paths that actually changed.
- If any did, it posts `WorkspaceFilesChanged(paths)` back to the UI
  thread (tool execution happens in a worker thread; DOM/widget
  mutation has to cross back via `call_from_thread`, same pattern
  every other cross-thread update in this file already uses).
- `CCTApp.on_workspace_files_changed` calls
  `WorkspaceShell.refresh_explorer(paths)`, which calls the new
  `Explorer.refresh_tree()` (`DirectoryTree.reload()` on the mounted
  tree) and, for each changed path that's currently open in a tab, the
  new `EditorPane.reload_if_open(path)` (re-reads the file from disk,
  replaces the tab's text, restores the cursor to the same row/col
  clamped to the new bounds).

### Explicitly not done in this slice

- **Full "Workspace Event Bus"** (WorkspaceManager → EventBus →
  Explorer/Editor/Search/AI Context/Terminal/Build/Notebook/Agent, with
  typed Created/Deleted/Renamed/Modified/Folder events) — what's here
  is one coarse event carrying a list of touched paths, enough to fix
  the two reported symptoms, not the general pub/sub architecture the
  spec describes. Search index, Build system, and Agent context aren't
  real subsystems in this codebase yet, so "refresh" for them isn't
  meaningful yet either.
- **Filesystem watching for external changes** (someone edits the open
  project in VS Code while CCT is running) — not implemented. Would
  need a real watcher (e.g. `watchdog`), which isn't in
  `requirements.txt` and can't be installed/tested from this
  environment (no network access here). Everything above only fires
  when CCT's own AI tools make the change.
- **Refresh only the affected branch** — `refresh_tree()` reloads the
  whole mounted tree, not just the parent folder of the changed path.
  Fine for the tree sizes this app deals with; a real incremental
  refresh is a further optimization, not a correctness fix.
- **The recurring "editor stays blank when clicking a file"** report:
  traced the full call path again this round
  (`sidebar.Explorer.on_directory_tree_file_selected` →
  `FileOpenRequested` → `CCTApp.on_file_open_requested` →
  `WorkspaceShell.open_file` → `EditorPane.open_file`, which switches
  the active tab to `wtab-editor` itself) and it looks correct and
  complete in this source. I can't reproduce or find a defect in it
  without actually running Textual (still no network access here).
  The screenshot this was reported against shows a project folder path
  and permission-mode label that don't match anything in this zip, so
  before assuming this source still has the bug: please test it
  specifically against this v0.7.2 build and let me know if a file
  click still leaves the Editor blank there. If it does, the next
  thing to check is whether Textual is actually delivering
  `DirectoryTree.FileSelected` on a single click in the installed
  Textual version, vs. only on Enter/double-click — that would be a
  Textual-version behavior difference, not a wiring bug in this file.

## First slice, out-of-scope items (unchanged this round)

- Right-click context menus (AI-response menu: Copy/New Session/Try
  Again/Build/Plan/Notebook/Agent Mode; user-message menu: Rewrite/
  Copy/Revert/Fork). This is a real, separate feature (new component,
  keyboard nav, animation) and deserves its own slice rather than being
  bolted onto this pass.
- The four-tier permission model the spec describes (Read Only / Ask
  Every Time / Workspace Only / Full Access) doesn't fully line up with
  the three modes `permissions.py` currently has (Ask/Restricted/Full).
  Fix #2 above rides on top of whatever gating already exists there —
  reconciling the mode *names* and semantics with the spec is a
  separate, not-yet-scoped task.
- Terminal auto-`cd` into the active project, "Open with Terminal",
  "Open with Code", and making Run Project use the active workspace —
  all real asks from the later note, none touched here. `active_project()`
  now exists as the one place to read the answer from, but nothing
  outside the file tools consumes it yet.
- Nothing above was exercised against a running instance — this
  container has no network access to install `textual`. Treat the fix
  as logically sound (traced through the actual call paths, not
  guessed) but functionally unconfirmed until it's run for real.
