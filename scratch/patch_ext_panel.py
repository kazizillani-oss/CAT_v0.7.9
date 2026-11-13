with open("calc_terminal/ui/extensions_panel.py", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Update close button in titlebar to "✕"
text = text.replace('yield Button("✕ Close", id="ext-close", classes="cct-modal-close-btn")', 'yield Button("✕", id="ext-close", classes="cct-modal-close-btn")')
text = text.replace('yield Button("✕ Close", id="gh-close", classes="cct-modal-close-btn")', 'yield Button("✕", id="gh-close", classes="cct-modal-close-btn")')
text = text.replace('yield Button("✕ Close", id="det-close", classes="cct-modal-close-btn")', 'yield Button("✕", id="det-close", classes="cct-modal-close-btn")')
text = text.replace('yield Button("✕ Close", id="create-close", classes="cct-modal-close-btn")', 'yield Button("✕", id="create-close", classes="cct-modal-close-btn")')

# 2. Remove the filter buttons row in compose
filters_block = """                with Horizontal(id="ext-filters"):
                    yield Button("All", id="filter-all", classes="ext-filter-btn active")
                    yield Button("Installed", id="filter-installed", classes="ext-filter-btn")
                    yield Button("Updates", id="filter-updates", classes="ext-filter-btn")
                    yield Button("MCP Servers", id="filter-mcp", classes="ext-filter-btn")"""

if filters_block in text:
    text = text.replace(filters_block, "")
    print("Removed filter buttons row from extensions_panel.py!")
else:
    # Try CRLF version
    filters_block_crlf = filters_block.replace("\n", "\r\n")
    if filters_block_crlf in text:
        text = text.replace(filters_block_crlf, "")
        print("Removed CRLF filter buttons row from extensions_panel.py!")

with open("calc_terminal/ui/extensions_panel.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Updated extensions_panel.py successfully!")

