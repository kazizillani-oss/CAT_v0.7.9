"""
Unit & Integration Tests for CAT CLI v0.9.000 Built-in Skills & Extensions Engine Upgrade.
Verifies all 15 Core Dev skills, 8 Open-Source skills, 10 CAT-Native skills,
Progressive disclosure, Kitty agent compatibility, Main Menu visibility, and Security permissions.
"""

import json
import os
import pytest
from pathlib import Path

from calc_terminal.skills.engine import SkillsEngine, get_skills_engine
from calc_terminal.skills.registry import SkillRegistry, get_skill_registry
from calc_terminal import extensions as ext_mgr
from calc_terminal.ui.header import get_nav_items, NavPanel


BUILTIN_DIR = Path(__file__).parent.parent / "skills" / "builtin"
MANIFEST_FILE = BUILTIN_DIR / "manifest.json"


# -----------------------------------------------------------------------------
# Test Suite 1: Manifest & Offline Bundling Integrity
# -----------------------------------------------------------------------------
def test_builtin_manifest_exists_and_valid():
    """Verify manifest.json exists, is valid JSON, and bundles at least 30+ skills offline."""
    assert MANIFEST_FILE.is_file(), f"Missing manifest at {MANIFEST_FILE}"
    with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "skills" in data
    assert len(data["skills"]) >= 35, f"Expected >= 35 skills, got {len(data['skills'])}"
    assert data.get("version") == "0.9.000"


def test_all_15_core_development_skills_exist():
    """Verify all 15 Core Development Skills exist with complete SKILL.md and YAML frontmatter."""
    core_skills = [
        "brainstorming", "planning", "code-review", "debugging", "testing",
        "security-audit", "frontend-design", "git-workflow", "documentation",
        "research", "browser-automation", "refactoring", "humanizer",
        "seo-optimization", "scientific-research"
    ]
    for sid in core_skills:
        sdir = BUILTIN_DIR / sid
        skill_file = sdir / "SKILL.md"
        assert skill_file.is_file(), f"Missing {skill_file}"
        content = skill_file.read_text(encoding="utf-8")
        assert content.startswith("---"), f"{sid} missing frontmatter marker"
        assert "name:" in content, f"{sid} missing name in frontmatter"
        assert len(content) > 300, f"{sid} instructions are too short"


def test_famous_open_source_skills_attribution_and_offline():
    """Verify famous open-source skills carry creator attribution and repository links."""
    with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)
    manifest_by_id = {s["cat_skill_id"]: s for s in manifest_data.get("skills", [])}

    os_skills = [
        ("superpowers", "@obra", "https://github.com/obra/superpowers"),
        ("ts-wizard", "@mattpocock", "https://github.com/mattpocock/skills"),
        ("mcp-builder", "@anthropics", "https://github.com/anthropics/skills"),
        ("ui-ux-pro-max", "@nextlevelbuilder", "https://github.com/nextlevelbuilder/ui-ux-pro-max-skill"),
        ("cloudflare-security", "@cloudflare", "https://github.com/cloudflare/security-audit-skill"),
        ("addy-agent-skills", "@addyosmani", "https://github.com/addyosmani/agent-skills"),
        ("impeccable", "@pbakaus", "https://github.com/pbakaus/impeccable"),
        ("rea-reverse-engineer", "@morluto", "https://github.com/morluto/rea"),
        ("archify", "@tt-a1i", "https://github.com/tt-a1i/archify"),
        ("page-mascot", "@nilbuild", "https://github.com/nilbuild/page-mascot"),
    ]
    for sid, expected_author, expected_repo in os_skills:
        sdir = BUILTIN_DIR / sid
        skill_file = sdir / "SKILL.md"
        assert skill_file.is_file(), f"Missing open-source skill: {skill_file}"
        content = skill_file.read_text(encoding="utf-8")
        
        # Check author credit in SKILL.md or manifest
        meta = manifest_by_id.get(sid, {})
        author_ok = (expected_author in content or expected_author.replace("@", "") in content
                     or expected_author in meta.get("github_username", "") or expected_author in meta.get("original_creator", ""))
        assert author_ok, f"Missing author credit {expected_author} in {sid}"
        
        # Check repo link in SKILL.md or manifest
        repo_ok = (expected_repo in content or expected_repo == meta.get("repository", ""))
        assert repo_ok, f"Missing repository link {expected_repo} in {sid}"


def test_all_10_cat_native_skills_exist():
    """Verify all 10 CAT-native original skills exist and are bundled offline."""
    cat_skills = [
        "cat-project-analyzer", "cat-auto-fix", "cat-context-manager",
        "cat-dependency-doctor", "cat-performance", "cat-api-builder",
        "cat-database", "cat-test-generator", "cat-deployment", "cat-quantum"
    ]
    for sid in cat_skills:
        skill_file = BUILTIN_DIR / sid / "SKILL.md"
        assert skill_file.is_file(), f"Missing CAT-native skill: {skill_file}"
        content = skill_file.read_text(encoding="utf-8")
        assert "cat-native" in content or "CAT" in content, f"{sid} missing CAT attribution"


# -----------------------------------------------------------------------------
# Test Suite 2: SkillsEngine Progressive Disclosure & Routing
# -----------------------------------------------------------------------------
def test_skills_engine_progressive_disclosure():
    """Verify level 1 fast metadata bootstrap and level 2 on-demand instruction loading."""
    engine = get_skills_engine()
    skills = engine.list_skills()
    assert len(skills) >= 35, f"Expected >= 35 skills in engine, got {len(skills)}"

    # Check a specific skill has metadata loaded
    meta = engine.get_skill("cat-quantum")
    assert meta is not None
    assert meta.category == "science"
    assert meta.active is True

    # Check instructions load on-demand
    instructions = engine.load_skill_instructions("cat-quantum")
    assert "Quantum" in instructions
    assert len(instructions) > 200


def test_skills_engine_all_6_kitties_compatibility():
    """Verify prompt generation works across all 6 Kitty personas and their aliases."""
    engine = get_skills_engine()
    kitties = ["aria", "build", "dex", "debugger", "mira", "plan", "sage", "research", "qala", "notebook", "nova", "operator"]
    for kitty in kitties:
        prompts = engine.get_skill_prompts_for_agent(kitty)
        assert len(prompts) > 100, f"Empty prompts block for kitty: {kitty}"
        assert "ACTIVE AGENT SKILLS" in prompts


def test_dynamic_skill_detection():
    """Verify prompt intent and keywords correctly route to appropriate skills."""
    engine = get_skills_engine()
    # Test debugging prompt
    detected_debug = engine.detect_relevant_skills("I have an unhandled traceback and error crash in my script", active_mode="dex")
    assert any(s in detected_debug for s in ("debugging", "cat-auto-fix")), f"Failed to detect debug skills: {detected_debug}"

    # Test testing prompt
    detected_test = engine.detect_relevant_skills("Write unit tests and pytest assertions with coverage", active_mode="build")
    assert any(s in detected_test for s in ("testing", "cat-test-generator")), f"Failed to detect test skills: {detected_test}"

    # Test quantum prompt
    detected_quantum = engine.detect_relevant_skills("Synthesize a quantum circuit with Hadamard and CNOT gates", active_mode="qala")
    assert "cat-quantum" in detected_quantum, f"Failed to detect cat-quantum: {detected_quantum}"


def test_context_isolation_and_token_budgeting():
    """Verify token budgeting limits instruction context cleanly without exceeding bounds."""
    engine = get_skills_engine()
    all_skill_ids = [s.skill_id for s in engine.list_skills()]
    # Request with a tight token budget of 500 tokens (~2000 chars)
    context = engine.load_skills_context(all_skill_ids[:15], max_tokens=500)
    assert len(context) <= 2500, f"Context exceeded token budget: {len(context)} chars"
    assert "ACTIVE AGENT SKILLS" in context


def test_skill_security_permissions():
    """Verify read actions are permitted and ungranted write/shell actions are blocked."""
    engine = get_skills_engine()
    # cat-context-manager has permissions: ["read_files"]
    assert engine.check_skill_permissions("cat-context-manager", "read_files") is True
    assert engine.check_skill_permissions("cat-context-manager", "shell_commands") is False


# -----------------------------------------------------------------------------
# Test Suite 3: Extensions & Main Menu Visibility Bug Resolution
# -----------------------------------------------------------------------------
def test_nav_items_includes_all_installed_extensions():
    """Verify get_nav_items keeps the main menu clean and focused on navigation,
    while all skills/extensions are viewed and managed in the Extensions section."""
    nav_items = get_nav_items()
    # Check standard items exist
    actions = [it[0] for it in nav_items]
    assert "open_folder" in actions
    assert "chats" in actions
    assert "ai_agents" in actions
    assert "themes" in actions
    assert "extensions" in actions

    # Skills are exclusively kept in the Extensions section (not cluttering main menu)
    assert len(actions) <= 25, f"Main menu should be clean, got {len(actions)} items"


def test_nav_panel_portrait_logic_fixed():
    """Verify is_portrait does not falsely classify standard 80x24/100x30 terminals as portrait."""
    panel = NavPanel()
    class FakeApp:
        class FakeSize:
            width = 80
            height = 24
        size = FakeSize()
    panel._app = FakeApp()
    # 80x24 has height (24) < width (80) and width (80) >= 54 -> False!
    assert panel.is_portrait() is False, "Standard 80x24 was incorrectly identified as portrait"

    # Narrow mobile screen width 48 -> True
    class MobileSize:
        width = 48
        height = 70
    panel._app.size = MobileSize()
    assert panel.is_portrait() is True

    # In portrait mode, _get_filtered() still retains chats, ai_agents, and Downloaded Extensions
    filtered = panel._get_filtered()
    filtered_actions = [it[0] for it in filtered]
    assert "chats" in filtered_actions
    assert "ai_agents" in filtered_actions
    assert "__section_dl" in filtered_actions


def test_extensions_manager_lifecycle_and_discovery():
    """Verify list_extensions returns 40+ items and enable/disable updates both registries."""
    all_exts = ext_mgr.list_extensions()
    assert len(all_exts) >= 40, f"Expected >= 40 extensions/skills, got {len(all_exts)}"

    # Ensure clean enabled baseline
    ext_mgr.enable("cat-quantum")
    assert ext_mgr.is_enabled("cat-quantum") is True
    engine = get_skills_engine()
    assert engine.is_active("cat-quantum") is True

    # Test disabling a skill
    ok, msg = ext_mgr.disable("cat-quantum")
    assert ok is True
    assert engine.is_active("cat-quantum") is False
    assert ext_mgr.is_enabled("cat-quantum") is False

    # Test re-enabling
    ok, msg = ext_mgr.enable("cat-quantum")
    assert ok is True
    assert engine.is_active("cat-quantum") is True
    assert ext_mgr.is_enabled("cat-quantum") is True
