"""
CAT Skills Engine — Progressive Disclosure & Agent Skills Runtime (v0.9.000).

Implements progressive disclosure for agent skills:
- Level 1: Lightweight metadata index parsed from manifest.json on startup (~2ms, minimal RAM).
- Level 2: Lazy on-demand loading of full SKILL.md instruction blocks and YAML frontmatter.
- Level 3: Dynamic skill activation, agent routing, and MCP protocol integration.

Supports official skills:
- REA (Reverse Engineer Anything) — Morluto (@morluto)
- Archify (Architecture Blueprinting) — tt-a1i (@tt-a1i)
- Remotion Best Practices — Jonny Burger & Remotion Dev (@remotion-dev)
- SkillOpt — Microsoft Research (@microsoft)
- Page Mascot — nilbuild (@nilbuild)
- Frontend Design — Anthropic & Antigravity Design (@anthropic)
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("cat.skills.engine")

_ENGINE_LOCK = threading.RLock()
_SKILLS_ENGINE_INSTANCE: Optional[SkillsEngine] = None

_BUILTIN_DIR = Path(__file__).parent / "builtin"
_MANIFEST_FILE = _BUILTIN_DIR / "manifest.json"


class SkillMetadata:
    """Lightweight metadata descriptor for progressive disclosure."""

    def __init__(
        self,
        skill_id: str,
        name: str,
        creator: str,
        github_username: str,
        repository: str,
        category: str,
        icon: str,
        local_path: str,
        version: str = "1.0.0",
        license_name: str = "MIT",
        upstream_commit: str = "",
        description: str = "",
    ):
        self.skill_id = skill_id
        self.name = name
        self.creator = creator
        self.github_username = github_username
        self.repository = repository
        self.category = category
        self.icon = icon
        self.local_path = local_path
        self.version = version
        self.license_name = license_name
        self.upstream_commit = upstream_commit
        self.description = description
        self.active: bool = True
        self.loaded_instructions: Optional[str] = None
        self.frontmatter: Dict[str, Any] = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.skill_id,
            "name": self.name,
            "creator": self.creator,
            "github_username": self.github_username,
            "repository": self.repository,
            "category": self.category,
            "icon": self.icon,
            "version": self.version,
            "license": self.license_name,
            "active": self.active,
            "description": self.description,
            "upstream_commit": self.upstream_commit,
        }


class SkillsEngine:
    """Core runtime engine managing Agent Skills with progressive disclosure."""

    def __init__(self, builtin_dir: Optional[Path] = None):
        self.builtin_dir = builtin_dir or _BUILTIN_DIR
        self.manifest_file = self.builtin_dir / "manifest.json"
        self._skills: Dict[str, SkillMetadata] = {}
        self._active_skill_ids: set[str] = set()
        self._loaded: bool = False
        self._bootstrap_metadata()

    def _bootstrap_metadata(self) -> None:
        """Level 1: Fast initialization loading only metadata descriptors from manifest.json."""
        with _ENGINE_LOCK:
            if not self.manifest_file.exists():
                logger.warning(f"Manifest not found at {self.manifest_file}")
                return

            try:
                with open(self.manifest_file, "r", encoding="utf-8") as f:
                    manifest = json.load(f)

                skills_list = manifest.get("skills", [])
                for entry in skills_list:
                    sid = entry.get("cat_skill_id")
                    if not sid:
                        continue
                    desc = entry.get("description") or f"Official skill by {entry.get('original_creator', 'community')} ({entry.get('category', 'general')})"
                    meta = SkillMetadata(
                        skill_id=sid,
                        name=entry.get("original_skill_name", sid),
                        creator=entry.get("original_creator", "Unknown"),
                        github_username=entry.get("github_username", ""),
                        repository=entry.get("repository", ""),
                        category=entry.get("category", "coding"),
                        icon=entry.get("icon", "⚡"),
                        local_path=entry.get("local_path", ""),
                        version=entry.get("local_version", "1.0.0"),
                        license_name=entry.get("license", "MIT"),
                        upstream_commit=entry.get("upstream_commit_sha", ""),
                        description=desc,
                    )
                    self._skills[sid.lower()] = meta
                    self._active_skill_ids.add(sid.lower())

                self._loaded = True
                logger.info(f"Loaded {len(self._skills)} skills descriptors via progressive disclosure.")
            except Exception as e:
                logger.error(f"Error bootstrapping skills manifest: {e}")

    def list_skills(self) -> List[SkillMetadata]:
        """Return list of all registered skill metadata descriptors."""
        with _ENGINE_LOCK:
            return list(self._skills.values())

    def get_skill(self, skill_id: str) -> Optional[SkillMetadata]:
        """Lookup skill metadata by ID."""
        with _ENGINE_LOCK:
            return self._skills.get(str(skill_id).strip().lower())

    def is_active(self, skill_id: str) -> bool:
        """Check whether a skill is currently active."""
        with _ENGINE_LOCK:
            return str(skill_id).strip().lower() in self._active_skill_ids

    def activate_skill(self, skill_id: str) -> bool:
        """Activate a skill."""
        with _ENGINE_LOCK:
            sid = str(skill_id).strip().lower()
            if sid in self._skills:
                self._active_skill_ids.add(sid)
                self._skills[sid].active = True
                return True
            return False

    def deactivate_skill(self, skill_id: str) -> bool:
        """Deactivate a skill."""
        with _ENGINE_LOCK:
            sid = str(skill_id).strip().lower()
            if sid in self._skills:
                self._active_skill_ids.discard(sid)
                self._skills[sid].active = False
                return True
            return False

    def load_skill_instructions(self, skill_id: str) -> str:
        """
        Level 2: Progressive disclosure on-demand loading of full SKILL.md.
        Loads and caches content only when the skill is actually invoked.
        """
        with _ENGINE_LOCK:
            sid = str(skill_id).strip().lower()
            meta = self._skills.get(sid)
            if not meta:
                return ""

            if meta.loaded_instructions is not None:
                return meta.loaded_instructions

            # Resolve relative local path against repo root or builtin dir
            target_file: Optional[Path] = None
            if meta.local_path:
                candidate = Path(meta.local_path)
                if candidate.is_file():
                    target_file = candidate
                elif (self.builtin_dir.parent.parent / meta.local_path).is_file():
                    target_file = self.builtin_dir.parent.parent / meta.local_path
                elif (self.builtin_dir / sid / "SKILL.md").is_file():
                    target_file = self.builtin_dir / sid / "SKILL.md"

            if not target_file or not target_file.exists():
                fallback_candidates = [
                    self.builtin_dir / sid / "SKILL.md",
                    self.builtin_dir / sid.replace("-", "_") / "SKILL.md",
                ]
                for c in fallback_candidates:
                    if c.is_file():
                        target_file = c
                        break

            if not target_file or not target_file.exists():
                logger.warning(f"SKILL.md for {sid} not found at {meta.local_path}")
                meta.loaded_instructions = ""
                return ""

            try:
                with open(target_file, "r", encoding="utf-8") as f:
                    raw_content = f.read()

                # Parse optional YAML frontmatter
                instructions = raw_content
                if raw_content.startswith("---"):
                    parts = raw_content.split("---", 2)
                    if len(parts) >= 3:
                        instructions = parts[2].strip()
                        # Quick key-value parse for frontmatter
                        for line in parts[1].splitlines():
                            if ":" in line:
                                k, v = line.split(":", 1)
                                meta.frontmatter[k.strip()] = v.strip().strip('"\'')
                                if k.strip() == "description" and not meta.description:
                                    meta.description = v.strip().strip('"\'')

                meta.loaded_instructions = instructions
                logger.info(f"Loaded full instructions for {sid} ({len(instructions)} chars).")
                return instructions
            except Exception as e:
                logger.error(f"Error reading {target_file}: {e}")
                return ""

    def get_skill_prompts_for_agent(self, agent_role: str) -> str:
        """
        Produce a tailored instructions block for the given Kitty agent role:
        - Aria / Build -> Frontend Design, UI/UX Pro Max, Archify, REA, TS Wizard, API Builder, Refactoring
        - Dex / Debugger -> Debugging, Auto-Fix, Dependency Doctor, Code Review, Testing, Performance
        - Mira / Plan -> Planning, Brainstorming, Archify, REA, Context Manager, Research
        - Sage / Research -> Research, Scientific Research, Documentation, Find-Skills, SkillOpt
        - Qala / Notebook -> Scientific Research, Quantum Engine, SkillOpt, REA
        - Nova / Operator -> Dynamic multi-skill orchestration across all active capabilities
        """
        role_map = {
            "aria": [
                "frontend-design", "ui-ux-pro-max", "cat-api-builder", "archify",
                "rea-reverse-engineer", "ts-wizard", "refactoring", "cat-project-analyzer",
                "mcp-builder", "remotion-best-practices"
            ],
            "build": [
                "frontend-design", "ui-ux-pro-max", "cat-api-builder", "archify",
                "rea-reverse-engineer", "ts-wizard", "refactoring", "cat-project-analyzer",
                "mcp-builder", "remotion-best-practices"
            ],
            "mira": ["planning", "brainstorming", "archify", "rea-reverse-engineer", "cat-context-manager", "research", "skillopt-sleep"],
            "plan": ["planning", "brainstorming", "archify", "rea-reverse-engineer", "cat-context-manager", "research", "skillopt-sleep"],
            "dex": ["debugging", "cat-auto-fix", "cat-dependency-doctor", "code-review", "rea-reverse-engineer", "testing", "cat-performance"],
            "debugger": ["debugging", "cat-auto-fix", "cat-dependency-doctor", "code-review", "rea-reverse-engineer", "testing", "cat-performance"],
            "debug": ["debugging", "cat-auto-fix", "cat-dependency-doctor", "code-review", "rea-reverse-engineer", "testing", "cat-performance"],
            "sage": ["research", "scientific-research", "documentation", "find-skills", "skillopt-sleep", "cat-quantum", "archify"],
            "research": ["research", "scientific-research", "documentation", "find-skills", "skillopt-sleep", "cat-quantum", "archify"],
            "qala": ["scientific-research", "cat-quantum", "skillopt-sleep", "rea-reverse-engineer", "math"],
            "notebook": ["scientific-research", "cat-quantum", "skillopt-sleep", "rea-reverse-engineer"],
            "math": ["scientific-research", "cat-quantum", "skillopt-sleep", "rea-reverse-engineer"],
            "nova": [
                "cat-project-analyzer", "rea-reverse-engineer", "archify", "planning",
                "debugging", "cat-auto-fix", "frontend-design", "testing", "git-workflow",
                "superpowers", "page-mascot", "skillopt-sleep"
            ],
            "operator": [
                "cat-project-analyzer", "rea-reverse-engineer", "archify", "planning",
                "debugging", "cat-auto-fix", "frontend-design", "testing", "git-workflow",
                "superpowers", "page-mascot", "skillopt-sleep"
            ],
        }
        target_ids = role_map.get(agent_role.lower(), list(self._skills.keys()))
        return self.load_skills_context(target_ids, max_tokens=6000)

    def detect_relevant_skills(self, prompt: str, active_mode: str = "nova", max_skills: int = 4) -> List[str]:
        """
        Dynamically detect the most relevant skills based on user prompt, intent keywords,
        and current active Kitty agent role.
        """
        p_low = prompt.lower()
        matched_scores: Dict[str, int] = {}

        keyword_rules = [
            (["test", "pytest", "unit test", "integration test", "coverage", "mock", "assert"], ["testing", "cat-test-generator"]),
            (["debug", "error", "traceback", "exception", "crash", "fix this", "bug", "segfault"], ["debugging", "cat-auto-fix"]),
            (["plan", "roadmap", "architecture", "break down", "design system", "steps to implement"], ["planning", "brainstorming", "archify"]),
            (["review", "audit", "security", "vulnerability", "cve", "owasp", "leak", "clean code"], ["code-review", "security-audit", "cloudflare-security"]),
            (["git", "commit", "branch", "merge", "conflict", "stash", "pr", "repo"], ["git-workflow"]),
            (["ui", "ux", "css", "layout", "responsive", "frontend", "bevel", "color", "screen", "theme"], ["frontend-design", "ui-ux-pro-max", "page-mascot", "impeccable"]),
            (["mcp", "model context protocol", "mcp server", "tools/call"], ["mcp-builder"]),
            (["typescript", "generics", "type-level", "ts-ignore", "interface", "zod"], ["ts-wizard"]),
            (["humanize", "robotic", "natural writing", "rewrite", "tone", "cliche"], ["humanizer"]),
            (["seo", "meta tags", "sitemap", "web vitals", "indexable", "googlebot"], ["seo-optimization"]),
            (["quantum", "qiskit", "circuit", "qubit", "superposition", "statevector"], ["cat-quantum"]),
            (["database", "sql", "migration", "query", "schema", "postgres", "sqlite"], ["cat-database"]),
            (["api", "rest", "graphql", "fastapi", "endpoint", "openapi", "routes"], ["cat-api-builder"]),
            (["docker", "container", "deploy", "ci/cd", "github actions", "devops"], ["cat-deployment"]),
            (["browser", "playwright", "puppeteer", "scrape", "headless", "e2e"], ["browser-automation"]),
            (["performance", "profile", "bottleneck", "slow", "memory leak", "cpu", "latency"], ["cat-performance", "addy-agent-skills"]),
            (["reverse engineer", "disassemble", "decompile", "inspect binary"], ["rea-reverse-engineer"]),
            (["dependency", "package", "pip install", "npm install", "lockfile", "version conflict"], ["cat-dependency-doctor"]),
            (["video", "animation", "motion graphics", "render mp4", "remotion"], ["remotion-best-practices"]),
            (["analyze project", "project structure", "workspace summary", "tech stack"], ["cat-project-analyzer"]),
            (["superpower", "sysadmin", "system recon", "processes", "daemon"], ["superpowers"]),
        ]

        for keywords, skill_list in keyword_rules:
            for kw in keywords:
                if kw in p_low:
                    for sid in skill_list:
                        matched_scores[sid] = matched_scores.get(sid, 0) + 3

        # Add agent role affinity
        role_priors = {
            "aria": ["frontend-design", "ui-ux-pro-max", "cat-api-builder"],
            "build": ["frontend-design", "ui-ux-pro-max", "cat-api-builder"],
            "dex": ["debugging", "cat-auto-fix", "code-review"],
            "debugger": ["debugging", "cat-auto-fix", "code-review"],
            "mira": ["planning", "brainstorming", "archify"],
            "plan": ["planning", "brainstorming", "archify"],
            "sage": ["research", "scientific-research", "documentation"],
            "research": ["research", "scientific-research", "documentation"],
            "qala": ["scientific-research", "cat-quantum", "skillopt-sleep"],
            "nova": ["cat-project-analyzer", "rea-reverse-engineer"],
        }
        for sid in role_priors.get(active_mode.lower(), []):
            matched_scores[sid] = matched_scores.get(sid, 0) + 1

        # Sort descending by score
        sorted_skills = sorted(matched_scores.items(), key=lambda x: x[1], reverse=True)
        return [sid for sid, score in sorted_skills if self.is_active(sid)][:max_skills]

    def load_skills_context(self, skill_ids: List[str], max_tokens: int = 4000) -> str:
        """
        Progressive disclosure context loader: formats instruction blocks with strict
        context isolation and token budgeting (~4 chars per token).
        """
        max_chars = max_tokens * 4
        blocks = []
        current_chars = 0

        for sid in skill_ids:
            if not self.is_active(sid):
                continue
            meta = self.get_skill(sid)
            instr = self.load_skill_instructions(sid)
            if not meta or not instr:
                continue

            block = (
                f"### Active Skill: {meta.name} (by {meta.creator} {meta.github_username})\n"
                f"Repository: {meta.repository}\n"
                f"Category: {meta.category.title()} | License: {meta.license_name}\n\n"
                f"{instr}\n"
            )

            # Check if block fits within budget
            if current_chars + len(block) > max_chars:
                # Truncate cleanly at section boundary
                allowed = max_chars - current_chars
                if allowed > 400:
                    truncated_instr = instr[:allowed - 200]
                    # Cut to last newline
                    if "\n" in truncated_instr:
                        truncated_instr = truncated_instr.rsplit("\n", 1)[0]
                    truncated_block = (
                        f"### Active Skill: {meta.name} (by {meta.creator} {meta.github_username})\n"
                        f"Repository: {meta.repository} [Summary Mode]\n\n"
                        f"{truncated_instr}\n\n*(remaining instructions truncated for context budget)*\n"
                    )
                    blocks.append(truncated_block)
                break

            blocks.append(block)
            current_chars += len(block)

        if not blocks:
            return ""

        return "\n---\n## 🧩 ACTIVE AGENT SKILLS\n" + "\n".join(blocks) + "\n---\n"

    def check_skill_permissions(self, skill_id: str, requested_action: str) -> bool:
        """
        Check whether a skill's declared permission scope permits the requested action.
        Standard scopes: 'read_files', 'write_files', 'shell_commands', 'network'.
        """
        meta = self.get_skill(skill_id)
        if not meta:
            return False
        # Read frontmatter permissions if available
        perms = meta.frontmatter.get("permissions") or []
        if isinstance(perms, str):
            perms = [p.strip() for p in perms.strip("[]").replace("'", "").replace('"', '').split(",")]
        # Default safety: read_files is allowed for all active skills; destructive actions require explicit grant
        if requested_action in ("read_files", "read"):
            return True
        return requested_action in perms


def get_skills_engine() -> SkillsEngine:
    """Retrieve global singleton instance of SkillsEngine."""
    global _SKILLS_ENGINE_INSTANCE
    with _ENGINE_LOCK:
        if _SKILLS_ENGINE_INSTANCE is None:
            _SKILLS_ENGINE_INSTANCE = SkillsEngine()
        return _SKILLS_ENGINE_INSTANCE

