import sys

sys.stdout.reconfigure(encoding='utf-8')

with open("calc_terminal/ui/editor.py", "r", encoding="utf-8") as f:
    ed_content = f.read()

ed_content = ed_content.replace("\r\n", "\n")

# 1. Update compose() close button label
old_comp_close = 'yield Static("\\u2715", id="cct-tb-close", classes="cct-tb-close")'
new_comp_close = 'yield Static("Close", id="cct-tb-close", classes="cct-tb-close")'
assert old_comp_close in ed_content, "old_comp_close not found"
ed_content = ed_content.replace(old_comp_close, new_comp_close)

# 2. Update toolbar split and back buttons visibility
old_tb_ctrls = """                    # ▷ and ⿻ — show only for web-previewable files (spec 2)
                    try:
                        run_pill = self.query_one("#cct-tb-run")
                        split_pill = self.query_one("#cct-tb-split")
                        is_port = False
                        try:
                            s = getattr(self.app, "size", None) or getattr(self.screen, "size", None)
                            if s:
                                is_port = (s.width < 92) or (s.width <= 105 and (s.width / max(1, s.height)) < 2.3)
                        except Exception:
                            pass
                        try:
                            self.query_one("#cct-tb-back", Static).display = is_port
                        except Exception:
                            pass
                        is_web = is_web_previewable(area.path)
                        is_split = is_web or is_markdown_file(area.path)
                        run_pill.display = bool(is_web)
                        split_pill.display = not is_port
                        try:
                            run_pill.set_class(is_web, "-run")
                            split_pill.set_class(is_split, "-split")
                        except Exception:
                            pass
                        try:
                            if is_web:
                                run_pill.tooltip = "Open Live Web Preview (▷)"
                                split_pill.tooltip = "Fullscreen / Restore Editor (⿻)"
                            elif is_split:
                                split_pill.tooltip = "Fullscreen / Restore Editor (⿻)"
                                try: run_pill.tooltip = ""
                                except: pass
                            else:
                                run_pill.tooltip = ""
                                split_pill.tooltip = ""
                        except Exception:
                            pass
                    except Exception:
                        pass"""

new_tb_ctrls = """                    # Toolbar controls: ⿻ (maximize toggle) in landscape, Back in portrait, Close in landscape
                    try:
                        run_pill = self.query_one("#cct-tb-run")
                        split_pill = self.query_one("#cct-tb-split")
                        back_pill = self.query_one("#cct-tb-back", Static)
                        close_pill = self.query_one("#cct-tb-close", Static)
                        is_port = False
                        try:
                            s = getattr(self.app, "size", None) or getattr(self.screen, "size", None)
                            if s:
                                is_port = (s.width < 92) or (s.width <= 105 and (s.width / max(1, s.height)) < 2.3)
                        except Exception:
                            pass
                        if is_port:
                            back_pill.display = True
                            split_pill.display = False
                            close_pill.display = False
                        else:
                            back_pill.display = False
                            split_pill.display = True
                            close_pill.display = True
                            close_pill.update("Close")
                            close_pill.tooltip = "Close Editor & Return to CAT"
                            try:
                                shell = self.app.query_one("#cct-workspace")
                                is_fs = getattr(shell, "fullscreen", False)
                                split_pill.tooltip = "Restore Split View (⿻)" if is_fs else "Maximize Editor (⿻)"
                            except Exception:
                                split_pill.tooltip = "Maximize / Restore Editor (⿻)"
                        is_web = is_web_previewable(area.path)
                        run_pill.display = bool(is_web)
                        try:
                            run_pill.set_class(is_web, "-run")
                            split_pill.set_class(True, "-split")
                        except Exception:
                            pass
                    except Exception:
                        pass"""

assert old_tb_ctrls in ed_content, "old_tb_ctrls not found"
ed_content = ed_content.replace(old_tb_ctrls, new_tb_ctrls)

# 3. Update on_click for split and close
old_click_split = """            if widget_id == "cct-tb-close":
                self.close_active()
                return
            if widget_id == "cct-tb-wrap":
                self._toggle_wrap(self.active_text_area())
                return
            if widget_id == "cct-tb-preview":
                self._toggle_preview(self.active_text_area())
                return
            if widget_id == "cct-tb-run":
                self.action_show_preview()
                return
            if widget_id == "cct-tb-split":
                area = self.active_text_area()
                path = getattr(area, "path", None)
                if path:
                    try:
                        from ..browser import WorkspaceMode
                        shell = self.app.query_one("#cct-workspace")
                        if shell.mode is WorkspaceMode.SPLIT:
                            shell.set_right_mode(WorkspaceMode.CODE)
                            return
                        try:
                            ctrl = getattr(self.app, "_preview_ctrl", None)
                            running = ctrl is not None and ctrl.preview_state.value == "running"
                        except Exception:
                            running = False
                        if not running:
                            from .events import PreviewRequested
                            self.post_message(PreviewRequested(path))
                            def _to_split():
                                try:
                                    if shell.mode is not WorkspaceMode.SPLIT:
                                        shell.set_right_mode(WorkspaceMode.SPLIT)
                                Except Exception:
                                    pass
                            Self.set_timer(0.8, _to_split)
                        Else:
                            Shell.set_right_mode(WorkspaceMode.SPLIT)
                    Except Exception:
                        From .events import PreviewRequested
                        Self.post_message(PreviewRequested(path))
                Return"""

# Find exact start and end for split click
idx_close = ed_content.find('            if widget_id == "cct-tb-close":\n                self.close_active()\n                return')
idx_tab = ed_content.find('            if isinstance(widget, Tab) and widget_id and widget_id.startswith(self._TAB_PREFIX):')
assert idx_close != -1 and idx_tab != -1, "click section not found"

new_click_section = """            if widget_id == "cct-tb-close":
                event.stop()
                self.close_active()
                try:
                    shell = self.app.query_one("#cct-workspace")
                    if not self._open_paths:
                        shell.show_chat()
                except Exception:
                    pass
                self._refresh_toolbar()
                return
            if widget_id == "cct-tb-wrap":
                self._toggle_wrap(self.active_text_area())
                return
            if widget_id == "cct-tb-preview":
                self._toggle_preview(self.active_text_area())
                return
            if widget_id == "cct-tb-run":
                self.action_show_preview()
                return
            if widget_id == "cct-tb-split":
                event.stop()
                try:
                    shell = self.app.query_one("#cct-workspace")
                    shell.set_fullscreen(not shell.fullscreen)
                except Exception:
                    try:
                        self.app.action_toggle_right_pane_fullscreen()
                    except Exception:
                        pass
                self._refresh_toolbar()
                return\n"""

ed_content = ed_content[:idx_close] + new_click_section + ed_content[idx_tab:]

with open("calc_terminal/ui/editor.py", "w", encoding="utf-8", newline="\r\n") as f:
    f.write(ed_content)

print("Updated editor.py successfully")

