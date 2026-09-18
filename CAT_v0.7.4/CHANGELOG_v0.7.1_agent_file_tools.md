# v0.7.1 (in progress) — Real permission-gated AI file operations

Scope of this slice: ONE full vertical feature from the v0.7.1 spec,
wired end-to-end and tested — not a pass over all 20 spec sections.
See the spec's own section 1 example card and section 20 ("prevent
path traversal") — this is what makes both real.

## What's new

- `calc_terminal/agent.py` — the AI agent can now actually touch the
  filesystem, with six new tools: `write_file`, `create_folder`,
  `delete_file`, `rename_file`, `read_file`, `list_directory`. Every
  mutating one goes through the same permission gate — no exceptions,
  no code path that bypasses it.
- `calc_terminal/workspace.py` — new `resolve_writable_path()`. Every
  file tool resolves through this before touching disk: relative
  paths land under the configured workspace root, absolute paths are
  honored as given, and anything that resolves into a system directory
  or outside both the workspace root and the user's home is refused
  with a clear `ValueError` (this is the actual path-traversal guard —
  the blocklist next to it is a named extra, not the real boundary).
- `calc_terminal/agent.py` — `run_agent()` now takes an optional
  `permission_callback`. When a mutating tool needs a prompt (per the
  existing three-mode system in `permissions.py` — Ask/Restricted/
  Full, unchanged), the loop calls back out *before* running the tool,
  and only executes it if the answer says to. No caller of
  `run_agent()` had to change to get this — the classic REPL
  (`calc_terminal/app.py`, 5 call sites) automatically gets a real
  inline permission card (styled like `code_editor.py`'s existing
  `_scan_and_confirm`) via a default terminal prompt, since none of
  those call sites pass their own callback.
- `calc_terminal/ui/app.py` (the primary Textual UI) — passes its own
  callback instead: the streaming worker thread posts a real
  `PermissionCard` into the conversation (via `call_from_thread`) and
  blocks on a `threading.Event` until a button press resolves it — the
  UI thread itself is never blocked. `on_permission_granted`/`_denied`
  now route to either the existing pre-turn gate or this new
  mid-agent-loop gate, whichever request_id they belong to.
- `calc_terminal/ui/permission_panel.py` — `PermissionCard` can now
  show an optional Path line (the spec's card example has one; the
  existing "Run Python" gate doesn't use it, so it's opt-in).

## Honestly out of scope for this slice

- The "Edit Path" button from the spec's example card isn't wired —
  cards show the resolved path but can't be edited inline yet.
- `delete_file` refuses folders on purpose (deletes single files only)
  to avoid one bad path wiping a whole tree; a real recursive
  folder-delete tool isn't implemented.
- This does not touch the File Explorer, drag-and-drop, Open Folder,
  main menu, or any of the other ~19 spec sections — see the earlier
  chat discussion for why those are a separate, much larger effort.

## Tests run (not shipped as a test suite, just verification for this reply)

Verified directly against the real filesystem (no AI provider needed):
path-resolution safety (workspace-relative, absolute, blocked system
paths, traversal attempts), write/read/list/rename/delete on real
files, and all three permission modes (`ask` deny / allow-once /
always-allow, `restricted` accept/reject framing, `full` silent
execution) — including confirming `allow_once` does NOT persist while
`always_allow` does. Also confirmed the classic REPL's default
terminal-based prompt renders and blocks correctly with no UI code
involved.

## Second slice: header permission control → real animated dropdown

The v0.7.1 spec's "PERMISSION SYSTEM (Highest Priority)" section asks
for "ONE permission button with an animated dropdown" showing all
three modes at once (icon, description, color, hover, keyboard nav,
smooth open/close) — not the click-to-cycle badge this UI had.

- `calc_terminal/ui/header.py` — `HeaderPermissionSelector` now opens
  `PermissionModeMenu` on click instead of cycling modes in place.
  `PermissionModeMenu` is a `textual.screen.Screen` push (same pattern
  `app.py`'s existing `_AttachPrompt`/`_PathPrompt` already use for
  "needs its own key handling"), top-anchored instead of centered so
  it reads as a dropdown under the header rather than a dialog.
  - Each of the three rows (`_PermMenuRow`) shows the mode's icon,
    colored label, and a one-line description; a check mark marks the
    currently-active mode.
  - Hover highlight is the existing `:hover` CSS pseudo-class trick
    already used elsewhere in this package; keyboard highlight
    (Up/Down/Tab/Shift+Tab) is tracked explicitly and applied as a
    `.cct-permmenu-row-selected` class, since arrow-key navigation
    isn't a real mouse hover.
  - Enter or a row click picks a mode and posts the same
    `PermissionModeChanged` event as before — `on_permission_mode_changed`
    in `app.py` did not need to change.
  - Escape, or a click on the dimmed backdrop, closes the menu without
    changing the mode.
  - Open animation: the box starts at `opacity: 0` / `offset-y: -2`
    and gets an `.open` class one frame after mount (via
    `call_after_refresh`), which Textual's CSS `transition` on those
    two properties animates smoothly.

### Deliberate convention break, called out on purpose

Every other interactive surface in this package (command palette,
permission cards, settings panel) is explicitly documented as "mounted
inline, never a popup" — `header.py` previously had a comment saying
exactly that was why the old badge just cycled instead of opening a
menu. This is the first widget in the package that behaves like a
floating dropdown. It still isn't a separate OS window (it's a Textual
`Screen` push, same mechanism as the two existing path-entry prompts),
but visually and functionally it is a dropdown, which the rest of the
package deliberately avoided until now. Worth knowing if a future pass
wants every menu-like control to work the same way, or wants this to
stay the one exception.

### Honestly out of scope / unverified in this slice

- **Not runtime-tested.** This container has no network access, so
  `textual` couldn't be installed here — everything above is verified
  by `python3 -m py_compile` only (confirmed clean), not by actually
  running the app. The click-outside-to-close handler in particular
  (`PermissionModeMenu.on_click`, keyed off `event.widget`) is written
  defensively but hasn't been exercised against a real Click event in
  this environment — Escape and row-click are the two interactions to
  trust first if something about backdrop-click doesn't behave as
  expected.
- The "Edit Path" button, and everything else this file's first slice
  already marked out of scope, remain out of scope.
- No other header field (Workspace/GPU/API/Time) changed — only the
  center permission control.
