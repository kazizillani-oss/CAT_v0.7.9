"""
CAT Universal Capability Registry (v0.7.9 Complete Platform Expansion)

Central discovery, metadata, and lifecycle registry for all CAT platform capabilities:
- CORE_TOOL: built-in calculation, terminal, file, git tools
- MCP_TOOL: tools exposed via Model Context Protocol servers
- EXTENSION: packaged UI and functional add-ons
- SKILL: specialized instruction sets and automated procedures
- AGENT_KITTY: specialized AI personas (Aria, Dexter, Orion, Nova, Lyra, Echo, custom)
- MODEL: LLM providers and backends
- CLI_COMMAND: interactive slash commands
- WORKFLOW: automated multi-step pipelines
- DATABASE_ADAPTER: database connections and query runners
- INTEGRATION: external SaaS / app connectors
- DEPLOYER: build and deployment targets
- STORAGE: file and memory providers
"""

import os
import json
import inspect
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Callable

CAPABILITY_TYPES = (
    "core_tool",
    "mcp_tool",
    "extension",
    "skill",
    "agent_kitty",
    "model",
    "cli_command",
    "workflow",
    "database_adapter",
    "integration",
    "deployer",
    "storage",
)

@dataclass
class CapabilitySpec:
    id: str
    name: str
    type: str  # one of CAPABILITY_TYPES
    description: str = ""
    category: str = "General"
    provider: str = "CAT Core"
    version: str = "1.0.0"
    requires_permission: str = "normal"  # normal, protected, admin
    parameters_schema: Dict[str, Any] = field(default_factory=dict)
    handler: Optional[Callable] = None
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("handler", None)
        return d


class UniversalCapabilityRegistry:
    """Singleton capability registry providing introspection and access control."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._capabilities: Dict[str, CapabilitySpec] = {}
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not getattr(self, "_initialized", False):
            self._capabilities: Dict[str, CapabilitySpec] = {}
            self._initialized = True
            self._bootstrap_core_capabilities()

    def register(self, cap: CapabilitySpec) -> bool:
        """Register a new capability."""
        if not cap.id:
            return False
        self._capabilities[cap.id] = cap
        return True

    def unregister(self, cap_id: str) -> bool:
        """Remove a capability by ID."""
        if cap_id in self._capabilities:
            del self._capabilities[cap_id]
            return True
        return False

    def get(self, cap_id: str) -> Optional[CapabilitySpec]:
        """Fetch a capability by ID."""
        return self._capabilities.get(cap_id)

    def list_all(self, cap_type: Optional[str] = None, enabled_only: bool = False) -> List[CapabilitySpec]:
        """List capabilities filtered by type and enabled state."""
        caps = list(self._capabilities.values())
        if cap_type:
            ct = cap_type.lower()
            caps = [c for c in caps if c.type.lower() == ct]
        if enabled_only:
            caps = [c for c in caps if c.enabled]
        return caps

    def search(self, query: str) -> List[CapabilitySpec]:
        """Fuzzy keyword search across capabilities."""
        q = query.lower().strip()
        if not q:
            return list(self._capabilities.values())
        results = []
        for c in self._capabilities.values():
            haystack = f"{c.id} {c.name} {c.type} {c.description} {c.category} {c.provider}".lower()
            if q in haystack:
                results.append(c)
        return results

    def enable(self, cap_id: str) -> bool:
        """Enable a capability."""
        c = self._capabilities.get(cap_id)
        if c:
            c.enabled = True
            return True
        return False

    def disable(self, cap_id: str) -> bool:
        """Disable a capability."""
        c = self._capabilities.get(cap_id)
        if c:
            c.enabled = False
            return True
        return False

    def get_agent_capabilities(self, agent_name: str) -> List[CapabilitySpec]:
        """Return capabilities permitted for a specific Kitty agent."""
        agent_name = agent_name.lower()
        all_caps = self.list_all(enabled_only=True)
        # Aria has full access; others may specialize
        if agent_name in ("aria", "echo"):
            return all_caps
        elif agent_name == "dexter":
            # Developer agent: tools, code intel, git, terminal
            return [c for c in all_caps if c.type in ("core_tool", "cli_command", "mcp_tool", "database_adapter", "deployer")]
        elif agent_name == "orion":
            # Architect/researcher: code intel, knowledge, workflows
            return [c for c in all_caps if c.type in ("core_tool", "cli_command", "workflow", "storage")]
        elif agent_name == "nova":
            # Creative/UI/frontend
            return [c for c in all_caps if c.type in ("core_tool", "cli_command", "extension", "integration")]
        elif agent_name == "lyra":
            # Data/analytics agent
            return [c for c in all_caps if c.type in ("core_tool", "cli_command", "database_adapter", "workflow")]
        return all_caps

    def _bootstrap_core_capabilities(self):
        """Bootstrap default capabilities from existing CAT systems."""
        # Core Kitties
        kitties = [
            ("agent_aria", "Aria", "Master Generalist & Orchestrator", "orchestration"),
            ("agent_dexter", "Dexter", "Deep Systems & Software Architect", "development"),
            ("agent_orion", "Orion", "Creative Strategist & Researcher", "research"),
            ("agent_nova", "Nova", "UI/UX & Frontend Artisan", "frontend"),
            ("agent_lyra", "Lyra", "Data Scientist & Analytics Engine", "data"),
            ("agent_echo", "Echo", "Ultra-fast Minimalist Assistant", "quick"),
        ]
        for cid, name, desc, cat in kitties:
            self.register(CapabilitySpec(
                id=cid,
                name=name,
                type="agent_kitty",
                description=desc,
                category=cat,
                provider="CAT Core",
                requires_permission="normal"
            ))

        # Core Tools
        tools = [
            ("tool_read_file", "Read File", "Read text or binary files from workspace", "file_io"),
            ("tool_write_file", "Write File", "Create or append files in workspace", "file_io"),
            ("tool_edit_file", "Edit File", "Surgically patch files in workspace", "file_io"),
            ("tool_run_command", "Run Shell Command", "Execute powershell/bash commands", "terminal"),
            ("tool_search_files", "Search Files", "Find files by pattern or content", "workspace"),
            ("tool_git_status", "Git Status", "Check repository branch and modified files", "git"),
            ("tool_solve_math", "Solve Math", "Evaluate algebraic and calculus equations", "math"),
            ("tool_eval_code", "Eval Code", "Execute Python expressions safely in sandbox", "execution"),
        ]
        for tid, name, desc, cat in tools:
            self.register(CapabilitySpec(
                id=tid,
                name=name,
                type="core_tool",
                description=desc,
                category=cat,
                provider="CAT Core",
                requires_permission="protected" if "write" in tid or "command" in tid else "normal"
            ))

        # Platform Engines
        engines = [
            ("engine_code_intel", "Code Intelligence Engine", "AST indexing, symbol search, dead code detection", "intelligence"),
            ("engine_ai_eval", "AI Evaluation Engine", "Model latency, benchmark scoring, side-by-side comparison", "evaluation"),
            ("engine_automation", "Automation Engine", "Scheduled cron triggers, multi-agent delegation", "automation"),
            ("engine_security", "Security Center", "Secret scanner, dependency audit, AST code safety", "security"),
            ("engine_deployment", "Deployment Center", "Multi-target deployers (Vercel, Netlify, Docker, SSH)", "deployment"),
            ("engine_db_studio", "Database Studio", "SQLite, Postgres, MySQL schema and query runner", "database"),
            ("engine_ai_cost", "AI Cost Manager", "Token usage tracking, budget caps, provider pricing", "finance"),
            ("engine_workflow", "Workflow Builder", "DAG node workflow pipelines and templates", "automation"),
            ("engine_github", "GitHub Studio", "Repos, PRs, issues, actions, and commits", "vcs"),
            ("engine_cloud", "Cloud Workspace", "Remote SSH and Docker container workspace manager", "cloud"),
            ("engine_knowledge", "Knowledge Center", "Document parser, semantic search with citations", "knowledge"),
            ("engine_connectors", "App Connectors", "Google, Slack, Notion, Discord integrations", "integrations"),
        ]
        for eid, name, desc, cat in engines:
            self.register(CapabilitySpec(
                id=eid,
                name=name,
                type="workflow",
                description=desc,
                category=cat,
                provider="CAT Platform",
                requires_permission="normal"
            ))


# Global singleton instance
capability_registry = UniversalCapabilityRegistry()

def get_registry() -> UniversalCapabilityRegistry:
    return capability_registry

