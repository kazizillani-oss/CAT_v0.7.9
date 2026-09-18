"""
CCT — orchestrator.py: Agent Orchestrator (v0.7.7 spec section 9).

A Coordinator assigns work to specialist agents, and the Coordinator
continuously monitors them. This layers on top of agent.py's existing
multi-agent team (researcher/planner/specialist/programmer/debugger/
tester — see the "Multi-agent collaboration" section of agent.py) the
spec's remaining specialist roles:

    Coordinator   — decides the roster, watches every stage, reports
    Planner       — breaks the request into ordered sub-tasks
    Research      — gathers outside context (live web search)
    Coding        — executes real tools / writes code
    Reviewer      — cross-checks the coding agent's work for gaps
    Testing       — spot-checks numbers + sandbox-runs generated code
    Security      — real static security scan of generated code
    Documentation — writes the summary/report pass
    Performance   — flags obvious performance problems in generated code
    UI            — reviews UI-facing suggestions (only for UI requests)
    Architecture  — reviews structure/design of the proposed solution

Same honest architecture note as agent.py: CCT talks to one configured
provider, so "agents" are specialized prompt passes over that provider,
sequenced by the Coordinator, with the Coding agent running the real
tool loop. The Coordinator is the only object that decides which
specialists join and in what order; it reports every agent start/finish
through `on_agent(role_key, role_label, status)` so the UI can show a
live roster.

The orchestrated run returns a full record:
    final_text, steps, meta, agents  where `agents` is the ordered list
    of {key, label, status, summary} the coordinator monitored.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import json
import re

from . import aicore
from . import agent
from . import security_scanner
from . import sound
from . import event_stream

# All spec-listed specialist roles. `matches` is a content gate — the
# role only joins the roster when the request actually needs it.
SPECIALIST_ROLES = {
    "coordinator": ("Coordinator", "assigns work and monitors every other agent"),
    "planner": ("Planner", "breaks the request into an ordered task list"),
    "research": ("Research", "gathers outside context via live web search"),
    "coding": ("Coding", "executes real tools to do the work"),
    "reviewer": ("Reviewer", "cross-checks the result against the request"),
    "testing": ("Testing", "spot-checks numbers and sandbox-runs generated code"),
    "security": ("Security", "static security scan of any generated code"),
    "documentation": ("Documentation", "writes the final report"),
    "performance": ("Performance", "flags performance problems in generated code"),
    "ui": ("UI", "reviews UI-facing suggestions"),
    "architecture": ("Architecture", "reviews the design structure"),
}

_CODE_HINTS = re.compile(
    r"\b(code|python|script|program|function|write a .*(class|module)|"
    r"generate.*(code|script))\b", re.I)
_UI_HINTS = re.compile(
    r"\b(ui|interface|screen|layout|widget|button|menu|dashboard|"
    r"frontend|web page|landing page|design)\b", re.I)
_ARCH_HINTS = re.compile(
    r"\b(architecture|design|structure|module|layers?|service|"
    r"microservice|api design|database schema|data model)\b", re.I)
_PERF_HINTS = re.compile(
    r"\b(performance|fast|speed up|optimize|slow|efficient|benchmark)\b", re.I)

_REVIEWER_PROMPT = """You are the REVIEWER on an AI team working inside CCT
(Chemistry Calc Terminal). You are handed the ORIGINAL request and the
CODING agent's final answer. Look for: parts of the request left
unanswered, implied assumptions that were never stated, and results
that don't obviously follow from the given data. Reply with ONLY a JSON
object:
{"ok": true, "note": ""} if the answer covers the request, or
{"ok": false, "note": "<what's missing or wrong, one sentence>"}."""

_PERFORMANCE_PROMPT = """You are the PERFORMANCE agent on an AI team working
inside CCT. You are handed the generated code (or solution). Identify at
most 3 concrete performance problems (algorithmic complexity, repeated
work, I/O patterns) — no fluff. Reply with ONLY a JSON object:
{"ok": true, "note": "no significant issues"} or
{"ok": false, "note": "<problem 1; problem 2; ...>"}."""

_ARCHITECTURE_PROMPT = """You are the ARCHITECTURE agent on an AI team working
inside CCT. You are handed the original request and the proposed
solution. Assess whether the structure (files/modules/components/API
shape) is sound, and name at most 2 concrete structural improvements.
Reply with ONLY a JSON object:
{"ok": true, "note": "structure is sound"} or
{"ok": false, "note": "<concrete improvements>"}."""

_UI_PROMPT = """You are the UI agent on an AI team working inside CCT. You
are handed the request and the proposed solution. Assess usability and
visual clarity at a high level; suggest at most 2 concrete improvements
(layout, hierarchy, affordances — not pixel details). Reply with ONLY a
JSON object:
{"ok": true, "note": "UI approach is sound"} or
{"ok": false, "note": "<concrete improvements>"}."""


def _extract_json(text):
    if not text:
        return {}
    try:
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
        m = re.search(r"\{.*\}", text, re.S)
        return json.loads(m.group(0)) if m else {}
    except Exception:
        return {}


def _quick_judge(prompt_text, system_prompt):
    """One focused model pass that returns (ok, note) — the generic
    reviewer-style check used by reviewer/performance/architecture/ui.
    Never raises; a garbled response is treated as 'ok' (no fabricated
    criticism) — same honesty rule agent.py's _verify_answer uses."""
    try:
        raw = aicore.query_ai(prompt_text, system_prompt=system_prompt)
        data = _extract_json(raw)
        if data.get("ok") is False and data.get("note"):
            return False, str(data["note"])
        return True, ""
    except Exception:
        return True, ""


def run_orchestrated(user_text, max_steps=agent.MAX_STEPS, on_agent=None,
                     mode="agent", permission_callback=None, turn_id=""):
    """Runs the Coordinator-led specialist pipeline. Returns
    (final_text, steps, meta, agents) where agents is the monitored
    roster (list of {key, label, status, summary})."""

    agents = []
    _act_ids = {}  # key -> activity id for live activity tracking

    def _report(key, status, summary=""):
        label = SPECIALIST_ROLES[key][0]
        agents.append({"key": key, "label": label, "status": status, "summary": summary})
        if on_agent:
            on_agent(key, label, status, summary)
        # v0.8.0: Emit to event stream
        try:
            if status == "start":
                event_stream.stream.emit("agent_started", source="orchestrator",
                                         role=key, label=label)
            elif status == "done":
                event_stream.stream.emit("agent_completed", source="orchestrator",
                                         role=key, label=label, summary=summary)
        except Exception:
            pass

    def _run(key):
        _report(key, "start")
        sound.play("tool")
        # v0.8.0: Create live Activity for this specialist agent
        try:
            from . import activity as _act
            label = SPECIALIST_ROLES[key][0]
            desc = SPECIALIST_ROLES[key][1]
            act = _act.manager.create(
                type=_act.TYPE_STATUS, action="agent",
                title=f"Agent: {label}",
                status=_act.RUNNING, turn_id=turn_id,
                details=desc, description=f"{label} — {desc}"
            )
            _act_ids[key] = act.id
        except Exception:
            pass

    def _done(key, summary=""):
        _report(key, "done", summary)
        sound.play("success")
        # v0.8.0: Complete the live Activity for this specialist
        try:
            from . import activity as _act
            aid = _act_ids.get(key)
            if aid:
                _act.manager.update(aid, status=_act.COMPLETED, result=summary[:100] if summary else "Done")
        except Exception:
            pass

    system_prompt = agent.AGENT_SYSTEM_PROMPT if mode == "agent" else agent.AI_SYSTEM_PROMPT

    # ---- Coordinator: build the roster -----------------------------------
    wants_code = bool(_CODE_HINTS.search(user_text))
    wants_ui = bool(_UI_HINTS.search(user_text))
    wants_arch = bool(_ARCH_HINTS.search(user_text))
    wants_perf = bool(_PERF_HINTS.search(user_text))
    wants_research = bool(agent._RESEARCH_HINTS.search(user_text))
    roster = ["planner"]
    if wants_research:
        roster.insert(0, "research")
    roster.append("coding")
    roster.append("reviewer")
    if wants_ui:
        roster.append("ui")
    if wants_perf:
        roster.append("performance")
    if wants_arch:
        roster.append("architecture")
    if wants_code:
        roster.extend(["security", "testing"])
    roster.append("documentation")
    _report("coordinator", "start",
            f"roster: {', '.join(SPECIALIST_ROLES[r][0] for r in roster)}")

    # ---- Planner -----------------------------------------------------------
    _run("planner")
    plan = agent._plan_steps(user_text, system_prompt)
    _done("planner", f"{len(plan)} milestone(s)")

    # ---- Research ----------------------------------------------------------
    research_brief = ""
    if wants_research:
        _run("research")
        research_brief = agent._research_pass(user_text, system_prompt)
        _done("research", "brief folded in" if research_brief else "nothing relevant found")

    # ---- Coding (the real tool loop) --------------------------------------
    _run("coding")
    plan_note = ("\n\nTEAM PLAN (from the Planner \u2014 follow it, adapt if needed):\n" +
                 "\n".join(f"{i+1}. {p}" for i, p in enumerate(plan)))
    if research_brief:
        plan_note += "\n\n" + research_brief
    final_text, steps, meta = agent.run_agent(
        user_text + plan_note, max_steps=max_steps, verbose=False, mode=mode,
        permission_callback=permission_callback, turn_id=turn_id)
    _done("coding", f"{len(steps)} tool step(s)")

    # ---- Reviewer -----------------------------------------------------------
    _run("reviewer")
    ok, note = _quick_judge(
        "ORIGINAL REQUEST:\n" + user_text +
        "\n\nCODING AGENT'S ANSWER:\n" + final_text,
        _REVIEWER_PROMPT)
    if not ok and note:
        final_text = final_text + f"\n\n\u2696 Reviewer flag: {note}"
    _done("reviewer", "ok" if ok else f"flag: {note}")

    # ---- UI / Performance / Architecture (content-gated) -------------------
    for key, prompt, prompt_text in (
        ("ui", _UI_PROMPT, "REQUEST:\n" + user_text + "\n\nSOLUTION:\n" + final_text),
        ("performance", _PERFORMANCE_PROMPT, "GENERATED CODE/SOLUTION:\n" + final_text),
        ("architecture", _ARCHITECTURE_PROMPT,
         "ORIGINAL REQUEST:\n" + user_text + "\n\nPROPOSED SOLUTION:\n" + final_text),
    ):
        if key not in roster:
            continue
        _run(key)
        p_ok, p_note = _quick_judge(prompt_text, prompt)
        if not p_ok and p_note:
            final_text = final_text + f"\n\n\u26a0 {SPECIALIST_ROLES[key][0]} note: {p_note}"
        _done(key, "ok" if p_ok else f"note: {p_note}")

    # ---- Security + Testing (only for coding requests) ---------------------
    if wants_code:
        _run("security")
        code = agent._extract_code_block(final_text)
        findings = security_scanner.scan_code(code) if code else []
        if findings:
            final_text += agent._DEBUGGER_NOTE_TEMPLATE.format(
                summary=security_scanner.summarize(findings),
                details="\n".join(f"  {repr(f)}" for f in findings[:5]))
        _done("security",
              f"{len(findings)} finding(s)" if findings else "no risky patterns")

        _run("testing")
        final_text, debug_note = agent._debug_pass(final_text)
        if debug_note:
            sb = debug_note.get("sandbox_test")
            _done("testing", f"risk {debug_note.get('risk')}" +
                  (f" \u00b7 sandbox exit {sb.get('returncode')}" if isinstance(sb, dict) else ""))
        else:
            _done("testing", "no code block to test")
    else:
        _run("testing")
        ok_t, note_t = agent._verify_answer(user_text, plan, final_text, system_prompt)
        if not ok_t and note_t:
            final_text = final_text + f"\n\n\u26a0 Tester flagged this for review: {note_t}"
        _done("testing", "ok" if ok_t else f"flag: {note_t}")

    # ---- Documentation ------------------------------------------------------
    _run("documentation")
    doc = ("\u2705 Orchestrated run complete\n\n"
           "Agents that worked on this:\n" +
           "\n".join(f"- {SPECIALIST_ROLES[a['key']][0]} \u2014 {a['status']}"
                     + (f" ({a['summary']})" if a.get("summary") else "")
                     for a in agents if a["key"] != "coordinator"))
    final_text = final_text.rstrip() + "\n\n" + doc
    _done("documentation", "final report appended")

    _report("coordinator", "done", f"{len(agents)} agent events monitored")
    meta = dict(meta or {})
    meta["roster"] = [a["key"] for a in agents]
    return final_text, steps, meta, agents
