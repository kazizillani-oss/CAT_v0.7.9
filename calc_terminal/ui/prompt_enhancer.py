"""
CAT Prompt Enhancer.

Transforms ambiguous, rough, or incomplete user requests into structured, actionable prompts:
- Clarifies intended outcomes
- Organizes constraints and scope boundaries
- Separates requirements from suggestions
- Adds acceptance criteria
- Provides before/after comparison and bypass controls
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional


class PromptEnhancer:
    """Intelligent prompt refiner and clarifier."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def enhance(self, raw_prompt: str, context_type: str = "general") -> Dict[str, Any]:
        """Refines a user prompt into a structured, high-signal instruction block."""
        cleaned = raw_prompt.strip()
        if not self.enabled or len(cleaned) < 10:
            return {
                "original": raw_prompt,
                "enhanced": raw_prompt,
                "changed": False,
                "notes": "Prompt enhancer bypassed or prompt too short.",
            }

        # Structure analysis
        has_tests = bool(re.search(r"\b(test|validate|verify|check)\b", cleaned, re.I))
        has_files = bool(re.search(r"\b(file|code|script|module|class|function)\b", cleaned, re.I))

        sections = []
        sections.append(f"## Objective\n{cleaned}")

        constraints = []
        if has_files:
            constraints.append("Inspect relevant project files before making changes.")
            constraints.append("Preserve unrelated files and maintain existing coding style.")
        if not has_tests:
            constraints.append("Verify changes with appropriate tests or build checks.")
        constraints.append("Explain actions taken with actual file paths and clear diffs.")

        sections.append("## Constraints & Scope\n" + "\n".join(f"- {c}" for c in constraints))

        acceptance_criteria = [
            "The requested functionality works as expected without errors or regressions.",
            "All modified files pass syntax and lint validations.",
        ]
        sections.append("## Acceptance Criteria\n" + "\n".join(f"- [ ] {ac}" for ac in acceptance_criteria))

        enhanced = "\n\n".join(sections)
        return {
            "original": raw_prompt,
            "enhanced": enhanced,
            "changed": True,
            "added_constraints": len(constraints),
            "added_criteria": len(acceptance_criteria),
        }


prompt_enhancer = PromptEnhancer()
