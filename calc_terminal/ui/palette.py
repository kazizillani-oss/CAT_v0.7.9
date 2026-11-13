"""
CCT UI — the "/" command palette. Filters calc_terminal/commands_data.py's
COMMANDS (the SAME list the fallback CLI's /help prints — one registry,
not a second hand-maintained copy), renders the dropdown, and posts
CommandExecuted when a command is chosen. Deciding what a command does
is calc_terminal/app.py's job, not this module's.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

from ..commands_data import COMMANDS

TEXTUAL_AVAILABLE = True
try:
    from textual.containers import Vertical
    from textual.widgets import Static
except Exception:
    TEXTUAL_AVAILABLE = False

PROMPT_SUGGESTIONS = [
    # Kinetics & Numerical Chemistry
    ("what is a first order reaction", "Quick conceptual answer · Kinetics"),
    ("half life of a first order reaction", "Numerical calculation · Kinetics"),
    ("explain the arrhenius equation simply", "Conceptual explanation · Physical Chem"),
    ("what's the difference between molarity and molality", "Concentration comparison · Solutions"),
    ("quick mole concept refresher", "Core principles & formulas · Class 11"),
    ("how to balance redox reactions", "Ion-electron oxidation-reduction method"),
    ("calculate molar mass of glucose", "Step-by-step formula C6H12O6 mass"),
    ("activation energy numerical", "Arrhenius rate constant equation"),
    ("zero order reaction half life", "Zero order rate formula & graph"),
    ("real-time voice transcription", "Speak coding instructions via microphone"),
    ("calculate gibbs free energy delta G", "Thermodynamics spontaneity calculation"),
    ("calculate ph of weak acid solution", "Equilibrium pH & dissociation constant"),
    # Physics, Solves, Derivations & Simulations
    ("solve ideal gas law with P=1, n=2, T=300", "Symbolic solve + full notebook"),
    ("derive the first order rate law step by step", "Full derivation, notebook format"),
    ("plot the arrhenius graph and export it", "Interactive plot + PNG export"),
    ("plot y = sin(x)*exp(-x/5) from 0 to 20", "Damped wave function plot"),
    ("simulate an iron atom in 3d", "Live 3D Bohr electron simulation"),
    ("show me the 2p orbital cloud", "Quantum orbital 3D probability density"),
    ("explain redox titration in detail", "Full reaction mechanism & calculations"),
    ("integrate x*exp(-x^2) dx from 0 to infinity", "Calculus definite integration"),
]


class SuggestionEngine:
    """Pure filtering logic — no widgets, so it's independently testable
    and reusable anywhere a command or prompt list needs fuzzy filtering."""

    @staticmethod
    def fuzzy_score(query, candidate):
        """Every character of `query` (lowercased) must appear in
        `candidate` in order. Returns a score (lower is better) or None
        if it doesn't match — a subsequence match is good enough for a
        few dozen commands without pulling in a dependency."""
        query = query.lower()
        candidate = candidate.lower()
        if not query:
            return 0
        if query in candidate:
            return candidate.index(query)
        pos = 0
        gaps = 0
        for ch in query:
            found = candidate.find(ch, pos)
            if found == -1:
                return None
            gaps += found - pos
            pos = found + 1
        return 100 + gaps

    _HIDDEN_IN_CHAT = {"/notebook", "/workspace", }

    @classmethod
    def match(cls, query, limit=30):
        query = (query or "").strip()
        scored = []
        is_cmd_query = query.startswith("/")
        search_term = query[1:].strip() if is_cmd_query else query

        # 1. Match slash commands
        for cmd, desc in COMMANDS:
            if cmd in cls._HIDDEN_IN_CHAT:
                continue
            if is_cmd_query:
                # Slash query: match against command name
                score = cls.fuzzy_score(search_term, cmd[1:])
            elif search_term:
                # Plain text: match against command name as fallback
                score = cls.fuzzy_score(search_term, cmd[1:])
                if score is not None:
                    score += 25
            else:
                score = None

            if score is not None:
                scored.append((score, cmd, desc))

        # 2. Match prompt suggestions
        for prompt_text, desc in PROMPT_SUGGESTIONS:
            if not search_term:
                # Top prompt suggestions after commands
                score = 35 if is_cmd_query else 10
            else:
                score = cls.fuzzy_score(search_term, prompt_text)
                if score is not None and is_cmd_query:
                    score += 20  # Prefer slash commands when user explicitly typed '/'
                if score is None:
                    words = search_term.lower().split()
                    if words and all(w in prompt_text.lower() or w in desc.lower() for w in words):
                        score = 50 if is_cmd_query else 40
            if score is not None:
                scored.append((score, prompt_text, desc))

        scored.sort(key=lambda t: t[0])
        return [(item, desc) for _, item, desc in scored[:limit]]


if TEXTUAL_AVAILABLE:
    from textual.containers import VerticalScroll

    PAGE_SIZE = 6

    class CommandPaletteRow(Static):
        ALLOW_SELECT = False
        can_focus = False

        def __init__(self, markup, index, palette_ref, **kwargs):
            super().__init__(markup, **kwargs)
            self.index = index
            self.palette_ref = palette_ref

        def on_enter(self, event):
            if self.palette_ref:
                self.palette_ref.select_index(self.index, scroll=False)

        def on_mouse_move(self, event):
            if self.palette_ref:
                self.palette_ref.select_index(self.index, scroll=False)

        def on_click(self, event):
            if self.palette_ref:
                self.palette_ref.select_index(self.index, scroll=False)
                if self.palette_ref.parent and hasattr(self.palette_ref.parent, "on_palette_selected"):
                    self.palette_ref.parent.on_palette_selected(self.palette_ref.selected_command())

    class CommandPalette(VerticalScroll):
        """The command and prompt suggestions palette — mounted inline inside
        the composer card. ComposerInput drives it: Up/Down/PageUp/PageDown
        move selection, Tab/Enter accept it, Esc closes it, and clicking
        any item selects it."""

        def __init__(self, id="cct-cmdpalette"):
            super().__init__(id=id)
            self._matches = []
            self._selected = 0

        def compose(self):
            yield from ()

        def is_open(self):
            return self.has_class("open")

        def open_for_query(self, query):
            self._matches = SuggestionEngine.match(query)
            if not self._matches:
                self.close()
                return
            self._selected = min(self._selected, len(self._matches) - 1)
            self._redraw()
            self.add_class('open')
            try:
                screen_h = getattr(getattr(self.app, 'size', None), 'height', 30)
                max_items = 5 if screen_h < 26 else (6 if screen_h < 34 else 8)
            except Exception:
                max_items = 6
            visible_rows = min(max_items, len(self._matches))
            self.styles.height = visible_rows
            self.styles.max_height = 8
            self.scroll_home(animate=False)
            if self.parent and hasattr(self.parent, '_on_palette_state_changed'):
                self.parent._on_palette_state_changed(True)
        def close(self):
            was_open = self.is_open()
            self._matches = []
            self._selected = 0
            self.remove_class("open")
            for child in list(self.children):
                child.remove()
            if was_open and self.parent and hasattr(self.parent, "_on_palette_state_changed"):
                self.parent._on_palette_state_changed(False)

        def _get_palette_width(self):
            palette_w = 0
            try:
                palette_w = self.size.width if (self.size and self.size.width > 0) else 0
            except Exception:
                palette_w = 0
            if not palette_w and self.parent and getattr(self.parent, "size", None):
                palette_w = max(0, self.parent.size.width - 4)
            if not palette_w and hasattr(self, "app") and getattr(self.app, "size", None):
                palette_w = max(0, self.app.size.width - 4)
            return palette_w or 80

        def _format_row_markup(self, i, palette_w, is_compact):
            from . import theme_css
            accent = theme_css.current_hex('accent')
            item, desc = self._matches[i]
            is_sel = (i == self._selected)
            marker = '▶ ' if is_sel else '  '
            color = self._get_item_color(item, accent)
            if item.startswith('/'):
                cmd_pad = f'{item} ' if is_compact else (f'{item:<14}' if len(item) < 14 else f'{item} ')
                avail_desc = max(16, palette_w - len(cmd_pad) - 4)
                disp_desc = (desc[:avail_desc - 1] + '…') if len(desc) > avail_desc else desc
                return f'{marker}[{color} b]{cmd_pad}[/][dim]{disp_desc}[/dim]'
            else:
                avail_item = max(10, int(palette_w * (0.35 if is_compact else 0.45)))
                disp_item = (item[:avail_item - 1] + '…') if len(item) > avail_item else item
                avail_desc = max(8, palette_w - len(disp_item) - 8)
                disp_desc = (desc[:avail_desc - 1] + '…') if len(desc) > avail_desc else desc
                return f'{marker}[{accent}]✦[/] [b]{disp_item}[/] [dim]{disp_desc}[/dim]'

        def _get_item_color(self, item, default_accent):
            return default_accent

        def select_index(self, index, scroll=True):
            if not self._matches or not (0 <= index < len(self._matches)):
                return
            if self._selected == index:
                return
            old_idx = self._selected
            self._selected = index
            children = [c for c in self.children if isinstance(c, CommandPaletteRow)]
            if len(children) == len(self._matches):
                palette_w = self._get_palette_width()
                is_compact = (palette_w < 55)
                if 0 <= old_idx < len(children):
                    children[old_idx].remove_class("cct-cmd-row-selected")
                    children[old_idx].update(self._format_row_markup(old_idx, palette_w, is_compact))
                if 0 <= index < len(children):
                    children[index].add_class("cct-cmd-row-selected")
                    children[index].update(self._format_row_markup(index, palette_w, is_compact))
            else:
                self._redraw()
            if scroll:
                self._scroll_selected_into_view()

        def on_mouse_move(self, event):
            try:
                target = getattr(event, "widget", None)
                for i, child in enumerate(self.children):
                    if child is target or child in getattr(target, "ancestors", []):
                        if self._selected != i:
                            self.select_index(i, scroll=False)
                        break
            except Exception:
                pass

        def on_click(self, event):
            try:
                target = getattr(event, "widget", None)
                for i, child in enumerate(self.children):
                    if child is target or child in getattr(target, "ancestors", []):
                        self.select_index(i, scroll=False)
                        if self.parent and hasattr(self.parent, "on_palette_selected"):
                            self.parent.on_palette_selected(self.selected_command())
                        break
            except Exception:
                pass

        def move(self, delta):
            if not self._matches:
                return
            new_idx = (self._selected + delta) % len(self._matches)
            self.select_index(new_idx, scroll=True)

        def move_page(self, direction):
            if not self._matches:
                return
            last = len(self._matches) - 1
            new_idx = max(0, min(last, self._selected + direction * PAGE_SIZE))
            self.select_index(new_idx, scroll=True)

        def selected_command(self):
            if not self._matches:
                return None
            return self._matches[self._selected][0]

        def _scroll_selected_into_view(self):
            try:
                rows = list(self.query(".cct-cmd-row"))
                if 0 <= self._selected < len(rows):
                    self.scroll_to_widget(rows[self._selected], animate=True)
            except Exception:
                pass

        def _redraw(self):
            for child in list(self.children):
                child.remove()
            palette_w = self._get_palette_width()
            is_compact = (palette_w < 55)
            for i in range(len(self._matches)):
                classes = 'cct-cmd-row' + (' cct-cmd-row-selected' if i == self._selected else '')
                markup = self._format_row_markup(i, palette_w, is_compact)
                self.mount(CommandPaletteRow(markup, i, self, classes=classes))
else:
    CommandPalette = None
