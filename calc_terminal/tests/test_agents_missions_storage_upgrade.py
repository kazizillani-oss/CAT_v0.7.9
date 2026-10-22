"""
Comprehensive Test Suite for CAT CLI Multi-Agent, Mission System, Storage, and Integrations Upgrade.
"""

import copy
import json
import os
import shutil
import tempfile
import time
import pytest

from calc_terminal.agents.agent_model import AgentSpec, AgentResult
from calc_terminal.agents.builtin_agents import BUILTIN_AGENTS, get_builtin_agents
from calc_terminal.agents.registry import AgentRegistry, get_agent_registry
from calc_terminal.agents.handoff import AgentHandoffPipeline
from calc_terminal.agents.orchestration import AgentOrchestrationEngine
from calc_terminal.missions.models import Mission, Task, Checkpoint
from calc_terminal.missions.manager import MissionManager, get_mission_manager
from calc_terminal.integrations.models import IntegrationSpec, STATE_CONNECTED, STATE_DISCONNECTED
from calc_terminal.integrations.registry import IntegrationRegistry, get_integration_registry
from calc_terminal.tools_registry import ToolSpec, ToolRegistry, get_tool_registry
from calc_terminal import storage
from calc_terminal import ai_modes
from calc_terminal import model_router
from calc_terminal.cli_commands import (
    agents_cli,
    missions_cli,
    storage_cli,
    backup_cli,
    integrations_cli,
    cat_file_cli,
)


@pytest.fixture
def temp_storage(monkeypatch):
    """Provides an isolated temporary CAT storage directory for testing."""
    tmp_dir = tempfile.mkdtemp(prefix="cat_test_storage_")
    monkeypatch.setenv("CAT_STORAGE_DIR", tmp_dir)
    storage._ensure_subdirs(tmp_dir)
    yield tmp_dir
    shutil.rmtree(tmp_dir, ignore_errors=True)


# =============================================================================
# 1. AgentRegistry & Core Lifecycle Tests
# =============================================================================

def test_builtin_agents_registered():
    """Verify all built-in and assistant-inspired agents exist with valid metadata."""
    reg = AgentRegistry()
    agents = reg.list(include_disabled=True)
    agent_ids = {a.id for a in agents}

    expected_builtins = [
        "cat-coder", "cat-debugger", "cat-researcher", "cat-planner",
        "cat-reviewer", "cat-architect", "cat-tester", "cat-docs",
        "cat-git", "cat-terminal", "grok-agent", "openai-agent", "browser-agent"
    ]
    for bid in expected_builtins:
        assert bid in agent_ids, f"Expected built-in agent '{bid}' not found"
        spec = reg.get(bid)
        assert spec is not None
        assert spec.name
        assert spec.primary_mode
        assert spec.builtin is True


def test_agent_registration_and_persistence(temp_storage):
    """Tests creating, registering, updating, and saving a custom agent."""
    agents_dir = os.path.join(temp_storage, "agents")
    reg = AgentRegistry(agents_dir=agents_dir)

    custom = AgentSpec(
        id="quantum-researcher",
        name="Quantum Researcher",
        description="Researches quantum algorithms and superconducting circuits.",
        primary_mode="research",
        provider="gemini",
        model="gemini-2.0-flash",
        system_instructions="Explain quantum computing with first-principles clarity.",
        tools=["web_search", "deep_research", "read_file"],
        permissions={"level": "restricted", "read_files": True, "write_files": False},
        tags=["quantum", "physics", "research"],
    )

    reg.register(custom, persist=True)

    # Verify memory retrieval
    fetched = reg.get("quantum-researcher")
    assert fetched is not None
    assert fetched.name == "Quantum Researcher"
    assert fetched.provider == "gemini"
    assert fetched.model == "gemini-2.0-flash"

    # Verify filesystem persistence (.cat file)
    cat_file = os.path.join(agents_dir, "quantum-researcher.cat")
    assert os.path.isfile(cat_file)

    # Reload fresh registry from the directory
    fresh_reg = AgentRegistry(agents_dir=agents_dir)
    fresh_agent = fresh_reg.get("quantum-researcher")
    assert fresh_agent is not None
    assert fresh_agent.name == "Quantum Researcher"
    assert "web_search" in fresh_agent.tools


def test_agent_search(temp_storage):
    """Tests searching agents across names, descriptions, tags, and tools."""
    agents_dir = os.path.join(temp_storage, "agents")
    reg = AgentRegistry(agents_dir=agents_dir)

    # Built-in search
    debug_matches = reg.search(query="debugger")
    assert any(a.id == "cat-debugger" for a in debug_matches)

    # Mode filter
    research_agents = reg.search(mode="research")
    assert all(a.primary_mode == "research" or "research" in a.allowed_modes for a in research_agents)

    # Tag filter
    git_agents = reg.search(tags=["git"])
    assert any(a.id == "cat-git" for a in git_agents)


def test_agent_enable_disable_duplicate(temp_storage):
    """Tests enabling/disabling agents and duplicating agents."""
    agents_dir = os.path.join(temp_storage, "agents")
    reg = AgentRegistry(agents_dir=agents_dir)

    # Disable built-in
    assert reg.disable("cat-coder") is True
    assert reg.get("cat-coder").enabled is False
    enabled_only = reg.list(include_disabled=False)
    assert not any(a.id == "cat-coder" for a in enabled_only)

    # Re-enable
    assert reg.enable("cat-coder") is True
    assert reg.get("cat-coder").enabled is True

    # Duplicate
    dup = reg.duplicate("cat-coder", "cat-coder-v2", "CAT Coder v2")
    assert dup.id == "cat-coder-v2"
    assert dup.name == "CAT Coder v2"
    assert dup.builtin is False
    assert reg.get("cat-coder-v2") is not None


def test_100_plus_agents_performance(temp_storage):
    """Stress test: verify CAT easily supports 100+ registered agents with instant search."""
    agents_dir = os.path.join(temp_storage, "agents")
    reg = AgentRegistry(agents_dir=agents_dir)

    t0 = time.perf_counter()
    for i in range(120):
        spec = AgentSpec(
            id=f"agent-stress-{i:03d}",
            name=f"Stress Agent {i}",
            description=f"Specialist agent number {i} for high-scale pipeline execution.",
            primary_mode="build" if i % 2 == 0 else "research",
            tags=[f"tag-{i % 5}", "stress-test"],
            tools=["read_file", "search_workspace"] if i % 3 == 0 else ["web_search"],
        )
        reg.register(spec, persist=False)  # in-memory fast register
    duration = time.perf_counter() - t0
    assert duration < 1.0, f"Registration of 120 agents took {duration:.2f}s (must be < 1s)"

    assert len(reg.list()) >= 130  # built-ins + 120 stress agents

    # Benchmark search across 130+ agents
    t_search = time.perf_counter()
    matches = reg.search(query="agent-stress-042")
    search_duration = time.perf_counter() - t_search
    assert len(matches) == 1
    assert matches[0].id == "agent-stress-042"
    assert search_duration < 0.05, f"Search took {search_duration:.4f}s"


# =============================================================================
# 2. Native `.cat` Format & Storage Tests
# =============================================================================

def test_cat_envelope_validation():
    """Verify validation of native .cat schema and security warnings."""
    valid_data = {
        "id": "test-agent",
        "name": "Test Agent",
        "tools": ["run_terminal", "write_file"],
        "permissions": {"level": "full"},
    }
    env = storage.create_cat_envelope("agent", "test-agent", valid_data)
    valid, err, warnings = storage.validate_cat_envelope(env)
    assert valid is True
    assert err == ""
    assert any("Terminal / code execution" in w for w in warnings)
    assert any("Mutating filesystem" in w for w in warnings)

    # Test invalid format
    invalid_env = {"format": "unknown", "version": 1}
    valid, err, _ = storage.validate_cat_envelope(invalid_env)
    assert valid is False
    assert "Missing or invalid format" in err


def test_cat_secret_sanitization():
    """Ensure API keys and sensitive tokens are redacted during storage and export."""
    sensitive_dict = {
        "name": "Secret Agent",
        "api_key": "sk-1234567890abcdef1234567890abcdef",
        "nested": {
            "token": "ghp_1234567890abcdef1234567890abcdef12",
            "instruction": "Use key xai-9876543210fedcba9876543210 for requests",
        }
    }
    sanitized = storage.sanitize_secrets(sensitive_dict)
    assert sanitized["api_key"] == storage.REDACTED_SECRET
    assert sanitized["nested"]["token"] == storage.REDACTED_SECRET
    assert storage.REDACTED_SECRET in sanitized["nested"]["instruction"]
    assert "sk-" not in json.dumps(sanitized)


def test_cat_export_and_import(temp_storage):
    """Test exporting and importing portable .cat files."""
    agents_dir = os.path.join(temp_storage, "agents")
    reg = AgentRegistry(agents_dir=agents_dir)

    agent = AgentSpec(
        id="portable-bot",
        name="Portable Bot",
        description="A portable exported agent",
        primary_mode="notebook",
        tools=["web_search"],
    )
    reg.register(agent, persist=True)

    export_path = os.path.join(temp_storage, "portable-bot.catagent")
    exported_p = reg.export_agent("portable-bot", export_path)
    assert os.path.isfile(exported_p)

    # Read and inspect
    valid, envelope, err, warnings = storage.read_cat_file(exported_p)
    assert valid is True
    assert envelope["type"] == "agent"
    assert envelope["data"]["name"] == "Portable Bot"

    # Import with new ID
    imported_agent = reg.import_agent(exported_p, force=False)
    assert imported_agent.id == "portable-bot-copy"


def test_cat_migration(temp_storage):
    """Test migrating legacy or older .cat format files."""
    legacy_file = os.path.join(temp_storage, "legacy_agent.cat")
    legacy_content = {
        "name": "Old Agent",
        "primary_mode": "build",
        "system_instructions": "Old prompt",
    }
    with open(legacy_file, "w", encoding="utf-8") as f:
        json.dump(legacy_content, f)

    ok, msg = storage.migrate_cat_file(legacy_file)
    assert ok is True

    valid, env, _, _ = storage.read_cat_file(legacy_file)
    assert valid is True
    assert env["format"] == "cat"
    assert env["version"] == storage.CAT_FORMAT_VERSION
    assert env["type"] == "agent"


def test_storage_metrics_and_backup(temp_storage):
    """Test user storage metrics, backup archiving, and restoration."""
    st = storage.get_storage_status()
    assert "base_path" in st
    assert "breakdown" in st
    assert "agents" in st["breakdown"]
    assert "missions" in st["breakdown"]

    # Create backup
    backup_file = os.path.join(temp_storage, "test_backup.zip")
    archive = storage.create_backup(backup_file)
    assert os.path.isfile(archive)

    # Test restoration
    restore_dir = tempfile.mkdtemp(prefix="cat_test_restore_")
    try:
        ok, msg = storage.restore_backup(archive)
        assert ok is True
    finally:
        shutil.rmtree(restore_dir, ignore_errors=True)


# =============================================================================
# 3. Mission & Task System Tests
# =============================================================================

def test_mission_lifecycle(temp_storage):
    """Tests mission creation, checkpoints, pause, resume, and completion."""
    missions_dir = os.path.join(temp_storage, "missions")
    mm = MissionManager(missions_dir=missions_dir)

    plan_steps = [
        "Inspect project architecture",
        "Implement core REST API",
        "Author pytest test suite",
        "Verify 100% test pass",
    ]

    mission = mm.create(
        title="Build REST API",
        objective="Implement and verify a complete FastAPI service.",
        agents=["cat-planner", "cat-coder", "cat-tester"],
        plan=plan_steps,
    )

    assert mission.id.startswith("mission-")
    assert mission.status == "pending"
    assert len(mission.tasks) == 4
    assert len(mission.checkpoints) >= 1  # initial checkpoint

    # Pause mission
    assert mm.pause(mission.id) is True
    assert mm.get(mission.id).status == "paused"
    assert len(mm.get(mission.id).checkpoints) == 2

    # Resume mission
    assert mm.resume(mission.id) is True
    assert mm.get(mission.id).status == "running"
    assert len(mm.get(mission.id).checkpoints) == 3

    # Add custom checkpoint
    cp = mm.add_checkpoint(mission.id, "API Endpoints Verified", snapshot={"endpoints": ["/users", "/items"]})
    assert cp is not None
    assert cp.name == "API Endpoints Verified"

    # Complete mission
    assert mm.complete(mission.id, final_result="All 45 tests passed. REST API operational.") is True
    completed_m = mm.get(mission.id)
    assert completed_m.status == "completed"
    assert "operational" in completed_m.final_result


def test_mission_export_and_import(temp_storage):
    """Tests exporting and importing persistent missions."""
    missions_dir = os.path.join(temp_storage, "missions")
    mm = MissionManager(missions_dir=missions_dir)

    m = mm.create(title="Export Test Mission", objective="Testing export functionality.")
    export_path = os.path.join(temp_storage, "mission_exported.cat")
    exported_p = mm.export_mission(m.id, export_path)
    assert os.path.isfile(exported_p)

    imported_m = mm.import_mission(exported_p, force=False)
    assert imported_m is not None
    assert "Export Test Mission" in imported_m.title


# =============================================================================
# 4. Standardized Tool Registry & Agent Permissions
# =============================================================================

def test_tool_registry():
    """Verify ToolRegistry discovers built-in tools and filters by agent permissions."""
    treg = ToolRegistry()
    tools = treg.list()
    tool_names = {t.name for t in tools}

    assert "read_file" in tool_names
    assert "write_file" in tool_names
    assert "run_terminal" in tool_names
    assert "web_search" in tool_names

    # Test agent tool gating
    agent_read_only = AgentSpec(
        id="read-only-bot",
        name="Read Only",
        tools=["read_file", "search_workspace"],
        permissions={"level": "restricted", "read_files": True, "write_files": False, "shell_commands": False},
    )
    allowed = treg.get_tools_for_agent(agent_read_only)
    assert "read_file" in allowed
    assert "write_file" not in allowed
    assert "run_terminal" not in allowed


# =============================================================================
# 5. Integration Center & Probers
# =============================================================================

def test_integration_registry():
    """Verify built-in integrations and non-crashing realistic probers."""
    ireg = IntegrationRegistry()
    integrations = ireg.list()
    ids = {i.id for i in integrations}

    assert "openai" in ids
    assert "gemini" in ids
    assert "xai" in ids
    assert "ollama" in ids
    assert "github" in ids
    assert "mcp" in ids

    # Refresh statuses should complete without error
    statuses = ireg.refresh_statuses()
    assert isinstance(statuses, dict)
    assert "openai" in statuses
    assert "github" in statuses


# =============================================================================
# 6. Inter-Agent Handoff & Router Integration
# =============================================================================

def test_agent_handoff_pipeline():
    """Verify structured AgentResult passing through the handoff pipeline."""
    pipeline = AgentHandoffPipeline(mission_id="test-handoff-101")

    # Step 1: Planner creates plan
    r1 = AgentResult(
        agent_id="cat-planner",
        status="success",
        summary="Created implementation plan with 3 modules.",
        artifacts={"plan": ["auth.py", "api.py", "db.py"]},
    )
    pipeline.submit_result(r1)

    # Step 2: Coder modifies files
    r2 = AgentResult(
        agent_id="cat-coder",
        status="success",
        summary="Implemented auth and db modules.",
        files_changed=["auth.py", "db.py"],
    )
    pipeline.submit_result(r2)

    # Generate handoff prompt for Tester
    prompt = pipeline.format_handoff_prompt("cat-tester", "Run test suite on modified code.")
    assert "cat-planner" in prompt
    assert "auth.py" in prompt
    assert "db.py" in prompt


def test_ai_modes_active_agent_integration():
    """Verify setting active agent updates primary mode and injects instructions."""
    ag = ai_modes.set_active_agent("cat-debugger")
    assert ag is not None
    assert ag.id == "cat-debugger"
    assert ai_modes.active_agent_id() == "cat-debugger"
    assert ai_modes.current_mode() == "debugger"

    prompt = ai_modes.system_prompt_for("debugger")
    assert "CAT Agent: CAT Debugger" in prompt

    # Reset
    ai_modes.set_active_agent(None)
    assert ai_modes.active_agent_id() is None


def test_intelligence_router():
    """Verify router task classification and team delegation."""
    r_debug = model_router.route_task_to_agent_and_mission("We are getting a KeyError in line 42 traceback crash")
    assert r_debug["primary_agent"] == "cat-debugger"

    r_plan = model_router.route_task_to_agent_and_mission("Design architecture roadmap for our new microservice")
    assert r_plan["primary_agent"] == "cat-planner"

    r_complex = model_router.route_task_to_agent_and_mission(
        "Build a full end-to-end user authentication microservice with JWT tokens, "
        "PostgreSQL database migration, automated pytest test suite, and Docker container setup."
    )
    assert r_complex["is_complex"] is True
    assert len(r_complex["suggested_team"]) >= 3


# =============================================================================
# 7. CLI Commands Tests
# =============================================================================

def test_cli_agents_command(capsys):
    """Verify `cat agent list` and `cat agent search` execution."""
    rc = agents_cli(["agent", "list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "CAT AI AGENT REGISTRY" in out
    assert "CAT Coder" in out

    rc_search = agents_cli(["agent", "search", "debug"])
    assert rc_search == 0
    out_search = capsys.readouterr().out
    assert "CAT Debugger" in out_search


def test_cli_missions_command(capsys):
    """Verify `cat mission list` and `cat mission create` execution."""
    rc = missions_cli(["mission", "list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "CAT MISSION SYSTEM" in out

    rc_create = missions_cli(["mission", "create", "CLI Test Mission", "Testing CLI mission creation."])
    assert rc_create == 0
    out_create = capsys.readouterr().out
    assert "Created mission 'CLI Test Mission'" in out_create


def test_cli_storage_command(capsys):
    """Verify `cat storage status` and `cat storage path` execution."""
    rc = storage_cli(["storage", "status"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "CAT USER STORAGE REPORT" in out

    rc_path = storage_cli(["storage", "path"])
    assert rc_path == 0
    out_path = capsys.readouterr().out.strip()
    assert os.path.isdir(out_path)


def test_cli_integrations_command(capsys):
    """Verify `cat integrations` command output."""
    rc = integrations_cli(["integrations", "list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "CAT INTEGRATION CENTER" in out
    assert "OpenAI" in out
    assert "GitHub" in out
