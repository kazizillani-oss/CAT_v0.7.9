# v0.7.4 — NavBar & Workspace Navigation Redesign

Complete redesign of the top-of-screen header and the "open the menu"
flow into a proper NavBar + structured navigation panel, plus fixes to
the editor and command palette this redesign surfaced.

## NavBar (`ui/header.py`, rewritten)

Three sections, and only three:

- **Left** — `MenuButton`, an animated ☰ → ✕ menu glyph (replaces the
  old plain hamburger), plus `Logo`, a cleaner single-hexagon CCT mark.
- **Center** — `PermissionPill`, a rounded, primary-action-styled
  button showing the live permission mode. No dropdown triangle in
  either state; hover/active states communicate "this opens something"
  instead.
- **Right** — the current workspace path, and nothing else. The old
  GPU/API/clock/context cluster is gone from the header (that
  information never belonged in the nav bar to begin with).

`BrandHeader.refresh_right()` now takes a single path string instead of
a list of status fields; `refresh_breadcrumb()` is a kept-for-compat
no-op since the second breadcrumb row no longer exists.

## NavPanel (`ui/header.py`, new)

Clicking the menu button no longer silently toggles the Explorer (which
did nothing useful when no folder was open yet). It now opens a real,
keyboard-navigable panel listing every top-level destination in the
app: Dashboard, Open Folder, Recent Workspaces, MCP Servers, Customize
AI, Diff Viewer, Settings, Themes, Extensions, Keyboard Shortcuts, Help.

Only **Open Folder** reaches for the system folder picker. Everything
else routes through the new `events.NavAction` message to
`CCTApp.on_nav_action`, which is the one place that decides what each
destination does:

- `dashboard` → re-shows the Welcome Dashboard
- `open_folder` → the existing `_PathPrompt` folder picker
- `recent_workspaces` → new `sidebar.RecentWorkspacesScreen`, a picker
  that works even before any folder has been opened this session
- `themes` → new `nav_screens.ThemesPanel` (dark/light — the one real
  toggle this build has)
- `settings` → new `nav_screens.SettingsPanel`, a live snapshot of
  permission mode / theme / workspace / model / AI mode
- `keyboard_shortcuts` → new `nav_screens.InfoPanel` listing the real
  `BINDINGS`
- `help` → same `InfoPanel`, listing `commands_data.COMMANDS`
- `mcp_servers` / `customize_ai` / `diff_viewer` / `extensions` → the
  same `InfoPanel`, clearly labeled as not wired to a real backend yet
  in this build (no MCP client, per-project AI-instruction store, diff
  engine, or plugin loader exists) — an honest placeholder, not
  fabricated data.

Ctrl+B / `action_toggle_sidebar` still show/hide the Explorer directly,
unchanged.

## Startup workspace auto-load (`ui/app.py`)

`CCTApp.on_mount` now calls `_autoload_last_workspace()`, which reopens
`projects.recent()[0]` (the most-recently-opened project — already
tracked on every Open Folder) if that path still exists on disk. Silent
no-op with no history or a since-deleted path.

## Editor fixes (`ui/editor.py`)

- **Blank-editor bug**: tab ids were built from
  `len(self._open_paths)`, which isn't monotonic once a tab closes
  (open A → id0, open B → id1, close A → dict len back to 1, open C →
  id1 again). A collision here can raise `DuplicateIds` inside
  `add_pane()`, which the caller never awaited or guarded — the new
  tab never finishes mounting, but `open_file()` had already reported
  success. Fixed with a strictly monotonic `self._tab_counter` that's
  never reused.
- Setting `tabs.active` right after `add_pane()` raced Textual's
  message pump (`add_pane()` only *schedules* the mount). Now deferred
  to `call_after_refresh`.
- **Unsaved-changes marking**: `self._dirty` was declared but never
  written to. `on_text_area_changed` now marks the file dirty as the
  user types; save/reload clear it. Best-effort `●` marker on the tab
  label itself, guarded since `Tab.label` isn't necessarily a
  documented setter across Textual versions.

Syntax highlighting, cursor position, and undo history were already
correct (native to `TextArea.code_editor()` and the same instance
persisting per open tab) — no change needed there.

## Command palette scrolling (`ui/palette.py`, `ui/command_palette.py`)

- Base class changed from `Vertical` to `VerticalScroll` — mouse wheel
  scrolling is now native, with a themed scrollbar.
- `SuggestionEngine.match()`'s limit raised from 8 to 40, since there's
  now somewhere for the extra rows to live.
- New `move_page(direction)` for PageUp/PageDown, wired in
  `composer.py`'s `ComposerInput._on_key`.
- Keyboard-driven selection now scrolls itself into view
  (`_scroll_selected_into_view`) instead of only re-painting.

## Sidebar polish (`ui/sidebar.py`, CSS in `ui/app.py`)

- New `RecentWorkspacesScreen` (see NavPanel above).
- Hover-state background/color transitions on project rows and Clear
  Recent Projects.
- Themed scrollbar (`scrollbar-color`/`scrollbar-size`) instead of
  Textual's flat default.

## Honest gaps carried forward

MCP Servers, Customize AI, Diff Viewer, and Extensions have no backing
engine in this codebase — they're clearly-labeled placeholders, not
simulated functionality. Drag & drop in the Explorer is still the
existing documented hint text, not real OS-level drag & drop (Textual
has no built-in primitive for that). Resizable sidebar dragging remains
out of scope for the same reason it was in v0.7.0 (no draggable-
splitter primitive to fake honestly).
