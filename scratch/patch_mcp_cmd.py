mcp_cmd_func = '''

def cmd_mcp(arg: str) -> str:
    """Handles /mcp slash command operations."""
    parts = arg.strip().split(None, 1)
    sub = parts[0].lower() if parts else "list"
    rest = parts[1].strip() if len(parts) > 1 else ""

    if sub in ("help", "--help", "-h"):
        return (
            "🔌 **Model Context Protocol (MCP) Server Commands:**\\n"
            "- `/mcp list` — List configured MCP servers and connection status\\n"
            "- `/mcp tools <server>` — Inspect tools provided by an MCP server\\n"
            "- `/mcp connect <server>` — Connect to a configured MCP server\\n"
            "- `/mcp disconnect <server>` — Disconnect from an MCP server\\n"
            "- `/mcp test <server>` — Test latency and connection to an MCP server"
        )

    servers = load_servers()

    if sub in ("list", "ls"):
        if not servers:
            return "ℹ️ No MCP servers configured. Open Main Menu → MCP Servers to add one."
        lines = [
            f"🔌 **Configured MCP Servers ({len(servers)} total):**\\n",
            "| ID | Name | Transport | Status | Tools |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
        for s in servers:
            st = server_status(s)
            status_glyph = "🟢 Connected" if st["status"] == "connected" else ("🟡 Connecting" if st["status"] == "connecting" else "🔴 Offline")
            tools_cnt = len(st["tools"])
            kind = s.get("kind", "stdio")
            name = s.get("name") or s.get("id")
            lines.append(f"| `{s.get('id')}` | {name} | {kind} | {status_glyph} | {tools_cnt} tools |")
        return "\\n".join(lines)

    if sub == "tools":
        if not rest:
            return "Usage: `/mcp tools <server_id_or_name>`"
        target = None
        for s in servers:
            if s.get("id") == rest or s.get("name", "").lower() == rest.lower():
                target = s
                break
        if not target:
            return f"❌ Server `{rest}` not found."
        st = server_status(target)
        tools = st.get("tools") or []
        if not tools:
            return f"ℹ️ No tools exposed by server `{rest}` (server may be offline)."
        lines = [f"🔌 **Tools exposed by `{target.get('name')}`:**\\n"]
        for t in tools:
            lines.append(f"- **`{t.get('name')}`**: {t.get('description', 'No description')}")
        return "\\n".join(lines)

    if sub == "connect":
        if not rest:
            return "Usage: `/mcp connect <server_id_or_name>`"
        target = None
        for s in servers:
            if s.get("id") == rest or s.get("name", "").lower() == rest.lower():
                target = s
                break
        if not target:
            return f"❌ Server `{rest}` not found."
        ok, msg = connect_server(target)
        if ok:
            return f"✅ **Connected to MCP Server:** `{target.get('name')}`"
        else:
            return f"❌ Connection failed: {msg}"

    if sub == "disconnect":
        if not rest:
            return "Usage: `/mcp disconnect <server_id_or_name>`"
        target = None
        for s in servers:
            if s.get("id") == rest or s.get("name", "").lower() == rest.lower():
                target = s
                break
        if not target:
            return f"❌ Server `{rest}` not found."
        disconnect_server(target.get("id"))
        return f"🔌 Disconnected from `{target.get('name')}`."

    if sub == "test":
        if not rest:
            return "Usage: `/mcp test <server_id>`"
        target = None
        for s in servers:
            if s.get("id") == rest or s.get("name", "").lower() == rest.lower():
                target = s
                break
        if not target:
            return f"❌ Server `{rest}` not found."
        ok, msg = connect_server(target)
        st = server_status(target)
        lat = st.get("latency_ms")
        lat_txt = f"{lat}ms" if lat is not None else "N/A"
        if ok:
            return f"✅ **MCP Server Test Passed:** `{target.get('name')}` (latency: {lat_txt})"
        else:
            return f"❌ Connection test failed: {msg}"

    return f"Unknown mcp subcommand `{sub}`. Type `/mcp help` for available options."
'''

with open("calc_terminal/mcp.py", "r", encoding="utf-8") as f:
    content = f.read()

if "def cmd_mcp(" not in content:
    content += "\n" + mcp_cmd_func
    with open("calc_terminal/mcp.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("SUCCESS: cmd_mcp added to calc_terminal/mcp.py")
else:
    print("cmd_mcp already present")

