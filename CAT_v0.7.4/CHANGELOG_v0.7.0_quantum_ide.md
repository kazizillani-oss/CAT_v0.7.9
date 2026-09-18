# CCT v0.7.0 — Quantum AI IDE (architecture/IDE integration pass)

## Scope

This session's brief (see the v0.7 spec doc) was explicit: don't rewrite
working modules, don't remove existing AI modes, add IDE components on
top of what already exists. Two things from the *previous* v0.7.0 pass
(`CHANGELOG_v0.7.0_permissions.md`) were left honestly unfinished —
"No header-level mode selector control" and PermissionCard's labels not
being mode-aware — those are fixed here first, then the new IDE surface
(Explorer, integrated editor, workspace shell, Welcome Dashboard,
richer status bar, colored command palette) is added alongside them.

Unlike the previous permissions-only pass, `textual` **is** installed
in this session's sandbox, so everything below was actually mounted
and driven through Textual's `run_test()` headless pilot — not just
syntax-checked. That test isn't included in the delivered zip (it's a
throwaway dev script), but here's what it exercised, all passing:
dashboard mounts by default; the header permission selector cycles
Ask → Restricted → Full → Ask on click; `/open <folder>` mounts a real
`WorkspaceShell`; opening a `.py` file loads real content into a
`TextArea`; editing + `Ctrl+S` writes it back to disk; the sidebar
toggle, command palette, AI-mode switch, and chat message handling all
still work with the workspace mounted; opening a second folder reuses
the same shell instead of duplicating widgets.

One real bug this caught: `Explorer._render_projects()` re-mounted a
fixed-id `Static` (the drag-and-drop hint) every time a folder opened,
which raced Textual's async widget teardown and threw
`DuplicateIds` the moment `/open` ran a second time. Fixed by dropping
the id (nothing referenced it) — the kind of bug that's invisible from
reading the code and only shows up by actually mounting it, which is
exactly why the test was worth writing.

## What changed, file by file

**`ui/header.py`** — `BrandHeader` now has a top row: `☰` sidebar
toggle (left), `CCT` mark (left), a clickable **Permission Selector**
badge (center — `▼ Ask Every Time` / `Restricted` / `Full Access`,
click to cycle), and a right-side info cluster (Workspace / GPU / API /
time). The existing breadcrumb row (mode · model · workspace · context)
is unchanged, still directly below. This closes the exact gap the
prior permissions changelog flagged as unwired.

**`ui/permission_panel.py`** — `PermissionCard` now reads
`permissions.manager.restricted_review(key)` and shows **Accept /
Reject** in Restricted mode vs. **Allow Once / Always Allow / Deny**
otherwise — the other gap that changelog flagged.

**`ui/sidebar.py`** *(new)* — Explorer: Open Folder button, a real
`DirectoryTree` once a folder's open, Pinned/Recent Projects (backed by
the new `calc_terminal/projects.py` store), a drag-and-drop hint area.
Collapsible (`Ctrl+B` or the header's `☰`) and always reopenable.
Honest limitation: no draggable resize splitter — Textual has no
built-in primitive for that, and faking the mouse-drag math without
being able to see it render is exactly the kind of guess this project's
own conventions avoid. `set_width()` exists for programmatic resizing.

**`ui/editor.py`** *(new)* — tabbed multi-file editor built on
Textual's own `TextArea.code_editor()`, which already provides syntax
highlighting, line numbers, current-line highlight, and undo/redo
natively — this file adds the tab strip, save-to-disk (`Ctrl+S`), and
an inline find/replace bar (`Ctrl+F`) on top, rather than reimplementing
any of that.

**`ui/workspace.py`** *(new)* — `WorkspaceShell`: Explorer + a tabbed
main area (Chat / Editor / Terminal / Problems / Output). Opening a
folder re-parents the app's *existing* `ConversationView` instance into
the Chat tab instead of creating a second one, so chat history/state
survives switching into IDE mode, and nothing changes for anyone who
never opens a folder. Terminal/Problems/Output are honestly-labeled
placeholders — there's no real shell/linter/build backend in this
codebase yet to wire them to.

**`ui/dashboard.py`** *(new)* — the Welcome Dashboard shown when no
folder is open: logo, version/GPU/model line, quick actions (Open
Folder / New Chat / Settings / Docs), Recent Projects, and Session
Notebooks/generated-file stats pulled from the real `projects.py` and
`calc_terminal/workspace.py` data. Honest gap: the spec's "Recent
Simulations / Calculations / Quantum Projects / Pinned Notes" sections
have no dedicated data store anywhere in this codebase — rather than
fabricating numbers, the dashboard only shows sections it can back with
real data.

**`ui/statusbar.py`**, **`ui/command_palette.py`**, **`ui/animations.py`**
*(new)* — the spec's project-structure list names these three files;
the engines they need (status-line rendering, fuzzy command matching +
live filtering, thinking/searching/responding spinners with elapsed
time) already existed, correctly, as `footer.StatusLine`,
`palette.CommandPalette`/`SuggestionEngine`, and `thinking.py`. These
three files extend those (richer fields incl. CPU/memory/Ollama
reachability; per-category command coloring; a self-driving
`AnimatedTick` widget) instead of duplicating logic that already works.

**`calc_terminal/projects.py`** *(new)* — small JSON-backed store for
recently-opened/pinned project folders, same pattern as `workspace.py`
and `config.py` rather than growing either.

**`ui/events.py`** — added `PermissionModeChanged`, `FolderOpened`,
`SidebarToggled`, `FileOpenRequested`, `FileSaved`, following this
package's existing "components only talk through events" convention.

**`ui/app.py`** — wires all of the above: new commands `/open [path]`,
`/sidebar`, `/find`; bindings `Ctrl+B` (sidebar), `Ctrl+S` (save),
`Ctrl+F` (find); `_open_folder()` mounts/reuses one `WorkspaceShell`;
`StatusLine` swapped for the richer `StatusBar`; the plain welcome
banner swapped for `WelcomeDashboard` on startup (both still live in
`conversation.py` unchanged — `show_dashboard`/`hide_dashboard` were
added there as new methods alongside the existing
`show_welcome`/`hide_welcome`, not instead of them).

**Version**: bumped `0.1.0`/`0.5.8` → `0.7.0` in `__init__.py` and
`calc_terminal/app.py` (this is the version the spec's own title names).

## Explicitly NOT done (spec sections with no real foothold to build on)

- Project-wide code indexing, git integration, or AI
  read/write/refactor/rename/delete file *actions* (the editor is
  human-driven; the AI doesn't call it yet — the permission-mode gate
  it would need already exists and is ready for this the moment such a
  tool is added, same note as the prior permissions changelog).
- A real integrated terminal (Problems/Output panels are placeholders,
  not backed by a shell/build system).
- True draggable-splitter resizing of the sidebar.
- Syntax highlighting for chemistry-specific formats (`.xyz`/`.pdb`/
  `.mol`/`.cif`) — they open as plain text in the editor; there's no
  tree-sitter grammar for them.

## Regression

Fallback (non-Textual) CLI path re-verified directly: `/permissions`
still renders correctly, `App()` still constructs and dispatches. The
existing `test_script.py` wasn't re-run end-to-end (it blocks on a real
tty via `input()`), but nothing it exercises was touched this session.
