"""
CCT UI — command_palette.py (spec v0.7 project structure list + "Command
Highlighting" section: every command gets a category color, e.g. /solve
blue, /simulate purple, /gpu3d cyan, /build yellow, /plan green,
/websearch orange, /deepresearch magenta, /history gray, /help blue).

palette.py already implements the real engine this needs — fuzzy
subsequence matching (SuggestionEngine), live filtering as you type,
Up/Down navigation, Tab/Enter to accept (all driven from
composer.py's ComposerInput, unchanged here). Per the v0.7 brief ("Do
NOT rewrite working modules"), this file does not reimplement that;
it subclasses palette.CommandPalette and only changes how each row is
colored, then re-exports SuggestionEngine so callers can import either
name from this module going forward.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

from .palette import SuggestionEngine, TEXTUAL_AVAILABLE as _PALETTE_OK  # noqa: F401

TEXTUAL_AVAILABLE = True
try:
    from textual.containers import Vertical
    from textual.widgets import Static
except Exception:
    TEXTUAL_AVAILABLE = False

TEXTUAL_AVAILABLE = TEXTUAL_AVAILABLE and _PALETTE_OK

# Command (stripped of leading "/") -> category, used only to pick a
# color below. Anything not listed here falls back to "default".
# Categories map 1:1 to the spec's "Command Highlighting" table.
_CATEGORY_OF = {
    "solve": "solve", "calculator": "solve", "kinetics": "solve",
    "derive": "solve", "electrochemistry": "solve", "formulas": "solve",

    "sim3d": "simulate", "atomsim": "simulate", "orbitals": "simulate",
    "orbitalgrid": "simulate", "bonding": "simulate", "bloch": "simulate",
    "react": "simulate", "graph": "simulate",

    "gpu3d": "gpu3d",

    "build": "build", "codepad": "build", "edit": "build",

    "plan": "plan", "mode": "plan", "notebook": "plan", "agent": "plan", "ai": "plan",
    "research": "research", "debug": "debug",

    "install": "install", "packages": "install", "pipeline": "pipeline",
    "orchestrate": "pipeline", "devices": "devices",

    "websearch": "websearch",

    "history": "history", "memory": "history", "workspace": "history",

    "help": "help", "about": "help", "shortcuts": "help",
}

# Category -> semantic COLOR ROLE, resolved against the CURRENT theme at
# call time (theme.role_hex). v0.7.9.0 light-mode fix: these used to be
# hardcoded Tokyo-Night hexes whose pastels (#c0caf5 default!) were
# near-invisible on the light theme's white surfaces.
_CATEGORY_ROLE = {
    "solve": "blue",
    "simulate": "purple",
    "gpu3d": "cyan",
    "build": "amber",
    "plan": "green",
    "websearch": "amber",
    "deepresearch": "purple",
    "research": "cyan",
    "debug": "red",
    "install": "green",
    "pipeline": "cyan",
    "devices": "purple",
    "history": "gray",
    "help": "blue",
}


def category_color(cmd):
    """`cmd` includes the leading '/'. Public so composer.py can color
    a fully-typed command the same way the palette rows are colored.
    Resolves through theme.role_hex so every theme stays readable —
    v0.7.9.5: the old dependency-free Tokyo-Night fallback table is
    gone (it leaked dark pastels onto light surfaces when the theme
    module was briefly unimportable); the neutral gray fallback is
    readable on BOTH dark and light backgrounds."""
    role = _CATEGORY_ROLE.get(_CATEGORY_OF.get(cmd.lstrip("/"), ""), None)
    try:
        from .. import theme
        if role:
            return theme.role_hex(role)
        r, g, b = theme.TEXT
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return "#888888"


if TEXTUAL_AVAILABLE:
    from .palette import CommandPalette as _BaseCommandPalette

    class CommandPalette(_BaseCommandPalette):
        """Same behavior as palette.CommandPalette (fuzzy match, live
        filter, arrow nav) — only `_redraw` changes, to paint each
        command in its category color instead of the flat accent color.
        """

        def _redraw(self):
            from . import theme_css
            accent = theme_css.current_hex("accent")
            for child in list(self.children):
                child.remove()
            for i, (item, desc) in enumerate(self._matches):
                classes = "cct-cmd-row" + (" cct-cmd-row-selected" if i == self._selected else "")
                if item.startswith("/"):
                    color = category_color(item)
                    self.mount(Static(f"[{color} b]{item}[/]  [dim]{desc}[/dim]", classes=classes))
                else:
                    self.mount(Static(f"[{accent}]\u2726[/] [b]{item}[/]  [dim]{desc}[/dim]", classes=classes))

else:
    CommandPalette = None
