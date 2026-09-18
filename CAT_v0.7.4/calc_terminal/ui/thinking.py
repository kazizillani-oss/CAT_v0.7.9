"""
CCT UI — thinking.py: the "Advanced AI Response Animation System" (spec
item #25). Pure logic + formatting helpers only — no Textual dependency,
no widgets. composer.py's live status bar and conversation.py's
completion-summary line are the only two things that render what this
module computes; this file just decides *what* to show (stage label,
color, spinner frame, elapsed-time text) and never *how* to paint it.

Kept dependency-free on purpose: stage detection and timer formatting
are simple enough to unit test directly, and staying importable outside
Textual means the fallback CLI could reuse the same stage vocabulary
later without dragging in ui/ at all.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import re

# ---------------------------------------------------------- spinner styles
# Animation Style 1 / 2 / 3 from the spec.
DOT_FRAMES = ["\u25cf\u25cb\u25cb\u25cb\u25cb", "\u25cf\u25cf\u25cb\u25cb\u25cb",
              "\u25cf\u25cf\u25cf\u25cb\u25cb", "\u25cf\u25cf\u25cf\u25cf\u25cb",
              "\u25cf\u25cf\u25cf\u25cf\u25cf"]
BRAILLE_FRAMES = ["\u280b", "\u2819", "\u2839", "\u2838", "\u283c", "\u2834",
                   "\u2826", "\u2827", "\u2807", "\u280f"]
BLOCK_FRAMES = ["\u25a1\u25a1\u25a1\u25a1\u25a1\u25a1\u25a1\u25a1",
                 "\u25a0\u25a0\u25a1\u25a1\u25a1\u25a1\u25a1\u25a1",
                 "\u25a0\u25a0\u25a0\u25a0\u25a1\u25a1\u25a1\u25a1",
                 "\u25a0\u25a0\u25a0\u25a0\u25a0\u25a0\u25a1\u25a1",
                 "\u25a0\u25a0\u25a0\u25a0\u25a0\u25a0\u25a0\u25a0"]

STYLES = {"dots": DOT_FRAMES, "braille": BRAILLE_FRAMES, "blocks": BLOCK_FRAMES}


def spinner_frame(style, tick):
    """Loops continuously, per spec ('Loop until completion')."""
    frames = STYLES.get(style, BRAILLE_FRAMES)
    return frames[tick % len(frames)]


# --------------------------------------------------------------- stages --
# stage_key -> (display label, COLOR ROLE, spinner style).
#
# v0.7.9.0 LIGHT-MODE FIX: the second tuple slot used to be a hardcoded
# Tokyo-Night hex (#7aa2f7, #9ece6a, #e0af68...). Those pastels are
# unreadable on the light theme's white surfaces — several fall below
# 2:1 contrast. Colors are now semantic ROLES resolved through
# theme.role_hex() at CALL time (see stage_info), so dark keeps its
# exact Tokyo Night values and light automatically gets its darker,
# readable palette. `style` is just which of the three animation styles
# best fits that stage's feel.
STAGES = {
    "preparing":   ("Preparing",                 "blue",    "braille"),
    "thinking":    ("Thinking",                  "blue",    "braille"),
    "web":         ("Searching Web",             "cyan",    "dots"),
    "knowledge":   ("Searching Knowledge",       "cyan",    "dots"),
    "notebook":    ("Searching Notebook",        "cyan",    "dots"),
    "formula_db":  ("Searching Formula Database", "cyan",   "dots"),
    "quantum_lib": ("Searching Quantum Library",  "cyan",   "dots"),
    "analyzing":   ("Analyzing Question",        "blue",    "braille"),
    "calc":        ("Running Calculation",       "amber",   "blocks"),
    "simulation":  ("Running Simulation",        "purple",  "blocks"),
    "sim3d":       ("Rendering 3D Simulation",   "purple",  "blocks"),
    "graph":       ("Rendering Graph",           "purple",  "blocks"),
    "html":        ("Generating HTML",           "magenta", "braille"),
    "code":        ("Executing Code",            "magenta", "braille"),
    "building":    ("Building Response",         "blue",    "braille"),
    "formatting":  ("Formatting Result",         "blue",    "dots"),
    "finalizing":  ("Finalizing",                "blue",    "dots"),
    "debugging":   ("Debugging",                 "red",     "braille"),
    "installing":  ("Installing Package",        "amber",   "blocks"),
    "done":        ("Completed",                 "green",   "dots"),
    "error":       ("Error",                     "red",     "dots"),
}

# Role -> theme.color-role used by theme.role_hex(). "magenta" maps to
# the purple family in both palettes.
_ROLE_MAP = {
    "blue": "blue", "cyan": "cyan", "purple": "purple",
    "magenta": "purple", "amber": "amber", "green": "green",
    "red": "red", "gray": "gray",
}

DEFAULT_STAGE = "thinking"

# Elapsed-time fallback used once no keyword signal fires — keeps the
# indicator visibly alive on a plain, keyword-free question instead of
# freezing on one word the whole time it's waiting on the model.
_PRE_TOKEN_PROGRESSION = ["preparing", "thinking", "analyzing"]
_POST_TOKEN_PROGRESSION = ["building", "formatting", "finalizing"]

# "Smart Status Detection": prompt keywords -> stage. Order matters —
# first match wins, most specific first.
_KEYWORD_STAGES = [
    (("/research", "deep research"), "web"),
    (("/websearch", "web search", "search the web", "search online"), "web"),
    (("/install", "/packages", "install ", "pip install", "npm install", "setup "), "installing"),
    (("/debug", "debug this", "fix this bug", "error message", "traceback", "why is this failing"), "debugging"),
    (("/pipeline", "build me a", "build us an", "build a full"), "building"),
    (("/orbitals", "orbital", "quantum library", "electron cloud"), "quantum_lib"),
    (("/atomsim", "/sim3d", "3d simulation", "atomic simulation"), "sim3d"),
    (("/react", "reaction sim", "kinetics ode", "equilibrium ode", "simulate"), "simulation"),
    (("/graph", "plot ", "plot a", "graph of", "draw a graph"), "graph"),
    (("/codepad", "```", "write code", "generate code", "run python"), "code"),
    (("render html", "generate html", "html report"), "html"),
    (("/formulas", "formula database", "formula library"), "formula_db"),
    (("/history", "notebook", "past numericals"), "notebook"),
    (("/solve", "calculate", "compute", "solve for", "/calculator"), "calc"),
]


def detect_stage(prompt, elapsed, chunk_count=0):
    """Best-effort stage for a moment in time. `prompt` drives an early,
    strong keyword match (what's about to happen is real signal); once
    tokens are already streaming (`chunk_count > 0`) with nothing more
    specific detected, elapsed time alone walks the generic
    building -> formatting -> finalizing tail so the status bar keeps
    moving instead of sitting still for the rest of the response."""
    text = (prompt or "").lower()
    for keywords, stage in _KEYWORD_STAGES:
        if any(k in text for k in keywords):
            return stage

    progression = _POST_TOKEN_PROGRESSION if chunk_count else _PRE_TOKEN_PROGRESSION
    idx = min(int(elapsed // 1.4), len(progression) - 1)
    return progression[idx]


def stage_info(stage_key):
    """(label, hex_color, spinner_style) for a stage key, defaulting to
    'thinking' for anything unrecognized so callers never need a guard.

    The hex is resolved from the CURRENT theme at call time (dark =
    Tokyo Night values as before; light = its darker, readable
    palette), so a live /theme switch recolors every spinner/status on
    the next tick without any extra wiring."""
    label, role, style = STAGES.get(stage_key, STAGES[DEFAULT_STAGE])
    try:
        from .. import theme
        color = theme.role_hex(_ROLE_MAP.get(role, "blue"))
    except Exception:
        # Dependency-free fallbacks matching the DARK theme (the
        # classic terminal may import this module before theme setup).
        _DARK_FALLBACK = {"blue": "#7aa2f7", "cyan": "#7dcfff",
                          "purple": "#bb9af7", "magenta": "#bb9af7",
                          "amber": "#e0af68", "green": "#9ece6a",
                          "red": "#f7768e"}
        color = _DARK_FALLBACK.get(role, "#7aa2f7")
    return label, color, style


def format_timer(elapsed):
    """0.1 s / 1.2 s / 5.8 s under a minute; mm:ss beyond, matching the
    spec's live-timer examples exactly for the common case."""
    if elapsed < 0:
        elapsed = 0.0
    if elapsed < 60:
        return f"{elapsed:.1f} s"
    minutes, seconds = divmod(int(elapsed), 60)
    return f"{minutes}:{seconds:02d}"


# ---------------------------------------------------- idle chemistry icons
IDLE_ICONS = ["\u269b", "\U0001f9ea", "\U0001f9ec", "\u2601"]  # ⚛ 🧪 🧬 ☁


def idle_icon(tick):
    return IDLE_ICONS[tick % len(IDLE_ICONS)]


# --------------------------------------------------------- command usage --
_SLASH_CMD_RE = re.compile(r"(?<!\S)/[a-zA-Z][a-zA-Z\-]*")


def commands_used(*texts):
    """Slash commands mentioned across the given texts (prompt +
    response), de-duplicated and sorted, for the completion summary's
    'Commands Used' line."""
    found = set()
    for text in texts:
        if not text:
            continue
        found.update(m.group(0) for m in _SLASH_CMD_RE.finditer(text))
    return sorted(found)


# ------------------------------------------------------- completion block
def completion_summary_lines(*, provider=None, model=None, duration=None,
                              tokens=None, commands=None, extras=None):
    """Rich-markup lines for the 'Message Completion' block the spec
    describes (✓ Response Complete / Provider / Model / Time / Tokens /
    Commands Used / feature flags). Returns a list of markup strings —
    rendering them is the caller's job (conversation.py turns each into
    a Text.from_markup line under the finished bubble).

    v0.7.9.0: the ✓ color resolves from the CURRENT theme (was a
    hardcoded dark-palette green that washed out in light mode)."""
    try:
        from .. import theme
        ok_hex = theme.role_hex("green")
    except Exception:
        ok_hex = "#9ece6a"
    lines = [f"[{ok_hex}]\u2713 Response Complete[/]"]

    meta = []
    if provider:
        meta.append(f"Provider: {provider}")
    if model:
        meta.append(f"Model: {model}")
    if duration is not None:
        meta.append(f"Time: {format_timer(duration)}")
    if tokens:
        meta.append(f"Tokens: {tokens}")
    if meta:
        lines.append("[dim]" + "  \u00b7  ".join(meta) + "[/dim]")

    if commands:
        lines.append("[dim]Commands used: " + ", ".join(commands) + "[/dim]")

    if extras:
        lines.append("[dim]" + "  \u00b7  ".join(extras) + "[/dim]")

    return lines
