import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9"

path = os.path.join(ROOT, "calc_terminal/ui/app.py")
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update #cct-brandheader
target1 = '''#cct-brandheader {
    dock: top;
    height: 4;
    padding: 0 2;
    background: $app-background;
    color: $text;
    border-bottom: tall $border-active $border;
}'''

replace1 = '''#cct-brandheader {
    dock: top;
    height: 4;
    padding: 0 1;
    background: $app-background;
    color: $text;
    border-bottom: solid $border;
}'''

assert target1 in content, "target1 not found"
content = content.replace(target1, replace1, 1)

# 2. Update #cct-cmdpalette
target2 = '''#cct-cmdpalette {
    background: $surface-alt;
    border: tall;
    border-top: tall $surface-highlight;
    border-left: tall $surface-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
    tint: $surface-highlight 4%;
    margin-left: 2;
    margin-right: 2;
    margin-top: 1;
    margin-bottom: 1;
    width: 1fr;
    max-height: 8;
    height: auto;
    display: none;
    padding: 0 1;
    scrollbar-size: 1 1;
    scrollbar-gutter: stable;
    scrollbar-color: $accent $surface-dark;
    scrollbar-color-hover: $accent-highlight $surface-dark;
    scrollbar-color-active: $accent $surface-dark;
}'''

replace2 = '''#cct-cmdpalette {
    background: $surface;
    border: round $border;
    tint: $accent 4%;
    margin-left: 1;
    margin-right: 1;
    margin-top: 0;
    margin-bottom: 0;
    width: 1fr;
    max-height: 10;
    height: auto;
    display: none;
    padding: 0;
    scrollbar-size: 1 1;
    scrollbar-gutter: auto;
    scrollbar-color: $accent $surface;
}'''

assert target2 in content, "target2 not found"
content = content.replace(target2, replace2, 1)

# 3. Update landscape header button borders (lines 1294 to 1438)
target3 = '''/* LEFT: clean menu button + logo */
.cct-menu-btn {
    width: 5; min-width: 5; height: 3; color: $text; content-align: center middle;
    background: $surface-alt;
    border-top: tall $surface-highlight;
    border-left: tall $surface-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
    margin-right: 1;
    transition: color 120ms, border 120ms, background 120ms, offset 80ms;
}
.cct-menu-btn:hover {
    color: $text;
    background: $accent 24%;
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
}
.cct-menu-btn.-active {
    offset: 0 0;
    border-top: tall $surface-dark;
    border-left: tall $surface-dark;
    border-bottom: tall $surface-highlight;
    border-right: tall $surface-highlight;
}
.cct-menu-btn-active {
    color: $text;
    background: $accent 30%;
    border-top: tall $surface-dark;
    border-left: tall $surface-dark;
    border-bottom: tall $surface-highlight;
    border-right: tall $surface-highlight;
    text-style: none;
}
.cct-logo { width: auto; padding: 0 1; content-align: left middle; height: 3; text-style: bold; }

/* CENTER: Permission pill */
.cct-perm-pill {
    width: auto; content-align: center middle; height: 3;
    padding: 0 2; margin: 0;
    background: $surface-alt;
    border-top: tall $surface-highlight;
    border-left: tall $surface-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
    text-style: bold;
    color: $text;
    transition: border 120ms, color 120ms, background 120ms;
}
.cct-perm-pill:hover {
    background: $accent 24%;
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
    color: $text;
}
.cct-perm-pill.-active {
    offset: 0 0;
    border-top: tall $surface-dark;
    border-left: tall $surface-dark;
    border-bottom: tall $surface-highlight;
    border-right: tall $surface-highlight;
}
.cct-perm-pill:focus {
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
}
.cct-perm-pill-active {
    background: $accent 30%;
    color: $text;
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
}

.cct-chat-title-pill {
    width: auto; max-width: 30; content-align: center middle; height: 3;
    padding: 0 2; margin: 0 1 0 1;
    background: $surface-alt;
    border-top: tall $surface-highlight;
    border-left: tall $surface-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
    color: $text;
    text-style: bold;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: border 120ms, color 120ms, background 120ms, offset 80ms;
}
.cct-chat-title-pill:hover {
    background: $accent 18%;
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
    color: $text;
    offset-y: 0;
}
.cct-chat-title-pill:focus {
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
}
.cct-chat-title-pill.-active {
    background: $accent 28%;
    border-top: tall $surface-dark;
    border-left: tall $surface-dark;
    border-bottom: tall $surface-highlight;
    border-right: tall $surface-highlight;
    offset-y: 1;
}

/* RIGHT: 3D workspace path chip — aligned, beveled, and balanced with the pill */
#cct-header-right {
    width: auto; max-width: 32; content-align: center middle;
    padding: 0 2; height: 3;
    background: $surface-alt;
    border: tall;
    border-top: tall $surface-highlight;
    border-left: tall $surface-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
    overflow: hidden;
    text-overflow: ellipsis;
    text-style: bold;
    color: $text;
    transition: background 120ms, border 120ms, color 120ms, offset 80ms;
}
#cct-header-right:hover {
    background: $accent 20%;
    border: tall;
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-bottom: tall $accent-shadow;
    border-right: tall $accent-shadow;
    color: #ffffff;
    offset: 0 0;
}
.cct-menu-btn:focus { color: $accent; text-style: bold; }
.cct-perm-pill:focus { border: tall $accent; }'''

replace3 = '''/* LEFT: clean menu button + logo */
.cct-menu-btn {
    width: 5; min-width: 5; height: 3; color: $text; content-align: center middle;
    background: $surface-alt;
    border: round $border;
    margin-right: 1;
    transition: color 120ms, border 120ms, background 120ms;
}
.cct-menu-btn:hover {
    color: $accent;
    background: $accent 24%;
    border: round $accent;
}
.cct-menu-btn.-active, .cct-menu-btn-active {
    color: $accent;
    background: $accent 30%;
    border: round $accent;
    text-style: none;
}
.cct-logo { width: auto; padding: 0 1; content-align: left middle; height: 3; text-style: bold; }

/* CENTER: Permission pill */
.cct-perm-pill {
    width: auto; content-align: center middle; height: 3;
    padding: 0 2; margin: 0;
    background: $surface-alt;
    border: round $border;
    text-style: bold;
    color: $text;
    transition: border 120ms, color 120ms, background 120ms;
}
.cct-perm-pill:hover {
    background: $accent 24%;
    border: round $accent;
    color: $text;
}
.cct-perm-pill.-active {
    background: $accent 35%;
    border: round $accent;
    color: $text;
}
.cct-perm-pill:focus, .cct-perm-pill-active {
    background: $accent 30%;
    border: round $accent;
    color: $text;
}

.cct-chat-title-pill {
    width: auto; max-width: 30; content-align: center middle; height: 3;
    padding: 0 2; margin: 0 1 0 1;
    background: $surface-alt;
    border: round $border;
    color: $text;
    text-style: bold;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: border 120ms, color 120ms, background 120ms;
}
.cct-chat-title-pill:hover {
    background: $accent 18%;
    border: round $accent;
    color: $text;
}
.cct-chat-title-pill:focus, .cct-chat-title-pill.-active {
    background: $accent 28%;
    border: round $accent;
}

/* RIGHT: workspace path chip — cleanly aligned with permission pill */
#cct-header-right {
    width: auto; max-width: 32; content-align: center middle;
    padding: 0 2; height: 3;
    background: $surface-alt;
    border: round $border;
    overflow: hidden;
    text-overflow: ellipsis;
    text-style: bold;
    color: $text;
    transition: background 120ms, border 120ms, color 120ms;
}
#cct-header-right:hover {
    background: $accent 20%;
    border: round $accent;
    color: #ffffff;
}
.cct-menu-btn:focus { color: $accent; text-style: bold; border: round $accent; }
.cct-perm-pill:focus { border: round $accent; }'''

assert target3 in content, "target3 not found"
content = content.replace(target3, replace3, 1)

# 4. Update _handle_signout & add _handle_quit
target4 = '''        def _handle_signout(self):
            """Prompt confirmation modal before signing out (Requirement #42)."""
            from textual.screen import Screen
            from textual.containers import Vertical, Horizontal
            from textual.widgets import Static, Button
            from textual.binding import Binding

            class SignOutModal(Screen):
                """Requirement #42: Sign out confirmation modal."""
                DEFAULT_CSS = """
                SignOutModal {
                    align: center middle;
                    background: #1a1b26 75%;
                    width: 100%;
                    height: 100%;
                }
                #signout-box {
                    width: 52;
                    height: auto;
                    background: #1f2335;
                    border: thick #a78bfa;
                    padding: 2 3;
                    layout: vertical;
                    align: center middle;
                }
                #signout-title {
                    color: #a78bfa;
                    text-style: bold;
                    text-align: center;
                    margin-bottom: 1;
                }
                #signout-prompt {
                    text-align: center;
                    margin-bottom: 2;
                    color: #e2e8f0;
                }
                #signout-buttons {
                    height: 3;
                    width: 100%;
                    align: center middle;
                    layout: horizontal;
                }
                #signout-buttons Button {
                    margin: 0 2;
                    min-width: 14;
                    height: 3;
                    border: none;
                }
                #btn-signout-yes {
                    background: #2e3440;
                    color: #e2e8f0;
                    border: round #4c566a;
                }
                #btn-signout-yes:hover, #btn-signout-yes:focus {
                    background: #3b4252;
                    color: #ffffff;
                    border: round #a78bfa;
                }
                #btn-signout-cancel {
                    background: #7c3aed;
                    color: #ffffff;
                    text-style: bold;
                    border: round #7c3aed;
                }
                #btn-signout-cancel:hover, #btn-signout-cancel:focus {
                    background: #8b5cf6;
                    color: #ffffff;
                    border: round #c4b5fd;
                    text-style: bold;
                }
                """

                BINDINGS = [
                    Binding("escape", "cancel", "Cancel"),
                ]

                def compose(self):
                    with Vertical(id="signout-box"):
                        yield Static("SIGN OUT", id="signout-title")
                        yield Static("Are you sure you want to sign out?", id="signout-prompt")
                        with Horizontal(id="signout-buttons"):
                            yield Button("  Yes  ", id="btn-signout-yes")
                            yield Button("  Cancel  ", id="btn-signout-cancel")

                def on_mount(self):
                    try:
                        # Default focus: Cancel (Requirement #42)
                        self.query_one("#btn-signout-cancel", Button).focus()
                    except Exception:
                        pass

                def action_cancel(self):
                    self.dismiss(False)

                def on_button_pressed(self, event):
                    if event.button.id == "btn-signout-yes":
                        self.dismiss(True)
                    else:
                        self.dismiss(False)

            def _on_confirmed(confirmed):
                if confirmed:
                    self._do_execute_signout()

            self.push_screen(SignOutModal(), _on_confirmed)'''

replace4 = '''        def _handle_signout(self):
            """Prompt ultra-responsive confirmation modal before signing out."""
            from textual.screen import Screen
            from textual.containers import Vertical, Horizontal
            from textual.widgets import Static, Button
            from textual.binding import Binding

            class SignOutModal(Screen):
                """Ultra-responsive sign out confirmation modal."""
                DEFAULT_CSS = """
                SignOutModal {
                    align: center middle;
                    background: $app-background 75%;
                    width: 100%;
                    height: 100%;
                }
                #signout-box {
                    width: 90%;
                    max-width: 48;
                    height: auto;
                    background: $surface;
                    border: round $accent;
                    padding: 1 2;
                    layout: vertical;
                    align: center middle;
                }
                #signout-title {
                    color: $accent;
                    text-style: bold;
                    text-align: center;
                    margin-bottom: 1;
                }
                #signout-prompt {
                    text-align: center;
                    margin-bottom: 1;
                    color: $text;
                }
                #signout-buttons {
                    height: 3;
                    width: 100%;
                    align: center middle;
                    layout: horizontal;
                }
                #signout-buttons Button {
                    margin: 0 1;
                    min-width: 12;
                    height: 3;
                }
                SignOutModal.is-portrait #signout-buttons,
                .is-portrait #signout-buttons {
                    layout: vertical;
                    height: auto;
                }
                SignOutModal.is-portrait #signout-buttons Button,
                .is-portrait #signout-buttons Button {
                    width: 100%;
                    margin: 1 0;
                }
                """

                BINDINGS = [
                    Binding("escape", "cancel", "Cancel"),
                ]

                def compose(self):
                    with Vertical(id="signout-box"):
                        yield Static("⎋  SIGN OUT", id="signout-title")
                        yield Static("Are you sure you want to sign out?", id="signout-prompt")
                        with Horizontal(id="signout-buttons"):
                            yield Button("  Sign Out  ", id="btn-signout-yes", variant="error")
                            yield Button("  Cancel  ", id="btn-signout-cancel", variant="default")

                def on_mount(self):
                    try:
                        w = getattr(self.app, "size", None)
                        if w and (w.width < 75 or (w.width / max(1, w.height)) < 2.0):
                            self.add_class("is-portrait")
                    except Exception:
                        pass
                    try:
                        self.query_one("#btn-signout-cancel", Button).focus()
                    except Exception:
                        pass

                def action_cancel(self):
                    self.dismiss(False)

                def on_button_pressed(self, event):
                    if event.button.id == "btn-signout-yes":
                        self.dismiss(True)
                    else:
                        self.dismiss(False)

            def _on_confirmed(confirmed):
                if confirmed:
                    self._do_execute_signout()

            self.push_screen(SignOutModal(), _on_confirmed)

        def _handle_quit(self):
            """Prompt ultra-responsive confirmation modal before quitting."""
            from textual.screen import Screen
            from textual.containers import Vertical, Horizontal
            from textual.widgets import Static, Button
            from textual.binding import Binding

            class QuitModal(Screen):
                """Ultra-responsive quit confirmation modal."""
                DEFAULT_CSS = """
                QuitModal {
                    align: center middle;
                    background: $app-background 75%;
                    width: 100%;
                    height: 100%;
                }
                #quit-box {
                    width: 90%;
                    max-width: 46;
                    height: auto;
                    background: $surface;
                    border: round $error;
                    padding: 1 2;
                    layout: vertical;
                    align: center middle;
                }
                #quit-title {
                    color: $error;
                    text-style: bold;
                    text-align: center;
                    margin-bottom: 1;
                }
                #quit-prompt {
                    text-align: center;
                    margin-bottom: 1;
                    color: $text;
                }
                #quit-buttons {
                    height: 3;
                    width: 100%;
                    align: center middle;
                    layout: horizontal;
                }
                #quit-buttons Button {
                    margin: 0 1;
                    min-width: 12;
                    height: 3;
                }
                QuitModal.is-portrait #quit-buttons,
                .is-portrait #quit-buttons {
                    layout: vertical;
                    height: auto;
                }
                QuitModal.is-portrait #quit-buttons Button,
                .is-portrait #quit-buttons Button {
                    width: 100%;
                    margin: 1 0;
                }
                """

                BINDINGS = [
                    Binding("escape", "cancel", "Cancel"),
                ]

                def compose(self):
                    with Vertical(id="quit-box"):
                        yield Static("✕  QUIT CAT", id="quit-title")
                        yield Static("Are you sure you want to quit CAT?", id="quit-prompt")
                        with Horizontal(id="quit-buttons"):
                            yield Button("✕  Quit Application  ", id="btn-quit-yes", variant="error")
                            yield Button("  Cancel  ", id="btn-quit-cancel", variant="default")

                def on_mount(self):
                    try:
                        w = getattr(self.app, "size", None)
                        if w and (w.width < 75 or (w.width / max(1, w.height)) < 2.0):
                            self.add_class("is-portrait")
                    except Exception:
                        pass
                    try:
                        self.query_one("#btn-quit-cancel", Button).focus()
                    except Exception:
                        pass

                def action_cancel(self):
                    self.dismiss(False)

                def on_button_pressed(self, event):
                    if event.button.id == "btn-quit-yes":
                        self.dismiss(True)
                    else:
                        self.dismiss(False)

            def _on_quit_confirmed(confirmed):
                if confirmed:
                    self.exit()

            self.push_screen(QuitModal(), _on_quit_confirmed)'''

assert target4 in content, "target4 not found"
content = content.replace(target4, replace4, 1)

# 5. Update on_nav_action to route quit to _handle_quit
target5 = '''            if action == "signout":
                self._handle_signout()
                return'''

replace5 = '''            if action == "signout":
                self._handle_signout()
                return

            if action == "quit":
                self._handle_quit()
                return'''

assert target5 in content, "target5 not found"
content = content.replace(target5, replace5, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("calc_terminal/ui/app.py updated successfully.")

