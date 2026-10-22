"""
CCT UI — header.py: the persistent NavBar docked at the very top of the
screen (v0.7.4 "AI-native IDE navigation" redesign).

Three sections, and only three (spec's own words: "The navigation bar
must contain ONLY three sections"):

  LEFT    animated menu button (MenuButton) + the CCT mark (Logo)
  CENTER  the Permission pill (PermissionPill) — a real button, not a
          form dropdown, with no triangle glyph
  RIGHT   the current workspace path, and nothing else — no GPU/API/
          clock cluster (those used to live in `refresh_right`; that
          method's contract is now "one path string", see below)

Opening the menu button no longer silently toggles the Explorer (that
surprised people who had no folder open yet, and conflated "browse the
IDE's own features" with "browse this project's files" — two different
jobs). It now opens NavPanel: a real, keyboard-navigable list of every
top-level destination in the app (Dashboard, Open Folder, Recent
Workspaces, MCP Servers, Personalize, Diff Viewer, Settings, Themes,
Extensions, Keyboard Shortcuts, Help). Only "Open Folder" reaches for
the system folder picker; everything else routes through
`events.NavAction` to CCTApp.on_nav_action, which is the one place
allowed to decide what each destination actually does — same one-way
event-flow convention every other component in ui/ already follows.

"Open Folder" and "Recent Workspaces" (the two destinations that end
in a system folder picker) KEEP the panel open when picked — the main
menu stays up after a folder is opened, per v0.7.4 — while every other
item dismisses as usual. The menu button's ✕ morph doubles as a close
control: clicking it while the panel is open closes the menu.

Explorer's own show/hide toggle still exists — it's just reached via
Ctrl+B (CCTApp.action_toggle_sidebar) or a NavPanel item, not by
re-purposing the header's menu glyph for it.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import os

from .. import permissions as perm
from .events import PermissionModeChanged, NavAction

TEXTUAL_AVAILABLE = True
try:
    from textual.containers import Vertical, Horizontal
    from textual.screen import Screen
    from textual.widgets import Static, Button
except Exception:
    TEXTUAL_AVAILABLE = False

_MARK = "\u2b21"  # WHITE HEXAGON — a molecule/benzene-ring silhouette,
                  # a cleaner and more legible brand mark at 1-cell size
                  # than the previous alembic glyph.

# spec v0.7 Header section: three selectable modes.
_MODE_ORDER = ("ask", "restricted", "full")

_MODE_DESCRIPTIONS = {
    "ask": "Ask me before protected actions.",
    "restricted": "Analyze and help, but block protected actions.",
    "full": "Work automatically within my allowed workspace.",
}
_MODE_TONE = {"ask": "text", "restricted": "warning", "full": "success"}

# Permission mode icons for the selector
_MODE_ICONS = {"ask": "\U0001f510", "restricted": "\U0001f6e1", "full": "\u26a1"}

# NavPanel items: (action id, icon, label). v0.7.8.1 cleanup: "New
# Workspace" / "Save Workspace" / "Close Workspace" are gone — opening a
# folder already records it in Recent Workspaces automatically, so those
# three were redundant in a terminal IDE. The menu is now exactly:
# Open Folder / Recent Workspaces / Chats, then Integrations, then
# Settings / Account section.
# v0.7.9.10: Gestures / Vision / Personalize are Extensions — they appear
# in the main menu only when enabled via Extensions panel (see
# extensions.should_show_in_menu). This keeps the main menu uncluttered
# and lets users install/uninstall via Extensions.
_NAV_ITEMS_BASE = (
    ("open_folder", "\U0001f4c1", "Open Folder"),
    ("recent_workspaces", "\U0001f553", "Recent Workspaces"),
    ("chats", "\U0001f4ac", "Chats"),
    ("sep1", "", ""),
    ("mcp_servers", "\U0001f50c", "MCP Servers"),
    ("backup_providers", "\U0001f4e1", "Backup Providers"),
    ("sep2", "", ""),
    ("customize_ai", "🎨", "Personalize"),
    ("themes", "\u25d1", "Themes"),
    ("gestures", "\u270b", "Gestures"),
    ("extensions", "\u25a3", "Extensions"),
    ("sep3", "", ""),
    ("user", "\u263a", "Users"),
    ("signout", "\u238b", "Sign Out"),
)

def get_nav_items():
    """Filtered NAV_ITEMS for current extensions state.

    v0.7.9.12: Gestures / CAT Vision / Personalize are now grouped in the
    dedicated 'Downloaded Extensions' section at the bottom of the main
    menu instead of being scattered in the top list. This removes the
    previous duplication where they appeared both in the top scattered
    positions AND again in Downloaded (2×). Install → appears in
    Downloaded as '●', disable → stays in Downloaded as '○' (still
    reachable to re-enable), uninstall → removed. Other items use
    should_show_in_menu filtering as before.
    """
    try:
        from .. import extensions as _ext
        # --- base items (excluding builtin extensions — they are grouped) ---
        # Builtin extension actions are handled exclusively in the Downloaded
        # section to avoid scattering + duplication. Compute dynamically so
        # future builtins are also grouped without hard-coding.
        try:
            builtin_actions = {v.get("action") for v in _ext.BUILTIN_EXTENSIONS.values() if v.get("action")}
        except Exception:
            builtin_actions = {"gestures", "vision", "customize_ai"}
        out = []
        for action, icon, label in _NAV_ITEMS_BASE:
            if action.startswith("sep"):
                out.append((action, icon, label))
                continue
            if action in builtin_actions:
                # grouped in Downloaded Extensions — skip scattered position
                continue
            if not _ext.should_show_in_menu(action):
                continue
            out.append((action, icon, label))

        # Check customization main_menu settings (Section 14)
        try:
            from .. import customization as _cust
            if _cust.is_active():
                _mm = _cust.get_manager().get_main_menu()
                _mm_vis = _mm.get("visibility", {})
                _mm_order = _mm.get("order", [])
                if _mm_vis:
                    out = [it for it in out if it[0].startswith("sep") or _mm_vis.get(it[0], True) is not False]
                if _mm_order:
                    def _key(it):
                        act = it[0]
                        return _mm_order.index(act) if act in _mm_order else 999
                    seps = [it for it in out if it[0].startswith("sep")]
                    non_seps = [it for it in out if not it[0].startswith("sep")]
                    non_seps.sort(key=_key)
                    out = non_seps + seps
        except Exception:
            pass

        # collapse consecutive seps and trim leading/trailing seps
        filtered = []
        prev_sep = True  # treat start as sep to trim leading
        for item in out:
            is_sep = item[0].startswith("sep")
            if is_sep and prev_sep:
                continue
            filtered.append(item)
            prev_sep = is_sep
        while filtered and filtered[-1][0].startswith("sep"):
            filtered.pop()

        # --- Downloaded Extensions section (v0.7.9.12) ---
        # Grouped section at the bottom that always appears so users can
        # see what is downloaded/installed and jump directly to it.
        # Enabled builtins use their original action id (so nav_has checks
        # still pass and clicking opens the panel directly); disabled
        # builtins and all custom extensions use 'ext:<id>' with ○ hint
        # (so disabled does not count as visible for should_show_in_menu
        # tests but remains reachable to re-enable).
        try:
            installed = []
            if hasattr(_ext, "list_installed"):
                try:
                    installed = _ext.list_installed()
                except Exception:
                    installed = []
            if not installed:
                try:
                    installed = [m for m in _ext.list_extensions() if m.get("installed")]
                except Exception:
                    installed = []
            try:
                installed = sorted(installed, key=lambda m: (m.get("display_name") or m.get("name") or m.get("id", "")).lower())
            except Exception:
                pass

            dl_extra = []
            if filtered and not filtered[-1][0].startswith("sep"):
                dl_extra.append(("sep_dl", "", ""))
            count = len(installed)
            hdr_label = f"Downloaded Extensions ({count})" if count else "Downloaded Extensions"
            dl_extra.append(("__section_dl", "📦", hdr_label))
            if installed:
                for m in installed:
                    eid = m.get("id")
                    if not eid:
                        continue
                    icon = m.get("icon", "▣")
                    name = m.get("display_name") or m.get("name") or eid
                    enabled = bool(m.get("enabled"))
                    # For builtins use original action when enabled (so
                    # main-menu tests and direct panel open still work),
                    # otherwise use ext: prefix with disabled hint.
                    builtin_meta = _ext.BUILTIN_EXTENSIONS.get(eid) if hasattr(_ext, "BUILTIN_EXTENSIONS") else None
                    if builtin_meta and enabled:
                        action_id = builtin_meta.get("action") or f"ext:{eid}"
                        # no suffix needed — enabled is the normal visible state
                        label = name
                    else:
                        suffix = " \u25cf" if enabled else " \u25cb"
                        max_len = 28 - len(suffix)
                        if len(name) > max_len:
                            name = name[:max_len - 1] + "\u2026"
                        label = f"{name}{suffix}"
                        action_id = f"ext:{eid}"
                    dl_extra.append((action_id, icon, label))
            else:
                dl_extra.append(("__placeholder_dl", "", "No extensions installed"))
                dl_extra.append(("__hint_dl", "", "Install from Extensions \u2192"))
            filtered = filtered + dl_extra
        except Exception:
            pass

        return tuple(filtered)
    except Exception:
        return _NAV_ITEMS_BASE

# Backward compat: NAV_ITEMS remains as filtered view for old importers
# that do `from header import NAV_ITEMS`. At import time extensions are
# all enabled (empty config), so this equals the filtered view anyway.
NAV_ITEMS = get_nav_items()


if TEXTUAL_AVAILABLE:

    class _Clickable(Static):
        """A Static that reports clicks to a callback — the same minimal
        pattern footer.py's `_Badge` already uses, kept local here so
        header.py doesn't need to import from footer.py for one thing."""

        def __init__(self, text, widget_id, on_click=None, classes=""):
            super().__init__(text, id=widget_id, classes=classes)
            self._on_click = on_click

        def on_mouse_down(self, event):
            self.add_class("-active")

        def on_mouse_up(self, event):
            self.remove_class("-active")

        def on_leave(self, event):
            self.remove_class("-active")

        def on_blur(self, event):
            self.remove_class("-active")

        def on_click(self, event):
            self.remove_class("-active")
            if self._on_click:
                self._on_click()

    # ---------------------------------------------------------- nav panel --
    class _NavRow(Static):
        """One row of NavPanel: icon + label. Hover is free via CSS
        `:hover`; keyboard-driven highlight is applied explicitly via
        the `selected` class from the parent screen (same split
        PermissionModeMenu's `_PermMenuRow` already uses, since arrow-key
        movement isn't a real mouse hover)."""

        def __init__(self, action_id, icon, label, index):
            super().__init__("", classes="cct-navmenu-row")
            self.action_id = action_id
            self._icon = icon
            self._label = label
            self.index = index

        def on_mount(self):
            self.redraw()

        def redraw(self):
            from . import theme_css
            text_color = theme_css.current_hex("text")
            self.update(f"[{text_color}]{self._icon}  {self._label}[/]")

        def on_click(self, event):
            # v0.7.6 Patch 1: only act while the panel is still the
            # active screen (see _PermMenuRow.on_click for the
            # re-delivered-click explanation).
            if self.app.screen is self.screen:
                self.screen.on_row_picked(self.action_id)

    class NavPanel(Screen):
        """The structured navigation panel opened by MenuButton (spec
        v0.7.4 "PRIMARY GOALS #2"). Top-left-anchored so it visually
        drops down from the menu button rather than reading as a
        centered dialog — same real-Screen-push-as-modal pattern this
        package already uses for PermissionModeMenu, _AttachPrompt, and
        _PathPrompt.

        v0.7.4's "Main Menu stays open after opening a folder": the two
        destinations that lead to a system folder picker ('open_folder',
        'recent_workspaces') keep the panel open and post NavAction
        directly, so the user can immediately pick another destination
        when the picker returns. Every other item dismisses the panel as
        usual (the dismiss callback then posts NavAction).

        v0.7.9.10: Gestures / Vision / Personalize are Extensions — this
        panel now builds from get_nav_items() so disabled extensions are
        hidden here until re-enabled via Extensions panel."""

        # Destinations that keep the menu open instead of dismissing.
        _KEEP_OPEN = {"open_folder", "recent_workspaces"}

        CSS = """
        NavPanel { align: left top; background: $app-background 0%; }
        #cct-navmenu-box {
            margin-top: 3; margin-left: 1;
            width: 42; height: auto;
            max-height: 88%;
            background: $surface;
            border-top: tall $surface-highlight;
            border-left: tall $surface-highlight;
            border-bottom: tall $surface-dark;
            border-right: tall $surface-dark;
            padding: 1 0;
            opacity: 1; offset-y: 0;
            overflow-y: auto;
            scrollbar-gutter: stable;
            scrollbar-size: 1 1;
            scrollbar-color: $border $surface;
        }
        #cct-navmenu-box.open { opacity: 1; offset-y: 0; }
        .cct-navmenu-row {
            height: 1; padding: 0 2;
            background: $surface;
            color: $text;
            border-left: thick $surface;
            border-right: thick $surface;
        }
        .cct-navmenu-row:hover {
            background: $surface-alt;
            color: $text;
            border-left: thick $accent;
            border-right: thick $surface-alt;
            text-style: none;
        }
        .cct-navmenu-row-selected {
            background: $surface-highlight;
            color: $text;
            border-left: thick $accent;
            border-right: thick $surface-highlight;
            text-style: none;
        }
        .cct-navmenu-sep {
            height: 1; background: $surface; color: $border; padding: 0 2;
            border-left: thick $surface; border-right: thick $surface;
        }
        .cct-navmenu-section {
            height: 1; color: $accent; text-style: bold; padding: 0 2;
            background: $surface-alt;
            border-bottom: solid $border;
            border-left: thick $surface-alt; border-right: thick $surface-alt;
        }
        .cct-navmenu-placeholder {
            height: 1; background: $surface; color: $text-muted; padding: 0 2; text-style: italic;
            border-left: thick $surface; border-right: thick $surface;
        }
        .cct-navmenu-hint {
            height: 1; background: $surface; color: $text-faint; padding: 0 2;
            border-left: thick $surface; border-right: thick $surface;
        }
        .cct-touch-mode .cct-navmenu-row { min-height: 2; height: 2; content-align: left middle; }
        .cct-touch-mode .cct-navmenu-row:hover,
        .cct-touch-mode .cct-navmenu-row:focus {
            background: $surface-alt; color: $text;
            border-left: thick $accent; border-right: thick $surface-alt;
        }
        """

        def __init__(self):
            super().__init__()
            self._selected = None  # action_id of selected row
            self._nav_cache = None

        def _get_filtered(self):
            try:
                return get_nav_items()
            except Exception:
                return _NAV_ITEMS_BASE

        def compose(self):
            items = self._get_filtered()
            self._nav_cache = items
            # No default forced text selection on open; keyboard navigation activates it on demand
            with Vertical(id="cct-navmenu-box"):
                for i, (action_id, icon, label) in enumerate(items):
                    if action_id.startswith("sep"):
                        yield Static("\u2500" * 30, id=f"cct-navmenu-sep-{i}",
                                     classes="cct-navmenu-sep")
                    elif action_id.startswith("__section"):
                        yield Static(f"{icon}  {label}", id=f"cct-navmenu-section-{i}",
                                     classes="cct-navmenu-section")
                    elif action_id.startswith("__placeholder") or action_id.startswith("__hint"):
                        cls = "cct-navmenu-placeholder" if "placeholder" in action_id else "cct-navmenu-hint"
                        yield Static(label, id=f"cct-navmenu-placeholder-{i}", classes=cls)
                    else:
                        yield _NavRow(action_id, icon, label, i)

        def on_mount(self):
            self._sync_selected_class()
            try:
                self.query_one("#cct-navmenu-box").add_class("open")
            except Exception:
                pass

        def _sync_selected_class(self):
            for row in self.query(_NavRow):
                row.set_class(row.action_id == self._selected, "cct-navmenu-row-selected")

        def on_row_picked(self, action_id):
            """Shared by mouse clicks and the Enter key. Keep-open
            destinations post NavAction and leave the panel up; the
            rest dismiss, which triggers the usual push callback."""
            if action_id in self._KEEP_OPEN:
                self.post_message(NavAction(action_id))
                return
            self.dismiss(action_id)

        def _nav_items(self):
            """Return only the selectable (non-separator) filtered items."""
            items = self._get_filtered()
            return [(i, a, ic, l) for i, (a, ic, l) in enumerate(items)
                    if not a.startswith("sep") and not a.startswith("__")]

        def on_key(self, event):
            items = self._nav_items()
            if not items:
                return
            cur_ids = [a for _, a, _, _ in items]
            if event.key == "escape":
                self.dismiss(None)
            elif event.key in ("down", "tab"):
                if self._selected not in cur_ids:
                    cur_idx = 0
                else:
                    cur_idx = (cur_ids.index(self._selected) + 1) % len(items)
                self._selected = items[cur_idx][1]
                self._sync_selected_class()
            elif event.key in ("up", "shift+tab"):
                if self._selected not in cur_ids:
                    cur_idx = len(items) - 1
                else:
                    cur_idx = (cur_ids.index(self._selected) - 1) % len(items)
                self._selected = items[cur_idx][1]
                self._sync_selected_class()
            elif event.key == "enter":
                if self._selected:
                    self.on_row_picked(self._selected)

        def on_click(self, event):
            # Click on the dimmed backdrop (outside the box) closes the
            # panel without picking anything — rows handle their own
            # clicks (see _NavRow.on_click). v0.7.6 Patch 1: only
            # dismiss while the panel is still the active screen.
            if getattr(event, "widget", None) in (self, None) and self.app.screen is self:
                self.dismiss(None)

    class MenuButton(_Clickable):
        """Left-of-header menu button (spec: "Modern animated menu
        button, replace the existing hamburger icon"). Morphs
        ≡ -> ✕ while NavPanel is open, with a smooth color transition
        on both states and on hover, instead of a static glyph. While
        the panel is open the button is that ✕: clicking it closes the
        menu (toggle behavior), so the ✕ is a real close control.

        The closed-state glyph is U+2261 IDENTICAL TO (≡) — a cleaner
        three-bar menu mark than the U+2630 TRIGRAM (☰) it replaces:
        the trigram renders with uneven bar lengths and baseline
        offsets in several common terminal fonts, which read as a
        glitchy/off-center hamburger; ≡ is three uniform, crisp lines
        in every font that has it (and it's far more widely covered
        than the trigram block)."""

        # U+2261 — clean three-bar menu mark.
        _MENU_GLYPH = "\u2261"
        _CLOSE_GLYPH = "\u2715"

        def __init__(self, id="cct-menu-btn"):
            super().__init__(self._MENU_GLYPH, widget_id=id, classes="cct-menu-btn")
            self._open = False

        def on_click(self, event):
            # v0.7.6 Patch 1: stop the opening click from bubbling to
            # the freshly pushed NavPanel's backdrop.
            event.stop()
            if self._open:
                self.close_menu()
            else:
                self.open_menu()

        def open_menu(self):
            """Opens NavPanel — shared by the click handler and the
            Ctrl+M binding, so keyboard and mouse go through one path
            and the button's ≡→✕ morph stays in sync either way."""
            if self._open:
                return
            self._open = True
            self.update(self._CLOSE_GLYPH)
            self.add_class("cct-menu-btn-active")
            self.app.push_screen(NavPanel(), self._on_closed)

        def close_menu(self):
            """Closes the open NavPanel (used by the ✕-morph click and
            Ctrl+M's close branch) — the panel's dismiss callback
            restores the ≡ glyph and posts the picked action."""
            for screen in list(self.app.screen_stack):
                if isinstance(screen, NavPanel):
                    screen.dismiss(None)
                    return

        def _on_closed(self, action_id):
            self._open = False
            self.update(self._MENU_GLYPH)
            self.remove_class("cct-menu-btn-active")
            if action_id:
                self.post_message(NavAction(action_id))

    class Logo(Static):
        """The CAT mark (spec: "Redesigned logo with a cleaner, more
        recognizable identity"). A single hexagon glyph + bold wordmark,
        no subtitle crowding the compact one-line nav bar — the fuller
        "Coding Agent Terminal" subtitle still appears once on the
        Welcome Dashboard (conversation.py), not here."""

        def __init__(self, id="cct-logo"):
            super().__init__("", id=id, classes="cct-logo")

        def on_mount(self):
            self.redraw()

        def redraw(self):
            from . import theme_css
            accent = theme_css.current_hex("accent")
            self.update(f"[{accent} b]{_MARK} CAT[/]")

    # ------------------------------------------------------ permission pill --
    class _PermMenuRow(Static):
        """One row of the permission dropdown: icon + label (colored
        per-mode) on top, faint description underneath."""

        def __init__(self, mode, index):
            super().__init__("", classes="cct-permmenu-row")
            self.mode = mode
            self.index = index

        def on_mount(self):
            self.redraw()

        def redraw(self):
            from . import theme_css
            color = theme_css.current_hex(_MODE_TONE[self.mode])
            faint = theme_css.current_hex("text-faint")
            plain_label = perm.manager.plain_mode_label(self.mode)
            icon = {"ask": "\U0001f512", "restricted": "\U0001f7e1", "full": "\u26a1"}.get(self.mode, "\u25cf")
            desc = _MODE_DESCRIPTIONS[self.mode]
            check = " \u2713" if self.mode == perm.manager.mode else ""
            self.update(f"[{color} b]{icon} {plain_label}{check}[/]\n  [{faint}]{desc}[/]")

        def on_click(self, event):
            # v0.7.6 Patch 1: guard against a click being delivered to
            # this menu after it was already dismissed (the same click
            # that closed it can be re-delivered to the popped screen —
            # double-dismiss then hits an empty screen stack). A row
            # click only acts while the menu is still the active screen.
            if self.app.screen is self.screen:
                self.screen.dismiss(self.mode)

    class PermissionModeMenu(Screen):
        """The dropdown itself (spec: "Options: Ask Every Time /
        Restricted / Full Access", each with icon/description/color,
        hover + selection + keyboard-nav + open/close animation).

        Real anchored popup, not a centered dialog: takes the trigger
        widget (the PermissionPill) at construction time and, on mount
        (and again on every terminal resize while it's open), reads
        that widget's live `region` — screen-absolute coordinates,
        recomputed fresh each time rather than cached — to place the
        box directly under the pill via `styles.offset`. Previously
        this used `align: center top` + a fixed `margin-top: 3`, which
        is why the popup always rendered centered/floating in the
        middle of the screen instead of next to the button, and never
        adapted to resizes or the button's real position — the root
        cause of the reported positioning bugs. Edge collision is
        handled explicitly: the box is clamped so it never renders
        past the right or bottom edge of the terminal, and flips to
        open *above* the pill instead of below when there isn't enough
        room underneath. `align: left top` on the Screen makes (0, 0)
        the coordinate origin so the computed offset is truly
        absolute, rather than fighting a centering rule."""

        CSS = """
        PermissionModeMenu {
            align: left top;
            background: $app-background 60%;
        }
        #cct-permmenu-box {
            width: 50;
            height: auto;
            background: $surface;
            border-top: tall $surface-highlight;
            border-left: tall $surface-highlight;
            border-bottom: tall $surface-dark;
            border-right: tall $surface-dark;
            padding: 1 1;
            opacity: 1; offset-y: 0;
        }
        #cct-permmenu-box.open { opacity: 1; offset-y: 0; }
        .cct-permmenu-title {
            color: $accent;
            text-style: bold;
            padding: 0 1 1 1;
            border-bottom: solid $border;
            margin-bottom: 1;
        }
        .cct-permmenu-row {
            height: 3;
            padding: 0 1;
            background: $surface;
            border-left: thick $surface;
            border-right: thick $surface;
        }
        .cct-permmenu-row:hover {
            background: $surface-alt;
            color: $accent;
            border-left: thick $accent;
            border-right: thick $surface-alt;
        }
        .cct-permmenu-row-selected {
            background: $surface-highlight;
            border-left: thick $accent;
            border-right: thick $surface-highlight;
            text-style: bold;
        }
        .cct-permmenu-row-focused {
            background: $surface-alt;
            border-left: thick $accent;
            border-right: thick $surface-alt;
        }
        """

        _BOX_WIDTH = 48
        # Fallback estimate for the box's height before Textual has had
        # a chance to lay it out for real (title row + 3 cells/mode row).
        _ESTIMATED_HEIGHT = 1 + 2 + len(_MODE_ORDER) * 3

        def __init__(self, anchor=None):
            super().__init__()
            self._selected = _MODE_ORDER.index(perm.manager.mode)
            # The PermissionPill that triggered this menu, so the popup
            # can anchor to its actual on-screen position instead of
            # being centered. `None` is a safe fallback (falls back to
            # the old centered-under-header placement) for any caller
            # that doesn't have a trigger widget handy.
            self._anchor = anchor

        def compose(self):
            with Vertical(id="cct-permmenu-box"):
                yield Static("\U0001f510 Access", classes="cct-permmenu-title")
                for i, mode in enumerate(_MODE_ORDER):
                    yield _PermMenuRow(mode, i)

        def on_mount(self):
            self._sync_selected_class()
            self._reposition()
            self.call_after_refresh(self._reposition)  # box has real height now
            self.call_after_refresh(lambda: self.query_one("#cct-permmenu-box").add_class("open"))

        def on_resize(self, event):
            """Terminal resized while the menu is open: re-read the
            anchor's (possibly moved) region and re-clamp so the popup
            never ends up outside the new terminal bounds."""
            self._reposition()

        def _reposition(self):
            try:
                box = self.query_one("#cct-permmenu-box")
            except Exception:
                return
            screen_w, screen_h = self.size.width, self.size.height
            if not screen_w or not screen_h:
                return
            box_w = self._BOX_WIDTH
            box_h = box.size.height or self._ESTIMATED_HEIGHT

            if self._anchor is not None:
                region = self._anchor.region
                x, y = region.x, region.y + region.height
            else:
                x, y = (screen_w - box_w) // 2, 3

            # Edge collision, horizontal: never let the box run past
            # the right edge (or, on a very narrow terminal, the left).
            x = max(0, min(x, max(0, screen_w - box_w)))

            # Edge collision, vertical: prefer opening below the
            # anchor, but flip to above it when there isn't enough
            # room underneath; then clamp to the terminal's height.
            if self._anchor is not None and y + box_h > screen_h:
                above = region.y - box_h
                y = above if above >= 0 else max(0, screen_h - box_h)
            y = max(0, min(y, max(0, screen_h - box_h)))

            box.styles.offset = (x, y)

        def _sync_selected_class(self):
            for row in self.query(_PermMenuRow):
                row.set_class(row.index == self._selected, "cct-permmenu-row-selected")

        def on_key(self, event):
            if event.key == "escape":
                self.dismiss(None)
            elif event.key in ("down", "tab"):
                self._selected = (self._selected + 1) % len(_MODE_ORDER)
                self._sync_selected_class()
            elif event.key in ("up", "shift+tab"):
                self._selected = (self._selected - 1) % len(_MODE_ORDER)
                self._sync_selected_class()
            elif event.key == "enter":
                self.dismiss(_MODE_ORDER[self._selected])

        def on_click(self, event):
            # v0.7.6 Patch 1: only dismiss while this menu is still the
            # active screen. The click that opened the menu can be
            # re-delivered here after the menu already popped; a second
            # dismiss would then hit an empty screen stack and raise
            # ScreenStackError ("Can't pop screen").
            if getattr(event, "widget", None) in (self, None) and self.app.screen is self:
                self.dismiss(None)

    class FullAccessConfirmScreen(Screen):
        CSS = """
        FullAccessConfirmScreen { align: center middle; background: $app-background 60%; }
        #fullaccess-box {
            width: 60; height: auto; background: $surface; border: round $warning;
            padding: 1 2; align: center middle;
        }
        #fullaccess-title { color: $warning; text-style: bold; height: 1; }
        #fullaccess-body { color: $text; height: auto; padding: 1 0; }
        #fullaccess-btns { height: 3; align: center middle; }
        #fullaccess-btns Button { margin: 0 1; }
        """
        def compose(self):
            with Vertical(id="fullaccess-box"):
                yield Static("Enable Full Access?", id="fullaccess-title")
                yield Static(
                    "CAT will be able to perform permitted workspace actions\n"
                    "without asking each time. Scope: current CAT workspace.\n"
                    "You can change this at any time.",
                    id="fullaccess-body")
                with Horizontal(id="fullaccess-btns"):
                    yield Button("Cancel", id="fullaccess-cancel", classes="cct-btn")
                    yield Button("Enable Access", id="fullaccess-ok", variant="primary", classes="cct-btn")
        def on_button_pressed(self, event):
            self.dismiss(event.button.id == "fullaccess-ok")
        def on_key(self, event):
            if event.key == "escape":
                self.dismiss(False)

    class PermissionPill(_Clickable):
        """Center-of-header permission control (spec: "large rounded
        Permission button... Remove the default dropdown triangle...
        Style it as a primary action button rather than a form
        widget"). No ▲/▼ glyph in either state — the pill's rounded
        border + background swap on click/focus is what communicates
        "this opens something", the same way a real button in Warp or
        VS Code's command palette doesn't need a caret to read as
        pressable."""

        def __init__(self, id="cct-perm-pill"):
            super().__init__("", widget_id=id, classes="cct-perm-pill")
            self._open = False

        def on_mount(self):
            self.refresh_label()

        def on_click(self, event):
            # v0.7.6 Patch 1: stop the opening click from bubbling —
            # otherwise the new menu screen can receive the same click
            # as a backdrop hit and instantly close itself.
            event.stop()
            if self._open:
                return
            self._open = True
            self.add_class("cct-perm-pill-active")
            self.refresh_label()
            self.app.push_screen(PermissionModeMenu(anchor=self), self._on_menu_closed)

        def _on_menu_closed(self, chosen):
            if not self._open:
                return
            self._open = False
            self.remove_class("cct-perm-pill-active")
            if chosen and chosen != perm.manager.mode:
                if chosen == "full":
                    # Full Access requires confirmation
                    self.app.push_screen(FullAccessConfirmScreen(), lambda ok: self._apply_mode(chosen) if ok else self.refresh_label())
                    return
                self._apply_mode(chosen)
            self.refresh_label()

        def _apply_mode(self, mode):
            perm.manager.set_mode(mode)
            self.post_message(PermissionModeChanged(mode))
            self.refresh_label()
            try:
                from .. import workspace as _ws
                ws = _ws.root_dir() if hasattr(_ws, 'root_dir') else "workspace"
                scope = ws if mode == "full" else ""
                note = f"Access: {perm.manager.mode_label()}" + (f"  Scope: {scope}" if scope else "")
                self.app._system_note(note)
            except Exception:
                pass

        def refresh_label(self, compact=None):
            from . import theme_css
            if compact is not None:
                self._compact = compact
            is_compact = getattr(self, "_compact", False)
            mode = perm.manager.mode
            color = theme_css.current_hex(_MODE_TONE[mode])
            icon = {"ask": "\U0001f512", "restricted": "\U0001f7e1", "full": "\u26a1"}.get(mode, "\u25cf")
            if is_compact:
                self.update(f"{icon}")
            else:
                plain_label = perm.manager.plain_mode_label()
                self.update(f"{icon} [{color} b]{plain_label}[/]")
            # tooltip for current mode
            try:
                self.tooltip = _MODE_DESCRIPTIONS.get(mode, "")
            except Exception:
                pass

    # Back-compat aliases: older code (and any external caller) that
    # still imports the pre-redesign names keeps working unchanged.
    HeaderPermissionSelector = PermissionPill
    SidebarToggleGlyph = MenuButton

    class BrandHeader(Vertical):
        """The NavBar. Exactly one row, height 3: MenuButton + Logo
        (left) / PermissionPill (center) / workspace path (right).

        The old second breadcrumb row (Notebook mode · model · context)
        is gone — the spec is explicit that the bar holds only three
        sections and the right side shows only the workspace path.
        `refresh_breadcrumb`/`refresh_right` are kept as thin methods
        (rather than deleted outright) so callers elsewhere in app.py
        don't need simultaneous surgery just to keep importing cleanly;
        `refresh_right` now expects a single path string, not a list of
        status fields.
        """

        def __init__(self, subtitle="Coding Agent Terminal", id="cct-brandheader"):
            super().__init__(id=id)
            self._subtitle = subtitle
            self._workspace_path = None  # None = never painted, forces first render
            self._current_chat_title = "New Chat"

        def _show_workspace_info(self):
            try:
                info_lines = [f"Path: {self._workspace_path or 'No workspace open'}"]
                try:
                    from .. import workspace as _ws
                    from ..workspace_index import index_project
                    root = self._workspace_path
                    if root and root != "No workspace open" and os.path.isdir(root):
                        idx = index_project(root)
                        info_lines.append(f"Files: {idx.get('file_count', '?')}")
                        langs = idx.get("languages") or []
                        if langs:
                            info_lines.append("Languages: " + ", ".join(langs))
                        pms = idx.get("package_managers") or []
                        if pms:
                            info_lines.append("Managers: " + ", ".join(pms))
                except Exception:
                    pass
                from .nav_screens import InfoPanel
                self.app.push_screen(InfoPanel("Workspace", info_lines))
            except Exception:
                pass

        def _on_chat_title_click(self):
            try:
                self.post_message(NavAction("chats"))
            except Exception:
                pass

        def set_chat_title(self, title: str):
            """Updates the current chat title shown in the header pill."""
            clean = (title or "New Chat").strip()
            if len(clean) > 28:
                clean = clean[:27] + "\u2026"
            self._current_chat_title = title or "New Chat"
            try:
                w = self.query_one("#cct-chat-title-pill", Static)
                from . import theme_css
                accent = theme_css.current_hex("accent")
                w.update(f"[{accent}]\U0001f4ac[/] {clean}")
                try:
                    w.tooltip = f"Chat: {title}\nClick to view all chats"
                except Exception:
                    pass
            except Exception:
                pass

        def compose(self):
            with Horizontal(id="cct-header-top"):
                with Horizontal(id="cct-header-left"):
                    yield MenuButton()
                    yield Logo()
                yield Static("", id="cct-header-spacer-left")
                yield PermissionPill()
                yield Static("", id="cct-header-spacer-right")
                yield _Clickable("", widget_id="cct-header-right", on_click=self._show_workspace_info)

        def on_mount(self):
            self.refresh_brand()
            self.apply_custom_header()
            # Force initial workspace paint (fixes blank on launch)
            try:
                self.refresh_right(self._workspace_path or "No workspace open")
            except Exception:
                pass

        def apply_custom_header(self, hdr_cfg=None):
            """Apply header customization (height, visibility, logo visibility)."""
            try:
                from .. import customization as _cust
                if not _cust.is_active():
                    self.display = True
                    self.styles.height = 4
                    try:
                        logo = self.query_one(Logo)
                        if logo:
                            logo.display = True
                    except Exception:
                        pass
                    return
                if hdr_cfg is None:
                    hdr_cfg = _cust.get_manager().get_component("header") or {}
                # Visibility (releases space if hidden)
                vis = hdr_cfg.get("visible", True)
                self.display = bool(vis)
                # Height: #cct-brandheader has border-bottom: solid $border (1 row),
                # so 3 rows of content (pill height: 3) requires header height: 4.
                h = hdr_cfg.get("height")
                if h is not None:
                    try:
                        val = int(h)
                        self.styles.height = max(4, min(10, val if val >= 4 else val + 1))
                    except Exception:
                        self.styles.height = 4
                else:
                    self.styles.height = 4
                # Logo visibility
                logo_vis = hdr_cfg.get("logo_visible", True)
                try:
                    logo = self.query_one(Logo)
                    if logo:
                        logo.display = bool(logo_vis)
                except Exception:
                    pass
            except Exception:
                pass

        def refresh_brand(self):
            """Re-renders the mark/pill colors from the current theme —
            content doesn't change, only the accent color it's painted
            with. Called once on mount and again whenever `/theme`
            toggles."""
            try:
                self.query_one(Logo).redraw()
            except Exception:
                pass
            try:
                self.query_one(PermissionPill).refresh_label()
            except Exception:
                pass
            try:
                self.set_chat_title(self._current_chat_title)
            except Exception:
                pass

        def refresh_breadcrumb(self, *args, **kwargs):
            """No-op retained for backward compatibility — the NavBar no
            longer has a breadcrumb row (spec: only 3 sections)."""
            return

        def refresh_right(self, workspace_path):
            """`workspace_path` is the single string CCTApp now passes
            (the open folder's absolute path, or a "No workspace open"
            placeholder) — the right side shows this and nothing else
            (no GPU/API/clock cluster).

            v0.7.6 Patch 1 (header flicker fix): CCTApp's idle
            animation calls this every 1.6s while nothing streams, and
            Static.update() with byte-identical text still marks the
            widget dirty and triggers a full repaint of that row every
            tick — which is the steady "header flickering" everyone
            reported. Guarded here: no change, no update() call, no
            repaint. The first call still renders unconditionally."""
            from . import theme_css
            new_text = workspace_path or "No workspace open"
            if new_text == self._workspace_path:
                return
            self._workspace_path = new_text
            accent = theme_css.current_hex("accent")
            faint = theme_css.current_hex("text-faint")
            # Extract just the folder name for compact display
            short_name = os.path.basename(new_text) if new_text and new_text != "No workspace open" else "No workspace"
            # Workspace indicator: 📁 prefix + short name, with full path as tooltip
            display = f"[{accent}]\U0001f4c1[/] [b]{short_name}[/b]"
            try:
                w = self.query_one("#cct-header-right", Static)
                w.update(display)
                try:
                    w.tooltip = new_text
                except Exception:
                    pass
            except Exception:
                pass

        def on_resize(self, event=None):
            """Responsive header collapse: prevent horizontal overflow at small widths."""
            w = (event.size.width if event else None) or (self.size.width if self.size else 80)
            compact = (w < 72)
            very_compact = (w < 50)
            try:
                self.query_one(PermissionPill).refresh_label(compact=compact)
            except Exception:
                pass
            try:
                w_right = self.query_one("#cct-header-right", Static)
                if very_compact:
                    w_right.display = False
                else:
                    w_right.display = True
            except Exception:
                pass

else:
    BrandHeader = None
    HeaderPermissionSelector = None
    SidebarToggleGlyph = None
    NavPanel = None
    MenuButton = None
    Logo = None
    PermissionPill = None
