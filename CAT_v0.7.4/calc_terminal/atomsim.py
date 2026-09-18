"""
Live atom & electron simulation, rendered as real-time ASCII/ANSI
animation in the terminal (redrawn in-place, no external GUI needed).

Two simulators:

  atom_simulation(z)      -- Bohr planetary-model animation: a nucleus of
                              Z protons + N neutrons, with electrons
                              orbiting real K/L/M/N/... shells at
                              shell-dependent angular speed.

  orbital_simulation(key) -- a Monte-Carlo "electron cloud" builder for
                              real hydrogen-like orbitals (1s..3d), using
                              the actual radial/angular probability
                              density |psi|^2, accumulated dot-by-dot
                              live, the way textbooks describe orbitals
                              being "probability clouds" rather than
                              fixed paths.
"""

import math
import random
import sys
import time

from . import theme
from . import keys
from . import scires

# ------------------------------------------------------------- elements --
# Simplified Bohr-Bury shell model (K, L, M, N...) — the standard
# teaching model. Transition-metal shells (Z=21-30) are approximate.
ELEMENTS = {
    1: ("H", "Hydrogen", [1], 1),        2: ("He", "Helium", [2], 4),
    3: ("Li", "Lithium", [2, 1], 7),     4: ("Be", "Beryllium", [2, 2], 9),
    5: ("B", "Boron", [2, 3], 11),       6: ("C", "Carbon", [2, 4], 12),
    7: ("N", "Nitrogen", [2, 5], 14),    8: ("O", "Oxygen", [2, 6], 16),
    9: ("F", "Fluorine", [2, 7], 19),    10: ("Ne", "Neon", [2, 8], 20),
    11: ("Na", "Sodium", [2, 8, 1], 23), 12: ("Mg", "Magnesium", [2, 8, 2], 24),
    13: ("Al", "Aluminium", [2, 8, 3], 27), 14: ("Si", "Silicon", [2, 8, 4], 28),
    15: ("P", "Phosphorus", [2, 8, 5], 31), 16: ("S", "Sulfur", [2, 8, 6], 32),
    17: ("Cl", "Chlorine", [2, 8, 7], 35),  18: ("Ar", "Argon", [2, 8, 8], 40),
    19: ("K", "Potassium", [2, 8, 8, 1], 39), 20: ("Ca", "Calcium", [2, 8, 8, 2], 40),
    21: ("Sc", "Scandium", [2, 8, 9, 2], 45), 22: ("Ti", "Titanium", [2, 8, 10, 2], 48),
    23: ("V", "Vanadium", [2, 8, 11, 2], 51), 24: ("Cr", "Chromium", [2, 8, 13, 1], 52),
    25: ("Mn", "Manganese", [2, 8, 13, 2], 55), 26: ("Fe", "Iron", [2, 8, 14, 2], 56),
    27: ("Co", "Cobalt", [2, 8, 15, 2], 59), 28: ("Ni", "Nickel", [2, 8, 16, 2], 59),
    29: ("Cu", "Copper", [2, 8, 18, 1], 64), 30: ("Zn", "Zinc", [2, 8, 18, 2], 65),
    31: ("Ga", "Gallium", [2, 8, 18, 3], 70), 32: ("Ge", "Germanium", [2, 8, 18, 4], 73),
    33: ("As", "Arsenic", [2, 8, 18, 5], 75), 34: ("Se", "Selenium", [2, 8, 18, 6], 79),
    35: ("Br", "Bromine", [2, 8, 18, 7], 80), 36: ("Kr", "Krypton", [2, 8, 18, 8], 84),
}
SYMBOL_TO_Z = {v[0].lower(): k for k, v in ELEMENTS.items()}
SHELL_NAMES = ["K", "L", "M", "N", "O", "P"]


def resolve_element(query):
    q = str(query).strip().lower()
    if q.isdigit() and int(q) in ELEMENTS:
        return int(q)
    return SYMBOL_TO_Z.get(q)


# --------------------------------------------------------- bohr display --
def _plot(grid, x, y, ch, color_fn):
    w, h = len(grid[0]), len(grid)
    xi, yi = int(round(x)), int(round(y))
    if 0 <= yi < h and 0 <= xi < w:
        grid[yi][xi] = color_fn(ch)


def _render_bohr_frame(z, angle, width=64, height=22):
    sym, name, shells, mass = ELEMENTS[z]
    neutrons = mass - z
    cx, cy = width // 2, height // 2
    grid = [[" "] * width for _ in range(height)]

    max_shell_r = min(cx - 3, cy - 2)
    n_shells = len(shells)
    radii = [max_shell_r * (i + 1) / n_shells for i in range(n_shells)]

    # orbit rings (faint dotted circles), x-scaled 2:1 for terminal char aspect
    for si, radius in enumerate(radii):
        steps = int(radius * 10) + 12
        for k in range(steps):
            th = 2 * math.pi * k / steps
            x = cx + radius * 2 * math.cos(th)
            y = cy + radius * math.sin(th)
            _plot(grid, x, y, "\u00b7", lambda c: theme.faint(c))

    # nucleus: protons (red) + neutrons (gray) packed in a tiny cluster
    random.seed(z * 7)
    cluster = []
    total_nucleons = z + neutrons
    pack_r = max(1.4, math.sqrt(total_nucleons) * 0.55)
    for i in range(min(total_nucleons, 40)):
        ang = random.uniform(0, 2 * math.pi)
        rr = random.uniform(0, pack_r)
        cluster.append((cx + rr * 2 * math.cos(ang) * 0.6, cy + rr * math.sin(ang) * 0.6, i < z))
    for x, y, is_proton in cluster:
        ch = "P" if is_proton else "n"
        color = (lambda c: theme.red(c, bold=True)) if is_proton else (lambda c: theme.dim(c))
        _plot(grid, x, y, ch, color)

    # electrons orbiting each shell — inner shells move faster (higher w)
    electron_positions = []
    for si, (count, radius) in enumerate(zip(shells, radii)):
        speed = 1.0 / (si + 1) ** 0.7
        for e in range(count):
            phase = 2 * math.pi * e / max(count, 1)
            th = angle * speed + phase
            x = cx + radius * 2 * math.cos(th)
            y = cy + radius * math.sin(th)
            electron_positions.append((x, y, si))
            _plot(grid, x, y, "\u25cf", lambda c: theme.cyan(c, bold=True))

    lines = ["".join(row) for row in grid]

    info = [
        theme.purple(f"{name} ({sym})", bold=True) + theme.dim(f"   Z={z}   mass number \u2248 {mass}"),
        theme.dim("Protons: ") + theme.red(str(z), bold=True) + "   " +
        theme.dim("Neutrons: ") + theme.fg(str(neutrons), theme.FAINT, bold=True) + "   " +
        theme.dim("Electrons: ") + theme.cyan(str(z), bold=True),
        theme.dim("Shells (Bohr-Bury): ") + "  ".join(
            f"{SHELL_NAMES[i]}={c}" for i, c in enumerate(shells)),
    ]
    return lines, info


def _snapshot_bohr(z, angle):
    """Save a scientific-style matplotlib PNG snapshot (glow-density
    nucleus + electron shells on black) via calc_terminal.scires.
    Returns the saved path, or None if matplotlib/numpy/scipy are
    unavailable. `angle` is accepted for backward compatibility with
    existing call sites but no longer affects the static snapshot."""
    if z not in ELEMENTS:
        return None
    sym, name, shells, mass = ELEMENTS[z]
    return scires.render_atom(z, sym, name, shells, mass,
                               out_name=f"atom_{sym.lower()}_snapshot.png")


def atom_simulation(z, out=sys.stdout, max_frames=600, frame_delay=0.06):
    """Runs the live Bohr-model animation. Returns cleanly on 'q', on
    frame limit, or on KeyboardInterrupt -- never crashes the app."""
    if z not in ELEMENTS:
        print(theme.red(f"  No shell data for element Z={z} (supported: 1-36)."))
        return

    angle = 0.0
    speed = 0.35
    paused = False
    status_msg = ""
    interactive = keys.stdin_is_interactive()
    theme.hide_cursor()
    try:
        theme.clear_screen()
        frame = 0
        while frame < max_frames:
            lines, info = _render_bohr_frame(z, angle)
            theme.cursor_home()
            out.write(theme.panel(info + [""] + lines, title="atom · live simulation",
                                   color=theme.CYAN, width=70))
            out.write("\n" + theme.faint(
                "  [q] quit   [space] pause   [+/-] speed   [n/p] next/prev   [s] snapshot"
                f"   speed={speed:.2f}{'  (paused)' if paused else ''}") + "\n")
            if status_msg:
                out.write("  " + theme.green(status_msg) + "\n")
                status_msg = ""
            if not interactive:
                out.write(theme.dim(
                    "  (no interactive terminal detected — showing a single "
                    "frame instead of the live view)\n"))
            out.flush()

            if not paused:
                angle += speed
                frame += 1

            if not interactive:
                break

            k = keys.read_key() if keys.key_available() else ""
            if k == "q":
                break
            elif k == " ":
                paused = not paused
            elif k == "+":
                speed = min(3.0, speed + 0.1)
            elif k == "-":
                speed = max(0.05, speed - 0.1)
            elif k == "n":
                nxt = min(36, z + 1)
                if nxt in ELEMENTS:
                    z = nxt
            elif k == "p":
                prv = max(1, z - 1)
                if prv in ELEMENTS:
                    z = prv
            elif k == "r":
                angle = 0.0
            elif k == "s":
                path = _snapshot_bohr(z, angle)
                status_msg = f"Saved: {path}" if path else "matplotlib not installed — snapshot skipped."

            time.sleep(frame_delay)
    except KeyboardInterrupt:
        pass
    finally:
        theme.show_cursor()
    print()


# ------------------------------------------------------ quantum orbitals --
# Real (unnormalized, relative) hydrogen-like radial & angular probability
# density functions. a0 units. Good enough for a live, correctly-shaped
# probability-cloud visualization keyed by real quantum numbers n, l, m.
ORBITALS = {
    "1s": (1, 0, 0), "2s": (2, 0, 0), "2p": (2, 1, 0),
    "3s": (3, 0, 0), "3p": (3, 1, 0), "3d": (3, 2, 0),
}


def _radial_density(n, l, r):
    # r in units of a0. Standard hydrogen radial shapes (unnormalized).
    if (n, l) == (1, 0):
        R = math.exp(-r)
    elif (n, l) == (2, 0):
        R = (2 - r) * math.exp(-r / 2)
    elif (n, l) == (2, 1):
        R = r * math.exp(-r / 2)
    elif (n, l) == (3, 0):
        R = (27 - 18 * r + 2 * r * r) * math.exp(-r / 3)
    elif (n, l) == (3, 1):
        R = r * (6 - r) * math.exp(-r / 3)
    elif (n, l) == (3, 2):
        R = r * r * math.exp(-r / 3)
    else:
        R = math.exp(-r)
    return (R * R) * (r * r)  # include r^2 volume-element weighting


def _angular_density(l, m, theta):
    if l == 0:
        return 1.0
    if l == 1:
        return math.cos(theta) ** 2       # 2pz-type lobe, x-z cross-section
    if l == 2:
        return (3 * math.cos(theta) ** 2 - 1) ** 2  # dz2-type
    return 1.0


def _sample_point(n, l, m, r_max):
    """Rejection-sample an (r, theta) pair from the real |psi|^2 density."""
    peak = 0.0
    for rr in [i * r_max / 60 for i in range(61)]:
        for th in [j * math.pi / 20 for j in range(21)]:
            v = _radial_density(n, l, rr) * _angular_density(l, m, th)
            peak = max(peak, v)
    peak = max(peak, 1e-9)
    for _ in range(200):
        r = random.uniform(0, r_max)
        th = random.uniform(0, math.pi)
        val = _radial_density(n, l, r) * _angular_density(l, m, th)
        if random.uniform(0, peak) <= val:
            phi = random.uniform(0, 2 * math.pi)
            return r, th, phi
    return None


def _snapshot_orbital(orbital_key, n, l, m, r_max):
    """Save a scientific-style probability-density point-cloud PNG
    (density-colored magma scatter on black) via calc_terminal.scires.
    `r_max` is accepted for backward compatibility with existing call
    sites; scires picks its own r_max per n internally."""
    return scires.render_orbital(orbital_key, n, l, m,
                                  out_name=f"orbital_{orbital_key}_snapshot.png")


def snapshot_orbital_grid():
    """Save a reference-chart-style grid of many hydrogen orbitals'
    |psi|^2 (like the classic 'Hydrogen Wave Function' chart). Returns
    the saved path, or None if matplotlib/numpy/scipy are unavailable."""
    return scires.render_orbital_grid()


def orbital_simulation(orbital_key, out=sys.stdout, max_points=2200, width=62, height=26):
    """Live Monte-Carlo build-up of a real quantum orbital's probability
    cloud (the textbook 'electron cloud'), redrawn as it accumulates."""
    if orbital_key not in ORBITALS:
        print(theme.red(f"  Unknown orbital '{orbital_key}'. Try 1s, 2s, 2p, 3s, 3p, 3d."))
        return
    n, l, m = ORBITALS[orbital_key]
    r_max = {1: 6, 2: 14, 3: 24}[n]

    grid = [[0 for _ in range(width)] for _ in range(height)]
    cx, cy = width // 2, height // 2
    shade = " .:-=+*#%@"

    theme.hide_cursor()
    placed = 0
    paused = False
    status_msg = ""
    try:
        theme.clear_screen()
        while placed < max_points:
            k = keys.read_key() if keys.key_available() else ""
            if k == "q":
                break
            if k == " ":
                paused = not paused
            if k == "r":
                grid = [[0 for _ in range(width)] for _ in range(height)]
                placed = 0
            if k == "s":
                path = _snapshot_orbital(orbital_key, n, l, m, r_max)
                status_msg = f"Saved: {path}" if path else "matplotlib not installed — snapshot skipped."

            if not paused:
                for _ in range(6):
                    pt = _sample_point(n, l, m, r_max)
                    if pt is None:
                        continue
                    r, th, phi = pt
                    # project onto the x-z plane (side-on cross-section)
                    x = r * math.sin(th) * math.cos(phi)
                    z_ = r * math.cos(th)
                    scale = (width / 2 - 2) / r_max
                    gx = int(round(cx + x * scale * 2))
                    gy = int(round(cy - z_ * scale))
                    if 0 <= gx < width and 0 <= gy < height:
                        grid[gy][gx] = min(len(shade) - 1, grid[gy][gx] + 1)
                    placed += 1

            rows = []
            for row in grid:
                line = ""
                for v in row:
                    ch = shade[min(v, len(shade) - 1)]
                    if v == 0:
                        line += " "
                    elif v < 3:
                        line += theme.fg(ch, theme.CYAN)
                    elif v < 6:
                        line += theme.fg(ch, theme.PURPLE, bold=True)
                    else:
                        line += theme.fg(ch, theme.TEXT, bold=True)
                rows.append(line)

            info = [
                theme.purple(f"Orbital {orbital_key}", bold=True) +
                theme.dim(f"   n={n}  l={l}  m={m}   (Monte-Carlo |\u03c8|\u00b2 sampling)"),
                theme.dim(f"Points placed: {placed}/{max_points}" + ("  (paused)" if paused else "")),
            ]
            theme.cursor_home()
            out.write(theme.panel(info + [""] + rows, title="orbital · live simulation",
                                   color=theme.PURPLE, width=width + 8))
            out.write("\n" + theme.faint("  [q] quit   [space] pause   [r] restart   [s] snapshot") + "\n")
            if status_msg:
                out.write("  " + theme.green(status_msg) + "\n")
                status_msg = ""
            out.flush()
            time.sleep(0.015)
    except KeyboardInterrupt:
        pass
    finally:
        theme.show_cursor()
    print()
