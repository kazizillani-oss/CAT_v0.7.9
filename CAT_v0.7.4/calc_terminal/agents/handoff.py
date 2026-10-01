"""
CAT Agents — Structured Agent Handoff System.

Provides structured internal messaging between collaborating agents
rather than passing uncontrolled raw text.
"""

from __future__ import annotations

import copy
import logging
import time
from typing import Any, Dict, List, Optional, Sequence

from .agent_model import AgentResult

logger = logging.getLogger("cat.agents.handoff")


class AgentHandoffPipeline:
    """Manages the structured flow of work and results between agents."""

    def __init__(self, mission_id: Optional[str] = None):
        self.mission_id = mission_id or f"handoff-{int(time.time())}"
        self.history: List[AgentResult] = []
        self.context_artifacts: Dict[str, Any] = {}
        self.changed_files: Set[str] = set()

    def submit_result(self, result: AgentResult) -> None:
        """Records an agent's structured result and updates cumulative state."""
        self.history.append(result)
        for f in result.files_changed:
            self.changed_files.add(f)
        for k, v in result.artifacts.items():
            self.context_artifacts[k] = v

    def build_handoff_context(self, target_agent_id: str, prompt: str = "") -> Dict[str, Any]:
        """Prepares structured context for the next agent in the sequence."""
        recent_results = [r.to_dict() for r in self.history[-5:]]
        accumulated_errors = []
        for r in self.history:
            accumulated_errors.extend(r.errors)

        return {
            "mission_id": self.mission_id,
            "target_agent": target_agent_id,
            "user_prompt": prompt,
            "recent_results": recent_results,
            "all_changed_files": sorted(list(self.changed_files)),
            "active_errors": accumulated_errors[-10:],
            "artifacts": self.context_artifacts,
        }

    def format_handoff_prompt(self, target_agent_id: str, original_prompt: str) -> str:
        """Builds a high-signal prompt containing prior agent findings and artifacts."""
        lines = [f"[Agent Collaboration Context for {target_agent_id}]"]
        if self.history:
            lines.append("Previous Agent Actions:")
            for r in self.history[-4:]:
                status_glyph = "✓" if r.status == "success" else "✗"
                lines.append(f"  {status_glyph} {r.agent_id}: {r.summary}")
                if r.files_changed:
                    lines.append(f"    Modified: {', '.join(r.files_changed[:8])}")
                if r.errors:
                    lines.append(f"    Errors: {'; '.join(r.errors[:3])}")

        if self.changed_files:
            lines.append(f"\nFiles Modified So Far: {', '.join(sorted(list(self.changed_files)))}")

        if self.context_artifacts:
            lines.append("\nAvailable Artifacts:")
            for k, v in self.context_artifacts.items():
                summary = str(v)[:150].replace("\n", " ")
                lines.append(f"  - {k}: {summary}")

        lines.append(f"\nCurrent Task Instruction:\n{original_prompt}")
        return "\n".join(lines)
