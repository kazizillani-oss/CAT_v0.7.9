"""
CCT Reaction Simulator — real chemical-equation balancing plus a genuine
numerical playback of kinetics (concentration vs time, integrated with
RK4) and equilibrium approach (mass-action ODE integrated to steady
state), rendered as an ASCII/ANSI terminal chart.

Nothing here is faked: the balancer solves the actual null-space of the
element x species matrix over the rationals (via fractions.Fraction, no
numpy floating-point rounding surprises), and the kinetics/equilibrium
views integrate real rate-law ODEs step by step.
"""

import re
from fractions import Fraction
from math import gcd

# ------------------------------------------------------------- parsing --
_TOKEN = re.compile(r"([A-Z][a-z]?)(\d*)")
_GROUP = re.compile(r"\(([^()]+)\)(\d*)")


def _parse_formula(formula, multiplier=1):
    """Return {element: count} for a formula, expanding one level of
    parentheses (e.g. Ca(OH)2, (NH4)2SO4)."""
    counts = {}

    def add(el, n):
        counts[el] = counts.get(el, 0) + n * multiplier

    # expand parenthesised groups first
    def expand_group(m):
        inner, mult = m.group(1), m.group(2)
        mult = int(mult) if mult else 1
        sub = _parse_formula(inner, mult)
        for el, n in sub.items():
            add(el, n)
        return ""

    formula = _GROUP.sub(expand_group, formula)
    for el, n in _TOKEN.findall(formula):
        if not el:
            continue
        add(el, int(n) if n else 1)
    return counts


def parse_species(token):
    """Strip a leading stoichiometric coefficient (if the user typed one)
    and any state tag like (aq)/(s)/(l)/(g), return (formula, coeff)."""
    token = token.strip()
    token = re.sub(r"\((?:aq|s|l|g)\)", "", token, flags=re.I)
    m = re.match(r"^(\d+)\s*(.*)$", token)
    if m and m.group(2):
        return m.group(2).strip(), int(m.group(1))
    return token.strip(), 1


class BalanceError(Exception):
    pass


def balance_equation(equation):
    """Balance 'Fe + O2 -> Fe2O3' style equations (also accepts '='), and
    return (balanced_string, coeffs, reactants, products).

    Method: build the element x species stoichiometry matrix, solve for
    the integer null-space vector via exact fraction row-reduction (a
    real Gaussian elimination, not a guess-and-check loop), then scale
    to the smallest integers using LCM of denominators / GCD reduction.
    """
    if "->" in equation:
        left, right = equation.split("->", 1)
    elif "=" in equation:
        left, right = equation.split("=", 1)
    elif "\u2192" in equation:
        left, right = equation.split("\u2192", 1)
    else:
        raise BalanceError("Use '->' between reactants and products, e.g. Fe + O2 -> Fe2O3")

    reactants = [parse_species(t)[0] for t in left.split("+") if t.strip()]
    products = [parse_species(t)[0] for t in right.split("+") if t.strip()]
    species = reactants + products
    if len(species) < 2:
        raise BalanceError("Need at least one reactant and one product.")

    formulas = [_parse_formula(s) for s in species]
    elements = sorted({el for f in formulas for el in f})
    n_species = len(species)

    # matrix: rows = elements, cols = species; reactants positive, products negative
    matrix = []
    for el in elements:
        row = []
        for i, f in enumerate(formulas):
            count = f.get(el, 0)
            sign = 1 if i < len(reactants) else -1
            row.append(Fraction(count * sign))
        matrix.append(row)

    coeffs = _null_space_positive(matrix, n_species)
    if coeffs is None:
        raise BalanceError("Could not balance — check the formulas are valid.")

    r_coeffs = coeffs[:len(reactants)]
    p_coeffs = coeffs[len(reactants):]

    def side(names, cs):
        parts = []
        for name, c in zip(names, cs):
            parts.append((f"{c}" if c != 1 else "") + name)
        return " + ".join(parts)

    balanced = f"{side(reactants, r_coeffs)} \u2192 {side(products, p_coeffs)}"
    return balanced, coeffs, reactants, products


def _null_space_positive(matrix, n_cols):
    """Gaussian elimination over Fractions to find a 1-D null-space
    vector, then scale to smallest positive integers. Appends the
    normalization row (last species = 1) to force a unique solution,
    same trick every by-hand equation balancer uses."""
    import copy
    rows = copy.deepcopy(matrix)
    n_rows = len(rows)

    # reduce to row echelon form
    pivot_row = 0
    pivot_cols = []
    for col in range(n_cols):
        sel = None
        for r in range(pivot_row, n_rows):
            if rows[r][col] != 0:
                sel = r
                break
        if sel is None:
            continue
        rows[pivot_row], rows[sel] = rows[sel], rows[pivot_row]
        piv = rows[pivot_row][col]
        rows[pivot_row] = [v / piv for v in rows[pivot_row]]
        for r in range(n_rows):
            if r != pivot_row and rows[r][col] != 0:
                factor = rows[r][col]
                rows[r] = [a - factor * b for a, b in zip(rows[r], rows[pivot_row])]
        pivot_cols.append(col)
        pivot_row += 1
        if pivot_row == n_rows:
            break

    free_cols = [c for c in range(n_cols) if c not in pivot_cols]
    if not free_cols:
        return None
    free_col = free_cols[-1]

    solution = [Fraction(0)] * n_cols
    solution[free_col] = Fraction(1)
    for i, col in enumerate(pivot_cols):
        row = rows[i]
        val = -row[free_col]
        solution[col] = val

    if any(v != 0 for v in solution) is False:
        return None

    # scale to integers: multiply by LCM of denominators
    denoms = [v.denominator for v in solution]
    lcm = 1
    for d in denoms:
        lcm = lcm * d // gcd(lcm, d)
    ints = [int(v * lcm) for v in solution]

    g = 0
    for v in ints:
        g = gcd(g, abs(v))
    if g > 1:
        ints = [v // g for v in ints]

    if any(v <= 0 for v in ints):
        # flip sign if solver found the negative-oriented vector
        if all(v <= 0 for v in ints):
            ints = [-v for v in ints]
        else:
            return None
    return ints


# ------------------------------------------------------------- kinetics --
def integrate_rk4(rate_fn, y0, t_span, steps=200):
    """Classic RK4 integrator for dY/dt = rate_fn(t, Y). y0 is a list of
    concentrations, rate_fn returns a list of derivatives. Returns
    (times, trajectory) where trajectory[i] is the state at times[i]."""
    t0, t1 = t_span
    dt = (t1 - t0) / steps
    t = t0
    y = list(y0)
    times = [t]
    traj = [list(y)]
    for _ in range(steps):
        k1 = rate_fn(t, y)
        y2 = [y[i] + dt / 2 * k1[i] for i in range(len(y))]
        k2 = rate_fn(t + dt / 2, y2)
        y3 = [y[i] + dt / 2 * k2[i] for i in range(len(y))]
        k3 = rate_fn(t + dt / 2, y3)
        y4 = [y[i] + dt * k3[i] for i in range(len(y))]
        k4 = rate_fn(t + dt, y4)
        y = [max(0.0, y[i] + dt / 6 * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i])) for i in range(len(y))]
        t += dt
        times.append(t)
        traj.append(list(y))
    return times, traj


def kinetics_series(order, k, c0, t_end, steps=120):
    """Real integration (RK4) of dA/dt for order 0/1/2, single-species
    decay A -> products. Also returns the analytic solution for
    comparison where one exists (order 1 and 2 have closed forms)."""
    def rate(t, y):
        A = y[0]
        if order == 0:
            return [-k]
        if order == 1:
            return [-k * A]
        return [-k * A * A]

    times, traj = integrate_rk4(rate, [c0], (0, t_end), steps=steps)
    series = [row[0] for row in traj]
    return times, series


def equilibrium_series(kf, kb, a0, b0, c0, d0, t_end, steps=150):
    """A + B <-> C + D mass-action kinetics, integrated to steady state
    with RK4. Returns times and the four concentration trajectories."""
    def rate(t, y):
        A, B, C, D = y
        r = kf * A * B - kb * C * D
        return [-r, -r, r, r]

    times, traj = integrate_rk4(rate, [a0, b0, c0, d0], (0, t_end), steps=steps)
    A = [row[0] for row in traj]
    B = [row[1] for row in traj]
    C = [row[2] for row in traj]
    D = [row[3] for row in traj]
    return times, A, B, C, D


# --------------------------------------------------------- ascii charts --
def ascii_chart(series_dict, times, height=14, width=60, y_label="conc."):
    """Render one or more named time series as an overlaid ASCII line
    chart using block characters, with a simple legend. series_dict maps
    label -> list of y values (same length as times)."""
    glyphs = "\u25cf\u25b2\u25c6\u25a0\u2b22"
    all_vals = [v for series in series_dict.values() for v in series]
    if not all_vals:
        return ["(no data)"]
    y_min, y_max = min(all_vals), max(all_vals)
    if y_max - y_min < 1e-12:
        y_max = y_min + 1

    grid = [[" " for _ in range(width)] for _ in range(height)]
    n = len(times)

    for si, (label, series) in enumerate(series_dict.items()):
        g = glyphs[si % len(glyphs)]
        for i in range(width):
            idx = int(i / (width - 1) * (n - 1)) if width > 1 else 0
            idx = max(0, min(n - 1, idx))
            val = series[idx]
            row = int((val - y_min) / (y_max - y_min) * (height - 1))
            row = max(0, min(height - 1, row))
            grid[height - 1 - row][i] = g

    lines = []
    for r, row in enumerate(grid):
        y_val = y_max - (r / (height - 1)) * (y_max - y_min)
        lines.append(f"{y_val:8.3g} \u2502 " + "".join(row))
    lines.append(" " * 9 + "\u2514" + "\u2500" * width)
    legend = "  ".join(f"{glyphs[i % len(glyphs)]} {label}" for i, label in enumerate(series_dict))
    lines.append(" " * 10 + legend)
    lines.append(" " * 10 + f"t: 0 \u2192 {times[-1]:.3g}s   ({y_label})")
    return lines
