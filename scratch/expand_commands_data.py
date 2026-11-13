NEW_COMMANDS = [
    # Dev & Workspace
    ("/files", "List workspace files with sizes and modification times"),
    ("/tree", "Render interactive directory tree of workspace"),
    ("/search", "Search file contents across workspace"),
    ("/grep", "Regex search across workspace files"),
    ("/replace", "Search and replace string across workspace files"),
    ("/rename", "Rename a file or directory"),
    ("/new", "Create a new file or directory"),
    ("/diff", "Show git diff or workspace changes"),
    ("/git", "Execute git commands directly in workspace"),
    ("/test", "Run workspace test suite (pytest/unittest)"),
    ("/lint", "Run lint checks across workspace code"),
    ("/format", "Format workspace code using black/ruff"),
    ("/typecheck", "Run type checker (mypy/pyright)"),
    ("/run", "Execute Python script or shell command"),
    # Office & Productivity
    ("/word", "Generate, inspect, and convert Word documents"),
    ("/excel", "Create and analyze spreadsheets and CSVs"),
    ("/sheets", "Alias for /excel spreadsheet manager"),
    ("/slides", "Author presentation slide decks (Marp/PPTX)"),
    ("/presentation", "Alias for /slides presentation deck creator"),
    ("/design", "Generate UI mockups, 3D cards, and banners"),
    ("/pdf", "PDF file inspection and text extraction"),
    ("/office", "Office productivity suite overview & status"),
    # Package, Python & Node
    ("/pkg", "Multi-ecosystem package manager (pip, npm, bun)"),
    ("/py", "Python environment inspector and runner"),
    ("/node", "Node.js and npm runtime manager"),
    # Skills & MCP
    ("/skill", "Kitty skills discovery, GitHub install, update & remove"),
    ("/mcp", "MCP server connections, tools inspection & testing"),
]

with open("calc_terminal/commands_data.py", "r", encoding="utf-8") as f:
    content = f.read()

import re
# Find COMMANDS = [ ... ]
pattern = r"COMMANDS\s*=\s*\[(.*?)\]"
m = re.search(pattern, content, re.DOTALL)
if m:
    existing_cmds = set(re.findall(r'\("([^"]+)"', m.group(1)))
    additions = []
    for cmd, desc in NEW_COMMANDS:
        if cmd not in existing_cmds:
            additions.append(f'    ("{cmd}", "{desc}"),')
    if additions:
        insert_text = "\n" + "\n".join(additions) + "\n]"
        new_content = content[:m.end()-1] + insert_text + content[m.end():]
        with open("calc_terminal/commands_data.py", "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"SUCCESS: Added {len(additions)} commands to commands_data.py")
    else:
        print("All commands already present in commands_data.py")
else:
    print("ERROR: COMMANDS list not found")

