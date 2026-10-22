"""
Universal Chemistry Formula Calculator.

Two modes:

1. Library mode — pick any of ~35 real chemistry formulas spanning
   kinetics, gas laws, thermodynamics, electrochemistry, equilibrium,
   solutions and atomic/quantum structure. Supply the values you know,
   leave the one you want blank, and it's solved symbolically with
   sympy for the missing variable — not hardcoded per-direction code.

2. Free-form mode — type ANY formula (e.g. "P*V = n*R*T" or
   "y = m*x + c") plus known variable=value pairs, and calc_terminal
   solves for whatever's left, using real symbolic algebra.
"""

try:
    import sympy as sp
    _HAS_SYMPY = True
except ImportError:
    sp = None
    _HAS_SYMPY = False

CONSTANTS = {
    "R": 8.314,        # J / (mol K)
    "Rgas_atm": 0.0821,  # L atm / (mol K)
    "NA": 6.022e23,    # Avogadro's number
    "h": 6.626e-34,    # Planck's constant, J s
    "c": 3.0e8,        # speed of light, m/s
    "k_B": 1.381e-23,  # Boltzmann constant
    "F": 96500,        # Faraday constant, C/mol
    "e": 2.71828182845904523536,
    "pi": 3.14159265358979323846,
    "Rinf": 1.097e7,   # Rydberg constant, 1/m
    "a0": 5.29e-11,    # Bohr radius, m
    "me": 9.109e-31,   # electron mass, kg
}

# Each entry: id -> (Display name, category, "lhs = rhs" string, {symbol: description})
FORMULA_LIBRARY = {
    "kin_zero":      ("Zero Order Kinetics", "Kinetics", "R = R0 - k*t",
                       {"R": "concentration at t", "R0": "initial concentration", "k": "rate constant", "t": "time"}),
    "kin_first":     ("First Order Rate Law", "Kinetics", "k = (2.303/t) * log(R0/R, 10)",
                       {"k": "rate constant", "t": "time", "R0": "initial concentration", "R": "concentration at t"}),
    "kin_second":    ("Second Order Kinetics", "Kinetics", "1/R = 1/R0 + k*t",
                       {"R": "concentration at t", "R0": "initial concentration", "k": "rate constant", "t": "time"}),
    "kin_third":     ("Third Order Kinetics", "Kinetics", "1/R**2 = 1/R0**2 + 2*k*t",
                       {"R": "concentration at t", "R0": "initial concentration", "k": "rate constant", "t": "time"}),
    "half_life_1":   ("First Order Half-Life", "Kinetics", "t_half = 0.693/k",
                       {"t_half": "half life", "k": "rate constant"}),
    "half_life_0":   ("Zero Order Half-Life", "Kinetics", "t_half = R0/(2*k)",
                       {"t_half": "half life", "R0": "initial concentration", "k": "rate constant"}),
    "half_life_2":   ("Second Order Half-Life", "Kinetics", "t_half = 1/(k*R0)",
                       {"t_half": "half life", "k": "rate constant", "R0": "initial concentration"}),
    "arrhenius":     ("Arrhenius Equation", "Kinetics", "k = A * exp(-Ea/(R*T))",
                       {"k": "rate constant", "A": "pre-exponential factor", "Ea": "activation energy (J/mol)",
                        "R": "gas constant", "T": "temperature (K)"}),
    "ideal_gas":     ("Ideal Gas Law", "Gas Laws", "P*V = n*R*T",
                       {"P": "pressure", "V": "volume", "n": "moles", "R": "gas constant", "T": "temperature (K)"}),
    "boyles":        ("Boyle's Law", "Gas Laws", "P1*V1 = P2*V2",
                       {"P1": "initial pressure", "V1": "initial volume", "P2": "final pressure", "V2": "final volume"}),
    "charles":       ("Charles's Law", "Gas Laws", "V1/T1 = V2/T2",
                       {"V1": "initial volume", "T1": "initial temp (K)", "V2": "final volume", "T2": "final temp (K)"}),
    "gay_lussac":    ("Gay-Lussac's Law", "Gas Laws", "P1/T1 = P2/T2",
                       {"P1": "initial pressure", "T1": "initial temp (K)", "P2": "final pressure", "T2": "final temp (K)"}),
    "combined_gas":  ("Combined Gas Law", "Gas Laws", "(P1*V1)/T1 = (P2*V2)/T2",
                       {"P1": "P initial", "V1": "V initial", "T1": "T initial", "P2": "P final", "V2": "V final", "T2": "T final"}),
    "van_der_waals": ("Van der Waals Equation", "Gas Laws", "(P + a*n**2/V**2) * (V - n*b) = n*R*T",
                       {"P": "pressure", "a": "vdW constant a", "n": "moles", "V": "volume", "b": "vdW constant b",
                        "R": "gas constant", "T": "temperature"}),
    "molarity":      ("Molarity", "Solutions", "M = n/V",
                       {"M": "molarity (mol/L)", "n": "moles of solute", "V": "volume of solution (L)"}),
    "moles_mass":    ("Moles from Mass", "Mole Concept", "n = m/Mm",
                       {"n": "moles", "m": "mass (g)", "Mm": "molar mass (g/mol)"}),
    "dilution":      ("Dilution Law", "Solutions", "C1*V1 = C2*V2",
                       {"C1": "initial conc.", "V1": "initial volume", "C2": "final conc.", "V2": "final volume"}),
    "ph":            ("pH from [H+]", "Equilibrium/Acid-Base", "pH = -log(H, 10)",
                       {"pH": "pH", "H": "[H+] concentration (mol/L)"}),
    "poh":           ("pOH from [OH-]", "Equilibrium/Acid-Base", "pOH = -log(OH, 10)",
                       {"pOH": "pOH", "OH": "[OH-] concentration (mol/L)"}),
    "ph_poh":        ("pH + pOH = 14", "Equilibrium/Acid-Base", "pH + pOH = 14",
                       {"pH": "pH", "pOH": "pOH"}),
    "henderson":     ("Henderson-Hasselbalch", "Equilibrium/Acid-Base", "pH = pKa + log(A/HA, 10)",
                       {"pH": "pH", "pKa": "acid dissociation constant (pKa)", "A": "[conjugate base]", "HA": "[acid]"}),
    "kw":            ("Ion Product of Water", "Equilibrium/Acid-Base", "H*OH = 1.0e-14",
                       {"H": "[H+]", "OH": "[OH-]"}),
    "nernst":        ("Nernst Equation", "Electrochemistry", "Ecell = Ecell0 - (0.0592/n) * log(Q, 10)",
                       {"Ecell": "cell potential", "Ecell0": "standard cell potential", "n": "electrons transferred", "Q": "reaction quotient"}),
    "faraday":       ("Faraday's Law of Electrolysis", "Electrochemistry", "m = (M*I*t)/(n*F)",
                       {"m": "mass deposited (g)", "M": "molar mass", "I": "current (A)", "t": "time (s)",
                        "n": "electrons transferred", "F": "Faraday constant"}),
    "gibbs":         ("Gibbs Free Energy", "Thermodynamics", "dG = dH - T*dS",
                       {"dG": "Gibbs free energy change", "dH": "enthalpy change", "T": "temperature (K)", "dS": "entropy change"}),
    "gibbs_cell":    ("Gibbs Energy <-> Cell Potential", "Thermodynamics", "dG = -n*F*Ecell",
                       {"dG": "Gibbs free energy change", "n": "electrons transferred", "F": "Faraday constant", "Ecell": "cell potential"}),
    "eq_gibbs":      ("Gibbs Energy <-> Equilibrium Const.", "Thermodynamics", "dG0 = -R*T*log(K)",
                       {"dG0": "standard Gibbs free energy", "R": "gas constant", "T": "temperature (K)", "K": "equilibrium constant"}),
    "clausius":      ("Clausius-Clapeyron Equation", "Thermodynamics",
                       "log(P2/P1) = -(dHvap/R) * (1/T2 - 1/T1)",
                       {"P2": "vapor pressure at T2", "P1": "vapor pressure at T1", "dHvap": "enthalpy of vaporization",
                        "R": "gas constant", "T2": "temp 2 (K)", "T1": "temp 1 (K)"}),
    "raoult":        ("Raoult's Law", "Solutions", "Psoln = Xsolvent * P0",
                       {"Psoln": "vapor pressure of solution", "Xsolvent": "mole fraction of solvent", "P0": "pure solvent vapor pressure"}),
    "osmotic":       ("Osmotic Pressure", "Solutions", "Pi = M*R*T",
                       {"Pi": "osmotic pressure", "M": "molarity", "R": "gas constant", "T": "temperature (K)"}),
    "freezing_dep":  ("Freezing Point Depression", "Solutions", "dTf = Kf*m*i",
                       {"dTf": "freezing point depression", "Kf": "cryoscopic constant", "m": "molality", "i": "van't Hoff factor"}),
    "boiling_elev":  ("Boiling Point Elevation", "Solutions", "dTb = Kb*m*i",
                       {"dTb": "boiling point elevation", "Kb": "ebullioscopic constant", "m": "molality", "i": "van't Hoff factor"}),
    "planck":        ("Planck's Energy Equation", "Atomic/Quantum", "E = h*f",
                       {"E": "photon energy (J)", "h": "Planck's constant", "f": "frequency (Hz)"}),
    "photon_wave":   ("Photon Energy from Wavelength", "Atomic/Quantum", "E = (h*c)/lam",
                       {"E": "photon energy (J)", "h": "Planck's constant", "c": "speed of light", "lam": "wavelength (m)"}),
    "de_broglie":    ("De Broglie Wavelength", "Atomic/Quantum", "lam = h/(m*v)",
                       {"lam": "wavelength", "h": "Planck's constant", "m": "mass (kg)", "v": "velocity (m/s)"}),
    "rydberg":       ("Rydberg Equation", "Atomic/Quantum", "invlam = Rinf*(1/n1**2 - 1/n2**2)",
                       {"invlam": "1/wavelength (1/m)", "Rinf": "Rydberg constant", "n1": "lower level", "n2": "higher level"}),
    "bohr_energy":   ("Bohr Energy Level", "Atomic/Quantum", "En = -2.18e-18/n**2",
                       {"En": "orbit energy (J)", "n": "principal quantum number"}),
    "bohr_radius":   ("Bohr Radius of Orbit", "Atomic/Quantum", "rn = a0*n**2/Z",
                       {"rn": "orbit radius (m)", "a0": "Bohr radius const.", "n": "principal quantum number", "Z": "atomic number"}),
    "heisenberg":    ("Heisenberg Uncertainty Principle", "Atomic/Quantum", "dx*dp = h/(4*pi)",
                       {"dx": "position uncertainty", "dp": "momentum uncertainty", "h": "Planck's constant", "pi": "pi"}),
    "avg_ke_gas":    ("Average KE of Gas Molecule", "Thermodynamics", "KE = (3/2)*k_B*T",
                       {"KE": "average kinetic energy", "k_B": "Boltzmann constant", "T": "temperature (K)"}),
}

CATEGORIES = sorted({v[1] for v in FORMULA_LIBRARY.values()})


class SolveError(Exception):
    pass


def _make_symbols(names):
    return {n: sp.Symbol(n, real=True) for n in names}


def solve_formula(formula_str, known, solve_for, extra_constants=None):
    """
    formula_str: "lhs = rhs" style string, e.g. "P*V = n*R*T"
    known: dict of {symbol_name: numeric value} for everything EXCEPT solve_for
    solve_for: name of the symbol to solve for
    Returns: (numeric_result, sympy_equation_used)
    """
    if not _HAS_SYMPY:
        raise SolveError("sympy is not installed. Run: pip install sympy --break-system-packages "
                          "(or 'pip install -r requirements.txt') to enable /solve.")
    if "=" not in formula_str:
        raise SolveError("Formula must contain '=' (e.g. 'P*V = n*R*T').")
    lhs_s, rhs_s = formula_str.split("=", 1)

    const_ns = dict(CONSTANTS)
    if extra_constants:
        const_ns.update(extra_constants)

    all_names = set(known) | {solve_for}
    # discover any additional free symbols mentioned in the formula text
    import re as _re
    tokens = set(_re.findall(r"[A-Za-z_][A-Za-z_0-9]*", formula_str))
    tokens -= {"log", "exp", "sqrt", "sin", "cos", "tan"}
    all_names |= tokens

    symtab = _make_symbols(all_names)
    local_dict = dict(symtab)
    local_dict.update({
        "log": sp.log, "exp": sp.exp, "sqrt": sp.sqrt,
        "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
    })

    try:
        lhs = sp.sympify(lhs_s.strip(), locals=local_dict)
        rhs = sp.sympify(rhs_s.strip(), locals=local_dict)
    except Exception as exc:
        raise SolveError(f"Could not parse formula: {exc}")

    eq = sp.Eq(lhs, rhs)

    # substitute known numeric values (and any constants the formula uses,
    # e.g. R, h, c, NA, F, Rinf, a0, pi, e — unless the user overrides them)
    subs = {}
    for name, val in known.items():
        if name in symtab:
            subs[symtab[name]] = val
    for name, val in const_ns.items():
        if name in symtab and name not in known and name != solve_for:
            subs[symtab[name]] = val

    eq_sub = eq.subs(subs)

    target = symtab[solve_for]
    if target not in eq_sub.free_symbols:
        raise SolveError(f"'{solve_for}' does not appear in this formula, or all values were already substituted.")

    solutions = sp.solve(eq_sub, target)
    if not solutions:
        raise SolveError("No solution found — check the values you supplied.")

    numeric = []
    for s in solutions:
        try:
            numeric.append(complex(sp.N(s)))
        except Exception:
            continue
    if not numeric:
        raise SolveError("Solution is symbolic / non-numeric — supply more known values.")

    # prefer the real, positive root when several exist (typical in chemistry)
    real_candidates = [z.real for z in numeric if abs(z.imag) < 1e-9]
    if real_candidates:
        positives = [v for v in real_candidates if v > 0]
        result = positives[0] if positives else real_candidates[0]
    else:
        result = numeric[0]

    return result, eq


def pretty(obj):
    """Render a formula string (e.g. 'P*V = n*R*T') or a sympy Eq/expr as
    notebook-style text: division becomes a stacked fraction bar (never
    '/'), multiplication becomes 'x' (never '*'). Falls back to a plain
    text substitution if sympy isn't available or parsing fails.
    """
    def _fallback(s):
        s = str(s).replace("**", "^")
        # collapse "a*b*c" -> "a x b x c" without touching '**' (already gone)
        return " x ".join(p.strip() for p in s.split("*"))

    if not _HAS_SYMPY:
        return _fallback(obj)

    try:
        if isinstance(obj, str):
            import re as _re
            if "=" in obj:
                lhs_s, rhs_s = obj.split("=", 1)
                tokens = set(_re.findall(r"[A-Za-z_][A-Za-z_0-9]*", obj))
                tokens -= {"log", "exp", "sqrt", "sin", "cos", "tan"}
                local_dict = dict(_make_symbols(tokens))
                local_dict.update({
                    "log": sp.log, "exp": sp.exp, "sqrt": sp.sqrt,
                    "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
                })
                expr = sp.Eq(sp.sympify(lhs_s.strip(), locals=local_dict),
                             sp.sympify(rhs_s.strip(), locals=local_dict))
            else:
                expr = sp.sympify(obj)
        else:
            expr = obj
        out = sp.pretty(expr, use_unicode=True)
    except Exception:
        return _fallback(obj)

    # sympy's pretty-printer uses "\u22c5" (dot) for multiplication; the
    # house style here is "x", never "*" or a bare dot.
    out = out.replace("\u22c5", " x ")
    return out


def solve_library_formula(key, known):
    """Solve a named formula from FORMULA_LIBRARY. `known` must contain
    every variable except exactly one (the one being solved for)."""
    if key not in FORMULA_LIBRARY:
        raise SolveError(f"Unknown formula id: {key}")
    name, category, formula_str, var_desc = FORMULA_LIBRARY[key]
    all_vars = set(var_desc)
    missing = all_vars - set(known)
    if len(missing) != 1:
        raise SolveError(
            f"Give values for exactly all-but-one variable. "
            f"Variables: {', '.join(sorted(all_vars))}. Missing/target: {', '.join(missing) or 'none'}"
        )
    solve_for = next(iter(missing))
    result, eq = solve_formula(formula_str, known, solve_for)
    return solve_for, result, name, category, eq
