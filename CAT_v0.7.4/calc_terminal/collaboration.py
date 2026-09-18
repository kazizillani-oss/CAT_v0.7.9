"""
CCT — collaboration.py: Multi-AI Collaboration Engine.

Extends the single-orchestrator pattern (orchestrator.py) into a richer
multi-agent collaboration framework with:

  - A shared CollaborationContext that every agent reads from and writes to.
  - Named agent roles, each with a dedicated system prompt.
  - File-lock coordination so two agents never edit the same file at once.
  - A MultiAgentOrchestrator that sequences roles, feeds the real tool
    system (agent.TOOLS) to the coding agent, and collects structured
    findings from every stage.

Usage:
    from .collaboration import MultiAgentOrchestrator, CollaborationContext

    orch = MultiAgentOrchestrator(query_fn=aicore.query_ai, tools_dict=agent.TOOLS)
    final_text, steps, meta, agents = orch.run_collaborative("Plot the Arrhenius curve for ...")
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import aicore
from . import tool_call_normalizer
from . import agent
from . import security_scanner
from . import sandbox

# =====================================================================
#  Agent Role Constants
# =====================================================================

PLANNER = "planner"
RESEARCHER = "researcher"
ARCHITECT = "architect"
CODER = "coder"
UI_DESIGNER = "ui_designer"
DEBUGGER = "debugger"
REVIEWER = "reviewer"
TESTER = "tester"
SECURITY = "security"
FINALIZER = "finalizer"

# =====================================================================
#  Agent Role System Prompts
# =====================================================================

ROLE_PROMPTS: Dict[str, str] = {
    PLANNER: (
        "You are the PLANNER on a multi-AI team working inside CAT "
        "(Chemistry Calc Terminal). You break a user request into a concise, "
        "ordered list of concrete subtasks that other agents can execute "
        "independently. You do NOT solve anything or call tools yourself.\n"
        "Reply with ONLY a JSON object:\n"
        '{"plan": ["subtask 1", "subtask 2", ...]}\n'
        "Keep it to 2-8 actionable steps. No prose outside the JSON."
    ),
    RESEARCHER: (
        "You are the RESEARCHER on a multi-AI team working inside CCT. You "
        "gather external context via live web search so other agents do not "
        "reason from stale training data on fast-moving facts.\n"
        "You receive the original request and any prior findings. Produce a "
        "short, cited research brief — bullet points with sources — that the "
        "team can fold into their work. If nothing relevant is found, say so "
        "plainly. No fabrication."
    ),
    ARCHITECT: (
        "You are the ARCHITECT on a multi-AI team working inside CCT. You "
        "review the structural design of proposed solutions: module layout, "
        "file organisation, API boundaries, data flow.\n"
        "You receive the original request and the current solution. Reply "
        "with ONLY a JSON object:\n"
        '{"ok": true/false, "note": "<concrete structural observation or '
        'improvement suggestion, one sentence>"}'
    ),
    CODER: (
        "You are the CODER on a multi-AI team working inside CCT. You have "
        "access to real tools (solve formulas, plot, write files, run "
        "commands, etc.). Use them — never fabricate results that could be "
        "computed.\n"
        "Follow the plan handed to you. When you are finished, return a "
        "comprehensive answer using the standard CAT notebook format."
    ),
    UI_DESIGNER: (
        "You are the UI_DESIGNER on a multi-AI team working inside CCT. You "
        "evaluate the usability, layout, and visual clarity of UI-facing "
        "proposals.\n"
        "Reply with ONLY a JSON object:\n"
        '{"ok": true/false, "note": "<concrete UI improvement or approval>"}'
    ),
    DEBUGGER: (
        "You are the DEBUGGER on a multi-AI team working inside CCT. You "
        "review generated code for correctness, edge cases, and runtime "
        "errors. You may also run sandboxed tests.\n"
        "Reply with ONLY a JSON object:\n"
        '{"ok": true/false, "note": "<issue description or \'no issues\'>"}'
    ),
    REVIEWER: (
        "You are the REVIEWER on a multi-AI team working inside CCT. You "
        "cross-check the CODER's final output against the original request. "
        "Look for unanswered parts, implied assumptions, and inconsistencies.\n"
        "Reply with ONLY a JSON object:\n"
        '{"ok": true/false, "note": "<what is missing or wrong, one sentence>"}'
    ),
    TESTER: (
        "You are the TESTER on a multi-AI team working inside CCT. You "
        "spot-check arithmetic, units, and internal consistency of the "
        "answer against the given data.\n"
        "Reply with ONLY a JSON object:\n"
        '{"ok": true/false, "note": "<what looks wrong, one sentence>"}'
    ),
    SECURITY: (
        "You are the SECURITY agent on a multi-AI team working inside CCT. "
        "You run a static security scan on any generated code and flag "
        "dangerous patterns (subprocess calls, eval, exec, file-system "
        "deletion, credential leaks, network calls, etc.).\n"
        "Reply with ONLY a JSON object:\n"
        '{"ok": true/false, "note": "<findings summary or \'clean\'>"}'
    ),
    FINALIZER: (
        "You are the FINALIZER on a multi-AI team working inside CCT. You "
        "receive all prior agent findings, decisions, and the coder's output. "
        "Your job is to produce the single polished final answer the user "
        "will see — merging feedback, resolving conflicts, and ensuring "
        "completeness.\n"
        "Reply with ONLY the final answer text, no JSON wrapper."
    ),
}

# =====================================================================
#  Content-gate patterns (which roles to activate for which task types)
# =====================================================================

_CODE_HINTS = re.compile(
    r"\b(code|python|script|program|function|write a .*(class|module)|"
    r"generate.*(code|script))\b", re.I)
_UI_HINTS = re.compile(
    r"\b(ui|interface|screen|layout|widget|button|menu|dashboard|"
    r"frontend|web page|landing page|design)\b", re.I)
_ARCH_HINTS = re.compile(
    r"\b(architecture|design|structure|module|layers?|service|"
    r"microservice|api design|database schema|data model)\b", re.I)
_RESEARCH_HINTS = re.compile(
    r"\b(latest|recent|current|news|today|this year|search|look up|find out|"
    r"who is|what happened|price of|update on)\b", re.I)

# =====================================================================
#  CollaborationContext — shared mutable state passed between agents
# =====================================================================

@dataclass
class CollaborationContext:
    """Mutable state bag shared across all agents during a collaborative run.

    Every agent reads from and appends to the fields it cares about. The
    orchestrator is responsible for serialising this context into each
    agent's prompt so they can see what prior agents decided / found.
    """
    task: str = ""
    project_state: Dict[str, Any] = field(default_factory=dict)
    relevant_files: List[str] = field(default_factory=list)
    agent_findings: Dict[str, Any] = field(default_factory=dict)
    decisions: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # serialisation helpers
    # ------------------------------------------------------------------
    def to_prompt_block(self, exclude_roles: Optional[List[str]] = None) -> str:
        """Render the context as a short text block suitable for injection
        into a system prompt so an agent can see what came before it."""
        exclude = set(exclude_roles or [])
        lines: List[str] = []
        if self.task:
            lines.append(f"TASK: {self.task}")
        if self.decisions:
            lines.append("DECISIONS:")
            for d in self.decisions:
                lines.append(f"  - {d}")
        if self.issues:
            lines.append("OPEN ISSUES:")
            for i in self.issues:
                lines.append(f"  - {i}")
        if self.open_questions:
            lines.append("OPEN QUESTIONS:")
            for q in self.open_questions:
                lines.append(f"  - {q}")
        if self.relevant_files:
            lines.append("RELEVANT FILES: " + ", ".join(self.relevant_files))
        for role_key, finding in self.agent_findings.items():
            if role_key in exclude:
                continue
            label = role_key.replace("_", " ").title()
            lines.append(f"{label.upper()} FINDING: {finding}")
        return "\n".join(lines)


# =====================================================================
#  FileLockManager — prevent concurrent edits to the same file
# =====================================================================

class FileLockManager:
    """Lightweight in-process file lock.

    Agents request an exclusive lock before editing a file and release it
    when done.  If another agent already holds the lock the request fails
    (returns False) so the orchestrator can retry or skip.

    Thread-safe via a lock on the internal dict.
    """

    def __init__(self) -> None:
        self._locked: Dict[str, str] = {}       # file_path -> agent_id
        self._lock = threading.Lock()

    def lock(self, file_path: str, agent_id: str) -> bool:
        """Attempt to acquire an exclusive lock for *file_path*.

        Returns True on success, False if another agent already holds it.
        """
        with self._lock:
            if file_path in self._locked:
                return False
            self._locked[file_path] = agent_id
            return True

    def unlock(self, file_path: str, agent_id: str) -> None:
        """Release the lock on *file_path* if *agent_id* is the current owner.

        Safe to call even if the lock was already released.
        """
        with self._lock:
            if self._locked.get(file_path) == agent_id:
                del self._locked[file_path]

    def is_locked(self, file_path: str) -> bool:
        """Return True if *file_path* is currently locked by any agent."""
        with self._lock:
            return file_path in self._locked

    def get_lock_owner(self, file_path: str) -> Optional[str]:
        """Return the agent_id that holds the lock, or None."""
        with self._lock:
            return self._locked.get(file_path)

    def release_all(self, agent_id: str) -> List[str]:
        """Release every lock held by *agent_id*. Returns list of paths released."""
        released: List[str] = []
        with self._lock:
            for path in list(self._locked):
                if self._locked[path] == agent_id:
                    del self._locked[path]
                    released.append(path)
        return released


# =====================================================================
#  MultiAgentOrchestrator
# =====================================================================

def _extract_json(text: str) -> Dict[str, Any]:
    """Best-effort extraction of the first JSON object from *text*."""
    if not text:
        return {}
    try:
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
        m = re.search(r"\{.*\}", text, re.S)
        return json.loads(m.group(0)) if m else {}
    except Exception:
        return {}


class MultiAgentOrchestrator:
    """Sequences specialist AI agents through a shared CollaborationContext.

    Parameters
    ----------
    query_fn : callable
        The AI query function — ``aicore.query_ai`` by default.  Signature:
        ``query_fn(prompt, system_prompt=...) -> str``.
    tools_dict : dict
        The tools dictionary — ``agent.TOOLS`` by default.  Only the CODER
        role receives this directly; other roles see a filtered tool list
        or no tools at all.
    """

    def __init__(self, query_fn: Optional[Callable] = None,
                 tools_dict: Optional[Dict[str, Any]] = None) -> None:
        self.query_fn = query_fn or aicore.query_ai
        self.tools_dict = tools_dict or agent.TOOLS
        self.file_locks = FileLockManager()

    # ------------------------------------------------------------------
    #  Internal helpers
    # ------------------------------------------------------------------

    def _query(self, prompt: str, system_prompt: str) -> str:
        """Thin wrapper so all AI calls go through one choke-point."""
        try:
            raw = self.query_fn(prompt, system_prompt=system_prompt)
            return raw or ""
        except Exception:
            return ""

    def _extract_code_block(self, text: str) -> Optional[str]:
        """Pull the first fenced Python code block out of *text*."""
        m = re.search(r"```(?:python)?\s*\n(.*?)```", text or "", re.S)
        return m.group(1) if m else None

    def _activate_roles(self, user_text: str,
                        roles: Optional[List[str]] = None) -> List[str]:
        """Determine which roles to activate based on task content and the
        explicit *roles* override.

        v0.7.9.0 (requirement #21 — DYNAMIC TEAM): the roster size now
        follows real task complexity instead of always fielding everyone.
        The model_router's complexity score decides:
            simple   (<= 0.35) → planner + coder + finalizer
            moderate (<= 0.6)  → + reviewer + tester
            complex  (> 0.6)   → full gated roster (architect/ui/security/
                                 debugger/researcher as content warrants)
        """
        if roles is not None:
            return list(roles)

        try:
            from . import model_router as _mr
            types = _mr.classify(user_text)
            complexity = _mr.complexity_score(types, user_text)
        except Exception:
            types, complexity = set(), 0.4

        roster: List[Dict[str, str]] = [PLANNER, CODER]
        wants_code = bool(_CODE_HINTS.search(user_text))
        wants_ui = bool(_UI_HINTS.search(user_text))
        wants_arch = bool(_ARCH_HINTS.search(user_text))
        wants_research = bool(_RESEARCH_HINTS.search(user_text))

        if complexity <= 0.35:
            # Simple task: a second opinion is latency theatre — skip it.
            pass
        elif complexity <= 0.6:
            roster.extend([REVIEWER, TESTER])
        else:
            if wants_research:
                roster.append(RESEARCHER)
            if wants_arch:
                roster.append(ARCHITECT)
            if wants_ui:
                roster.append(UI_DESIGNER)
            roster.append(REVIEWER)
            if wants_code:
                roster.extend([DEBUGGER, SECURITY])
            roster.append(TESTER)

        roster.append(FINALIZER)
        # De-duplicate preserving order.
        seen: set = set()
        return [r for r in roster if not (r in seen or seen.add(r))]

    def _run_single_role(self, role: str, ctx: CollaborationContext,
                         user_text: str, plan: List[str],
                         coder_result: str, steps: List,
                         permission_callback: Optional[Callable] = None,
                         on_agent: Optional[Callable] = None,
                         record_finding: bool = True) -> str:
        """Run one non-CODER specialist role and return its output string.

        v0.7.9.0 fixes:
        * The output is now actually recorded into
          `ctx.agent_findings[role]` — previously the planner's plan was
          written nowhere, so run_collaborative always read an empty
          finding and silently fell back to a generic one-step plan.
        * RESEARCHER performs a REAL web search (aicore.web_search) and
          hands the genuine snippets to the model, instead of pretending.
        """
        role_label = role.replace("_", " ").title()
        if on_agent:
            on_agent(role, role_label, "start", "")

        ctx_block = ctx.to_prompt_block(exclude_roles=[role])
        prompt_parts: List[str] = []

        # Build role-specific prompt
        if role == PLANNER:
            prompt_parts.append(f"User request:\n{user_text}")
        elif role == RESEARCHER:
            prompt_parts.append(f"User request:\n{user_text}")
            prompt_parts.append(f"Context:\n{ctx_block}")
        elif role == ARCHITECT:
            prompt_parts.append(f"ORIGINAL REQUEST:\n{user_text}")
            prompt_parts.append(f"CURRENT SOLUTION:\n{coder_result or '(not yet produced)'}")
            prompt_parts.append(f"CONTEXT:\n{ctx_block}")
        elif role == UI_DESIGNER:
            prompt_parts.append(f"ORIGINAL REQUEST:\n{user_text}")
            prompt_parts.append(f"CURRENT SOLUTION:\n{coder_result}")
            prompt_parts.append(f"CONTEXT:\n{ctx_block}")
        elif role == REVIEWER:
            prompt_parts.append(f"ORIGINAL REQUEST:\n{user_text}")
            prompt_parts.append(f"PLAN:\n" + "\n".join(f"- {p}" for p in plan))
            prompt_parts.append(f"CODER OUTPUT:\n{coder_result}")
            prompt_parts.append(f"CONTEXT:\n{ctx_block}")
        elif role == TESTER:
            prompt_parts.append(f"ORIGINAL REQUEST:\n{user_text}")
            prompt_parts.append(f"PLAN:\n" + "\n".join(f"- {p}" for p in plan))
            prompt_parts.append(f"CODER OUTPUT:\n{coder_result}")
            prompt_parts.append(f"CONTEXT:\n{ctx_block}")
        elif role == DEBUGGER:
            prompt_parts.append(f"CODE TO REVIEW:\n{coder_result}")
            prompt_parts.append(f"CONTEXT:\n{ctx_block}")
        elif role == SECURITY:
            prompt_parts.append(f"CODE TO SCAN:\n{coder_result}")
            prompt_parts.append(f"CONTEXT:\n{ctx_block}")
        elif role == FINALIZER:
            prompt_parts.append(f"ORIGINAL REQUEST:\n{user_text}")
            prompt_parts.append(f"PLAN:\n" + "\n".join(f"- {p}" for p in plan))
            prompt_parts.append(f"CODER OUTPUT:\n{coder_result}")
            prompt_parts.append(f"ALL FINDINGS:\n{ctx_block}")
        else:
            prompt_parts.append(f"User request:\n{user_text}")
            prompt_parts.append(f"Context:\n{ctx_block}")

        prompt = "\n\n".join(prompt_parts)
        system = ROLE_PROMPTS.get(role, ROLE_PROMPTS[PLANNER])

        # RESEARCHER: real web retrieval first; the model then synthesizes
        # over the ACTUAL results (never fabricated sources).
        if role == RESEARCHER:
            try:
                results = aicore.web_search(user_text, max_results=5) or []
            except Exception:
                results = []
            if results:
                evidence = "\n\n".join(
                    f"[{i + 1}] {r['title']}\n{r['url']}\n{r['snippet']}"
                    for i, r in enumerate(results))
                prompt += ("\n\nLIVE SEARCH RESULTS (use ONLY these as external "
                           "facts, cite by bracket number):\n" + evidence)
                system += " Cite the bracketed result numbers you used."
            else:
                prompt += ("\n\nLIVE SEARCH RESULTS: none retrieved (search "
                           "unreachable). Say so plainly — do not invent sources.")
                system += " No web results were retrievable; say so plainly."

        output = self._query(prompt, system)

        # Parse structured JSON responses where expected
        if role in (PLANNER, REVIEWER, TESTER, UI_DESIGNER, ARCHITECT,
                    DEBUGGER, SECURITY):
            data = _extract_json(output)
            if role == PLANNER:
                plan_data = data.get("plan")
                if isinstance(plan_data, list) and plan_data:
                    output = json.dumps({"plan": [str(s) for s in plan_data[:8]]})
            # For review-type roles, store as-is; orchestrator decides what to do

        # THE FIX: record the finding so later roles (and the orchestrator)
        # can actually see this agent's work via the shared context.
        if record_finding:
            try:
                ctx.agent_findings[role] = output
            except Exception:
                pass

        if on_agent:
            summary = output[:120].replace("\n", " ") if output else "(empty)"
            on_agent(role, role_label, "done", summary)

        return output

    # ------------------------------------------------------------------
    #  File-locking integration for the CODER role
    # ------------------------------------------------------------------

    def _acquire_file_locks(self, coder_result: str, coder_id: str = "coder") -> None:
        """Scan coder output for write_file / create_folder tool calls and
        acquire file locks for the paths they touch."""
        for tr in coder_result if isinstance(coder_result, list) else []:
            if isinstance(tr, dict):
                tool_name = tr.get("tool", "")
                args = tr.get("args", {})
                path = args.get("path", "")
                if tool_name in ("write_file", "rename_file", "delete_file") and path:
                    self.file_locks.lock(path, coder_id)
                elif tool_name == "create_folder" and path:
                    self.file_locks.lock(path, coder_id)

    def _release_file_locks(self, coder_id: str = "coder") -> None:
        """Release all locks held by the coder agent."""
        self.file_locks.release_all(coder_id)

    # ------------------------------------------------------------------
    #  Main collaborative pipeline
    # ------------------------------------------------------------------

    def run_collaborative(
        self,
        user_text: str,
        roles: Optional[List[str]] = None,
        on_agent: Optional[Callable] = None,
        permission_callback: Optional[Callable] = None,
        max_steps: int = 12,
    ) -> Tuple[str, list, dict, list]:
        """Run the full multi-agent collaborative pipeline.

        Parameters
        ----------
        user_text : str
            The user's original request.
        roles : list[str] | None
            Explicit roster of role keys to activate.  When *None* the
            roster is chosen automatically based on task content.
        on_agent : callable | None
            ``on_agent(role_key, role_label, status, summary)`` — called
            on every agent start/done event so the UI can show a live
            roster.  *status* is ``"start"`` or ``"done"``.
        permission_callback : callable | None
            Forwarded to the CODER's ``agent.run_agent`` call for
            write-permission gates.
        max_steps : int
            Maximum tool-loop steps for the CODER agent.

        Returns
        -------
        (final_text, steps, meta, agents)
            final_text : str   — the merged, polished answer.
            steps : list       — tool-call steps from the CODER agent.
            meta : dict        — pipeline metadata (roster, plan, etc.).
            agents : list[dict] — ``{key, label, status, summary}`` for
                                  every agent event (chronological).
        """

        agents: List[Dict[str, str]] = []
        steps: List[Any] = []
        ctx = CollaborationContext(task=user_text)

        def _report(key: str, status: str, summary: str = "") -> None:
            label = key.replace("_", " ").title()
            agents.append({"key": key, "label": label, "status": status, "summary": summary})
            if on_agent:
                on_agent(key, label, status, summary)
            try:
                from .event_stream import stream as _es, MULTI_AGENT_PROGRESS
                _es.emit(MULTI_AGENT_PROGRESS, source="multi_ai",
                         agent=key, status=status, summary=str(summary)[:160])
            except Exception:
                pass

        try:
            from .event_stream import stream as _es, MULTI_AGENT_STARTED
            roster_preview = self._activate_roles(user_text, roles)
            _es.emit(MULTI_AGENT_STARTED, source="multi_ai",
                     roster=roster_preview, task=user_text[:200])
        except Exception:
            pass

        # ---- 1. Determine which roles to activate --------------------
        roster = self._activate_roles(user_text, roles)
        _report("orchestrator", "start",
                f"roster: {', '.join(r.replace('_', ' ').title() for r in roster)}")

        # ---- 2. PLANNER — break task into subtasks -------------------
        plan: List[str] = []
        if PLANNER in roster:
            self._run_single_role(PLANNER, ctx, user_text, [], "", steps,
                                  permission_callback, on_agent)
            # Parse plan from the planner's REAL recorded finding
            # (ctx.agent_findings is now actually written — see
            # _run_single_role's v0.7.9.0 fix).
            planner_findings = ctx.agent_findings.get(PLANNER, "")
            data = _extract_json(planner_findings)
            plan_raw = data.get("plan")
            if isinstance(plan_raw, list) and plan_raw:
                plan = [str(s) for s in plan_raw[:8]]
            else:
                plan = ["Work out and answer the question directly."]
            ctx.decisions.append(f"Plan: {len(plan)} subtasks defined")
        else:
            plan = ["Work out and answer the question directly."]

        # ---- 3. RESEARCHER — real web search for context ------------------
        research_brief = ""
        if RESEARCHER in roster:
            research_brief = self._run_single_role(
                RESEARCHER, ctx, user_text, plan, "", steps,
                permission_callback, on_agent)
            if research_brief:
                ctx.decisions.append("Research brief obtained")

        # ---- 4. CODER — run the real tool loop -----------------------
        coder_result = ""
        coder_steps: list = []
        if CODER in roster:
            _report(CODER, "start", "running tool loop")
            plan_note = "\n\nTEAM PLAN (from the Planner — follow it, adapt if needed):\n" + \
                "\n".join(f"{i+1}. {p}" for i, p in enumerate(plan))
            if research_brief:
                plan_note += "\n\nRESEARCH BRIEF:\n" + research_brief

            try:
                coder_result, coder_steps, coder_meta = agent.run_agent(
                    user_text + plan_note,
                    max_steps=max_steps,
                    verbose=False,
                    mode="agent",
                    permission_callback=permission_callback,
                )
            except Exception as exc:
                coder_result = f"(Coder agent failed: {exc})"
                coder_meta = {}

            steps.extend(coder_steps)
            ctx.agent_findings[CODER] = coder_result
            # Shared structured state (requirement #22): every later role
            # sees the actual tool results instead of rediscovering them.
            ctx.tool_results = [{"tool": t, "args": a, "result": str(r)[:400]}
                                for t, a, r, _c in coder_steps]
            ctx.relevant_files = [
                (a or {}).get("path") for t, a, _r, _c in coder_steps
                if isinstance(a, dict) and a.get("path")]
            ctx.decisions.append(f"Coder completed {len(coder_steps)} tool step(s)")

            # Acquire file locks for any files the coder wrote
            self._acquire_file_locks(coder_steps, "coder")
            _report(CODER, "done", f"{len(coder_steps)} tool step(s)")

        # ---- 5-8. INDEPENDENT REVIEW ROLES — run in PARALLEL ----------
        # REVIEWER / SECURITY / DEBUGGER / TESTER / ARCHITECT /
        # UI_DESIGNER all consume the SAME finished coder output and do
        # not write files, so they are genuinely independent work
        # (requirement #11/#24): executed concurrently on a thread pool,
        # cutting wall-clock review time to roughly the slowest single
        # role instead of the sum of all of them.
        parallel_roles = [r for r in (SECURITY, DEBUGGER, REVIEWER, TESTER,
                                      ARCHITECT, UI_DESIGNER) if r in roster]
        if parallel_roles:
            try:
                from .event_stream import stream as _es
                _es.emit(MULTI_AGENT_PROGRESS, source="multi_ai",
                         agent="review-team",
                         status="start",
                         summary=f"{len(parallel_roles)} reviewer(s) running concurrently")
            except Exception:
                pass
            max_workers = min(4, len(parallel_roles))
            with ThreadPoolExecutor(max_workers=max_workers,
                                    thread_name_prefix="cat-review") as pool:
                futures = {
                    r: pool.submit(
                        self._run_single_role, r, ctx, user_text, plan,
                        coder_result, steps, permission_callback, on_agent)
                    for r in parallel_roles
                }
                outputs = {}
                for role_key, fut in futures.items():
                    try:
                        outputs[role_key] = fut.result()
                    except Exception as exc:
                        outputs[role_key] = ""
                        ctx.issues.append(f"{role_key}: reviewer crashed ({exc})")
            for role_key, out in outputs.items():
                data = _extract_json(out or "")
                if isinstance(data, dict) and data.get("ok") is False and data.get("note"):
                    label = {"security": "Security", "debugger": "Debugger",
                             "reviewer": "Reviewer", "tester": "Tester",
                             "architect": "Architecture",
                             "ui_designer": "UI"}.get(role_key, role_key.title())
                    ctx.issues.append(f"{label}: {data['note']}")
                ctx.agent_findings.setdefault(role_key, out or "")

        # ---- 9. FINALIZER — merge everything into the final answer ---
        final_text = coder_result
        if FINALIZER in roster:
            final_text = self._run_single_role(
                FINALIZER, ctx, user_text, plan, coder_result, steps,
                permission_callback, on_agent)
            # Finalizer may have returned a polished version; fall back
            # to coder_result if it returned empty/garbled output.
            if not final_text or len(final_text.strip()) < 10:
                final_text = coder_result

        # Append a standard issues/flags block if any reviewer flagged issues
        if ctx.issues:
            flag_lines = "\n".join(f"  {i}" for i in ctx.issues)
            final_text = final_text.rstrip() + \
                f"\n\n[Agent Review Flags]\n{flag_lines}\n"

        # ---- 10. Release file locks ----------------------------------
        self._release_file_locks("coder")

        # ---- 11. Build metadata --------------------------------------
        meta: Dict[str, Any] = {
            "roster": [a["key"] for a in agents],
            "plan": plan,
            "research_brief": research_brief,
            "issues": ctx.issues,
            "decisions": ctx.decisions,
            "tool_steps": len(steps),
        }
        _report("orchestrator", "done",
                f"{len(agents)} agent events, {len(ctx.issues)} issue(s)")
        try:
            from .event_stream import stream as _es, MULTI_AGENT_FINISHED
            _es.emit(MULTI_AGENT_FINISHED, source="multi_ai",
                     agents=len(agents), issues=len(ctx.issues),
                     tool_steps=len(steps))
        except Exception:
            pass

        return final_text, steps, meta, agents
