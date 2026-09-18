"""
CCT UI — PersonalizeCenter: personalization hub (v0.8.a) — glitch-fixed.

Fixes:
- Removed buggy `with Vertical(): container.mount()` pattern (mounted to wrong parent)
- Responsive height: auto + max-height instead of fixed
- Fixed memory row overflow on narrow terminals
- Proper mount tree via explicit Horizontal/Vertical objects
- Clean input handling, profile sync, about_me wiring
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import os
import time
import json

TEXTUAL_AVAILABLE = True
try:
    from textual.screen import Screen
    from textual.containers import Vertical, Horizontal, ScrollableContainer
    try:
        from textual.containers import HorizontalScroll
    except Exception:
        HorizontalScroll = Horizontal
    from textual.widgets import Static, Button, Input, Switch, Label
    from textual.binding import Binding
    try:
        from textual.widgets import TextArea
        _HAS_TEXTAREA = True
    except Exception:
        TextArea = None
        _HAS_TEXTAREA = False
except Exception:
    TEXTUAL_AVAILABLE = False
    _HAS_TEXTAREA = False

if TEXTUAL_AVAILABLE:
    try:
        from .. import ai_personalization as ap
    except Exception:
        ap = None
    try:
        from .. import permissions as perm
    except Exception:
        perm = None
    try:
        from .. import memory
    except Exception:
        memory = None
    try:
        from .. import memory_v2
    except Exception:
        memory_v2 = None
    try:
        from . import theme_css
    except Exception:
        theme_css = None
    try:
        from .. import config as cct_config
    except Exception:
        cct_config = None

    _TONE_BTNS = (
        ("balanced", "Balanced"),
        ("concise", "Concise"),
        ("detailed", "Detailed"),
        ("playful", "Playful"),
        ("formal", "Formal"),
    )
    _SEG_BTNS = {
        "pc-reasoning": (("low", "Low"), ("medium", "Medium"), ("high", "High")),
        "pc-length": (("short", "Short"), ("medium", "Medium"), ("long", "Long")),
        "pc-memory": (("auto", "Auto"), ("on", "On"), ("off", "Off")),
        "pc-teaching": (("direct", "Direct"), ("step_by_step", "Step-by-Step"), ("explanatory", "Explanatory")),
    }
    _NAV_SECTIONS = [
        ("PERSONALIZATION", [
            ("personality", "🎨  AI Personality"),
            ("response_style", "\u25c7  Response Style"),
            ("tone", "\u25c7  Tone"),
            ("instructions", "\u25c7  Custom Instructions"),
            ("about_me", "\u25c7  About Me"),
        ]),
        ("MEMORY", [
            ("mem_overview", "\U0001f9e0  Memory Overview"),
            ("mem_saved", "\U0001f9e0  Saved Memories"),
            ("mem_add", "+ Add Memory"),
        ]),
        ("AI BEHAVIOR", [
            ("context", "\u25c7  Context"),
            ("coding_prefs", "\u25c7  Coding Preferences"),
            ("proactivity", "\u25c7  Proactivity"),
        ]),
        ("SECURITY", [
            ("permissions", "\U0001f510  Security & Access"),
            ("perm_list", "\U0001f6e1  Permissions"),
            ("privacy", "\u25c7  Privacy"),
        ]),
    ]
    _HINTS = {
        "personality": "Tab: next field  \u00b7  Esc: close",
        "response_style": "Tab: next  \u00b7  Esc: close",
        "tone": "Click tone  \u00b7  Esc: close",
        "instructions": "Tab: edit  \u00b7  Esc: close",
        "about_me": "Tab: next  \u00b7  Esc: close",
        "mem_overview": "Esc: close",
        "mem_saved": "Search/filter  \u00b7  Edit/Delete  \u00b7  Esc: close",
        "mem_add": "Enter: add  \u00b7  Esc: close",
        "context": "Toggle  \u00b7  Esc: close",
        "coding_prefs": "Toggle  \u00b7  Esc: close",
        "proactivity": "Toggle  \u00b7  Esc: close",
        "permissions": "Select mode  \u00b7  Esc: close",
        "perm_list": "Toggle  \u00b7  Esc: close",
        "privacy": "Esc: close",
    }
    _CODING_PREF_KEYS = [
        ("prefer_si", "Prefer SI units", True),
        ("show_steps", "Show step-by-step", True),
        ("show_derivations", "Show derivations", False),
        ("code_comments", "Add code comments", True),
        ("verbose_errors", "Verbose error output", False),
        ("compact_output", "Compact output", False),
    ]
    _CONTEXT_SOURCES = [
        ("current_conversation", "Current conversation", True),
        ("workspace_context", "Workspace context", True),
        ("project_files", "Project files", True),
        ("custom_instructions", "Custom instructions", True),
        ("saved_memories", "Saved memories", True),
    ]
    _PROACTIVITY_KEYS = [
        ("auto_suggest", "Auto-suggest improvements", True),
        ("explain_changes", "Explain file changes", True),
        ("ask_before_files", "Ask before file changes", True),
        ("command_execution", "Command execution", True),
    ]
    _ABOUT_ME_FIELDS = [
        ("name", "Name", ""),
        ("role", "Role", "e.g. Software Engineer"),
        ("experience", "Experience", "e.g. 5 years"),
        ("interests", "Programming interests", "e.g. AI, Web, Systems"),
        ("technologies", "Preferred technologies", "e.g. Python, Rust, React"),
        ("context", "Additional context", ""),
    ]

    def _hex(role):
        if theme_css is not None:
            try:
                return theme_css.current_hex(role)
            except Exception:
                pass
        return "#888888"

    def _fmt_ts(ts):
        if not ts:
            return "\u2014"
        try:
            return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
        except Exception:
            return "\u2014"

    def _safe_query(widget, selector, widget_type=None):
        try:
            if widget_type:
                return widget.query_one(selector, widget_type)
            return widget.query_one(selector)
        except Exception:
            return None

    def _load_about_me():
        if ap is not None and hasattr(ap, "load_about_me"):
            try:
                return ap.load_about_me()
            except Exception:
                pass
        try:
            p = os.path.join(os.path.expanduser("~"), ".cct_about_me.json")
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_about_me(data):
        if ap is not None and hasattr(ap, "ABOUT_ME_FILE"):
            try:
                with open(ap.ABOUT_ME_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                return True
            except Exception:
                pass
        try:
            p = os.path.join(os.path.expanduser("~"), ".cct_about_me.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception:
            return False

    class _NavButton(Button):
        def __init__(self, key, label):
            self.nav_key = key
            super().__init__(label, id=f"pc-nav-{key}", classes="pc-nav-btn")

    class _MemoryRow(Horizontal):
        def __init__(self, memory_obj):
            self.mem = memory_obj
            super().__init__(classes="pc-mem-row")
        def compose(self):
            content = (self.mem.content or "")[:48]
            if len(self.mem.content or "") > 48:
                content += "\u2026"
            cat = (self.mem.category or "").replace("_", " ").title()[:12]
            source = getattr(self.mem, "source", "user") or "user"
            source_label = {"user": "User", "ai": "AI", "imported": "Import"}.get(source, source)[:6]
            yield Static(cat, classes="pc-mem-cat")
            yield Static(content, classes="pc-mem-content")
            yield Static(source_label, classes="pc-mem-source")
            yield Static(_fmt_ts(self.mem.created_at), classes="pc-mem-date")
            yield Button("\u270e", id=f"pc-mem-edit-{self.mem.id}", classes="pc-mem-edit-btn cct-btn-sm")
            yield Button("\u2715", id=f"pc-mem-del-{self.mem.id}", classes="pc-mem-del-btn cct-btn-sm")

    class PersonalizeCenter(Screen):
        CSS = """
        PersonalizeCenter { align: center middle; background: $background 70%; }
        #pc-box {
            width: 98; max-width: 98%; height: 40; max-height: 92%;
            background: $surface; border: heavy; border-top: heavy $surface-highlight; border-left: heavy $surface-highlight; border-bottom: heavy $surface-shadow; border-right: heavy $surface-shadow; padding: 0;
            layout: vertical; overflow: hidden;
        }
        #pc-titlebar { height: 3; min-height: 3; padding: 0 2; border-bottom: solid $border; }
        #pc-title { text-style: bold; width: 1fr; }
        #pc-close { min-width: 3; width: 3; height: 1; }
        #pc-disabled { height: auto; padding: 2 2; align: center middle; }
        .pc-disabled-msg { color: $warning; text-style: bold; height: auto; text-align: center; }
        .pc-disabled-hint { color: $text-faint; height: auto; text-align: center; padding-top: 1; }
        #pc-disabled-actions { height: auto; padding-top: 1; layout: horizontal; align: center middle; }
        #pc-disabled-actions Button { margin: 0 1; }
        #pc-body { height: 1fr; min-height: 0; layout: horizontal; }
        #pc-sidebar { width: 28; min-width: 28; height: 100%; padding: 0; border-right: solid $border; }
        #pc-search { height: 3; min-height: 3; padding: 0 1; border-bottom: solid $border; align-vertical: middle; }
        #pc-search Input {
            width: 1fr; height: 3; min-height: 3; background: $surface;
            border: tall; border-top: tall $surface-shadow; border-left: tall $surface-shadow; border-bottom: tall $surface-highlight; border-right: tall $surface-highlight;
            color: $text; padding: 0 1;
        }
        #pc-search Input:focus {
            border-top: tall $accent-shadow; border-left: tall $accent-shadow; border-bottom: tall $accent-highlight; border-right: tall $accent-highlight;
        }
        #pc-sidebar-inner { width: 100%; height: 1fr; min-height: 0; overflow-y: auto; scrollbar-size-vertical: 1; }
        .pc-nav-section { color: $text-faint; height: 1; min-height: 1; padding: 1 1 0 1; text-style: bold; }
        .pc-nav-btn { width: 100%; height: 1; min-height: 1; padding: 0 1; text-align: left; background: transparent; border: none; color: $text-muted; }
        .pc-nav-btn:hover { background: $accent 10%; color: $text; }
        .pc-nav-btn-sel { background: $accent 15%; color: $accent; text-style: bold; }
        #pc-content { width: 1fr; height: 100%; min-height: 0; padding: 1 2; overflow-y: auto; scrollbar-size-vertical: 1; }
        .pc-section-title { color: $accent; height: 1; min-height: 1; padding-top: 1; margin-top: 1; text-style: bold; }
        .pc-section-title:first-child { padding-top: 0; margin-top: 0; }
        .pc-field { height: auto; min-height: 1; margin-bottom: 1; }
        .pc-flbl { color: $text-faint; height: 1; min-height: 1; }
        .pc-fval { color: $text; height: 1; min-height: 1; }
        .pc-char-count { color: $text-faint; height: 1; text-align: right; }
        .pc-switch-row { height: auto; min-height: 2; padding: 0 1; align-vertical: middle; border-bottom: solid $surface-alt 50%; }
        .pc-switch-row:hover { background: $surface-alt 35%; }
        .pc-switch-label { width: 1fr; color: $text; height: 1; }
        .pc-switch-status { width: 6; color: $text-faint; height: 1; text-align: right; margin-right: 1; }
        .pc-switch-row Switch, Switch {
            border: none; height: 1; min-height: 1; width: 6; min-width: 6; padding: 0; margin: 0; background: transparent;
        }
        .pc-switch-row Switch.-on, Switch.-on { color: $success; }
        .pc-switch-row Switch .switch--slider, Switch .switch--slider { color: $surface-highlight; background: $surface-shadow; }
        .pc-switch-row Switch.-on .switch--slider, Switch.-on .switch--slider { color: $success; background: $surface-shadow; }
        #pc-tone-row {
            width: 100%; height: auto; min-height: 4; overflow-x: auto; scrollbar-size-horizontal: 1;
            layout: horizontal; align-vertical: middle; padding: 0 0 1 0; margin-top: 1;
        }
        #pc-tone-row Button {
            min-width: 12; height: 3; padding: 0 1; margin: 0 1 0 0;
            background: $surface-alt; color: $text; text-style: bold;
            border: heavy; border-top: heavy $surface-highlight; border-left: heavy $surface-highlight;
            border-bottom: heavy $surface-shadow; border-right: heavy $surface-shadow;
            transition: background 80ms, border 80ms, offset 80ms;
        }
        #pc-tone-row Button:hover {
            background: $accent 25%; color: #ffffff;
            border-top: heavy #ffffff; border-left: heavy #ffffff;
            border-bottom: heavy $accent-highlight; border-right: heavy $accent-highlight;
            offset-y: -1;
        }
        #pc-tone-row Button.-active {
            offset-y: 1;
            border-top: heavy $accent-shadow; border-left: heavy $accent-shadow;
            border-bottom: heavy #ffffff; border-right: heavy #ffffff;
        }
        #pc-tone-row Button.-primary, #pc-tone-row Button.variant-primary {
            background: $accent 40%; color: #ffffff;
            border-top: heavy #ffffff; border-left: heavy #ffffff;
            border-bottom: heavy $accent-shadow; border-right: heavy $accent-shadow;
        }
        #pc-tone-row Button.-primary:hover, #pc-tone-row Button.variant-primary:hover {
            background: $accent 60%;
            border-bottom: heavy $accent-highlight; border-right: heavy $accent-highlight;
        }
        .pc-mem-row { height: 1; min-height: 1; padding: 0 1; border-bottom: solid $border; }
        .pc-mem-cat { width: 12; color: $accent; height: 1; }
        .pc-mem-content { width: 1fr; color: $text; height: 1; overflow: hidden; }
        .pc-mem-source { width: 7; color: $text-faint; height: 1; text-align: center; }
        .pc-mem-date { width: 11; color: $text-faint; height: 1; }
        .pc-mem-edit-btn { min-width: 3; width: 3; height: 1; padding: 0; background: transparent; color: $accent; border: none; }
        .pc-mem-edit-btn:hover { background: $accent 15%; }
        .pc-mem-del-btn { min-width: 3; width: 3; height: 1; padding: 0; background: transparent; color: $error; border: none; }
        .pc-mem-del-btn:hover { background: $error 15%; }
        .pc-empty-msg { color: $text-faint; padding: 1 1; height: auto; }
        .pc-perm-mode-row { height: 1; min-height: 1; padding: 1 0; }
        .pc-perm-mode-row Button { margin-right: 1; }
        .pc-privacy-note { color: $text-faint; padding: 1 0; height: auto; min-height: 1; margin-top: 1; }
        #pc-btns { height: auto; min-height: 4; padding: 0 1; border-top: solid $border; layout: horizontal; align-vertical: middle; }
        #pc-btns-left { width: auto; height: 3; layout: horizontal; align-vertical: middle; }
        #pc-btns-right { width: 1fr; height: 3; layout: horizontal; align-horizontal: right; align-vertical: middle; }
        #pc-btns-left Button, #pc-btns-right Button {
            min-width: 8; height: 3; padding: 0 1; margin: 0 1 0 0;
            background: $surface-alt; color: $text; text-style: bold;
            border: heavy; border-top: heavy $surface-highlight; border-left: heavy $surface-highlight;
            border-bottom: heavy $surface-shadow; border-right: heavy $surface-shadow;
            transition: background 80ms, border 80ms, offset 80ms;
        }
        #pc-btns-left Button:hover, #pc-btns-right Button:hover {
            background: $accent 25%; color: #ffffff;
            border-top: heavy #ffffff; border-left: heavy #ffffff;
            border-bottom: heavy $accent-highlight; border-right: heavy $accent-highlight;
            offset-y: -1;
        }
        #pc-btns-left Button.-active, #pc-btns-right Button.-active {
            offset-y: 1;
            border-top: heavy $accent-shadow; border-left: heavy $accent-shadow;
            border-bottom: heavy #ffffff; border-right: heavy #ffffff;
        }
        #pc-btns-left Button#pc-delete {
            color: $error;
            border: heavy; border-top: heavy #ffffff 30%; border-left: heavy #ffffff 30%;
            border-bottom: heavy $error 80%; border-right: heavy $error 80%;
        }
        #pc-btns-left Button#pc-delete:hover {
            background: $error 30%; color: #ffffff;
            border-top: heavy #ffffff; border-left: heavy #ffffff;
            border-bottom: heavy $error; border-right: heavy $error;
        }
        #pc-btns-right Button#pc-save {
            background: $accent 40%; color: #ffffff;
            border-top: heavy #ffffff; border-left: heavy #ffffff;
            border-bottom: heavy $accent-shadow; border-right: heavy $accent-shadow;
            margin-right: 1;
        }
        #pc-btns-right Button#pc-save:hover {
            background: $accent 60%;
            border-bottom: heavy $accent-highlight; border-right: heavy $accent-highlight;
        }
        #pc-btns-right Button#pc-cancel {
            margin-right: 0;
        }
        #pc-hint { color: $text-faint; height: 1; min-height: 1; padding: 0 1; margin: 0 0 1 0; }
        .pc-add-mem-bar {
            height: auto; min-height: 3; padding: 0; margin: 1 0;
            layout: horizontal; align-vertical: middle;
        }
        .pc-add-mem-bar Button {
            min-width: 8; height: 3; padding: 0 1; margin: 0 1 0 0;
            background: $surface-alt; color: $text; text-style: bold;
            border: heavy; border-top: heavy $surface-highlight; border-left: heavy $surface-highlight;
            border-bottom: heavy $surface-shadow; border-right: heavy $surface-shadow;
            transition: background 80ms, border 80ms, offset 80ms;
        }
        .pc-add-mem-bar Button:hover {
            background: $accent 25%; color: #ffffff;
            border-top: heavy #ffffff; border-left: heavy #ffffff;
            border-bottom: heavy $accent-highlight; border-right: heavy $accent-highlight;
            offset-y: -1;
        }
        .pc-add-mem-bar Button.-primary, .pc-add-mem-bar Button.variant-primary {
            background: $accent 40%; color: #ffffff;
            border-top: heavy #ffffff; border-left: heavy #ffffff;
            border-bottom: heavy $accent-shadow; border-right: heavy $accent-shadow;
        }
        #pc-mem-search-input {
            width: 100%; height: 3; min-height: 3; background: $surface;
            border: tall; border-top: tall $surface-shadow; border-left: tall $surface-shadow;
            border-bottom: tall $surface-highlight; border-right: tall $surface-highlight;
            color: $text; padding: 0 1; margin: 0 0 1 0;
        }
        #pc-mem-search-input:focus {
            border-top: tall $accent-shadow; border-left: tall $accent-shadow;
            border-bottom: tall $accent-highlight; border-right: tall $accent-highlight;
        }
        .pc-mode-card { height: auto; min-height: 2; padding: 0 1; border-bottom: solid $border; }
        .pc-mode-label { color: $text; height: 1; text-style: bold; }
        .pc-mode-desc { color: $text-faint; height: 1; }
        """

        BINDINGS = [
            Binding("escape", "cancel", "Cancel"),
            Binding("down", "scroll_down", "Scroll down"),
            Binding("up", "scroll_up", "Scroll up"),
            Binding("page_down", "page_down", "Page down"),
            Binding("page_up", "page_up", "Page up"),
        ]

        def __init__(self):
            super().__init__()
            self._nav_state = "personality"
            self._search_query = ""
            self._profiles = []
            self._active_name = ""
            self._selected_profile = 0
            self._perm_snapshot = []
            self._mem_v2_manager = None
            self._mem_legacy_data = {}
            self._mem_filter = "all"
            self._mem_v2_all = []
            self._mem_search_query = ""
            self._config = None
            self._coding_prefs = {}
            self._about_me = {}
            self._new_mem_text = ""
            self._editing_mem_id = None
            self._editing_mem_text = ""

        def _load_data(self):
            try:
                if ap is not None:
                    self._profiles = ap.profiles()
                    loaded = ap.load_profiles()
                    self._active_name = loaded.get("active", "")
                else:
                    self._profiles = []
                    self._active_name = ""
            except Exception:
                self._profiles = []
                self._active_name = ""
            try:
                if perm is not None:
                    self._perm_snapshot = perm.manager.snapshot()
                else:
                    self._perm_snapshot = []
            except Exception:
                self._perm_snapshot = []
            try:
                if memory is not None:
                    self._mem_legacy_data = memory.load()
                else:
                    self._mem_legacy_data = {}
            except Exception:
                self._mem_legacy_data = {}
            try:
                if memory_v2 is not None:
                    self._mem_v2_manager = memory_v2.get_manager()
                    self._mem_v2_all = self._mem_v2_manager.get_all_memories()
                else:
                    self._mem_v2_manager = None
                    self._mem_v2_all = []
            except Exception:
                self._mem_v2_manager = None
                self._mem_v2_all = []
            try:
                if cct_config is not None:
                    self._config = cct_config.get_config()
                else:
                    self._config = None
            except Exception:
                self._config = None
            try:
                self._about_me = _load_about_me()
            except Exception:
                self._about_me = {}
            self._coding_prefs = {"prefer_si": True, "show_steps": True, "show_derivations": False, "code_comments": True, "verbose_errors": False, "compact_output": False}

        def _current_profile(self):
            if self._profiles and 0 <= self._selected_profile < len(self._profiles):
                return self._profiles[self._selected_profile]
            return None

        def compose(self):
            # Extension guard: Personalize is an installable extension
            try:
                from .. import extensions as _ext
                if not _ext.is_enabled("personalize"):
                    with Vertical(id="pc-box"):
                        with Horizontal(id="pc-titlebar"):
                            yield Static("🎨  Personalize", id="pc-title")
                            yield Button("\u2715", id="pc-close", classes="cct-popup-close")
                        with Vertical(id="pc-disabled"):
                            yield Static("🎨 Personalize is currently disabled.", classes="pc-disabled-msg")
                            yield Static("Enable it in Extensions (main menu → Extensions) to customize AI.", classes="pc-disabled-hint")
                            with Horizontal(id="pc-disabled-actions"):
                                yield Button("Open Extensions", id="pc-open-ext", variant="primary")
                                yield Button("Close", id="pc-close2")
                    return
            except Exception:
                pass
            with Vertical(id="pc-box"):
                with Horizontal(id="pc-titlebar"):
                    yield Static("🎨  Personalize", id="pc-title")
                    yield Button("\u2715", id="pc-close", classes="cct-popup-close")
                with Horizontal(id="pc-body"):
                    with Vertical(id="pc-sidebar"):
                        with Horizontal(id="pc-search"):
                            yield Input(placeholder="\U0001f50d Search settings\u2026", id="pc-search-input")
                        yield ScrollableContainer(id="pc-sidebar-inner")
                    with ScrollableContainer(id="pc-content"):
                        pass
                with Horizontal(id="pc-btns"):
                    with Horizontal(id="pc-btns-left"):
                        yield Button("+ New", id="pc-new", classes="cct-btn cct-btn-sm")
                        yield Button("Duplicate", id="pc-dup", classes="cct-btn cct-btn-sm")
                        yield Button("Set Active", id="pc-active", classes="cct-btn cct-btn-sm")
                        yield Button("Delete", id="pc-delete", variant="error", classes="cct-btn cct-btn-sm")
                    with Horizontal(id="pc-btns-right"):
                        yield Button("Save", id="pc-save", variant="primary", classes="cct-btn cct-btn-sm")
                        yield Button("Cancel", id="pc-cancel", classes="cct-btn cct-btn-sm")
                yield Static("", id="pc-hint")

        def on_mount(self):
            self._load_data()
            self._rebuild_nav()
            self._render_section_content()

        def on_key(self, event):
            if event.key == "escape":
                self.action_cancel()
        def action_cancel(self):
            self.dismiss(None)
        def action_scroll_down(self):
            try:
                c = self.query_one("#pc-content", ScrollableContainer)
                if c.max_scroll_y > 0:
                    c.scroll_down(animate=False)
            except Exception:
                pass
        def action_scroll_up(self):
            try:
                self.query_one("#pc-content", ScrollableContainer).scroll_up(animate=False)
            except Exception:
                pass
        def action_page_down(self):
            try:
                self.query_one("#pc-content", ScrollableContainer).scroll_page_down(animate=False)
            except Exception:
                pass
        def action_page_up(self):
            try:
                self.query_one("#pc-content", ScrollableContainer).scroll_page_up(animate=False)
            except Exception:
                pass

        def _rebuild_nav(self):
            try:
                nav = self.query_one("#pc-sidebar-inner", ScrollableContainer)
                nav.remove_children()
            except Exception:
                return
            for section_name, items in _NAV_SECTIONS:
                sec_slug = section_name.lower().replace(" ", "-")
                try:
                    nav.mount(Static(section_name, id=f"pc-sec-{sec_slug}", classes="pc-nav-section"))
                except Exception:
                    pass
                for key, label in items:
                    btn = _NavButton(key, label)
                    if key == self._nav_state:
                        btn.add_class("pc-nav-btn-sel")
                    try:
                        nav.mount(btn)
                    except Exception:
                        pass
            try:
                self.query_one("#pc-hint", Static).update(_HINTS.get(self._nav_state, "Esc: close"))
            except Exception:
                pass
            if getattr(self, "_search_query", ""):
                self._filter_nav()

        def _filter_nav(self):
            query = (getattr(self, "_search_query", "") or "").strip().lower()
            try:
                nav = self.query_one("#pc-sidebar-inner", ScrollableContainer)
            except Exception:
                return
            for section_name, items in _NAV_SECTIONS:
                sec_slug = section_name.lower().replace(" ", "-")
                sec_match = False
                for key, label in items:
                    btn = _safe_query(nav, f"#pc-nav-{key}")
                    if btn is not None:
                        matched = not query or (query in key.lower() or query in label.lower())
                        btn.display = matched
                        if matched:
                            sec_match = True
                hdr = _safe_query(nav, f"#pc-sec-{sec_slug}")
                if hdr is not None:
                    hdr.display = sec_match or (not query)

        def _cache_current_state(self):
            # Persist whatever the user typed/selected in the currently active tab into memory
            try:
                prof = self._current_profile()
                if prof is not None:
                    # Identity fields
                    for fid, pkey in [("pc-name", "name"), ("pc-desc", "description"), ("pc-model", "model")]:
                        w = _safe_query(self, f"#{fid}", Input)
                        if w is not None:
                            prof[pkey] = w.value
                    for fid, pkey, lo, hi in [("pc-temp", "temperature", 0, 2), ("pc-topp", "top_p", 0, 1), ("pc-creativity", "creativity", 0, 1)]:
                        w = _safe_query(self, f"#{fid}", Input)
                        if w is not None:
                            s = w.value.strip()
                            if s:
                                try:
                                    prof[pkey] = max(lo, min(hi, float(s)))
                                except Exception:
                                    pass
                            else:
                                prof[pkey] = None
                    # Tone
                    if _safe_query(self, "#pc-tone-balanced") is not None:
                        t = self._tone_from_buttons()
                        if t:
                            prof["tone"] = t
                    # Response Style & Segments
                    if _safe_query(self, "#pc-reasoning-medium") is not None:
                        prof["reasoning"] = self._seg_value("pc-reasoning")
                    if _safe_query(self, "#pc-length-medium") is not None:
                        prof["response_length"] = self._seg_value("pc-length")
                    if _safe_query(self, "#pc-teaching-direct") is not None:
                        prof["teaching_style"] = self._seg_value("pc-teaching")
                    if _safe_query(self, "#pc-memory-auto") is not None:
                        prof["memory_pref"] = self._seg_value("pc-memory")
                    # custom instructions - check both Input and TextArea
                    ta = _safe_query(self, "#pc-additions-ta", TextArea) if _HAS_TEXTAREA else None
                    if ta is not None:
                        try:
                            prof["additions"] = ta.text
                        except Exception:
                            pass
                    else:
                        w = _safe_query(self, "#pc-additions", Input)
                        if w is not None:
                            prof["additions"] = w.value
                    # about_me fields
                    for fkey, _, _ in _ABOUT_ME_FIELDS:
                        w = _safe_query(self, f"#pc-about-{fkey}", Input)
                        if w is not None:
                            self._about_me[fkey] = w.value.strip()
                    # new memory TextArea
                    if _HAS_TEXTAREA:
                        ta2 = _safe_query(self, "#pc-mem-add-ta", TextArea)
                        if ta2 is not None:
                            try:
                                self._new_mem_text = ta2.text
                            except Exception:
                                pass
                    else:
                        w = _safe_query(self, "#pc-mem-add-input", Input)
                        if w is not None:
                            self._new_mem_text = w.value
                    w = _safe_query(self, "#pc-mem-edit-input", Input)
                    if w is not None:
                        self._editing_mem_text = w.value
            except Exception:
                pass

        def _set_nav(self, key):
            try:
                self._cache_current_state()
            except Exception:
                pass
            self._nav_state = key
            try:
                for btn in self.query(".pc-nav-btn"):
                    if isinstance(btn, _NavButton):
                        btn.set_class(btn.nav_key == key, "pc-nav-btn-sel")
                self.query_one("#pc-hint", Static).update(_HINTS.get(self._nav_state, "Esc: close"))
            except Exception:
                pass
            self._render_section_content()

        def _render_section_content(self):
            try:
                content = self.query_one("#pc-content", ScrollableContainer)
                content.remove_children()
            except Exception:
                return
            handler = getattr(self, f"_render_{self._nav_state}", None)
            if handler:
                try:
                    handler(content)
                except Exception as e:
                    try:
                        content.mount(Static(f"Error: {e}", classes="pc-empty-msg"))
                    except Exception:
                        pass
            else:
                try:
                    content.mount(Static("Section not available.", classes="pc-empty-msg"))
                except Exception:
                    pass

        # helpers to build rows without buggy `with` context
        def _field_row(self, container, label, widget):
            container.mount(Static(label, classes="pc-flbl"))
            container.mount(widget)

        def _seg_value(self, row_id):
            try:
                for key, _lbl in _SEG_BTNS[row_id]:
                    btn = self.query_one(f"#{row_id}-{key}", Button)
                    if btn.variant == "primary":
                        return key
            except Exception:
                pass
            return _SEG_BTNS[row_id][0][0] if _SEG_BTNS.get(row_id) else ""

        def _tone_from_buttons(self):
            for btone, _ in _TONE_BTNS:
                try:
                    btn = self.query_one(f"#pc-tone-{btone}", Button)
                    if btn.variant == "primary":
                        return btone
                except Exception:
                    continue
            return "balanced"

        def _unique_name(self, root):
            names = {p.get("name") for p in self._profiles}
            if root not in names:
                return root
            i = 2
            while f"{root} {i}" in names:
                i += 1
            return f"{root} {i}"

        # ── AI Personality ──
        def _render_personality(self, container):
            prof = self._current_profile()
            try:
                container.mount(Static("AI Personality", classes="pc-section-title"))
                container.mount(Static("Customize how CAT communicates.", classes="pc-fval"))
                container.mount(Static("Profile Identity", classes="pc-section-title"))
                for fid, flbl, ph in [("pc-name", "Name", "Profile name"), ("pc-desc", "Description", "e.g. chemistry student"), ("pc-model", "Preferred Model", "gpt-4o")]:
                    key = {"pc-name": "name", "pc-desc": "description", "pc-model": "model"}[fid]
                    val = prof.get(key, "") if prof else ""
                    container.mount(Static(flbl, classes="pc-flbl"))
                    container.mount(Input(value=val, id=fid, placeholder=ph))
                container.mount(Static("Model Parameters", classes="pc-section-title"))
                # single column to avoid Horizontal overflow on narrow
                for fid, flbl, ph, pkey in [("pc-temp", "Temperature (0-2)", "0.7", "temperature"), ("pc-topp", "Top P (0-1)", "0.9", "top_p"), ("pc-creativity", "Creativity (0-1)", "0.7", "creativity")]:
                    v = prof.get(pkey) if prof else None
                    s = "" if v is None else str(v)
                    container.mount(Static(flbl, classes="pc-flbl"))
                    container.mount(Input(value=s, id=fid, placeholder=ph))
            except Exception:
                pass

        def _render_response_style(self, container):
            prof = self._current_profile()
            try:
                container.mount(Static("Response Style", classes="pc-section-title"))
                mapping = {"pc-reasoning": ("reasoning", "medium"), "pc-length": ("response_length", "medium"), "pc-teaching": ("teaching_style", "direct")}
                labels = {"pc-reasoning": "Reasoning Depth", "pc-length": "Response Length", "pc-teaching": "Teaching Style"}
                for seg_id in ("pc-reasoning", "pc-length", "pc-teaching"):
                    pkey, default = mapping[seg_id]
                    cur = (prof.get(pkey) or default) if prof else default
                    container.mount(Static(labels[seg_id], classes="pc-flbl"))
                    btns = []
                    for key, label in _SEG_BTNS[seg_id]:
                        btn = Button(label, id=f"{seg_id}-{key}", classes="cct-btn cct-btn-sm")
                        if key == cur:
                            btn.variant = "primary"
                        btns.append(btn)
                    row = Horizontal(*btns, id=seg_id)
                    container.mount(row)
            except Exception:
                pass

        def _render_tone(self, container):
            prof = self._current_profile()
            tone = (prof.get("tone") or "balanced") if prof else "balanced"
            try:
                container.mount(Static("Tone", classes="pc-section-title"))
                container.mount(Static("Choose CAT's voice.", classes="pc-fval"))
                container.mount(Static("Communication Tone", classes="pc-flbl"))
                btns = []
                for btone, label in _TONE_BTNS:
                    btn = Button(label, id=f"pc-tone-{btone}", classes="cct-btn cct-btn-sm")
                    if btone == tone:
                        btn.variant = "primary"
                        btn.add_class("-primary")
                    btns.append(btn)
                row = HorizontalScroll(*btns, id="pc-tone-row")
                container.mount(row)
                if ap is not None:
                    directive = ap.TONES.get(tone, "")
                    if directive:
                        container.mount(Static("Active Directive", classes="pc-flbl", id="pc-tone-dir-lbl"))
                        container.mount(Static(directive, classes="pc-fval", id="pc-tone-dir-val"))
            except Exception:
                pass

        def _render_instructions(self, container):
            prof = self._current_profile()
            additions = (prof.get("additions") or "") if prof else ""
            try:
                container.mount(Static("Custom Instructions", classes="pc-section-title"))
                container.mount(Static("Rules applied to every conversation.", classes="pc-fval"))
                # Use TextArea if available for multi-line, else Input
                if _HAS_TEXTAREA:
                    ta = TextArea(text=additions, id="pc-additions-ta")
                    ta.styles.height = 8
                    ta.styles.min_height = 4
                    container.mount(ta)
                    container.mount(Static(f"Character count: {len(additions)}", classes="pc-char-count"))
                else:
                    container.mount(Input(value=additions, id="pc-additions", placeholder="e.g. always use SI units"))
                    container.mount(Static(f"Character count: {len(additions)}", classes="pc-char-count"))
            except Exception:
                pass

        def _render_about_me(self, container):
            try:
                container.mount(Static("About Me", classes="pc-section-title"))
                container.mount(Static("Optional — helps CAT understand you.", classes="pc-fval"))
                for field_key, field_label, placeholder in _ABOUT_ME_FIELDS:
                    val = self._about_me.get(field_key, "")
                    container.mount(Static(field_label, classes="pc-flbl"))
                    container.mount(Input(value=val, id=f"pc-about-{field_key}", placeholder=placeholder))
            except Exception:
                pass

        def _render_mem_overview(self, container):
            try:
                container.mount(Static("Memory Overview", classes="pc-section-title"))
                container.mount(Static("CAT can use saved memories to personalize.", classes="pc-fval"))
                v2_count = len(self._mem_v2_all)
                v2_cats = {}
                for m in self._mem_v2_all:
                    cat = m.category or "unknown"
                    v2_cats[cat] = v2_cats.get(cat, 0) + 1
                container.mount(Static(f"Long-term memories: {v2_count}", classes="pc-flbl"))
                if v2_cats:
                    parts = [f"{c.replace('_',' ').title()}: {n}" for c, n in sorted(v2_cats.items())]
                    container.mount(Static("  " + "  \u00b7  ".join(parts), classes="pc-fval"))
                if self._mem_legacy_data:
                    lt = len(self._mem_legacy_data.get("turns", []))
                    lf = len(self._mem_legacy_data.get("facts", []))
                    la = len(self._mem_legacy_data.get("activity", []))
                    ltop = len(self._mem_legacy_data.get("topics", {}))
                    container.mount(Static(f"Legacy: {lf} facts \u00b7 {lt} turns \u00b7 {la} activity \u00b7 {ltop} topics", classes="pc-fval"))
                    upd = self._mem_legacy_data.get("updated", 0)
                    if upd:
                        container.mount(Static(f"Last updated: {_fmt_ts(upd)}", classes="pc-fval"))
            except Exception:
                pass

        def _render_mem_saved(self, container):
            try:
                container.mount(Static("Saved Memories", classes="pc-section-title"))
                container.mount(Input(value=self._mem_search_query, id="pc-mem-search-input", placeholder="\U0001f50d Search memories\u2026"))
                btns = []
                for fkey, flabel in [("all","All"),("user","User"),("ai","AI"),("imported","Import")]:
                    btn = Button(flabel, id=f"pc-mem-filter-{fkey}", classes="cct-btn cct-btn-sm")
                    if fkey == self._mem_filter:
                        btn.variant = "primary"
                    btns.append(btn)
                container.mount(Horizontal(*btns, classes="pc-add-mem-bar"))
            except Exception:
                pass
            if self._editing_mem_id:
                try:
                    container.mount(Static("Edit Memory", classes="pc-section-title"))
                    container.mount(Input(value=self._editing_mem_text, id="pc-mem-edit-input", placeholder="Edit memory\u2026"))
                    container.mount(Horizontal(
                        Button("  Save  ", id="pc-mem-edit-save", variant="primary", classes="cct-btn cct-btn-sm"),
                        Button("  Cancel  ", id="pc-mem-edit-cancel", classes="cct-btn cct-btn-sm"),
                        classes="pc-add-mem-bar"
                    ))
                except Exception:
                    pass
            # List container — rows live here so search updates don't destroy the search Input
            list_box = Vertical(id="pc-mem-list")
            container.mount(list_box)
            try:
                self._refresh_mem_list_box(list_box)
            except Exception:
                pass

        def _refresh_mem_list_box(self, list_box=None):
            try:
                if list_box is None:
                    list_box = self.query_one("#pc-mem-list", Vertical)
                list_box.remove_children()
            except Exception:
                return
            memories_to_show = self._mem_v2_all
            if self._mem_filter != "all":
                memories_to_show = [m for m in memories_to_show if (getattr(m, "source", "user") or "user").lower() == self._mem_filter]
            if self._mem_search_query:
                q = self._mem_search_query.lower()
                memories_to_show = [m for m in memories_to_show if q in (m.content or "").lower() or q in (m.category or "").lower()]
            if not memories_to_show:
                try:
                    list_box.mount(Static("No saved memories. Add one from sidebar.", classes="pc-empty-msg"))
                except Exception:
                    pass
                return
            try:
                list_box.mount(Static(f"Memories ({len(memories_to_show)} of {len(self._mem_v2_all)})", classes="pc-section-title"))
            except Exception:
                pass
            for mem in memories_to_show[:25]:
                try:
                    list_box.mount(_MemoryRow(mem))
                except Exception:
                    pass

        def _render_mem_add(self, container):
            try:
                container.mount(Static("Add Memory", classes="pc-section-title"))
                container.mount(Static("What should CAT remember?", classes="pc-fval"))
                if _HAS_TEXTAREA:
                    ta = TextArea(text=self._new_mem_text, id="pc-mem-add-ta")
                    ta.styles.height = 6
                    ta.styles.min_height = 4
                    container.mount(ta)
                else:
                    container.mount(Input(value=self._new_mem_text, id="pc-mem-add-input", placeholder="Type a memory\u2026"))
                container.mount(Horizontal(
                    Button("  Add Memory  ", id="pc-mem-add-btn", variant="primary", classes="cct-btn cct-btn-sm"),
                    Button("  Cancel  ", id="pc-mem-add-cancel", classes="cct-btn cct-btn-sm"),
                    classes="pc-add-mem-bar"
                ))
            except Exception:
                pass

        def _render_context(self, container):
            try:
                container.mount(Static("AI Context", classes="pc-section-title"))
                container.mount(Static("What CAT can use while responding.", classes="pc-fval"))
                for key, label, default in _CONTEXT_SOURCES:
                    status_color = _hex("success") if default else _hex("text-faint")
                    mark = "\u2713" if default else "\u2717"
                    container.mount(Horizontal(
                        Static(f"[{status_color}]{mark}[/] {label}", classes="pc-switch-label"),
                        Switch(value=default, id=f"pc-ctx-{key}"),
                        classes="pc-switch-row"
                    ))
                container.mount(Static("Memory Injection", classes="pc-section-title"))
                prof = self._current_profile()
                mem_pref = (prof.get("memory_pref") or "auto") if prof else "auto"
                btns = []
                for key, label in _SEG_BTNS["pc-memory"]:
                    btn = Button(label, id=f"pc-memory-{key}", classes="cct-btn cct-btn-sm")
                    if key == mem_pref:
                        btn.variant = "primary"
                    btns.append(btn)
                container.mount(Horizontal(*btns, id="pc-memory"))
                turn_count = len(self._mem_legacy_data.get("turns", [])) if self._mem_legacy_data else 0
                container.mount(Static(f"{turn_count} recent turns in legacy memory", classes="pc-fval"))
                if self._mem_v2_manager:
                    try:
                        sess = self._mem_v2_manager.get_session_context(max_turns=20)
                        container.mount(Static(f"{len(sess)} turns in session memory", classes="pc-fval"))
                    except Exception:
                        pass
            except Exception:
                pass

        def _render_coding_prefs(self, container):
            try:
                container.mount(Static("Coding Preferences", classes="pc-section-title"))
                for key, label, default in _CODING_PREF_KEYS:
                    val = self._coding_prefs.get(key, default)
                    container.mount(Horizontal(
                        Static(label, classes="pc-switch-label"),
                        Static("ON" if val else "OFF", classes="pc-switch-status"),
                        Switch(value=val, id=f"pc-coding-{key}"),
                        classes="pc-switch-row"
                    ))
            except Exception:
                pass

        def _render_proactivity(self, container):
            try:
                container.mount(Static("Proactivity", classes="pc-section-title"))
                for key, label, default in _PROACTIVITY_KEYS:
                    container.mount(Horizontal(
                        Static(label, classes="pc-switch-label"),
                        Static("ON" if default else "OFF", classes="pc-switch-status"),
                        Switch(value=default, id=f"pc-proact-{key}"),
                        classes="pc-switch-row"
                    ))
            except Exception:
                pass

        def _render_permissions(self, container):
            current_mode = perm.manager.mode if perm is not None else "ask"
            mode_info = {
                "ask": ("\U0001f510", "Ask Every Time", "CAT asks before protected actions."),
                "restricted": ("\U0001f6e1", "Restricted", "Analyze and suggest, but blocked."),
                "full": ("\u26a1", "Full Access", "Work automatically within workspace."),
            }
            try:
                container.mount(Static("Security & Access", classes="pc-section-title"))
                container.mount(Static("Choose how CAT handles protected actions.", classes="pc-fval"))
                for mode_key in ("ask", "restricted", "full"):
                    icon, label, desc = mode_info[mode_key]
                    is_active = mode_key == current_mode
                    mark = "\u25cf" if is_active else "\u25cb"
                    container.mount(Horizontal(
                        Static(f"{icon} {mark} {label}", classes="pc-mode-label"),
                        classes="pc-mode-card"
                    ))
                    container.mount(Static(f"  {desc}", classes="pc-mode-desc"))
                btns = []
                for mode_key in ("ask", "restricted", "full"):
                    ml = perm.MODE_LABELS[mode_key] if perm and mode_key in perm.MODE_LABELS else mode_key.title()
                    btn = Button(ml, id=f"pc-mode-{mode_key}", classes="cct-btn cct-btn-sm")
                    if mode_key == current_mode:
                        btn.variant = "primary"
                    btns.append(btn)
                container.mount(Horizontal(*btns, classes="pc-perm-mode-row"))
                ws_path = self._config.workspace_directory if self._config and hasattr(self._config, 'workspace_directory') else "No workspace open"
                container.mount(Static("Workspace Scope", classes="pc-section-title"))
                container.mount(Static(f"  {ws_path}", classes="pc-fval"))
                container.mount(Static("  Scope: current CAT workspace — no OS-wide access.", classes="pc-fval"))
                container.mount(Static("Recent Access Decisions", classes="pc-section-title"))
                log = perm.manager.log[-5:] if perm and hasattr(perm.manager, "log") else []
                if not log:
                    container.mount(Static("  No recent decisions.", classes="pc-fval"))
                else:
                    for ts, key, action, decision in reversed(log):
                        try:
                            tstr = time.strftime("%H:%M", time.localtime(ts))
                            mark = "\u2713" if decision in ("allow_once","always_allow","allow") else "\u2717"
                            container.mount(Static(f"  {mark} {action or key} — {decision}  {tstr}", classes="pc-fval"))
                        except Exception:
                            pass
            except Exception:
                pass

        def _render_perm_list(self, container):
            try:
                container.mount(Static("Permissions", classes="pc-section-title"))
                container.mount(Static("Toggles overridden by access mode.", classes="pc-fval"))
                for key, label, is_on in self._perm_snapshot:
                    status_color = _hex("success") if is_on else _hex("error")
                    mark = "\u2713" if is_on else "\u2717"
                    container.mount(Horizontal(
                        Static(f"[{status_color}]{mark}[/] {label}", classes="pc-switch-label"),
                        Switch(value=is_on, id=f"pc-perm-{key}"),
                        classes="pc-switch-row"
                    ))
            except Exception:
                pass

        def _render_privacy(self, container):
            try:
                container.mount(Static("Privacy", classes="pc-section-title"))
                container.mount(Static("What CAT stores and where.", classes="pc-fval"))
                parts = []
                try:
                    parts.append(f"Profiles: {len(self._profiles)}")
                    parts.append(f"Memories: {len(self._mem_v2_all)}")
                    if self._mem_legacy_data:
                        parts.append(f"Legacy: {len(self._mem_legacy_data.get('facts',[]))} facts")
                except Exception:
                    pass
                if parts:
                    container.mount(Static("  " + "  \u00b7  ".join(parts), classes="pc-fval"))
                container.mount(Static("Data Locations", classes="pc-section-title"))
                container.mount(Static("  Profiles: ~/.cct_profiles.json", classes="pc-fval"))
                container.mount(Static("  About Me: ~/.cct_about_me.json", classes="pc-fval"))
                container.mount(Static("  Legacy: ~/.cct_memory.json", classes="pc-fval"))
                container.mount(Static("  V2: ~/.cct_memory_v2/", classes="pc-fval"))
                container.mount(Static("Privacy Notes", classes="pc-privacy-note"))
                container.mount(Static("  \u2022 API keys redacted before storage.", classes="pc-fval"))
                container.mount(Static("  \u2022 Data stays on your machine.", classes="pc-fval"))
                container.mount(Static("  \u2022 Session cleared on restart.", classes="pc-fval"))
            except Exception:
                pass

        def _save_form_to_profile(self):
            self._cache_current_state()
            prof = self._current_profile()
            if not prof:
                return False
            name = (prof.get("name") or "").strip()
            if not name:
                return False
            if ap is not None:
                try:
                    ap.add_profile(
                        name,
                        tone=prof.get("tone", "balanced"),
                        additions=prof.get("additions", ""),
                        temperature=prof.get("temperature"),
                        model=prof.get("model", ""),
                        description=prof.get("description", ""),
                        top_p=prof.get("top_p"),
                        creativity=prof.get("creativity"),
                        reasoning=prof.get("reasoning", "medium"),
                        response_length=prof.get("response_length", "medium"),
                        memory_pref=prof.get("memory_pref", "auto"),
                        teaching_style=prof.get("teaching_style", "direct"),
                    )
                except Exception:
                    pass
                self._profiles = ap.profiles()
            return True

        def _save_about_me(self):
            data = {}
            for field_key, _, _ in _ABOUT_ME_FIELDS:
                try:
                    w = _safe_query(self, f"#pc-about-{field_key}", Input)
                    if w is not None:
                        data[field_key] = w.value.strip()
                    elif field_key in getattr(self, "_about_me", {}):
                        data[field_key] = self._about_me[field_key]
                except Exception:
                    pass
            _save_about_me(data)
            self._about_me = data

        def _save_all(self):
            self._cache_current_state()
            try:
                self._save_form_to_profile()
            except Exception:
                pass
            try:
                self._save_about_me()
            except Exception:
                pass
            try:
                for key, _lbl, _ in self._perm_snapshot:
                    sw = _safe_query(self, f"#pc-perm-{key}", Switch)
                    if sw is not None and perm is not None:
                        perm.manager.set(key, sw.value)
            except Exception:
                pass
            try:
                for key, _lbl, _def in _CODING_PREF_KEYS:
                    sw = _safe_query(self, f"#pc-coding-{key}", Switch)
                    if sw is not None:
                        self._coding_prefs[key] = sw.value
            except Exception:
                pass

        def _save_and_close(self):
            self._save_all()
            try:
                self.app._system_note("\u2713 Changes saved")
            except Exception:
                pass
            self.dismiss(True)

        def _delete_selected_profile(self):
            prof = self._current_profile()
            if not prof or ap is None:
                return
            name = prof.get("name", "")
            try:
                self._save_form_to_profile()
            except Exception:
                pass
            try:
                ap.delete_profile(name)
                if self._active_name == name:
                    self._active_name = ""
                    ap.set_active("")
                self._profiles = ap.profiles()
                self._selected_profile = min(self._selected_profile, max(0, len(self._profiles) - 1))
                self._rebuild_nav()
                self._render_section_content()
            except Exception:
                pass

        def _duplicate_selected_profile(self):
            prof = self._current_profile()
            if not prof or ap is None:
                return
            try:
                self._save_form_to_profile()
            except Exception:
                pass
            name = self._unique_name(prof.get("name", "Profile") + " Copy")
            try:
                ap.add_profile(name, tone=prof.get("tone", "balanced"), additions=prof.get("additions", ""), temperature=prof.get("temperature"), model=prof.get("model", ""), description=prof.get("description", ""), top_p=prof.get("top_p"), creativity=prof.get("creativity"), reasoning=prof.get("reasoning", ""), response_length=prof.get("response_length", ""), memory_pref=prof.get("memory_pref", ""), teaching_style=prof.get("teaching_style", ""))
                self._profiles = ap.profiles()
                self._selected_profile = len(self._profiles) - 1
                self._rebuild_nav()
                self._render_section_content()
            except Exception:
                pass

        def _new_profile(self):
            if ap is None:
                return
            name = self._unique_name("New Profile")
            try:
                ap.add_profile(name, tone="balanced", additions="", temperature=None, model="")
                self._profiles = ap.profiles()
                self._selected_profile = len(self._profiles) - 1
                self._active_name = name
                try:
                    ap.set_active(name)
                except Exception:
                    pass
                self._rebuild_nav()
                self._render_section_content()
            except Exception:
                pass

        def _set_active_profile(self):
            prof = self._current_profile()
            if not prof or ap is None:
                return
            name = prof.get("name", "")
            try:
                ap.set_active(name)
                self._active_name = name
                self._rebuild_nav()
                try:
                    self.app._system_note(f"\u2726 '{name}' is now active.")
                except Exception:
                    pass
            except Exception:
                pass

        def _delete_memory(self, memory_id):
            if self._mem_v2_manager is None:
                return
            try:
                self._mem_v2_manager.delete_memory(memory_id)
                self._mem_v2_all = self._mem_v2_manager.get_all_memories()
                # preserve search Input focus — refresh list only if still in mem_saved
                if self._nav_state == "mem_saved":
                    try:
                        self._refresh_mem_list_box()
                        return
                    except Exception:
                        pass
                self._render_section_content()
            except Exception:
                pass

        def _add_memory(self):
            # support TextArea id as well
            if not self._new_mem_text.strip() and _HAS_TEXTAREA:
                try:
                    ta = _safe_query(self, "#pc-mem-add-ta", TextArea)
                    if ta is not None:
                        self._new_mem_text = ta.text
                except Exception:
                    pass
            if self._mem_v2_manager is None or not self._new_mem_text.strip():
                return
            try:
                self._mem_v2_manager.store_memory("custom", self._new_mem_text.strip(), importance=0.5, confidence=1.0, source="user")
                self._mem_v2_all = self._mem_v2_manager.get_all_memories()
                self._new_mem_text = ""
                self._nav_state = "mem_saved"
                self._rebuild_nav()
                self._render_section_content()
                try:
                    self.app._system_note("\u2713 Memory added")
                except Exception:
                    pass
            except Exception:
                pass

        def _confirm_mode_switch(self, mode, ok):
            if not ok:
                try:
                    self._render_section_content()
                except Exception:
                    pass
                return
            try:
                if perm is not None:
                    perm.manager.set_mode(mode)
                self._perm_snapshot = perm.manager.snapshot() if perm is not None else []
            except Exception:
                pass
            try:
                self._render_section_content()
            except Exception:
                pass

        def _edit_memory(self, memory_id):
            if self._mem_v2_manager is None:
                return
            try:
                self._mem_v2_manager.update_memory(memory_id, content=self._editing_mem_text)
                self._mem_v2_all = self._mem_v2_manager.get_all_memories()
                self._editing_mem_id = None
                self._editing_mem_text = ""
                self._render_section_content()
            except Exception:
                pass

        def on_button_pressed(self, event):
            eid = event.button.id or ""
            if eid in ("pc-open-ext", "pc-close2"):
                try:
                    self.dismiss(None)
                    from .extensions_panel import ExtensionsPanel
                    self.app.push_screen(ExtensionsPanel())
                except Exception:
                    self.dismiss(None)
                return
            if eid in ("pc-cancel", "pc-close"):
                self.action_cancel()
                return
            if eid == "pc-save":
                self._save_and_close()
                return
            if eid == "pc-new":
                self._new_profile()
                return
            if eid == "pc-dup":
                self._duplicate_selected_profile()
                return
            if eid == "pc-active":
                self._set_active_profile()
                return
            if eid == "pc-delete":
                self._delete_selected_profile()
                return
            if eid.startswith("pc-nav-"):
                key = eid[len("pc-nav-"):]
                self._set_nav(key)
                return
            if eid.startswith("pc-tone-"):
                tone = eid.split("-", 2)[2]
                try:
                    for btone, _ in _TONE_BTNS:
                        btn = self.query_one(f"#pc-tone-{btone}", Button)
                        is_active = (btone == tone)
                        btn.variant = "primary" if is_active else "default"
                        if is_active:
                            btn.add_class("-primary")
                        else:
                            btn.remove_class("-primary")
                    if ap is not None:
                        dir_val = self.query_one("#pc-tone-dir-val", Static)
                        if dir_val:
                            dir_val.update(ap.TONES.get(tone, ""))
                except Exception:
                    pass
                prof = self._current_profile()
                if prof:
                    prof["tone"] = tone
                return
            for seg_id in ("pc-reasoning", "pc-length", "pc-memory", "pc-teaching"):
                if eid.startswith(f"{seg_id}-"):
                    key = eid.split("-", 2)[2]
                    try:
                        for k, _label in _SEG_BTNS[seg_id]:
                            btn = self.query_one(f"#{seg_id}-{k}", Button)
                            btn.variant = "primary" if k == key else "default"
                    except Exception:
                        pass
                    prof = self._current_profile()
                    if prof:
                        prop_map = {
                            "pc-reasoning": "reasoning",
                            "pc-length": "response_length",
                            "pc-memory": "memory_pref",
                            "pc-teaching": "teaching_style"
                        }
                        if seg_id in prop_map:
                            prof[prop_map[seg_id]] = key
                    return
            if eid.startswith("pc-mode-"):
                mode = eid.split("-", 2)[2]
                if mode == "full" and perm is not None and perm.manager.mode != "full":
                    try:
                        from .header import FullAccessConfirmScreen
                        self.app.push_screen(FullAccessConfirmScreen(), lambda ok: self._confirm_mode_switch(mode, ok))
                    except Exception:
                        self._confirm_mode_switch(mode, True)
                    return
                self._confirm_mode_switch(mode, True)
                return
            if eid.startswith("pc-mem-del-"):
                mem_id = eid[len("pc-mem-del-"):]
                self._delete_memory(mem_id)
                return
            if eid.startswith("pc-mem-edit-"):
                mem_id = eid[len("pc-mem-edit-"):]
                self._editing_mem_id = mem_id
                for m in self._mem_v2_all:
                    if m.id == mem_id:
                        self._editing_mem_text = m.content or ""
                        break
                self._render_section_content()
                return
            if eid.startswith("pc-mem-filter-"):
                self._mem_filter = eid[len("pc-mem-filter-"):]
                try:
                    for fkey in ("all", "user", "ai", "imported"):
                        btn = self.query_one(f"#pc-mem-filter-{fkey}", Button)
                        is_active = (fkey == self._mem_filter)
                        btn.variant = "primary" if is_active else "default"
                        if is_active:
                            btn.add_class("-primary")
                        else:
                            btn.remove_class("-primary")
                except Exception:
                    pass
                try:
                    # Only refresh list, not entire content, to keep search focus
                    if self._nav_state == "mem_saved":
                        self._refresh_mem_list_box()
                    else:
                        self._render_section_content()
                except Exception:
                    try:
                        self._render_section_content()
                    except Exception:
                        pass
                return
            if eid == "pc-mem-edit-save":
                if self._editing_mem_id and self._editing_mem_text.strip():
                    self._edit_memory(self._editing_mem_id)
                else:
                    self._editing_mem_id = None
                    self._editing_mem_text = ""
                    self._render_section_content()
                return
            if eid == "pc-mem-edit-cancel":
                self._editing_mem_id = None
                self._editing_mem_text = ""
                self._render_section_content()
                return
            if eid == "pc-mem-add-btn":
                self._add_memory()
                return
            if eid == "pc-mem-add-cancel":
                self._new_mem_text = ""
                self._nav_state = "mem_saved"
                self._rebuild_nav()
                self._render_section_content()
                return

        def _on_textarea_changed(self, ta_id, text):
            if ta_id == "pc-additions-ta":
                self._additions_cache = text
                try:
                    count_el = self.query_one(".pc-char-count", Static)
                    count_el.update(f"Character count: {len(text)}")
                except Exception:
                    pass
            elif ta_id == "pc-mem-add-ta":
                self._new_mem_text = text

        def on_text_area_changed(self, event):
            try:
                ta = getattr(event, "text_area", None) or getattr(event, "widget", None)
                if ta is None:
                    return
                tid = getattr(ta, "id", "") or ""
                txt = getattr(ta, "text", "")
                self._on_textarea_changed(tid, txt)
            except Exception:
                pass

        def on_input_changed(self, event):
            if event.input.id == "pc-search-input":
                self._search_query = event.value
                try:
                    self._filter_nav()
                except Exception:
                    pass
            elif event.input.id == "pc-mem-search-input":
                self._mem_search_query = event.value
                try:
                    self._refresh_mem_list_box()
                except Exception:
                    try:
                        self._render_section_content()
                    except Exception:
                        pass
            elif event.input.id == "pc-mem-edit-input":
                self._editing_mem_text = event.value
            elif event.input.id == "pc-mem-add-input":
                self._new_mem_text = event.value
            elif event.input.id == "pc-additions":
                try:
                    count_el = self.query_one(".pc-char-count", Static)
                    count_el.update(f"Character count: {len(event.value)}")
                except Exception:
                    pass

        def on_input_submitted(self, event):
            if event.input.id == "pc-mem-search-input":
                self._mem_search_query = event.value
                try:
                    self._render_section_content()
                except Exception:
                    pass
            elif event.input.id == "pc-mem-edit-input":
                if self._editing_mem_id and event.value.strip():
                    self._editing_mem_text = event.value
                    self._edit_memory(self._editing_mem_id)
            elif event.input.id == "pc-mem-add-input":
                if event.value.strip():
                    self._add_memory()

        def on_switch_changed(self, event):
            sw_id = event.switch.id
            if sw_id.startswith("pc-perm-"):
                key = sw_id[len("pc-perm-"):]
                try:
                    if perm is not None:
                        perm.manager.set(key, event.value)
                except Exception:
                    pass
            elif sw_id.startswith("pc-coding-"):
                key = sw_id[len("pc-coding-"):]
                self._coding_prefs[key] = event.value
                try:
                    parent = event.switch.parent
                    if parent:
                        for child in parent.children:
                            if isinstance(child, Static) and "pc-switch-status" in (child.classes or []):
                                child.update("ON" if event.value else "OFF")
                except Exception:
                    pass
            elif sw_id.startswith("pc-ctx-"):
                key = sw_id[len("pc-ctx-"):]
                try:
                    parent = event.switch.parent
                    if parent:
                        for child in parent.children:
                            if isinstance(child, Static) and "pc-switch-label" in (child.classes or []):
                                status_color = _hex("success") if event.value else _hex("text-faint")
                                mark = "\u2713" if event.value else "\u2717"
                                lbl = next((l for k, l, _ in _CONTEXT_SOURCES if k == key), key)
                                child.update(f"[{status_color}]{mark}[/] {lbl}")
                except Exception:
                    pass
            elif sw_id.startswith("pc-proact-"):
                key = sw_id[len("pc-proact-"):]
                try:
                    parent = event.switch.parent
                    if parent:
                        for child in parent.children:
                            if isinstance(child, Static) and "pc-switch-status" in (child.classes or []):
                                child.update("ON" if event.value else "OFF")
                except Exception:
                    pass

else:
    PersonalizeCenter = None
