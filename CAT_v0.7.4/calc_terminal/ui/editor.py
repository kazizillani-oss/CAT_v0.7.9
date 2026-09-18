"""
CCT UI — editor.py (spec v0.7 Editor section): open multiple tabs,
syntax highlighting, line numbers, current-line highlight, auto
indentation, search/replace, save, undo/redo, file-tree sync.

Built on Textual's own `TextArea.code_editor()` (syntax highlighting,
line numbers, current-line highlight, and undo/redo are all native to
that widget — reimplementing them here would be exactly the kind of
"rewrite a working module" v0.7's brief says not to do). This file's
own job is the parts that widget doesn't provide: a tab strip for
multiple open files (with a per-tab ✕ close zone), save-to-disk, an
inline find/replace bar, a status toolbar (file · language · UTF-8 ·
Ln/Col · Spaces · Modified · ✕), and the package's Tokyo Night
syntax theme.

v0.7.10 additions:
- Live Diff Viewer: shows before/after changes when files are modified
- Change tracking: stores original content for diff comparison
- Inline diff view: shows additions/deletions inline in the editor
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import os
import time

from .events import ChatRequested, EditorTabsChanged, FileSaved

TEXTUAL_AVAILABLE = True
try:
    from rich.markdown import Markdown
    from rich.style import Style
    from textual.binding import Binding
    from textual.containers import Vertical, Horizontal, VerticalScroll
    from textual.widgets import (
        Tab, TabbedContent, TabPane, Tabs, TextArea, Static, Input, Button,
    )
    from textual.widgets.text_area import TextAreaTheme
except Exception:
    TEXTUAL_AVAILABLE = False

# Whether real syntax highlighting can actually happen. `tree_sitter`
# (plus the per-language `tree_sitter_<lang>` grammar packages the
# `textual[syntax]` extra installs) is what TextArea's highlighter
# needs; Textual itself swallows a missing import here and just
# renders plain, unhighlighted text with no warning to the user (see
# requirements.txt's note on the `textual[syntax]` extra for the full
# story). Checked once at import time so open_file() can tell the user
# plainly instead of leaving them staring at an editor that silently
# looks like Notepad.
try:
    import tree_sitter  # noqa: F401
    HIGHLIGHTING_AVAILABLE = True
except Exception:
    HIGHLIGHTING_AVAILABLE = False

# Extension -> TextArea/tree-sitter language id. Anything unlisted opens
# as plain text (no highlighting) rather than guessing wrong.
_LANGUAGE_OF = {
    ".py": "python", ".json": "json", ".md": "markdown", ".markdown": "markdown",
    ".html": "html", ".htm": "html", ".css": "css", ".js": "javascript",
    ".jsx": "javascript", ".tsx": "javascript", ".ts": "javascript",
    ".vue": "html", ".svelte": "html",
    ".yaml": "yaml", ".yml": "yaml", ".toml": "toml", ".sql": "sql",
    ".sh": "bash", ".bash": "bash", ".rs": "rust", ".go": "go",
    ".java": "java", ".xml": "xml", ".regex": "regex",
}

# Web-previewable extensions — show ▷ and ⿻ (spec 2)
_WEB_PREVIEW_EXTS = {".html", ".htm", ".css", ".js", ".jsx", ".tsx", ".ts", ".vue", ".svelte"}
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico"}
_MARKDOWN_EXTS = {".md", ".markdown"}
_PDF_EXTS = {".pdf"}
_DATA_EXTS = {".csv"}

def is_web_previewable(path: str) -> bool:
    return os.path.splitext(str(path).lower())[1] in _WEB_PREVIEW_EXTS

def is_image_file(path: str) -> bool:
    return os.path.splitext(str(path).lower())[1] in _IMAGE_EXTS

def is_markdown_file(path: str) -> bool:
    return os.path.splitext(str(path).lower())[1] in _MARKDOWN_EXTS

def is_csv_file(path: str) -> bool:
    return os.path.splitext(str(path).lower())[1] in _DATA_EXTS

def get_file_icon(path: str) -> str:
    ext = os.path.splitext(str(path).lower())[1]
    if ext in _IMAGE_EXTS:
        return "🖼"
    if ext in {".html", ".htm"}:
        return "🌐"
    if ext in {".css"}:
        return "🎨"
    if ext in {".js", ".jsx", ".ts", ".tsx"}:
        return "📜"
    if ext in {".vue", ".svelte"}:
        return "⚡"
    if ext in _MARKDOWN_EXTS:
        return "📝"
    if ext in {".json"}:
        return "{}"
    if ext in {".pdf"}:
        return "📄"
    if ext in {".csv"}:
        return "📊"
    if ext in {".py"}:
        return "🐍"
    if ext in {".java"}:
        return "☕"
    if ext in {".rs"}:
        return "🦀"
    if ext in {".go"}:
        return "🐹"
    return "📄"

# The grammars Textual 8.2.8 actually ships: tree-sitter has no
# c/cpp/typescript here, so those files open as plain text instead of
# letting TextArea's highlight machinery raise LanguageDoesNotExist.
_BUILTIN_LANGUAGES = {
    "python", "markdown", "json", "toml", "yaml", "html", "css",
    "javascript", "rust", "go", "regex", "sql", "java", "bash", "xml",
}

_TEXTY_FALLBACK_EXTS = {
    ".txt", ".xyz", ".pdb", ".mol", ".cif", ".csv", ".log", ".cfg", ".ini",
}


def language_for(path):
    lang = _LANGUAGE_OF.get(os.path.splitext(path)[1].lower())
    return lang if lang in _BUILTIN_LANGUAGES else None


def is_probably_text(path):
    """Best-effort binary/text guess for drag & drop / open-in-editor:
    known text extensions, or a null-byte sniff of the first 2KB for
    anything unrecognized. Never guesses yes for the spec's known
    binary formats (pdf/docx/pptx/xlsx/png/jpg/gif/svg/zip/7z)."""
    ext = os.path.splitext(path)[1].lower()
    if ext in _LANGUAGE_OF or ext in _TEXTY_FALLBACK_EXTS:
        return True
    binary_exts = {".pdf", ".docx", ".pptx", ".xlsx", ".png", ".jpg", ".jpeg",
                    ".gif", ".svg", ".zip", ".7z"}
    if ext in binary_exts:
        return False
    try:
        with open(path, "rb") as f:
            chunk = f.read(2048)
        return b"\x00" not in chunk
    except Exception:
        return False


if TEXTUAL_AVAILABLE:

    # ------------------------------------------------- Tokyo Night theme --
    # The package's Python palette (calc_terminal/theme.py) plus the
    # Tokyo Night tones it doesn't cover (blue/light-blue/yellow/magenta
    # and the bg/gutter family). Applied per TextArea instance, since
    # Textual 8.2.8's register_theme() is per-instance.
    #
    # v0.7.9.0 LIGHT-MODE AUDIT: these styles used to be applied
    # unconditionally — a full dark-mode block (near-black background,
    # pale selection, dark cursor line) leaked into light mode every
    # time a file was opened. There is now a matching GitHub-Light set,
    # and _apply_editor_theme() picks by the CURRENT app theme.
    _TOKYO_BG = Style(color="#E8EBFA", bgcolor="#16161E")
    _TOKYO_GUTTER = Style(color="#3B4261", bgcolor="#16161E")
    _TOKYO_GUTTER_ACTIVE = Style(color="#7DCFFF", bgcolor="#16161E")
    _TOKYO_CURSOR = Style(color="#16161E", bgcolor="#7DCFFF")
    _TOKYO_CURSOR_LINE = Style(bgcolor="#1E2030")
    _TOKYO_BRACKET = Style(color="#7DCFFF", bgcolor="#2F3349")
    _TOKYO_SELECTION = Style(color="#C0CAF5", bgcolor="#3B4261")
    _TOKYO_PURPLE = Style(color="#C3A0FF")
    _TOKYO_CYAN = Style(color="#7DCFFF")
    _TOKYO_GREEN = Style(color="#8BE08B")
    _TOKYO_ORANGE = Style(color="#F0B45F")
    _TOKYO_RED = Style(color="#FF7F9A")
    _TOKYO_BLUE = Style(color="#82AAFF")
    _TOKYO_LIGHT_BLUE = Style(color="#89DDFF")
    _TOKYO_YELLOW = Style(color="#E0AF68")
    _TOKYO_MAGENTA = Style(color="#BB9AF7")
    _TOKYO_COMMENT = Style(color="#565F89")
    _TOKYO_WHITE = Style(color="#C0CAF5")

    # GitHub Light editor surface — same structure as the Tokyo set:
    # readable base/gutter on white, a clearly visible cursor, and a
    # SUBTLE selection wash that keeps strong contrast without glowing
    # blocks. No foreground on the selection style: selected code keeps
    # its syntax colors over the soft blue wash.
    _GITHUB_BG = Style(color="#24292F", bgcolor="#FFFFFF")
    _GITHUB_GUTTER = Style(color="#8C959F", bgcolor="#F6F8FA")
    _GITHUB_GUTTER_ACTIVE = Style(color="#0550AE", bgcolor="#F6F8FA")
    _GITHUB_CURSOR = Style(color="#FFFFFF", bgcolor="#0969DA")
    _GITHUB_CURSOR_LINE = Style(bgcolor="#F6F8FA")
    _GITHUB_BRACKET = Style(color="#24292F", bgcolor="#DCE7F5")
    _GITHUB_SELECTION = Style(bgcolor="#B6D7FF")
    _GITHUB_PURPLE = Style(color="#8250DF")
    _GITHUB_CYAN = Style(color="#0550AE")
    _GITHUB_GREEN = Style(color="#0A3069")
    _GITHUB_ORANGE = Style(color="#0550AE")
    _GITHUB_RED = Style(color="#CF222E")
    _GITHUB_BLUE = Style(color="#8250DF")
    _GITHUB_LIGHT_BLUE = Style(color="#953800")
    _GITHUB_YELLOW = Style(color="#953800")
    _GITHUB_MAGENTA = Style(color="#B35900")
    _GITHUB_COMMENT = Style(color="#57606A")
    _GITHUB_WHITE = Style(color="#24292F")

    def _editor_palette():
        """(name, bg, gutter, gutter_active, cursor, cursor_line,
        bracket, selection, syntax_role_map_colors) for the CURRENT app
        theme. Both palettes share one capture->role mapping; only the
        Style objects differ."""
        try:
            from .. import theme as _theme
            light = _theme.is_light()
        except Exception:
            light = False
        if light:
            return ("cct-github-light",
                    _GITHUB_BG, _GITHUB_GUTTER, _GITHUB_GUTTER_ACTIVE,
                    _GITHUB_CURSOR, _GITHUB_CURSOR_LINE, _GITHUB_BRACKET,
                    _GITHUB_SELECTION,
                    {"purple": _GITHUB_PURPLE, "cyan": _GITHUB_CYAN,
                     "green": _GITHUB_GREEN, "orange": _GITHUB_ORANGE,
                     "red": _GITHUB_RED, "blue": _GITHUB_BLUE,
                     "light_blue": _GITHUB_LIGHT_BLUE,
                     "yellow": _GITHUB_YELLOW, "magenta": _GITHUB_MAGENTA,
                     "comment": _GITHUB_COMMENT, "white": _GITHUB_WHITE})
        return ("cct-tokyonight",
                _TOKYO_BG, _TOKYO_GUTTER, _TOKYO_GUTTER_ACTIVE,
                _TOKYO_CURSOR, _TOKYO_CURSOR_LINE, _TOKYO_BRACKET,
                _TOKYO_SELECTION,
                {"purple": _TOKYO_PURPLE, "cyan": _TOKYO_CYAN,
                 "green": _TOKYO_GREEN, "orange": _TOKYO_ORANGE,
                 "red": _TOKYO_RED, "blue": _TOKYO_BLUE,
                 "light_blue": _TOKYO_LIGHT_BLUE, "yellow": _TOKYO_YELLOW,
                 "magenta": _TOKYO_MAGENTA, "comment": _TOKYO_COMMENT,
                 "white": _TOKYO_WHITE})

    # capture-name -> Style. Every capture the bundled *.scm highlight
    # queries emit is mapped here explicitly (TextAreaTheme.get_highlight
    # is a plain dict lookup, so an unmapped capture gets no style at all).
    def _syntax_styles(colors):
        return {
            # keywords
            "keyword": colors["purple"], "conditional": colors["purple"],
            "repeat": colors["purple"], "exception": colors["purple"],
            "keyword.return": colors["purple"], "keyword.function": colors["purple"],
            "keyword.operator": colors["purple"], "storageclass": colors["purple"],
            "import": colors["purple"], "include": colors["purple"],
            "preproc": colors["purple"], "keyframes": colors["purple"],
            "media": colors["purple"], "supports": colors["purple"],
            # functions / methods
            "function": colors["blue"], "method": colors["blue"],
            "function.call": colors["blue"], "method.call": colors["blue"],
            "function.macro": colors["blue"],
            # classes / types
            "type": colors["cyan"], "type.class": colors["cyan"],
            "type.definition": colors["cyan"], "type.qualifier": colors["cyan"],
            "constructor": colors["cyan"], "heading": colors["cyan"],
            "heading.marker": colors["cyan"], "markup.heading": colors["cyan"],
            # builtins
            "type.builtin": colors["light_blue"], "function.builtin": colors["light_blue"],
            "variable.builtin": colors["light_blue"],
            # strings
            "string": colors["green"], "string.special": colors["green"],
            "string.special.symbol": colors["green"], "string.escape": colors["green"],
            "escape": colors["green"], "charset": colors["green"],
            "text.literal": colors["green"], "text.uri": colors["green"],
            "link.uri": colors["green"], "link.label": colors["green"],
            "label": colors["green"], "markup.raw": colors["green"],
            # numbers
            "number": colors["orange"], "float": colors["orange"],
            "constant.character": colors["orange"], "list.marker": colors["orange"],
            # constants
            "constant": colors["magenta"], "constant.builtin": colors["magenta"],
            "boolean": colors["magenta"], "json.null": colors["magenta"],
            "toml.datetime": colors["magenta"],
            # comments
            "comment": colors["comment"], "spell": colors["comment"],
            # attributes / decorators / tags
            "attribute": colors["yellow"], "attribute.builtin": colors["yellow"],
            "property": colors["yellow"], "field": colors["yellow"],
            "json.label": colors["yellow"], "yaml.field": colors["yellow"],
            "toml.type": colors["yellow"], "tag.attribute": colors["yellow"],
            "namespace": colors["yellow"], "tag": colors["red"],
            # operators / punctuation stay near-base
            "operator": colors["white"], "punctuation.bracket": colors["white"],
            "punctuation.delimiter": colors["white"], "punctuation.special": colors["white"],
            "tag.delimiter": colors["white"], "variable": colors["white"],
            "variable.parameter": colors["white"], "parameter": colors["white"],
            "embedded": colors["white"], "conceal": colors["white"],
            "markup": colors["white"], "markup.link": colors["blue"],
            "text": colors["white"], "error": colors["red"],
            "json.error": colors["red"], "toml.error": colors["red"],
            "html.end_tag_error": colors["red"],
        }

    def _apply_editor_theme(area):
        """Register + activate the editor theme matching the CURRENT app
        theme (Tokyo Night in dark, GitHub Light in light) on one TextArea
        instance (register_theme is per-instance in 8.2.8, so this runs at
        open_file() time for every new editor — and again from
        EditorPane.retheme() after a /theme switch)."""
        try:
            name, bg, gutter, gutter_active, cursor, cursor_line, \
                bracket, selection, colors = _editor_palette()
            ed_theme = TextAreaTheme(
                name=name,
                base_style=bg,
                gutter_style=gutter,
                cursor_style=cursor,
                cursor_line_style=cursor_line,
                cursor_line_gutter_style=gutter_active,
                bracket_matching_style=bracket,
                selection_style=selection,
                syntax_styles=_syntax_styles(colors),
            )
            area.register_theme(ed_theme)
            area.theme = name
        except Exception:
            pass

    # Back-compat alias (older call sites / external tooling).
    _apply_tokyo_theme = _apply_editor_theme

    class _EditorArea(TextArea, inherit_bindings=False):
        """A TextArea whose Ctrl+W is deliberately unbound. Textual's
        default Ctrl+W deletes the word left of the cursor, but v0.7.4
        needs Ctrl+W to close the editor tab — and 8.2.8's Widget has
        no remove_binding() to strip it per instance, and its binding
        merge keeps ancestor keys the subclass simply omits, so the
        subclass drops it via inherit_bindings=False and the key
        bubbles up to the EditorPane's close-tab binding instead.
        TextArea itself is the only widget in the MRO with BINDINGS,
        so nothing else is lost."""

        BINDINGS = [
            binding for binding in TextArea.BINDINGS
            if "ctrl+w" not in binding.key.split(",")
        ] + [
            # Shift+Enter must work INSIDE the editor (TextArea consumes Enter)
            # so we bind it here and forward to the EditorPane.
            Binding("shift+enter", "show_preview", "Show Preview", show=False),
            Binding("ctrl+enter", "show_preview", "Show Preview", show=False),
            Binding("ctrl+shift+enter", "show_preview", "Show Preview", show=False),
            Binding("cmd+shift+enter", "show_preview", "Show Preview", show=False),
            Binding("super+shift+enter", "show_preview", "Show Preview", show=False),
            Binding("shift+linefeed", "show_preview", "Show Preview", show=False),
            Binding("f11", "toggle_fullscreen", "Fullscreen", show=False),
        ]

        def action_show_preview(self):
            # Called when this TextArea receives shift+enter / ctrl+enter
            try:
                node = self._parent
                while node is not None and not isinstance(node, EditorPane):
                    node = getattr(node, "_parent", None)
                if isinstance(node, EditorPane):
                    node.action_show_preview()
            except Exception:
                pass

        def action_toggle_fullscreen(self):
            try:
                node = self._parent
                while node is not None and not isinstance(node, EditorPane):
                    node = getattr(node, "_parent", None)
                if isinstance(node, EditorPane):
                    try:
                        self.app.action_toggle_right_pane_fullscreen()
                    except Exception:
                        try:
                            node.app.action_toggle_right_pane_fullscreen()
                        except Exception:
                            pass
            except Exception:
                pass

        def _on_key(self, event):
            """Intercept keys before TextArea's default handling via centralized ShortcutManager."""
            raw_key = (getattr(event, "key", "") or "").lower().strip()

            # Spec: Shift+Enter / Cmd+Shift+Enter / Ctrl+Shift+Enter / ▷ => Show Web Preview
            # MUST NEVER insert newline into the code editor!
            preview_keys = {
                "shift+enter", "ctrl+shift+enter", "cmd+shift+enter", "super+shift+enter",
                "shift+linefeed", "ctrl+linefeed", "ctrl+shift+linefeed", "shift+return",
                "ctrl+shift+return", "super+shift+return", "cmd+shift+return", "ctrl+enter"
            }
            if raw_key in preview_keys or (
                "shift" in raw_key and any(k in raw_key for k in ("enter", "return", "linefeed"))
            ):
                event.stop()
                try:
                    event.prevent_default()
                except Exception:
                    pass
                self.action_show_preview()
                return

            # 1. Centralized CAT Shortcut Manager resolution
            try:
                from ..editor.shortcuts import get_shortcut_manager
                from ..editor import actions as ed_actions

                cmd_id = get_shortcut_manager().resolve(raw_key, context="editor")
                if cmd_id:
                    # Direct line and editing manipulations
                    if cmd_id == "editor.toggleComment":
                        event.stop()
                        try: event.prevent_default()
                        except Exception: pass
                        ed_actions.toggle_line_comment(self)
                        return
                    elif cmd_id == "editor.deleteLine":
                        event.stop()
                        try: event.prevent_default()
                        except Exception: pass
                        ed_actions.delete_line(self)
                        return
                    elif cmd_id == "editor.moveLineUp":
                        event.stop()
                        try: event.prevent_default()
                        except Exception: pass
                        ed_actions.move_line_up(self)
                        return
                    elif cmd_id == "editor.moveLineDown":
                        event.stop()
                        try: event.prevent_default()
                        except Exception: pass
                        ed_actions.move_line_down(self)
                        return
                    elif cmd_id == "editor.copyLineUp":
                        event.stop()
                        try: event.prevent_default()
                        except Exception: pass
                        ed_actions.copy_line_up(self)
                        return
                    elif cmd_id == "editor.copyLineDown":
                        event.stop()
                        try: event.prevent_default()
                        except Exception: pass
                        ed_actions.copy_line_down(self)
                        return
                    elif cmd_id == "editor.insertLineBelow":
                        event.stop()
                        try: event.prevent_default()
                        except Exception: pass
                        ed_actions.insert_line_below(self)
                        return
                    elif cmd_id == "editor.insertLineAbove":
                        event.stop()
                        try: event.prevent_default()
                        except Exception: pass
                        ed_actions.insert_line_above(self)
                        return
                    elif cmd_id == "editor.selectNextOccurrence":
                        event.stop()
                        try: event.prevent_default()
                        except Exception: pass
                        ed_actions.select_next_occurrence(self)
                        return

                    # Find parent EditorPane
                    node = self._parent
                    while node is not None and not isinstance(node, EditorPane):
                        node = getattr(node, "_parent", None)

                    if cmd_id == "preview.open":
                        event.stop()
                        try: event.prevent_default()
                        except Exception: pass
                        if isinstance(node, EditorPane):
                            node.action_show_preview()
                        return
                    elif cmd_id == "editor.save":
                        event.stop()
                        try: event.prevent_default()
                        except Exception: pass
                        if isinstance(node, EditorPane):
                            node.save_active()
                        return
                    elif cmd_id == "editor.find":
                        event.stop()
                        try: event.prevent_default()
                        except Exception: pass
                        if isinstance(node, EditorPane):
                            node.toggle_find()
                        return
                    elif cmd_id == "editor.closeTab":
                        event.stop()
                        try: event.prevent_default()
                        except Exception: pass
                        if isinstance(node, EditorPane):
                            node.close_active()
                        return
                    elif cmd_id == "editor.commandPalette":
                        event.stop()
                        try: event.prevent_default()
                        except Exception: pass
                        app = getattr(self, "app", getattr(node, "app", None))
                        if app is not None:
                            try:
                                from .command_palette_modal import CommandPaletteModal
                                app.push_screen(CommandPaletteModal())
                            except Exception:
                                pass
                        return
                    elif cmd_id == "workbench.action.closeOverlays":
                        event.stop()
                        try: event.prevent_default()
                        except Exception: pass
                        if isinstance(node, EditorPane):
                            node.action_editor_escape()
                        return
            except Exception:
                pass

            # Fallback check: Shift+Enter / Cmd+Shift+Enter / Ctrl+Enter => Show Web Preview
            if raw_key in preview_keys or (
                "shift" in raw_key and any(k in raw_key for k in ("enter", "return", "linefeed"))
            ):
                event.stop()
                try:
                    event.prevent_default()
                except Exception:
                    pass
                self.action_show_preview()
                return
            if event.key == "escape":
                event.stop()
                try:
                    event.prevent_default()
                except Exception:
                    pass
                node = self._parent
                while node is not None and not isinstance(node, EditorPane):
                    node = getattr(node, "_parent", None)
                if isinstance(node, EditorPane):
                    node.action_editor_escape()
                return
            # Also check for custom shortcuts registered via Gestures
            try:
                from ..gestures.manager import handle_shortcut
                if handle_shortcut(event.key, app=getattr(self, "app", None)):
                    event.stop()
                    try:
                        event.prevent_default()
                    except Exception:
                        pass
                    return
            except Exception:
                pass

    class _FindBar(Horizontal):
        """Inline find/replace row, toggled open by the parent
        EditorPane — never a popup, matching the rest of this package."""

        def __init__(self, id="cct-editor-findbar"):
            super().__init__(id=id, classes="cct-editor-findbar")

        def compose(self):
            yield Input(placeholder="Find", id="cct-find-input")
            yield Input(placeholder="Replace with", id="cct-replace-input")
            yield Button("Next", id="cct-find-next", classes="cct-ctrl")
            yield Button("Replace All", id="cct-replace-all", classes="cct-ctrl")
            yield Button("\u2715", id="cct-find-close", classes="cct-ctrl")

        def on_mount(self):
            # Focusing here (not right after mount() returns in the
            # caller) is what actually works: mount() only *schedules*
            # attachment to the DOM, it doesn't complete it — querying
            # or focusing a child synchronously right after calling
            # mount() races Textual's message pump and raises NoMatches
            # on a slow enough frame. This widget's own on_mount fires
            # only once it's genuinely attached, so focusing itself here
            # is always safe.
            self.query_one("#cct-find-input", Input).focus()

    class _PreviewPane(Static):
        """Live Markdown preview pane (v0.7.8 editor upgrade): renders
        the active editor tab's text through Rich's Markdown renderer
        every time the source changes. Hidden by default — only the
        toolbar's Preview toggle shows it. Falls back to the raw text
        if Rich's Markdown ever errors on pathological input."""

        def __init__(self, id="cct-editor-preview"):
            super().__init__("", id=id, classes="cct-editor-preview")
            self._source = ""
            self._note = ""

        def set_source(self, text, note=""):
            self._source = text or ""
            self._note = note or ""
            self.refresh()

        def render(self):
            if self._note and not self._source:
                return f"[italic]{self._note}[/italic]"
            if not self._source.strip():
                return "[italic]Nothing to preview[/italic]"
            try:
                return Markdown(self._source)
            except Exception:
                return self._source

    class _ImageViewer(Vertical):
        """Image viewer tab for png/jpg/webp/svg etc. Shows zoom, fit, reset,
        dimensions, file size, and checkerboard for transparency. Renders a
        small colored preview via PIL when available."""

        def __init__(self, path, **kwargs):
            super().__init__(**kwargs)
            self.path = os.path.abspath(path)
            self._zoom = 1.0
            self._fit = False  # Show at own resolution by default (not pixelated fit)

        def compose(self):
            with Horizontal(id="cct-image-toolbar", classes="cct-image-toolbar"):
                yield Static("", id="cct-image-info", classes="cct-tb-pill")
                yield Button("−", id="cct-image-zoomout", classes="cct-ctrl", tooltip="Zoom Out")
                yield Button("+", id="cct-image-zoomin", classes="cct-ctrl", tooltip="Zoom In")
                yield Button("Fit", id="cct-image-fit", classes="cct-ctrl", tooltip="Fit to screen")
                yield Button("100%", id="cct-image-reset", classes="cct-ctrl", tooltip="Reset zoom")
                yield Button("✕", id="cct-image-close", classes="cct-ctrl")
            with VerticalScroll(id="cct-image-scroll"):
                yield Static("", id="cct-image-display", classes="cct-image-display")

        def on_mount(self):
            self._refresh_info()
            self._refresh_display()

        def _get_info(self):
            try:
                size = os.path.getsize(self.path)
                if size < 1024:
                    size_str = f"{size} B"
                elif size < 1024*1024:
                    size_str = f"{size/1024:.1f} KB"
                else:
                    size_str = f"{size/(1024*1024):.1f} MB"
            except Exception:
                size_str = "? B"
            w = h = 0
            has_alpha = False
            fmt = ""
            try:
                from PIL import Image
                with Image.open(self.path) as im:
                    w, h = im.size
                    fmt = im.format or ""
                    has_alpha = im.mode in ("RGBA", "LA") or "transparency" in im.info
            except Exception:
                if self.path.lower().endswith(".svg"):
                    try:
                        txt = open(self.path, "r", encoding="utf-8", errors="ignore").read(4096)
                        import re
                        m = re.search(r'width="(\d+)"', txt)
                        n = re.search(r'height="(\d+)"', txt)
                        if m and n:
                            w, h = int(m.group(1)), int(n.group(1))
                            fmt = "SVG"
                    except Exception:
                        pass
            return w, h, size_str, has_alpha, fmt

        def _refresh_info(self):
            try:
                w, h, size_str, has_alpha, fmt = self._get_info()
                info = f"{w}×{h} {size_str}" if w and h else size_str
                if fmt:
                    info = f"{fmt} · " + info
                if has_alpha:
                    info += " · transparent"
                info += f" · zoom {int(self._zoom*100)}%"
                self.query_one("#cct-image-info", Static).update(info)
            except Exception:
                pass

        def _render_ascii_preview(self):
            """Render preview at own resolution (not pixelated thumbnail) when zoom=100% and not fit.
            Uses high-quality LANCZOS and preserves aspect, with scroll for large images."""
            try:
                from PIL import Image
                from rich.text import Text
                from rich.style import Style
                with Image.open(self.path) as im:
                    if im.mode in ("RGBA", "LA"):
                        bg = Image.new("RGBA", im.size, (40, 40, 40, 255))
                        im = Image.alpha_composite(bg, im.convert("RGBA")).convert("RGB")
                    elif im.mode == "P":
                        im = im.convert("RGB")
                    elif im.mode != "RGB":
                        im = im.convert("RGB")
                    iw, ih = im.size
                    if iw == 0 or ih == 0:
                        return None
                    resample = getattr(Image, "LANCZOS", 1)
                    if self._fit:
                        # Fit to screen: thumbnail to reasonable max for overview
                        max_w, max_h = 88, 36
                        im.thumbnail((max_w, max_h), resample)
                    else:
                        # Own resolution: show at native size * zoom, with very large cap (800x600) so 1:1 is possible
                        # Allows scrolling for large images instead of aggressive downscale
                        target_w = int(iw * self._zoom)
                        target_h = int(ih * self._zoom)
                        # Only cap extremely huge images (e.g., 4000px) to avoid OOM
                        max_cap_w, max_cap_h = 800, 600
                        if target_w > max_cap_w or target_h > max_cap_h:
                            ratio = min(max_cap_w / max(1, target_w), max_cap_h / max(1, target_h))
                            target_w = int(target_w * ratio)
                            target_h = int(target_h * ratio)
                        if target_w != iw or target_h != ih:
                            im = im.resize((max(1, target_w), max(1, target_h)), resample)
                    tw, th = im.size
                    if tw == 0 or th == 0:
                        return None
                    # Use half-block "▄" to double vertical resolution (less pixelated)
                    # Each terminal cell shows 2 vertical pixels: top as fg, bottom as bg
                    txt = Text()
                    for y in range(0, th, 2):
                        for x in range(tw):
                            r1, g1, b1 = im.getpixel((x, y))
                            # Bottom pixel (or same if at bottom edge)
                            if y + 1 < th:
                                r2, g2, b2 = im.getpixel((x, y+1))
                            else:
                                r2, g2, b2 = r1, g1, b1
                            # Use "▄" where upper half is bg and lower is fg? Actually "▄" is lower half block
                            # So fg = bottom pixel, bg = top pixel
                            style = Style(color=f"#{r2:02x}{g2:02x}{b2:02x}", bgcolor=f"#{r1:02x}{g1:02x}{b1:02x}")
                            txt.append("▄", style=style)
                        if y + 2 < th:
                            txt.append("\n")
                    return txt
            except Exception:
                return None
            return None

        def _refresh_display(self):
            try:
                w, h, _, has_alpha, _ = self._get_info()
                disp = self.query_one("#cct-image-display", Static)
                # Try rich colored preview
                preview = self._render_ascii_preview()
                if preview is not None:
                    # Show filename header + colored preview + footer
                    from rich.console import Group
                    from rich.text import Text
                    icon = get_file_icon(self.path)
                    base = os.path.basename(self.path)
                    header = Text(f"{icon} {base}", style="bold")
                    if w and h:
                        sub = Text(f"{w} × {h}  {'Fit' if self._fit else f'{int(self._zoom*100)}%'}", style="dim")
                    else:
                        sub = Text(f"{'Fit' if self._fit else f'{int(self._zoom*100)}%'}", style="dim")
                    footer = Text(f"Path: {self.path}", style="dim")
                    # Add checker note if transparent
                    parts = [header, sub, Text(""), preview, Text(""), footer]
                    if has_alpha:
                        parts.append(Text("Checkerboard shows transparency", style="dim"))
                    disp.update(Group(*parts))
                    return
                # Fallback textual placeholder
                icon = get_file_icon(self.path)
                base = os.path.basename(self.path)
                zoom_label = "Fit" if self._fit else f"{int(self._zoom*100)}%"
                bg = "░" if has_alpha else "█"
                lines = []
                lines.append(f"[b]{icon} {base}[/]")
                if w and h:
                    lines.append(f"[dim]{w} × {h}  {zoom_label}[/]")
                else:
                    lines.append(f"[dim]{zoom_label}[/]")
                lines.append("")
                box_w = max(20, min(40, int(20*self._zoom))) if not self._fit else 32
                box_h = max(6, min(16, int(8*self._zoom))) if not self._fit else 10
                for _ in range(box_h):
                    lines.append(f"[dim]{bg * box_w}[/]")
                lines.append("")
                lines.append(f"[dim]Path: {self.path}[/]")
                if has_alpha:
                    lines.append("[dim]Checkerboard shows transparency — install Pillow for true preview[/]")
                disp.update("\n".join(lines))
            except Exception as e:
                try:
                    self.query_one("#cct-image-display", Static).update(f"Could not render image: {e}")
                except Exception:
                    pass

        def on_button_pressed(self, event):
            bid = event.button.id
            if bid == "cct-image-close":
                try:
                    # Find parent EditorPane and close
                    node = self._parent
                    while node is not None and not isinstance(node, EditorPane):
                        node = getattr(node, "_parent", None)
                    if isinstance(node, EditorPane):
                        # Find tab id for this path
                        for p, tid in list(node._open_paths.items()):
                            if os.path.normcase(p) == os.path.normcase(self.path):
                                node.close_active(tid)
                                break
                except Exception:
                    pass
            elif bid == "cct-image-zoomin":
                self._fit = False
                self._zoom = min(3.0, self._zoom * 1.25)
                self._refresh_info()
                self._refresh_display()
            elif bid == "cct-image-zoomout":
                self._fit = False
                self._zoom = max(0.25, self._zoom / 1.25)
                self._refresh_info()
                self._refresh_display()
            elif bid == "cct-image-fit":
                self._fit = True
                self._zoom = 1.0
                self._refresh_info()
                self._refresh_display()
            elif bid == "cct-image-reset":
                self._fit = False
                self._zoom = 1.0
                self._refresh_info()
                self._refresh_display()

    class _CsvViewer(Vertical):
        """CSV table viewer using Textual DataTable when available, else plain text."""

        def __init__(self, path, **kwargs):
            super().__init__(**kwargs)
            self.path = os.path.abspath(path)

        def compose(self):
            with Horizontal(id="cct-csv-toolbar", classes="cct-csv-toolbar"):
                yield Static(os.path.basename(self.path), id="cct-csv-info", classes="cct-tb-pill")
                yield Button("✕", id="cct-csv-close", classes="cct-ctrl")
            try:
                from textual.widgets import DataTable
                yield DataTable(id="cct-csv-table")
            except Exception:
                yield Static("", id="cct-csv-fallback")

        def on_mount(self):
            self._load_csv()

        def _load_csv(self):
            try:
                import csv
                with open(self.path, "r", encoding="utf-8", errors="replace", newline="") as f:
                    reader = csv.reader(f)
                    rows = list(reader)[:200]  # limit
                if not rows:
                    return
                try:
                    from textual.widgets import DataTable
                    table = self.query_one("#cct-csv-table", DataTable)
                    table.clear(columns=True)
                    header = rows[0]
                    for col in header:
                        table.add_column(col, width=None)
                    for r in rows[1:]:
                        # Pad/truncate to header length
                        if len(r) < len(header):
                            r = r + [""]*(len(header)-len(r))
                        elif len(r) > len(header):
                            r = r[:len(header)]
                        table.add_row(*r)
                except Exception:
                    txt = "\n".join([", ".join(r) for r in rows[:50]])
                    self.query_one("#cct-csv-fallback", Static).update(txt)
            except Exception as e:
                try:
                    self.query_one("#cct-csv-fallback", Static).update(f"Could not load CSV: {e}")
                except Exception:
                    pass

        def on_button_pressed(self, event):
            if event.button.id == "cct-csv-close":
                try:
                    node = self._parent
                    while node is not None and not isinstance(node, EditorPane):
                        node = getattr(node, "_parent", None)
                    if isinstance(node, EditorPane):
                        for p, tid in list(node._open_paths.items()):
                            if os.path.normcase(p) == os.path.normcase(self.path):
                                node.close_active(tid)
                                break
                except Exception:
                    pass

    class _PdfViewer(Vertical):
        """Real scrolling PDF viewer — shows each page with text, scrollable, with zoom."""

        def __init__(self, path, **kwargs):
            super().__init__(**kwargs)
            self.path = os.path.abspath(path)
            self._zoom = 1.0

        def compose(self):
            with Horizontal(id="cct-pdf-toolbar", classes="cct-pdf-toolbar"):
                yield Static(os.path.basename(self.path), id="cct-pdf-info", classes="cct-tb-pill")
                yield Button("−", id="cct-pdf-zoomout", classes="cct-ctrl", tooltip="Zoom Out")
                yield Button("+", id="cct-pdf-zoomin", classes="cct-ctrl", tooltip="Zoom In")
                yield Button("Fit", id="cct-pdf-fit", classes="cct-ctrl")
                yield Button("Open Externally", id="cct-pdf-open", classes="cct-ctrl")
                yield Button("✕", id="cct-pdf-close", classes="cct-ctrl")
            yield VerticalScroll(id="cct-pdf-scroll")

        def on_mount(self):
            self._render_pdf()

        def _render_pdf(self):
            try:
                scroll = self.query_one("#cct-pdf-scroll", VerticalScroll)
                scroll.remove_children()
            except Exception:
                return
            # Header
            try:
                size = os.path.getsize(self.path)
                if size < 1024*1024:
                    size_str = f"{size/1024:.1f} KB"
                else:
                    size_str = f"{size/(1024*1024):.1f} MB"
            except Exception:
                size_str = "?"
            # Try to get pages
            pages_text = []
            page_count = 0
            # Use mount with children in one call to avoid "Can't mount before parent is mounted"
            try:
                import fitz
                doc = fitz.open(self.path)
                page_count = len(doc)
                for i in range(min(page_count, 20)):
                    page = doc[i]
                    text = page.get_text()[:2000]
                    preview = text[:int(800 * self._zoom)] if text else "[dim]No extractable text on this page (scanned PDF)[/]"
                    # Create page as Vertical with children via compose
                    pg = Vertical(
                        Static(f"[b]Page {i+1}/{page_count}[/]  [dim]{size_str} · zoom {int(self._zoom*100)}%[/]", classes="cct-pdf-page-header"),
                        Static(preview, classes="cct-pdf-page-text"),
                        classes="cct-pdf-page"
                    )
                    scroll.mount(pg)
                doc.close()
                if page_count == 0:
                    scroll.mount(Static("[dim]PDF is empty[/]"))
                elif page_count > 20:
                    scroll.mount(Static(f"[dim]... {page_count-20} more pages not shown (limit 20) — open externally for full[/]"))
            except Exception:
                try:
                    import PyPDF2
                    with open(self.path, "rb") as f:
                        reader = PyPDF2.PdfReader(f)
                        page_count = len(reader.pages)
                        for i in range(min(page_count, 20)):
                            text = reader.pages[i].extract_text()[:2000] or "[dim]No text[/]"
                            pg = Vertical(
                                Static(f"[b]Page {i+1}/{page_count}[/]", classes="cct-pdf-page-header"),
                                Static(text[:int(800*self._zoom)], classes="cct-pdf-page-text"),
                                classes="cct-pdf-page"
                            )
                            scroll.mount(pg)
                except Exception as e:
                    scroll.mount(Static(f"[dim]PDF preview requires PyMuPDF (`pip install PyMuPDF`) or PyPDF2.[/]\n[dim]Error: {e}[/]\n[dim]Try opening externally.[/]"))
                    page_count = "?"
            try:
                self.query_one("#cct-pdf-info", Static).update(f"{os.path.basename(self.path)} · {page_count if isinstance(page_count,int) else page_count} pages")
            except Exception:
                pass

        def on_button_pressed(self, event):
            bid = event.button.id
            if bid == "cct-pdf-close":
                try:
                    node = self._parent
                    while node is not None and not isinstance(node, EditorPane):
                        node = getattr(node, "_parent", None)
                    if isinstance(node, EditorPane):
                        for p, tid in list(node._open_paths.items()):
                            if os.path.normcase(p) == os.path.normcase(self.path):
                                node.close_active(tid)
                                break
                except Exception:
                    pass
            elif bid == "cct-pdf-zoomin":
                self._zoom = min(2.5, self._zoom * 1.25)
                self._render_pdf()
            elif bid == "cct-pdf-zoomout":
                self._zoom = max(0.5, self._zoom / 1.25)
                self._render_pdf()
            elif bid == "cct-pdf-fit":
                self._zoom = 1.0
                self._render_pdf()
            elif bid == "cct-pdf-open":
                try:
                    import pathlib
                    uri = pathlib.Path(self.path).resolve().as_uri()
                    from ..host.launcher import launch_cat_host, can_launch_host
                    if can_launch_host():
                        launch_cat_host(start_browser_url=uri, start_mode="browser", block=False)
                except Exception:
                    pass

    class EditorPane(Vertical):
        """Tabbed multi-file editor. One TabPane per open file, each
        holding one `TextArea.code_editor()` keyed by absolute path so
        opening the same file twice focuses the existing tab instead of
        duplicating it. A status toolbar above the tabs shows the
        active file's name, language, encoding, cursor position,
        indentation, modified state and a ✕ close button; each tab
        carries its own ✕ close zone on the right edge."""

        BINDINGS = [
            ("ctrl+w", "close_active", "Close Tab"),
            ("ctrl+tab", "next_tab", "Next Tab"),
            ("ctrl+shift+tab", "previous_tab", "Previous Tab"),
            ("escape", "editor_escape", "Back to Chat"),
            ("shift+enter", "show_preview", "Show Preview"),
            ("ctrl+shift+enter", "show_preview", "Show Preview"),
            ("cmd+shift+enter", "show_preview", "Show Preview"),
            ("super+shift+enter", "show_preview", "Show Preview"),
            ("ctrl+enter", "show_preview", "Show Preview"),
        ]

        _TAB_PREFIX = "--content-tab-"

        _DISPLAY_LANGUAGES = {
            "python": "Python", "markdown": "Markdown", "json": "JSON",
            "toml": "TOML", "yaml": "YAML", "html": "HTML", "css": "CSS",
            "javascript": "JavaScript", "rust": "Rust", "go": "Go",
            "regex": "Regex", "sql": "SQL", "java": "Java", "bash": "Bash",
            "xml": "XML",
        }

        def __init__(self, id="cct-editor"):
            super().__init__(id=id)
            self._open_paths = {}  # path -> tab_id
            self._dirty = set()
            self._find_open = False
            self._highlighting_warned = False
            self._wrap_on = True
            self._preview_on = False
            # Gesture double-click tracking
            self._last_click_time = 0
            self._last_click_target = None
            # Monotonically increasing, never reused even after a tab
            # closes — the previous `len(self._open_paths)` scheme
            # handed out the SAME numeric prefix again the moment a tab
            # closed and a new one opened (open A id0, open B id1, close
            # A -> dict len back to 1, open C -> id1 again). Textual
            # raises DuplicateIds if that collides with a tab that
            # hasn't finished being torn down yet, and the caller here
            # only wraps the *read* (open()) in a try/except, not this
            # mount — an uncaught DuplicateIds during add_pane is the
            # most likely cause of the reported "blank editor" bug,
            # since the new pane never actually finishes mounting but
            # open_file() had already told the caller it succeeded.
            self._tab_counter = 0
            # v0.7.10: Change tracking for Live Diff Viewer
            self._original_content = {}  # path -> original content (for diff)
            self._change_history = {}    # path -> list of changes
            self._last_tb_refresh = 0.0
            self._tb_refresh_timer = None

        def compose(self):
            with Horizontal(id="cct-editor-toolbar"):
                yield Static("", id="cct-tb-file", classes="cct-tb-file")
                yield Static("", id="cct-tb-language", classes="cct-tb-pill")
                yield Static("UTF-8", id="cct-tb-encoding", classes="cct-tb-pill")
                yield Static("", id="cct-tb-pos", classes="cct-tb-pill")
                yield Static("", id="cct-tb-spaces", classes="cct-tb-pill")
                yield Static("", id="cct-tb-modified", classes="cct-tb-pill")
                # Web preview controls — ▷ and ⿻ only for web-previewable files
                yield Static("\u25b7", id="cct-tb-run",
                             classes="cct-tb-pill cct-tb-run")
                yield Static("\u2ffb", id="cct-tb-split",
                             classes="cct-tb-pill cct-tb-split")
                yield Static("Wrap", id="cct-tb-wrap", classes="cct-tb-pill")
                yield Static("Preview", id="cct-tb-preview", classes="cct-tb-pill")
                yield Static("\u2715", id="cct-tb-close", classes="cct-tb-close")
            with TabbedContent(id="cct-editor-tabs"):
                yield TabPane("Editor", Static(
                    "Open a file from the Explorer to start editing.",
                    classes="cct-editor-placeholder"), id="tab-welcome")
            yield _PreviewPane()

        def on_mount(self):
            self._refresh_toolbar()

        def retheme(self):
            """v0.7.9.0 light-mode audit: called by CCTApp after a
            /theme switch — re-applies the matching editor palette
            (Tokyo Night / GitHub Light) to every OPEN TextArea, so no
            tab is ever left styled with the previous theme."""
            try:
                tabs = self.query_one(TabbedContent)
            except Exception:
                return
            for pane in tabs.query(TabPane):
                for area in pane.query(_EditorArea):
                    _apply_editor_theme(area)

        # ------------------------------------------------------- open/save --
        def _create_tab(self, path, content_widget, is_text=False, text_content=""):
            """Helper to create a new tab with proper label and tracking."""
            self._tab_counter += 1
            tab_id = f"tab-{self._tab_counter}-{abs(hash(path)) % 100000}"
            pane = TabPane(self._tab_label(path, dirty=False), content_widget, id=tab_id)
            tabs = self.query_one(TabbedContent)
            tabs.add_pane(pane)
            self._open_paths[path] = tab_id
            try:
                tabs.remove_pane("tab-welcome")
            except Exception:
                pass
            tabs.active = tab_id
            if is_text:
                self.store_original(path, text_content)
            self._post_tab_count()
            self._refresh_toolbar()
            try:
                from .. import customization as _cust
                if _cust.is_active():
                    shell = self.app.query_one("#cct-workspace") if hasattr(self, "app") and self.app else None
                    if shell and hasattr(shell, "apply_custom_layout"):
                        shell.apply_custom_layout()
            except Exception:
                pass
            return True

        def open_file(self, path):
            """Unified file-type-aware opener: routes to correct visual viewer or code editor."""
            path = os.path.abspath(os.path.expanduser(path))
            try:
                tabs = self.query_one(TabbedContent)
            except Exception:
                return False
            if path in self._open_paths:
                tabs.active = self._open_paths[path]
                return True

            # Use Universal ViewerRegistry first (Images, PDFs, DOCX, PPTX, XLSX, CSV)
            try:
                from ..viewers.registry import get_viewer_registry
                v_reg = get_viewer_registry()
                if v_reg.can_open_visually(path):
                    if not os.path.isfile(path):
                        return False
                    viewer = v_reg.create_viewer_for_file(path, id=f"viewer-{self._tab_counter+1}")
                    if viewer is not None:
                        viewer.path = path
                        return self._create_tab(path, viewer)
            except Exception:
                pass

            ext = os.path.splitext(path)[1].lower()
            # Image viewer
            if is_image_file(path):
                if not os.path.isfile(path):
                    return False
                try:
                    viewer = _ImageViewer(path, id=f"img-{self._tab_counter+1}")
                    viewer.path = path
                    return self._create_tab(path, viewer)
                except Exception:
                    return False
            # PDF viewer
            if ext in _PDF_EXTS:
                if not os.path.isfile(path):
                    return False
                try:
                    viewer = _PdfViewer(path, id=f"pdf-{self._tab_counter+1}")
                    viewer.path = path
                    return self._create_tab(path, viewer)
                except Exception:
                    return False
            # CSV viewer
            if is_csv_file(path):
                if not os.path.isfile(path):
                    return False
                try:
                    viewer = _CsvViewer(path, id=f"csv-{self._tab_counter+1}")
                    viewer.path = path
                    return self._create_tab(path, viewer)
                except Exception:
                    pass  # fall through to text
            # Text/code/markdown/json etc
            if not is_probably_text(path):
                # For unknown binary, try image check already done, else fail
                return False
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except Exception:
                return False
            lang = language_for(path)
            area = _EditorArea.code_editor(text, language=lang, id=f"ed-{self._tab_counter+1}-{abs(hash(path)) % 100000}")
            area.path = path
            area.soft_wrap = True
            _apply_editor_theme(area)
            if lang and not HIGHLIGHTING_AVAILABLE:
                self._warn_no_highlighting()
            return self._create_tab(path, area, is_text=True, text_content=text)

        def open_file_at(self, path: str, line: int = 1, col: int = 1) -> bool:
            """Open file and navigate cursor to line and column."""
            ok = self.open_file(path)
            if not ok:
                return False
            area = self.active_text_area()
            if area and hasattr(area, "move_cursor"):
                try:
                    target_row = max(0, int(line) - 1)
                    target_col = max(0, int(col) - 1)
                    area.move_cursor((target_row, target_col))
                    area.scroll_cursor_visible()
                except Exception:
                    pass
            return True

        def _post_tab_count(self):
            """Tells the shell how many *files* are open (the Welcome
            placeholder never counts) so it can pick split vs. stacked
            layout and show/hide the Chat/Files switcher."""
            try:
                self.post_message(EditorTabsChanged(len(self._open_paths)))
            except Exception:
                pass

        def close_active(self, tab_id=None):
            """Close the active tab (or specific tab_id if provided)."""
            try:
                tabs = self.query_one(TabbedContent)
                target_id = tab_id or tabs.active
                if not target_id or target_id == "tab-welcome":
                    return
                for p, tid in list(self._open_paths.items()):
                    if tid == target_id:
                        del self._open_paths[p]
                        self._dirty.discard(p)
                        break
                tabs.remove_pane(target_id)
                if not self._open_paths:
                    try:
                        tabs.add_pane(TabPane("Editor", Static(
                            "Open a file from the Explorer to start editing.",
                            classes="cct-editor-placeholder"), id="tab-welcome"))
                    except Exception:
                        pass
                self._post_tab_count()
                self._refresh_toolbar()
                try:
                    from .. import customization as _cust
                    if _cust.is_active():
                        shell = self.app.query_one("#cct-workspace") if hasattr(self, "app") and self.app else None
                        if shell and hasattr(shell, "apply_custom_layout"):
                            shell.apply_custom_layout()
                except Exception:
                    pass
            except Exception:
                pass

        def _activate_tab(self, tab_id):
            try:
                tabs = self.query_one(TabbedContent)
                tabs.active = tab_id
            except Exception:
                pass

        def _tab_label(self, path, dirty):
            name = os.path.basename(path)
            icon = get_file_icon(path)
            prefix = f"{icon} " if icon else ""
            return ("\u25cf " if dirty else "") + prefix + name

        def _set_tab_dirty(self, path, dirty):
            """Marks/clears the unsaved-changes indicator (spec v0.7.4
            PRIMARY GOALS #4: "mark unsaved changes correctly"). Best
            effort: Textual's TabPane doesn't expose a documented
            'rename this tab' setter, so this reaches for the Tab
            widget's own `.label` (what the visible tab strip actually
            renders) and silently no-ops if that attribute isn't there
            in the installed Textual version — the dirty *state*
            (self._dirty) is still tracked correctly either way, so
            save-time behavior never depends on this cosmetic step
            succeeding."""
            tab_id = self._open_paths.get(path)
            if not tab_id:
                return
            already_dirty = path in self._dirty
            if dirty == already_dirty:
                return  # No change in dirty state -> skip redundant DOM updates!
            if dirty:
                self._dirty.add(path)
            else:
                self._dirty.discard(path)
            try:
                tabs = self.query_one(TabbedContent)
                tab = tabs.get_tab(tab_id)
                tab.label = self._tab_label(path, dirty)
            except Exception:
                pass

        def on_text_area_changed(self, event):
            """TextArea.Changed bubbles up from whichever tab's editor
            the user is typing in. Marks that file dirty immediately."""
            area = getattr(event, "text_area", None) or getattr(event, "control", None)
            path = getattr(area, "path", None)
            if path:
                self._set_tab_dirty(path, True)
            self._schedule_toolbar_refresh()

        def on_text_area_selection_changed(self, event):
            """Cursor moved (or selection changed) in an editor tab —
            keep the toolbar's Ln/Col readout honest with low latency."""
            self._schedule_toolbar_refresh()

        def _schedule_toolbar_refresh(self):
            # Throttle toolbar updates during rapid typing to keep editor smooth and responsive
            now = time.time()
            if getattr(self, "_last_tb_refresh", 0.0) + 0.08 < now:
                self._last_tb_refresh = now
                self._refresh_toolbar()
            else:
                if getattr(self, "_tb_refresh_timer", None) is None:
                    try:
                        self._tb_refresh_timer = self.set_timer(0.08, self._delayed_toolbar_refresh)
                    except Exception:
                        self._refresh_toolbar()

        def _delayed_toolbar_refresh(self):
            self._tb_refresh_timer = None
            self._last_tb_refresh = time.time()
            self._refresh_toolbar()

        def on_tabbed_content_tab_activated(self, event):
            """User clicked a tab (or a tab became active another way):
            sync the toolbar to the newly active file."""
            self._refresh_toolbar()

        # -------------------------------------------------------- toolbar --
        def _language_label(self, lang):
            if not lang or lang == "css":
                return "Plain Text"
            return self._DISPLAY_LANGUAGES.get(lang, lang.title())

        def _get_active_content(self):
            """Return (widget, path) for the active tab regardless of viewer type."""
            try:
                tabs = self.query_one(TabbedContent)
                pane = tabs.get_pane(tabs.active)
                if pane is None:
                    return None, None
                for area in pane.query(_EditorArea):
                    return area, getattr(area, "path", None)
                for child in pane.query("*"):
                    if hasattr(child, "path"):
                        return child, getattr(child, "path", None)
            except Exception:
                pass
            return None, None

        def _refresh_toolbar(self):
            """Syncs the status toolbar to the active tab: file name,
            language, cursor position, indentation and modified state.
            Hidden entirely while only the Welcome placeholder is up.
            For visual viewers shows viewer-specific info."""
            try:
                bar = self.query_one("#cct-editor-toolbar")
            except Exception:
                return
            area = self.active_text_area()
            content, path = self._get_active_content()
            if area is None and (content is not None or path is not None):
                bar.display = True
                icon = get_file_icon(path or "")
                name = os.path.basename(path) if path else "Viewer"
                self.query_one("#cct-tb-file", Static).update(f"{icon} {name}")
                try:
                    self.query_one("#cct-tb-file", Static).tooltip = path or ""
                except Exception:
                    pass
                for sel in ("#cct-tb-language", "#cct-tb-pos", "#cct-tb-spaces", "#cct-tb-modified", "#cct-tb-wrap", "#cct-tb-preview"):
                    try:
                        self.query_one(sel).display = False
                    except Exception:
                        pass
                try:
                    self.query_one("#cct-tb-run").display = False
                    self.query_one("#cct-tb-split").display = False
                except Exception:
                    pass
                try:
                    self.query_one("#cct-tb-close", Static).display = True
                except Exception:
                    pass
                return
            if area is None or not hasattr(area, "path"):
                bar.display = False
                return
            bar.display = True
            row, col = (0, 0)
            try:
                row, col = area.cursor_location
            except Exception:
                pass
            dirty = area.path in self._dirty
            icon = get_file_icon(area.path)
            self.query_one("#cct-tb-file", Static).update(f"{icon} {os.path.basename(area.path)}")
            try:
                self.query_one("#cct-tb-file", Static).tooltip = area.path
            except Exception:
                pass
            self.query_one("#cct-tb-language", Static).update(
                self._language_label(area.language))
            self.query_one("#cct-tb-pos", Static).update(f"Ln {row + 1}, Col {col + 1}")
            self.query_one("#cct-tb-spaces", Static).update(
                f"Spaces: {getattr(area, 'indent_width', 4)}")
            self.query_one("#cct-tb-modified", Static).update(
                "\u25cf Modified" if dirty else "")
            # Ensure code pills visible again (may have been hidden for image)
            for sel in ("#cct-tb-language", "#cct-tb-encoding", "#cct-tb-pos", "#cct-tb-spaces", "#cct-tb-modified", "#cct-tb-wrap", "#cct-tb-preview"):
                try:
                    self.query_one(sel, Static).display = True
                except Exception:
                    pass
            try:
                self.query_one("#cct-tb-encoding", Static).display = True
            except Exception:
                pass
            # ▷ and ⿻ — show only for web-previewable files (spec 2)
            try:
                run_pill = self.query_one("#cct-tb-run")
                split_pill = self.query_one("#cct-tb-split")
                is_web = is_web_previewable(area.path)
                is_split = is_web or is_markdown_file(area.path)
                run_pill.display = bool(is_web)
                split_pill.display = bool(is_split)
                try:
                    run_pill.set_class(is_web, "-run")
                    split_pill.set_class(is_split, "-split")
                except Exception:
                    pass
                try:
                    if is_web:
                        run_pill.tooltip = "Open Live Web Preview (▷)"
                        split_pill.tooltip = "Split editor / preview (⿻)"
                    elif is_split:
                        split_pill.tooltip = "Split editor / preview (⿻)"
                        try:
                            run_pill.tooltip = ""
                        except: pass
                    else:
                        run_pill.tooltip = ""
                        split_pill.tooltip = ""
                except Exception:
                    pass
            except Exception:
                pass
            self._update_view_pills(area)
            self._refresh_preview(area)

        def _apply_toolbar_compaction(self):
            """v0.7.10: the right pane is now user-resizable down to ~24
            columns — the status row MUST compress instead of pushing the
            ▷ / ⿻ / ✕ controls past the visible edge (they'd become
            unclickable). Informational pills collapse first; file name ·
            ▷ · ⿻ · ✕ always survive. Re-applied on every toolbar refresh AND
            on pane resize."""
            try:
                bar_w = self.size.width or 100
                compact = bar_w < 72    # drop language/encoding/pos/spaces
                tiny = bar_w < 54       # additionally drop Wrap/Preview/Mod
                # ▷ and ⿻ are never hidden by compaction — they are primary tab controls
                for sel, hidden in (("#cct-tb-language", compact),
                                    ("#cct-tb-encoding", compact),
                                    ("#cct-tb-pos", compact),
                                    ("#cct-tb-spaces", compact),
                                    ("#cct-tb-modified", tiny),
                                    ("#cct-tb-wrap", tiny),
                                    ("#cct-tb-preview", tiny)):
                    try:
                        self.query_one(sel, Static).display = not hidden
                    except Exception:
                        pass
                # Ensure close and web controls stay visible
                try:
                    self.query_one("#cct-tb-close", Static).display = True
                except Exception:
                    pass
            except Exception:
                pass

        def on_resize(self):
            self._apply_toolbar_compaction()

        def _update_view_pills(self, area):
            """Wrap / Preview pills mirror the active editor's real
            state: the Wrap pill tracks the TextArea's soft_wrap, the
            Preview pill tracks this pane's preview toggle. The `-on`
            class lights the pill in the accent color."""
            try:
                wrap_pill = self.query_one("#cct-tb-wrap", Static)
            except Exception:
                return
            try:
                self._wrap_on = bool(getattr(area, "soft_wrap", True))
            except Exception:
                pass
            wrap_pill.update(f"Wrap: {'On' if self._wrap_on else 'Off'}")
            wrap_pill.set_class(self._wrap_on, "-on")
            try:
                preview_pill = self.query_one("#cct-tb-preview", Static)
                preview_pill.set_class(self._preview_on, "-on")
            except Exception:
                pass

        def _refresh_preview(self, area=None):
            """Shows/hides the live preview pane and refills it from the
            active tab. Only Markdown files get a real rendered preview;
            every other language gets an honest hint instead of fake
            output. Hidden whenever the Preview toggle is off."""
            try:
                pane = self.query_one(_PreviewPane)
            except Exception:
                return
            if not self._preview_on:
                pane.display = False
                return
            pane.display = True
            if area is None:
                area = self.active_text_area()
            if area is None or not hasattr(area, "path"):
                pane.set_source("", "Open a file to preview it.")
                return
            if (area.language or "") != "markdown":
                pane.set_source("", "Live preview renders Markdown files. "
                                "This tab is not Markdown.")
                return
            try:
                pane.set_source(area.text)
            except Exception:
                pane.set_source("", "Preview unavailable.")

        def _toggle_wrap(self, area):
            try:
                self._wrap_on = not bool(getattr(area, "soft_wrap", True))
                area.soft_wrap = self._wrap_on
            except Exception:
                self._wrap_on = True
            self._update_view_pills(area)

        def _toggle_preview(self, area):
            self._preview_on = not self._preview_on
            try:
                preview_pill = self.query_one("#cct-tb-preview", Static)
                preview_pill.set_class(self._preview_on, "-on")
            except Exception:
                pass
            self._refresh_preview(area)

        def _warn_no_highlighting(self):
            """Shown at most once per session, the first time a file
            that should be highlighted opens with `tree_sitter` not
            actually importable — tells the user the real fix
            (`pip install "textual[syntax]"`) instead of leaving a
            silently plain-text editor with no explanation."""
            if self._highlighting_warned:
                return
            self._highlighting_warned = True
            self.mount(
                Static(
                    "\u26a0 Syntax highlighting isn't installed \u2014 run: "
                    "pip install \"textual[syntax]\"  (click to dismiss)",
                    id="cct-editor-highlight-warning",
                    classes="cct-editor-highlight-warning",
                ),
                before="#cct-editor-tabs",
            )

        def on_click(self, event):
            """Two close affordances, both delegated to the tab/control
            that was actually clicked:
            - the toolbar's ✕ closes the active file;
            - the right-edge ✕ zone of a tab label closes that tab.
            Tab ✕ closes are deferred one refresh so the tab's own
            activation (Tab.Clicked -> Tabs._on_tab_clicked) is fully
            processed before the pane is torn down.

            Also handles GESTURES: double-click on the editor area
            triggers the configured gesture for (double_click, editor)
            — e.g. open in VS Code (spec section 23)."""
            import time as _t
            widget = event.widget
            widget_id = getattr(widget, "id", None)
            # --- Gesture: double-click editor → VS Code ---
            try:
                is_editor_area = isinstance(widget, _EditorArea) or isinstance(widget, TextArea)
                # Also consider clicks inside the editor pane itself
                if is_editor_area or widget_id in (None, "cct-editor"):
                    now = _t.time()
                    if now - self._last_click_time < 0.35 and self._last_click_target == "editor":
                        # double-click detected
                        self._last_click_time = 0
                        self._last_click_target = None
                        try:
                            from ..gestures.manager import handle_gesture
                            area = self.active_text_area()
                            ctx = {"path": getattr(area, "path", "") if area else "", "workspace": getattr(area, "path", "") if area else ""}
                            if handle_gesture("double_click", "editor", app=getattr(self, "app", None), context=ctx):
                                event.stop()
                                return
                        except Exception:
                            pass
                    else:
                        self._last_click_time = now
                        self._last_click_target = "editor" if is_editor_area else None
            except Exception:
                pass
            if widget_id == "cct-editor-highlight-warning":
                widget.remove()
                return
            if widget_id == "cct-tb-close":
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
                                except Exception:
                                    pass
                            self.set_timer(0.8, _to_split)
                        else:
                            shell.set_right_mode(WorkspaceMode.SPLIT)
                    except Exception:
                        from .events import PreviewRequested
                        self.post_message(PreviewRequested(path))
                return
            if isinstance(widget, Tab) and widget_id and widget_id.startswith(self._TAB_PREFIX):
                target_id = widget_id[len(self._TAB_PREFIX):]
                self._activate_tab(target_id)
                return

        def active_text_area(self):
            tabs = self.query_one(TabbedContent)
            try:
                pane = tabs.get_pane(tabs.active)
            except Exception:
                return None
            areas = pane.query(TextArea)
            return areas.first() if areas else None

        def save_active(self):
            area = self.active_text_area()
            if area is None or not hasattr(area, "path"):
                return False, "No file is open."
            try:
                with open(area.path, "w", encoding="utf-8") as f:
                    f.write(area.text)
            except Exception as e:
                return False, str(e)
            self._set_tab_dirty(area.path, False)
            self.post_message(FileSaved(area.path))
            return True, area.path

        def reload_if_open(self, path):
            """If `path` is currently open in a tab, re-read it from disk
            and replace the tab's text — used after the AI (or an
            external watcher, once one exists) modifies a file that's
            already open, so the editor doesn't keep showing stale
            content. Cursor position is preserved on a best-effort basis
            (same row/col clamped to the new text's bounds) since an
            AI edit can change line count/offsets in ways a simple
            row/col carry-over can't perfectly track — that's an honest
            limitation, not a claim of true diff-based cursor mapping."""
            path = os.path.abspath(os.path.expanduser(path))
            tab_id = self._open_paths.get(path)
            if not tab_id:
                return False
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except Exception:
                return False
            tabs = self.query_one(TabbedContent)
            pane = tabs.get_pane(tab_id)
            areas = pane.query(TextArea)
            if not areas:
                return False
            area = areas.first()
            row, col = area.cursor_location
            area.text = text
            lines = text.splitlines() or [""]
            row = min(row, len(lines) - 1)
            col = min(col, len(lines[row]))
            try:
                area.move_cursor((row, col))
            except Exception:
                pass
            self._set_tab_dirty(path, False)
            return True

        def close_active(self, tab_id=None):
            """Closes the active tab (or a specific one, used by the
            per-tab ✕) and restores the Welcome placeholder when the
            last file tab goes away. Ctrl+W routes here too."""
            tabs = self.query_one(TabbedContent)
            active = tab_id or tabs.active
            if active == "tab-welcome" or not active:
                return
            path = next((p for p, t in self._open_paths.items() if t == active), None)
            if path:
                del self._open_paths[path]
                self._dirty.discard(path)
            tabs.remove_pane(active)
            if not self._open_paths:
                tabs.add_pane(TabPane("Editor", Static(
                    "Open a file from the Explorer to start editing.",
                    classes="cct-editor-placeholder"), id="tab-welcome"))
                # add_pane mounts panes hidden, so the placeholder must
                # be explicitly activated once it has actually landed.
                self.call_after_refresh(self._activate_tab, "tab-welcome")
                # If we were in fullscreen with no files left, exit fullscreen
                # so header/sidebar/chat become visible again (fix for glitch
                # where closing all tabs while fullscreen leaves header hidden).
                try:
                    # Find workspace shell and check fullscreen
                    node = self._parent
                    while node is not None and not hasattr(node, "fullscreen"):
                        node = getattr(node, "_parent", None)
                    if node is not None and getattr(node, "fullscreen", False):
                        # Exit fullscreen via app action to restore header/status
                        try:
                            self.app.action_toggle_right_pane_fullscreen()
                        except Exception:
                            # fallback: directly restore
                            try:
                                node.set_fullscreen(False)
                            except Exception:
                                pass
                            try:
                                self.app.brand_header.display = True
                                self.app.status_line.display = True
                            except Exception:
                                pass
                except Exception:
                    pass
            self._refresh_toolbar()
            self._post_tab_count()

        def action_close_active(self):
            self.close_active()

        def _tabs_bar(self):
            try:
                return next(iter(self.query(Tabs)))
            except Exception:
                return None

        def action_next_tab(self):
            bar = self._tabs_bar()
            if bar is not None:
                bar.action_next_tab()

        def action_previous_tab(self):
            bar = self._tabs_bar()
            if bar is not None:
                bar.action_previous_tab()

        def action_editor_escape(self):
            """Esc: close the find/replace bar if it's open; exit the
            right pane's EXPANDED (⿻) state if that's active (spec
            section 24 — Esc leaves fullscreen before anything else);
            otherwise hand focus back to the chat composer (via
            ChatRequested, which the shell resolves to a pane switch +
            app-side composer focus)."""
            if self._find_open:
                self.toggle_find()
                return
            try:
                # Query by id, not class: workspace.py imports THIS
                # module, so a class import here would be circular.
                shell = self.app.query_one("#cct-workspace")
                if shell.fullscreen:
                    self.app.action_toggle_right_pane_fullscreen()
                    return
            except Exception:
                pass
            try:
                self.post_message(ChatRequested())
            except Exception:
                pass

        def action_show_preview(self):
            """Shift+Enter / Cmd+Shift+Enter or ▷ click: show live preview and open in CAT browser (real-time)."""
            area = self.active_text_area()
            path = getattr(area, "path", None) if area else None
            if not path or not is_web_previewable(path):
                # 1. Check open tabs for any web-previewable file
                try:
                    for p in self._open_paths.keys():
                        if is_web_previewable(p):
                            path = p
                            break
                except Exception:
                    pass
            if not path or not is_web_previewable(path):
                # 2. Search workspace for index.html, home.html, or any .html/.htm
                try:
                    from .. import workspace as _ws
                    root = _ws.root_dir()
                    if root and os.path.isdir(root):
                        for f in os.listdir(root):
                            if f.lower().endswith((".html", ".htm")):
                                path = os.path.join(root, f)
                                break
                        if not path or not os.path.isfile(path):
                            for dirpath, dirs, files in os.walk(root):
                                dirs[:] = [d for d in dirs if not d.startswith(('.', '_')) and d not in ('node_modules', 'venv', '.venv', '__pycache__')]
                                for f in files:
                                    if f.lower().endswith((".html", ".htm")):
                                        path = os.path.join(dirpath, f)
                                        break
                                if path and os.path.isfile(path):
                                    break
                except Exception:
                    pass

            if path:
                from .events import PreviewRequested
                self.post_message(PreviewRequested(path))

        def _open_in_cat_browser(self, path):
            """Open the live preview URL in CAT's embedded browser (real-time)."""
            try:
                ctrl = getattr(self.app, "_preview_ctrl", None)
                url = None
                if ctrl and getattr(ctrl, "base_url", None):
                    # Use preview URL if available, else construct from path
                    try:
                        url = ctrl.url or ctrl.base_url
                    except Exception:
                        url = ctrl.base_url
                if not url:
                    # Fallback: try to get from workspace
                    try:
                        from ..browser.preview_entry import relative_url_for
                        from .. import workspace as _ws
                        root = _ws.root_dir()
                        if root and path:
                            rel = relative_url_for(os.path.abspath(path), root)
                            if rel:
                                # Need base_url, try to get from ctrl or guess
                                base = getattr(ctrl, "base_url", None) if ctrl else None
                                if base:
                                    url = base.rstrip("/") + "/" + rel.lstrip("/")
                    except Exception:
                        pass
                if not url and path:
                    import pathlib
                    url = pathlib.Path(path).resolve().as_uri()

                if url:
                    # Open in CAT browser (embedded Chromium / Qt WebEngine — never external Chrome/Edge)
                    try:
                        from ..host.launcher import launch_cat_host, can_launch_host
                        if can_launch_host():
                            launch_cat_host(start_browser_url=url, start_mode="browser", block=False)
                            return
                    except Exception:
                        pass
            except Exception:
                pass

        # --------------------------------------------------- find/replace --
        def toggle_find(self):
            self._find_open = not self._find_open
            existing = self.query(_FindBar)
            if self._find_open:
                if not existing:
                    self.mount(_FindBar())
            else:
                for bar in existing:
                    bar.remove()

        def on_button_pressed(self, event):
            bid = event.button.id
            if bid == "cct-tb-run":
                area = self.active_text_area()
                path = getattr(area, "path", None)
                if path:
                    from .events import PreviewRequested
                    self.post_message(PreviewRequested(path))
                    # Also open in CAT browser for real-time preview (user requested)
                    try:
                        self.set_timer(0.9, lambda: self._open_in_cat_browser(path))
                    except Exception:
                        pass
                return
            elif bid == "cct-tb-split":
                # ⿻ is for code editor fullscreen/restore per user spec
                try:
                    self.app.action_toggle_right_pane_fullscreen()
                except Exception:
                    # Fallback to split if fullscreen not available
                    area = self.active_text_area()
                    path = getattr(area, "path", None)
                    if path:
                        try:
                            from ..browser import WorkspaceMode
                            shell = self.app.query_one("#cct-workspace")
                            if shell and shell.mode is WorkspaceMode.SPLIT:
                                shell.set_right_mode(WorkspaceMode.CODE)
                            elif shell:
                                shell.set_right_mode(WorkspaceMode.SPLIT)
                        except Exception:
                            pass
                return
            if bid == "cct-find-close":
                self.toggle_find()
            elif bid == "cct-find-next":
                self._find_next()
            elif bid == "cct-replace-all":
                self._replace_all()

        def _find_next(self):
            """Line-by-line search starting just after the cursor,
            wrapping to the top — uses only TextArea's public
            cursor_location/move_cursor API rather than reaching into
            its internal Document offset math, which isn't part of the
            widget's stable public surface."""
            area = self.active_text_area()
            if area is None:
                return
            query = self.query_one("#cct-find-input", Input).value
            if not query:
                return
            lines = area.text.splitlines()
            cur_row, cur_col = area.cursor_location
            n = len(lines)
            for i in range(n + 1):
                row = (cur_row + i) % n if n else 0
                line = lines[row] if row < len(lines) else ""
                search_from = cur_col + 1 if i == 0 else 0
                col = line.find(query, search_from)
                if col == -1 and i == 0:
                    col = line.find(query)  # also allow a match at/before the cursor on the same line
                if col != -1:
                    area.move_cursor((row, col))
                    area.selection = area.selection.__class__((row, col), (row, col + len(query)))
                    area.scroll_cursor_visible()
                    return

        def _replace_all(self):
            area = self.active_text_area()
            if area is None:
                return
            query = self.query_one("#cct-find-input", Input).value
            repl = self.query_one("#cct-replace-input", Input).value
            if not query:
                return
            area.text = area.text.replace(query, repl)

        # --------------------------------------------------- diff viewer --
        def store_original(self, path, content):
            """Store original content for diff comparison (v0.7.10)."""
            path = os.path.abspath(os.path.expanduser(path))
            if path not in self._original_content:
                self._original_content[path] = content

        def get_original(self, path):
            """Get original content for diff comparison."""
            path = os.path.abspath(os.path.expanduser(path))
            return self._original_content.get(path, "")

        def compute_diff(self, path):
            """Compute diff between original and current content."""
            path = os.path.abspath(os.path.expanduser(path))
            original = self.get_original(path)
            tab_id = self._open_paths.get(path)
            if not tab_id:
                return None
            try:
                tabs = self.query_one(TabbedContent)
                pane = tabs.get_pane(tab_id)
                areas = pane.query(TextArea)
                if not areas:
                    return None
                area = areas.first()
                current = area.text
                return self._compute_line_diff(original, current)
            except Exception:
                return None

        def _compute_line_diff(self, old_text, new_text):
            """Compute a simple line-by-line diff."""
            old_lines = old_text.splitlines()
            new_lines = new_text.splitlines()
            import difflib
            diff = list(difflib.unified_diff(
                old_lines, new_lines,
                lineterm='',
                n=0
            ))
            return diff

        def show_diff(self, path=None):
            """Show diff for the active file or a specific path."""
            if path is None:
                area = self.active_text_area()
                if area is None:
                    return
                path = getattr(area, "path", None)
                if not path:
                    return
            diff = self.compute_diff(path)
            if diff is None:
                return
            # Store change in history
            path = os.path.abspath(os.path.expanduser(path))
            if path not in self._change_history:
                self._change_history[path] = []
            self._change_history[path].append({
                'diff': diff,
                'timestamp': __import__('time').time()
            })
            # Emit event for UI to show diff
            try:
                from .events import DiffViewerRequested
                self.post_message(DiffViewerRequested(path, diff))
            except Exception:
                pass

        def has_changes(self, path=None):
            """Check if a file has unsaved changes from original."""
            if path is None:
                area = self.active_text_area()
                if area is None:
                    return False
                path = getattr(area, "path", None)
                if not path:
                    return False
            path = os.path.abspath(os.path.expanduser(path))
            original = self.get_original(path)
            if not original:
                return False
            tab_id = self._open_paths.get(path)
            if not tab_id:
                return False
            try:
                tabs = self.query_one(TabbedContent)
                pane = tabs.get_pane(tab_id)
                areas = pane.query(TextArea)
                if not areas:
                    return False
                area = areas.first()
                return area.text != original
            except Exception:
                return False

else:
    EditorPane = None
