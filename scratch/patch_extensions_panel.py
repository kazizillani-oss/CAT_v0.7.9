with open("calc_terminal/ui/extensions_panel.py", "r", encoding="utf-8") as f:
    content = f.read()

content_norm = content.replace("\r\n", "\n")

# 1. Update CSS
t_css = """        .ext-card { height: auto; min-height: 6; padding: 1 2; border: tall $border; background: $surface; margin: 0 0 1 0; layout: horizontal; overflow: hidden; }
        .ext-card:hover { border: tall $accent; }
        .ext-card.ext-busy { background: $surface; border: tall $accent; }
        .ext-card-icon { width: 6; height: auto; text-align: center; text-style: bold; content-align: center middle; background: $accent 8%; border: tall $border; margin-right: 1; padding: 1 0; }
        .ext-icon { width: 100%; height: 1; text-align: center; content-align: center middle; }
        .ext-loading { width: 6; height: 3; color: $accent; content-align: center middle; }
        .ext-card-info { width: 1fr; height: auto; min-width: 16; }
        .ext-title-row { height: 1; layout: horizontal; }
        .ext-name { width: auto; height: 1; text-style: bold; margin-right: 1; color: $text; }
        .ext-type-badge { width: auto; height: 1; color: $accent; text-style: bold; margin-right: 1; }
        .ext-verified { width: auto; height: 1; color: $success; }
        .ext-trusted { width: auto; height: 1; color: $success; margin-left: 1; }
        .ext-desc { width: 100%; height: auto; color: $text-muted; max-height: 2; overflow: hidden; }
        .ext-meta { width: 100%; height: 1; color: $text-muted; }
        .ext-status { width: 100%; height: 1; }
        .ext-busy { color: $accent; }
        .ext-busy-label { color: $warning; text-style: bold; }
        .ext-card-actions { width: auto; min-width: 28; height: auto; layout: horizontal; align: center middle; }
        .ext-card-actions Button { min-width: 12; height: 3; min-height: 3; padding: 0 1; margin-left: 1; }"""

r_css = """        .ext-card { height: auto; min-height: 6; padding: 1 2; border: round $border; background: $surface; margin: 0 0 1 0; layout: horizontal; align-vertical: middle; overflow: hidden; transition: border 120ms, background 120ms; }
        .ext-card:hover { border: round $accent; }
        .ext-card.ext-busy { background: $surface; border: round $accent; }
        .ext-card-icon { width: 6; min-width: 6; height: 4; text-align: center; text-style: bold; content-align: center middle; background: $surface-alt; border: round $border; margin-right: 2; padding: 0; }
        .ext-icon { width: 100%; height: 100%; text-align: center; content-align: center middle; }
        .ext-loading { width: 6; height: 3; color: $accent; content-align: center middle; }
        .ext-card-info { width: 1fr; height: auto; min-width: 16; }
        .ext-title-row { height: 1; layout: horizontal; }
        .ext-name { width: auto; height: 1; text-style: bold; margin-right: 1; color: $text; }
        .ext-type-badge { width: auto; height: 1; color: $accent; text-style: bold; margin-right: 1; }
        .ext-verified { width: auto; height: 1; color: #5af78e; text-style: bold; }
        .ext-trusted { width: auto; height: 1; color: #5af78e; text-style: bold; margin-left: 1; }
        .ext-desc { width: 100%; height: auto; color: $text-muted; max-height: 2; overflow: hidden; }
        .ext-meta { width: 100%; height: 1; color: $text-muted; }
        .ext-status { width: 100%; height: 1; }
        .ext-busy { color: $accent; }
        .ext-busy-label { color: $warning; text-style: bold; }
        .ext-card-actions { width: auto; min-width: 16; height: auto; layout: horizontal; align: right middle; }
        .ext-card-actions Button { min-width: 12; height: 3; min-height: 3; padding: 0 1; margin-left: 1; border: round $accent; background: $surface; color: $text; }
        .ext-card-actions Button:hover { background: $surface-alt; color: #ffffff; border: round $accent-lighten-2; }"""

if t_css in content_norm:
    content_norm = content_norm.replace(t_css, r_css, 1)

# 2. Update filter tabs to include all 8 categories
t_filters = """                with Horizontal(id="ext-filters"):
                    yield Button("All", id="filter-all", classes="ext-filter-btn active")
                    yield Button("Extensions", id="filter-extension", classes="ext-filter-btn")
                    yield Button("Skills", id="filter-skill", classes="ext-filter-btn")
                    yield Button("Commands", id="filter-command", classes="ext-filter-btn")
                    yield Button("Integrations", id="filter-integration", classes="ext-filter-btn")"""

r_filters = """                with Horizontal(id="ext-filters"):
                    yield Button("All", id="filter-all", classes="ext-filter-btn active")
                    yield Button("Extensions", id="filter-extension", classes="ext-filter-btn")
                    yield Button("Skills", id="filter-skill", classes="ext-filter-btn")
                    yield Button("Commands", id="filter-command", classes="ext-filter-btn")
                    yield Button("Integrations", id="filter-integration", classes="ext-filter-btn")
                    yield Button("MCP", id="filter-mcp", classes="ext-filter-btn")
                    yield Button("Installed", id="filter-installed", classes="ext-filter-btn")
                    yield Button("Updates", id="filter-updates", classes="ext-filter-btn")"""

if t_filters in content_norm:
    content_norm = content_norm.replace(t_filters, r_filters, 1)

# 3. Update footer actions row to have exactly the 4 buttons from Image 8
t_actions = """                with Horizontal(id="ext-actions"):
                    with Horizontal(id="ext-actions-left"):
                        yield Button("↓ GitHub Install", id="ext-gh-install-btn", classes="cct-btn-sm")
                        yield Button("＋ Create Extension", id="ext-create-btn", classes="cct-btn-sm")
                        yield Button("Enable All", id="ext-enable-all", classes="cct-btn-sm")
                        yield Button("Disable All", id="ext-disable-all", classes="cct-btn-sm")
                    yield Button("Close", id="ext-close2", variant="primary", classes="cct-btn-sm")"""

r_actions = """                with Horizontal(id="ext-actions"):
                    with Horizontal(id="ext-actions-left"):
                        yield Button("↓ GitHub Install", id="ext-gh-install-btn", classes="cct-btn-sm")
                        yield Button("＋ Create Extension", id="ext-create-btn", classes="cct-btn-sm")
                        yield Button("Enable All", id="ext-enable-all", classes="cct-btn-sm")
                    yield Button("Close", id="ext-close2", variant="primary", classes="cct-btn-sm")"""

if t_actions in content_norm:
    content_norm = content_norm.replace(t_actions, r_actions, 1)

# 4. Update _filtered() logic for installed, updates, and mcp filters
t_filt_func = """                ftype = None if self._current_filter == "all" else self._current_filter
                all_exts = ext_mgr.list_extensions(component_type=ftype) if ext_mgr else []"""

r_filt_func = """                ftype = None if self._current_filter in ("all", "installed", "updates", "mcp") else self._current_filter
                all_exts = ext_mgr.list_extensions(component_type=ftype) if ext_mgr else []
                if self._current_filter == "installed":
                    all_exts = [e for e in all_exts if e.get("installed")]
                elif self._current_filter == "updates":
                    all_exts = [e for e in all_exts if e.get("has_update") or e.get("installed")]
                elif self._current_filter == "mcp":
                    all_exts = [e for e in all_exts if str(e.get("type", "")).lower() in ("mcp", "mcp_component")]"""

if t_filt_func in content_norm:
    content_norm = content_norm.replace(t_filt_func, r_filt_func, 1)

if "\r\n" in content:
    content_norm = content_norm.replace("\n", "\r\n")

with open("calc_terminal/ui/extensions_panel.py", "w", encoding="utf-8") as f:
    f.write(content_norm)

print("SUCCESS: calc_terminal/ui/extensions_panel.py patched")

