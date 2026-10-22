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
