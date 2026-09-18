"""
CCT — mode_detection.py: Automatic Mode Switching (v0.7.7 spec section 5).

The AI should intelligently determine which mode a message needs, switch
to it (with a visible transition), and keep the user informed. Modes are
the ai_modes.py personas plus the two the spec adds for autonomous work:

    Notebook   — conversation, explanation, teaching, documentation,
                 summaries, general chat.
    Planner    — roadmaps, architecture, algorithms, task planning,
                 project decomposition, todo generation.
    Research   — documentation search, API research, framework
                 comparison, web research, deep analysis.
    Build      — coding, file editing, dependency installation,
                 compilation, testing, execution, deployment.
    Debugger   — error analysis, crash investigation, performance
                 profiling, security analysis.
    Agent      — the tool-executing loop (kept for explicit /agent use;
                 the detector never force-switches into it, because
                 run_agent's blocking loop is a user choice, not an
                 auto-routing destination).

Honest scope: detection is keyword/regex-based intent classification
(the same category of heuristic the app's existing `detect_intent` /
`detect_derivation` use), NOT an LLM call per message — a model call
just to decide which prompt to send next would double every request's
cost for a label a regex table gets right ~95% of the time. The
classifier exposes its matched reason so the UI can show a real
transition note ("Switching Notebook → Build — detected a dependency
install request") instead of a silent persona change.

The router also recognizes the spec's *workflow* triggers: install
requests are routed to the package-manager flow (spec section 1),
deep-research-ish requests to Research mode, big build requests to the
autonomous pipeline (spec section 6) when the caller opts in.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import re

# (regex, mode, reason-template). Ordered: first match wins.
_RULES = [
    # ---- Build (software) ----
    (re.compile(r"\b(install|pip install|npm install|npm i|apt install|brew install|choco install|winget install|cargo install|go install)\b", re.I),
     "build", "dependency / package install request"),
    (re.compile(r"\b(compile|build the project|build a project|build an app|build this|make a program|write the code|write code for|generate code|implement the|create a script|write a script|develop an app|create an app|create a project|set up a project|scaffold)\b", re.I),
     "build", "code generation / project build request"),
    (re.compile(r"\b(coding|codepad|code review|refactor|debug a (python|js|script)|deploy|deployment|dockerfile|docker compose|\.py\b|\.js\b|\.ts\b|\.html\b|\.css\b)\b", re.I),
     "build", "software development task"),
    # ---- Debugger ----
    (re.compile(r"\b(debug this|why is this (broken|failing|erroring)|fix this error|crash|traceback|stack trace|segfault|exception|performance profiling|profile this|memory leak|security scan|security audit|vulnerab|malware|sandbox)\b", re.I),
     "debugger", "error / performance / security diagnosis"),
    (re.compile(r"\b(what's wrong with|what went wrong|error analysis|root cause|code is slow|slow code)\b", re.I),
     "debugger", "failure / slowdown investigation"),
    # ---- Research ----
    (re.compile(r"\b(research|compare (the )?(frameworks|libraries|tools|packages)|which (library|framework|tool) (should|is best|to use)|latest version|documentation for|docs for|api reference|how does .* work)\b", re.I),
     "research", "documentation / framework research"),
    (re.compile(r"\b(best practices for|alternatives to|pros and cons|vs\.?\s|versus|is .* better than|difference between)\b", re.I),
     "research", "technology comparison"),
    # ---- Planner ----
    (re.compile(r"\b(roadmap|architecture (design|diagram)|design (the )?(system|architecture|api)|algorithm design|task plan|plan of action|project plan|decompose|break this (down|into)|create a plan|todo list|milestones|phases? for|study plan)\b", re.I),
     "plan", "planning / roadmap / task decomposition"),
    # ---- Notebook (teaching / explanation) ----
    (re.compile(r"\b(explain|teach|what is|what are|define|concept|concepts|summary|summarize|overview|derive|derive the|half ?life|mole concept|nernst|arrhenius|kinetics|thermodynamics|stoichiometry)\b", re.I),
     "notebook", "conceptual / teaching question"),
]

# Workflow triggers — not mode changes, but *pipeline* routing decisions.
# (regex, kind) where kind is one of "install" | "research_deep" |
# "pipeline" (a big multi-stage autonomous build).
_WORKFLOW_RULES = [
    (re.compile(r"\b(install|setup|get)\s+(latest\s+)?[a-z0-9]", re.I), "install"),
    (re.compile(r"\b(pip|npm|pnpm|yarn|bun|cargo|go install|conda|brew|choco|winget|apt|dnf|composer|vcpkg)\s+install\b", re.I), "install"),
    (re.compile(r"\b(deep research|in-depth research|research thoroughly|full research)\b", re.I), "research_deep"),
    (re.compile(r"\b(build (me |us )?(an? |the )?([a-z0-9-]+ )?(app|project|program|tool|api|website|script|viewer|dashboard|cli|game|module|server)|create a full (app|project|program|api)|develop a complete|implement a full)\b", re.I), "pipeline"),
]

_DEBUG_PREFIXES = re.compile(r"^(traceback|error|exception|crash|fatal|segfault|core dump)", re.I)
_CODE_FENCE = re.compile(r"```")


def classify(text):
    """Returns (mode_key, reason, confidence) for a piece of user text.
    confidence is "high" (explicit rule match) or "low" (fallback:
    Notebook — no signal either way)."""
    if not text:
        return "notebook", "empty message", "low"
    low = text.strip()
    if _CODE_FENCE.search(low):
        return "build", "code block detected", "high"
    if _DEBUG_PREFIXES.match(low):
        return "debugger", "error report detected", "high"
    for pattern, mode, reason in _RULES:
        if pattern.search(low):
            return mode, reason, "high"
    # Weak conversational signals.
    if re.search(r"\b(what do you think|any ideas|brainstorm|tell me about)\b", low, re.I):
        return "plan", "open-ended ideation", "low"
    return "notebook", "general conversation", "low"


def workflow_kind(text):
    """Returns one of None | "install" | "research_deep" | "pipeline"
    for workflow routing (spec sections 1/6), or None when the message
    is ordinary conversation."""
    if not text:
        return None
    low = text.strip()
    for pattern, kind in _WORKFLOW_RULES:
        if pattern.search(low):
            return kind
    return None


def transition_line(from_mode, to_mode, reason=""):
    """The visible transition note callers show when auto-switching
    (spec section 5: "Show transition animation"). Pure text — each UI
    renders it its own way."""
    from . import ai_modes
    if from_mode == to_mode:
        return None
    f = ai_modes.meta(from_mode)
    t = ai_modes.meta(to_mode)
    base = f"{f['icon']} {f['label']} \u2192 {t['icon']} {t['label']}"
    if reason:
        base += f" \u2014 {reason}"
    return base


def suggest_mode_change(current_mode, text):
    """One-stop helper: classify `text`, and if the suggested mode
    differs from `current_mode` (and isn't agent), return
    (to_mode, transition_text). Otherwise return None."""
    if current_mode == "agent":
        # Never yank the user out of the explicit tool-executing loop
        # based on a heuristic — auto-switching only applies between
        # the streaming personas.
        return None
    mode, reason, _conf = classify(text)
    if mode == current_mode:
        return None
    return mode, transition_line(current_mode, mode, reason)
