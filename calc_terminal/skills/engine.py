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
        - Aria (Build Agent) -> Archify, Frontend Design, REA
        - Mira (Plan Mode Agent) -> REA, Archify, SkillOpt
        - Qala (Notebook / Math Agent) -> SkillOpt, REA
        - Nova (Operator Agent) -> All active skills
        - Dex (Debugger Agent) -> REA, Archify
        - Sage (Research Agent) -> SkillOpt, Archify, REA
        """
        role_map = {
            "aria": ["archify", "frontend-design", "rea-reverse-engineer", "remotion-best-practices"],
            "mira": ["rea-reverse-engineer", "archify", "skillopt-sleep"],
            "qala": ["skillopt-sleep", "rea-reverse-engineer"],
            "nova": ["rea-reverse-engineer", "archify", "frontend-design", "remotion-best-practices", "page-mascot", "skillopt-sleep"],
            "dex": ["rea-reverse-engineer", "archify"],
            "sage": ["skillopt-sleep", "archify", "rea-reverse-engineer"],
        }
        target_ids = role_map.get(agent_role.lower(), list(self._skills.keys()))

        blocks = []
        for sid in target_ids:
            if self.is_active(sid):
                instr = self.load_skill_instructions(sid)
                meta = self.get_skill(sid)
                if instr and meta:
                    blocks.append(
                        f"### Active Skill: {meta.name} (by {meta.creator} {meta.github_username})\n"
                        f"Repository: {meta.repository}\n\n"
                        f"{instr}\n"
                    )

        if not blocks:
            return ""

        return "\n---\n## 🧩 ACTIVE AGENT SKILLS\n" + "\n".join(blocks) + "\n---\n"


def get_skills_engine() -> SkillsEngine:
    """Retrieve global singleton instance of SkillsEngine."""
    global _SKILLS_ENGINE_INSTANCE
    with _ENGINE_LOCK:
        if _SKILLS_ENGINE_INSTANCE is None:
            _SKILLS_ENGINE_INSTANCE = SkillsEngine()
        return _SKILLS_ENGINE_INSTANCE

