with open("calc_terminal/ui/extensions_panel.py", "r", encoding="utf-8") as f:
    text = f.read()

target = """                with Vertical(id="ext-search"):
                    yield Input(placeholder="Search extensions, skills, commands...", id="ext-search-input")

                yield Static("", id="ext-error")"""

replacement = """                with Vertical(id="ext-search"):
                    yield Input(placeholder="Search extensions, skills, commands...", id="ext-search-input")
                with Horizontal(id="ext-filters"):
                    yield Button("All", id="filter-all", classes="ext-filter-btn active")
                    yield Button("Installed", id="filter-installed", classes="ext-filter-btn")
                    yield Button("Updates", id="filter-updates", classes="ext-filter-btn")
                    yield Button("MCP Servers", id="filter-mcp", classes="ext-filter-btn")
                yield Static("", id="ext-error")"""

if target in text:
    text = text.replace(target, replacement, 1)
else:
    target_crlf = target.replace("\n", "\r\n")
    replacement_crlf = replacement.replace("\n", "\r\n")
    text = text.replace(target_crlf, replacement_crlf, 1)

with open("calc_terminal/ui/extensions_panel.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Restored clean modern tabs (All, Installed, Updates, MCP Servers) in extensions_panel.py!")

