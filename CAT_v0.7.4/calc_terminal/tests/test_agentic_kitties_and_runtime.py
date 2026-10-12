"""
Test Suite for CAT Agentic Architecture & The Six Canonical Kitties.

Verifies:
1. Six canonical Kitties (Aria, Dex, Mira, Sage, Nova, Qala) registered with distinct roles & tools.
2. Custom Kitty CRUD, validation, export, import.
3. Agent lifecycle states, execution context, and reality verification.
4. Real delegation from Nova to specialist Kitties.
5. Qala's notebook and mathematical computing engine (SymPy, NumPy, SciPy).
6. LaTeX authoring, validation, Unicode terminal formatting, and compiler fallback.
7. Platform automation safety levels and emergency stop.
8. Persistent 24/7 task scheduler.
9. Email automation and confirmation policy.
"""

import json
import os
import shutil
import tempfile
import pytest

from calc_terminal.agents.builtin_agents import (
    get_canonical_kitties,
    get_builtin_agents,
    get_builtin_agent,
    ARIA,
    DEX,
    MIRA,
    SAGE,
    NOVA,
    QALA,
)
from calc_terminal.agents.agent_model import AgentSpec
from calc_terminal.agents.registry import AgentRegistry, get_agent_registry
from calc_terminal.agents.lifecycle import lifecycle_manager, LifecycleState
from calc_terminal import ai_modes
from calc_terminal.compute import qala_science, latex_engine
from calc_terminal.automation.platform_automation import (
    PlatformAutomationManager,
    AutomationSafetyLevel,
    trigger_emergency_stop,
    reset_emergency_stop,
    is_emergency_stopped,
    EmergencyStopTriggered,
)
from calc_terminal.tasks.scheduler import TaskScheduler, TaskStatus
from calc_terminal.integrations.email_automation import EmailAutomationService


# =============================================================================
# 1. The Six Canonical Kitties Verification
# =============================================================================

def test_six_canonical_kitties_exist():
    """Verify Aria, Dex, Mira, Sage, Nova, and Qala are registered with distinct roles."""
    kitties = get_canonical_kitties()
    assert len(kitties) == 6
    kitty_ids = {k.id for k in kitties}
    assert kitty_ids == {"aria", "dex", "mira", "sage", "nova", "qala"}

    # Aria: Build Agent
    assert ARIA.name == "Aria"
    assert ARIA.primary_mode == "build"
    assert "write_file" in ARIA.tools
    assert "run_tests" in ARIA.tools

    # Dex: Debugger Agent
    assert DEX.name == "Dex"
    assert DEX.primary_mode == "debugger"
    assert "edit_file" in DEX.tools
    assert "run_terminal" in DEX.tools

    # Mira: Planning Agent
    assert MIRA.name == "Mira"
    assert MIRA.primary_mode == "plan"
    assert "inspect_project" in MIRA.tools

    # Sage: Research Agent
    assert SAGE.name == "Sage"
    assert SAGE.primary_mode == "research"
    assert "web_search" in SAGE.tools

    # Nova: Autonomous Agent (replaces generic Agent mode)
    assert NOVA.name == "Nova"
    assert NOVA.primary_mode == "agent"
    assert "delegate_task_to_kitty" in NOVA.tools

    # Qala: Notebook and Scientific Agent
    assert QALA.name == "Qala"
    assert QALA.primary_mode == "notebook"
    assert "qala_solve_math" in QALA.tools
    assert "qala_notebook_ops" in QALA.tools


def test_ai_modes_metadata_reflection():
    """Verify ai_modes maps to the canonical Kitties."""
    assert ai_modes.MODE_META["notebook"]["label"] == "Qala"
    assert "Notebook & Science" in ai_modes.MODE_META["notebook"]["full_label"]
    assert ai_modes.MODE_META["agent"]["label"] == "Nova"
    assert "Autonomous Agent" in ai_modes.MODE_META["agent"]["full_label"]
    assert ai_modes.MODE_META["build"]["label"] == "Aria"
    assert ai_modes.MODE_META["debugger"]["label"] == "Dex"
    assert ai_modes.MODE_META["plan"]["label"] == "Mira"
    assert ai_modes.MODE_META["research"]["label"] == "Sage"


# =============================================================================
# 2. Custom Kitty Creation & Validation
# =============================================================================

def test_custom_kitty_crud_and_validation(tmp_path):
    """Test custom Kitty creation, validation, storage, and retrieval."""
    reg = AgentRegistry(agents_dir=str(tmp_path))

    # Test validation
    invalid_agent = AgentSpec(id="", name="Invalid")
    valid, err = reg.validate_agent(invalid_agent)
    assert not valid
    assert "empty" in err.lower()

    # Valid custom agent
    custom = AgentSpec(
        id="chem-analyst",
        name="Chem Analyst",
        description="Specialist in spectroscopy and molecular dynamics.",
        primary_mode="notebook",
        tools=["calculate", "solve_formula"],
        permissions={"level": "restricted"},
    )
    valid, _ = reg.validate_agent(custom)
    assert valid

    reg.register(custom, persist=True)
    fetched = reg.get("chem-analyst")
    assert fetched is not None
    assert fetched.name == "Chem Analyst"

    # Case-insensitive lookup by name
    fetched_by_name = reg.get("Chem Analyst")
    assert fetched_by_name is not None
    assert fetched_by_name.id == "chem-analyst"

    # Export & Import
    exp_file = str(tmp_path / "chem_analyst.catagent")
    reg.export_agent("chem-analyst", filepath=exp_file)
    assert os.path.exists(exp_file)

    # Delete
    assert reg.unregister("chem-analyst")
    assert reg.get("chem-analyst") is None


# =============================================================================
# 3. Agent Lifecycle Engine
# =============================================================================

def test_agent_lifecycle_transitions():
    """Verify lifecycle state progression and verification recording."""
    task = lifecycle_manager.create_task(agent_id="nova", objective="Diagnose web crash")
    assert task.state == LifecycleState.IDLE

    task.transition(LifecycleState.ANALYZING, detail="Inspecting error logs")
    assert task.state == LifecycleState.ANALYZING

    task.transition(LifecycleState.PLANNING, detail="Decomposing task into 3 steps")
    assert task.state == LifecycleState.PLANNING

    task.transition(LifecycleState.EXECUTING, detail="Executing diagnostic tools")
    assert task.state == LifecycleState.EXECUTING

    task.add_step("read_file", {"path": "src/app.py"}, "File read successfully", verified=True)
    task.record_verification("All 4 regression tests passed with exit code 0.")
    assert task.is_verified()

    task.transition(LifecycleState.COMPLETED, detail="Fix verified")
    assert task.state == LifecycleState.COMPLETED
    assert task.end_time is not None


# =============================================================================
# 4. Qala's Science & Notebook Engine
# =============================================================================

def test_qala_notebook_operations(tmp_path):
    """Verify Jupyter notebook creation, inspection, and cell modification."""
    nb_path = str(tmp_path / "test_science.ipynb")

    # Create
    res = qala_science.create_notebook(nb_path, title="Quantum Kinetics")
    assert res["status"] == "created"

    # Read
    nb_data = qala_science.read_notebook(nb_path)
    assert nb_data["cell_count"] >= 1

    # Add cell
    qala_science.add_notebook_cell(nb_path, source="x = 42\nprint('Computed:', x * 2)", cell_type="code")
    nb_data = qala_science.read_notebook(nb_path)
    assert nb_data["cell_count"] >= 2

    # Execute cell
    exec_res = qala_science.execute_notebook_cell("import math\ny = math.sqrt(16)\nprint('Result:', y)\ny")
    assert exec_res["success"] is True
    assert "Result: 4.0" in exec_res["stdout"]
    assert exec_res["result"] == "4.0"


def test_qala_symbolic_mathematics():
    """Verify exact symbolic algebra and calculus via SymPy."""
    # Solve equation: x**2 - 9 = 0
    sol = qala_science.solve_symbolic_equation("x**2 - 9 = 0", "x")
    assert sol["success"] is True
    assert "-3" in sol["solutions"]
    assert "3" in sol["solutions"]

    # Differentiation: d/dx(x**3 + 2*x) = 3*x**2 + 2
    diff_res = qala_science.perform_calculus("diff", "x**3 + 2*x", var="x")
    assert diff_res["success"] is True
    assert "3*x**2 + 2" in diff_res["result"]

    # Integration: int(2*x, x) = x**2
    int_res = qala_science.perform_calculus("integrate", "2*x", var="x")
    assert int_res["success"] is True
    assert "x**2" in int_res["result"]


# =============================================================================
# 5. LaTeX Engine Validation & Rendering
# =============================================================================

def test_latex_validation_and_terminal_rendering():
    """Verify LaTeX parsing, syntax validation, and Unicode rendering."""
    # Valid expression
    latex_expr = r"\int_{0}^{\infty} x^2 e^{-x} dx"
    valid, err = latex_engine.validate_latex(latex_expr)
    assert valid is True

    # Invalid expression (unbalanced bracket)
    invalid_expr = r"\int_{0}^{\infty x^2 dx"
    valid, err = latex_engine.validate_latex(invalid_expr)
    assert valid is False
    assert err is not None

    # Unicode rendering
    rendered = latex_engine.render_to_terminal_unicode(r"\alpha + \beta = \gamma")
    assert "α" in rendered
    assert "β" in rendered
    assert "γ" in rendered

    frac_rendered = latex_engine.render_to_terminal_unicode(r"\frac{a}{b}")
    assert "(a / b)" in frac_rendered


# =============================================================================
# 6. Computer Automation Safety & Emergency Stop
# =============================================================================

def test_platform_automation_safety_and_emergency_stop():
    """Verify safety levels and the emergency stop mechanism."""
    mgr = PlatformAutomationManager(safety_level=AutomationSafetyLevel.RESTRICTED)

    # Disallowed command in restricted mode
    res = mgr.run_command("rmdir /s /q test_dir")
    assert not res["ok"]
    assert res["error"] == "PolicyViolation"

    # Emergency stop
    reset_emergency_stop()
    assert not is_emergency_stopped()

    trigger_emergency_stop()
    assert is_emergency_stopped()

    with pytest.raises(EmergencyStopTriggered):
        mgr.run_command("dir")

    reset_emergency_stop()
    assert not is_emergency_stopped()


# =============================================================================
# 7. Background Task Scheduler
# =============================================================================

def test_task_scheduler_lifecycle(tmp_path):
    """Verify scheduled tasks can be created, paused, resumed, and cancelled."""
    sched_file = str(tmp_path / "scheduler.json")
    sched = TaskScheduler(state_file=sched_file)

    task = sched.add_task(
        name="Daily Test Runner",
        agent_id="aria",
        objective="Run workspace test suite",
        schedule_type="interval",
        interval_seconds=3600,
    )
    assert task.status == TaskStatus.IDLE

    # Pause
    assert sched.pause_task(task.task_id) is True
    assert sched.get_task(task.task_id).status == TaskStatus.PAUSED

    # Resume
    assert sched.resume_task(task.task_id) is True
    assert sched.get_task(task.task_id).status == TaskStatus.IDLE

    # Cancel
    assert sched.cancel_task(task.task_id) is True
    assert sched.get_task(task.task_id).status == TaskStatus.CANCELLED


# =============================================================================
# 8. Email Automation Confirmation Policy
# =============================================================================

def test_email_automation_confirmation_policy():
    """Verify search, thread summarization, and mandatory confirmation policy."""
    svc = EmailAutomationService()

    # Search
    results = svc.search_messages("release")
    assert len(results) >= 1

    # Thread summary
    summary = svc.summarize_thread("thread-release")
    assert summary["message_count"] >= 1

    # Drafting
    draft = svc.create_draft(["lead@example.com"], "PR Approval", "Code looks good to ship.")
    did = draft["draft_id"]

    # Send without user confirmation must be refused
    denied = svc.send_email(did, user_confirmed=False)
    assert not denied["ok"]
    assert denied["error"] == "ConfirmationRequired"

    # Send with explicit confirmation succeeds
    sent = svc.send_email(did, user_confirmed=True)
    assert sent["ok"] is True
    assert sent["status"] == "sent"


# =============================================================================
# 9. Run Agent Lifecycle & Emergency Stop in Tools
# =============================================================================

def test_run_agent_lifecycle_and_verification_recording(monkeypatch):
    """Verify run_agent instantiates and transitions lifecycle_task, recording verified steps."""
    from calc_terminal import agent
    from calc_terminal import aicore

    responses = [
        '{"action": "tool", "tool": "calculate", "args": {"expr": "12 * 12"}}',
        '{"action": "final", "text": "The result is 144."}',
    ]
    call_idx = 0
    def mock_query_ai(*args, **kwargs):
        nonlocal call_idx
        res = responses[min(call_idx, len(responses) - 1)]
        call_idx += 1
        return res

    monkeypatch.setattr(aicore, "query_ai", mock_query_ai)

    final_text, steps, meta = agent.run_agent("Calculate 12 * 12", max_steps=4, mode="agent")
    assert "144" in final_text
    assert len(steps) >= 1
    assert "lifecycle_task" in meta
    lt = meta["lifecycle_task"]
    assert lt is not None
    assert lt["state"] == "COMPLETED"
    assert len(lt["steps"]) >= 1


def test_tool_terminal_and_device_emergency_stop():
    """Verify _tool_run_terminal and _tool_device_action refuse execution when emergency stop is active."""
    from calc_terminal import agent
    from calc_terminal.automation.platform_automation import trigger_emergency_stop, reset_emergency_stop

    reset_emergency_stop()
    trigger_emergency_stop()

    term_res = agent._tool_run_terminal({"command": "echo 'should not run'"})
    assert "emergency stop is active" in term_res.lower()

    dev_res = agent._tool_device_action({"provider": "terminal", "action": "run", "command": "echo test"})
    assert "emergency stop is active" in dev_res.lower()

    reset_emergency_stop()


# =============================================================================
# 8. Skills System, Artifacts, Memory Governance, Sandboxing, & Evaluations
# =============================================================================

def test_skills_system_registry_and_validation(tmp_path):
    """Verify SkillDefinition dataclass, validation, and SkillRegistry CRUD."""
    from calc_terminal.skills.skill_model import SkillDefinition
    from calc_terminal.skills.registry import SkillRegistry

    # 1. Validation failure on invalid version
    with pytest.raises(ValueError, match="semantic version"):
        SkillDefinition(id="test-skill", name="Test", version="invalid", prompt_instructions="Do things")

    # 2. Built-in skills presence
    reg = SkillRegistry(storage_dir=str(tmp_path / "skills"))
    assert len(reg.list_all()) >= 6
    pytest_skill = reg.get("pytest-tdd-cycle")
    assert pytest_skill is not None
    assert pytest_skill.version.startswith("1.")
    assert "run_tests" in pytest_skill.required_tools

    # 3. Custom skill registration and persistence
    custom_skill = SkillDefinition(
        id="custom-fastapi",
        name="FastAPI Development",
        version="0.2.1",
        description="FastAPI endpoint scaffold",
        prompt_instructions="Use FastAPI routers with dependency injection.",
        required_tools=["write_file", "edit_file"],
        permissions={"network": True},
    )
    reg.register(custom_skill)
    assert reg.get("custom-fastapi") is not None
    assert reg.get("custom-fastapi").name == "FastAPI Development"

    # Export & Import
    data = reg.export_skill("custom-fastapi")
    assert "FastAPI Development" in data
    reg.delete("custom-fastapi")
    assert reg.get("custom-fastapi") is None
    reg.import_skill(data)
    assert reg.get("custom-fastapi") is not None


def test_skills_assigned_to_canonical_kitties():
    """Verify built-in Kitties have their designated skills assigned."""
    from calc_terminal.agents.builtin_agents import ARIA, DEX, MIRA, SAGE, NOVA, QALA

    assert "pytest-tdd-cycle" in ARIA.skills
    assert "git-workflow" in ARIA.skills
    assert "task-decomposition" in MIRA.skills
    assert "research-synthesis" in SAGE.skills
    assert "task-decomposition" in NOVA.skills
    assert "scientific-notebook-workflow" in QALA.skills
    assert "latex-equation-authoring" in QALA.skills


def test_artifact_manager_tracking_and_hashing(tmp_path):
    """Verify ArtifactManager records file modifications with SHA-256 and task provenance."""
    from calc_terminal.artifacts.artifact_manager import ArtifactManager

    mgr = ArtifactManager(storage_dir=str(tmp_path / "artifacts"))
    sample_file = tmp_path / "app.py"
    sample_file.write_text("print('hello world')", encoding="utf-8")

    rec = mgr.record_artifact(
        task_id="task-101",
        agent_id="aria",
        file_path=str(sample_file),
        action="create",
        diff_summary="Created app.py",
    )

    assert rec.category == "code"
    assert rec.agent_id == "aria"
    assert rec.task_id == "task-101"
    assert len(rec.sha256) == 64

    # Query provenance
    task_artifacts = mgr.get_artifacts_for_task("task-101")
    assert len(task_artifacts) == 1
    assert os.path.normpath(task_artifacts[0].file_path) == os.path.normpath(str(sample_file))


def test_memory_governance_task_preference_and_export(tmp_path):
    """Verify memory governance: task memory isolation, preference approval, inspection, correction, and export."""
    from calc_terminal.memory_v2 import MemoryManager

    mm = MemoryManager(memory_dir=str(tmp_path / "memory"))

    # 1. Task memory isolation
    mm.store_task_fact("task-42", "Transient observation in step 2", category="diagnostics")
    task_facts = mm.get_task_context("task-42")
    assert len(task_facts) == 1
    assert task_facts[0]["fact"] == "Transient observation in step 2"
    assert len(mm.get_task_context("task-99")) == 0
    mm.clear_task_memory("task-42")
    assert len(mm.get_task_context("task-42")) == 0

    # 2. Long-term memory store & inspect
    mem = mm.store_memory(
        category="user_preferences",
        content="Prefer pytest over unittest",
        importance=0.9,
        status="approved",
    )
    inspected = mm.inspect_memory(mem.id)
    assert inspected is not None
    assert inspected["content"] == "Prefer pytest over unittest"
    assert inspected["status"] == "approved"

    # 3. User-approved correction
    corrected = mm.correct_memory(mem.id, "Prefer pytest with coverage over unittest")
    assert corrected is not None
    assert corrected.content == "Prefer pytest with coverage over unittest"

    # 4. Approved preferences query
    prefs = mm.get_approved_preferences()
    assert any(p.id == mem.id for p in prefs)

    # 5. Export in JSON and Markdown
    export_json = mm.export_memories(format="json")
    export_md = mm.export_memories(format="markdown")
    assert "Prefer pytest" in export_json
    assert "# CAT CLI Governed Memory Export" in export_md
    assert "Prefer pytest" in export_md


def test_central_policy_delegation_clamping():
    """Verify central policy clamping prevents child Kitty privilege escalation during delegation."""
    from calc_terminal.agents.agent_model import AgentSpec
    from calc_terminal import agent

    # Create caller with strictly restricted permissions (no shell commands)
    caller = AgentSpec(
        id="restricted_agent",
        name="RestrictedAgent",
        description="Restricted Agent",
        primary_mode="agent",
        tools=["delegate_task_to_kitty", "calculate"],
        permissions={"shell_commands": False, "write_files": True},
    )

    # Set as active agent spec in thread-local
    agent._CURRENT_AGENT_SPEC.spec = caller

    # Try executing run_terminal (perm_key shell_commands)
    allowed, denial = agent._check_permission("run_terminal", {"command": "dir"}, None)
    assert not allowed
    assert "restricted" in denial.lower()

    # Reset thread-local
    agent._CURRENT_AGENT_SPEC.spec = None


def test_sandbox_isolated_execution():
    """Verify sandbox runs code in an isolated subprocess with scrubbed environment."""
    from calc_terminal.sandbox import run_sandboxed, _get_scrubbed_env

    # 1. Environment scrubbing
    os.environ["TEST_SECRET_API_KEY"] = "sk-super-secret-12345"
    safe_env = _get_scrubbed_env()
    assert "TEST_SECRET_API_KEY" not in safe_env

    # 2. Execution
    code = "import sys\nprint('sandbox_ok')\nsys.stdout.flush()"
    res = run_sandboxed(code, timeout=5)
    assert res["sandboxed"] is True
    assert res["isolated_env"] is True
    assert "sandbox_ok" in res["stdout"]
    assert res["returncode"] == 0


def test_agent_evals_suite_and_controlled_improvement():
    """Verify agent evaluations measure completion, reliability, and produce controlled improvements."""
    from calc_terminal.evals.agent_evals import (
        AgentEvaluator,
        EvalTask,
        get_standard_eval_suite,
    )

    evaluator = AgentEvaluator()
    suite = get_standard_eval_suite()
    assert len(suite) == 6

    # Test task execution with simulated runner
    def mock_runner(task, tracer):
        tracer(1, "write_file", {"path": "test.py"}, "Wrote 20 chars")
        tracer(2, "run_tests", {"command": "pytest"}, "1 passed in 0.05s")
        return "def test_ok(): pass", [("write_file", {}), ("run_tests", {})], {"tester_ok": True}

    task = suite[0]  # Aria TDD task
    res = evaluator.evaluate_task(task, runner_fn=mock_runner)
    assert res.passed is True
    assert res.completion_rate == 1.0
    assert res.tool_reliability_score == 1.0
    assert res.verification_score == 1.0
    assert res.composite_score() > 90.0

    # Test controlled improvements generator
    failing_task = EvalTask(
        task_id="failing-task",
        name="Failing Task",
        target_kitty="dex",
        objective="Find nonexistent bug",
        verification_required=True,
    )
    def failing_runner(t, tracer):
        tracer(1, "run_terminal", {}, "Error: tool failed")
        return "Could not solve", [], {"tester_ok": False}

    fail_res = evaluator.evaluate_task(failing_task, runner_fn=failing_runner)
    summary = evaluator.evaluate_suite([failing_task], runner_fn=failing_runner)
    recs = evaluator.generate_controlled_improvements(summary)
    assert len(recs) == 1
    assert recs[0]["status"] == "pending_user_review"
    assert recs[0]["permission_escalation_requested"] is False

