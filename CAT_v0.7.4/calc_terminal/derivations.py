"""
Real calculus derivations for chemical kinetics rate laws.

These are NOT random numericals — they are the actual step-by-step
derivation of the integrated rate law from the differential rate law,
using proper mathematical notation (stacked fractions via mathtext,
"x" for multiplication, integral signs, etc.), the way it is worked
out on paper / on a board.

Each function returns a dict consumed by engine.render_derivation():
    topic, goal, steps: [(label, [compose-parts]), ...], result, note
"""

from .mathtext import frac_part as F, sub, sup

MUL = "\u00d7"          # x   (never "*")
INT = "\u222b"          # integral sign
DDT = "d[R]/dt"


def zero_order_derivation():
    steps = [
        ("Rate law (differential form)",
         [f"Rate = \u2212d[R]/dt = k[R]", sup(0), " = k"]),
        ("Separate the variables",
         ["\u2212d[R] = k ", "dt"]),
        ("Integrate both sides",
         [INT, " ", "from [R]", sub(0), " to [R]", "  \u2212d[R]  =  k ", INT, " from 0 to t  dt"]),
        ("Evaluate the integral",
         ["\u2212([R] \u2212 [R]", sub(0), ") = k(t \u2212 0)"]),
        ("Rearrange for [R]",
         ["[R] = [R]", sub(0), " \u2212 kt"]),
        ("Solve for k (rearranged form)",
         ["k = ", F(f"[R]{sub(0)} \u2212 [R]", "t")]),
    ]
    return {
        "topic": "Derivation \u00b7 Zero Order Integrated Rate Law",
        "goal": "Derive [R] = [R]\u2080 \u2212 kt starting from the differential rate law of a zero order reaction.",
        "steps": steps,
        "result": f"[R] = [R]{sub(0)} \u2212 kt      (equivalently  k = ([R]{sub(0)} \u2212 [R]) / t )",
        "note": "For a zero order reaction the rate is independent of concentration, so [R] falls "
                "LINEARLY with time \u2014 a straight line of slope \u2212k when [R] is plotted against t.",
    }


def first_order_derivation():
    steps = [
        ("Rate law (differential form)",
         ["Rate = \u2212d[R]/dt = k[R]"]),
        ("Separate the variables",
         ["\u2212", F("d[R]", "[R]"), " = k dt"]),
        ("Integrate both sides",
         [INT, " from [R]", sub(0), " to [R]  \u2212", F("d[R]", "[R]"), "  =  k ", INT, " from 0 to t  dt"]),
        ("Evaluate the integral (\u222bd[R]/[R] = ln[R])",
         ["\u2212(ln[R] \u2212 ln[R]", sub(0), ") = kt"]),
        ("Combine logarithms",
         ["ln(", f"[R]{sub(0)}", "/[R]) = kt"]),
        ("Solve for k, convert ln \u2192 log", 
         ["k = ", F("1", "t"), " ln(", f"[R]{sub(0)}", "/[R])  =  ", F("2.303", "t"),
          f"  log{sub(10)}([R]{sub(0)}/[R])"]),
    ]
    return {
        "topic": "Derivation \u00b7 First Order Integrated Rate Law",
        "goal": "Derive k = (2.303/t) log([R]\u2080/[R]) starting from the differential rate law of a first order reaction.",
        "steps": steps,
        "result": f"k = (2.303/t) \u00d7 log{sub(10)}([R]{sub(0)}/[R])      (equivalently  [R] = [R]{sub(0)} e{sup('-kt')} )",
        "note": "Because the exponent is linear in t, a plot of ln[R] (or log[R]) against t is a straight "
                "line of slope \u2212k \u2014 the diagnostic test for first order kinetics.",
    }


def second_order_derivation():
    steps = [
        ("Rate law (differential form)",
         ["Rate = \u2212d[R]/dt = k[R]", sup(2)]),
        ("Separate the variables",
         ["\u2212", F("d[R]", "[R]" + sup(2)), " = k dt"]),
        ("Integrate both sides",
         [INT, " from [R]", sub(0), " to [R]  \u2212", F("d[R]", "[R]" + sup(2)), "  =  k ", INT, " from 0 to t  dt"]),
        ("Evaluate the integral (\u222bd[R]/[R]\u00b2 = \u22121/[R])",
         [F("1", "[R]"), " \u2212 ", F("1", f"[R]{sub(0)}"), " = kt"]),
        ("Rearrange", 
         [F("1", "[R]"), " = ", F("1", f"[R]{sub(0)}"), " + kt"]),
    ]
    return {
        "topic": "Derivation \u00b7 Second Order Integrated Rate Law",
        "goal": "Derive 1/[R] = 1/[R]\u2080 + kt starting from the differential rate law of a second order reaction.",
        "steps": steps,
        "result": f"1/[R] = 1/[R]{sub(0)} + kt",
        "note": "A plot of 1/[R] against t is a straight line of slope +k \u2014 the diagnostic test for "
                "second order kinetics (unlike zero order, which is linear in [R] itself).",
    }

def third_order_derivation():
    steps = [
        ("Rate law (differential form)",
         ["Rate = \u2212d[R]/dt = k[R]", sup(3)]),
        ("Separate the variables",
         ["\u2212", F("d[R]", "[R]" + sup(3)), " = k dt"]),
        ("Integrate both sides",
         [INT, " from [R]", sub(0), " to [R]  \u2212", F("d[R]", "[R]" + sup(3)), "  =  k ", INT, " from 0 to t  dt"]),
        ("Evaluate the integral (\u222bdx/x\u00b3 = \u22121/(2x\u00b2))",
         [F("1", "2[R]" + sup(2)), " \u2212 ", F("1", f"2[R]{sub(0)}" + sup(2)), " = kt"]),
        ("Rearrange",
         [F("1", "[R]" + sup(2)), " = ", F("1", f"[R]{sub(0)}" + sup(2)), " + 2kt"]),
    ]
    return {
        "topic": "Derivation \u00b7 Third Order Integrated Rate Law",
        "goal": "Derive 1/[R]\u00b2 = 1/[R]\u2080\u00b2 + 2kt starting from the differential rate law of a third order reaction.",
        "steps": steps,
        "result": f"1/[R]{sup(2)} = 1/[R]{sub(0)}{sup(2)} + 2kt",
        "note": "A plot of 1/[R]\u00b2 against t is a straight line of slope +2k \u2014 the diagnostic test for "
                "third order kinetics.",
    }

def half_life_first_derivation():
    steps = [
        ("Start from the first order integrated law",
         ["k = ", F("2.303", "t"), f"  log{sub(10)}([R]{sub(0)}/[R])"]),
        (f"At t = t{sub('1/2')}, [R] = [R]",
         [f"[R] = [R]{sub(0)}/2  \u21d2  [R]{sub(0)}/[R] = 2"]),
        ("Substitute and simplify",
         ["k = ", F("2.303", f"t{sub('1/2')}"), f"  log{sub(10)}(2)"]),
        ("Use log\u2081\u2080(2) = 0.301",
         ["k = ", F("2.303 \u00d7 0.301", f"t{sub('1/2')}"), f"  =  ", F("0.693", f"t{sub('1/2')}")]),
        ("Solve for t\u2081/\u2082",
         [f"t{sub('1/2')}", " = ", F("0.693", "k")]),
    ]
    return {
        "topic": "Derivation \u00b7 First Order Half-Life",
        "goal": "Derive t\u00bd = 0.693/k from the first order integrated rate law.",
        "steps": steps,
        "result": f"t{sub('1/2')} = 0.693 / k",
        "note": "Notice [R]\u2080 cancels out completely \u2014 first order half-life does NOT depend on the "
                "starting concentration, unlike zero or second order.",
    }


DERIVATIONS = {
    "zero": zero_order_derivation,
    "first": first_order_derivation,
    "second": second_order_derivation,
    "third": third_order_derivation,
    "halflife": half_life_first_derivation,
}

DERIVATION_KEYWORDS = [
    (r"zero\s*order", "zero"),
    (r"second\s*order", "second"),
    (r"third\s*order", "third"),
    (r"half.?life", "halflife"),
    (r"first\s*order", "first"),
]
