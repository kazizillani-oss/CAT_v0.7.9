"""
CCT — pipeline.py: the AI Execution Pipeline (v0.7.7 spec section 6/7/8).

Large tasks automatically follow the spec's workflow, and the workflow
is VISIBLE to the user the whole way:

    Step 1  Planner Mode   -> analyze request, break into milestones,
                              generate roadmap + task graph + todos,
                              estimate complexity
        (auto switch)
    Step 2  Research Mode  -> search documentation, read APIs, compare
                              technologies, deep reasoning
        (auto switch)
    Step 3  Build Mode     -> create files, install packages, generate
                              code, run tests, fix issues, verify output
        (auto switch)
    Step 4  Notebook Mode  -> report, flowchart, architecture diagram,
                              performance summary, final explanation

Implementation notes (honest scope):
  * Stages are real, sequential passes over the configured AI provider
    (the same single-provider architecture agent.py's multi-agent team
    uses — see its "Multi-agent collaboration" section). Planner and
    Tester are dedicated prompt passes; Implementation reuses
    agent.run_agent()'s real tool-executing loop so files/plots/
    installs genuinely happen; the Debugger pass reuses agent._debug_pass
    (real ast scan + sandbox run).
  * The live todo list (spec section 7) drives the stage UI: the plan
    becomes todos with statuses Pending / Researching / Coding /
    Testing / Completed / Skipped / Failed / Currently Running. Status
    transitions are published through the on_todo callback and the
    eventbus so the Todo panel and the task graph can both react.
  * "Running" is the current stage's highlight (spec section 8) — the
    graph text below is rendered by callers; this module just tracks
    which stage is current and what happened at each.
  * Complexity estimation is a heuristic (word count + plan length),
    labeled as such in the report — not a model call.

Checkpoints (v0.7.8.1): after every completed stage the run state
(plan, todos, steps, research brief, stage) is persisted to
~/.cct_pipeline_checkpoint.json. When a stage fails — say the provider
chain is exhausted mid-run — the caller can run again with
resume=True: matching runs skip the completed stages and continue
from the failed one instead of restarting from the planner. The
checkpoint is cleared once a run reaches 'completed'. This is the
long-task "continue from checkpoint" + provider-failover-resume
behavior, done with real persisted state, not a fiction.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import json
import os
import re
import time

from . import aicore
from . import agent
from . import eventbus
from . import sound

# ------------------------------------------------------------------ stages --
PIPELINE_STAGES = [
    "planner",           # Step 1 — Plan
    "research",          # Step 2 — Research
    "implementation",    # Step 3 — Build
    "testing",           # Step 3b — Test & fix
    "verification",      # Step 3c — Verify
    "documentation",     # Step 4 — Notebook report
    "completed",
]

_STAGE_ORDER = [
    "planner",
    "research",
    "implementation",
    "testing",
    "verification",
    "documentation",
    "completed",
]

_CHECKPOINT_FILE = os.path.join(os.path.expanduser("~"), ".cct_pipeline_checkpoint.json")

STAGE_LABELS = {
    "planner": "\U0001f9ed Planner",
    "research": "\U0001f50d Research",
    "implementation": "\U0001f528 Implementation",
    "testing": "\u2699 Testing",
    "verification": "\u2705 Verification",
    "documentation": "\U0001f4d8 Documentation",
    "completed": "\U0001f389 Completed",
}

# Live-todo status vocabulary (spec section 7) â€” mirrors the statuses
# the Todo panel renders.
TODO_PENDING = "pending"
TODO_RUNNING = "running"          # current stage in flight
TODO_RESEARCHING = "researching"
TODO_CODING = "coding"
TODO_TESTING = "testing"
TODO_COMPLETED = "completed"
TODO_SKIPPED = "skipped"
TODO_FAILED = "failed"

_ANY_STAGE = re.compile(r"\b(planner|planning|research|implementation|build|testing|verify|verification|documentation|docs)\b", re.I)


def _classify_stage(chunk_text):
    """Very cheap keyword stage classifier for the tool-step -> stage
    mapping during Implementation (see _PipelineRun._advance_todos)."""
    t = (chunk_text or "").lower()
    if re.search(r"\b(test|pytest|assert|sandbox)\b", t):
        return "testing"
    if re.search(r"\b(search|research|docs|documentation)\b", t):
        return "research"
    if re.search(r"\b(solve|plot|simulate|calculate|write_file|create_folder)\b", t):
        return "coding"
    return None


def _classify_intent(text):
    """Best-effort complexity + stage-intent estimate for the report
    (spec section 6's "estimate complexity"). Heuristic, labeled as
    such in the report text."""
    words = len(re.findall(r"\w+", text or ""))
    if words < 20:
        return "simple"
    if words < 60:
        return "moderate"
    return "complex"


# ---------------------------------------------------------------- graph --
def task_graph(current_stage=None):
    """The execution graph (spec section 8): planner -> research ->
    implementation -> testing -> verification -> documentation ->
    completed, with the current stage highlighted. Returns a list of
    (stage_key, label, is_current) tuples so callers can render it
    with their own theming."""
    out = []
    for stage in PIPELINE_STAGES:
        out.append((stage, STAGE_LABELS[stage], stage == current_stage))
    return out


def render_task_graph(current_stage, term_width=78):
    """Classic-terminal render of the task graph, current stage
    highlighted with a marker."""
    from . import theme
    lines = []
    for i, (stage, label, current) in enumerate(task_graph(current_stage)):
        arrow = "\u2193"
        if stage == "planner":
            prefix = ""
        else:
            prefix = "  "
        indent = " " * 2
        if current:
            lines.append(f"{indent}{theme.cyan(arrow if stage != 'planner' else ' ')} "
                         f"{theme.cyan('>', bold=True)} {theme.cyan(label, bold=True)}  {theme.orange('\u25cf CURRENT', bold=True)}")
        else:
            lines.append(f"{indent}{theme.faint(arrow if stage != 'planner' else ' ')}  {theme.faint(label)}")
    return lines


# ---------------------------------------------------------- checkpoints --
def save_checkpoint(run) -> bool:
    """Persist a pipeline run's state at its current stage so a later
    run with the same user_text can resume from where it stopped."""
    try:
        payload = {
            "user_text": run.user_text,
            "mode": run.mode,
            "last_completed": run._last_completed,
            "plan": run.plan,
            "todos": run.todos,
            "steps": run.steps,
            "final_text": run.final_text,
            "research_brief": getattr(run, "research_brief", ""),
            "started": run.started,
        }
        with open(_CHECKPOINT_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return True
    except Exception:
        return False


def load_checkpoint() -> dict | None:
    try:
        if os.path.exists(_CHECKPOINT_FILE):
            with open(_CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "last_completed" in data:
                return data
    except Exception:
        pass
    return None


def clear_checkpoint():
    try:
        if os.path.exists(_CHECKPOINT_FILE):
            os.remove(_CHECKPOINT_FILE)
    except Exception:
        pass


def has_checkpoint(user_text) -> bool:
    cp = load_checkpoint()
    return bool(cp and cp.get("user_text") == user_text)


# ------------------------------------------------------------------ run --
class PipelineRun:
    """One full pipeline execution. Callbacks (all optional, all plain
    Python â€” safe from any thread):
        on_note(text)          â€” a one-line status note (stage entered)
        on_stage(stage_key)    â€” stage transition happened
        on_todo(todo_dict)     â€” a todo's status changed
        on_message(text)       â€” free-form text to surface (report lines)
        on_event(ev_dict)      â€” raw pipeline event (for logs/dashboards)
    """

    def __init__(self, user_text, mode="agent", on_note=None, on_stage=None,
                 on_todo=None, on_message=None, on_event=None, permission_callback=None,
                 should_cancel=None):
        self.user_text = user_text
        self.mode = mode
        self.on_note = on_note or (lambda t: None)
        self.on_stage = on_stage or (lambda s: None)
        self.on_todo = on_todo or (lambda t: None)
        self.on_message = on_message or (lambda t: None)
        self.on_event = on_event or (lambda e: None)
        self.permission_callback = permission_callback
        # v0.7.8.1 interrupt: zero-arg callable checked before each stage
        # and threaded into the implementation stage's agent loop.
        self.should_cancel = should_cancel
        self.stage = None
        self.todos = []          # [{id, text, status}]
        self.steps = []          # agent tool steps
        self.plan = []           # planner step list
        self.report_lines = []   # documentation stage output
        self.final_text = ""
        self.started = time.time()
        self.duration = 0.0
        self.failed_stage = None
        self._todo_seq = 0
        self._last_completed = None  # last stage that finished cleanly

    # ------------------------------------------------------------ helpers --
    def _cancelled(self):
        """v0.7.8.1 interrupt: True once the caller's cancel callback
        fires (the UI worker marks its worker cancelled on Stop/Esc)."""
        try:
            return bool(self.should_cancel and self.should_cancel())
        except Exception:
            return False

    def _restore_checkpoint(self):
        """Load the saved checkpoint for THIS user_text and fast-forward
        the run state to just after the last completed stage. Returns
        True when a usable checkpoint was found."""
        cp = load_checkpoint()
        if not cp or cp.get("user_text") != self.user_text:
            return False
        self.plan = cp.get("plan") or []
        self.todos = cp.get("todos") or []
        self.steps = cp.get("steps") or []
        self.final_text = cp.get("final_text") or ""
        self.research_brief = cp.get("research_brief", "")
        self.started = cp.get("started") or time.time()
        self._last_completed = cp.get("last_completed") or None
        self._todo_seq = max((t.get("id", 0) for t in self.todos), default=0)
        for t in self.todos:
            self.on_todo(t)  # re-sync live todo UIs to restored statuses
        return True
    def _emit(self, kind, message, **extra):
        ev = {"kind": kind, "stage": self.stage, "message": message}
        ev.update(extra)
        self.on_event(ev)
        if kind in ("note", "stage", "error", "done"):
            self.on_note(message)
        elif kind in ("report", "summary", "graph"):
            self.on_message(message)

    def _enter(self, stage):
        self.stage = stage
        self.on_stage(stage)
        eventbus.bus.publish(eventbus.PIPELINE_STAGE, stage=stage,
                             detail=STAGE_LABELS.get(stage, stage))
        if stage == "testing":
            for t in self.todos:
                if t["status"] not in (TODO_COMPLETED, TODO_SKIPPED, TODO_FAILED):
                    t["status"] = TODO_TESTING
                    self.on_todo(t)
        elif stage == "research":
            for t in self.todos:
                if t["status"] not in (TODO_COMPLETED, TODO_SKIPPED, TODO_FAILED):
                    t["status"] = TODO_RESEARCHING
                    self.on_todo(t)
        elif stage == "implementation":
            for t in self.todos:
                if t["status"] not in (TODO_COMPLETED, TODO_SKIPPED, TODO_FAILED):
                    t["status"] = TODO_RUNNING
                    self.on_todo(t)

    def _add_todo(self, text):
        self._todo_seq += 1
        todo = {"id": self._todo_seq, "text": text, "status": TODO_PENDING}
        self.todos.append(todo)
        self.on_todo(todo)
        return todo

    def _advance_todos(self, step_text):
        """Best-effort mapping of executed tool steps onto the plan's
        todos during Implementation: each tool step completes the first
        not-yet-done todo. Documented as an approximation, not a
        semantic match."""
        if not self.todos:
            return
        for t in self.todos:
            if t["status"] not in (TODO_COMPLETED, TODO_SKIPPED, TODO_FAILED):
                t["status"] = TODO_COMPLETED
                self.on_todo(t)
                return

    # ------------------------------------------------------------ stages --
    def _stage_planner(self):
        """Step 1 â€” Planner Mode: analyze, break into milestones,
        roadmap, todos, complexity estimate."""
        self._emit("note", "Step 1/6 \u2014 Planner: analyzing the request and breaking it into milestones...")
        system_prompt = agent.AGENT_SYSTEM_PROMPT if self.mode == "agent" else agent.AI_SYSTEM_PROMPT
        plan = agent._plan_steps(self.user_text, system_prompt)
        self.plan = plan
        for step in plan:
            self._add_todo(step)
        if not self.plan:
            self._add_todo("Work out and answer the request directly.")
        complexity = _classify_intent(self.user_text)
        self._emit("note",
                   f"Planner produced {len(self.plan)} milestone(s) \u00b7 "
                   f"complexity estimate: {complexity} (heuristic)")

    def _stage_research(self):
        """Step 2 â€” Research Mode: web brief when the request has a
        recency/lookup flavor, folded into the Implementation context."""
        self._emit("note", "Step 2/6 \u2014 Research: searching documentation and comparing approaches...")
        brief = agent._research_pass(self.user_text, agent.AGENT_SYSTEM_PROMPT)
        self.research_brief = brief
        if brief:
            self._emit("note", "Research brief gathered (live web search) \u2014 folding into the build.")
        else:
            self._emit("note", "No live research needed for this request (or search unreachable).")

    def _stage_implementation(self):
        """Step 3 â€” Build Mode: real tool execution (files, installs,
        plots) via agent.run_agent."""
        self._emit("note", "Step 3/6 \u2014 Implementation: creating files, installing packages, generating code...")
        plan_note = ("\n\nPIPELINE PLAN (follow it step by step, completing each "
                     "milestone in order):\n" +
                     "\n".join(f"{i+1}. {p}" for i, p in enumerate(self.plan)))
        if getattr(self, "research_brief", ""):
            plan_note += "\n\n" + self.research_brief

        def _on_step(name, args):
            args = args or {}
            target = (args.get("path") or args.get("command") or "").strip()
            label = f"{name}" + (f" {target}" if target else "")
            self._emit("note", f"\u2699 executing: {label}")
            self._advance_todos(label)

        final_text, steps, _meta = agent.run_agent(
            self.user_text + plan_note, max_steps=agent.MAX_STEPS,
            verbose=False, mode=self.mode,
            permission_callback=self.permission_callback,
            on_step=_on_step, should_cancel=self._cancelled)
        self.steps = steps
        self.final_text = final_text
        changes = agent.summarize_file_changes(steps)
        if changes:
            self._emit("report", changes)
        self._emit("note", f"Implementation finished \u2014 {len(steps)} tool step(s) run.")

    def _stage_testing(self):
        """Step 3b â€” Debugger/Tester pass: static scan + sandbox run of
        any code blocks the implementation produced."""
        self._emit("note", "Step 4/6 \u2014 Testing: statically scanning and sandbox-testing generated code...")
        final_text, note = agent._debug_pass(self.final_text)
        if note:
            risk = note.get("risk", "none")
            self._emit("note",
                       f"Debugger scan: {risk} risk "
                       + (f"\u2014 {note.get('sandbox_test', 'not sandboxed')}" if risk != "high" else
                          "\u2014 high-risk code not auto-executed"))
            if risk == "high":
                for t in self.todos:
                    if t["status"] == TODO_TESTING:
                        pass
            if note.get("findings"):
                details = "\n".join(f"  {f}" for f in note["findings"][:5])
                self._emit("report", "Debugger findings:\n" + details)
        self.final_text = final_text

    def _stage_verification(self):
        """Step 3c â€” Tester pass: spot-check the final answer."""
        self._emit("note", "Step 5/6 \u2014 Verification: checking the result against the request...")
        ok, note = agent._verify_answer(self.user_text, self.plan, self.final_text,
                                        agent.AGENT_SYSTEM_PROMPT)
        if not ok and note:
            self._emit("note", f"Tester flagged this for review: {note}")
            self.final_text = self.final_text + f"\n\n\u26a0 Tester flagged this for review: {note}"
        else:
            self._emit("note", "Verification passed \u2014 the result is internally consistent.")

    def _stage_documentation(self):
        """Step 4 â€” Notebook Mode: the final report card (stages,
        graph, todos, summary)."""
        self._emit("note", "Step 6/6 \u2014 Documentation: composing the final report...")
        self._emit("graph", "Pipeline task graph (current stage highlighted):")
        graph_lines = render_task_graph("completed")
        self._emit("report", "\n".join(graph_lines))
        done = sum(1 for t in self.todos if t["status"] == TODO_COMPLETED)
        skipped = sum(1 for t in self.todos if t["status"] == TODO_SKIPPED)
        failed = sum(1 for t in self.todos if t["status"] == TODO_FAILED)
        self.duration = round(time.time() - self.started, 1)
        card = [
            "\u2705 Pipeline complete",
            "",
            f"Milestones: {len(self.plan)} \u00b7 completed {done}"
            + (f" \u00b7 skipped {skipped}" if skipped else "")
            + (f" \u00b7 failed {failed}" if failed else ""),
            f"Tool steps executed: {len(self.steps)}",
            f"Duration: {self.duration}s",
            f"Complexity estimate: {_classify_intent(self.user_text)} (heuristic)",
        ]
        self._emit("summary", "\n".join(card))
        eventbus.bus.publish(eventbus.PIPELINE_COMPLETED, steps=len(self.steps),
                             milestones=len(self.plan))

    # --------------------------------------------------------------- run --
    def run(self, resume=False):
        """Execute the pipeline. Stages run in order; after each one
        completes the state is checkpointed (so a failed run can be
        resumed). With `resume=True`, a matching checkpoint is loaded
        and the completed stages are skipped — execution continues
        from the last-completed stage. The checkpoint is cleared when
        the run reaches 'completed'."""
        sound.play("notify")
        try:
            resumed = False
            if resume:
                resumed = self._restore_checkpoint()
                if resumed:
                    at = STAGE_LABELS.get(self._last_completed, self._last_completed or "start")
                    self._emit("note",
                               f"\u267b Resuming from checkpoint \u2014 "
                               f"skipping completed stages (up to '{at}').")
                else:
                    self._emit("note", "No matching checkpoint found \u2014 starting fresh.")
            else:
                clear_checkpoint()  # stale checkpoint from a previous crash
            skip_until = self._last_completed if resumed else None
            stages = [
                ("planner", self._stage_planner),
                ("research", self._stage_research),
                ("implementation", self._stage_implementation),
                ("testing", self._stage_testing),
                ("verification", self._stage_verification),
                ("documentation", self._stage_documentation),
            ]
            skipping = False
            for key, fn in stages:
                if skip_until and not skipping:
                    skipping = (key == skip_until)
                    continue  # completed in the previous run — skip it too
                if self._cancelled():
                    self._emit("note",
                               "\u23f9 Interrupted \u2014 completed work is preserved.")
                    return self.final_text
                self._enter(key)
                fn()
                self._last_completed = key
                save_checkpoint(self)
            self._enter("completed")
            sound.play("success")
            clear_checkpoint()
        except Exception as e:
            self.failed_stage = self.stage
            self._emit("error", f"Pipeline failed at {STAGE_LABELS.get(self.stage, self.stage)}: {e}")
            save_checkpoint(self)
            sound.play("error")
        return self.final_text


def run_pipeline(user_text, **callbacks):
    """Module-level convenience: builds a PipelineRun, runs it, returns
    it (callers read .final_text / .todos / .plan / .duration)."""
    run = PipelineRun(user_text, **callbacks)
    run.run()
    return run
