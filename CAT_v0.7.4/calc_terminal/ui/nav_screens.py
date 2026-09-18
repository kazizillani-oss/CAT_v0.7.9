"""
CCT UI — nav_screens.py: the destination screens NavPanel's non-file
items open (spec v0.7.4 PRIMARY GOALS #2's list, minus Dashboard/Open
Folder/Recent Workspaces, which already have real homes elsewhere:
WelcomeDashboard, the system folder picker via _PathPrompt, and
sidebar.RecentWorkspacesScreen respectively).

Same real-Screen-push-as-modal pattern every other overlay in this
package uses (PermissionModeMenu, NavPanel, _AttachPrompt) — centered,
dismissible with Escape or a click outside the box, never a floating
popup window.

Honest scope: MCP Servers, Personalize, Diff Viewer, and Extensions
have no backing engine in this codebase yet (no MCP client, no per-
project AI-instruction store, no diff engine, no plugin loader) — they
render as clearly-labeled placeholders rather than fabricated content,
matching this project's existing "honest gaps" documentation style
(see CHANGELOG_v0.7.0_permissions.md / ui/workspace.py's docstring).
Settings, Themes, and Keyboard Shortcuts DO have real state to show and
are fully wired.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

TEXTUAL_AVAILABLE = True
try:
    from textual.containers import Vertical, Horizontal, ScrollableContainer
    from textual.message import Message
    from textual.screen import Screen
    from textual.widgets import Static, Button, Input, Switch
    from textual.binding import Binding
except Exception:
    TEXTUAL_AVAILABLE = False


if TEXTUAL_AVAILABLE:

    class _CenteredPanel(Screen):
        """Shared chrome for every screen in this file: a centered,
        rounded, animated-open box with a title and a body. Subclasses
        only provide `compose_body()`."""

        CSS = """
        _CenteredPanel, ThemesPanel, SettingsPanel, UserPanel, InfoPanel, .cct-centered-screen {
            align: center middle;
            background: $app-background 60%;
            width: 100%;
            height: 100%;
            min-width: 100%;
            min-height: 100%;
        }
        .cct-navpanel-box {
            width: 90%;
            max-width: 68;
            min-width: 30;
            height: auto;
            max-height: 28;
            background: $surface;
            border: tall $border-active $border;
            padding: 1 2;
            opacity: 1;
            offset-y: 0;
            layout: vertical;
            overflow: hidden hidden;
        }
        .cct-navpanel-box.open { opacity: 1; offset-y: 0; }
        .cct-navpanel-title { text-style: bold; padding-bottom: 1; }
        .cct-navpanel-body {
            height: 1fr; overflow-y: auto;
            scrollbar-gutter: stable;
            scrollbar-size: 1 1;
            scrollbar-color: $border $surface;
        }
        .cct-navpanel-row { height: 1; color: $text-muted; }
        .cct-navpanel-row:hover { color: $accent; }
        .cct-navpanel-hint { color: $text-faint; padding-top: 1; height: 1; }
        """

        title = "Panel"

        def __init__(self, *args, **kwargs):
            cls = kwargs.get("classes", "")
            kwargs["classes"] = f"cct-centered-screen {cls}".strip()
            super().__init__(*args, **kwargs)

        def compose(self):
            with Vertical(classes="cct-navpanel-box", id="cct-navpanel-box"):
                yield Static(self.title, classes="cct-navpanel-title")
                with ScrollableContainer(classes="cct-navpanel-body"):
                    yield from self.compose_body()
                yield Static("Esc to close", classes="cct-navpanel-hint")

        def compose_body(self):
            yield from ()

        def on_mount(self):
            self.call_after_refresh(
                lambda: self.query_one("#cct-navpanel-box").add_class("open"))

        def on_key(self, event):
            if event.key == "escape":
                self.dismiss(None)

        def on_click(self, event):
            if getattr(event, "widget", None) in (self, None):
                try:
                    if len(self.app.screen_stack) > 1:
                        self.dismiss(None)
                except Exception:
                    pass

    class InfoPanel(_CenteredPanel):
        """Read-only line-list panel — used for Help and Keyboard
        Shortcuts, and for the four honest-gap placeholders."""

        CSS = _CenteredPanel.CSS + """
        InfoPanel { align: center middle; background: $app-background 60%; width: 100%; height: 100%; }
        """

        def __init__(self, title, lines):
            self._lines = list(lines)
            super().__init__()
            self.title = title

        def compose_body(self):
            for line in self._lines:
                yield Static(line, classes="cct-navpanel-row")

    # ------------------------------------------- theme hover-preview --
    class ThemePreviewRequested(Message):
        """Mouse entered a theme row — CCTApp temporarily applies that
        theme (preview). Never persists anything."""

        def __init__(self, name):
            self.name = name
            super().__init__()

    class ThemePreviewEnded(Message):
        """Mouse left every theme row — restore the selected theme."""

        def __init__(self):
            super().__init__()

    class _ThemeRow(Static):
        """One selectable theme entry.

        v0.7.9.5: rows are generated from the central theme registry
        (theme.available_themes()) instead of two hardcoded entries.
        States are pure text-prefix swaps of IDENTICAL cell width, so a
        row's geometry can never shift when its state changes:

            ✓ Dracula     ← the permanently selected theme
            › Nord        ← hovered (live preview)
              Tokyo Night ← everything else

        Hovering posts ThemePreviewRequested (the app applies a
        temporary, non-persisted preview); leaving posts
        ThemePreviewEnded (the app restores the saved theme); clicking
        dismisses the panel with the chosen name (the app applies it
        permanently and saves it)."""

        MARK_W = 2  # every mark ("✓ ", "› ", "  ") is exactly 2 cells

        def __init__(self, name, label, current):
            super().__init__(classes="cct-navpanel-row cct-themerow")
            self.theme_name = name
            self.label = label
            self._current = (name == current)
            self._hovered = False
            self._render_mark()

        def _render_mark(self):
            if self._current:
                mark = "\u2713 "
            elif self._hovered:
                mark = "\u203a "
            else:
                mark = " " * self.MARK_W
            self.update(f"{mark}{self.label}")

        def sync_current(self, current_name):
            """Called after a click/apply so the single ✓ always tracks
            the permanent selection without recomposing the panel."""
            self._current = (self.theme_name == current_name)
            self._render_mark()

        def on_enter(self, event):
            self._hovered = True
            self._render_mark()
            self.post_message(ThemePreviewRequested(self.theme_name))

        def on_leave(self, event):
            self._hovered = False
            self._render_mark()
            self.post_message(ThemePreviewEnded())

        def on_click(self, event):
            self.screen.dismiss(self.theme_name)

    class ThemesPanel(_CenteredPanel):
        """NavPanel item "Themes" — the FULL theme catalog from the one
        authoritative registry (theme.available_themes()). Hovering a
        row live-previews it; clicking applies + persists it; exactly
        one row carries the permanent ✓. Scrollable so all themes fit
        on short terminals."""

        CSS = _CenteredPanel.CSS + """
        ThemesPanel { align: center middle; background: $app-background 60%; width: 100%; height: 100%; }
        #cct-navpanel-box { width: 56; max-height: 30; overflow: hidden hidden; }
        """

        def __init__(self, current_theme):
            self._current = current_theme
            super().__init__()
            self.title = "Themes"

        def compose_body(self):
            from .. import theme
            yield Static("Hover/Arrows = preview · Click/Enter = apply",
                         classes="cct-navpanel-hint")
            for name in theme.available_themes():
                yield _ThemeRow(name, theme.theme_label(name), self._current)

        def sync_marks(self, current_name):
            for row in self.query(_ThemeRow):
                row.sync_current(current_name)

        def on_key(self, event):
            if event.key == "escape":
                self.dismiss(None)
                return
            rows = list(self.query(_ThemeRow))
            if not rows:
                return
            current_idx = -1
            for i, r in enumerate(rows):
                if r._hovered or (current_idx == -1 and r._current):
                    current_idx = i
            if event.key in ("down", "j"):
                event.prevent_default()
                next_idx = min(len(rows) - 1, current_idx + 1)
                for i, r in enumerate(rows):
                    r._hovered = (i == next_idx)
                    r._render_mark()
                rows[next_idx].scroll_visible(animate=False)
                self.post_message(ThemePreviewRequested(rows[next_idx].theme_name))
            elif event.key in ("up", "k"):
                event.prevent_default()
                prev_idx = max(0, current_idx - 1)
                for i, r in enumerate(rows):
                    r._hovered = (i == prev_idx)
                    r._render_mark()
                rows[prev_idx].scroll_visible(animate=False)
                self.post_message(ThemePreviewRequested(rows[prev_idx].theme_name))
            elif event.key in ("enter", "space"):
                event.prevent_default()
                if 0 <= current_idx < len(rows):
                    self.dismiss(rows[current_idx].theme_name)

    # ------------------------------------------------------- settings --
    class _SettingRow(Static):
        """One row of the merged Settings window. Three shapes, chosen
        by `kind`:

          - "choice":  `✓ Label` when `values[category] == value`,
                       `  Label` otherwise (Permission Mode / Theme /
                       AI Mode — same check-mark convention ThemesPanel
                       already uses)
          - "toggle":  `  Label  [ON]` / `[OFF]` (Auto-save, Sound,
                       Animated responses)
          - "speed"/"precision": `  Label  <current>` cycling through
                       a fixed step list on every click
          - "action":  `  Label: <current> ›` (Model / Workspace /
                       Clear history)

        Clicking always posts events.SettingChanged(category, value)
        (None for toggles/actions, whose current state the app flips).
        The row never applies anything itself and never reads app
        state directly — CCTApp hands the panel a fresh values dict via
        refresh_rows() after it applies each change."""

        def __init__(self, label, category, value=None, kind="choice"):
            super().__init__("", classes="cct-navpanel-row")
            self.label = label
            self.category = category
            self.value = value
            self.kind = kind
            self._hovered = False
            self._last_values = None

        def on_click(self, event):
            from .events import SettingChanged
            self.post_message(SettingChanged(self.category, self.value))

        # v0.7.9.5: theme rows live-preview on hover, same contract as
        # ThemesPanel rows (see _ThemeRow). Non-theme rows are untouched.
        def on_enter(self, event):
            if self.category != "theme" or self.kind != "choice":
                return
            self._hovered = True
            self.render_state(self._last_values or {})
            self.post_message(ThemePreviewRequested(str(self.value)))

        def on_leave(self, event):
            if self.category != "theme" or self.kind != "choice":
                return
            self._hovered = False
            self.render_state(self._last_values or {})
            self.post_message(ThemePreviewEnded())

        def render_state(self, values):
            from . import theme_css
            self._last_values = dict(values) if isinstance(values, dict) else values
            if self.kind == "choice":
                selected = values.get(self.category) == self.value
                if selected:
                    mark = "\u2713 "
                elif self._hovered:
                    mark = "\u203a "
                else:
                    mark = "  "
                self.update(f"{mark}{self.label}")
                return
            if self.kind == "toggle":
                on = bool(values.get(self.category))
                color = theme_css.current_hex("success" if on else "error")
                state = f"[{color} b]ON[/]" if on else f"[{color} b]OFF[/]"
                self.update(f"  {self.label}  [{theme_css.current_hex('text-faint')}]\u00b7[/]  {state}")
                return
            if self.kind in ("speed", "precision"):
                from . import theme_css
                current = values.get(self.category)
                if self.kind == "speed":
                    shown = f"{current:.1f}x" if isinstance(current, float) else str(current)
                else:
                    shown = str(current)
                self.update(f"  {self.label}  [{theme_css.current_hex('text-faint')}]\u00b7[/]  "
                            f"{shown}  [{theme_css.current_hex('text-faint')}]\u21bb[/]")
                return
            # action row
            from . import theme_css
            current = values.get(self.category) or ""
            shown = f": {current} " if current else " "
            self.update(f"  {self.label}{shown}[{theme_css.current_hex('text-faint')}]\u203a[/]")

    class SettingsPanel(_CenteredPanel):
        """The merged Settings window (v0.7.6 Patch 1). Every setting
        this build actually exposes lives here in ONE window, in the
        same centered rounded-box chrome every other panel uses:

          - Permission Mode (Ask Every Time / Restricted / Full Access)
          - Theme (the full catalog — hover previews, click applies)
          - AI Mode (Notebook / Agent / Build / Plan)
          - Model (opens the provider setup screen)
          - Workspace (opens the folder picker)
          - Preferences (auto-save history, sound, animated responses,
            animation speed, decimal precision, clear history)

        `get_values` is a zero-arg callable returning a dict of current
        values keyed by category — supplied by CCTApp so this window
        never reads app state itself. Clicking a row posts
        SettingChanged; the app applies it and calls refresh_rows() to
        re-render the check marks/values in place."""

        # Slightly taller + scrollable box: 22 rows of settings must
        # never clip on a short terminal.
        CSS = _CenteredPanel.CSS + """
        SettingsPanel { align: center middle; background: $app-background 60%; width: 100%; height: 100%; }
        #cct-navpanel-box { max-height: 30; overflow: hidden hidden; }
        .cct-navpanel-section {
            color: $text-faint; height: auto;
            padding-top: 1; border-top: solid $border; margin-top: 1;
        }
        """

        def __init__(self, get_values):
            self._get_values = get_values
            super().__init__()
            self.title = "Settings"

        def compose_body(self):
            from .. import permissions as perm
            from .. import ai_modes
            from .. import theme

            yield Static("Permission Mode", classes="cct-navpanel-section")
            for mode in ("ask", "restricted", "full"):
                yield _SettingRow(perm.MODE_LABELS[mode], "perm_mode", mode)
            yield Static("Theme", classes="cct-navpanel-section")
            # v0.7.8 BUG 3: the single palette source (theme.py) drives
            # this list — no second hardcoded dark/light in the UI.
            for name in theme.theme_names():
                yield _SettingRow(theme.theme_label(name), "theme", name)
            yield Static("AI Mode", classes="cct-navpanel-section")
            for key in ai_modes.MODE_ORDER:
                m = ai_modes.meta(key)
                yield _SettingRow(f"{m['icon']}  {m['label']}", "ai_mode", key)
            yield Static("Personalization", classes="cct-navpanel-section")
            yield _SettingRow("AI Personalization \u2026", "open_personalization", kind="action")
            yield Static("Integrations", classes="cct-navpanel-section")
            yield _SettingRow("Backup Providers \u2026", "open_backup_providers", kind="action")
            yield _SettingRow("MCP Servers \u2026", "open_mcp_servers", kind="action")
            yield Static("Model", classes="cct-navpanel-section")
            yield _SettingRow("Model", "model", kind="action")
            yield Static("Workspace", classes="cct-navpanel-section")
            yield _SettingRow("Workspace", "workspace", kind="action")
            yield Static("Preferences", classes="cct-navpanel-section")
            yield _SettingRow("Auto-save history", "autosave", kind="toggle")
            yield _SettingRow("Sound effects", "sound", kind="toggle")
            yield _SettingRow("Animated responses", "animation", kind="toggle")
            yield _SettingRow("Animation speed", "anim_speed", kind="speed")
            yield _SettingRow("Decimal precision", "precision", kind="precision")
            yield _SettingRow("Clear notebook history", "clear_history", kind="action")

        def on_mount(self):
            super().on_mount()
            self.call_after_refresh(self.refresh_rows)

        def refresh_rows(self):
            """Repaints every row from a fresh get_values() snapshot —
            called once on mount and again by CCTApp after it applies
            a SettingChanged, so ✓ marks and value readouts always show
            the live state without recomposing the window."""
            try:
                values = self._get_values()
            except Exception:
                return
            for row in self.query(_SettingRow):
                row.render_state(values)

    class UserPanel(_CenteredPanel):
        """Users panel — v0.7.9 rename of Settings (spec section 22).

        Unified surface for: account / profile / AI configuration /
        providers / permissions / workspace / themes / shortcuts /
        gestures / automation preferences.  Keeps the original account
        + model + memory readouts, then adds live entry points for every
        former Settings item so nothing is lost after the rename."""

        CSS = _CenteredPanel.CSS + """
        UserPanel { align: center middle; background: $app-background 60%; width: 100%; height: 100%; }
        .cct-navpanel-box { width: 68; max-height: 34; overflow: hidden hidden; }
        .user-section { color: $text-faint; height: auto; padding-top: 1;
                        border-top: solid $border; margin-top: 1; }
        .user-detail { height: 1; color: $text-muted; padding: 0 1; }
        .user-toggle-row { height: 3; align-vertical: middle; padding: 0 1; margin-top: 1; }
        .user-toggle-label { width: 1fr; height: 1; color: $text; text-style: bold; }
        #user-wordwrap-switch { border: tall $border-active $border; background: $surface-alt; }
        #user-wordwrap-switch.-on { border: tall #86efac $success; }
        .user-quick { height: auto; padding-top: 1; border-top: solid $border; }
        .user-quick Button { margin-right: 1; margin-top: 0; border: tall $border-active $border; }
        .user-actions { height: auto; padding-top: 1; border-top: solid $border; }
        .user-actions Button { margin-right: 1; margin-top: 0; border: tall $border-active $border; }
        .user-prefs { height: auto; padding-top: 1; }
        .user-prefs Button { margin-right: 1; margin-top: 1; border: tall $border-active $border; }
        """

        def __init__(self, get_values):
            self._get_values = get_values
            super().__init__()
            self.title = "\u263a  Users"

        def compose(self):
            with Vertical(classes="cct-navpanel-box", id="cct-navpanel-box"):
                yield Static("\u263a  Users", classes="cct-navpanel-title")
                with ScrollableContainer(classes="cct-navpanel-body"):
                    yield Static("Account / Profile", classes="user-section")
                    yield Static("", id="user-name", classes="user-detail")
                    yield Static("", id="user-email", classes="user-detail")
                    yield Static("", id="user-status", classes="user-detail")
                    yield Static("AI Configuration", classes="user-section")
                    yield Static("", id="user-model", classes="user-detail")
                    yield Static("", id="user-provider", classes="user-detail")
                    with Horizontal(classes="user-prefs"):
                        yield Button("  Model / Provider  ", id="user-modelcfg", classes="cct-btn cct-btn-sm")
                        yield Button("  Permissions  ", id="user-perms", classes="cct-btn cct-btn-sm")
                    yield Static("AI Mode Colors", classes="user-section")
                    yield Static("", id="user-modecolors-preview", classes="user-detail")
                    with Horizontal(classes="user-prefs"):
                        yield Button("  \U0001f3a8 Mode Colors  ", id="user-modecolors", classes="cct-btn cct-btn-sm")
                    yield Static("Workspace & Preferences", classes="user-section")
                    yield Static("", id="user-memory", classes="user-detail")
                    yield Static("", id="user-sessions", classes="user-detail")
                    with Horizontal(classes="user-prefs"):
                        yield Button("  Workspace  ", id="user-workspace", classes="cct-btn cct-btn-sm")
                        yield Button("  Themes  ", id="user-themes", classes="cct-btn cct-btn-sm")
                        yield Button("  Gestures  ", id="user-gestures", classes="cct-btn cct-btn-sm")
                    yield Static("Editor Preferences", classes="user-section")
                    with Horizontal(classes="user-toggle-row"):
                        yield Static("Word Wrap", classes="user-toggle-label")
                        yield Switch(value=True, id="user-wordwrap-switch")
                    yield Static("Automation & Shortcuts", classes="user-section")
                    with Horizontal(classes="user-prefs"):
                        yield Button("  \u2328 Shortcuts  ", id="user-shortcuts", classes="cct-btn cct-btn-sm")
                        yield Button("  Automation  ", id="user-automation", classes="cct-btn cct-btn-sm")
                    yield Static("Quick Links", classes="user-section")
                    with Horizontal(classes="user-quick"):
                        yield Button("  ? Help Center  ", id="user-help", classes="cct-btn cct-btn-sm")
                        yield Button("  Personalize  ", id="user-personalize", classes="cct-btn cct-btn-sm")
                with Horizontal(classes="user-actions"):
                    yield Button("  Settings  ", id="user-settings", classes="cct-btn")
                    yield Button("  Sign Out  ", id="user-signout", variant="error", classes="cct-btn")
                yield Static("Esc to close", classes="cct-navpanel-hint")

        def on_mount(self):
            super().on_mount()
            self.call_after_refresh(self._refresh)

        def _refresh(self):
            try:
                v = self._get_values()
            except Exception:
                v = {}
            user = v.get("user", {})
            model = v.get("model", "none")
            provider = v.get("provider", "none")
            memory = v.get("memory", "0 turns")
            sessions = v.get("chat_sessions", "0 saved")
            authenticated = v.get("authenticated", False)
            name = user.get("name", "Anonymous")
            email = user.get("email", "Not signed in")
            # Get current wordwrap state from editor if available
            wrap_on = True
            try:
                # Try to get from app's editor
                app = self.app
                if hasattr(app, '_workspace_shell') and app._workspace_shell and app._workspace_shell.editor:
                    wrap_on = getattr(app._workspace_shell.editor, '_wrap_on', True)
                else:
                    # Fallback to config or default
                    wrap_on = True
            except Exception:
                wrap_on = True

            def _set(widget_id, text):
                try:
                    self.query_one(widget_id, Static).update(text)
                except Exception:
                    pass

            _set("#user-name", f"  Name:  [b]{name}[/b]")
            _set("#user-email", f"  Email:  {email}")
            _set("#user-status", f"  Status:  {'[b]\u2713 Signed In[/b]' if authenticated else '[dim]Signed Out[/dim]'}")
            _set("#user-model", f"  Active:  [b]{model}[/b]")
            _set("#user-provider", f"  Provider:  {provider}")
            # Mode colors preview: show current mode's accent + small palette
            try:
                from .. import ai_modes as _am
                cur = _am.current_mode()
                hexc = _am.accent_hex(cur)
                g0, g1 = _am.gradient(cur)
                # show current mode color + 3 other mode dots
                parts = []
                for k in _am.MODE_ORDER[:4]:
                    hk = _am.accent_hex(k)
                    parts.append(f"[{hk}]●[/]")
                dots = " ".join(parts)
                _set("#user-modecolors-preview", f"  Current: [{hexc}]{cur} {hexc}[/]  [dim]{g0}→{g1}[/]   {dots}")
            except Exception:
                _set("#user-modecolors-preview", "  Customize each AI mode's color")
            _set("#user-memory", f"  Conversation memory:  {memory}")
            _set("#user-sessions", f"  Saved chats:  {sessions}")
            # Update wordwrap switch state
            try:
                sw = self.query_one("#user-wordwrap-switch", Switch)
                sw.value = wrap_on
            except Exception:
                pass

        def on_switch_changed(self, event: Switch.Changed):
            if event.switch.id == "user-wordwrap-switch":
                wrap_on = event.value
                try:
                    app = self.app
                    if hasattr(app, '_workspace_shell') and app._workspace_shell and app._workspace_shell.editor:
                        editor = app._workspace_shell.editor
                        editor._wrap_on = wrap_on
                        area = editor.active_text_area()
                        if area:
                            if hasattr(area, 'show_line_numbers'):
                                area.wrap = wrap_on
                            elif hasattr(area, 'wrap'):
                                area.wrap = wrap_on
                except Exception:
                    pass

        def on_button_pressed(self, event):
            if event.button.id == "user-signout":
                self.dismiss("signout")
            elif event.button.id == "user-wordwrap":
                # Legacy button fallback if present
                try:
                    app = self.app
                    if hasattr(app, '_workspace_shell') and app._workspace_shell and app._workspace_shell.editor:
                        editor = app._workspace_shell.editor
                        editor._wrap_on = not getattr(editor, '_wrap_on', True)
                        sw = self.query_one("#user-wordwrap-switch", Switch)
                        sw.value = editor._wrap_on
                except Exception:
                    pass
                self._refresh()
                return
            elif event.button.id == "user-personalize":
                self.dismiss("personalize")
            elif event.button.id == "user-shortcuts":
                self.dismiss("shortcuts")
            elif event.button.id == "user-help":
                self.dismiss("help")
            elif event.button.id == "user-modelcfg":
                self.dismiss("model")
            elif event.button.id == "user-perms":
                self.dismiss("permissions")
            elif event.button.id == "user-workspace":
                self.dismiss("workspace")
            elif event.button.id == "user-themes":
                self.dismiss("themes")
            elif event.button.id == "user-modecolors":
                self.dismiss("mode_colors")
            elif event.button.id == "user-gestures":
                self.dismiss("gestures")
            elif event.button.id == "user-automation":
                self.dismiss("automation")
            elif event.button.id == "user-settings":
                self.dismiss("settings")

    from .chats_panel import ChatsPanel

    class RenameChatModal(Screen):
        """3D styled modal dialog for renaming a chat session."""
        CSS = """
        RenameChatModal { align: center middle; background: $app-background 60%; }
        #rename-box {
            width: 56; height: auto;
            background: $surface; border: tall $border-active $border;
            padding: 1 2;
        }
        #rename-title { text-style: bold; color: $accent; margin-bottom: 1; }
        #rename-input { margin-bottom: 1; }
        #rename-btns { height: 3; align: right middle; }
        #rename-btns Button { margin-left: 1; }
        """
        def __init__(self, current_name=""):
            super().__init__()
            self._initial = current_name

        def compose(self):
            with Vertical(id="rename-box"):
                yield Static("\U0001f4ac  Rename Chat Session", id="rename-title")
                yield Input(value=self._initial, placeholder="Enter chat title...", id="rename-input")
                with Horizontal(id="rename-btns"):
                    yield Button("Cancel", id="rename-cancel", classes="cct-btn")
                    yield Button("Save", id="rename-save", variant="primary", classes="cct-btn")

        def on_mount(self):
            try:
                inp = self.query_one("#rename-input", Input)
                inp.focus()
            except Exception:
                pass

        def on_button_pressed(self, event):
            if event.button.id == "rename-save":
                val = self.query_one("#rename-input", Input).value.strip()
                self.dismiss(val or None)
            else:
                self.dismiss(None)

        def on_key(self, event):
            if event.key == "escape":
                self.dismiss(None)
            elif event.key == "enter":
                val = self.query_one("#rename-input", Input).value.strip()
                self.dismiss(val or None)

    class ConfirmDeleteChatModal(Screen):
        """3D styled modal confirmation dialog for deleting a conversation."""
        CSS = """
        ConfirmDeleteChatModal { align: center middle; background: $app-background 60%; }
        #delete-box {
            width: 58; height: auto;
            background: $surface;
            border-top: tall $surface-highlight;
            border-bottom: tall $surface-dark;
            border-left: tall $surface-highlight;
            border-right: tall $surface-dark;
            padding: 1 2;
        }
        #delete-title { text-style: bold; color: $error; margin-bottom: 1; }
        #delete-msg { margin-bottom: 1; }
        #delete-note { color: $text-faint; font-style: italic; margin-bottom: 1; }
        #delete-btns { height: 3; align: right middle; }
        #delete-btns Button { margin-left: 1; min-height: 3; }
        """
        BINDINGS = [
            Binding("escape", "cancel", "Cancel"),
            Binding("enter", "confirm", "Delete"),
        ]

        def __init__(self, chat_name="Untitled"):
            super().__init__()
            self._chat_name = chat_name

        def compose(self):
            with Vertical(id="delete-box"):
                yield Static("\U0001f5d1  Delete Conversation", id="delete-title")
                yield Static(f"Are you sure you want to delete '{self._chat_name}'?", id="delete-msg")
                yield Static("(This removes the saved chat record only. No files in your workspace are deleted.)", id="delete-note")
                with Horizontal(id="delete-btns"):
                    yield Button("Cancel", id="delete-cancel", classes="cct-btn")
                    yield Button("Delete", id="delete-confirm", variant="error", classes="cct-btn cct-btn-danger")

        def on_mount(self):
            try:
                self.query_one("#delete-confirm", Button).focus()
            except Exception:
                pass

        def action_cancel(self):
            self.dismiss(False)

        def action_confirm(self):
            self.dismiss(True)

        def on_button_pressed(self, event):
            if event.button.id == "delete-confirm":
                self.dismiss(True)
            else:
                self.dismiss(False)

        def on_key(self, event):
            if event.key == "escape":
                self.dismiss(False)
            elif event.key == "enter":
                self.dismiss(True)

else:
    InfoPanel = None
    ThemesPanel = None
    SettingsPanel = None
    UserPanel = None
    ChatsPanel = None
    RenameChatModal = None
    ConfirmDeleteChatModal = None

