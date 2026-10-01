"""
CAT Tools — Standardized Tool Registry & Permission Gating System.

Provides a unified registry for all agent tools:
- Filesystem (read_file, write_file, edit_file, delete_file, list_directory, search_workspace)
- Execution (run_terminal, run_build, run_tests, install_packages, calculate)
- Research (web_search, deep_research, read_attachment)
- MCP (Model Context Protocol dynamically registered tools)
- Version control & diagnostics
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from . import permissions as perm

logger = logging.getLogger("cat.tools_registry")

_REGISTRY_LOCK = threading.RLock()
_TOOL_INSTANCE: Optional[ToolRegistry] = None


@dataclass
class ToolSpec:
    name: str
    description: str
    category: str = "general"               # "files" | "terminal" | "research" | "testing" | "mcp" | "calculation"
    args_schema: str = "{}"
    perm_key: Optional[str] = None          # Key in permissions.py, e.g. "write_files", "shell_commands"
    handler: Optional[Callable[[Dict[str, Any]], Any]] = None
    enabled: bool = True
    is_mcp: bool = False
    mcp_server_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "args_schema": self.args_schema,
            "perm_key": self.perm_key,
            "enabled": self.enabled,
            "is_mcp": self.is_mcp,
            "mcp_server_id": self.mcp_server_id,
        }


class ToolRegistry:
    """Thread-safe registry for CAT tools."""

    def __init__(self):
        self._tools: Dict[str, ToolSpec] = {}
        self._disabled_tools: set[str] = set()
        self._bootstrap_tools()

    def _bootstrap_tools(self) -> None:
        """Registers built-in tools from agent.py."""
        try:
            from . import agent

            for name, meta in agent.TOOLS.items():
                cat = "general"
                if "file" in name or "directory" in name or "archive" in name or "workspace" in name:
                    cat = "files"
                elif "terminal" in name or "package" in name:
                    cat = "terminal"
                elif "search" in name or "research" in name or "attachment" in name:
                    cat = "research"
                elif "test" in name or "build" in name or "inspect" in name:
                    cat = "testing"
                elif "plot" in name or "formula" in name or "solve" in name or "sim" in name or "calc" in name:
                    cat = "calculation"

                desc = meta.get("desc", "")
                args_s = meta.get("args", "{}")
                perm_k = meta.get("perm_key")
                run_fn = meta.get("run")

                spec = ToolSpec(
                    name=name,
                    description=desc,
                    category=cat,
                    args_schema=args_s,
                    perm_key=perm_k,
                    handler=run_fn,
                    enabled=True,
                )
                self._tools[name] = spec
        except Exception as e:
            logger.warning(f"Error bootstrapping built-in tools: {e}")

        # Also register dynamic MCP tools
        self._sync_mcp_tools()

    def _sync_mcp_tools(self) -> None:
        """Syncs registered MCP tools from mcp.py."""
        try:
            from . import mcp

            servers = mcp.load_servers()
            for s in servers:
                if not s.get("enabled"):
                    continue
                sid = s.get("id") or s.get("name")
                for t in s.get("tools", []):
                    t_name = f"mcp_{sid}_{t.get('name')}" if not t.get('name', '').startswith('mcp_') else t.get('name')
                    spec = ToolSpec(
                        name=t_name,
                        description=f"[MCP {sid}] {t.get('description', '')}",
                        category="mcp",
                        args_schema=str(t.get("inputSchema", {})),
                        perm_key="shell_commands",
                        handler=lambda args, _s=s, _t=t: mcp.call_tool(_s, _t["name"], args),
                        enabled=True,
                        is_mcp=True,
                        mcp_server_id=sid,
                    )
                    self._tools[t_name] = spec
        except Exception:
            pass

    def register(self, tool: ToolSpec) -> ToolSpec:
        """Registers a new tool."""
        with _REGISTRY_LOCK:
            self._tools[tool.name] = tool
            return tool

    def unregister(self, tool_name: str) -> bool:
        """Unregisters a tool."""
        with _REGISTRY_LOCK:
            if tool_name in self._tools:
                del self._tools[tool_name]
                return True
            return False

    def get(self, tool_name: str) -> Optional[ToolSpec]:
        """Look up tool by name."""
        with _REGISTRY_LOCK:
            return self._tools.get(tool_name)

    def list(self, category: Optional[str] = None, include_disabled: bool = True) -> List[ToolSpec]:
        """Lists registered tools."""
        with _REGISTRY_LOCK:
            tools = list(self._tools.values())
            if not include_disabled:
                tools = [t for t in tools if t.enabled and t.name not in self._disabled_tools]
            if category:
                tools = [t for t in tools if t.category == category]
            return tools

    def search(self, query: str = "", category: Optional[str] = None) -> List[ToolSpec]:
        """Searches tools by name or description."""
        q = (query or "").strip().lower()
        with _REGISTRY_LOCK:
            results = []
            for t in self.list(category=category, include_disabled=True):
                if q:
                    if q not in t.name.lower() and q not in t.description.lower() and q not in t.category.lower():
                        continue
                results.append(t)
            return results

    def enable(self, tool_name: str) -> bool:
        with _REGISTRY_LOCK:
            t = self.get(tool_name)
            if t:
                t.enabled = True
                self._disabled_tools.discard(tool_name)
                return True
            return False

    def disable(self, tool_name: str) -> bool:
        with _REGISTRY_LOCK:
            t = self.get(tool_name)
            if t:
                t.enabled = False
                self._disabled_tools.add(tool_name)
                return True
            return False

    def get_tools_for_agent(self, agent: Any) -> Dict[str, ToolSpec]:
        """Filters available tools according to an Agent's declared tools and permissions."""
        with _REGISTRY_LOCK:
            declared = getattr(agent, "tools", []) or []
            perms = getattr(agent, "permissions", {}) or {}

            out: Dict[str, ToolSpec] = {}
            for name, spec in self._tools.items():
                if not spec.enabled or name in self._disabled_tools:
                    continue

                # If the agent specified a non-empty tool list, filter to it
                if declared and name not in declared:
                    continue

                # Check agent permissions
                if spec.perm_key:
                    if spec.perm_key in perms and not perms[spec.perm_key]:
                        continue
                    if perms.get("level") == "restricted" and spec.perm_key in ("delete_files", "shell_commands") and not perms.get(spec.perm_key):
                        continue

                out[name] = spec
            return out


def get_tool_registry() -> ToolRegistry:
    """Returns singleton ToolRegistry."""
    global _TOOL_INSTANCE
    if _TOOL_INSTANCE is None:
        with _REGISTRY_LOCK:
            if _TOOL_INSTANCE is None:
                _TOOL_INSTANCE = ToolRegistry()
    return _TOOL_INSTANCE
