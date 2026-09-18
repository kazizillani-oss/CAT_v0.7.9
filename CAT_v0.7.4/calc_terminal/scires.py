"""
Scientific rendering — matplotlib PNG snapshots styled after real
quantum-chemistry visualizations (probability-density point clouds,
Hydrogen-Wave-Function-style orbital grids, and ELF-style chemical
bonding density maps).

Everything here is additive: it does not touch the existing live
ASCII/ANSI terminal animations in atomsim.py / sim3d.py / gpu3d.py,
it only gives the "press s to snapshot" PNG export path a much more
scientific look, and adds two new renders (orbital grid, bonding map)
that didn't exist before.

All renders:
  - pure black background (#000000), no axes/ticks/spines
  - a small monospace caption in the corner (matches the
    "QUANTUM ORBITAL PROBABILITY DENSITY VISUALIZER" style caption)
  - saved to ~/cct_exports and the path is returned (None if
    matplotlib/numpy/scipy aren't installed)

Physics notes:
  - Atom / orbital renders use the *real* hydrogen-like radial
    wavefunction (via the generalized Laguerre polynomials) and the
    real spherical-harmonic angular density (via associated Legendre
    functions) — not a cartoon approximation. |psi|^2 is exact for a
    hydrogenic (single-electron) atom in those quantum numbers.
  - The bonding/ELF map is NOT a real Electron Localization Function
    from a DFT calculation (that needs an actual electronic-structure
    solver). It's a stylized analytic stand-in — concentric per-atom
    "shell" rings plus Gaussian bond-lobes, tuned to reproduce the
    *visual language* of a real ELF plot (rings around cores, bright
    bonding saddle regions, rainbow colormap) for illustration inside
    the app. Documented here so nobody mistakes it for lab output.
"""

import math
import os

try:
    import numpy as np
    from scipy.special import genlaguerre, lpmv
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    from scipy.ndimage import gaussian_filter
    HAVE_DEPS = True
except ImportError:
    HAVE_DEPS = False

BG = "#000000"


def _export_dir(category="simulations"):
    """Renders go into the shared Project Workspace now (spec section
    16, calc_terminal/workspace.py) instead of scires.py's own
    ~/cct_exports. Falls back to the old location only if the
    workspace module can't be imported for some reason, so a broken
    workspace config never blocks a render outright.

    STRICT FIX v0.7.9.6: explicit ensure=True — this is a WRITE path
    (render requested explicitly). Read paths never create dirs."""
    try:
        from . import workspace
        return workspace.category_dir(category, ensure=True)
    except Exception:
        d = os.path.join(os.path.expanduser("~"), "cct_exports")
        os.makedirs(d, exist_ok=True)
        return d


def _caption(ax, text, color="#e8ebfa"):
    ax.text(0.015, 0.02, text, transform=ax.transAxes, color=color,
             fontsize=7.5, family="monospace", alpha=0.85, va="bottom")


def _no_axes(ax):
    ax.set_facecolor(BG)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)


def _wireframe_box(ax, half, n=2, color="#ffffff", alpha=0.35, lw=0.7, seed=0):
    """Decorative rotated-square wireframe accents (the crossed-diamond
    look behind the point cloud in reference orbital renders)."""
    rng = np.random.default_rng(seed)
    for _ in range(n):
        ang = rng.uniform(0, math.pi)
        pts = []
        for k in range(5):
            a = ang + k * math.pi / 2
            pts.append((half * 1.15 * math.cos(a), half * 1.15 * math.sin(a)))
        xs, ys = zip(*pts)
        ax.plot(xs, ys, color=color, alpha=alpha, lw=lw)


# ----------------------------------------------------------- hydrogen --
def hydrogen_R(n, l, r):
    """Exact (normalized) hydrogenic radial wavefunction, a0 units, Z=1."""
    r = np.asarray(r, dtype=float)
    rho = 2.0 * r / n
    lag = genlaguerre(n - l - 1, 2 * l + 1)(rho)
    norm = math.sqrt((2.0 / n) ** 3 * math.factorial(n - l - 1) /
                      (2.0 * n * math.factorial(n + l)))
    return norm * np.exp(-rho / 2.0) * rho ** l * lag


def hydrogen_angular2(l, m, theta):
    """|Y_l^m(theta,phi)|^2 — independent of phi since the complex
    exponential has unit modulus, so this is exact and axisymmetric."""
    m = abs(m)
    cos_t = np.cos(theta)
    p = lpmv(m, l, cos_t)
    norm = (2 * l + 1) / (4 * math.pi) * math.factorial(l - m) / math.factorial(l + m)
    return norm * p ** 2


def psi2(n, l, m, r, theta):
    """|psi_nlm(r,theta)|^2 at a point in the meridian half-plane."""
    return hydrogen_R(n, l, r) ** 2 * hydrogen_angular2(l, m, theta)


R_MAX_FOR_N = {1: 6, 2: 15, 3: 28, 4: 44}


# --------------------------------------------------- 1. atom / nucleus --
def render_atom(z, symbol, name, shells, mass, out_name=None):
    """Nucleus (protons/neutrons) + electron shells, glow-density style
    on black, matching the rendering language of the orbital plots."""
    if not HAVE_DEPS:
        return None
    neutrons = mass - z
    rng = np.random.default_rng(z * 7)

    fig, ax = plt.subplots(figsize=(6.4, 6.4), facecolor=BG)
    _no_axes(ax)

    max_shell_r = len(shells) + 1.0

    # faint dotted shell orbits
    th = np.linspace(0, 2 * math.pi, 400)
    for si in range(len(shells)):
        r = si + 1.3
        ax.plot(r * np.cos(th), r * np.sin(th), color="#3b4261", lw=0.6,
                 alpha=0.55, ls=(0, (1, 3)))

    # electrons as soft glow dots at random shell phase (static snapshot)
    for si, count in enumerate(shells):
        r = si + 1.3
        for e in range(count):
            a = 2 * math.pi * e / max(count, 1) + rng.uniform(-0.15, 0.15)
            ex, ey = r * math.cos(a), r * math.sin(a)
            for gs, ga in ((90, 0.05), (35, 0.12), (10, 0.9)):
                ax.scatter([ex], [ey], s=gs, c="#7dcfff", alpha=ga, linewidths=0)

    # nucleus: protons + neutrons packed, glow-layered
    total = z + neutrons
    pack_r = max(0.5, math.sqrt(total) * 0.24)
    kinds = [True] * z + [False] * neutrons
    rng.shuffle(kinds)
    xs, ys = [], []
    for is_p in kinds[:80]:
        ang = rng.uniform(0, 2 * math.pi)
        rr = pack_r * math.sqrt(rng.uniform(0, 1))
        xs.append(rr * math.cos(ang))
        ys.append(rr * math.sin(ang))
    xs, ys = np.array(xs), np.array(ys)
    is_proton = np.array(kinds[:80])
    for gs, ga in ((260, 0.05), (110, 0.12)):
        ax.scatter(xs[is_proton], ys[is_proton], s=gs, c="#ff7f9a", alpha=ga, linewidths=0)
        ax.scatter(xs[~is_proton], ys[~is_proton], s=gs, c="#8891c9", alpha=ga, linewidths=0)
    ax.scatter(xs[is_proton], ys[is_proton], s=22, c="#ff9fb4", alpha=0.95, linewidths=0)
    ax.scatter(xs[~is_proton], ys[~is_proton], s=22, c="#a9b1e8", alpha=0.95, linewidths=0)

    ax.set_xlim(-max_shell_r, max_shell_r)
    ax.set_ylim(-max_shell_r, max_shell_r)
    ax.set_aspect("equal")
    ax.set_title(f"{name} ({symbol})   Z={z}   A\u2248{mass}", color="#c0caf5",
                 fontsize=12, family="monospace", pad=10)
    _caption(ax, f"NUCLEUS: {z} PROTON{'S' if z != 1 else ''} \u00b7 {neutrons} NEUTRON{'S' if neutrons != 1 else ''}"
                 f"   \u2014   {z} ELECTRON{'S' if z != 1 else ''} ({', '.join(str(c) for c in shells)})")

    path = os.path.join(_export_dir(), out_name or f"atom_{symbol.lower()}.png")
    fig.savefig(path, dpi=170, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


# -------------------------------------------------- 2. single orbital --
CMAP_MAGMA_BLACK = None


def render_orbital(orbital_key, n, l, m, n_points=18000, out_name=None):
    """Point-cloud probability density render, colored by local point
    density (magma), on black — the 'live electron cloud' aesthetic."""
    if not HAVE_DEPS:
        return None
    rng = np.random.default_rng(abs(hash((n, l, m))) % (2 ** 32))
    r_max = R_MAX_FOR_N.get(n, 40)

    # rejection-sample the true 3D density including the r^2*sin(theta)
    # spherical volume element
    grid_r = np.linspace(1e-4, r_max, 220)
    grid_t = np.linspace(1e-4, math.pi - 1e-4, 90)
    RR, TT = np.meshgrid(grid_r, grid_t, indexing="ij")
    dens = psi2(n, l, m, RR, TT) * RR ** 2 * np.sin(TT)
    peak = dens.max()

    pts = []
    batch = max(n_points * 6, 20000)
    tries = 0
    while len(pts) < n_points and tries < 40:
        tries += 1
        r = rng.uniform(0, r_max, batch)
        th = rng.uniform(0, math.pi, batch)
        val = psi2(n, l, m, r, th) * r ** 2 * np.sin(th)
        acc = rng.uniform(0, peak, batch) <= val
        r, th = r[acc], th[acc]
        phi = rng.uniform(0, 2 * math.pi, len(r))
        x = r * np.sin(th) * np.cos(phi)
        z_ = r * np.cos(th)
        pts.extend(zip(x.tolist(), z_.tolist()))
    pts = np.array(pts[:n_points]) if pts else np.zeros((0, 2))

    fig, ax = plt.subplots(figsize=(6.4, 6.4), facecolor=BG)
    _no_axes(ax)
    half = r_max * 0.75

    if len(pts):
        # local density via a blurred 2D histogram, sampled back at each point
        bins = 160
        H, xedges, yedges = np.histogram2d(pts[:, 0], pts[:, 1], bins=bins,
                                            range=[[-half, half], [-half, half]])
        H = gaussian_filter(H, sigma=1.4)
        xi = np.clip(np.digitize(pts[:, 0], xedges) - 1, 0, bins - 1)
        yi = np.clip(np.digitize(pts[:, 1], yedges) - 1, 0, bins - 1)
        c = H[xi, yi]
        c = c / (c.max() + 1e-9)
        _wireframe_box(ax, half, n=2, seed=n * 10 + l * 3 + m)
        ax.scatter(pts[:, 0], pts[:, 1], c=c, cmap="magma", s=3.2, alpha=0.75,
                   linewidths=0, vmin=0.0, vmax=1.0)

    ax.set_xlim(-half, half)
    ax.set_ylim(-half, half)
    ax.set_aspect("equal")
    _caption(ax, f"ORBITAL {orbital_key.upper()} PROBABILITY DENSITY VISUALIZER   n={n} l={l} m={m}")

    path = os.path.join(_export_dir(), out_name or f"orbital_{orbital_key}.png")
    fig.savefig(path, dpi=170, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


# ------------------------------------------------------ 3. orbital grid --
DEFAULT_GRID = [
    (2, 0, 0), (3, 0, 0),
    (2, 1, 0), (3, 1, 0), (3, 1, 1),
    (2, 1, 1), (3, 2, 0), (3, 2, 1), (3, 2, 2),
    (4, 0, 0), (4, 1, 0), (4, 1, 1),
    (4, 2, 0), (4, 2, 1), (4, 2, 2),
    (4, 3, 0), (4, 3, 1), (4, 3, 2), (4, 3, 3),
]


def render_orbital_grid(specs=None, out_name="orbital_grid.png", cols=5):
    """Reference-chart-style grid of many (n,l,m) orbitals' |psi|^2,
    computed as an exact deterministic density field (not sampled),
    matching the classic 'Hydrogen Wave Function' probability chart."""
    if not HAVE_DEPS:
        return None
    specs = specs or DEFAULT_GRID
    rows = math.ceil(len(specs) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 2.1, rows * 2.1), facecolor=BG)
    axes = np.array(axes).reshape(rows, cols)

    for idx, ax in enumerate(axes.flat):
        _no_axes(ax)
        if idx >= len(specs):
            ax.axis("off")
            continue
        n, l, m = specs[idx]
        r_max = R_MAX_FOR_N.get(n, 44) * 0.85
        size = 160
        xs = np.linspace(-r_max, r_max, size)
        zs = np.linspace(-r_max, r_max, size)
        X, Z = np.meshgrid(xs, zs)
        R = np.sqrt(X ** 2 + Z ** 2) + 1e-9
        TH = np.arccos(np.clip(Z / R, -1, 1))
        dens = psi2(n, l, m, R, TH)
        dens = dens / (dens.max() + 1e-12)
        dens = dens ** 0.42  # gamma-boost so faint outer lobes stay visible
        ax.imshow(dens, cmap="inferno", origin="lower",
                   extent=[-r_max, r_max, -r_max, r_max])
        ax.set_aspect("equal")
        ax.text(0.05, 0.92, f"({n},{l},{m})", transform=ax.transAxes,
                 color="#f2e9ff", fontsize=9, family="monospace", va="top")

    fig.suptitle("Hydrogen Wave Function \u2014 probability density plots  |\u03c8\u2099\u2097\u2098(r,\u03b8,\u03c6)|\u00b2",
                  color="#e8ebfa", fontsize=13, family="monospace", y=0.995)
    fig.patch.set_facecolor(BG)
    fig.subplots_adjust(wspace=0.05, hspace=0.12, top=0.94)

    path = os.path.join(_export_dir("graphs"), out_name)
    fig.savefig(path, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


# ---------------------------------------------- 4. chemical bonding map --
# Illustrative 2D geometries (not to scale). shells: approximate K/L
# electron-shell ring radii (a0-ish, tuned for the visual, not ab-initio).
_ELEM = {
    "H": (1, "#ffffff", [(0.28, 0.10, 1.0)]),
    "C": (6, "#909090", [(0.16, 0.05, 1.0), (0.55, 0.14, 0.75)]),
    "N": (7, "#3050f8", [(0.15, 0.05, 1.0), (0.52, 0.13, 0.8)]),
    "O": (8, "#ff0d0d", [(0.14, 0.05, 1.0), (0.50, 0.13, 0.85)]),
}

MOLECULES = {
    "furan": {
        "atoms": [("O", 0.00, 0.95), ("C", 0.90, 0.29), ("C", 0.56, -0.77),
                  ("C", -0.56, -0.77), ("C", -0.90, 0.29)],
        "bonds": [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)],
    },
    "water": {
        "atoms": [("O", 0.0, 0.35), ("H", -0.76, -0.35), ("H", 0.76, -0.35)],
        "bonds": [(0, 1), (0, 2)],
    },
    "methane": {
        "atoms": [("C", 0.0, 0.0), ("H", 0.9, 0.55), ("H", -0.9, 0.55),
                  ("H", 0.55, -0.95), ("H", -0.55, -0.95)],
        "bonds": [(0, 1), (0, 2), (0, 3), (0, 4)],
    },
    "co2": {
        "atoms": [("O", -1.1, 0.0), ("C", 0.0, 0.0), ("O", 1.1, 0.0)],
        "bonds": [(0, 1), (1, 2)],
    },
    "ethanol": {
        "atoms": [("C", -1.1, 0.15), ("C", 0.05, -0.45), ("O", 1.15, 0.15),
                  ("H", -1.9, -0.35), ("H", -1.3, 0.85), ("H", -0.9, 1.0),
                  ("H", 0.2, -1.1), ("H", -0.15, -1.0)],
        "bonds": [(0, 1), (1, 2), (0, 3), (0, 4), (0, 5), (1, 6), (1, 7)],
    },
    "benzene": {
        "atoms": [("C", math.cos(a), math.sin(a)) for a in
                  [k * math.pi / 3 for k in range(6)]],
        "bonds": [(i, (i + 1) % 6) for i in range(6)],
    },
}


def _elf_like_field(X, Y, mol):
    field = np.zeros_like(X)
    atoms = mol["atoms"]
    for sym, ax_, ay_ in atoms:
        _, _, shells = _ELEM.get(sym, (1, "#cccccc", [(0.2, 0.07, 1.0)]))
        r = np.sqrt((X - ax_) ** 2 + (Y - ay_) ** 2)
        for shell_r, width, weight in shells:
            field += weight * np.exp(-((r - shell_r) / width) ** 2)
        field += 0.35 * np.exp(-(r / 0.06) ** 2)  # tiny core spike

    for i, j in mol["bonds"]:
        (sa, xa, ya), (sb, xb, yb) = atoms[i], atoms[j]
        bx, by = xb - xa, yb - ya
        length = math.hypot(bx, by)
        ux, uy = bx / length, by / length
        px, py = -uy, ux
        # sample along-bond position (0..1) and perpendicular offset
        along = ((X - xa) * ux + (Y - ya) * uy) / length
        perp = (X - xa) * px + (Y - ya) * py
        taper = np.clip(along, 0, 1)
        bulge = np.sin(np.pi * np.clip(along, 0, 1)) ** 1.5
        field += 0.85 * bulge * np.exp(-(perp / 0.16) ** 2) * (along > -0.05) * (along < 1.05)

    return field


def render_bonding(molecule, out_name=None):
    """ELF-style electron density/bonding map: concentric per-atom shell
    rings + bond-region lobes, rainbow colormap on black. Stylized
    illustration, not an ab-initio ELF calculation (see module docstring)."""
    if not HAVE_DEPS:
        return None
    key = molecule.strip().lower()
    if key not in MOLECULES:
        return None
    mol = MOLECULES[key]
    xs = [a[1] for a in mol["atoms"]]
    ys = [a[2] for a in mol["atoms"]]
    pad = 0.9
    xmin, xmax = min(xs) - pad, max(xs) + pad
    ymin, ymax = min(ys) - pad, max(ys) + pad
    size = 420
    X, Y = np.meshgrid(np.linspace(xmin, xmax, size), np.linspace(ymin, ymax, size))
    field = _elf_like_field(X, Y, mol)
    field = field / (field.max() + 1e-12)
    field = gaussian_filter(field, sigma=1.0)
    field = np.clip(field, 0, 1)

    fig, ax = plt.subplots(figsize=(6.6, 6.6), facecolor=BG)
    _no_axes(ax)
    im = ax.imshow(field, cmap="turbo", origin="lower",
                    extent=[xmin, xmax, ymin, ymax], vmin=0, vmax=1)
    for sym, ax_, ay_ in mol["atoms"]:
        ax.text(ax_, ay_, sym, color="#ffffff", fontsize=10, family="monospace",
                 ha="center", va="center", weight="bold",
                 bbox=dict(boxstyle="circle,pad=0.15", fc="#000000", ec="none", alpha=0.35))
    ax.set_aspect("equal")
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)

    cbar = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.02)
    cbar.set_label("ELF (stylized)", color="#c0caf5", family="monospace", fontsize=9)
    cbar.ax.yaxis.set_tick_params(color="#c0caf5")
    plt.setp(cbar.ax.get_yticklabels(), color="#c0caf5", family="monospace", fontsize=8)

    _caption(ax, f"{molecule.upper()} \u2014 ELECTRON LOCALIZATION (STYLIZED)  \u00b7  BONDING DENSITY MAP")

    path = os.path.join(_export_dir("graphs"), out_name or f"bonding_{key}.png")
    fig.savefig(path, dpi=170, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


# --------------------------------------------------- 5. Bloch sphere --
def bloch_state_probs(theta, phi):
    """Exact single-qubit measurement probabilities for
    |psi> = cos(theta/2)|0> + e^{i phi} sin(theta/2)|1>, theta/phi in
    RADIANS. Returns a dict of (basis -> (p_plus, p_minus)) for the
    Z, X, and Y bases — real quantum mechanics, not an approximation:
    Z: {|0>,|1>}, X: {|+>,|->} = (|0>+/-|1>)/sqrt(2),
    Y: {|+i>,|-i>} = (|0>+/-i|1>)/sqrt(2).
    """
    c, s = math.cos(theta / 2.0), math.sin(theta / 2.0)
    alpha = complex(c, 0.0)
    beta = complex(s * math.cos(phi), s * math.sin(phi))  # s * e^{i phi}

    p0 = abs(alpha) ** 2
    p1 = abs(beta) ** 2

    # X basis: |+> = (|0>+|1>)/sqrt2, |-> = (|0>-|1>)/sqrt2
    amp_plus = (alpha + beta) / math.sqrt(2)
    amp_minus = (alpha - beta) / math.sqrt(2)
    px_plus, px_minus = abs(amp_plus) ** 2, abs(amp_minus) ** 2

    # Y basis: |+i> = (|0>+i|1>)/sqrt2, |-i> = (|0>-i|1>)/sqrt2.
    # Projection amplitude is <+i|psi> = (<0| - i<1|)/sqrt2 . psi -- the
    # bra conjugates the i in the ket to -i. (Caught by testing: with the
    # sign the other way around, theta=90,phi=90 -- which IS |+i> by the
    # definition above -- came out reporting 100% probability of being
    # |-i> instead of |+i>. This is the corrected, verified version.)
    amp_pi = (alpha - 1j * beta) / math.sqrt(2)
    amp_mi = (alpha + 1j * beta) / math.sqrt(2)
    py_plus, py_minus = abs(amp_pi) ** 2, abs(amp_mi) ** 2

    return {
        "Z": (p0, p1),
        "X": (px_plus, px_minus),
        "Y": (py_plus, py_minus),
    }


def bloch_vector(theta, phi):
    """The real-space Bloch-sphere point (x,y,z) for the state at
    (theta, phi) — the standard identity that a qubit's density matrix
    rho = (I + x*sigma_x + y*sigma_y + z*sigma_z)/2 has
    (x,y,z) = (sin(theta)cos(phi), sin(theta)sin(phi), cos(theta))."""
    return (math.sin(theta) * math.cos(phi),
            math.sin(theta) * math.sin(phi),
            math.cos(theta))


def render_bloch_sphere(theta_deg=90.0, phi_deg=0.0, out_name=None):
    """Bloch sphere for |psi> = cos(theta/2)|0> + e^{i phi}sin(theta/2)|1>,
    theta_deg/phi_deg in DEGREES (matching how people naturally specify
    them, e.g. '/bloch 90 0' for the |+> state). Draws the sphere, the
    state vector, and the exact Z/X/Y measurement-probability bars —
    same information content as a standard qubit-state visualizer, all
    computed from bloch_state_probs()/bloch_vector() above, not faked."""
    if not HAVE_DEPS:
        return None
    theta = math.radians(theta_deg % 360.0)
    phi = math.radians(phi_deg % 360.0)
    x, y, z = bloch_vector(theta, phi)
    probs = bloch_state_probs(theta, phi)

    fig = plt.figure(figsize=(10.5, 5.2), facecolor=BG)
    ax3d = fig.add_subplot(1, 2, 1, projection="3d")
    ax3d.set_facecolor(BG)
    fig.patch.set_facecolor(BG)

    # wireframe sphere
    u = np.linspace(0, 2 * math.pi, 40)
    v = np.linspace(0, math.pi, 24)
    sx = np.outer(np.cos(u), np.sin(v))
    sy = np.outer(np.sin(u), np.sin(v))
    sz = np.outer(np.ones_like(u), np.cos(v))
    ax3d.plot_wireframe(sx, sy, sz, color="#3b4261", linewidth=0.4, alpha=0.6)

    # equator + prime meridian for orientation
    t = np.linspace(0, 2 * math.pi, 200)
    ax3d.plot(np.cos(t), np.sin(t), 0, color="#565f89", lw=0.8)
    ax3d.plot(np.cos(t), np.zeros_like(t), np.sin(t), color="#414868", lw=0.6)

    # axis lines + basis-state labels
    axis_len = 1.35
    for (dx, dy, dz), label in [
        ((0, 0, 1), "|0\u27e9"), ((0, 0, -1), "|1\u27e9"),
        ((1, 0, 0), "|+\u27e9"), ((-1, 0, 0), "|\u2212\u27e9"),
        ((0, 1, 0), "|+i\u27e9"), ((0, -1, 0), "|\u2212i\u27e9"),
    ]:
        ax3d.plot([0, dx * axis_len], [0, dy * axis_len], [0, dz * axis_len],
                   color="#565f89", lw=0.7)
        ax3d.text(dx * axis_len * 1.15, dy * axis_len * 1.15, dz * axis_len * 1.15,
                   label, color="#c0caf5", fontsize=9, family="monospace", ha="center")

    # the actual state vector
    ax3d.plot([0, x], [0, y], [0, z], color="#ff9e64", lw=2.6)
    ax3d.scatter([x], [y], [z], color="#ff9e64", s=60, depthshade=False)

    ax3d.set_xlim(-1.2, 1.2); ax3d.set_ylim(-1.2, 1.2); ax3d.set_zlim(-1.2, 1.2)
    ax3d.set_box_aspect((1, 1, 1))
    ax3d.set_axis_off()
    ax3d.set_title(f"|\u03c8\u27e9 = cos(\u03b8/2)|0\u27e9 + e^{{i\u03c6}}sin(\u03b8/2)|1\u27e9"
                    f"   \u03b8={theta_deg:.0f}\u00b0 \u03c6={phi_deg:.0f}\u00b0",
                    color="#c0caf5", fontsize=9.5, family="monospace", pad=0)

    # measurement-probability bars, exact values from bloch_state_probs
    ax2d = fig.add_subplot(1, 2, 2)
    _no_axes(ax2d)
    bases = ["Z", "X", "Y"]
    plus_labels = {"Z": "|0\u27e9", "X": "|+\u27e9", "Y": "|+i\u27e9"}
    minus_labels = {"Z": "|1\u27e9", "X": "|\u2212\u27e9", "Y": "|\u2212i\u27e9"}
    bar_colors = {"Z": "#7dcfff", "X": "#ff7f9a", "Y": "#9ece6a"}
    xpos = np.arange(len(bases)) * 2.2
    for i, b in enumerate(bases):
        pplus, pminus = probs[b]
        ax2d.bar(xpos[i] - 0.35, pplus, width=0.6, color=bar_colors[b], alpha=0.95)
        ax2d.bar(xpos[i] + 0.35, pminus, width=0.6, color=bar_colors[b], alpha=0.45)
        ax2d.text(xpos[i] - 0.35, pplus + 0.03, f"{pplus*100:.1f}%", ha="center",
                   color="#c0caf5", fontsize=8, family="monospace")
        ax2d.text(xpos[i] + 0.35, pminus + 0.03, f"{pminus*100:.1f}%", ha="center",
                   color="#c0caf5", fontsize=8, family="monospace")
        ax2d.text(xpos[i] - 0.35, -0.09, plus_labels[b], ha="center",
                   color="#c0caf5", fontsize=8, family="monospace")
        ax2d.text(xpos[i] + 0.35, -0.09, minus_labels[b], ha="center",
                   color="#c0caf5", fontsize=8, family="monospace")
        ax2d.text(xpos[i], 1.12, f"{b}-basis", ha="center",
                   color="#e8ebfa", fontsize=9.5, family="monospace", weight="bold")
    ax2d.set_ylim(-0.18, 1.25)
    ax2d.set_xlim(-1.2, xpos[-1] + 1.2)
    _caption(ax2d, "EXACT MEASUREMENT PROBABILITIES (Born rule, |amplitude|\u00b2)")

    path = os.path.join(_export_dir("simulations"), out_name or "bloch_sphere.png")
    fig.savefig(path, dpi=170, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path
