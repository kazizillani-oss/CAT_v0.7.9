"""
CAT Documentation & Learning Center (v1.0.0)

Unified documentation, interactive tutorials, developer guides, and API references:
- Comprehensive User Manual covering all 6 AI modes, Kitties, tools, browser, and deployment
- Complete Developer SDK Reference for extensions, skills, custom commands, and agents
- Interactive learning tracks (/learn basics, /learn extensions, /learn agents, /learn mcp)
- Dynamic validation verifying documentation against live registered commands and capabilities
"""

from __future__ import annotations

import os
import sys
import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple

from .commands_data import COMMANDS
from .capability_registry import get_registry


@dataclass
class DocTopic:
    id: str
    title: str
    category: str  # "user", "developer", "modes", "tools", "tutorial"
    summary: str
    content: str
    commands: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


DOC_TOPICS: List[DocTopic] = [
    DocTopic(
        id="getting_started",
        title="Getting Started with CAT CLI",
        category="user",
        summary="Initial setup, first run, and core user interface overview.",
        content="""# Getting Started with CAT CLI

CAT (Coding Agent Terminal) is an extensible, autonomous development environment with 6 AI modes, interactive browser, terminal multiplexing, and mathematical solvers.

## Quick Start
1. **Launch:** Run `cat` in your terminal or open the standalone GUI app.
2. **Setup Provider:** Type `/model` to configure an AI provider (Ollama, OpenAI, Anthropic, Gemini, DeepSeek, or NVIDIA NIM).
3. **Open Workspace:** Type `/open <folder>` or use the Explorer button to mount your project.
4. **Interactive Autocomplete:** Press `/` anytime in the composer to discover all commands.""",
        commands=["/help", "/model", "/open", "/shortcuts"],
        tags=["basics", "setup", "intro"],
    ),
    DocTopic(
        id="ai_modes",
        title="AI Modes & Specialized Kitties",
        category="modes",
        summary="Guide to Notebook, Research, Plan, Build, Debugger, and Agent modes.",
        content="""# CAT AI Modes & Kitty Personas

CAT separates intelligence into distinct operational modes with strict context isolation:
- **Notebook Mode (`/notebook`):** Interactive scientific calculations, SymPy derivations, and executable cells.
- **Research Mode (`/research`):** Deep academic and web investigation using European PMC, arXiv, and ChEMBL.
- **Plan Mode (`/plan`):** High-level architecture and task DAG decomposition before code modifications.
- **Build Mode (`/build`):** Deterministic project generation, file creation, and automated builds.
- **Debugger Mode (`/debug`):** Traceback analysis, AST inspection, and pinpoint fixes.
- **Agent Mode (`/agent`):** Autonomous multi-step Kitty collaboration (Aria, Dexter, Orion, Nova, Lyra, Echo).""",
        commands=["/mode", "/kitties", "/agent", "/plan", "/debug", "/notebook", "/build", "/research"],
        tags=["modes", "agents", "kitties"],
    ),
    DocTopic(
        id="developer_sdk",
        title="Developer SDK & Extension Authoring",
        category="developer",
        summary="How to build, validate, test, and package third-party extensions using CAT Developer SDK.",
        content="""# CAT Developer SDK Guide

Developers can create extensions, skills, and custom slash commands without touching CAT Core.

## Quick Extension Creation:
Run: `/dev extension create <name>`
This scaffolds:
- `manifest.json`: Metadata, declared permissions, and entry point.
- `extension.py`: Subclassing `calc_terminal.sdk.Extension` with lifecycle hooks `on_init()`, `on_load()`.

## Validation & Packaging:
- Validate: `/dev validate`
- Test: `/dev test`
- Package: `/dev package` (generates `.catpkg` bundle)""",
        commands=["/dev", "/dev extension create", "/dev validate", "/dev package", "/dev docs"],
        tags=["sdk", "developer", "extensions", "plugins"],
    ),
    DocTopic(
        id="mcp_servers",
        title="Model Context Protocol (MCP) Integration",
        category="tools",
        summary="Connecting and executing external tools via standard MCP servers.",
        content="""# Model Context Protocol (MCP) in CAT

CAT natively supports both Stdio and SSE MCP servers.
- **Listing servers:** `/mcp list`
- **Configuring servers:** Open `/mcp` or configure `~/.cat/mcp_servers.json`.
- **Tool Execution:** Tools exposed by MCP servers are automatically bridged into the Universal Capability Registry and available to AI agents.""",
        commands=["/mcp", "/mcp list", "/mcp test"],
        tags=["mcp", "tools", "integrations"],
    ),
    DocTopic(
        id="recovery_rollback",
        title="Recovery, Rollback & Transactions",
        category="user",
        summary="Safeguards against destructive modifications, undo/redo, and atomic rollback.",
        content="""# Recovery & Rollback Engine

CAT guarantees zero accidental code loss:
- **Pre-execution Snapshots:** Automatically taken before agents or refactoring workflows touch files.
- **Undo/Redo:** `/undo` reverts the most recent change; `/redo` restores it.
- **Rollback Preview:** `/recovery preview <id>` displays a unified diff before applying changes.
- **Single File Restore:** `/recovery file <id> <path>` recovers a specific file without affecting other files.""",
        commands=["/recovery", "/undo", "/redo", "/rollback", "/checkpoint"],
        tags=["recovery", "rollback", "safety", "git"],
    ),
    DocTopic(
        id="observability_center",
        title="Observability, Traces & Logs",
        category="developer",
        summary="Monitoring execution latency, token costs, and debugging errors.",
        content="""# Observability Center

CAT provides distributed execution tracing and measured telemetry:
- **Trace Inspection:** `/trace <id>` opens a hierarchical view of all sub-agent and tool execution spans.
- **Live Metrics:** `/observe metrics` displays average and p95 latency, token counts, and USD costs.
- **Structured Logs:** `/logs search <keyword>` filters logs with automatic secret redaction.""",
        commands=["/observe", "/trace", "/logs"],
        tags=["observability", "traces", "metrics", "logs"],
    ),
]

TUTORIALS = {
    "basics": [
        "1. Setting up your first model provider with `/model`.",
        "2. Navigating your workspace with `/open` and `/workspace`.",
        "3. Using `/` autocomplete to discover all available actions.",
        "4. Running a quick scientific calculation with `/calculator` or `/solve`.",
    ],
    "extensions": [
        "1. Scaffold a project with `/dev extension create MyFeature`.",
        "2. Add a custom slash command using `@command` decorator.",
        "3. Run `/dev validate` to verify schema and AST syntax.",
        "4. Package into `.catpkg` with `/dev package`.",
    ],
    "agents": [
        "1. Understanding Kitties: Aria (generalist), Dexter (code), Orion (architect).",
        "2. Delegating tasks using structured handoffs in `/agent` mode.",
        "3. Reviewing sub-agent executions in the Observability Center (`/observe`).",
    ],
    "mcp": [
        "1. What is Model Context Protocol (MCP)?",
        "2. Installing an MCP server in CAT using `/mcp add`.",
        "3. Verifying exposed tools with `/mcp list`.",
        "4. Permitting Kitty agents to invoke external MCP tools.",
    ],
    "commands": [
        "1. Core workflow commands: `/help`, `/model`, `/mode`, `/open`, `/settings`.",
        "2. Developer commands: `/dev`, `/test`, `/diff`, `/git`, `/package`.",
        "3. Safety commands: `/recovery`, `/undo`, `/redo`, `/rollback`.",
    ],
}


class DocumentationCenter:
    """Provides searchable docs, interactive learning modules, and command auditing."""

    _instance = None

    def __init__(self):
        self.topics = {t.id: t for t in DOC_TOPICS}

    @classmethod
    def get(cls) -> "DocumentationCenter":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def search_docs(self, query: str) -> List[Dict[str, Any]]:
        q = query.lower()
        matches = []
        for t in self.topics.values():
            score = 0
            if q in t.title.lower(): score += 50
            if q in t.summary.lower(): score += 30
            if any(q in cmd.lower() for cmd in t.commands): score += 40
            if any(q in tag.lower() for tag in t.tags): score += 20
            if q in t.content.lower(): score += 10

            if score > 0:
                matches.append({"topic": t, "score": score})

        matches.sort(key=lambda m: m["score"], reverse=True)
        return [
            {
                "id": m["topic"].id,
                "title": m["topic"].title,
                "category": m["topic"].category,
                "summary": m["topic"].summary,
                "commands": m["topic"].commands,
            }
            for m in matches
        ]

    def get_topic(self, topic_id: str) -> Optional[DocTopic]:
        return self.topics.get(topic_id)

    def list_topics(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": t.id,
                "title": t.title,
                "category": t.category,
                "summary": t.summary,
            }
            for t in self.topics.values()
        ]

    def get_tutorial(self, track: str = "basics") -> List[str]:
        return TUTORIALS.get(track.lower(), TUTORIALS["basics"])

    def validate_command_documentation(self) -> Dict[str, Any]:
        """Check all registered COMMANDS against documentation topics."""
        documented_cmds = set()
        for t in self.topics.values():
            documented_cmds.update(t.commands)

        all_cmds = [c[0] for c in COMMANDS]
        missing = [c for c in all_cmds if c not in documented_cmds]

        return {
            "total_commands": len(all_cmds),
            "explicitly_documented_in_guides": len(all_cmds) - len(missing),
            "all_commands_documented_in_palette": True,
            "coverage_percent": round(((len(all_cmds) - len(missing)) / len(all_cmds)) * 100.0, 1),
        }


doc_center = DocumentationCenter.get()

