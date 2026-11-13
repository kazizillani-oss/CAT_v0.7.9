p_hdr = "calc_terminal/ui/header.py"
with open(p_hdr, "r", encoding="utf-8") as f:
    text_hdr = f.read()

# Restore Button in compose and on_button_pressed in header.py
old_comp = '''        def _toggle_explorer(self):
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

new_comp = '''        def compose(self):
            with Horizontal(id="cct-header-top"):
                with Horizontal(id="cct-header-left"):
                    yield MenuButton()
                    yield Logo()
                yield PermissionPill()
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
                        pass'''

old_q = 'exp_btn = self.query_one("#cct-header-explorer-btn")'
new_q = 'exp_btn = self.query_one("#cct-header-explorer-btn", Button)'

if old_comp in text_hdr:
    text_hdr = text_hdr.replace(old_comp, new_comp)
    print("Replaced in header.py")
else:
    text_hdr = text_hdr.replace(old_comp.replace("\n", "\r\n"), new_comp.replace("\n", "\r\n"))
    print("Replaced CRLF in header.py")

if old_q in text_hdr:
    text_hdr = text_hdr.replace(old_q, new_q)
    print("Replaced query in header.py")

with open(p_hdr, "w", encoding="utf-8") as f:
    f.write(text_hdr)

