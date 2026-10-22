"""
Hidden easter eggs for Chemistry Calc Terminal.

None of these are listed in /help or /shortcuts on purpose — /shortcuts
just teases that they exist. They're triggered by typing an exact
phrase at the home prompt (checked in App.handle before the normal
free-text question pipeline), so they never interfere with real
chemistry questions.
"""

import random
import sys
import time

from . import theme
from . import sound
from . import keys
from . import identity
from . import aicore
from .atomsim import ELEMENTS
from .engine import WIDTH


# ------------------------------------------------------------- helpers --
def _panel(lines, title, color=theme.PURPLE, grad=None):
    print()
    print(theme.panel(lines, title=title, color=color, width=WIDTH, title_gradient=grad))
    print()


def _mark(app, key):
    app.eggs_found.add(key)


# --------------------------------------------------------------- eggs --
def _egg_42(app):
    _mark(app, "42")
    sound.play("success")
    _panel([
        theme.gradient("THE ANSWER", theme.CYAN, theme.PURPLE, bold=True),
        "",
        theme.text("42 is the Answer to the Ultimate Question of Life,"),
        theme.text("the Universe, and Everything."),
        "",
        theme.dim("It also happens to be the atomic number of ") + theme.orange("Molybdenum (Mo)", bold=True) + theme.dim("."),
        theme.dim("Deep Thought would probably have appreciated a transition metal."),
    ], "\u2728 easter egg", grad=(theme.CYAN, theme.PURPLE))


def _egg_gold(app):
    _mark(app, "gold")
    sound.play("success")
    bar = theme.gradient("\u2588" * 30, (201, 176, 55), (255, 223, 128), (201, 176, 55), bold=True)
    _panel([
        theme.orange("Au \u00b7 79 \u00b7 196.97 u", bold=True),
        bar,
        "",
        theme.dim("Gold is so unreactive it's found in nature as the pure metal \u2014"),
        theme.dim("which is exactly why alchemists never managed to make it from lead."),
    ], "\u2728 you struck gold", grad=((201, 176, 55), (255, 223, 128)))


def _egg_avogadro(app):
    _mark(app, "avogadro")
    sound.play("success")
    _panel([
        theme.cyan("6.022 \u00d7 10\u00b2\u00b3", bold=True) + theme.dim("  \u2014 one mole, give or take."),
        "",
        theme.dim("That's roughly how many grains of sand would cover the entire"),
        theme.dim("Earth in a layer several metres deep. Chemistry deals in numbers"),
        theme.dim("so big they stop being numbers and start being vibes."),
    ], "\u2728 mole moment", grad=(theme.CYAN, theme.GREEN))


def _egg_coffee(app):
    _mark(app, "coffee")
    sound.play("notify")
    cup = [
        "      ( (",
        "       ) )",
        "    .______.",
        "    |      |]",
        "    \\      /",
        "     `----'",
    ]
    lines = [theme.dim(l) for l in cup]
    lines.append("")
    lines.append(theme.text("Caffeine", bold=True) + theme.dim("  \u2014  C\u2088H\u2081\u2080N\u2084O\u2082"))
    lines.append(theme.dim("A methylxanthine alkaloid, and the reason this terminal exists."))
    _panel(lines, "\u2728 brewed", grad=(theme.ORANGE, theme.PURPLE))


def _egg_sandwich(app):
    _mark(app, "sandwich")
    sound.play("success")
    _panel([
        theme.green("Sandwich synthesized.", bold=True),
        theme.dim("Yield: 100%  \u00b7  Byproducts: crumbs  \u00b7  Reaction time: instantaneous"),
        "",
        theme.dim("(root privileges confirmed \u2014 you asked nicely, so it worked this time)"),
    ], "\u2728 sudo", grad=(theme.GREEN, theme.CYAN))


def _egg_who(app):
    _mark(app, "who")
    sound.play("notify")
    banner = theme.gradient("CHEMISTRY CALC TERMINAL", theme.CYAN, theme.PURPLE, theme.CYAN, bold=True)
    try:
        config = aicore.load_config()
    except Exception:
        config = None
    _panel([
        banner,
        "",
        theme.text(f"Created by {identity.CREATOR_NAME}, {identity.CREATOR_ROLE}."),
        theme.dim(f"{identity.DEVELOPMENT_NOTE.capitalize()}. Built to look like a dev CLI,"),
        theme.dim("but every calculation underneath is real \u2014 the fractions, the"),
        theme.dim("derivations, the atoms, all of it."),
        theme.faint(f"Stack: {identity.tech_stack_sentence(config)}."),
        "",
        theme.faint(f"You've now found {len(app.eggs_found) + 1} hidden thing(s). Keep looking."),
    ], "\u2728 credits", grad=(theme.CYAN, theme.PURPLE))


def _egg_model(app):
    _mark(app, "model")
    sound.play("notify")
    try:
        config = aicore.load_config()
    except Exception:
        config = None
    _panel([
        theme.gradient("ACTIVE MODEL", theme.CYAN, theme.PURPLE, bold=True),
        "",
        theme.text(identity.answer_model(config)),
    ], "\u2728 model", grad=(theme.CYAN, theme.PURPLE))


def _egg_god(app):
    _mark(app, "god")
    sound.play("sim_start")
    _panel([
        theme.gradient("\u2588\u2588 GOD MODE \u2588\u2588", theme.RED, theme.ORANGE, bold=True),
        "",
        theme.dim("Unlimited moles granted. Entropy locally reversed. Please use"),
        theme.dim("responsibly \u2014 the second law of thermodynamics is watching."),
        "",
        theme.faint("(no actual cheats here \u2014 just a nod to every '90s game you know)"),
    ], "\u2728 iddqd", grad=(theme.RED, theme.ORANGE))


def _matrix_rain(app):
    """A Matrix-style falling-code effect, except the "code" is real
    element symbols — press q to stop early."""
    _mark(app, "matrix")
    sound.play("sim_start")
    width, height = WIDTH, 20
    symbols = [v[0] for v in ELEMENTS.values()]
    cols = [random.randint(-height, 0) for _ in range(width // 2)]
    speeds = [random.choice([1, 1, 2]) for _ in cols]
    theme.hide_cursor()
    try:
        for frame in range(90):
            grid = [[" "] * width for _ in range(height)]
            for ci, c in enumerate(cols):
                x = ci * 2
                head = c
                for trail in range(10):
                    y = head - trail
                    if 0 <= y < height and 0 <= x < width:
                        sym = random.choice(symbols)
                        if trail == 0:
                            grid[y][x] = theme.fg(sym[0], (210, 255, 210), bold=True)
                        else:
                            fade = max(0, 1 - trail / 10)
                            col = theme.lerp((10, 40, 15), (80, 220, 110), fade)
                            grid[y][x] = theme.fg(sym[0], col)
                cols[ci] += speeds[ci % len(speeds)]
                if cols[ci] - 10 > height:
                    cols[ci] = random.randint(-height, -1)
            theme.cursor_home()
            out = "\n".join("".join(row) for row in grid)
            sys.stdout.write(out + "\n")
            sys.stdout.write(theme.faint("  press q to stop\u2026") + "\n")
            sys.stdout.flush()
            if keys.key_available():
                k = keys.read_key()
                if k and k.lower() == "q":
                    break
            time.sleep(0.05)
    finally:
        theme.show_cursor()
    print()
    print(theme.gradient("  There is no calculator. Only chemistry.", theme.GREEN, theme.CYAN, bold=True))
    print()


def _egg_3d(app):
    _mark(app, "3d")
    sound.play("notify")
    art = [
        "      +---------+",
        "     /|        /|",
        "    / |       / |",
        "   +--+------+ /",
        "   |  |      | +",
        "   |  +------+-|",
        "   | /       |/",
        "   +---------+",
    ]
    lines = [theme.gradient(l, theme.CYAN, theme.PURPLE) for l in art]
    lines.insert(0, "")
    lines.append("")
    lines.append(theme.dim("  A glimpse into the third dimension..."))
    _panel(lines, "\u2728 3d art", grad=(theme.CYAN, theme.PURPLE))


EGGS = {
    "42": _egg_42,
    "gold": _egg_gold,
    "au": _egg_gold,
    "avogadro": _egg_avogadro,
    "avogadro's number": _egg_avogadro,
    "avogadro number": _egg_avogadro,
    "coffee": _egg_coffee,
    "caffeine": _egg_coffee,
    "sudo make me a sandwich": _egg_sandwich,
    "make me a sandwich": _egg_sandwich,
    "who made this": _egg_who,
    "who made you": _egg_who,
    "who are you": _egg_who,
    "what are you": _egg_who,
    "who built this": _egg_who,
    "who built cct": _egg_who,
    "who built you": _egg_who,
    "who created this": _egg_who,
    "who created you": _egg_who,
    "who created cct": _egg_who,
    "who developed this": _egg_who,
    "who developed you": _egg_who,
    "who developed cct": _egg_who,
    "who owns this project": _egg_who,
    "who owns cct": _egg_who,
    "what is cct": _egg_who,
    "iddqd": _egg_god,
    "konami": _egg_god,
    "/matrix": _matrix_rain,
    "matrix": _matrix_rain,
    "3d": _egg_3d,
    "show me something 3d": _egg_3d,
    "cube": _egg_3d,
}


def check(low, app):
    """Return True if `low` (already lowercased/stripped) matched a
    hidden easter egg and was handled."""
    fn = EGGS.get(low)
    if fn is not None:
        fn(app)
        return True
    # Exact-match dict above misses natural phrasing variants ("who is
    # the developer of cct?", "who owns this project?" with punctuation,
    # etc.) — fall back to identity.py's looser matcher so those still
    # land on the same, correct answer instead of falling through to the
    # AI (or a "couldn't match that" error).
    kind = identity.classify_identity_question(low)
    if kind == "creator" or kind == "what":
        _egg_who(app)
        return True
    if kind == "model":
        _egg_model(app)
        return True
    return False
