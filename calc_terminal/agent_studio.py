"""
CAT Agent Studio (v0.7.9 Complete Platform Expansion)

Create, customize, test, and manage specialized Kitty AI agents with
custom system prompts, personality traits, allowed tools, and model preferences.
"""

import os
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional

@dataclass
class KittyAgentSpec:
    name: str
    display_name: str
    role: str
    tagline: str
    system_prompt: str
    icon: str = "🐱"
    tone: str = "balanced"  # balanced, concise, formal, playful, rigorous
    allowed_tools: List[str] = field(default_factory=list)
    preferred_model: str = "default"
    custom: bool = True
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

BUILTIN_KITTIES = [
    KittyAgentSpec(
        name="aria",
        display_name="Aria",
        role="Master Generalist & Orchestrator",
        tagline="Adaptive full-stack companion",
        system_prompt="You are Aria, the versatile lead intelligence of CAT CLI. Coordinate complex workflows, write clean code, and execute terminal tools.",
        icon="✨",
        tone="balanced",
        allowed_tools=["all"],
        custom=False
    ),
    KittyAgentSpec(
        name="dexter",
        display_name="Dexter",
        role="Deep Systems & Software Architect",
        tagline="Refactoring, debugging & systems architecture",
        system_prompt="You are Dexter, a principal systems engineer. You write bulletproof code, analyze architectures, and profile bottlenecks.",
        icon="🛠️",
        tone="rigorous",
        allowed_tools=["read_file", "write_file", "edit_file", "run_command", "git_status"],
        custom=False
    ),
    KittyAgentSpec(
        name="orion",
        display_name="Orion",
        role="Creative Strategist & Researcher",
        tagline="Design thinking & deep research",
        system_prompt="You are Orion, an AI researcher and technical strategist. Synthesize papers, plan projects, and formulate novel solutions.",
        icon="🔭",
        tone="formal",
        allowed_tools=["read_file", "search_files", "solve_math"],
        custom=False
    ),
    KittyAgentSpec(
        name="nova",
        display_name="Nova",
        role="UI/UX & Frontend Artisan",
        tagline="Textual styling, CSS & interactive experiences",
        system_prompt="You are Nova, a terminal UI specialist and UX designer. Craft pixel-perfect layouts, responsive widgets, and clean design systems.",
        icon="🎨",
        tone="playful",
        allowed_tools=["read_file", "write_file", "edit_file"],
        custom=False
    ),
    KittyAgentSpec(
        name="lyra",
        display_name="Lyra",
        role="Data Scientist & Analytics Engine",
        tagline="SQL, math, statistical modeling & data pipelines",
        system_prompt="You are Lyra, a mathematical and data science authority. Run numerical analyses, query databases, and formulate statistical proofs.",
        icon="📈",
        tone="rigorous",
        allowed_tools=["solve_math", "eval_code", "database_query"],
        custom=False
    ),
    KittyAgentSpec(
        name="echo",
        display_name="Echo",
        role="Ultra-fast Minimalist Assistant",
        tagline="Low-latency, direct terminal helper",
        system_prompt="You are Echo. Deliver immediate, concise, code-first answers without preamble or fluff.",
        icon="⚡",
        tone="concise",
        allowed_tools=["run_command", "read_file"],
        custom=False
    ),
]

class AgentStudio:
    """Manages custom and built-in Kitty agents."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agents: Dict[str, KittyAgentSpec] = {k.name.lower(): k for k in BUILTIN_KITTIES}
            cls._instance._storage_path = os.path.expanduser("~/.cat/custom_agents.json")
            os.makedirs(os.path.dirname(cls._instance._storage_path), exist_ok=True)
            cls._instance._load_custom_agents()
        return cls._instance

    def _load_custom_agents(self):
        if os.path.exists(self._storage_path):
            try:
                with open(self._storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data:
                    agent = KittyAgentSpec(**item)
                    self._agents[agent.name.lower()] = agent
            except Exception:
                pass

    def _save_custom_agents(self):
        try:
            custom_only = [a.to_dict() for a in self._agents.values() if a.custom]
            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump(custom_only, f, indent=2)
        except Exception:
            pass

    def list_agents(self) -> List[Dict[str, Any]]:
        return [a.to_dict() for a in self._agents.values()]

    def get_agent(self, name: str) -> Optional[KittyAgentSpec]:
        return self._agents.get(name.lower().strip())

    def create_agent(
        self,
        name: str,
        display_name: str,
        role: str,
        system_prompt: str,
        icon: str = "🐱",
        tone: str = "balanced",
        allowed_tools: Optional[List[str]] = None,
        preferred_model: str = "default"
    ) -> KittyAgentSpec:
        """Create and register a new custom Kitty agent."""
        slug = name.lower().strip().replace(" ", "_")
        agent = KittyAgentSpec(
            name=slug,
            display_name=display_name,
            role=role,
            tagline=f"Custom AI Agent: {role}",
            system_prompt=system_prompt,
            icon=icon,
            tone=tone,
            allowed_tools=allowed_tools or ["read_file", "search_files"],
            preferred_model=preferred_model,
            custom=True
        )
        self._agents[slug] = agent
        self._save_custom_agents()
        return agent

    def delete_agent(self, name: str) -> bool:
        slug = name.lower().strip()
        agent = self._agents.get(slug)
        if agent and agent.custom:
            del self._agents[slug]
            self._save_custom_agents()
            return True
        return False


# Global singleton
agent_studio = AgentStudio()

def get_agent_studio() -> AgentStudio:
    return agent_studio

