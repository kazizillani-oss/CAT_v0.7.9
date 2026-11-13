"""
Patch commands_data.py with Engineering Excellence upgrade commands.
"""

with open('calc_terminal/commands_data.py', 'r', encoding='utf-8') as f:
    text = f.read()

new_commands_block = '''    # --- v1.0.0 Engineering Excellence & Platform Maturity Upgrade ---
    ("/dev", "Open CAT Developer SDK Studio (scaffold, validate, test, package)"),
    ("/dev init", "Initialize new developer component project"),
    ("/dev extension create", "Scaffold a new CAT extension project"),
    ("/dev skill create", "Scaffold a new agent skill definition"),
    ("/dev command create", "Scaffold a new custom slash command module"),
    ("/dev agent create", "Scaffold a new custom Kitty AI persona"),
    ("/dev validate", "Validate component manifest, entrypoints, and syntax"),
    ("/dev test", "Run dry-run test harness on component"),
    ("/dev package", "Bundle component into distributable .catpkg archive"),
    ("/dev docs", "Generate Markdown API documentation for component"),
    ("/dev logs", "Display recent developer SDK activity logs"),
    ("/recovery", "Open Recovery & Rollback Engine status and history"),
    ("/recovery status", "Display recovery engine snapshot counts and active transactions"),
    ("/recovery history", "List recent project modification snapshots"),
    ("/recovery preview", "Preview unified diff of a rollback operation"),
    ("/recovery restore", "Restore project files from an operation snapshot"),
    ("/recovery file", "Selectively restore a single file from a snapshot"),
    ("/recovery operation", "Rollback an entire multi-file operation"),
    ("/undo", "Undo the most recent file modification snapshot"),
    ("/redo", "Redo the previously undone operation snapshot"),
    ("/rollback", "Rollback workspace to a specified checkpoint"),
    ("/context", "Open Centralized Context Engine dashboard"),
    ("/context status", "Display context token usage across all 7 categories"),
    ("/context inspect", "Inspect context slices for a specific category"),
    ("/context search", "Semantic & keyword search across active context"),
    ("/context summarize", "Summarize older conversation history into compact bullets"),
    ("/context compress", "Compress context slices to reduce token consumption"),
    ("/context budget", "Display token budget limits and reservations for current model"),
    ("/context sources", "List source references contributing to current context"),
    ("/context clear", "Clear active context slices for a category"),
    ("/observe", "Open Observability Center (health, traces, metrics, logs)"),
    ("/observe health", "Display overall CAT application health status"),
    ("/observe traces", "List recent distributed execution traces"),
    ("/observe metrics", "Display provider latencies, token consumption, and costs"),
    ("/observe errors", "Inspect recent tool, extension, and MCP errors"),
    ("/observe providers", "Display latency and health across all AI providers"),
    ("/observe agents", "Inspect active sub-agent traces and execution states"),
    ("/observe tools", "Display tool execution frequency and success rates"),
    ("/observe export", "Export telemetry, metrics, and structured logs to JSON"),
    ("/logs", "Search and view structured application logs"),
    ("/logs search", "Filter structured logs by keyword, level, or component"),
    ("/logs export", "Export structured logs to file with secret redaction"),
    ("/trace", "Inspect detailed span tree for a distributed execution trace"),
    ("/trace inspect", "Inspect details and attributes of a specific execution span"),
    ("/offline", "Display offline operating status and local capabilities"),
    ("/offline status", "Check real-time network connectivity and offline mode"),
    ("/offline enable", "Manually enable offline operating mode"),
    ("/offline disable", "Disable manual offline mode and restore auto-detection"),
    ("/offline capabilities", "List local tools and calculators available without internet"),
    ("/local", "Open Local AI management (Ollama detection and model testing)"),
    ("/local models", "List locally installed Ollama models with parameter sizes"),
    ("/local providers", "Inspect local AI runtime status and daemon health"),
    ("/local status", "Check local Ollama service connectivity"),
    ("/local test", "Execute benchmark test against a local model"),
    ("/update check", "Check for newer CAT releases on configured channel"),
    ("/update preview", "Preview release notes and breaking changes for an update"),
    ("/update install", "Safely install an update with pre-update snapshot"),
    ("/update history", "View history of applied updates and checkpoints"),
    ("/update rollback", "Rollback to version snapshot taken before last update"),
    ("/update channel", "Switch release channel (stable, beta, dev)"),
    ("/update verify", "Verify SHA-256 integrity of release package"),
    ("/workspaces", "Open Multi-Workspace Manager (list and switch projects)"),
    ("/workspace create", "Create a new project workspace from template"),
    ("/workspace switch", "Switch active project workspace and context"),
    ("/workspace clone", "Clone an existing workspace to a new directory"),
    ("/workspace archive", "Archive a workspace from active view"),
    ("/workspace delete", "Remove a workspace profile from registry"),
    ("/workspace export", "Export complete workspace configuration to ZIP"),
    ("/workspace import", "Import workspace profile from bundle"),
    ("/workspace status", "Display active workspace path, git branch, and languages"),
    ("/workspace health", "Run diagnostics on active workspace project health"),
    ("/docs search", "Search documentation across user and developer guides"),
    ("/docs topics", "List all documentation topic guides"),
    ("/docs tutorial", "Display step-by-step interactive tutorial tracks"),
    ("/docs api", "View Developer SDK public API reference"),
    ("/docs developer", "Open Developer SDK guide and extension manual"),
    ("/docs update", "Verify live command documentation coverage"),
    ("/learn", "Open CAT Interactive Learning Center"),
    ("/learn basics", "Interactive tutorial: Core CAT concepts and shortcuts"),
    ("/learn extensions", "Interactive tutorial: Authoring CAT extensions"),
    ("/learn agents", "Interactive tutorial: Autonomous Kitties and handoffs"),
    ("/learn mcp", "Interactive tutorial: Model Context Protocol tools"),
    ("/learn commands", "Interactive tutorial: Essential slash commands reference"),
]'''

# Replace closing brackets
if '("/integrations", "Alias for /apps — manage third-party SaaS connectors"),\n]' in text:
    text = text.replace('("/integrations", "Alias for /apps — manage third-party SaaS connectors"),\n]', new_commands_block)
elif '("/integrations", "Alias for /apps \u2014 manage third-party SaaS connectors"),\n]' in text:
    text = text.replace('("/integrations", "Alias for /apps \u2014 manage third-party SaaS connectors"),\n]', new_commands_block)
else:
    # Find last occurrence of ] before NATIVE_UI_COMMANDS
    idx = text.rfind(']', 0, text.find('NATIVE_UI_COMMANDS'))
    if idx != -1:
        text = text[:idx] + new_commands_block + text[idx+1:]

# Add new native commands to NATIVE_UI_COMMANDS
new_natives = {
    "/dev", "/recovery", "/undo", "/redo", "/rollback",
    "/context", "/observe", "/logs", "/trace",
    "/offline", "/local", "/update", "/workspaces", "/learn",
}

for cmd in new_natives:
    if f'"{cmd}"' not in text:
        text = text.replace('NATIVE_UI_COMMANDS = {', f'NATIVE_UI_COMMANDS = {{\n    "{cmd}",')

with open('calc_terminal/commands_data.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("SUCCESS: Updated commands_data.py")

