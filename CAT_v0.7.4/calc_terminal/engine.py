import shutil
import sys
import textwrap
import time

from . import theme
from .mathtext import compose, mathify


def term_width(min_w=60, max_w=100, margin=1, fallback=78):
    """The real, current terminal width, clamped to a sane range.

    Every box/panel in CCT is drawn at a fixed width — if that width is
    wider than the actual terminal, the border characters wrap onto the
    next line and the box looks broken (this was reported as a "border
    problem": the right-hand `│` shows up in a different, wrong column
    on every row, because every long line wraps at a different point).
    Sizing to the real terminal at startup fixes that in the vast
    majority of cases without needing a live-resize architecture.
    """
    try:
        cols = shutil.get_terminal_size(fallback=(fallback, 24)).columns
    except Exception:
        cols = fallback
    return max(min_w, min(max_w, cols - margin))


WIDTH = term_width()

ENGINE_STEPS = [
    "Initializing Chemistry Engine...",
    "Loading Formula Library...",
    "Searching Database...",
    "Checking Units...",
    "Generating Notebook...",
    "Rendering Output...",
]

DERIVE_STEPS = [
    "Setting up the differential rate law...",
    "Separating variables...",
    "Integrating both sides...",
    "Simplifying the result...",
    "Typesetting derivation...",
]

IMAGE_STEPS = [
    "Reading Image...",
    "Recognizing Formula...",
    "Extracting Text...",
    "Preparing Solution...",
]

SPINNER = "\u280b\u2819\u2839\u2838\u283c\u2834\u2826\u2827\u2807\u280f"


def run_steps(steps, step_time=0.35):
    """Print a sequential fake-AI processing log with a spinner + checkmark."""
    for step in steps:
        frames = max(3, int(step_time / 0.05))
        for i in range(frames):
            frame = SPINNER[i % len(SPINNER)]
            sys.stdout.write(f"\r  {theme.cyan(frame)} {theme.dim(step)}" + " " * 10)
            sys.stdout.flush()
            time.sleep(0.05)
        sys.stdout.write(f"\r  {theme.green(chr(0x2713))} {theme.dim(step)}" + " " * 10 + "\n")
        sys.stdout.flush()
    print(f"  {theme.green(chr(0x2713) + ' Completed', bold=True)}")
    time.sleep(0.15)


def _wrap(s, width=WIDTH - 10):
    return textwrap.wrap(s, width=width) or [""]


# ---------------------------------------------------------------- reveal --
# Animation is on by default; app.py can flip this off (e.g. non-tty runs
# or a user "fast mode" setting) without touching call sites.
ANIMATE = True


def set_animation(on):
    global ANIMATE
    ANIMATE = bool(on)


def _border(width, top=True, color=theme.CYAN):
    ch = theme.TL + theme.H * (width - 2) + theme.TR if top else theme.BL + theme.H * (width - 2) + theme.BR
    return theme.fg(ch, color)


def _row(text_line, width, color=theme.CYAN):
    inner = width - 2
    pad = max(0, inner - theme.vlen(text_line) - 2)
    return theme.fg(theme.V, color) + " " + text_line + " " * pad + theme.fg(theme.V, color)


def _title_row(title, width, color):
    inner = width - 2
    tag = f" {title} "
    left = 3
    right = max(0, inner - left - theme.vlen(tag))
    return theme.fg(theme.TL + theme.H * left, color) + theme.fg(tag, color, bold=True) + theme.fg(theme.H * right + theme.TR, color)


def animate_panel(lines, title=None, color=theme.CYAN, width=WIDTH, stage_pause=0.10, line_pause=0.014):
    """Reveal a panel progressively: border draws in, then each line
    fades in top-to-bottom, with a slightly longer pause on section
    headers (lines containing the bullet marker) so every response
    feels like it's being worked out live rather than dumped instantly.
    Falls back to an instant static panel when ANIMATE is off."""
    if not ANIMATE:
        print(theme.panel(lines, title=title, color=color, width=width))
        return
    try:
        print(_title_row(title, width, color) if title else _border(width, top=True, color=color))
        for line in lines:
            print(_row(line, width, color))
            time.sleep(stage_pause if "\u25cf" in line else line_pause)
        print(_border(width, top=False, color=color))
    except Exception:
        # any terminal-width edge case -> never break the actual output
        print(theme.panel(lines, title=title, color=color, width=width))


def render_notebook(nb):
    """Print a full step-by-step notebook panel for a generated numerical,
    revealed one stage at a time (animated)."""
    lines = []
    lines.append(theme.purple(nb["topic"].upper(), bold=True))
    for w in _wrap(nb["question"]):
        lines.append(theme.text(w, bold=True))
    lines.append("")

    def stage(label, body_lines, final=False):
        color = theme.GREEN if final else theme.CYAN
        lines.append(theme.fg("\u25cf " + label, color, bold=True))
        for bl in body_lines:
            lines.append("  " + bl)
        lines.append("")

    stage("GIVEN DATA", [theme.dim("\u2022 ") + theme.text(g) for g in nb["given"]])
    stage("FIND", [theme.text(nb["find"])])
    stage("FORMULA", [theme.text(l) for l in compose(nb["formula"]).split("\n")])
    stage("SUBSTITUTION", [theme.text(l) for l in compose(nb["substitution"]).split("\n")])
    stage("CALCULATION", [theme.dim(f"{i+1}. ") + theme.text(mathify(c)) for i, c in enumerate(nb["calculation"])])

    unit_lines = []
    for w in _wrap(mathify(nb["unit"])):
        unit_lines.append(theme.dim(w))
    stage("UNITS", unit_lines)

    ver_lines = []
    for w in _wrap(mathify(nb["verification"])):
        ver_lines.append(theme.dim(w))
    stage("VERIFICATION", ver_lines)

    stage("FINAL ANSWER", [theme.green(nb["final_answer"], bold=True)], final=True)

    animate_panel(lines, title="notebook", color=theme.CYAN, width=WIDTH)


import re as _re

# A header line is either a short markdown-ish "## SOME HEADER" line, or a
# short, mostly-uppercase line (with or without a trailing colon) — the
# style CCT Agent's system prompt asks the model to write in (GIVEN DATA,
# FORMULA, FINAL ANSWER...). Kept permissive since it's parsing free-form
# LLM text, not a fixed schema.
_AGENT_HEADER_RE = _re.compile(
    r"^\s*(?:#{1,4}\s*|\*\*)?([A-Z][A-Z0-9 /&()\-]{2,40}?)(?:\*\*)?\s*:?\s*$"
)


def _is_agent_header(line):
    s = line.strip()
    if not s or len(s) > 48:
        return None
    m = _AGENT_HEADER_RE.match(s)
    if not m:
        return None
    label = m.group(1).strip()
    letters = [c for c in label if c.isalpha()]
    if len(letters) < 3:
        return None
    # Require it to actually look shouted (mostly uppercase), not just any
    # short capitalized sentence fragment.
    upper = sum(1 for c in letters if c.isupper())
    if upper / len(letters) < 0.8:
        return None
    return label


def render_agent_answer(text, tag="CAT Agent", color=theme.PURPLE):
    """Render CAT Agent's free-form "final" text as a notebook-style
    panel — detecting the ALL-CAPS section headers (GIVEN DATA, FORMULA,
    FINAL ANSWER, OVERVIEW, EXPLANATION...) the agent's system prompt asks
    for, and falling back to a single plain ANSWER section for any text
    that doesn't use them (e.g. a short aside or an older-style reply), so
    /agent always reads like a worked notebook page rather than a wall of
    unstructured prose."""
    if not text or not text.strip():
        return
    raw_lines = text.strip().split("\n")
    sections = []          # [(header, [body_lines])]
    current_body = []
    for line in raw_lines:
        header = _is_agent_header(line)
        if header:
            sections.append([header, []])
            current_body = sections[-1][1]
        else:
            if not sections:
                sections.append(["ANSWER", []])
                current_body = sections[-1][1]
            if line.strip():
                current_body.append(line.strip())

    lines = [theme.badge(tag, theme.BG_AI, fgcolor=(225, 210, 255)), ""]
    for header, body in sections:
        is_final = "FINAL" in header
        hcolor = theme.GREEN if is_final else theme.CYAN
        lines.append(theme.fg("\u25cf " + header, hcolor, bold=True))
        if not body:
            body = [""]
        for b in body:
            for w in _wrap(b):
                lines.append("  " + (theme.green(w, bold=True) if is_final else theme.text(w)))
        lines.append("")

    animate_panel(lines, title="agent notebook", color=color, width=WIDTH, stage_pause=0.10)


def render_derivation(dv):
    """Print a full step-by-step DERIVATION panel (real calculus, not a
    numeric example) for the given derivation dict from derivations.py,
    revealed step-by-step so the logic visibly builds instead of
    appearing all at once."""
    lines = []
    lines.append(theme.purple(dv["topic"].upper(), bold=True))
    for w in _wrap(dv["goal"]):
        lines.append(theme.text(w, bold=True))
    lines.append("")

    for i, (label, parts) in enumerate(dv["steps"], 1):
        lines.append(theme.fg(f"\u25cf Step {i} \u2014 {label}", theme.CYAN, bold=True))
        for l in compose(parts).split("\n"):
            lines.append("  " + theme.text(l))
        lines.append("")

    lines.append(theme.fg("\u25cf RESULT", theme.GREEN, bold=True))
    lines.append("  " + theme.green(dv["result"], bold=True))
    lines.append("")

    lines.append(theme.fg("\u25cf WHAT IT MEANS", theme.ORANGE, bold=True))
    for w in _wrap(dv["note"]):
        lines.append("  " + theme.dim(w))

    animate_panel(lines, title="derivation", color=theme.PURPLE, width=WIDTH, stage_pause=0.16)
