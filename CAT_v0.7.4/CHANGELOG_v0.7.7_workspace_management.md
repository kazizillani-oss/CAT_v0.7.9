# v0.7.7 — Workspace Management Preview

CCT grows the real-IDE workspace layer: automatic workspace detection
on launch, a multi-workspace history (recent / pinned / favorite /
renamed / collapsed / searchable), a Folder Panel that no longer
closes when you click Open Folder, an AI workspace index with visible
progress notes in chat, persistent package-install history with the
professional install summary card, a Project Header strip, and one
unified design language for the new components.

The v0.7.7 Autonomous Development Preview build remains fully intact —
nothing that worked before this build was removed.

Spec-wide rules honored everywhere below:

- Detection, history, and indexing are honest: only real paths from
  real folders, only parsed content from real manifests, counts and
  caps documented — never fabricated data.
- History stores only paths/labels in JSON dotfiles; nothing on disk
  is ever moved or deleted by these features.
- The classic `/workspace <category>` generated-files browser keeps
  its exact old behavior.

---

## 1. Automatic Workspace Detection

New detection chain in `calc_terminal/workspace.py` (all additive):

- `app_directory()` — CCT's own source folder, so the detector never
  declares CCT itself to be the user's workspace.
- `detect_workspace(cwd)` returns the first valid workspace in this
  priority order: 1) the current working directory (when it isn't the
  app folder), 2) the VS Code workspace (a `*.code-workspace` file's
  folder paths, or a `.vscode/` marker), 3) the enclosing git
  repository root, 4) the directory CCT was launched from, 5) the
  last opened workspace. Pure function — never mutates state.
- `auto_load_workspace()` runs the chain once at startup: records the
  found workspace and makes it the active project root. The Textual
  UI calls it in `CCTApp.on_mount()` before the UI builds, so the
  header/status show the right workspace from the first frame; the
  app then auto-reopens the most recently opened project as before
  (v0.7.4 behavior, unchanged).
- `git_branch(path)` / `git_status_summary(path)` / `git_root(start)`
  — real `git` subprocess reads, never raising, None when not a repo.

## 2. Open Workspace — Main Menu Option

- The NavPanel's "Open Folder" menu item already pushed the
  `OpenWorkspaceScreen` picker (v0.7.4); this build keeps that, and
  the sidebar's own Open Folder button now does exactly the same
  thing — one picker, one behavior, everywhere.
- The picker (`ui/sidebar.py::OpenWorkspaceScreen`) keeps its modern
  compact design: manual path entry with live validation, a native
  Browse... folder dialog (tkinter, a separate OS dialog), recent
  workspaces, drag & drop hint, and keyboard shortcuts.

## 3. Folder Panel Improvement — It No Longer Closes

The reported bug: clicking "Open Folder" collapsed the Folder Panel.
Fixed:

- `_toggle_or_focus_explorer()` (ui/app.py) no longer toggles the
  Explorer closed. Open Folder now always pushes the picker over the
  app; the panel keeps whatever tree/workspace strip it had, so you
  can browse multiple folders without leaving the panel.
- After a folder is picked, `_ensure_explorer_visible()` expands the
  panel if it was collapsed and focuses the new folder's tree.
- Toggling still exists where it belongs: Ctrl+B and the sidebar
  chevron.

## 4. Multi-Workspace Management

- `calc_terminal/projects.py` (v0.7.7 additions, old API unchanged):
  per-workspace labels (`rename`/`label_for`), favorites
  (`toggle_favorite`/`is_favorite`/`favorites`), per-workspace
  sidebar collapse state (`set_collapsed`/`is_collapsed`), the
  combined `workspaces()` list (pinned + recent union with all
  metadata), `search()`, `remove()`, `clear_history()`,
  `last_opened()` — persisted to `~/.cct_recent_projects.json`.
- The Explorer sidebar gets a **Workspaces strip** (top of the
  Pinned/Recent block): every known workspace with its 📌/⭐ marks,
  click to switch to it in place (panel never closes), ✕ to remove
  it from history only.
- Per-workspace collapse: collapsing the tree remembers it, and
  reopening that workspace shows a "click to expand" row instead of
  the tree (`Explorer.toggle_collapsed` / `_CollapsedTreeRow`).
- Classic terminal: the full manager at `/workspace` — dashboard,
  `open <path>`, `list`/`history`, `add`, `remove`, `rename`,
  `pin`/`unpin`, `fav`/`unfav`, `last`, `search <q>`, `forget`,
  `detect`, and `open-current`. The old `/workspace <category>`
  generated-file browser and the original summary are preserved.

## 5. Workspace History

- Recent + pinned + favorite + last-opened + search + remove + clear,
  in both UIs: the sidebar Workspaces strip and `/workspace list`
  show the combined history; `/workspace last`, `search`, `remove`,
  `forget` cover the rest; the standalone Recent Workspaces picker
  (`RecentWorkspacesScreen`) still works unchanged.

## 6. AI Workspace Indexing (visible progress)

New `calc_terminal/workspace_index.py`:

- `index_project(path, on_progress=...)` scans the tree once (skipping
  `.git`/`node_modules`/`__pycache__`/`.venv`/`dist`/`build`/...),
  detects languages from the extension histogram, reads the README,
  parses real dependency manifests (requirements.txt, pyproject.toml,
  package.json, go.mod, Cargo.toml), detects package managers, and
  reads git branch/status. Bounded: 20k files max, 40 structure rows,
  40 dependencies, 2k README chars — honest, capped, never fabricated.
- Progress fires the spec's exact stages: `🔍 Scanning Workspace...`
  → `📖 Reading Files...` → `🛠 Building Context...` → `✅ Ready`.
- The Textual UI runs the index on every workspace open in a
  background worker; each stage lands in the chat as a system note,
  and completion posts "📂 Project Context — ready · <describe> ·
  indexed in Ns" plus the Project Header detail line. The classic
  REPL surfaces the same index through `/workspace open`.

## 7. Package Install Summary in Chat

- `packages.summarize()` is upgraded to the spec's professional card:
  ✅ Package Installed Successfully / Package / Version / Environment
  (Python + platform) / Dependencies Installed / Installation Time /
  Verification / conflicts line / Ready for use; and ❌ Package
  Installation Failed with the failing log tail and a suggested fix.
- The classic REPL prints the card in a panel after every install
  (unchanged call site); the agent tool flow streams the same card
  into chat (it already appended `summarize()` output), so the
  Textual UI shows it too.
- `run_install`'s result now carries `deps_installed` (counted from
  the installer's own "Successfully installed …" / "added N packages"
  lines, minus the requested package) and `conflicts` (mentions of
  conflicts in the output) — both read from real output only.

## 8. Package History

- `run_install` automatically records every outcome to
  `~/.cct_package_history.json` (`record_install`): package, version,
  manager, ok, environment, installed/updated timestamps, duration,
  verification, conflicts, exit code, and a short error tail.
- Reinstalls update the existing record (spec's Update semantics)
  instead of duplicating. Capped at 100 records.
- `package_history()`, `history_search(q)`, `history_entry(name)`,
  `remove_history(name)`, `clear_history()`.
- Classic terminal: `/packages history`, `/packages history <query>`,
  `/packages history remove <name>`, `/packages history clear` —
  newest first, ✓/✗ status, version, manager, date, environment,
  updated marker.

## 9. Project Header

- New `WorkspaceHeader` strip at the top of the Folder Panel
  (spec section 9): workspace name + git branch on the first line;
  indexed languages · file count · dependency count · package
  managers · memory turns · context % on the second.
- No duplicated widgets: model / AI mode / permission mode stay in
  their existing single homes (footer, header pill) — the Project
  Header shows only facts that aren't already on screen.

## 10. Design Language

- The new components follow one system: translucent `$surface-alt 35%`
  "glass" strip for the Project Header, and 150ms transitions on all
  new hover states (the spec's 120–180ms band — the existing
  OpenWorkspaceScreen animations were already 150/180ms).
- No new palette: every color is a `$variable` from theme_css.py.

## 11. Quality

- `python -m py_compile` clean on every touched file.
- Backend smoke tests: detection chain (cwd/VS Code/git/launch/last
  priority order), projects rename/favorite/pin/search/workspaces/
  last, index_project stages + languages/managers/deps/git, history
  record/search/remove round-trip, registry metadata, and both
  summarize() cards.
- Textual headless pilot (`App.run_test`): startup auto-detect, open
  folder → panel stays visible, Project Header renders real indexed
  data, Workspaces strip populated, picker push/pop clean, and the
  index worker completes without errors.

---

## Files touched in this build

- `calc_terminal/workspace.py` (additive: detection + git helpers)
- `calc_terminal/projects.py` (additive: labels/favorites/collapse/
  workspaces/search/remove/clear/last)
- `calc_terminal/workspace_index.py` (new)
- `calc_terminal/packages.py` (summary card, deps/conflicts analysis,
  history store)
- `calc_terminal/app.py` (Workspace Manager `/workspace`,
  `/packages history`, chat command suggestions)
- `calc_terminal/ui/sidebar.py` (WorkspaceHeader, Workspaces strip,
  per-workspace collapse)
- `calc_terminal/ui/app.py` (Open-Folder fix, picker-always flow,
  indexing worker, startup auto-detect, CSS)
- `calc_terminal/registry.py`, `calc_terminal/commands_data.py`
  (`/workspace` metadata/examples/description)
- `README.md`
