"""
CCT Error Recovery (spec section 19).

Before this module, a failure inside try/except blocks scattered
across app.py just did `print(theme.red(f"Error: {e}"))` and moved
on — a technical exception string, no way to retry without re-typing
the whole command, no way to see more detail, no way to know if it's
worth trying again. That's real (see the audit in
CHANGELOG_v0.6.3_architecture.md: 7 call sites doing exactly this).

This module gives failures one consistent shape: a themed card with a
plain-language title + message, and numbered recovery actions —
Retry (re-runs the same operation), View Details (the actual
exception message, only surfaced on request, not by default), and
Dismiss. It does NOT catch anything itself — callers still do their
own try/except, same as before; this just replaces the "print a red
line and give up" ending with a real recovery loop, and importantly
never lets the underlying exception propagate up and crash the REPL.

CONTEXTS below covers the failure kinds already wired in (see
WIRED_INTO at the bottom for the honest current list). Anything not
in CONTEXTS still gets a real card — just with a generic title.
"""

from . import theme

WIDTH = 78  # matches app.py's WIDTH; passed in by callers where it differs

CONTEXTS = {
    "export": ("Export failed", "CAT couldn't save your export."),
    "render": ("Visualization failed", "CAT couldn't generate that image."),
    "solve": ("Calculation failed", "CAT couldn't solve that with the numbers given."),
    "balance": ("Reaction balancing failed", "CAT couldn't balance that chemical equation."),
    "import": ("Import failed", "CAT couldn't read that file."),
    "ai_provider": ("AI provider unavailable", "CAT couldn't reach the configured AI provider."),
    "workspace": ("Workspace error", "CAT couldn't read or write to the project workspace."),
}


def error_card(context, exc, retry=None, extra_actions=None, width=None):
    """Show a friendly recovery card for `exc` and act on the user's
    choice.

    `retry` (zero-arg callable, optional): if given and the user picks
    Retry, calls it and loops — success closes the card, another
    failure reopens it with the new exception.

    `extra_actions` (list of (label, callback), optional): additional
    numbered options between Retry and View Details, e.g. Reconnect /
    Switch Provider for an AI-unavailable card. Each callback is
    zero-arg. After running one, if `retry` was also given this
    automatically attempts it (reconnecting and then not retrying the
    request would be a dead end); otherwise the card just closes.

    Returns True if the operation eventually succeeded via retry,
    False if the user dismissed without a successful retry."""
    w = width or WIDTH
    extra_actions = extra_actions or []
    current_exc = exc
    while True:
        title, friendly = CONTEXTS.get(context, ("Something went wrong", "CAT hit an unexpected error."))
        actions = []
        if retry is not None:
            actions.append(("Retry", "retry", None))
        for label, cb in extra_actions:
            actions.append((label, "extra", cb))
        actions.append(("View Details", "details", None))
        actions.append(("Dismiss", "dismiss", None))

        lines = [theme.red(f"\u26a0 {title}", bold=True), "", theme.text(friendly), ""]
        for i, (label, _, _) in enumerate(actions, 1):
            lines.append(f"{theme.cyan(str(i) + '.')} {label}")
        print()
        print(theme.panel(lines, title="error", color=theme.RED, width=w))
        raw_choice = input(theme.dim("  \u25b8 ")).strip().lower()

        chosen = None
        for i, (label, act, cb) in enumerate(actions, 1):
            if raw_choice == str(i) or raw_choice == label.lower() or raw_choice == act:
                chosen = (act, cb)
                break

        if chosen is None:
            return False  # unrecognized input or bare Enter dismisses
        act, cb = chosen

        if act == "details":
            print(theme.faint(f"\n  {current_exc}\n"))
            continue
        if act == "extra":
            cb()
            if retry is None:
                return False
            try:
                retry()
                return True
            except Exception as e2:
                current_exc = e2
                continue
        if act == "retry":
            try:
                retry()
                return True
            except Exception as e2:
                current_exc = e2
                continue
        return False  # "dismiss"


# What's actually wired into error_card() right now vs. still using a
# plain print(theme.red(...)) line — read this before assuming every
# failure in the app shows a recovery card.
WIRED_INTO = {
    "app.py cmd_export": "reports/PDF export failures",
    "app.py cmd_react/_react_balance": "equation-balancing failures",
    "app.py _solve_library/_solve_custom": "not yet — still a plain red line",
    "app.py cmd_orbitalgrid": "not yet — still a plain red line",
    "app.py cmd_import (zip extraction)": "not yet — still a plain red line",
    "agent.py AI tool calls": "not yet — still returns a plain error string",
}
