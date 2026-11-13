with open("calc_terminal/agent.py", "r", encoding="utf-8") as f:
    content = f.read()

target = "TOOLS = {"
insertion = """def _tool_install_skill(args):
    \"\"\"Installs a skill or component from GitHub, catalogue, or URL.\"\"\"
    target = str(args.get("target") or args.get("repo") or args.get("skill") or "").strip()
    if not target:
        return "No skill or repository given. Pass {\\"target\\": \\"owner/repo\\" or \\"skill_slug\\"}."
    try:
        from . import extension_installer
        insp = extension_installer.inspect_repository(target)
        if not insp.valid:
            return f"Validation failed for '{target}': {insp.error}"
        from . import extensions as ext_mgr
        ok, msg = ext_mgr.install_from_github(target)
        if ok:
            return f"Successfully installed and registered skill/component: '{insp.name}' (v{insp.version})."
        else:
            return f"Skill installation failed: {msg}"
    except Exception as e:
        return f"Error installing skill '{target}': {e}"


def _tool_manage_skills(args):
    \"\"\"Lists, inspects, or manages Kitty skills.\"\"\"
    action = str(args.get("action") or "list").lower()
    from .skills.registry import get_skill_registry
    reg = get_skill_registry()
    if action == "list":
        skills = reg.list_skills()
        return "\\n".join(f"- {s.name} ({s.id} v{s.version}): {s.description}" for s in skills)
    elif action == "info":
        sid = str(args.get("skill_id") or "")
        s = reg.get_skill(sid)
        if not s:
            return f"Skill '{sid}' not found."
        return f"{s.name} ({s.id} v{s.version}):\\n{s.description}\\nTools: {getattr(s, 'tool_requirements', [])}"
    return f"Unknown action: {action}"


"""

tool_entries = """    "install_skill": {
        "run": _tool_install_skill,
        "desc": "Install a Kitty skill, agent capability, or extension from GitHub or the component catalogue.",
        "args": '{"target": "owner/repo or skill_slug"}',
        "perm_key": "install_packages",
        "describe": lambda a: ("Install Skill", str(a.get("target", "")), "Install skill from repository"),
    },
    "manage_skills": {
        "run": _tool_manage_skills,
        "desc": "List, inspect, and query registered Kitty skills and agent capabilities.",
        "args": '{"action": "list"}',
        "describe": lambda a: ("Manage Skills", str(a.get("action", "list")), ""),
    },
"""

content_norm = content.replace("\r\n", "\n")
if "def _tool_install_skill" not in content_norm:
    idx = content_norm.find(target)
    assert idx != -1, "TOOLS = not found"
    content_norm = content_norm[:idx] + insertion + target + "\n" + tool_entries + content_norm[idx + len(target):]
    if "\r\n" in content:
        content_norm = content_norm.replace("\n", "\r\n")
    with open("calc_terminal/agent.py", "w", encoding="utf-8") as f:
        f.write(content_norm)
    print("SUCCESS: Skill tools added to calc_terminal/agent.py")
else:
    print("Skill tools already present in calc_terminal/agent.py")

