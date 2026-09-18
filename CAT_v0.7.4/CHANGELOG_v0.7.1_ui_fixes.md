# v0.7.1 UI Fixes (Post UI Review)

Three concrete bugs fixed from the review screenshots. No new features,
no scope beyond what was broken — per the standing rule for this
project, that stays out until it's phased and scoped on its own.

## 1. Header hover rendering glitch — fixed

`#cct-brand-title` had two separate CSS rules across `app.py`: one gave
it `height: 1; padding-top: 1`, the other gave it `width: auto;
padding-right: 2`. Combined, the title's box model was 2 rows tall
(1 content + 1 top padding) inside `#cct-header-top`, which is only
1 row tall. The overflow was invisible at rest but got painted as a
stray box the moment anything in that row triggered a repaint (e.g.
hovering the adjacent hamburger icon).

Fix: removed the conflicting rule, replaced `padding-top: 1` with
`content-align: left middle` (centers the text within the 1-row height
without growing the box), and added `overflow: hidden` to
`#cct-header-top` as a guard against this class of bug recurring.

## 2. Hamburger icon doing nothing — fixed (the specific bug, not the full nav-drawer ask)

The click handler (`on_sidebar_toggled` in `app.py`) only ever did
something when a workspace/folder was already open:

```python
def on_sidebar_toggled(self, event: SidebarToggled):
    if self._workspace_shell is not None:
        self._workspace_shell.explorer.toggle()
    # no else — silently did nothing otherwise
```

Since a fresh session has no folder open, clicking the hamburger was a
guaranteed no-op — that's the bug. Fixed by adding the same fallback
`action_toggle_sidebar` (the `ctrl+b` keyboard path) already had: it
now opens the folder picker instead of doing nothing.

**Not done:** the full slide-out navigation drawer described in the
review doc (Workspace/New Chat/Create Project/Documentation/Settings/
Extensions/MCP Servers/Themes/Keyboard Shortcuts/Command Palette/About,
a styled MCP Servers + Create Project button, a live theme selector,
slide/fade/blur/scale open animation). That's a large new feature, not
a bug fix, and it's the same shape of ask as the earlier "v0.7+ Major
Feature Specification" — it should go through the same phased,
one-slice-at-a-time process as the rest of the v0.7/v0.8 IDE work
rather than get bundled into a bugfix pass.

## 3. Permission dropdown wasting space — fixed

`#cct-permmenu-box` (the `Vertical` container in `PermissionModeMenu`)
never set an explicit `height`. Textual's `Vertical` defaults to
`height: 1fr` (fill available space), so the box stretched almost to
the bottom of the screen instead of wrapping its three rows — matching
the "big empty panel" in the screenshot exactly.

Fix: added `height: auto;` to `#cct-permmenu-box`. It now sizes to its
content (title + 3 mode rows), same compact feel as Cursor/VS Code/Warp.
