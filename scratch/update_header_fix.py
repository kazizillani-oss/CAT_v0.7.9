import sys

sys.stdout.reconfigure(encoding='utf-8')

with open("calc_terminal/ui/header.py", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Update NavPanel CSS
nav_css_target = """        NavPanel { align: left top; background: $app-background 0%; }
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
        }"""
new_nav_css = """        NavPanel { align: left top; background: $app-background 0%; }
        NavPanel.is-portrait { align: center top; background: $app-background 60%; }
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
        NavPanel.is-portrait #cct-navmenu-box,
        #cct-navmenu-box.is-portrait {
            margin-top: 2; margin-left: 0; margin-right: 0;
            width: 92%; max-width: 46;
            border: heavy $border;
        }
        .cct-navmenu-header {
            height: 2; background: $surface-alt; color: $accent;
            text-style: bold; padding: 0 2; content-align: left middle;
            border-bottom: solid $border;
        }"""
text = text.replace(nav_css_target, new_nav_css)

# 2. In NavPanel: find def _get_filtered(self): up to def _sync_selected_class(self):
start_tag = "        def _get_filtered(self):"
end_tag = "        def _sync_selected_class(self):"
idx1 = text.find(start_tag)
idx2 = text.find(end_tag)
assert idx1 != -1 and idx2 != -1, f"Indices not found: {idx1}, {idx2}"

replacement_nav = """        def is_portrait(self):
            try:
                s = getattr(self.app, "size", None) or getattr(self.screen, "size", None)
                if s:
                    return (s.width < 92) or (s.width <= 105 and (s.width / max(1, s.height)) < 2.3)
            except Exception:
                pass
            return False

        def _get_filtered(self):
            if self.is_portrait():
                return (
                    ("__header", "⬡ CAT", "Coding Agent Terminal"),
                    ("__section_proj", "📁", "Project"),
                    ("open_folder", "📂", "Open Folder"),
                    ("recent_workspaces", "🕒", "Recent Workspaces"),
                    ("sep_proj", "", ""),
                    ("__section_app", "🎨", "Appearance"),
                    ("themes", "◑", "Themes"),
                    ("extensions", "▣", "Extensions"),
                    ("sep_app", "", ""),
                    ("__section_acc", "👤", "Account"),
                    ("user", "☺", "Users & Profile"),
                    ("signout", "⎋", "Sign Out"),
                    ("sep_acc", "", ""),
                    ("__section_sys", "⚙", "Application"),
                    ("quit", "✕", "Quit"),
                )
            try:
                return get_nav_items()
            except Exception:
                return _NAV_ITEMS_BASE

        def compose(self):
            items = self._get_filtered()
            self._nav_cache = items
            with Vertical(id="cct-navmenu-box"):
                for i, (action_id, icon, label) in enumerate(items):
                    if action_id == "__header":
                        yield Static(f"⬡ CAT  [dim]Coding Agent Terminal[/dim]", classes="cct-navmenu-header")
                    elif action_id.startswith("sep"):
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
            if self.is_portrait():
                self.add_class("is-portrait")
                try:
                    self.query_one("#cct-navmenu-box").add_class("is-portrait")
                except Exception:
                    pass
            self._sync_selected_class()
            try:
                self.query_one("#cct-navmenu-box").add_class("open")
            except Exception:
                pass\n\n"""

text = text[:idx1] + replacement_nav + text[idx2:]

# 3. In on_row_picked: handle quit
old_picked = "        def on_row_picked(self, action_id):"
idx_picked = text.find(old_picked)
end_picked = text.find("        def _nav_items(self):")
assert idx_picked != -1 and end_picked != -1
replacement_picked = """        def on_row_picked(self, action_id):
            if action_id == "quit":
                self.dismiss(None)
                try:
                    self.app.exit()
                except Exception:
                    pass
                return
            if action_id in self._KEEP_OPEN:
                self.post_message(NavAction(action_id))
                return
            self.dismiss(action_id)\n\n"""
text = text[:idx_picked] + replacement_picked + text[end_picked:]

# 4. BrandHeader.compose
old_bh_comp = """        def compose(self):
            with Horizontal(id="cct-header-top"):
                with Horizontal(id="cct-header-left"):
                    yield MenuButton()
                    yield Logo()
                yield Static("", id="cct-header-spacer-left")
                yield PermissionPill()
                yield Static("", id="cct-header-spacer-right")
                yield _Clickable("", widget_id="cct-header-right", on_click=self._show_workspace_info)"""
new_bh_comp = """        def compose(self):
            with Horizontal(id="cct-header-top"):
                with Horizontal(id="cct-header-left"):
                    yield MenuButton()
                    yield Logo()
                yield Static("", id="cct-header-spacer-left")
                yield PermissionPill()
                yield Static("", id="cct-header-spacer-right")
                with Horizontal(id="cct-header-right-box"):
                    yield Button(_safe_glyph("📁", "Exp"), id="cct-header-explorer-btn", classes="cct-header-explorer-btn", tooltip="Toggle Explorer (Ctrl+B)")
                    yield _Clickable("", widget_id="cct-header-right", on_click=self._show_workspace_info)

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "cct-header-explorer-btn":
                event.stop()
                try:
                    self.app.action_toggle_sidebar()
                except Exception:
                    try:
                        from .workspace import WorkspaceShell
                        self.app.query_one(WorkspaceShell).toggle_sidebar()
                    except Exception:
                        pass"""
assert old_bh_comp in text, "old_bh_comp not found"
text = text.replace(old_bh_comp, new_bh_comp)

# 5. BrandHeader.on_resize
old_right_logic = """            try:
                w_right = self.query_one("#cct-header-right", Static)
                if ultra_compact or (is_portrait and w < 72):
                    w_right.display = False
                else:
                    w_right.display = True"""
new_right_logic = """            try:
                exp_btn = self.query_one("#cct-header-explorer-btn", Button)
                w_right = self.query_one("#cct-header-right", Static)
                if is_portrait:
                    exp_btn.display = True
                    w_right.display = False
                else:
                    exp_btn.display = False
                    if ultra_compact:
                        w_right.display = False
                    else:
                        w_right.display = True"""
assert old_right_logic in text, "old_right_logic not found"
text = text.replace(old_right_logic, new_right_logic)

with open("calc_terminal/ui/header.py", "w", encoding="utf-8") as f:
    f.write(text)

print("header.py patched successfully!")
