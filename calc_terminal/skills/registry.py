"""
CAT Skills Registry — Manages Reusable, Versioned Skills for Kitties.

Provides discovery, validation, storage, and assignment of skills to built-in
and custom Kitties.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from .skill_model import SkillDefinition
from .. import storage

logger = logging.getLogger("cat.skills.registry")

_SKILLS_LOCK = threading.RLock()
_REGISTRY_INSTANCE: Optional[SkillRegistry] = None

# ── Built-in Skills Definitions ──────────────────────────────────────────────

BUILTIN_SKILLS: List[SkillDefinition] = [
    SkillDefinition(
        id="pytest-tdd-cycle",
        name="Pytest TDD & Regression Cycle",
        version="1.2.0",
        description="Structured Test-Driven Development: run tests, isolate failures, apply minimal fixes, and verify 0 regressions.",
        category="testing",
        required_tools=["run_tests", "read_file", "edit_file"],
        permission_scope={"read_files": True, "write_files": True, "shell_commands": True, "execute_python": True},
        instructions=(
            "When executing TDD cycles:\n"
            "1. Run tests first to reproduce the failure and capture the exact assertion error.\n"
            "2. Read the implementation and test files to understand expected vs actual behavior.\n"
            "3. Apply targeted, surgical modifications to the code.\n"
            "4. Re-run tests to verify the fix with returncode 0.\n"
            "5. Never guess test outcomes without running real test commands."
        ),
        tags=["testing", "pytest", "tdd", "regression", "qa"],
        builtin=True,
    ),
    SkillDefinition(
        id="git-workflow",
        name="Git Safe Branch & Commit Workflow",
        version="1.1.0",
        description="Inspect git status, prepare surgical commits with clean commit messages, and ensure working tree hygiene.",
        category="devops",
        required_tools=["run_terminal", "read_file"],
        permission_scope={"read_files": True, "write_files": False, "shell_commands": True, "execute_python": False},
        instructions=(
            "When performing git operations:\n"
            "1. Inspect `git status --short` and `git diff` before committing.\n"
            "2. Never make blanket commits with `git add .` if untracked extraneous files exist.\n"
            "3. Author concise, descriptive commit messages following Conventional Commits format."
        ),
        tags=["git", "vcs", "branching", "commits", "devops"],
        builtin=True,
    ),
    SkillDefinition(
        id="latex-equation-authoring",
        name="LaTeX Mathematical Typesetting & Validation",
        version="1.0.0",
        description="Validates mathematical delimiters, produces verified LaTeX formulas, renders Unicode terminal notations, and compiles PDFs.",
        category="science",
        required_tools=["qala_render_latex", "qala_compile_latex"],
        permission_scope={"read_files": True, "write_files": True, "shell_commands": False, "execute_python": True},
        instructions=(
            "When authoring mathematical equations:\n"
            "1. Ensure balanced delimiters for all fractions, exponents, and matrices.\n"
            "2. Use exact mathematical symbols (Greek letters, integrals, summations).\n"
            "3. Render Unicode terminal previews for readable user presentation.\n"
            "4. For document export, generate valid standalone LaTeX documents."
        ),
        tags=["latex", "math", "equations", "typesetting", "science"],
        builtin=True,
    ),
    SkillDefinition(
        id="scientific-notebook-workflow",
        name="Jupyter Notebook Computational Analysis",
        version="1.0.0",
        description="Read, modify, add, and execute computational cells in .ipynb notebooks with SymPy, NumPy, and SciPy.",
        category="science",
        required_tools=["qala_notebook_ops", "qala_solve_math"],
        permission_scope={"read_files": True, "write_files": True, "shell_commands": False, "execute_python": True},
        instructions=(
            "When operating on Jupyter notebooks:\n"
            "1. Preserve existing notebook metadata and unrelated code cells.\n"
            "2. Execute computational cells in sequence and check stdout and exceptions.\n"
            "3. Use exact symbolic mathematics (SymPy) where applicable before falling back to approximations."
        ),
        tags=["notebook", "ipynb", "science", "sympy", "scipy"],
        builtin=True,
    ),
    SkillDefinition(
        id="research-synthesis",
        name="Evidence-Grounded Research Synthesis",
        version="1.0.0",
        description="Conduct live web searches, fetch authoritative web pages, extract evidence, cite sources, and contrast hypotheses.",
        category="research",
        required_tools=["web_search", "fetch_web_page", "read_file"],
        permission_scope={"read_files": True, "write_files": False, "shell_commands": False, "network": True},
        instructions=(
            "When synthesizing research:\n"
            "1. Search multiple queries across reputable documentation and live sources.\n"
            "2. Fetch and read source pages directly to verify claims.\n"
            "3. Distinguish empirical evidence from assumptions and cite real URLs."
        ),
        tags=["research", "web-search", "evidence", "citation"],
        builtin=True,
    ),
    SkillDefinition(
        id="task-decomposition",
        name="Hierarchical Task Decomposition & Planning",
        version="1.0.0",
        description="Deconstruct complex requirements into ordered dependency graphs with clear acceptance criteria and milestones.",
        category="planning",
        required_tools=["read_file", "list_directory", "inspect_project"],
        permission_scope={"read_files": True, "write_files": False, "shell_commands": False},
        instructions=(
            "When planning complex objectives:\n"
            "1. Inspect active project structure and files before drafting steps.\n"
            "2. Identify blocking prerequisites and dependencies between steps.\n"
            "3. Establish concrete verification criteria for each milestone."
        ),
        tags=["planning", "decomposition", "milestones", "dependencies"],
        builtin=True,
    ),
    SkillDefinition(
        id="tdd-workflow",
        name="Structured Test-Driven Development (TDD) Workflow",
        version="1.3.0",
        description="Rigorous Red-Green-Refactor development cycle: author failing test first, verify failure, implement minimal code, verify green pass, and refactor cleanly.",
        category="testing",
        required_tools=["run_tests", "read_file", "edit_file", "write_file"],
        permission_scope={"read_files": True, "write_files": True, "shell_commands": True, "execute_python": True},
        instructions=(
            "When executing TDD Workflows:\n"
            "1. RED PHASE: Write an automated test that defines the desired improvement or new function. Run test suite to verify it FAILS for the expected reason.\n"
            "2. GREEN PHASE: Implement the minimal production code necessary to make the test pass. Run test suite to verify 0 failures.\n"
            "3. REFACTOR PHASE: Clean up code, remove duplication, and optimize structure while maintaining 100% test pass rate.\n"
            "4. NEVER consider work done without verifying tests directly via execution."
        ),
        tags=["tdd", "testing", "red-green-refactor", "pytest", "unit-tests"],
        builtin=True,
    ),
    SkillDefinition(
        id="brainstorming-workflow",
        name="Structured Architectural Brainstorming Workflow",
        version="1.2.0",
        description="Structured design ideation: problem framing, divergent requirement exploration, design trade-off matrix evaluation, security impact analysis, and converging into an executable technical RFC.",
        category="planning",
        required_tools=["read_file", "list_directory"],
        permission_scope={"read_files": True, "write_files": False, "shell_commands": False},
        instructions=(
            "When executing Brainstorming Workflows:\n"
            "1. Problem Framing: Define the core goals, non-goals, and technical constraints.\n"
            "2. Divergent Exploration: Generate 3+ distinct architectural approaches with pros/cons.\n"
            "3. Trade-off Matrix: Compare options across complexity, scalability, security, and developer ergonomics.\n"
            "4. Convergence: Select recommended architecture and draft concrete implementation roadmap."
        ),
        tags=["brainstorming", "ideation", "architecture", "rfc", "planning", "design"],
        builtin=True,
    ),
    SkillDefinition(
        id="rea",
        name="REA — Reasoning & Execution Architecture",
        version="1.2.0",
        description="Autonomous dual-track reasoning and stepwise execution architecture for complex coding agents. Formulates hypotheses, verifies edge cases, and audits outcomes. Highly credited to Morluto (@morluto).",
        category="planning",
        required_tools=["read_file", "edit_file", "write_file", "run_terminal"],
        permission_scope={"read_files": True, "write_files": True, "shell_commands": True, "execute_python": True},
        instructions=(
            "# REA — Reasoning & Execution Architecture (Created by Morluto — https://github.com/morluto/rea)\n"
            "When executing complex coding and algorithmic requests:\n"
            "1. Formulation: Explicitly state requirements, technical invariants, and potential failure modes.\n"
            "2. Dual-Track Hypotheses: Propose at least two competing implementation or bugfix approaches.\n"
            "3. Empirical Verification: Validate assumptions with targeted file reads or test executions before writing code.\n"
            "4. Surgical Execution: Apply minimal, high-precision code modifications.\n"
            "5. Outcome Audit: Re-test all acceptance criteria to guarantee zero regressions."
        ),
        tags=["rea", "reasoning", "execution", "planning", "agent", "morluto"],
        builtin=True,
    ),
    SkillDefinition(
        id="archify",
        name="Archify — Codebase Architecture & Blueprinting",
        version="1.0.4",
        description="Comprehensive codebase architecture analysis, modular system design blueprinting, and architectural constraint enforcement. Highly credited to tt-a1i (@tt-a1i).",
        category="architecture",
        required_tools=["read_file", "list_directory"],
        permission_scope={"read_files": True, "write_files": False, "shell_commands": False},
        instructions=(
            "# Archify — Architecture & Blueprinting (Created by tt-a1i — https://github.com/tt-a1i/archify)\n"
            "When evaluating or refactoring system architecture:\n"
            "1. Domain Boundaries: Identify decoupled subsystems, contracts, and public entrypoints.\n"
            "2. Dependency Mapping: Graph module import chains and detect circular dependencies.\n"
            "3. Layering Discipline: Strictly enforce separation between presentation, logic, and persistence.\n"
            "4. Blueprinting: Provide clear structural blueprints and architectural trade-off evaluations."
        ),
        tags=["archify", "architecture", "system-design", "blueprints", "modularity", "tt-a1i"],
        builtin=True,
    ),
    SkillDefinition(
        id="remotion",
        name="Remotion — Programmatic Video & Motion Graphics",
        version="4.0.0",
        description="Programmatic video creation, React motion graphics, audio synchronization, and MP4 rendering with Remotion. Highly credited to Jonny Burger & the Remotion team (@remotion-dev).",
        category="media",
        required_tools=["read_file", "write_file", "run_terminal"],
        permission_scope={"read_files": True, "write_files": True, "shell_commands": True, "network": True},
        instructions=(
            "# Remotion — Video & Motion Graphics (Created by Jonny Burger & Remotion — https://github.com/remotion-dev/skills)\n"
            "When authoring programmatic video compositions:\n"
            "1. Component Compositions: Structure video frames as deterministic React components parameterized by frame number.\n"
            "2. Smooth Interpolation: Use `interpolate()` and `spring()` physics curves for fluid 60fps animations.\n"
            "3. Audio Layering: Synchronize background scores and sound effects with `<Audio>` frame offsets.\n"
            "4. High-Fidelity Rendering: Verify assets, fonts, and dimensions before CLI bundling into MP4/WebM."
        ),
        tags=["remotion", "video", "motion-graphics", "react", "rendering", "media", "jonnyburger"],
        builtin=True,
    ),
    SkillDefinition(
        id="skillopt",
        name="SkillOpt — Agent Skill & Context Optimizer",
        version="1.1.0",
        description="Algorithmic skill selection, context pruning, prompt optimization, and tool execution cost minimization for AI agents. Highly credited to Microsoft Research (@microsoft).",
        category="optimization",
        required_tools=["read_file"],
        permission_scope={"read_files": True, "write_files": False, "shell_commands": False},
        instructions=(
            "# SkillOpt — Skill & Context Optimizer (Created by Microsoft Research — https://github.com/microsoft/skillopt)\n"
            "When optimizing agent workflows and LLM context windows:\n"
            "1. Intent Routing: Select only relevant tools/skills to minimize cognitive overhead.\n"
            "2. Context Compression: Strip redundant chat turns, verbose logs, and unneeded instructions.\n"
            "3. Argument Pruning: Pass minimal required payloads to tool calls.\n"
            "4. Efficiency Metrics: Monitor prompt tokens and latency to maximize task throughput."
        ),
        tags=["skillopt", "optimization", "context-pruning", "token-reduction", "microsoft", "performance"],
        builtin=True,
    ),
    SkillDefinition(
        id="page-mascot",
        name="Page Mascot — Interactive Cursor Companion",
        version="1.0.2",
        description="Interactive cursor-tracking mascot, sprite animation controller, and companion reactivity widget for TUIs and web dashboards. Highly credited to nilbuild (@nilbuild).",
        category="design",
        required_tools=["read_file", "write_file"],
        permission_scope={"read_files": True, "write_files": True, "shell_commands": False},
        instructions=(
            "# Page Mascot — Interactive Cursor Companion (Created by nilbuild — https://github.com/nilbuild/page-mascot)\n"
            "When integrating interactive companions and mascots:\n"
            "1. Pointer Tracking: Calculate angle and vector from mouse cursor to mascot eye centers.\n"
            "2. Sprite Sheet Alignment: Manage discrete head-turn atlases to prevent visual jitter.\n"
            "3. Micro-Reactions: Fire blink, purr, and startled reactions on hover and click events.\n"
            "4. Non-Blocking Render: Maintain 60fps tracking without consuming excess CPU cycles."
        ),
        tags=["page-mascot", "mascot", "companion", "cursor-tracking", "interactive", "nilbuild", "sprites"],
        builtin=True,
    ),
    SkillDefinition(
        id="frontend-design",
        name="Frontend Design — Modern UI/UX & Responsive Systems",
        version="2.1.0",
        description="Production-grade frontend design system: tactile 3D tall bevels, WCAG AA color science, fluid responsive layouts, and polished micro-interactions. Highly credited to Anthropic Quickstarts & Antigravity Design (@anthropic).",
        category="design",
        required_tools=["read_file", "edit_file", "write_file"],
        permission_scope={"read_files": True, "write_files": True, "shell_commands": False},
        instructions=(
            "# Frontend Design — Modern UI/UX & Responsive Systems (Anthropic Quickstarts Standards)\n"
            "When crafting user interfaces and visual designs:\n"
            "1. Hierarchy: Create unambiguous visual hierarchy with clean titlebars, content canvases, and action bars.\n"
            "2. Tactile 3D Bevels: Apply skeuomorphic tall bevels with realistic light source highlights and shadows.\n"
            "3. Zero Dead Space: Guarantee containers expand or shrink dynamically to eliminate awkward voids.\n"
            "4. Typography & Contrast: Ensure text passes WCAG AA contrast rules across all dark surfaces.\n"
            "5. Responsive Layouts: Design gracefully for Ultrawide, Desktop, Tablet, and Portrait screen dimensions."
        ),
        tags=["frontend-design", "design", "ui", "ux", "responsive", "typography", "tall-bevel", "anthropic"],
        builtin=True,
    ),
]


class SkillRegistry:
    """Thread-safe registry for CAT Skills."""

    def __init__(self, skills_dir: Optional[str] = None, storage_dir: Optional[str] = None):
        self.skills_dir = storage_dir or skills_dir or storage.get_subpath("skills")
        os.makedirs(self.skills_dir, exist_ok=True)
        self._skills: Dict[str, SkillDefinition] = {}
        self._bootstrap()

    def _bootstrap(self) -> None:
        with _SKILLS_LOCK:
            # Register built-ins
            for skill in BUILTIN_SKILLS:
                self._skills[skill.id.lower()] = skill

            # Register built-ins from progressive disclosure manifest.json
            manifest_file = os.path.join(os.path.dirname(__file__), "builtin", "manifest.json")
            if os.path.exists(manifest_file):
                try:
                    with open(manifest_file, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                    for item in manifest.get("skills", []):
                        sid = item.get("cat_skill_id")
                        if not sid or sid.lower() in self._skills:
                            continue
                        self._skills[sid.lower()] = SkillDefinition(
                            id=sid,
                            name=item.get("original_skill_name", sid),
                            version=item.get("local_version", "1.0.0"),
                            description=item.get("description", ""),
                            category=item.get("category", "coding"),
                            tags=[sid, item.get("category", "general")],
                            builtin=True,
                            enabled=True,
                        )
                except Exception as e:
                    logger.warning(f"Error loading manifest skills into registry: {e}")

            # Load persistent user skills from disk
            self._load_from_disk()

    def _load_from_disk(self) -> None:
        if not os.path.isdir(self.skills_dir):
            return
        for fname in os.listdir(self.skills_dir):
            if fname.endswith(".json") or fname.endswith(".catskill"):
                fpath = os.path.join(self.skills_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        skill = SkillDefinition.from_dict(data)
                        self._skills[skill.id.lower()] = skill
                except Exception as e:
                    logger.warning(f"Error loading skill from {fpath}: {e}")

    def validate_skill(self, skill: SkillDefinition) -> Tuple[bool, Optional[str]]:
        """Validate skill configuration."""
        if not skill.id or not skill.id.strip():
            return False, "Skill ID cannot be empty."
        if not re.match(r"^[a-zA-Z0-9_\-]+$", skill.id.strip()):
            return False, "Skill ID must contain only alphanumeric characters, underscores, or hyphens."
        if not skill.name or not skill.name.strip():
            return False, "Skill name cannot be empty."
        if not skill.version or not re.match(r"^\d+\.\d+\.\d+", skill.version.strip()):
            return False, "Skill version must follow semantic versioning (e.g. 1.0.0)."
        return True, None

    def register(self, skill: SkillDefinition, persist: bool = False) -> Tuple[bool, Optional[str]]:
        """Register a new or updated skill."""
        valid, err = self.validate_skill(skill)
        if not valid:
            return False, err

        with _SKILLS_LOCK:
            skill.updated_at = time.time()
            self._skills[skill.id.lower()] = skill

            if persist:
                fpath = os.path.join(self.skills_dir, f"{skill.id}.catskill")
                try:
                    with open(fpath, "w", encoding="utf-8") as f:
                        json.dump(skill.to_dict(), f, indent=2)
                except Exception as e:
                    return False, f"Failed to persist skill: {e}"

        return True, None

    def get(self, skill_id: str) -> Optional[SkillDefinition]:
        """Lookup skill by ID (case-insensitive) or by exact name."""
        with _SKILLS_LOCK:
            sid = str(skill_id or "").strip().lower()
            if sid in self._skills:
                return self._skills[sid]
            # Secondary match on name
            for s in self._skills.values():
                if s.name.lower() == sid:
                    return s
            return None

    def list_skills(self, category: Optional[str] = None) -> List[SkillDefinition]:
        """List registered skills, optionally filtered by category."""
        with _SKILLS_LOCK:
            res = list(self._skills.values())
            if category:
                cat_low = category.strip().lower()
                res = [s for s in res if s.category.lower() == cat_low]
            return sorted(res, key=lambda s: s.id)

    def unregister(self, skill_id: str) -> bool:
        """Unregister and remove a skill."""
        sid = str(skill_id or "").strip().lower()
        with _SKILLS_LOCK:
            if sid in self._skills:
                skill = self._skills[sid]
                if skill.builtin:
                    return False  # Built-ins cannot be deleted
                del self._skills[sid]
                # Remove from disk
                for ext in (".catskill", ".json"):
                    fpath = os.path.join(self.skills_dir, f"{sid}{ext}")
                    if os.path.isfile(fpath):
                        try:
                            os.remove(fpath)
                        except OSError:
                            pass
                return True
            return False

    def list_all(self) -> List[SkillDefinition]:
        """Alias for list_skills()."""
        return self.list_skills()

    def delete(self, skill_id: str) -> bool:
        """Alias for unregister()."""
        return self.unregister(skill_id)

    def export_skill(self, skill_id: str, filepath: Optional[str] = None) -> Any:
        """Export a skill to a .catskill package file or return JSON string if filepath is None."""
        skill = self.get(skill_id)
        if not skill:
            return None if filepath is None else False
        if filepath is None:
            return json.dumps(skill.to_dict(), indent=2)
        try:
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(skill.to_dict(), f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error exporting skill {skill_id}: {e}")
            return False

    def import_skill(self, source: str) -> Optional[SkillDefinition]:
        """Import a skill from a .catskill file path or raw JSON string."""
        data = None
        if os.path.isfile(source):
            try:
                with open(source, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = None
        else:
            try:
                data = json.loads(source)
            except Exception:
                data = None
        if isinstance(data, dict):
            try:
                skill = SkillDefinition.from_dict(data)
                valid, _ = self.register(skill, persist=True)
                if valid:
                    return skill
            except Exception as e:
                logger.error(f"Error importing skill: {e}")
        return None


def get_skill_registry() -> SkillRegistry:
    """Thread-safe singleton accessor."""
    global _REGISTRY_INSTANCE
    if _REGISTRY_INSTANCE is None:
        with _SKILLS_LOCK:
            if _REGISTRY_INSTANCE is None:
                _REGISTRY_INSTANCE = SkillRegistry()
    return _REGISTRY_INSTANCE
