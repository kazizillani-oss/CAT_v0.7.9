"""
Showcase ASCII block-art library for Chemistry Calc Terminal.

A curated gallery of big block-art pieces built from `█ ▓ ▒ ▀ ▄ ╗ ╔ ║ ╣ ╠` and
friends — chemistry-themed (flask, atom, molecule, benzene ring, DNA), mascots
(cat, robot, owl, penguin), decorative dividers, abstract 3D shapes, and
wordmark banners. Every piece renders through `theme.gradient` + `theme.vpad`,
so it reuses the existing 24-bit color stack — no new rendering code.

Used by:
  * the rotating boot banner (a different piece bounces in each launch)
  * the `/art` browse command (walk the whole gallery)
  * easter eggs (themed reveals with a confetti burst)
"""

if __name__ == '__main__':
    print("This is a library file and is not meant to be run directly.")
    print("Please run 'python main.py' or 'python model.py' from the project root directory.")
    import sys
    sys.exit(1)

import random

from . import theme


# ============================================================ the gallery ==
# Each value is a list of plain (uncolored) art lines. They're colored at
# render time by `render()`. Keep widths moderate (<= ~46 cols) so a centered
# piece fits comfortably inside the app's panel width on an 80-col terminal.
GALLERY = {
    # ------------------------------------------------ chemistry ----------
    "flask": [
        "       _",
        "      / \\",
        "     |   |",
        "     |   |",
        "    /     \\",
        "   /       \\",
        "  /  ▓▓▓▓▓  \\",
        " /  ▓▓▓▓▓▓▓  \\",
        "/▓▓▓▓▓▓▓▓▓▓▓▓▓\\",
        "===============\\",
        "  \\___________/",
    ],
    "atom": [
        "        ___",
        "      ,'   `.",
        "     /  (o)  \\      .----.",
        "    |  .---.  |    /   o  \\",
        "     \\  \\|/  /----(   o    )",
        "      `-.|-.'      \\   o  /",
        "   .----'|`----.    `----'",
        "  /   o  |  o   \\      |",
        " (   o   |   o   )    (o)",
        "  \\   o  |  o   /      |",
        "   '----'|`----'",
        "         |",
    ],
    "molecule": [
        "        ___",
        "       /   \\",
        "      |  H  |",
        "       \\___/",
        "         |",
        "    _____|_____",
        "   /           \\",
        "  |      O      |",
        "   \\___________/",
        "    |       |",
        "  __|__   __|__",
        " /     \\ /     \\",
        "|  H    |    H  |",
        " \\_____/ \\_____/",
    ],
    "benzene": [
        "        _____",
        "      ,'     `.",
        "     /    .    \\",
        "    |   .   .   |",
        "     \\    .    /",
        "      `._____,'",
        "       /     \\",
        "      /  C₆H₆ \\",
        "     /_________\\",
    ],
    "testtube": [
        "   ╔═══╗",
        "   ║   ║",
        "   ║   ║",
        "   ║   ║",
        "   ║▓▓▓║",
        "   ║▓▓▓║",
        "   ║▓▓▓║",
        "   ║▓▓▓║",
        "   ╚═╦═╝",
        "     ║",
        "     ▼",
    ],
    "crystal": [
        "       /\\",
        "      /  \\",
        "     /____\\",
        "    /\\    /\\",
        "   /  \\  /  \\",
        "  /____\\/____\\",
        "  \\    /\\    /",
        "   \\  /  \\  /",
        "    \\/____\\/",
        "      ||",
        "      ||",
    ],
    "dna": [
        "   \\        /",
        "    \\      /",
        "     |    |",
        "    /      \\",
        "   /        \\",
        "   |        |",
        "    \\      /",
        "     |    |",
        "    /      \\",
        "   /        \\",
        "   |        |",
        "    \\      /",
        "     |    |",
    ],
    "beaker": [
        "    _______",
        "   |       |",
        "   |       |",
        "   |       |",
        "   |\\     /|",
        "   | \\   / |",
        "   |  \\ /  |",
        "   |   V   |",
        "   |_______|",
    ],

    # -------------------------------------------------- mascots ----------
    "cat_chemist": [
        "    /\\_/\\",
        "   ( o.o )  __",
        "    > ^ <  /  \\",
        "   /     \\ |██|",
        "  /       \\ \\__/",
        "  |  C C C |",
        "  |   H    |",
        "  \\___O____/",
    ],
    "robot_chemist": [
        "    .-------.",
        "   |  o   o  |",
        "   |  [___]  |",
        "   `-._____.-'",
        "    /|     |\\",
        "   / | ▓▓▓ | \\",
        "  |  | ▓▓▓ |  |",
        "  |  |_____|  |",
        "  |   _| |_   |",
        "  '__|_____|__'",
    ],
    "owl": [
        "     ___",
        "    /o o\\",
        "   (  v  )",
        "   /|   |\\",
        "  / |___| \\",
        " /  |   |  \\",
        "|   |___|   |",
        "|___|   |___|",
        "    |   |",
        "    ▢   ▢",
    ],
    "penguin": [
        "      ___",
        "     /   \\",
        "    | > < |",
        "    | \\_/ |",
        "    /_____\\",
        "   /\\     /\\",
        "  /  \\   /  \\",
        " /----\\ /----\\",
        "/      V      \\",
        "|             |",
        "\\_____________/",
    ],

    # ----------------------------------------------- wordmarks ----------
    "CAT": [
        " ██████╗  ██████╗██╗     ",
        "██╔════╝ ██╔════╝██║     ",
        "██║  ██╗ ██║     ██║     ",
        "██║  ╚██╗██║     ██║     ",
        "╚██████╔╝╚██████╗███████╗",
        " ╚═════╝  ╚═════╝╚══════╝",
    ],
    "CHEM": [
        "██╗  ██╗███████╗███╗   ███╗",
        "██║  ██║██╔════╝████╗ ████║",
        "███████║█████╗  ██╔████╔██║",
        "██╔══██║██╔══╝  ██║╚██╔╝██║",
        "██║  ██║███████╗██║ ╚═╝ ██║",
        "╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝",
    ],

    # ----------------------------------------------- decorative ----------
    "divider_ornate": [
        "✦━━━━━━━━━━━ ◆ ━━━━━━━━━━━✦",
        "         ╭─────────╮          ",
        "         │ ⚗  CAT  ⚗ │          ",
        "         ╰─────────╯          ",
        "✦━━━━━━━━━━━ ◆ ━━━━━━━━━━━✦",
    ],
    "stars_burst": [
        "       ✦       *       ✧",
        "   *       ✦       *",
        "         ╭───────╮",
        "    ✧    │  ✦ ✦  │    ✧",
        "         ╰───────╯",
        "    *        ✦        *",
        "       ✧       *       ✦",
    ],
    "wave": [
        "▁▂▃▄▅▆▇█▇▆▅▄▃▂▁▂▃▄▅▆▇█▇▆▅▄▃▂▁",
        "▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔",
        " ~ chemistry is just applied waves ~",
    ],

    # -------------------------------------------------- abstract ----------
    "cube_3d": [
        "  +---------+",
        " /|        /|",
        "/ |       / |",
        "+--+------+  |",
        "|  |      |  +",
        "|  +------+--+",
        "| /       | /",
        "|/        |/",
        "+---------+",
    ],
    "pyramid": [
        "           /\\",
        "          /  \\",
        "         /    \\",
        "        /      \\",
        "       /        \\",
        "      /          \\",
        "     /            \\",
        "    /______________\\",
    ],
    "spiral": [
        "        ╭─────╮",
        "       ╭╯     ╰╮",
        "      ╭╯  ╭─╮  ╰╮",
        "      │  ╭╯ ╰╮  │",
        "      │  ╰─╮  │  │",
        "      ╰╮   ╰─╯ ╭╯",
        "       ╰╮     ╭╯",
        "         ╰─────╯",
    ],
    "dragon": [
        "              /\\___/\\",
        "             ( o   o )",
        "             (  =^=  )",
        "              )     (",
        "         ____/       \\____",
        "        /                  \\",
        "    ====/  ◣            ◢  \\====",
        "        \\__________________/",
        "           |  |  |  |",
        "           ▤  ▤  ▤  ▤",
    ],
    "rocket": [
        "            /\\",
        "           /  \\",
        "          |    |",
        "          |    |",
        "          |____|",
        "         /| CAT|\\",
        "        / |____| \\",
        "       /  |    |  \\",
        "      |   |====|   |",
        "       \\  |    |  /",
        "        \\_/____\\_/",
        "          | || |",
        "          * ** *",
    ],
    "heart_molecule": [
        "   ◢◣   ◢◣",
        "  ◢██◣ ◢██◣",
        "  █████████",
        "   ███████",
        "    █████",
        "     ███",
        "      █",
    ],
    "wizard": [
        "        .-.",
        "       /   \\",
        "      |○ ○ ○|",
        "      |  ▽  |",
        "       \\___/",
        "       _|_|_",
        "      /     \\",
        "     /  ✦ ✦  \\",
        "    |  ▓▓▓▓▓  |",
        "     \\_______/",
        "        | |",
        "       _| |_",
    ],

    # ------------------------------------------------ chemistry (v0.5.6) --
    "bunsen_burner": [
        "        )  (",
        "       (    )",
        "      ) \\  / (",
        "     (   )(   )",
        "      \\_(  )_/",
        "        |  |",
        "     ___|  |___",
        "    /           \\",
        "   |   ▓▓▓▓▓▓▓   |",
        "   |_____________|",
        "        |  |",
        "     ___|  |___",
        "    |___________|",
    ],
    "erlenmeyer": [
        "      ___",
        "     |   |",
        "     |   |",
        "      \\ /",
        "      | |",
        "     /   \\",
        "    /  ▓▓  \\",
        "   / ▓▓▓▓▓▓ \\",
        "  /▓▓▓▓▓▓▓▓▓▓\\",
        " /____________\\",
    ],
    "periodic_tile": [
        "  ┌─────────┐",
        "  │ 29      │",
        "  │         │",
        "  │   Cu    │",
        "  │         │",
        "  │ Copper  │",
        "  │ 63.546  │",
        "  └─────────┘",
    ],
    "scale_balance": [
        "         ___",
        "        /   \\",
        "   ____|_____|____",
        "  |    |     |    |",
        " (‾‾‾‾)|     |(‾‾‾‾)",
        "  \\__/ |     | \\__/",
        "       |     |",
        "     __|_____|__",
        "    |____________|",
    ],
    "hourglass": [
        "    ┌───────┐",
        "    \\       /",
        "     \\  .  /",
        "      \\ : /",
        "       \\:/",
        "       /:\\",
        "      / : \\",
        "     /  .  \\",
        "    /       \\",
        "    └───────┘",
    ],
    "lightning_flask": [
        "      _",
        "     / \\",
        "    |   |",
        "    |   |    \\",
        "   /     \\    \\",
        "  /   ⚡  \\    \\",
        " /  ⚡▓▓⚡  \\   /",
        "/▓▓▓▓⚡▓▓▓▓▓▓\\ /",
        "==============\\",
        "  \\___________/",
    ],

    # -------------------------------------------------- mascots (v0.5.6) --
    "phoenix": [
        "        \\   ^   /",
        "     )   \\ ' /   (",
        "       `. (o) .'",
        "    -==( ('|') )==-",
        "       .' /'\\ `.",
        "     (   /   \\   )",
        "        /     \\",
        "       '       '",
    ],
    "fox_scholar": [
        "      /\\   /\\",
        "     ( ^.^ )___",
        "      >  ▽  < / \\",
        "     /       |███|",
        "    /   CAT  |___|",
        "   |  ________  |",
        "    \\________/‾\\/",
    ],
    "dragonfly": [
        "     ══════╤══════",
        "           │",
        "        ,-(°)-.",
        "     ╱══╡     ╞══╲",
        "    ╱   └──┬──┘   ╲",
        "           │",
        "           │",
        "          ╱ ╲",
    ],

    # ----------------------------------------------- decorative (v0.5.6) --
    "circuit_frame": [
        "┌──╴  ╶──┬──╴  ╶──┐",
        "│  ●     │     ●  │",
        "├──┐  ┌──┴──┐  ┌──┤",
        "│  └──┤ CAT ├──┘  │",
        "├──┐  └─────┘  ┌──┤",
        "│  ●     │     ●  │",
        "└──╴  ╶──┴──╴  ╶──┘",
    ],
    "molecule_ring": [
        "        ●───●",
        "       ╱     ╲",
        "      ●       ●",
        "      │       │",
        "      ●       ●",
        "       ╲     ╱",
        "        ●───●",
    ],
    "orbit_rings": [
        "      .  ·  ˚  ✦  ˚  ·  .",
        "    ⟨   ╭──────────╮   ⟩",
        "     ⟨  │  ╭────╮  │  ⟩",
        "      ⟨ │  │ ●● │  │ ⟩",
        "     ⟨  │  ╰────╯  │  ⟩",
        "    ⟨   ╰──────────╯   ⟩",
        "      ·  ˚  ✦  ˚  ·",
    ],
}


# -------------------------------------------------------------- captions --
# Short one-line descriptions, shown in the /art browser under each piece.
CAPTIONS = {
    "flask":         "The classic — where every reaction begins.",
    "atom":          "Nucleus in the center, electrons everywhere else.",
    "molecule":      "H₂O: two hydrogens, one oxygen, infinite importance.",
    "benzene":       "C₆H₆ — the aromatic ring that confused chemists for decades.",
    "testtube":      "Drop it in. Watch what happens.",
    "crystal":       "A lattice, frozen in time.",
    "dna":           "The double helix — chemistry that learned to remember.",
    "beaker":        "Bigger than a test tube, same science.",
    "cat_chemist":   "Schrodinger's lab assistant (may or may not be helpful).",
    "robot_chemist": "Never sleeps, never spills, never stops calculating.",
    "owl":           "Wise enough to know the answer is always 'it depends'.",
    "penguin":       "Linux's mascot, now doing chemistry.",
    "CAT":           "The wordmark, in big blocks.",
    "CHEM":          "CHEMISTRY, abbreviated loudly.",
    "divider_ornate": "A flourish for when you need a clean break.",
    "stars_burst":   "Pure decoration. Sparkle responsibly.",
    "wave":          "Everything is waves, if you zoom out enough.",
    "cube_3d":       "A three-dimensional hint, in two dimensions.",
    "pyramid":       "Ancient architecture, or a single molecular orbital?",
    "spiral":        "Entropy, visualized.",
    "dragon":        "Reactive. Approach with care.",
    "rocket":        "CAT, ready for liftoff.",
    "heart_molecule":"Bonding is just chemistry with feelings.",
    "wizard":        "Casts spells. Also casts equations.",
    "bunsen_burner": "The original heat source. Still undefeated.",
    "erlenmeyer":    "The conical one — least likely to spill on a swirl.",
    "periodic_tile": "Element 29. Also this edition's namesake.",
    "scale_balance": "Whatever goes in must come out — mass is stubborn like that.",
    "hourglass":     "Half-life, visualized one grain at a time.",
    "lightning_flask": "Exothermic and proud of it.",
    "phoenix":       "Combustion with better PR.",
    "fox_scholar":   "Quick, clever, mildly caffeinated.",
    "dragonfly":     "Symmetry with wings.",
    "circuit_frame": "For when the terminal wants to feel like a lab bench.",
    "molecule_ring": "Minimalist bonding, maximum vibes.",
    "orbit_rings":   "Electrons, doing their best impression of planets.",
}


# ============================================================ boot banners ==
# A handful of full banners shown one-per-launch (rotating). Each is a tuple
# (art_lines, subtitle). `random_boot()` picks one at random — different piece
# every launch. They're larger/wordier than gallery pieces so boot feels grand.
# v0.7.9.5: Updated branding from "CHEMISTRY CALC TERMINAL" to "CAT"
BOOT_BANNERS = [
    (GALLERY["flask"], "CAT"),
    (GALLERY["atom"], "CAT"),
    (GALLERY["molecule"], "CAT"),
    (GALLERY["CAT"], "CAT"),
    (GALLERY["benzene"], "CAT"),
    (GALLERY["dna"], "CAT"),
    (GALLERY["crystal"], "CAT"),
    (GALLERY["rocket"], "CAT"),
]


# ============================================================ render API ==
def gallery_names():
    """Ordered list of gallery piece names — the menu for the /art browser.
    Order is fixed (dict insertion order) so the menu is stable across runs."""
    return list(GALLERY.keys())


def info(name):
    """The short caption for a piece (or a fallback if unknown)."""
    return CAPTIONS.get(name, "an ASCII art piece")


def _piece_width(piece):
    return max((theme.vlen(line) for line in piece), default=0)


def render(piece, color_a=theme.CYAN, color_b=theme.PURPLE, bold=True,
           align="center", width=None):
    """Render a list of art lines as a gradient-colored, aligned block.

    Reuses `theme.gradient` (per-char 24-bit interpolation) and `theme.vpad`
    so there's no new color code here. `align` is "center" (default) or
    "left". `width`, if given, is the column budget to align within; when
    omitted it sizes to the widest line + a 2-col margin.

    Returns the joined string (newline-separated) — the caller prints it.
    Lines that are pure whitespace are preserved as blank rows so vertical
    spacing in the art is kept intact.
    """
    out = []
    target = width if width is not None else _piece_width(piece) + 2
    for line in piece:
        if line.strip() == "":
            out.append("")
            continue
        colored = theme.gradient(line, color_a, color_b, bold=bold)
        if align == "left":
            out.append(theme.vpad(colored, target, "left"))
        else:
            out.append(theme.vpad(colored, target, "center"))
    return "\n".join(out)


def render_by_name(name, color_a=theme.CYAN, color_b=theme.PURPLE, bold=True,
                   align="center", width=None):
    """Convenience: render a gallery piece by its name."""
    piece = GALLERY.get(name)
    if piece is None:
        return ""
    return render(piece, color_a, color_b, bold, align, width)


def random_boot(rng=None):
    """Pick one boot banner at random. Different each launch. Returns the
    (art_lines, subtitle) tuple; the caller animates + prints it.

    `rng` is accepted for deterministic tests (pass a `random.Random`); the
    default uses the global module RNG so boot genuinely varies per run."""
    pick = rng.choice(BOOT_BANNERS) if rng else random.choice(BOOT_BANNERS)
    return pick


# ---------------------------------------------------------- /art browser --
# Moved here from the old chatui.py during the chat-UI rewrite — this is
# an ASCII art gallery viewer, not part of the chat interface, so it
# belongs with the gallery data it browses rather than in fallback_cli.py.
# (Not currently wired to a slash command; kept intact rather than
# deleted so the feature isn't lost.)
def art_browser():
    """An interactive gallery viewer for this module's ASCII art library.
    Lists every piece in `GALLERY`; picking a number reveals that piece
    with a bouncy gradient animation + its caption. `r` re-rolls to a
    random piece, `q` returns to the caller.

    Cross-platform: uses blocking `input()` for the menu (works
    everywhere, including Windows where raw single-key reads are flaky).
    """
    from . import engine
    names = gallery_names()
    while True:
        theme.clear_screen()
        print()
        print(theme.center(theme.gradient("  ASCII ART GALLERY  ", theme.CYAN, theme.PURPLE, bold=True), engine.WIDTH))
        print(theme.center(theme.faint("browse the showcase — pick a number, or q to exit"), engine.WIDTH))
        print()
        per_col = (len(names) + 1) // 2
        for i in range(per_col):
            left = f"  {theme.fg(str(i + 1) + '.', theme.OC_PRIMARY, bold=True)} {names[i]}" if i < len(names) else ""
            j = i + per_col
            right = f"  {theme.fg(str(j + 1) + '.', theme.OC_PRIMARY, bold=True)} {names[j]}" if j < len(names) else ""
            gap = " " * max(2, 40 - theme.vlen(left))
            print(theme.text(left) + (gap + theme.text(right) if right else ""))
        print()
        print(theme.faint("  r = random piece   q = back to home"))
        try:
            choice = input(theme.badge(" PICK ", theme.BG_INFO) + " ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if choice in ("q", "quit", "exit", "/back", ""):
            return
        if choice in ("r", "random"):
            _show_art_piece(random.choice(names))
            continue
        if choice.isdigit() and 1 <= int(choice) <= len(names):
            _show_art_piece(names[int(choice) - 1])
            continue


def _show_art_piece(name):
    """Reveal one gallery piece with a bouncy animation + caption, then
    wait for Enter before returning to the menu."""
    from . import engine
    from . import anim as _anim
    theme.clear_screen()
    print()
    c1 = random.choice([theme.CYAN, theme.PURPLE, theme.GREEN, theme.OC_PRIMARY, theme.OC_ACCENT])
    c2 = random.choice([theme.PURPLE, theme.CYAN, theme.OC_SECONDARY, theme.ORANGE])
    _anim.confetti_burst(width=engine.WIDTH, count=14)
    print()
    print(theme.center(theme.gradient(name.upper(), c1, c2, bold=True), engine.WIDTH))
    print()
    rendered = render_by_name(name, color_a=c1, color_b=c2)
    _anim.bouncy_reveal(rendered.split("\n"), delay=0.05)
    print()
    print(theme.center(theme.dim(info(name)), engine.WIDTH))
    print()
    try:
        input(theme.faint("  press Enter to return to the gallery\u2026"))
    except (EOFError, KeyboardInterrupt):
        print()
