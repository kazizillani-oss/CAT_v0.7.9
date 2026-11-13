p = "calc_terminal/ui/header.py"
with open(p, "r", encoding="utf-8") as f:
    text = f.read()

# Replace Button with _Clickable for cct-header-explorer-btn
old_part = '''                with Horizontal(id="cct-header-right-box"):
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
                        pass'''

new_part = '''        def _toggle_explorer(self):
            try:
                self.app.action_toggle_sidebar()
            except Exception:
                try:
                    from .workspace import WorkspaceShell
                    self.app.query_one(WorkspaceShell).toggle_sidebar()
                except Exception:
                    pass

        def compose(self):
            with Horizontal(id="cct-header-top"):
                with Horizontal(id="cct-header-left"):
                    yield MenuButton()
                    yield Logo()
                yield PermissionPill()
                with Horizontal(id="cct-header-right-box"):
                    yield _Clickable(_safe_glyph("📁", "Exp"), widget_id="cct-header-explorer-btn", classes="cct-header-explorer-btn", on_click=self._toggle_explorer)
                    yield _Clickable("", widget_id="cct-header-right", on_click=self._show_workspace_info)'''

# Also fix `exp_btn = self.query_one("#cct-header-explorer-btn", Button)` to not require Button
old_query = 'exp_btn = self.query_one("#cct-header-explorer-btn", Button)'
new_query = 'exp_btn = self.query_one("#cct-header-explorer-btn")'

if old_part in text:
    text = text.replace(old_part, new_part)
    print("Replaced button in header.py")
else:
    # check with CRLF
    old_part_crlf = old_part.replace("\n", "\r\n")
    if old_part_crlf in text:
        text = text.replace(old_part_crlf, new_part.replace("\n", "\r\n"))
        print("Replaced button CRLF in header.py")
    else:
        print("old_part NOT found in header.py")

if old_query in text:
    text = text.replace(old_query, new_query)
    print("Replaced query in header.py")
else:
    print("old_query not found in header.py")

with open(p, "w", encoding="utf-8") as f:
    f.write(text)

