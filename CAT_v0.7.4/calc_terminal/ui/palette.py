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
    ("second order kinetics rate constant", "Integrated rate equation derivation"),
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

    _HIDDEN_IN_CHAT = {"/notebook", "/workspace", "/kinetics", "/orbitals"}

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
            self.add_class("open")
            # Dynamically size between 3 and 7 rows
            self.styles.height = min(7, max(3, len(self._matches)))
            self.scroll_home(animate=False)
            if self.parent and hasattr(self.parent, "_on_palette_state_changed"):
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

        def on_click(self, event):
            try:
                for i, child in enumerate(self.children):
                    if child == event.widget or child in getattr(event.widget, "ancestors", []):
                        self._selected = i
                        self._redraw()
                        if self.parent and hasattr(self.parent, "on_palette_selected"):
                            self.parent.on_palette_selected(self.selected_command())
                        break
            except Exception:
                pass

        def move(self, delta):
            if not self._matches:
                return
            self._selected = (self._selected + delta) % len(self._matches)
            self._redraw()
            self._scroll_selected_into_view()

        def move_page(self, direction):
            if not self._matches:
                return
            last = len(self._matches) - 1
            self._selected = max(0, min(last, self._selected + direction * PAGE_SIZE))
            self._redraw()
            self._scroll_selected_into_view()

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
            from . import theme_css
            accent = theme_css.current_hex("accent")
            for child in list(self.children):
                child.remove()
            for i, (item, desc) in enumerate(self._matches):
                classes = "cct-cmd-row" + (" cct-cmd-row-selected" if i == self._selected else "")
                if item.startswith("/"):
                    self.mount(Static(f"[{accent} b]{item}[/]  [dim]{desc}[/dim]", classes=classes))
                else:
                    self.mount(Static(f"[{accent}]\u2726[/] {item}  [dim]{desc}[/dim]", classes=classes))

else:
    CommandPalette = None
