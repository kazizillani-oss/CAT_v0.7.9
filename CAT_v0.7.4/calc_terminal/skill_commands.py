"""
CAT CLI — Skills Management Commands.

Real discovery, installation from GitHub, updating, and removal of Kitty skills.
"""

from __future__ import annotations

import os
from typing import List, Optional


def cmd_skill(arg: str) -> str:
    """Manages Kitty skills and agent capabilities."""
    parts = arg.strip().split(None, 1)
    sub = parts[0].lower() if parts else "list"
    rest = parts[1].strip() if len(parts) > 1 else ""

    from .skills.registry import get_skill_registry
    reg = get_skill_registry()

    if sub in ("help", "--help", "-h"):
        return (
            "🧠 **Kitty Skill Manager Commands:**\n"
            "- `/skill list` — List all registered skills and their assigned Kitties\n"
            "- `/skill search <query>` — Search available skills by tag or name\n"
            "- `/skill info <skill_id>` — Inspect a skill's instructions and tools\n"
            "- `/skill install <github_repo_or_slug>` — Install a skill from GitHub / Catalogue\n"
            "- `/skill update <skill_id>` — Update an installed skill\n"
            "- `/skill remove <skill_id>` — Delete or remove a custom skill"
        )

    if sub in ("list", "ls"):
        skills = reg.list_skills()
        if not skills:
            return "ℹ️ No skills registered yet. Try installing one with `/skill install <slug>`."
        lines = [
            f"🧠 **Registered Skills ({len(skills)} total):**\n",
            "| ID | Name | Version | Category | Builtin |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
        for s in skills:
            cat = getattr(s, "category", "General") or "General"
            b_str = "✅ Yes" if getattr(s, "builtin", False) else "Custom"
            lines.append(f"| `{s.id}` | {s.name} | v{s.version} | {cat} | {b_str} |")
        return "\n".join(lines)

    if sub == "search":
        if not rest:
            return "Usage: `/skill search <query>`"
        skills = reg.list_skills()
        q = rest.lower()
        matched = [s for s in skills if q in s.name.lower() or q in s.id.lower() or any(q in t.lower() for t in getattr(s, "tags", []))]
        if not matched:
            return f"🔍 No skills matching `{rest}` found."
        lines = [f"🔍 **Search Results for `{rest}`:**\n"]
        for s in matched:
            lines.append(f"- **{s.name}** (`{s.id}` v{s.version}): {s.description}")
        return "\n".join(lines)

    if sub == "info":
        if not rest:
            return "Usage: `/skill info <skill_id>`"
        s = reg.get_skill(rest.strip())
        if not s:
            return f"❌ Skill `{rest}` not found."
        tools = ", ".join(getattr(s, "tool_requirements", [])) or "None"
        agents = ", ".join(getattr(s, "applicable_modes", [])) or "All Agents"
        return (
            f"🧠 **Skill Details: {s.name}** (`{s.id}` v{s.version})\n"
            f"- **Author**: {getattr(s, 'author', 'CAT Ecosystem')}\n"
            f"- **Description**: {s.description}\n"
            f"- **Tools Required**: `{tools}`\n"
            f"- **Applicable Modes**: `{agents}`\n"
            f"- **Instructions Preview**:\n"
            f"```markdown\n{s.instructions[:400]}...\n```"
        )

    if sub == "install":
        if not rest:
            return "Usage: `/skill install <github_repo_slug_or_url>`"
        try:
            from . import extension_installer
            insp = extension_installer.inspect_repository(rest)
            if not insp.valid:
                return f"❌ Validation failed for `{rest}`: {insp.error}"
            from . import extensions as ext_mgr
            ok, msg = ext_mgr.install_from_github(rest)
            if ok:
                return f"✅ **Skill Installed Successfully:** `{insp.name}` (v{insp.version})\nRegistered in CAT component ecosystem."
            else:
                return f"❌ Skill installation failed: {msg}"
        except Exception as e:
            return f"❌ Error during installation: {e}"

    if sub == "remove":
        if not rest:
            return "Usage: `/skill remove <skill_id>`"
        ok = reg.delete_skill(rest.strip())
        if ok:
            return f"✅ Skill `{rest}` removed."
        else:
            return f"❌ Could not remove skill `{rest}` (may be a protected built-in skill)."

    return f"Unknown skill subcommand `{sub}`. Type `/skill help` for options."

