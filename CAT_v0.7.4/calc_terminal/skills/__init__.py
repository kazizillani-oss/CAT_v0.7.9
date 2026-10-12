"""
CAT Skills System — Reusable, Versioned Skills for Kitties.
"""

from .skill_model import SkillDefinition
from .registry import SkillRegistry, get_skill_registry, BUILTIN_SKILLS

__all__ = [
    "SkillDefinition",
    "SkillRegistry",
    "get_skill_registry",
    "BUILTIN_SKILLS",
]
