"""
CCT UI — StickyComposer: THE composer. One bordered card, permanently
docked at the bottom of the screen, that never scrolls. Prompt glyph +
auto-expanding editor + rotating placeholder at the top, the command
palette living inline right under it, an AttachmentBar, a
ComposerFooter control row, and a togglable PermissionsSettingsPanel —
all one component, not floating pieces or stacked toolbars.

Renders state and posts events (MessageSubmitted, AttachmentAdded via
AttachmentBar, PasteCollapsed/Expanded, NotebookChanged via
ComposerFooter, CommandExecuted). Never calls into ConversationView or
decides what a submitted message means — CCTApp does that.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import re

TEXTUAL_AVAILABLE = True
try:
    from textual.containers import Horizontal, Vertical, Container
    from textual.widgets import Static, TextArea, Button
    from textual.reactive import reactive
    from textual.screen import Screen
except Exception:
    TEXTUAL_AVAILABLE = False

from .events import MessageSubmitted, MessageRewritten, CommandExecuted, PasteExpanded
from .command_palette import CommandPalette, TEXTUAL_AVAILABLE as _PALETTE_OK
from .attachments import (AttachmentBar, PASTE_COLLAPSE_THRESHOLD, PASTE_WORD_THRESHOLD,
                           TEXTUAL_AVAILABLE as _ATTACH_OK)
from .footer import ComposerFooter, TEXTUAL_AVAILABLE as _FOOTER_OK
from .permission_panel import PermissionsSettingsPanel, TEXTUAL_AVAILABLE as _PERM_OK
from .. import mathtext

def _safe_glyph(emoji: str, fallback: str) -> str:
    try:
        import sys
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        emoji.encode(enc)
        return emoji
    except Exception:
        return fallback

TEXTUAL_AVAILABLE = TEXTUAL_AVAILABLE and _PALETTE_OK and _ATTACH_OK and _FOOTER_OK and _PERM_OK

# The input's one static hint, shown inside the TextArea itself while
# it is empty (Textual renders it dimmed in the editor area). v0.7.8.45:
# the old design showed a SEPARATE Static above the input whose text
# rotated through a suggestion list every ~2.6s ("Ask Chemistry...",
# "Molecular Geometry", ...). That widget read as a second prompt area,
# made the input look misaligned on first render, and caused a visible
# layout jump the moment typing started (the placeholder row appeared/
# disappeared above the editor). Replaced by TextArea's native
# placeholder: one line, inside the input, no extra widget, no rotation.
_INPUT_PLACEHOLDER = "Type a message\u2026"

# Large-paste confirmation threshold (5 KiB = 5120 characters).
# Pasting more than this shows the "Paste anyway / Cancel" warning
# instead of inserting (or collapsing) blindly; the ENTIRE approved
# clipboard text is then written into the composer input in one
# atomic document operation — never per-character key events, never
# truncated, never duplicated.
LARGE_PASTE_THRESHOLD = 5 * 1024

# v0.7.2 roadmap "Live preview while typing" trigger: a $...$/\(...\)/
# \[...\] delimiter pair, or any backslash-command mathtext.py actually
# knows how to convert (\frac, \sqrt, \sum, Greek words, etc.) — cheap
# substring/regex checks so this runs on every keystroke without
# calling render_math() on plain prose that has nothing to preview.
_LATEX_HINT_RE = re.compile(
    r"\$[^$]+\$|\\\(.+?\\\)|\\\[.+?\\\]|\\(?:frac|sqrt|sum|prod|int|begin)\b"
    r"|\^\{|_\{|\^-?[0-9A-Za-z]|_-?[0-9A-Za-z]"
)


if TEXTUAL_AVAILABLE:

    class _ConfirmPaste(Screen):
        """Large-paste confirmation dialog (v0.7.8.45 clipboard-input
        fix). Same real-Screen-push pattern as _ConfirmClearRecent
        (ui/sidebar.py) / PermissionModeMenu (ui/header.py): a pushed
        Screen behaves like a modal — it blocks input beneath it —
        without being one.

        dismiss(True)  = "Paste anyway" — the caller inserts the ENTIRE
                         approved clipboard text into the composer.
        dismiss(False) = Cancel — nothing is pasted, clipboard and
                         composer input stay untouched."""

        BINDINGS = [
            ("escape", "cancel", "Cancel"),
            ("enter", "paste_anyway", "Paste anyway"),
        ]

        CSS = """
        _ConfirmPaste { align: center middle; background: $app-background 60%; }
        #cct-largepaste-box {
            width: 64; height: auto; background: $surface;
            border: round $warning; padding: 1 2;
        }
        #cct-largepaste-title { text-style: bold; color: $warning; padding-bottom: 1; }
        #cct-largepaste-msg { color: $text-muted; padding-bottom: 1; }
        #cct-largepaste-btns { height: 3; align-horizontal: right; }
        #cct-largepaste-btns Button { margin-left: 1; }
        """

        def __init__(self, char_count):
            super().__init__()
            self._char_count = char_count

        def on_mount(self):
            # Keyboard default: Enter = "Paste anyway". Focus the box
            # (not a Button, whose Enter would click it) so the screen
            # binding fires; Tab moves on to the buttons, Escape cancels.
            box = self.query_one("#cct-largepaste-box")
            box.can_focus = True
            box.focus()

        def compose(self):
            with Vertical(id="cct-largepaste-box"):
                yield Static("\u26a0  Warning", id="cct-largepaste-title")
                yield Static(
                    "You are about to paste text that is longer than 5 KiB.\n"
                    f"It contains {self._char_count:,} characters.\n"
                    "Do you wish to continue?",
                    id="cct-largepaste-msg")
                with Horizontal(id="cct-largepaste-btns"):
                    yield Button("Cancel", id="cct-largepaste-cancel")
                    yield Button("Paste anyway", id="cct-largepaste-ok",
                                 variant="primary")

        def on_button_pressed(self, event):
            self.dismiss(event.button.id == "cct-largepaste-ok")

        def action_paste_anyway(self):
            self.dismiss(True)

        def action_cancel(self):
            self.dismiss(False)

    class PromptIndicator(Static):
        """The `\u276f` glyph at the left of the composer — swaps to a
        dim streaming glyph while a reply is in flight, purely a render
        of `is_streaming`; it doesn't know why."""

        is_streaming = reactive(False)

        def __init__(self, id="cct-prompt-glyph"):
            super().__init__("\u276f", id=id)

        def watch_is_streaming(self, value):
            self.update("\u2026" if value else "\u276f")

        def on_click(self, event) -> None:
            try:
                self.app.query_one("#cct-input", ComposerInput).focus()
            except Exception:
                pass

    class ComposerInput(TextArea):
        """Auto-expanding editor: 3 lines minimum, grows to 10, then
        scrolls. Enter (or Ctrl+Enter) submits; Shift+Enter inserts a
        newline.

        `composer_ref` is the owning StickyComposer — drives the inline
        CommandPalette (opened by typing '/') and hands large pastes off
        to the AttachmentBar as collapsible chips.
        """

        def __init__(self, *args, composer_ref=None, **kwargs):
            kwargs.setdefault("placeholder", _INPUT_PLACEHOLDER)
            super().__init__(*args, **kwargs)
            self._composer = composer_ref
            self.show_line_numbers = False
            self.highlight_cursor_line = False

        async def _on_key(self, event):
            palette = self._composer.palette if self._composer else None
            # Only intercept keys for palette if palette is open and user is typing a slash command
            if palette is not None and palette.is_open() and self.text.strip().startswith("/"):
                if event.key == "down":
                    event.stop()
                    try:
                        event.prevent_default()
                    except Exception:
                        pass
                    palette.move(1)
                    return
                if event.key == "up":
                    event.stop()
                    try:
                        event.prevent_default()
                    except Exception:
                        pass
                    palette.move(-1)
                    return
                if event.key == "pagedown":
                    event.stop()
                    try:
                        event.prevent_default()
                    except Exception:
                        pass
                    palette.move_page(1)
                    return
                if event.key == "pageup":
                    event.stop()
                    try:
                        event.prevent_default()
                    except Exception:
                        pass
                    palette.move_page(-1)
                    return
                if event.key in ("enter", "tab"):
                    event.stop()
                    try:
                        event.prevent_default()
                    except Exception:
                        pass
                    cmd = palette.selected_command()
                    if self._composer is not None:
                        self._composer._just_selected_suggestion = True
                        self._composer._palette_saved_text = None
                    if cmd:
                        if cmd.startswith("/"):
                            self.text = cmd + " "
                        else:
                            self.text = cmd
                        try:
                            self.move_cursor(self.document.end)
                        except Exception:
                            pass
                    # Accepting a command deliberately replaces whatever
                    # Ctrl+P stashed — no restore afterwards.
                    palette.close()
                    return
                if event.key == "escape":
                    event.stop()
                    try:
                        event.prevent_default()
                    except Exception:
                        pass
                    palette.close()
                    # v0.7.9.5: Ctrl+P overwrote an unsent draft — give
                    # it back on Escape instead of losing it.
                    if self._composer is not None:
                        saved = getattr(self._composer, "_palette_saved_text", None)
                        self._composer._palette_saved_text = None
                        if saved:
                            self.text = saved
                            try:
                                self.move_cursor(self.document.end)
                            except Exception:
                                pass
                    return

            if event.key == "escape" and self._composer is not None:
                try:
                    from .permission_panel import PermissionsSettingsPanel
                    panel = self._composer.query_one(PermissionsSettingsPanel)
                    if panel.has_class("open"):
                        event.stop()
                        try:
                            event.prevent_default()
                        except Exception:
                            pass
                        panel.close_panel()
                        return
                except Exception:
                    pass

            if event.key == "alt+a":
                event.stop()
                try:
                    event.prevent_default()
                except Exception:
                    pass
                if self._composer is not None:
                    try:
                        self._composer.app.action_prompt_attach()
                    except Exception:
                        pass
                return

            if event.key == "alt+p":
                event.stop()
                try:
                    event.prevent_default()
                except Exception:
                    pass
                if self._composer is not None:
                    try:
                        self._composer.app.action_toggle_permissions()
                    except Exception:
                        pass
                return

            if event.key == "ctrl+b":
                event.stop()
                try:
                    event.prevent_default()
                except Exception:
                    pass
                if self._composer is not None:
                    try:
                        self._composer.app.action_toggle_sidebar()
                    except Exception:
                        pass
                return

            if (event.key == "escape" and self._composer is not None
                    and getattr(self._composer, "_editing_turn_id", None) is not None):
                # Esc cancels Rewrite's edit mode (minor-bug-fix spec) —
                # only reachable when the palette isn't open, since that
                # branch above already handled/returned for Esc in that
                # case.
                event.stop()
                self._composer.cancel_edit()
                return

            if event.key in ("escape", "ctrl+c") and self._composer is not None:
                # If text is selected and user hits ctrl+c, preserve normal copy
                if event.key == "ctrl+c" and getattr(self, "selected_text", None):
                    pass
                else:
                    is_streaming = (
                        getattr(self._composer.prompt_indicator, "is_streaming", False)
                        or getattr(getattr(self._composer, "app", None), "_is_streaming", False)
                        or getattr(getattr(self._composer, "app", None), "_streaming_turn_id", None) is not None
                    )
                    if is_streaming or event.key == "ctrl+c" or event.key == "escape":
                        event.stop()
                        try:
                            event.prevent_default()
                        except Exception:
                            pass
                        try:
                            self._composer.app.action_cancel_streaming()
                        except Exception:
                            pass
                        return

            if event.key in ("enter", "ctrl+enter"):
                # Plain Enter submits (or interrupts if AI is currently streaming).
                # Ctrl+Enter behaves identically for muscle memory.
                event.stop()
                try:
                    event.prevent_default()
                except Exception:
                    pass
                if palette is not None and palette.is_open():
                    palette.close()
                if self._composer is not None:
                    if getattr(self._composer.prompt_indicator, "is_streaming", False):
                        try:
                            self._composer.app.action_cancel_streaming()
                        except Exception:
                            pass
                    else:
                        self._composer.submit()
                return

            if event.key == "shift+enter":
                event.stop()
                try:
                    event.prevent_default()
                except Exception:
                    pass
                self.insert("\n")
                return

            if self._composer is not None:
                if event.key == "up" and (not self.text.strip() or self._composer.history_active()):
                    event.stop()
                    self._composer.recall_history(-1, self)
                    return
                if event.key == "down" and self._composer.history_active():
                    event.stop()
                    self._composer.recall_history(1, self)
                    return

            await super()._on_key(event)

        async def _on_paste(self, event):
            text = getattr(event, "text", "") or ""
            # v0.7.6 Patch 1, Fix 5: pasting (or drag-dropping, which
            # Windows terminals deliver as a path paste) one or more
            # file paths turns them into attachment chips instead of
            # dumping literal paths into the message. Everything else
            # keeps the existing small/large paste behaviour below.
            # v0.8.1: routed through the app's single attach entry point
            # so validation, recents and TXT-import behave identically
            # for drag-and-drop and Browse origins.
            if self._composer is not None:
                from .attachments import paths_from_paste
                paths = paths_from_paste(text)
                if paths:
                    event.stop()
                    try:
                        event.prevent_default()
                    except Exception:
                        pass
                    try:
                        self._composer.app.attach_files_from_ui(
                            paths, source="drag_and_drop")
                    except Exception:
                        for p in paths:  # never dead-end on an app error
                            self._composer.add_attachment(
                                p, source="drag_and_drop")
                    return
            # v0.7.8.45 PowerShell paste fix: Windows console hosts
            # (conhost / Windows Terminal — whatever shell runs in
            # them) can truncate or drop very large bracketed-paste
            # payloads before Textual ever receives them. When the
            # delivered text is a strict prefix of the OS clipboard's
            # content, the clipboard is the authoritative copy — restore
            # it BEFORE the size checks below, so the >5 KiB warning
            # still fires and "Paste anyway" delivers the COMPLETE text.
            # Other terminals and intact deliveries are never touched.
            try:
                from .. import terminal_host
                delivered = len(text)
                text, source = terminal_host.clipboard_payload_override(text)
                if source != "terminal":
                    self.log.debug(
                        "paste: %s (%d chars delivered, %d chars recovered)",
                        source, delivered, len(text))
                    # the recovered payload is authoritative for every
                    # path below (large warning, small direct insert,
                    # collapse chip): keep the event in sync so
                    # TextArea._on_paste's own insert uses it too.
                    event.text = text
            except Exception:
                pass
            # Normalize Windows CRLF to LF so TextArea handles lines cleanly
            if "\r" in text:
                text = text.replace("\r\n", "\n").replace("\r", "\n")

            # Always insert pasted text directly into the composer input — allowing big
            # sentences, large word counts, code snippets, and multiline text
            # to paste cleanly without getting blocked by a 5 KiB dialog or forced collapse chip.
            event.stop()
            try:
                event.prevent_default()
            except Exception:
                pass
            self.insert(text)
            self.focus()
            return

    class StickyComposer(Vertical):
        """THE composer card. See module docstring."""

        def __init__(self, id="cct-composer", model_label="no model"):
            super().__init__(id=id)
            self._model_label = model_label
            self._sent_history = []
            self._history_index = None
            self._stream_start = None
            self._stream_timer = None
            self._prompt_hint = ""
            self._chunk_seen = False
            self._spin_tick = 0
            self._stream_turn_id: str | None = None
            # spinner frames for real activity (braille)
            self._real_spinner = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
            # Rewrite (minor-bug-fix spec): when set, this composer is
            # editing an existing user turn in place rather than
            # composing a brand-new message — see start_edit()/
            # cancel_edit()/submit().
            self._editing_turn_id = None
            # v0.7.9.0: explicit height set by the composer resize handle
            # (resizers.ComposerResizeHandle). None = natural auto height.
            self._explicit_height = None
            # v0.7.9.5: Ctrl+P draft preservation — when the palette is
            # force-opened over an unsent draft, the draft is stashed
            # here; Escape restores it, accepting a command clears it.
            self._palette_saved_text = None

        @property
        def context_tokens(self):
            return self.query_one(ComposerFooter).context_tokens

        @context_tokens.setter
        def context_tokens(self, value):
            self.query_one(ComposerFooter).context_tokens = value

        @property
        def palette(self):
            return self.query_one(CommandPalette)

        @property
        def prompt_indicator(self):
            return self.query_one(PromptIndicator)

        def compose(self):
            with Horizontal(id="cct-streaming-row"):
                yield Static("", id="cct-streaming-status")
                yield Button(_safe_glyph("■ Stop", "Stop"), id="btn-stop", classes="cct-stop-btn", tooltip="Stop response (Esc)")
            yield Static("", id="cct-edit-banner")
            yield Static("", id="cct-latex-preview")
            with Horizontal(id="cct-prompt-row"):
                yield PromptIndicator()
                with Container(id="cct-editor-stack"):
                    editor = ComposerInput(id="cct-input", composer_ref=self)
                    editor.show_line_numbers = False
                    editor.highlight_cursor_line = False
                    yield editor
            # Sibling of the prompt row, not nested in cct-editor-stack (which
            # is height-capped for the input alone) so the palette's own rows
            # aren't clipped by the editor's height cap.
            yield CommandPalette()
            yield AttachmentBar()
            yield ComposerFooter(model_label=self._model_label)
            yield PermissionsSettingsPanel()

        def on_mount(self):
            self.query_one("#cct-input", ComposerInput).focus()
            self._apply_compact_height()
            self.set_explicit_height(None)

        def on_unmount(self):
            # The 100ms streaming ticker is owned by this widget: stop
            # it here so a torn-down composer never keeps ticking.
            try:
                if self._stream_timer is not None:
                    self._stream_timer.stop()
            except Exception:
                pass
            self._stream_timer = None
            try:
                from .. import ai_modes
                self.set_ai_mode(ai_modes.current_mode())
            except Exception:
                pass

        def set_explicit_height(self, height):
            """v0.7.9.0: the composer resize handle's target setter.
            Sets min_height and height so user dragging expands the base height,
            while keeping height auto-resizable for palettes/multiline when reset."""
            try:
                from .resizers import COMPOSER_MIN_HEIGHT
                if height is None or int(height) <= COMPOSER_MIN_HEIGHT:
                    self._explicit_height = None
                    self.styles.height = "auto"
                    self.styles.min_height = COMPOSER_MIN_HEIGHT
                    self.styles.max_height = "32%"
                    try:
                        editor = self.query_one("#cct-input", ComposerInput)
                        stack = self.query_one("#cct-editor-stack", Container)
                        row = self.query_one("#cct-prompt-row")
                        line_count = max(2, min(5, editor.text.count("\n") + 1))
                        editor.styles.height = line_count
                        stack.styles.height = line_count
                        row.styles.height = "auto"
                    except Exception:
                        pass
                    return
                hi = min(8, max(COMPOSER_MIN_HEIGHT + 1,
                                 int(self.screen.size.height * 0.28)))
                height = max(COMPOSER_MIN_HEIGHT, min(hi, int(height)))
                self._explicit_height = height
                self.styles.height = height
                self.styles.min_height = height
                self.styles.max_height = "32%"
                try:
                    editor = self.query_one("#cct-input", ComposerInput)
                    stack = self.query_one("#cct-editor-stack", Container)
                    row = self.query_one("#cct-prompt-row")
                    editor.styles.height = "1fr"
                    stack.styles.height = "1fr"
                    row.styles.height = "1fr"
                except Exception:
                    pass
            except Exception:
                pass

        def on_resize(self):
            """v0.7.8.45: on short terminals (<= 20 rows) compress responsively."""
            self._apply_compact_height()

        def _apply_compact_height(self):
            try:
                short = self.screen.size.height <= 20
                try:
                    hints = self.query_one("#cct-kbhints", Static)
                    hints.display = not short
                except Exception:
                    pass
                editor = self.query_one("#cct-input", ComposerInput)
                stack = self.query_one("#cct-editor-stack", Container)
                row = self.query_one("#cct-prompt-row")
                if getattr(self, "_explicit_height", None):
                    stack.styles.min_height = 1
                    row.styles.min_height = 1
                    editor.styles.min_height = 1
                    return
                if short:
                    editor.styles.min_height = 1
                    editor.styles.max_height = 4
                    stack.styles.min_height = 1
                    stack.styles.max_height = 4
                    row.styles.min_height = 1
                    self.styles.max_height = "100%"
                else:
                    editor.styles.min_height = 1
                    avail = int(self.screen.size.height * 0.6) - 5
                    editor_max = max(2, min(10, avail))
                    editor.styles.max_height = editor_max
                    stack.styles.min_height = 1
                    stack.styles.max_height = editor_max
                    row.styles.min_height = 1
                    try:
                        from .permission_panel import PermissionsSettingsPanel
                        panel = self.query_one(PermissionsSettingsPanel)
                        self.styles.max_height = "85%" if panel.is_open else "75%"
                    except Exception:
                        self.styles.max_height = "75%"
            except Exception:
                pass

        def _rotate_placeholder(self):
            # v0.7.8.45: the rotating suggestion placeholder was removed
            # entirely (see _INPUT_PLACEHOLDER) — kept as a no-op stub so
            # any stale callers from older branches don't crash.
            return

        def set_model_label(self, label):
            self._model_label = label
            self.query_one(ComposerFooter).set_model_label(label)

        def set_ai_mode(self, mode_key):
            """Syncs the footer's mode badge after a `/mode`, `/agent`,
            `/build`, `/plan`, or `/notebook` command switches mode —
            keeps the clickable badge and the typed command in lock
            step without either one owning the other's state twice."""
            try:
                footer = self.query_one(ComposerFooter)
                footer.notebook_mode = mode_key
                footer.query_one("#badge-notebook").update(footer._mode_badge_markup(mode_key))
            except Exception:
                pass
            all_mode_classes = ["cct-mode-notebook", "cct-mode-research", "cct-mode-plan",
                                "cct-mode-build", "cct-mode-debugger", "cct-mode-agent"]
            for c in all_mode_classes:
                if c in self.classes:
                    self.remove_class(c)
            self.add_class(f"cct-mode-{mode_key}")

        def set_streaming(self, value, prompt_hint=None, turn_id=None):
            """Drives the composer's live status bar — REAL activity-driven,
            not fake stage. Shows the current running Live Activity's
            title/progress/elapsed/model — the ONE source of truth is
            ActivityManager. Falls back to a minimal generic spinner only
            if no real activity exists yet (never invents fake stages like
            'Analyzing Question...')."""
            import time
            self.prompt_indicator.is_streaming = value
            # store turn_id so the 100ms tick can query the real activity
            if value and turn_id:
                self._stream_turn_id = turn_id
            elif not value:
                self._stream_turn_id = None
            try:
                send_btn = self.query_one("#btn-send", Button)
                if value:
                    send_btn.label = _safe_glyph("⏸", "||")
                    send_btn.tooltip = "Interrupt response (Click || / Esc)"
                    send_btn.disabled = False
                    send_btn.set_class(True, "cct-btn-interrupt")
                else:
                    send_btn.label = _safe_glyph("➤", ">")
                    send_btn.tooltip = "Send message (Enter)"
                    send_btn.disabled = False
                    send_btn.set_class(False, "cct-btn-interrupt")
            except Exception:
                pass
            try:
                self.query_one("#btn-stop", Button).display = value
            except Exception:
                pass
            bar = self.query_one("#cct-streaming-status", Static)
            try:
                row = self.query_one("#cct-streaming-row")
            except Exception:
                row = None
            if value:
                self._stream_start = time.time()
                self._prompt_hint = prompt_hint or ""
                self._chunk_seen = False
                self._spin_tick = 0
                self._update_streaming_text()
                if row is not None:
                    row.add_class("active")
                bar.add_class("active")
                # 100ms tick for live elapsed + spinner. A second
                # set_streaming(True) before False must NOT orphan the
                # previous interval (rapid regenerate/switch otherwise
                # stacks one 10Hz ticker per call, forever).
                if self._stream_timer is not None:
                    try:
                        self._stream_timer.stop()
                    except Exception:
                        pass
                    self._stream_timer = None
                self._stream_timer = self.set_interval(0.1, self._update_streaming_text)
            else:
                if self._stream_timer is not None:
                    self._stream_timer.stop()
                    self._stream_timer = None
                if row is not None:
                    row.remove_class("active")
                    try:
                        row.display = False
                    except Exception:
                        pass
                bar.remove_class("active")
                try:
                    bar.update("")
                    bar.display = False
                except Exception:
                    pass
                try:
                    self.prompt_indicator.is_streaming = False
                except Exception:
                    pass
                self._stream_turn_id = None

        def note_chunk_received(self):
            """Tells the status bar real tokens have started arriving,
            so stage detection switches from the pre-token progression
            (Preparing/Thinking/Analyzing) to the post-token one
            (Building/Formatting/Finalizing) instead of staying stuck
            on 'Thinking' for the whole reply."""
            self._chunk_seen = True

        def _update_streaming_text(self):
            import time
            if self._stream_start is None:
                return
            elapsed = time.time() - self._stream_start
            self._spin_tick += 1
            bar = self.query_one("#cct-streaming-status", Static)
            # ── REAL activity: query the single source of truth ──
            try:
                from .. import activity as _act
                tid = getattr(self, "_stream_turn_id", None)
                if tid:
                    acts = _act.manager.get_for_turn(tid)
                    # prefer the most recent RUNNING/WAITING, otherwise last completed
                    running = [a for a in acts if a.status in (_act.RUNNING, _act.PENDING, _act.WAITING)]
                    target = running[-1] if running else (acts[-1] if acts else None)
                    if target:
                        # real spinner
                        spin = self._real_spinner[self._spin_tick % len(self._real_spinner)]
                        # color by status
                        try:
                            from . import theme_css as _tc
                            vars_ = _tc.css_variables()
                            col_map = {
                                _act.RUNNING: vars_.get("accent", "#38bdf8"),
                                _act.PENDING: vars_.get("text-faint", "#888"),
                                _act.WAITING: vars_.get("warning", "#eab308"),
                                _act.COMPLETED: vars_.get("success", "#22c55e"),
                                _act.FAILED: vars_.get("error", "#ef4444"),
                                _act.CANCELLED: vars_.get("text-faint", "#888"),
                            }
                            color = col_map.get(target.status, vars_.get("accent", "#38bdf8"))
                        except Exception:
                            color = "#38bdf8"
                        # title is real activity title, never fake
                        title = target.title or target.current_step or "Working"
                        # trim
                        if len(title) > 48:
                            title = title[:45] + "…"
                        # elapsed from real activity start, not composer's fake timer
                        real_elapsed = target.elapsed_time if hasattr(target, "elapsed_time") else elapsed
                        # fallback to composer's elapsed if activity hasn't started yet
                        if real_elapsed < 0.1:
                            real_elapsed = elapsed
                        from . import thinking as _th
                        timer_text = _th.format_timer(real_elapsed)
                        # model/provider - only if real
                        mp = ""
                        if target.provider or target.model:
                            prov = (target.provider or "").upper()
                            mdl = target.model or ""
                            mp = f"{prov} {mdl}".strip()
                        else:
                            mp = self._model_label
                        # progress bar if real progress exists (0..1)
                        prog_txt = ""
                        if target.progress is not None and 0 < target.progress < 1:
                            pct = int(target.progress * 100)
                            bar_len = 8
                            filled = int(target.progress * bar_len)
                            bar_chars = "█" * filled + "░" * (bar_len - filled)
                            prog_txt = f"  {bar_chars} {pct}%"
                        # current_step
                        step_txt = f" — {target.current_step[:32]}" if target.current_step else ""
                        # status suffix for WAITING
                        status_suf = ""
                        if target.status == _act.WAITING:
                            status_suf = " (waiting for permission)"
                        elif target.status == _act.FAILED and target.error:
                            status_suf = f" — {target.error[:40]}"
                        bar.update(
                            f"[{color}]{spin}[/] [{color}]{title}{step_txt}[/]{status_suf}  ·  "
                            f"[dim]{mp}[/dim]  ·  [{color}]{timer_text}[/]{prog_txt}"
                        )
                        return
            except Exception:
                pass
            # fallback: minimal real spinner without fake stage - only if no activity yet
            try:
                from . import thinking as _th
                timer_text = _th.format_timer(elapsed)
                spin = self._real_spinner[self._spin_tick % len(self._real_spinner)]
                bar.update(f"[{_th.stage_info('thinking')[1]}]{spin}[/] Working…  ·  [dim]{self._model_label}[/dim]  ·  {timer_text}")
            except Exception:
                bar.update(f"Working…  ·  {self._model_label}  ·  {elapsed:.1f}s")

        # ----------------------------------------------------- rewrite --
        def start_edit(self, turn_id, text):
            """Rewrite (minor-bug-fix spec): puts the composer into
            'editing an existing message' mode instead of loading text
            for a brand-new one. submit() checks self._editing_turn_id
            and, when set, posts MessageRewritten instead of
            MessageSubmitted — see that event's docstring for why this
            needs to be a distinct event rather than an optional field
            tacked onto MessageSubmitted (CCTApp's handling of the two
            is genuinely different: replace-in-place vs. append)."""
            self._editing_turn_id = turn_id
            editor = self.query_one("#cct-input", ComposerInput)
            editor.text = text
            try:
                editor.move_cursor(editor.document.end)
            except Exception:
                pass
            editor.focus()
            banner = self.query_one("#cct-edit-banner", Static)
            banner.update("\u270f\ufe0f Editing message \u2014 Enter to save, Esc to cancel")
            banner.add_class("active")

        def cancel_edit(self):
            if self._editing_turn_id is None:
                return
            self._editing_turn_id = None
            self.query_one("#cct-edit-banner", Static).remove_class("active")
            editor = self.query_one("#cct-input", ComposerInput)
            editor.text = ""

        # -------------------------------------------------------- attach --
        def add_attachment(self, path, kind="file", source="browse"):
            return self.query_one(AttachmentBar).add_file(path, kind=kind,
                                                          source=source)
        def collapse_paste(self, text, line_count, word_count=0):
            self.query_one(AttachmentBar).add_paste(text, line_count, word_count)

        def confirm_large_paste(self, text):
            """v0.7.8.45 clipboard-input fix: show the "Paste anyway /
            Cancel" warning for a paste larger than 5 KiB. On
            confirmation the FULL clipboard text is delivered into the
            composer input in one atomic insert (no key simulation, no
            truncation); on cancel nothing is pasted. Exactly one
            insert either way — no duplication."""
            try:
                from .. import terminal_host
                host = terminal_host.detect_host()
            except Exception:
                host = "unknown"
            self.log.debug(
                "large paste: host=%s, %d chars, warning shown",
                host, len(text))
            self._pending_large_paste = text
            try:
                self.app.push_screen(
                    _ConfirmPaste(len(text)), self._on_large_paste_answered)
            except Exception as e:
                self._pending_large_paste = None
                self.log.error(
                    "large paste: warning failed to open (%s) — aborting "
                    "the paste instead of inserting blindly", type(e).__name__)

        def _on_large_paste_answered(self, confirmed):
            text = getattr(self, "_pending_large_paste", None)
            if text is None:
                return
            self._pending_large_paste = None
            if not confirmed:
                self.log.debug("large paste: cancelled — nothing inserted")
                return
            editor = self.query_one("#cct-input", ComposerInput)
            try:
                try:
                    from .. import terminal_host
                    if terminal_host.is_windows():
                        # CRLF -> LF is the correct representation inside
                        # the Textual document (which always joins lines
                        # with \n); multiline code stays multiline and no
                        # blank/double lines appear. Non-Windows hosts
                        # are left exactly as delivered.
                        text = text.replace("\r\n", "\n")
                except Exception:
                    pass
                editor.insert(text)
                editor.focus()
                self.log.debug(
                    "large paste: approved=%d chars, inserted=%d",
                    len(text), len(text))
            except Exception as e:
                self.log.error(
                    "large paste: insert failed (%s) — %d chars NOT "
                    "delivered", type(e).__name__, len(text))

        def on_paste_expanded(self, event: PasteExpanded):
            editor = self.query_one("#cct-input", ComposerInput)
            try:
                editor.insert(event.text)
            except Exception:
                editor.text = editor.text + event.text

        # --------------------------------------------------------- submit --
        def on_button_pressed(self, event: Button.Pressed):
            bid = event.button.id
            if bid == "btn-send":
                if self.prompt_indicator.is_streaming:
                    try:
                        self.app.action_cancel_streaming()
                    except Exception:
                        pass
                else:
                    self.submit()
            elif bid == "btn-stop":
                # v0.7.8.1 interrupt: the ⏹ button next to the streaming
                # status line — same path as Esc / Ctrl+C.
                try:
                    self.app.action_cancel_streaming()
                except Exception:
                    pass
            elif bid == "btn-permissions":
                panel = self.query_one(PermissionsSettingsPanel)
                is_now_open = not panel.has_class("open")
                panel.set_class(is_now_open, "open")
                if is_now_open:
                    panel.refresh_rows()
                self._on_permission_panel_toggled(is_now_open)
            elif bid == "btn-attach":
                try:
                    self.app.action_prompt_attach()
                except Exception:
                    pass

        def on_click(self, event) -> None:
            target = getattr(event, "widget", None)
            if target is not None:
                from textual.widgets import Button
                if isinstance(target, Button) or any(isinstance(p, Button) for p in getattr(target, "ancestors", [])):
                    return
                try:
                    from .permission_panel import PermissionsSettingsPanel, Toggle3D
                    from .command_palette import CommandPalette
                    if isinstance(target, (PermissionsSettingsPanel, CommandPalette, Toggle3D)) or any(isinstance(p, (PermissionsSettingsPanel, CommandPalette, Toggle3D)) for p in getattr(target, "ancestors", [])):
                        return
                except Exception:
                    pass
            try:
                self.query_one("#cct-input", ComposerInput).focus()
            except Exception:
                pass

        def on_mouse_down(self, event) -> None:
            target = getattr(event, "widget", None)
            if target is not None:
                from textual.widgets import Button
                if isinstance(target, Button) or any(isinstance(p, Button) for p in getattr(target, "ancestors", [])):
                    return
                try:
                    from .permission_panel import PermissionsSettingsPanel, Toggle3D
                    from .command_palette import CommandPalette
                    if isinstance(target, (PermissionsSettingsPanel, CommandPalette, Toggle3D)) or any(isinstance(p, (PermissionsSettingsPanel, CommandPalette, Toggle3D)) for p in getattr(target, "ancestors", [])):
                        return
                except Exception:
                    pass
            try:
                self.query_one("#cct-input", ComposerInput).focus()
            except Exception:
                pass

        def on_key(self, event) -> None:
            if event.key == "escape":
                try:
                    panel = self.query_one(PermissionsSettingsPanel)
                    if panel.is_open:
                        event.stop()
                        try:
                            event.prevent_default()
                        except Exception:
                            pass
                        panel.close_panel()
                except Exception:
                    pass

        def submit(self):
            editor = self.query_one("#cct-input", ComposerInput)
            text = editor.text.strip()
            if not text:
                return
            # v0.7.8.1: real Attachment objects (not bare paths) travel
            # with the message — see AttachmentBar.pop_attachment_objects.
            attachments = self.query_one(AttachmentBar).pop_attachment_objects()
            editing_turn_id = self._editing_turn_id
            self._editing_turn_id = None
            self.query_one("#cct-edit-banner", Static).remove_class("active")
            self.query_one("#cct-latex-preview", Static).remove_class("active")
            self._sent_history.append(text)
            self._history_index = None
            editor.text = ""
            editor.styles.height = 2
            try:
                self.query_one("#cct-editor-stack", Container).styles.height = 2
            except Exception:
                pass
            self.palette.close()
            try:
                self.query_one(PermissionsSettingsPanel).close_panel()
            except Exception:
                pass
            if editing_turn_id is not None:
                self.post_message(MessageRewritten(editing_turn_id, text, attachments=attachments))
            else:
                self.post_message(MessageSubmitted(text, attachments=attachments))
            # Deployed into the conversation above — the composer itself
            # never becomes part of that history. Keep focus/cursor here
            # so the next prompt can be typed immediately.
            editor.focus()

        def history_active(self):
            return self._history_index is not None

        def recall_history(self, direction, editor):
            if not self._sent_history:
                return
            if self._history_index is None:
                self._history_index = len(self._sent_history)
            self._history_index = max(0, min(len(self._sent_history), self._history_index + direction))
            editor.text = (
                "" if self._history_index == len(self._sent_history)
                else self._sent_history[self._history_index]
            )

        def _on_palette_state_changed(self, is_open):
            if is_open:
                if self._explicit_height is None:
                    self.styles.height = "auto"
                    self.styles.max_height = "80%"
            else:
                if self._explicit_height is None:
                    self.styles.height = "auto"
                    self.styles.max_height = "75%"

        def _on_permission_panel_toggled(self, is_open):
            self.styles.height = "auto"
            if is_open:
                self.styles.max_height = "85%"
            else:
                self.styles.max_height = "80%" if self._explicit_height is not None else "75%"
            try:
                self.query_one("#btn-permissions", Button).set_class(bool(is_open), "-active")
            except Exception:
                pass

        def on_palette_selected(self, cmd):
            if not cmd:
                return
            self._just_selected_suggestion = True
            editor = self.query_one("#cct-input", ComposerInput)
            if cmd.startswith("/"):
                editor.text = cmd + " "
            else:
                editor.text = cmd
            try:
                editor.move_cursor(editor.document.end)
            except Exception:
                pass
            self.palette.close()
            editor.focus()

        def _update_palette(self, editor):
            if getattr(self, "_just_selected_suggestion", False):
                self._just_selected_suggestion = False
                self.palette.close()
                return
            text = editor.text
            if "\n" in text:
                self.palette.close()
                return
            first_line = text.strip()
            if first_line.startswith("/"):
                # If command is already followed by a space, user is entering arguments
                if " " in text:
                    self.palette.close()
                else:
                    self.palette.open_for_query(first_line)
            else:
                if not first_line.startswith("/"):
                    self._palette_saved_text = None
                self.palette.close()

        def refresh_palette_theme(self):
            """v0.7.9.5: repaint open palette rows against the NEW theme
            (row colors are baked Rich markup, so they'd otherwise keep
            the previous theme's hexes until the next keystroke)."""
            try:
                pal = self.palette
            except Exception:
                return
            try:
                if pal is not None and pal.is_open():
                    pal._redraw()
            except Exception:
                pass

        def on_text_area_changed(self, event):
            try:
                editor = self.query_one("#cct-input", ComposerInput)
                stack = self.query_one("#cct-editor-stack", Container)
                # Auto-resize editor and stack from 2 up to 8 lines based on line count
                line_count = max(2, min(8, editor.text.count("\n") + 1))
                if not getattr(self, "_explicit_height", None):
                    if editor.styles.height != line_count:
                        editor.styles.height = line_count
                        stack.styles.height = line_count
                else:
                    if editor.styles.height != "1fr":
                        editor.styles.height = "1fr"
                    if stack.styles.height != "1fr":
                        stack.styles.height = "1fr"

                self._update_palette(editor)
                self._update_latex_preview(editor.text)
                if self._history_index is not None:
                    expected = (
                        "" if self._history_index == len(self._sent_history)
                        else self._sent_history[self._history_index]
                    )
                    if editor.text != expected:
                        self._history_index = None
            except Exception:
                import traceback
                self.log.error("on_text_area_changed failed:\n" + traceback.format_exc())

        def _update_latex_preview(self, text):
            """Live preview (v0.7.2 roadmap's Full LaTeX Engine section)
            — whole-message scope, not per-equation: detecting exactly
            which span the cursor is currently inside would need real
            cursor-position math this editor doesn't track today, so
            this renders the WHOLE composer text through
            mathtext.render_math() and shows it in a strip under the
            editor whenever the text actually contains something
            LaTeX-shaped. Cheap enough to run on every keystroke —
            render_math() no-ops instantly on plain prose with no
            markup (see its own docstring)."""
            if not _LATEX_HINT_RE.search(text):
                self.query_one("#cct-latex-preview", Static).remove_class("active")
                return
            rendered = mathtext.render_math(text).replace("```", "").strip()
            preview = self.query_one("#cct-latex-preview", Static)
            if rendered and rendered != text.strip():
                preview.update(f"\U0001f441 {rendered}")
                preview.add_class("active")
            else:
                preview.remove_class("active")

else:
    PromptIndicator = None
    ComposerInput = None
    StickyComposer = None
