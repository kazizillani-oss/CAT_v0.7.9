"""
Notebook-style math rendering for the terminal: stacked fractions,
subscripts and superscripts using Unicode, so output never looks like
a raw inline "R0/R" — it looks handwritten, e.g.:

             2.303
k = ───────────────── log(R0/R)
                t
"""

import re as _re

from . import theme

_MUL_RE = _re.compile(r"(?<!\*)\*(?!\*)")
_DIV_RE = _re.compile(r"(?<=[\w\)\]\u2080-\u2089])\s*/\s*(?=[\w\(\[])")


def mathify(s):
    """House style, applied to any plain (already-computed) display line:
    never a literal '*' for multiplication (use 'x') and never a literal
    '/' for division (use the fraction slash \u2044, which reads as a
    proper divide rather than a path separator). Formula/substitution
    rows should prefer compose()+frac_part() for a full stacked bar —
    this is the lightweight fallback for single-line calculation text.

    Also normalizes explicit ^ / _ notation and Greek-letter words to
    their Unicode form. This only fires on explicit markup (a literal
    ``^``/``_``, or a whole Greek word), never on bare digits, so
    ordinary numbers like "15" are always left alone.
    """
    s = _MUL_RE.sub(" x ", str(s))
    s = _DIV_RE.sub("\u2044", s)
    s = convert_explicit_superscripts(s)
    s = convert_explicit_subscripts(s)
    s = convert_greek(s)
    return s

SUB = {"0": "\u2080", "1": "\u2081", "2": "\u2082", "3": "\u2083", "4": "\u2084",
       "5": "\u2085", "6": "\u2086", "7": "\u2087", "8": "\u2088", "9": "\u2089"}
SUP = {"0": "\u2070", "1": "\u00b9", "2": "\u00b2", "3": "\u00b3", "4": "\u2074",
       "5": "\u2075", "6": "\u2076", "7": "\u2077", "8": "\u2078", "9": "\u2079",
       "-": "\u207b", "+": "\u207a"}


def sub(n):
    return "".join(SUB.get(c, c) for c in str(n))


def sup(n):
    return "".join(SUP.get(c, c) for c in str(n))


def frac_part(num, den):
    """Return a ('frac', num, den) tuple for use in compose()."""
    return ("frac", str(num), str(den))


def compose(parts, color=theme.TEXT):
    """
    Compose a mixed list of plain strings and ('frac', num, den) tuples
    into a 3-row, baseline-aligned block of text, colored uniformly.
    """
    top_row, mid_row, bot_row = [], [], []
    for p in parts:
        if isinstance(p, tuple) and p[0] == "frac":
            _, num, den = p
            w = max(len(num), len(den))
            top_row.append(" " + num.center(w) + " ")
            mid_row.append(" " + ("\u2500" * w) + " ")
            bot_row.append(" " + den.center(w) + " ")
        else:
            s = str(p)
            top_row.append(" " * len(s))
            mid_row.append(s)
            bot_row.append(" " * len(s))

    top = "".join(top_row).rstrip()
    mid = "".join(mid_row).rstrip()
    bot = "".join(bot_row).rstrip()

    lines = [l for l in (top, mid, bot) if l.strip() != ""]
    return "\n".join(theme.fg(l, color) for l in lines) if lines else ""


# --------------------------------------------------------------------- #
# Scientific rendering engine (v0.6.2)                                  #
#                                                                        #
# Everything below extends the module above without touching it: the   #
# original mathify/sub/sup/frac_part/compose keep their exact old      #
# behavior (mathify only gained two new, narrowly-scoped calls). The   #
# goal of this section is a single entry point — render_math() — that  #
# any AI-generated or user-facing text can be piped through so raw     #
# Markdown/LaTeX markup never reaches the screen; textbook Unicode     #
# comes out the other side instead.                                    #
# --------------------------------------------------------------------- #

GREEK = {
    "alpha": "\u03b1", "beta": "\u03b2", "gamma": "\u03b3", "delta": "\u0394",
    "epsilon": "\u03b5", "zeta": "\u03b6", "eta": "\u03b7", "theta": "\u03b8",
    "iota": "\u03b9", "kappa": "\u03ba", "lambda": "\u03bb", "mu": "\u03bc",
    "nu": "\u03bd", "xi": "\u03be", "pi": "\u03c0", "rho": "\u03c1",
    "sigma": "\u03c3", "tau": "\u03c4", "upsilon": "\u03c5", "phi": "\u03c6",
    "chi": "\u03c7", "psi": "\u03c8", "omega": "\u03c9",
}
# Case-preserving alternates the spec calls out explicitly (e.g. capital
# Delta for change-in, lowercase everywhere else).
_GREEK_RE = _re.compile(
    r"\\?(?<![A-Za-z])(" + "|".join(sorted(GREEK, key=len, reverse=True)) + r")(?![A-Za-z])",
    _re.IGNORECASE,
)


def convert_greek(s):
    """Replace bare Greek-letter words (optionally LaTeX-escaped, e.g.
    'delta' or '\\delta') with their Unicode symbol. Word-boundary
    matched, so it never touches a word that merely contains one of
    these as a substring."""
    def _rep(m):
        return GREEK[m.group(1).lower()]
    return _GREEK_RE.sub(_rep, str(s))


_EXPL_SUP_BRACE_RE = _re.compile(r"\^\{([^{}]+)\}")
_EXPL_SUP_RE = _re.compile(r"\^(-?[0-9A-Za-z]+)")
_EXPL_SUB_BRACE_RE = _re.compile(r"_\{([^{}]+)\}")
_EXPL_SUB_RE = _re.compile(r"_(-?[0-9A-Za-z]+)")


def convert_explicit_superscripts(s):
    """Turn explicit ``x^2``, ``x^{12}``, ``10^-5`` into Unicode
    superscripts. Only fires on a literal caret, so plain numbers are
    never touched."""
    s = _EXPL_SUP_BRACE_RE.sub(lambda m: sup(m.group(1)), str(s))
    s = _EXPL_SUP_RE.sub(lambda m: sup(m.group(1)), s)
    return s


def convert_explicit_subscripts(s):
    """Turn explicit ``H_2``, ``psi_{100}`` into Unicode subscripts.
    Only fires on a literal underscore."""
    s = _EXPL_SUB_BRACE_RE.sub(lambda m: sub(m.group(1)), str(s))
    s = _EXPL_SUB_RE.sub(lambda m: sub(m.group(1)), s)
    return s


_SCI_NOTATION_RE = _re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)[eE]([+-]?\d+)(?!\w)")


def convert_scientific_notation(s):
    """6.022e23 -> 6.022 x 10^23 (Unicode). Requires digits on both
    sides of the 'e' so it can never fire on ordinary words."""
    return _SCI_NOTATION_RE.sub(lambda m: f"{m.group(1)} \u00d7 10{sup(m.group(2))}", str(s))


_LATEX_SYMBOLS = {
    r"\times": "\u00d7", r"\cdot": "\u00b7", r"\pm": "\u00b1", r"\mp": "\u2213",
    r"\geq": "\u2265", r"\leq": "\u2264", r"\neq": "\u2260", r"\approx": "\u2248",
    r"\infty": "\u221e", r"\rightarrow": "\u2192", r"\Rightarrow": "\u21d2",
    r"\leftarrow": "\u2190", r"\to": "\u2192", r"\propto": "\u221d",
    r"\partial": "\u2202", r"\nabla": "\u2207", r"\degree": "\u00b0",
    r"\circ": "\u00b0", r"\perp": "\u22a5", r"\parallel": "\u2225",
    r"\angle": "\u2220", r"\sim": "\u223c", r"\equiv": "\u2261",
    # v0.7.2 roadmap additions: big operators (bounds already come for
    # free — \sum_{i=1}^{n} still has the \sum replaced here, then the
    # existing convert_explicit_sub/superscript passes below pick up
    # the trailing _{i=1}/^{n} the same as they would on any other
    # symbol) plus quantum-mechanics/set notation the spec calls out
    # by name ("Quantum mechanics notation").
    r"\sum": "\u2211", r"\prod": "\u220f", r"\int": "\u222b",
    r"\iint": "\u222c", r"\iiint": "\u222d", r"\oint": "\u222e",
    r"\hbar": "\u210f", r"\langle": "\u27e8", r"\rangle": "\u27e9",
    r"\otimes": "\u2297", r"\oplus": "\u2295", r"\dagger": "\u2020",
    r"\forall": "\u2200", r"\exists": "\u2203", r"\nexists": "\u2204",
    r"\in": "\u2208", r"\notin": "\u2209", r"\subseteq": "\u2286",
    r"\subset": "\u2282", r"\cup": "\u222a", r"\cap": "\u2229",
    r"\emptyset": "\u2205", r"\wedge": "\u2227", r"\vee": "\u2228",
    r"\neg": "\u00ac", r"\therefore": "\u2234", r"\because": "\u2235",
    r"\ell": "\u2113", r"\Re": "\u211c", r"\Im": "\u2111",
    r"\aleph": "\u2135",
}


def _strip_latex_noise(s):
    """Replace common LaTeX macros with their Unicode glyph, and drop
    the purely-cosmetic ones (\\left, \\right, \\, , \\; , \\quad,
    stray $ / \\[ \\] delimiters) so nothing raw leaks through."""
    for macro, glyph in _LATEX_SYMBOLS.items():
        s = s.replace(macro, glyph)
    for noise in (r"\left", r"\right", r"\quad", r"\qquad", r"\,", r"\;",
                  r"\!", "\\\n"):
        s = s.replace(noise, "")
    s = s.replace(r"\[", "").replace(r"\]", "")
    s = _re.sub(r"(?<!\\)\$\$?", "", s)
    return s


def _find_balanced(s, open_idx):
    """s[open_idx] must be '{'. Returns the index just past the
    matching '}' (handling one level of nesting), or None."""
    depth = 0
    for i in range(open_idx, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    return None


def convert_sqrt(s):
    """\\sqrt{X} -> a Unicode radical with a combining overline across
    X, e.g. \\sqrt{2KE/m} -> '\u221a(2KE/m)' with an overline on the
    inside. Recurses so nested markup inside the radicand still gets
    converted."""
    s = str(s)
    out, i = [], 0
    while True:
        j = s.find(r"\sqrt", i)
        if j == -1:
            out.append(s[i:])
            break
        out.append(s[i:j])
        k = j + len(r"\sqrt")
        if k < len(s) and s[k] == "{":
            end = _find_balanced(s, k)
            if end is None:
                out.append(s[j:])
                break
            inner = render_inline(s[k + 1:end - 1])
            out.append("\u221a\u0305" + "\u0305".join(inner) + "\u0305" if inner else "\u221a")
            i = end
        else:
            out.append("\u221a")
            i = k
    return "".join(out)


def convert_fractions(s):
    """\\frac{A}{B} -> a real 3-row stacked-bar block (via compose),
    dropped in as its own fenced code section so the Markdown renderer
    preserves the line breaks and monospace alignment a stacked
    fraction depends on. Handles nested \\frac inside numerator or
    denominator by recursing first."""
    s = str(s)
    out, i = [], 0
    while True:
        j = s.find(r"\frac", i)
        if j == -1:
            out.append(s[i:])
            break
        out.append(s[i:j])
        k = j + len(r"\frac")
        if k < len(s) and s[k] == "{":
            num_end = _find_balanced(s, k)
            if num_end is None:
                out.append(s[j:])
                break
            num = s[k + 1:num_end - 1]
            den_start = num_end
            if den_start < len(s) and s[den_start] == "{":
                den_end = _find_balanced(s, den_start)
                if den_end is None:
                    out.append(s[j:den_start])
                    i = den_start
                    continue
                den = s[den_start + 1:den_end - 1]
                block = compose([frac_part(render_inline(num), render_inline(den))])
                out.append("\n```\n" + _strip_ansi(block) + "\n```\n")
                i = den_end
                continue
        out.append(s[j:k])
        i = k
    return "".join(out)


_ANSI_RE = _re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(s):
    """compose() colors its output with terminal ANSI codes for the
    fallback CLI; inside a Markdown fenced block those codes would show
    up as literal garbage, so strip them back to plain Unicode text."""
    return _ANSI_RE.sub("", s)


def render_inline(s):
    """Apply every *inline-safe* conversion (no fraction blocks, which
    span multiple lines) — Greek, explicit sup/sub, latex symbol noise,
    scientific notation. Used both standalone and as the recursive
    step inside sqrt/frac/matrix parsing."""
    s = _strip_latex_noise(str(s))
    s = convert_greek(s)
    s = convert_explicit_superscripts(s)
    s = convert_explicit_subscripts(s)
    s = convert_scientific_notation(s)
    return s


_MATRIX_ENV_RE = _re.compile(
    r"\\begin\{(matrix|bmatrix|pmatrix|vmatrix)\}(.*?)\\end\{\1\}", _re.DOTALL
)


def convert_matrices(s):
    """\\begin{bmatrix} a & b \\\\ c & d \\end{bmatrix} -> a bracket-
    bordered Unicode grid, e.g.:

        ⎡a b⎤
        ⎣c d⎦
    """
    def _rep(m):
        env, body = m.group(1), m.group(2)
        rows = [r.strip() for r in body.strip().split("\\\\") if r.strip()]
        grid = [[render_inline(cell.strip()) for cell in row.split("&")] for row in rows]
        if not grid:
            return ""
        widths = [max(len(row[c]) for row in grid) for c in range(len(grid[0]))]
        lines = []
        n = len(grid)
        left_edges = {"matrix": ("", "", ""), "bmatrix": ("\u23a1", "\u23a2", "\u23a3"),
                      "pmatrix": ("\u239b", "\u239c", "\u239d"),
                      "vmatrix": ("\u2502", "\u2502", "\u2502")}
        right_edges = {"matrix": ("", "", ""), "bmatrix": ("\u23a4", "\u23a5", "\u23a6"),
                       "pmatrix": ("\u239e", "\u239f", "\u23a0"),
                       "vmatrix": ("\u2502", "\u2502", "\u2502")}
        lft, rgt = left_edges.get(env, ("", "", "")), right_edges.get(env, ("", "", ""))
        for idx, row in enumerate(grid):
            pos = 0 if n == 1 else (0 if idx == 0 else (2 if idx == n - 1 else 1))
            cells = "  ".join(cell.rjust(widths[c]) for c, cell in enumerate(row))
            lines.append(f"{lft[pos]}{cells}{rgt[pos]}")
        return "\n```\n" + "\n".join(lines) + "\n```\n"

    return _MATRIX_ENV_RE.sub(_rep, str(s))


# Conservative chemistry-formula matcher: 2+ Element[digits] groups,
# optionally followed by a trailing ionic charge like ^2- or a bare +/-.
_CHEM_TOKEN_RE = _re.compile(
    r"\b((?:[A-Z][a-z]?\d*){2,}(?:\^?\d*[+\-])?)\b"
)
_CHEM_ELEMENT_RE = _re.compile(r"([A-Z][a-z]?)(\d+)")
_CHEM_CHARGE_CARET_RE = _re.compile(r"\^(\d*)([+\-])$")
_CHEM_CHARGE_BARE_RE = _re.compile(r"([+\-])$")


def chem_formula(token):
    """Render one chemistry token (e.g. 'SO4^2-', 'CaCO3', 'NH4+') with
    Unicode subscripts for atom counts and a Unicode superscript for a
    trailing ionic charge. A caret-prefixed digit (``^2-``) is the
    charge magnitude; a bare trailing sign (``NH4+``) is charge 1, and
    any digit right before it still belongs to the preceding element's
    atom count, not the charge — so 'NH4+' reads N, H4, +1, never
    N, H, charge 4. Meant to be called on a token already known to be
    a formula, not blindly across arbitrary prose."""
    charge = ""
    m = _CHEM_CHARGE_CARET_RE.search(token)
    if m:
        n, sign = m.groups()
        charge = sup((n or "") + sign)
        token = token[:m.start()]
    else:
        m = _CHEM_CHARGE_BARE_RE.search(token)
        if m:
            charge = sup(m.group(1))
            token = token[:m.start()]
    body = _CHEM_ELEMENT_RE.sub(lambda m2: m2.group(1) + sub(m2.group(2)), token)
    return body + charge


def find_latex_errors(text):
    """Real (if intentionally narrow) error-highlighting pass — v0.7.2
    roadmap's "Error highlighting" bullet. Checks for the mistakes that
    are actually detectable from the text alone without a real LaTeX
    parser: unbalanced braces after \\frac/\\sqrt, and an unclosed
    \\begin{...} environment. Does NOT validate that a macro name is a
    real LaTeX command (this file only ever converts a known allow-
    list — see _LATEX_SYMBOLS/convert_* above — and silently leaves
    anything else as plain text, which is the deliberately permissive
    choice made throughout this module already: rendering "unknown
    macro" warnings on every \\notarealcommand a user or AI might type
    would be noisier than useful). Returns a list of short strings,
    empty if nothing looks wrong."""
    text = str(text)
    errors = []
    for macro in (r"\frac", r"\sqrt"):
        i = 0
        while True:
            j = text.find(macro, i)
            if j == -1:
                break
            k = j + len(macro)
            if k >= len(text) or text[k] != "{":
                i = k
                continue
            if _find_balanced(text, k) is None:
                errors.append(f"Unbalanced {{}} after {macro}")
            i = k + 1
    for m in _re.finditer(r"\\begin\{([a-zA-Z*]+)\}", text):
        env = m.group(1)
        if f"\\end{{{env}}}" not in text[m.end():]:
            errors.append(f"\\begin{{{env}}} has no matching \\end{{{env}}}")
    return errors


def render_math(text):
    """Master entry point: run a full block of AI/user-facing text
    through the scientific rendering pipeline so LaTeX/Markdown math
    markup never reaches the screen as raw text. Fenced code blocks
    (real code, not math) are left completely untouched. Safe to call
    on plain prose with no math in it at all — everything here only
    fires on explicit markers (\\, ^, _, e-notation, a known Greek
    word), so ordinary sentences pass through unchanged."""
    text = str(text)
    if "```" not in text:
        return _render_math_segment(text)
    parts = text.split("```")
    for i in range(0, len(parts), 2):  # even indices are outside fences
        parts[i] = _render_math_segment(parts[i])
    return "```".join(parts)


def _render_math_segment(segment):
    segment = _strip_latex_noise(segment)
    segment = convert_fractions(segment)
    segment = convert_matrices(segment)
    segment = convert_sqrt(segment)
    segment = convert_greek(segment)
    segment = convert_explicit_superscripts(segment)
    segment = convert_explicit_subscripts(segment)
    segment = convert_scientific_notation(segment)
    return segment
