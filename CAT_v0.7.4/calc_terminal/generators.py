"""
Random numerical generators. Each returns a dict describing one full
notebook: Question -> Given -> Find -> Formula -> Substitution ->
Calculation -> Units -> Verification -> Final Answer.

`formula` / `substitution` are lists of parts consumed by
mathtext.compose() (plain strings or frac_part(num, den) tuples).
"""

import math
import random

from .mathtext import frac_part as F, sub, sup


def r(n, d=3):
    return round(n, d)


def first_order():
    t = random.choice([10, 15, 20, 25, 30, 40])
    ratio = random.choice([2, 3, 4, 5])
    R = random.choice([0.1, 0.2, 0.4, 0.5, 0.8, 1.0])
    R0 = r(R * ratio, 3)
    k = (2.303 / t) * math.log10(ratio)
    half_life = 0.693 / k

    return {
        "intent": "first",
        "topic": "Chemical Kinetics \u00b7 First Order",
        "question": f"A first order reaction has an initial concentration [R]{sub(0)} = {R0} mol/L, "
                    f"which falls to [R] = {R} mol/L in {t} minutes. Find the rate constant k.",
        "given": [
            f"Initial concentration [R]{sub(0)} = {R0} mol/L",
            f"Concentration after time t, [R] = {R} mol/L",
            f"Time, t = {t} min",
        ],
        "find": "Rate constant, k",
        "formula": ["k = ", F("2.303", "t"), f"  log([R]{sub(0)}/[R])"],
        "substitution": ["k = ", F("2.303", str(t)), f"  log({R0}/{R})"],
        "calculation": [
            f"[R]{sub(0)}/[R] = {R0}/{R} = {r(R0/R,3)}",
            f"log({r(R0/R,3)}) = {r(math.log10(ratio),4)}",
            f"k = (2.303 / {t}) \u00d7 {r(math.log10(ratio),4)} = {r(k,5)} min{sup('-1')}",
        ],
        "unit": f"k is expressed in time{sup('-1')} (here, min{sup('-1')}) — first-order rate constants are independent of concentration units.",
        "verification": f"Using k = {r(k,5)} min{sup('-1')}, half-life t\u00bd = 0.693/k \u2248 {r(half_life,2)} min, "
                        f"consistent with the concentration more than halving over {t} min. \u2713",
        "final_answer": f"k \u2248 {r(k,5)} min{sup('-1')}",
    }


def zero_order():
    R0 = random.choice([1.0, 0.8, 0.6, 0.5])
    t = random.choice([10, 20, 30, 40])
    frac_remaining = random.choice([0.9, 0.85, 0.8, 0.75, 0.7])
    R = r(R0 * frac_remaining, 3)
    k = r((R0 - R) / t, 5)

    return {
        "intent": "zero",
        "topic": "Chemical Kinetics \u00b7 Zero Order",
        "question": f"A zero order reaction starts with [R]{sub(0)} = {R0} mol/L and after {t} minutes "
                    f"the concentration falls to [R] = {R} mol/L. Find k.",
        "given": [
            f"Initial concentration [R]{sub(0)} = {R0} mol/L",
            f"Concentration after time t, [R] = {R} mol/L",
            f"Time, t = {t} min",
        ],
        "find": "Rate constant, k",
        "formula": ["k = ", F(f"[R]{sub(0)} \u2212 [R]", "t")],
        "substitution": ["k = ", F(f"{R0} \u2212 {R}", str(t))],
        "calculation": [
            f"[R]{sub(0)} \u2212 [R] = {R0} \u2212 {R} = {r(R0-R,3)} mol/L",
            f"k = {r(R0-R,3)} / {t} = {k} mol L{sup(-1)} min{sup(-1)}",
        ],
        "unit": f"k is expressed in mol L{sup(-1)} time{sup(-1)} for a zero order reaction, since rate is concentration-independent.",
        "verification": f"Check: [R] = [R]{sub(0)} \u2212 kt = {R0} \u2212 ({k}\u00d7{t}) = {r(R0-k*t,3)} mol/L, matching the given value. \u2713",
        "final_answer": f"k \u2248 {k} mol L{sup(-1)} min{sup(-1)}",
    }


def second_order():
    R0 = random.choice([0.5, 1, 1.5, 2])
    t = random.choice([10, 20, 30])
    k = random.choice([0.01, 0.02, 0.03, 0.05])
    R = r(1 / ((1 / R0) + k * t), 4)

    return {
        "intent": "second",
        "topic": "Chemical Kinetics \u00b7 Second Order",
        "question": f"For a second order reaction, [R]{sub(0)} = {R0} mol/L and k = {k} L mol{sup(-1)} min{sup(-1)}. "
                    f"Find [R] after {t} minutes.",
        "given": [
            f"Initial concentration [R]{sub(0)} = {R0} mol/L",
            f"Rate constant k = {k} L mol{sup(-1)} min{sup(-1)}",
            f"Time, t = {t} min",
        ],
        "find": "Concentration [R] at time t",
        "formula": [F("1", "[R]"), " = ", F("1", f"[R]{sub(0)}"), " + kt"],
        "substitution": [F("1", "[R]"), " = ", F("1", str(R0)), f" + ({k})({t})"],
        "calculation": [
            f"1/{R0} = {r(1/R0,4)}",
            f"kt = {k} \u00d7 {t} = {r(k*t,4)}",
            f"1/[R] = {r(1/R0,4)} + {r(k*t,4)} = {r((1/R0)+k*t,4)}",
            f"[R] = 1 / {r((1/R0)+k*t,4)} = {R} mol/L",
        ],
        "unit": f"k is expressed in L mol{sup(-1)} time{sup(-1)} for a second order reaction.",
        "verification": f"[R] = {R} mol/L is less than [R]{sub(0)} = {R0} mol/L, confirming concentration decreased over time. \u2713",
        "final_answer": f"[R] \u2248 {R} mol/L",
    }

def third_order():
    R0 = random.choice([0.5, 1, 1.5, 2])
    t = random.choice([5, 10, 15])
    k = random.choice([0.005, 0.01, 0.015])
    R_sq_inv = (1 / R0**2) + 2 * k * t
    R = r(1 / math.sqrt(R_sq_inv), 4)

    return {
        "intent": "third",
        "topic": "Chemical Kinetics \u00b7 Third Order",
        "question": f"For a third order reaction, [R]{sub(0)} = {R0} mol/L and k = {k} L{sup(2)} mol{sup(-2)} min{sup(-1)}. "
                    f"Find [R] after {t} minutes.",
        "given": [
            f"Initial concentration [R]{sub(0)} = {R0} mol/L",
            f"Rate constant k = {k} L{sup(2)} mol{sup(-2)} min{sup(-1)}",
            f"Time, t = {t} min",
        ],
        "find": "Concentration [R] at time t",
        "formula": [F("1", "[R]" + sup(2)), " = ", F("1", f"[R]{sub(0)}" + sup(2)), " + 2kt"],
        "substitution": [F("1", "[R]" + sup(2)), " = ", F("1", str(R0) + sup(2)), f" + 2({k})({t})"],
        "calculation": [
            f"1/({R0}){sup(2)} = {r(1/R0**2,4)}",
            f"2kt = 2 \u00d7 {k} \u00d7 {t} = {r(2*k*t,4)}",
            f"1/[R]{sup(2)} = {r(1/R0**2,4)} + {r(2*k*t,4)} = {r(R_sq_inv,4)}",
            f"[R] = \u221a(1 / {r(R_sq_inv,4)}) = {R} mol/L",
        ],
        "unit": f"k is expressed in L{sup(2)} mol{sup(-2)} time{sup(-1)} for a third order reaction.",
        "verification": f"[R] = {R} mol/L is less than [R]{sub(0)} = {R0} mol/L, confirming concentration decreased over time. \u2713",
        "final_answer": f"[R] \u2248 {R} mol/L",
    }


def half_life():
    t_half = random.choice([10, 15, 20, 25, 30, 40, 60])
    k = r(0.693 / t_half, 5)
    t75 = r(2 * t_half, 2)

    return {
        "intent": "halflife",
        "topic": "Chemical Kinetics \u00b7 Half-Life",
        "question": f"A first order reaction has a half-life of {t_half} minutes. "
                    f"Find the rate constant k and the time required for 75% completion.",
        "given": [f"Half-life, t\u00bd = {t_half} min", "Reaction order = first order"],
        "find": "Rate constant k, and time for 75% completion",
        "formula": ["k = ", F("0.693", "t\u00bd")],
        "substitution": ["k = ", F("0.693", str(t_half))],
        "calculation": [
            f"k = 0.693 / {t_half} = {k} min{sup(-1)}",
            "75% completion = 2 half-lives elapsed",
            f"t(75%) = 2 \u00d7 t\u00bd = 2 \u00d7 {t_half} = {t75} min",
        ],
        "unit": f"k is in min{sup(-1)}; t(75%) is in minutes.",
        "verification": f"After 2 half-lives, concentration falls to (1/2)\u00b2 = 1/4 of initial — "
                        f"i.e. 75% has reacted, consistent with t(75%) = {t75} min. \u2713",
        "final_answer": f"k \u2248 {k} min{sup(-1)}, t(75%) \u2248 {t75} min",
    }


def arrhenius():
    Ea = random.choice([50, 60, 75, 90, 100]) * 1000
    T1 = random.choice([290, 300, 310])
    T2 = T1 + random.choice([10, 15, 20])
    k1 = random.choice([1e-4, 2e-4, 3.2e-4, 5e-4])
    R = 8.314
    ln_ratio = (-Ea / R) * ((1 / T2) - (1 / T1))
    k2 = k1 * math.exp(ln_ratio)

    return {
        "intent": "arrhenius",
        "topic": "Chemical Kinetics \u00b7 Arrhenius Equation",
        "question": f"A reaction has activation energy Ea = {Ea/1000} kJ/mol and rate constant "
                    f"k{sub(1)} = {k1:.2e} s{sup(-1)} at T{sub(1)} = {T1} K. Find k{sub(2)} at T{sub(2)} = {T2} K.",
        "given": [
            f"Activation energy, Ea = {Ea/1000} kJ/mol = {Ea} J/mol",
            f"k{sub(1)} = {k1:.2e} s{sup(-1)} at T{sub(1)} = {T1} K",
            f"T{sub(2)} = {T2} K",
            "R = 8.314 J mol\u207b\u00b9 K\u207b\u00b9",
        ],
        "find": f"Rate constant k{sub(2)} at T{sub(2)}",
        "formula": [f"ln", F(f"k{sub(2)}", f"k{sub(1)}"), " = ", F("\u2212Ea", "R"),
                    "  \u00d7  (", F("1", f"T{sub(2)}"), " \u2212 ", F("1", f"T{sub(1)}"), ")"],
        "substitution": [f"ln", F(f"k{sub(2)}", f"k{sub(1)}"), " = ", F(f"\u2212{Ea}", "8.314"),
                          f"  \u00d7  (", F("1", str(T2)), " \u2212 ", F("1", str(T1)), ")"],
        "calculation": [
            f"1/T{sub(2)} \u2212 1/T{sub(1)} = {r((1/T2)-(1/T1),8)} K{sup(-1)}",
            f"ln(k{sub(2)}/k{sub(1)}) = {r(ln_ratio,4)}",
            f"k{sub(2)}/k{sub(1)} = e^{r(ln_ratio,4)} = {r(math.exp(ln_ratio),4)}",
            f"k{sub(2)} = {k1:.2e} \u00d7 {r(math.exp(ln_ratio),4)} = {k2:.3e} s{sup(-1)}",
        ],
        "unit": f"k keeps the units of the given rate constant (s{sup(-1)}); Ea is in J/mol when paired with R = 8.314 J mol{sup(-1)} K{sup(-1)}.",
        "verification": f"Since T{sub(2)} > T{sub(1)}, k should increase — k{sub(2)} = {k2:.3e} s{sup(-1)} "
                        f"is indeed larger than k{sub(1)} = {k1:.2e} s{sup(-1)}. \u2713",
        "final_answer": f"k{sub(2)} \u2248 {k2:.3e} s{sup(-1)}",
    }


COMPOUNDS = [
    ("NaOH", 40), ("CaCO3", 100), ("H2SO4", 98),
    ("C6H12O6 (glucose)", 180), ("NaCl", 58.5), ("CO2", 44),
]


def mole_concept():
    name, M = random.choice(COMPOUNDS)
    mass = random.choice([2, 4, 5, 8, 10, 20, 25])
    moles = r(mass / M, 4)

    return {
        "intent": "mole",
        "topic": "Mole Concept",
        "question": f"Calculate the number of moles present in {mass} g of {name}.",
        "given": [f"Mass of {name} = {mass} g", f"Molar mass of {name}, M = {M} g/mol"],
        "find": "Number of moles, n",
        "formula": ["n = ", F("Given mass", "Molar mass"), " = ", F("m", "M")],
        "substitution": ["n = ", F(f"{mass} g", f"{M} g/mol")],
        "calculation": [f"n = {mass} / {M} = {moles} mol"],
        "unit": "Moles are a pure count and carry the unit mol.",
        "verification": f"Reversing: mass = n \u00d7 M = {moles} \u00d7 {M} = {r(moles*M,2)} g, matching the given mass. \u2713",
        "final_answer": f"n \u2248 {moles} mol",
    }


GENERATORS = {
    "first": first_order,
    "zero": zero_order,
    "second": second_order,
    "third": third_order,
    "halflife": half_life,
    "arrhenius": arrhenius,
    "mole": mole_concept,
}

KINETICS_ORDER = ["zero", "first", "second", "third", "halflife", "arrhenius"]
