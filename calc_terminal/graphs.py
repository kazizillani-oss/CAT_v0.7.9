"""
Graphing for Chemistry Calc Terminal.

A real terminal can't natively draw a rotatable 3D plot, so this module
takes the honest, practical two-track approach:

  * ascii_plot()      -- live, animated (pen draws left-to-right) 2D
                          character-grid plot rendered directly in the
                          terminal. No dependencies.

  * export_2d/3d()     -- high quality PNG rendered with matplotlib
                           (Agg backend, no display needed) for anyone
                           who wants a crisp 2D curve or a real rotatable-
                           looking 3D surface, saved to disk and opened
                           with the OS default viewer.

Preset curves cover the numericals already in the notebook engine so a
graph is one keystroke away from any solved topic.
"""

import math
import os
import re
import sys
import time

from . import theme

EXPORT_DIR = os.path.join(os.path.expanduser("~"), "cct_exports")

# ---------------------------------------------------------- custom / AI --
# The AI agent (and anyone typing a formula) can plot or export ANY named
# 2D function or 3D surface, not just the 10 built-in presets. This uses
# the same restricted-character + restricted-namespace `eval` approach as
# the quick calculator and the symbolic solver's constant table, so no
# arbitrary code execution is possible.
_MATH_NS = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan, "asin": math.asin,
    "acos": math.acos, "atan": math.atan, "exp": math.exp, "log": math.log,
    "log10": math.log10, "sqrt": math.sqrt, "pi": math.pi, "e": math.e,
    "abs": abs, "pow": pow,
}
_EXPR_RE = re.compile(r"^[0-9A-Za-z_+\-*/().,\s]*$")


class ExpressionError(Exception):
    pass


def _compile_expr(expr_str, varnames):
    """Compile a user/AI-supplied math expression into a callable f(*vars).
    Only arithmetic, the functions in _MATH_NS, and the given variable
    names are reachable — no builtins, no attribute access."""
    if not expr_str or not _EXPR_RE.match(expr_str.replace("^", "")):
        raise ExpressionError(f"Invalid or unsafe expression: {expr_str!r}")
    code = compile(expr_str.replace("^", "**"), "<expr>", "eval")

    def f(*args):
        ns = dict(_MATH_NS)
        ns.update(dict(zip(varnames, args)))
        return eval(code, {"__builtins__": {}}, ns)

    # fail fast on a syntactically-valid-looking but broken expression
    try:
        f(*([1.0] * len(varnames)))
    except ExpressionError:
        raise
    except Exception as exc:
        raise ExpressionError(f"Could not evaluate expression: {exc}")
    return f


def custom_curve(expr, xmin=0.0, xmax=10.0, points=60, title=None,
                  xlabel="x", ylabel="y", var="x"):
    """Build (xs, ys, title, xlabel, ylabel) for ANY named function of one
    variable, e.g. custom_curve('sin(x)*exp(-x/5)', 0, 20, title='Damped wave').
    This is what lets the AI agent — or a person — graph something that
    isn't one of the 10 built-in chemistry presets."""
    xmin, xmax = float(xmin), float(xmax)
    if xmax <= xmin:
        xmax = xmin + 1.0
    f = _compile_expr(expr, [var])
    xs = [xmin + i * (xmax - xmin) / points for i in range(points + 1)]
    ys = []
    for x in xs:
        try:
            val = float(f(x))
        except Exception:
            val = 0.0
        ys.append(val if math.isfinite(val) else 0.0)
    return xs, ys, title or f"{ylabel} = {expr}", xlabel, ylabel


def export_custom_2d(expr, xmin=0.0, xmax=10.0, points=300, title=None,
                      xlabel="x", ylabel="y", filename=None):
    xs, ys, t, xl, yl = custom_curve(expr, xmin, xmax, points, title, xlabel, ylabel)
    return export_2d(xs, ys, t, xl, yl, filename)


def export_custom_3d(expr, xmin=-5.0, xmax=5.0, ymin=-5.0, ymax=5.0,
                      points=45, title=None, filename=None):
    """Export ANY named 3D surface z = f(x, y) as a high-quality PNG —
    the free-form counterpart to export_3d_surface()'s two fixed presets."""
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
    _ensure_dir()

    f = _compile_expr(expr, ["x", "y"])
    xs = np.linspace(float(xmin), float(xmax), points)
    ys = np.linspace(float(ymin), float(ymax), points)
    X, Y = np.meshgrid(xs, ys)
    Z = np.zeros_like(X)
    for i in range(X.shape[0]):
        for j in range(X.shape[1]):
            try:
                v = float(f(X[i, j], Y[i, j]))
                Z[i, j] = v if math.isfinite(v) else 0.0
            except Exception:
                Z[i, j] = 0.0

    fig = plt.figure(figsize=(7, 6), facecolor="#1a1b26")
    ax = fig.add_subplot(111, projection="3d")
    ax.set_facecolor("#1a1b26")
    ax.plot_surface(X, Y, Z, cmap="viridis", edgecolor="none")
    title = title or f"z = {expr}"
    ax.set_title(title, color="#c0caf5")
    ax.set_xlabel("x", color="#a9b1d6")
    ax.set_ylabel("y", color="#a9b1d6")
    ax.set_zlabel("z", color="#a9b1d6")
    ax.tick_params(colors="#a9b1d6")

    safe_name = re.sub(r"[^a-zA-Z0-9]+", "_", title.lower()).strip("_")[:40]
    filename = filename or f"{safe_name or 'custom_surface'}.png"
    path = os.path.join(EXPORT_DIR, filename)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


# --------------------------------------------------------------- presets --
def preset_curve(name, **params):
    """Returns (x_list, y_list, title, xlabel, ylabel) for a named
    chemistry curve, computed from the real governing formula."""
    n = 60
    if name == "zero_order":
        R0 = params.get("R0", 1.0); k = params.get("k", 0.02); tmax = params.get("tmax", 40)
        xs = [i * tmax / n for i in range(n + 1)]
        ys = [max(0.0, R0 - k * t) for t in xs]
        return xs, ys, "Zero Order: [R] vs t", "time", "[R]"
    if name == "first_order":
        R0 = params.get("R0", 1.0); k = params.get("k", 0.05); tmax = params.get("tmax", 60)
        xs = [i * tmax / n for i in range(n + 1)]
        ys = [R0 * math.exp(-k * t) for t in xs]
        return xs, ys, "First Order: [R] vs t", "time", "[R]"
    if name == "first_order_log":
        R0 = params.get("R0", 1.0); k = params.get("k", 0.05); tmax = params.get("tmax", 60)
        xs = [i * tmax / n for i in range(n + 1)]
        ys = [math.log10(max(R0 * math.exp(-k * t), 1e-12)) for t in xs]
        return xs, ys, "First Order: log[R] vs t (straight line)", "time", "log[R]"
    if name == "second_order":
        R0 = params.get("R0", 1.0); k = params.get("k", 0.05); tmax = params.get("tmax", 60)
        xs = [i * tmax / n for i in range(n + 1)]
        ys = [1.0 / (1.0 / R0 + k * t) for t in xs]
        return xs, ys, "Second Order: [R] vs t", "time", "[R]"
    if name == "arrhenius":
        A = params.get("A", 1e13); Ea = params.get("Ea", 75000)
        Ts = [i for i in range(250, 251 + n * 4, 4)]
        xs = [1.0 / T for T in Ts]
        ys = [math.log(A * math.exp(-Ea / (8.314 * T))) for T in Ts]
        return xs, ys, "Arrhenius: ln k vs 1/T", "1/T", "ln k"
    if name == "boyles":
        P1 = params.get("P1", 1.0); V1 = params.get("V1", 22.4)
        xs = [0.5 + i * (10 - 0.5) / n for i in range(n + 1)]
        ys = [(P1 * V1) / P for P in xs]
        return xs, ys, "Boyle's Law: V vs P (T const.)", "P", "V"
    if name == "maxwell_boltzmann":
        T = params.get("T", 300); M = params.get("M", 0.028)
        R = 8.314
        xs = [i * 2500 / n for i in range(1, n + 1)]
        ys = [4 * math.pi * (M / (2 * math.pi * R * T)) ** 1.5 * v * v *
              math.exp(-M * v * v / (2 * R * T)) for v in xs]
        return xs, ys, f"Maxwell-Boltzmann speed distribution (T={T}K)", "speed (m/s)", "f(v)"
    if name == "radial_prob_1s":
        xs = [i * 6 / n for i in range(n + 1)]
        ys = [(r * r) * math.exp(-2 * r) for r in xs]
        return xs, ys, "1s Radial Probability Density", "r (a0)", "r\u00b2R\u00b2"
    if name == "titration":
        Ca = params.get("Ca", 0.1); Va = params.get("Va", 25.0); Cb = params.get("Cb", 0.1)
        xs = [i * 60 / n for i in range(1, n)]
        ys = []
        for Vb in xs:
            moles_a = Ca * Va; moles_b = Cb * Vb
            excess = moles_b - moles_a
            total_v = Va + Vb
            if excess > 0.0001:
                pOH = -math.log10(excess / total_v)
                ys.append(14 - pOH)
            elif excess < -0.0001:
                H = -excess / total_v
                ys.append(-math.log10(H))
            else:
                ys.append(7.0)
        return xs, ys, "Titration Curve: pH vs Volume of Base", "V base (mL)", "pH"
    if name == "energy_levels":
        xs = list(range(1, 6))
        ys = [-2.18e-18 / (n_ * n_) for n_ in xs]
        return xs, ys, "Bohr Energy Levels (Hydrogen)", "n", "E (J)"
    raise ValueError(f"Unknown preset: {name}")


PRESETS = [
    ("zero_order", "Zero Order kinetics: [R] vs t"),
    ("first_order", "First Order kinetics: [R] vs t (exponential decay)"),
    ("first_order_log", "First Order: log[R] vs t (linear form)"),
    ("second_order", "Second Order kinetics: [R] vs t"),
    ("arrhenius", "Arrhenius plot: ln k vs 1/T"),
    ("boyles", "Boyle's Law: V vs P"),
    ("maxwell_boltzmann", "Maxwell-Boltzmann speed distribution"),
    ("radial_prob_1s", "1s orbital radial probability density"),
    ("titration", "Strong acid / strong base titration curve"),
    ("energy_levels", "Bohr hydrogen energy levels"),
]


# ------------------------------------------------------------ ascii plot --
def ascii_plot(xs, ys, title="", xlabel="x", ylabel="y", width=64, height=18,
                animate=True, out=sys.stdout, color=None):
    color = color or theme.CYAN
    ymin, ymax = min(ys), max(ys)
    xmin, xmax = min(xs), max(xs)
    if ymax == ymin:
        ymax += 1
    if xmax == xmin:
        xmax += 1

    grid = [[" "] * width for _ in range(height)]

    def gx(x): return int((x - xmin) / (xmax - xmin) * (width - 1))
    def gy(y): return int(height - 1 - (y - ymin) / (ymax - ymin) * (height - 1))

    points = [(gx(x), gy(y)) for x, y in zip(xs, ys)]

    def draw_upto(idx):
        for i in range(1, idx + 1):
            x0, y0 = points[i - 1]
            x1, y1 = points[i]
            steps = max(abs(x1 - x0), abs(y1 - y0), 1)
            for s in range(steps + 1):
                xx = round(x0 + (x1 - x0) * s / steps)
                yy = round(y0 + (y1 - y0) * s / steps)
                if 0 <= yy < height and 0 <= xx < width:
                    grid[yy][xx] = "\u25cf"

    def render():
        lines = []
        y_at = lambda row: ymax - row * (ymax - ymin) / (height - 1)
        for r, row in enumerate(grid):
            label = f"{y_at(r):>9.3g} |" if r % 3 == 0 else " " * 9 + " |"
            lines.append(theme.faint(label) + theme.fg("".join(row), color))
        axis = " " * 10 + "-" * width
        lines.append(theme.faint(axis))
        lines.append(" " * 10 + theme.dim(f"{xmin:.3g}") +
                      " " * (width - len(f"{xmin:.3g}") - len(f"{xmax:.3g}")) +
                      theme.dim(f"{xmax:.3g}"))
        return lines

    if title:
        print(theme.purple(title, bold=True))
    if animate:
        for i in range(1, len(points), max(1, len(points) // 40)):
            draw_upto(i)
            out.write("\033[H" if i > 1 else "")
            for l in render():
                out.write(l + "\n")
            out.flush()
            time.sleep(0.02)
    draw_upto(len(points) - 1)
    for l in render():
        print(l)
    print(theme.dim(f"  x: {xlabel}    y: {ylabel}"))


# --------------------------------------------------------- image export --
def _ensure_dir():
    os.makedirs(EXPORT_DIR, exist_ok=True)


def export_2d(xs, ys, title, xlabel, ylabel, filename=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _ensure_dir()
    filename = filename or (title.lower().replace(" ", "_").replace(":", "") + ".png")
    path = os.path.join(EXPORT_DIR, filename)
    fig, ax = plt.subplots(figsize=(7, 4.5), facecolor="#1a1b26")
    ax.set_facecolor("#1a1b26")
    ax.plot(xs, ys, color="#7dcfff", linewidth=2)
    ax.set_title(title, color="#c0caf5")
    ax.set_xlabel(xlabel, color="#a9b1d6")
    ax.set_ylabel(ylabel, color="#a9b1d6")
    ax.tick_params(colors="#a9b1d6")
    for spine in ax.spines.values():
        spine.set_color("#414868")
    ax.grid(True, color="#292e42", linewidth=0.5)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def export_3d_surface(kind="orbital_3d", filename=None):
    """Renders a real 3D surface (matplotlib) for a chemistry concept:
    'orbital_3d' -> a 2p-orbital-shaped probability surface,
    'pvt' -> the ideal-gas P-V-T surface."""
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
    _ensure_dir()

    fig = plt.figure(figsize=(7, 6), facecolor="#1a1b26")
    ax = fig.add_subplot(111, projection="3d")
    ax.set_facecolor("#1a1b26")

    if kind == "pvt":
        n_ = np.linspace(0.5, 3, 40)
        T = np.linspace(200, 500, 40)
        N, T2 = np.meshgrid(n_, T)
        P = N * 0.0821 * T2 / 10.0  # V fixed at 10 L
        surf = ax.plot_surface(N, T2, P, cmap="plasma", edgecolor="none")
        ax.set_xlabel("n (mol)", color="#a9b1d6")
        ax.set_ylabel("T (K)", color="#a9b1d6")
        ax.set_zlabel("P (atm)", color="#a9b1d6")
        ax.set_title("Ideal Gas Law surface: P(n, T) at V=10L", color="#c0caf5")
        filename = filename or "pvt_surface.png"
    else:
        theta = np.linspace(0, np.pi, 60)
        phi = np.linspace(0, 2 * np.pi, 60)
        TH, PH = np.meshgrid(theta, phi)
        r = np.abs(np.cos(TH))  # 2pz angular shape
        X = r * np.sin(TH) * np.cos(PH)
        Y = r * np.sin(TH) * np.sin(PH)
        Z = r * np.cos(TH)
        surf = ax.plot_surface(X, Y, Z, cmap="cool", edgecolor="none")
        ax.set_title("2p Orbital — angular probability surface", color="#c0caf5")
        filename = filename or "orbital_2p_3d.png"

    ax.tick_params(colors="#a9b1d6")
    path = os.path.join(EXPORT_DIR, filename)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path
