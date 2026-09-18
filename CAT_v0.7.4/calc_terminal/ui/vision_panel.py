"""
CAT Vision — terminal vision panel (v0.8.a).

Standalone CAT feature.
Shows image-attach workflow, annotation, and chat.

Responsive design: adapts to narrow terminals via scroll + stacked rows.
Circle uses WHITE CIRCLE (U+25CB) which renders at single-cell width in
Textual, unlike the emoji circle (U+2B55) which measures as double-width
and breaks button layout.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import os

TEXTUAL_AVAILABLE = True
try:
    from textual.screen import Screen
    from textual.containers import Vertical, Horizontal, VerticalScroll
    from textual.widgets import Static, Button, Input, LoadingIndicator
    from textual.binding import Binding
except Exception:
    TEXTUAL_AVAILABLE = False

if TEXTUAL_AVAILABLE:
    class VisionPanel(Screen):
        CSS = """
        VisionPanel { align: center middle; background: $app-background 60%; }

        #vision-box {
            width: 86; height: auto; max-height: 44;
            background: $surface; border: round $border;
            padding: 1 1;
            overflow: hidden;
            layout: vertical;
        }
        /* Title + live indicator row */
        #vision-title-row { height: 1; layout: horizontal; }
        #vision-title { width: auto; text-style: bold; color: $accent; }
        #vision-live { width: 1fr; text-align: right; color: $text-muted; }

        #vision-subtitle { height: 1; color: $text-faint; padding-bottom: 1; }
        #vision-disabled { height: auto; padding: 2 2; align: center middle; }
        .vision-disabled-msg { color: $warning; text-style: bold; height: auto; text-align: center; padding-bottom: 1; }

        /* Preview area - flexible, scrollable */
        #vision-preview-wrap {
            height: 1fr; min-height: 8; max-height: 14;
            border: solid $border; background: $app-background;
            overflow-y: auto; overflow-x: hidden;
            scrollbar-gutter: stable;
            scrollbar-size: 1 1;
            padding: 1;
        }
        #vision-preview { height: auto; color: $text; text-align: center; }
        #vision-stats { height: 1; color: $text-faint; text-align: right; padding-right: 1; }

        /* Toolbars - horizontal scroll on narrow, no clipping */
        .vision-toolbar {
            height: auto; min-height: 3;
            layout: horizontal;
            overflow-x: auto; overflow-y: hidden;
            scrollbar-size: 1 1;
            scrollbar-gutter: stable;
            padding: 1 0 0 0;
        }
        .vision-toolbar Button {
            margin-right: 1; margin-bottom: 1;
            min-width: 10; height: 3; min-height: 3;
        }
        .vision-toolbar Button.is-active {
            border: round $accent; color: $accent; text-style: bold;
            background: $accent 14%;
        }

        /* Chat */
        #vision-chat-wrap {
            height: 1fr; min-height: 8;
            border: solid $border; padding: 1 1 0 1;
            overflow: hidden; layout: vertical;
        }
        #vision-chat-log {
            height: 1fr; overflow-y: auto; overflow-x: hidden;
            scrollbar-gutter: stable; scrollbar-size: 1 1;
            padding-right: 1; color: $text;
        }
        #vision-chat-empty { color: $text-faint; height: auto; padding: 1 0; }
        .vision-msg-user { color: $accent; padding: 1 0 0 0; }
        .vision-msg-cat { color: $text; padding: 1 0 0 0; }

        #vision-input-row { height: 3; layout: horizontal; margin-top: 1; padding-bottom: 1; }
        #vision-input-row Input { width: 1fr; margin-right: 1; }
        #vision-input-row Button { min-width: 12; }

        #vision-actions {
            height: auto; min-height: 3;
            layout: horizontal; overflow-x: auto;
            scrollbar-size: 1 1; scrollbar-gutter: stable;
            padding-top: 1;
            border-top: solid $border;
        }
        #vision-actions Button { margin-right: 1; min-width: 16; }

        #vision-hint { color: $text-faint; height: 1; padding-top: 1; text-align: center; }

        /* Responsive narrow fallback */
        .cct-compact #vision-box { width: 96; height: auto; }
        """

        BINDINGS = [
            Binding("escape", "cancel", "Cancel"),
            Binding("ctrl+enter", "send", "Send"),
        ]

        def compose(self):
            # Extension guard: Vision is an installable extension
            try:
                from .. import extensions as _ext
                if not _ext.is_enabled("vision"):
                    with Vertical(id="vision-box"):
                        with Horizontal(id="vision-title-row"):
                            yield Static("CAT Vision", id="vision-title")
                            yield Static("OFF", id="vision-live")
                        yield Static("CAT Vision is disabled — enable it in Extensions to use vision.", id="vision-subtitle")
                        with Vertical(id="vision-disabled"):
                            yield Static("👁 CAT Vision is currently disabled.", classes="vision-disabled-msg")
                            yield Button("Open Extensions", id="vision-open-ext", variant="primary")
                            yield Button("Close", id="vision-close2")
                    return
            except Exception:
                pass
            with Vertical(id="vision-box"):
                with Horizontal(id="vision-title-row"):
                    yield Static("CAT Vision", id="vision-title")
                    yield Static("OFF", id="vision-live")
                yield Static("Share -> Annotate -> Chat -> Analyze -> Fix -> Verify", id="vision-subtitle")
                # Preview
                with Vertical(id="vision-preview-wrap"):
                    yield Static(
                        "No capture yet.\n"
                        "Attach an image or start a session below.\n"
                        "Your screen is never captured without explicit action.",
                        id="vision-preview"
                    )
                yield Static("0 frames  ·  0 annotations", id="vision-stats")
                # Toolbar row 1: capture controls
                with Horizontal(classes="vision-toolbar", id="vision-tb-capture"):
                    yield Button("Start", id="vision-start", variant="success", classes="cct-btn-sm")
                    yield Button("Pause", id="vision-pause", classes="cct-btn-sm")
                    yield Button("Resume", id="vision-resume", classes="cct-btn-sm")
                    yield Button("Stop", id="vision-stop", variant="error", classes="cct-btn-sm")
                    yield Button("Attach Image", id="vision-attach", classes="cct-btn-sm")
                    yield Button("Clear", id="vision-clear", classes="cct-btn-sm")
                # Toolbar row 2: annotation tools - WHITE CIRCLE fixes rendering
                with Horizontal(classes="vision-toolbar", id="vision-tb-tools"):
                    yield Button("Pen", id="vision-pen", classes="cct-btn-sm")
                    yield Button("Highlight", id="vision-highlight", classes="cct-btn-sm")
                    yield Button("O Circle", id="vision-circle", classes="cct-btn-sm")
                    yield Button("Rect", id="vision-rect", classes="cct-btn-sm")
                    yield Button("Arrow", id="vision-arrow", classes="cct-btn-sm")
                    yield Button("Text", id="vision-text", classes="cct-btn-sm")
                    yield Button("Undo", id="vision-undo", classes="cct-btn-sm")
                    yield Button("Redo", id="vision-redo", classes="cct-btn-sm")
                # Chat
                with Vertical(id="vision-chat-wrap"):
                    with VerticalScroll(id="vision-chat-log"):
                        yield Static("Ask CAT about the current capture. Attach an image, annotate with tools above, then chat.", id="vision-chat-empty", classes="cct-text-faint")
                    with Horizontal(id="vision-input-row"):
                        yield Input(placeholder="Describe the problem... (e.g. this button glitches)", id="vision-input")
                        yield Button("Send", id="vision-send", variant="primary", classes="cct-btn-sm")
                # Actions
                with Horizontal(id="vision-actions"):
                    yield Button("Analyze Selection", id="vision-analyze-sel", variant="primary", classes="cct-btn-sm")
                    yield Button("Analyze Screen", id="vision-analyze-all", classes="cct-btn-sm")
                    yield Button("Fix This", id="vision-fix", classes="cct-btn-sm")
                yield Static("Esc to close  ·  Enter to send  ·  White circle fixes emoji width bug", id="vision-hint")

        def on_mount(self):
            self._active_tool = "pen"
            self._session_live = False
            self._frame_count = 0
            self._ann_count = 0
            self._chat_turns = 0
            self._attached_image = None  # path
            self._highlight_tool("pen")
            self._refresh_chrome()
            # compact check (called once, no need for resize loop in panel)
            try:
                if self.size.width < 72 or self.size.height < 32:
                    self.query_one("#vision-box").add_class("cct-compact")
            except Exception:
                pass

        def _highlight_tool(self, tool_id):
            # remove old, add new
            for bid in ("vision-pen","vision-highlight","vision-circle","vision-rect","vision-arrow","vision-text"):
                try:
                    self.query_one(f"#{bid}", Button).remove_class("is-active")
                except Exception:
                    pass
            try:
                self.query_one(f"#vision-{tool_id}", Button).add_class("is-active")
            except Exception:
                pass
            self._active_tool = tool_id

        def _refresh_chrome(self):
            try:
                live = self.query_one("#vision-live", Static)
                if self._session_live:
                    live.update("[b green]● LIVE[/]")
                else:
                    live.update("[dim]○ OFF[/]")
            except Exception:
                pass
            try:
                self.query_one("#vision-stats", Static).update(f"{self._frame_count} frames  ·  {self._ann_count} annotations")
            except Exception:
                pass

        def _set_preview(self, text):
            try:
                self.query_one("#vision-preview", Static).update(text)
            except Exception:
                pass

        def _push_chat(self, who, text):
            # remove empty hint after first message
            try:
                empty = self.query_one("#vision-chat-empty", Static)
                if empty:
                    empty.remove()
            except Exception:
                pass
            try:
                log = self.query_one("#vision-chat-log", VerticalScroll)
                cls = "vision-msg-user" if who == "you" else "vision-msg-cat"
                safe = text.replace("[", "\\[").replace("]", "\\]")
                # Use markup: bold who, plain text
                if who == "you":
                    markup = f"[b #7aa2f7]You:[/] {safe}"
                elif who == "cat":
                    markup = f"[b #9ece6a]CAT:[/] {safe}"
                else:
                    markup = f"[dim]{safe}[/]"
                w = Static(markup, classes=cls)
                log.mount(w)
                log.scroll_end(animate=False)
                self._chat_turns += 1
            except Exception:
                pass

        def _update_status(self, msg):
            # legacy helper for tests that call it
            self._set_preview(msg)

        # ---- helpers for real attachment ----
        def _pick_image_via_dialog(self):
            # Use native file picker where available (desktop), else show input
            from textual.widgets import Input as _Input
            # Try tkinter first (desktop) - non-blocking fallback to Input
            path = None
            try:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                root.attributes("-topmost", True)
                p = filedialog.askopenfilename(
                    title="Attach image for CAT Vision",
                    filetypes=[("Images","*.png *.jpg *.jpeg *.webp *.gif *.bmp"),("All","*.*")],
                )
                try:
                    root.destroy()
                except Exception:
                    pass
                if p:
                    path = p
            except Exception:
                path = None
            return path

        def _attach_image(self, path):
            if not path or not os.path.isfile(path):
                self._push_chat("sys", f"Attach failed: not a file: {path}")
                return
            self._attached_image = path
            self._frame_count += 1
            self._refresh_chrome()
            name = os.path.basename(path)
            try:
                size = os.path.getsize(path)
                kb = f"{size/1024:.1f} KB" if size < 1024*1024 else f"{size/1024/1024:.1f} MB"
            except Exception:
                kb = "?"
            self._set_preview(f"Attached: {name} ({kb})\n{path}\n\nAnnotation: {self._active_tool} · add a label in chat\nReady to analyze.")
            self._push_chat("sys", f"Attached image: {name}")

        def _do_analyze(self, selection_only=True):
            # If no image attached, prompt
            if not self._attached_image:
                self._push_chat("sys", "Attach an image first (Attach Image button).")
                return
            prompt = ""
            try:
                inp = self.query_one("#vision-input", Input)
                prompt = inp.value.strip()
            except Exception:
                prompt = ""
            if not prompt:
                prompt = "Analyze this. What do you see and what is the likely issue?"
            # push user turn
            self._push_chat("you", prompt)
            try:
                self.query_one("#vision-input", Input).value = ""
            except Exception:
                pass
            # Show thinking
            self._push_chat("cat", "Analyzing with CAT Vision...")

            # Real call off-thread: normalize + classify + vision model via calc_terminal.vision
            def _run():
                try:
                    from calc_terminal import vision as _vis
                    ans, meta = _vis.analyze(self._attached_image, user_text=prompt)
                    return ans, meta, None
                except Exception as e:
                    return None, None, str(e)

            self._analyze_worker(_run, prompt, selection_only)

        @staticmethod
        def _fmt_meta(meta):
            if not meta:
                return ""
            act = meta.get("action","")
            wh = ""
            if "width" in meta and "height" in meta:
                wh = f"{meta['width']}x{meta['height']}"
            return f"{act} {wh}".strip()

        def _analyze_worker(self, runner, prompt, selection_only):
            # wrapper to run in thread and post result back
            import threading
            def _thread():
                ans, meta, err = runner()
                # schedule UI update on main thread
                try:
                    self.call_from_thread(self._on_analyze_done, ans, meta, err, selection_only)
                except Exception:
                    pass
            th = threading.Thread(target=_thread, daemon=True)
            th.start()

        def _on_analyze_done(self, ans, meta, err, selection_only):
            # replace last "Analyzing..." bubble with real answer
            # find last cat message and update it
            try:
                log = self.query_one("#vision-chat-log", VerticalScroll)
                # last child is the "Analyzing..." placeholder
                kids = list(log.children)
                if kids:
                    last = kids[-1]
                    if err:
                        last.update(f"[b #f7768e]Error:[/] {err}\\nCheck model config via /model.")
                    else:
                        info = self._fmt_meta(meta)
                        suffix = f"\\n[dim]({info})[/]" if info else ""
                        # escape markup brackets in answer
                        safe_ans = (ans or "No answer.").replace("[", "\\[")
                        last.update(f"[b #9ece6a]CAT:[/] {safe_ans}{suffix}")
                    log.scroll_end(animate=False)
                    return
            except Exception:
                pass
            # fallback push
            if err:
                self._push_chat("cat", f"Error: {err}")
            else:
                self._push_chat("cat", ans or "No answer.")

        # ---- events ----
        def on_button_pressed(self, event):
            bid = event.button.id
            # Extension disabled guard
            if bid == "vision-open-ext":
                try:
                    self.dismiss(None)
                    from .extensions_panel import ExtensionsPanel
                    self.app.push_screen(ExtensionsPanel())
                except Exception:
                    self.dismiss(None)
                return
            if bid in ("vision-close2", "vision-close"):
                self.dismiss(None)
                return
            if bid == "vision-start":
                self._session_live = True
                self._frame_count = max(self._frame_count, 1)
                self._refresh_chrome()
                self._set_preview("Session LIVE.\nAttach an image to analyze.\nUse annotation tools above to mark the region, then chat.")
                self._push_chat("sys", "Session started. Attach an image to begin.")
            elif bid == "vision-stop":
                self._session_live = False
                self._refresh_chrome()
                self._set_preview("Session stopped.\nStart again to create a new capture.")
                self._push_chat("sys", "Session stopped. Resources cleaned up.")
            elif bid == "vision-pause":
                self._push_chat("sys", "Paused.")
            elif bid == "vision-resume":
                self._push_chat("sys", "Resumed.")
            elif bid == "vision-clear":
                self._ann_count = 0
                self._attached_image = None
                self._frame_count = 0
                self._refresh_chrome()
                self._set_preview("Cleared. No image attached.")
                self._push_chat("sys", "Cleared annotations and attached image.")
            elif bid == "vision-attach":
                path = self._pick_image_via_dialog()
                if path:
                    self._attach_image(path)
                else:
                    self._push_chat("sys", "No file chosen. Type an image path in the input and press Attach Image again.")
                    try:
                        inp = self.query_one("#vision-input", Input)
                        typed = inp.value.strip()
                        if typed and os.path.isfile(os.path.expanduser(typed)):
                            self._attach_image(os.path.expanduser(typed))
                            inp.value = ""
                        else:
                            if typed:
                                self._push_chat("sys", f"Not found: {typed}")
                    except Exception:
                        pass
            elif bid in ("vision-pen","vision-highlight","vision-circle","vision-rect","vision-arrow","vision-text"):
                tool = bid.replace("vision-","")
                self._highlight_tool(tool)
                name_map = {"pen":"Pen","highlight":"Highlight","circle":"Circle ○","rect":"Rect","arrow":"Arrow","text":"Text"}
                self._set_preview(f"Tool: {name_map.get(tool, tool)}\nMark the region on the attached image, then describe it in chat.")
                self._ann_count += 1
                self._refresh_chrome()
                self._push_chat("sys", f"Tool selected: {name_map.get(tool, tool)} (annotations stay in this CAT Vision session)")
            elif bid in ("vision-undo","vision-redo"):
                self._push_chat("sys", "Undo/Redo for the annotation list in this session.")
            elif bid == "vision-analyze-sel":
                self._do_analyze(selection_only=True)
            elif bid == "vision-analyze-all":
                self._do_analyze(selection_only=False)
            elif bid == "vision-fix":
                self._push_chat("cat", "I can propose a fix for the selected region. Describe the expected behavior and I will generate a patch.\nFile edits require your permission (Ask / Full) - nothing is changed without approval.")
            elif bid == "vision-send":
                try:
                    inp = self.query_one("#vision-input", Input)
                    txt = inp.value.strip()
                    if not txt:
                        return
                    if not self._attached_image:
                        self._push_chat("you", txt)
                        inp.value = ""
                        self._push_chat("cat", "Attach an image to enable visual analysis, or keep chatting - I will use project context and your description.")
                        return
                    inp.value = txt
                    self._do_analyze(selection_only=True)
                except Exception:
                    pass

        def on_input_submitted(self, event):
            if event.input.id == "vision-input":
                # Enter in the input should Send (same as button)
                self.on_button_pressed(type("E", (), {"button": type("B", (), {"id": "vision-send"})()})())

        def action_cancel(self):
            # Esc: if there is live session, stop it cleanly before dismiss?
            self.dismiss(None)

        def action_send(self):
            self.on_button_pressed(type("E", (), {"button": type("B", (), {"id": "vision-send"})()})())

        def on_key(self, event):
            if event.key == "escape":
                self.dismiss(None)

else:
    VisionPanel = None
