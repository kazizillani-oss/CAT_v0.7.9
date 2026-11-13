with open(r"calc_terminal/ui/extensions_panel.py", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Update CSS
css_target = """        CSS = \"\"\"
        ExtensionsPanel { align: center middle; background: $surface-darken-2 60%; }
        #ext-box {
            width: 86; max-width: 96%; height: auto; max-height: 80%;
            background: $surface; border: tall $border; padding: 0;
            layout: vertical; overflow: hidden;
        }
        #ext-titlebar { height: 5; min-height: 5; max-height: 5; padding: 0 2; border-bottom: solid $border; layout: horizontal; align: center middle; }
        #ext-title { width: 1fr; text-style: bold; color: $text; }
        #ext-search { height: 3; padding: 0 2; margin: 0; }
        #ext-search Input { width: 1fr; height: 3; border: tall $border; background: $surface; }
        #ext-search Input:focus { border: tall $accent; }
        #ext-filters { height: 3; min-height: 3; padding: 0 2; margin: 0 0 1 0; layout: horizontal; }
        .ext-filter-btn { height: 3; min-width: 11; margin-right: 1; padding: 0 1; }
        .ext-filter-btn.active { background: $accent; color: $surface; text-style: bold; }
        #ext-subtitle { color: $text-muted; height: 1; padding: 0 2; display: none; }
        #ext-list { height: 1fr; min-height: 4; max-height: 60%; overflow-y: auto; scrollbar-gutter: stable; scrollbar-size: 1 1; scrollbar-color: $border $surface; scrollbar-color-hover: $accent $surface; margin: 0 1; padding: 1 0 0 0; }
        .ext-card { height: auto; min-height: 6; padding: 1 2; border: round $border; background: $surface; margin: 0 0 1 0; layout: horizontal; align-vertical: middle; overflow: hidden; transition: border 120ms, background 120ms; }
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
        .ext-card-actions Button:hover { background: $surface-alt; color: #ffffff; border: round $accent-lighten-2; }
        .ext-card-actions Button:first-child { margin-left: 0; }
        .ext-card-actions Button:disabled { opacity: 0.7; }
        #ext-actions { height: 4; min-height: 4; padding: 0 2; border-top: solid $border; background: $surface; layout: horizontal; align: center middle; overflow: hidden; }
        #ext-actions-left { width: 1fr; height: auto; layout: horizontal; align: center middle; }
        #ext-actions-left Button { margin-right: 1; min-width: 11; height: 3; min-height: 3; padding: 0 1; }
        #ext-actions Button { min-width: 9; height: 3; min-height: 3; padding: 0 1; }
        #ext-error { color: $error; background: $surface; height: 1; padding: 0 2; display: none; }
        #ext-error.show { display: block; }
        .cct-compact #ext-box { width: 96; max-height: 88%; }
        .cct-compact #ext-titlebar { height: 5; min-height: 5; }
        .cct-compact #ext-list { min-height: 6; }
        .cct-compact .ext-card { layout: vertical; min-height: 7; }
        .cct-compact .ext-card-info { width: 100%; }
        .cct-compact .ext-card-actions { width: 100%; layout: horizontal; align: center middle; margin-top: 1; }
        .cct-compact .ext-card-actions Button { width: 1fr; min-width: 10; padding: 0 1; margin-top: 0; margin-right: 1; margin-left: 0; }
        .cct-compact .ext-card-actions Button:last-child { margin-right: 0; }
        .cct-compact #ext-actions { padding: 0 1; }
        \"\"\""""

css_replacement = """        CSS = \"\"\"
        ExtensionsPanel { align: center middle; background: rgba(0, 0, 0, 0.72); }
        #ext-box {
            width: 88; max-width: 96%; height: auto; max-height: 84%;
            background: $surface;
            border-top: solid #7a7f9a;
            border-left: solid #6c7086;
            border-bottom: solid #11111b;
            border-right: solid #181825;
            padding: 0;
            layout: vertical;
            overflow: hidden;
        }
        #ext-titlebar {
            height: 5; min-height: 5; max-height: 5;
            padding: 0 2;
            border-bottom: solid #313244;
            layout: horizontal;
            align: center middle;
            background: $surface-darken-1;
        }
        #ext-title { width: 1fr; text-style: bold; color: $text; }
        #ext-search { height: 3; padding: 0 2; margin: 1 0 0 0; }
        #ext-search Input {
            width: 1fr; height: 3;
            border-top: solid #11111b;
            border-left: solid #181825;
            border-bottom: solid #6c7086;
            border-right: solid #585b70;
            background: $surface-darken-2;
            color: $text;
        }
        #ext-search Input:focus { border: round $accent; }
        #ext-filters { height: 3; min-height: 3; padding: 0 2; margin: 1 0 1 0; layout: horizontal; }
        .ext-filter-btn {
            height: 3; min-width: 12; margin-right: 1; padding: 0 1;
            border-top: solid #6c7086;
            border-left: solid #585b70;
            border-bottom: solid #181825;
            border-right: solid #181825;
            background: $surface-alt;
            color: $text;
        }
        .ext-filter-btn:hover {
            border-top: solid $accent-lighten-2;
            border-left: solid $accent;
            border-bottom: solid $accent-darken-3;
            border-right: solid $accent-darken-2;
            color: #ffffff;
        }
        .ext-filter-btn.active {
            background: $accent;
            color: $surface-darken-2;
            border: round $accent;
            text-style: bold;
        }
        #ext-subtitle { color: $text-muted; height: 1; padding: 0 2; display: none; }
        #ext-list {
            height: 1fr; min-height: 4; max-height: 62%;
            overflow-y: auto; scrollbar-gutter: stable; scrollbar-size: 1 1;
            scrollbar-color: $border transparent;
            margin: 0 1; padding: 1 0 0 0;
        }
        .ext-card {
            height: auto; min-height: 6; padding: 1 2;
            border-top: solid #585b70;
            border-left: solid #45475a;
            border-bottom: solid #11111b;
            border-right: solid #181825;
            background: $surface;
            margin: 0 0 1 0;
            layout: horizontal;
            align-vertical: middle;
            overflow: hidden;
            transition: border 120ms, background 120ms;
        }
        .ext-card:hover {
            border-top: solid $accent-lighten-2;
            border-left: solid $accent;
            border-bottom: solid $accent-darken-3;
            border-right: solid $accent-darken-2;
            background: $surface-alt;
        }
        .ext-card.ext-busy { background: $surface; border: round $accent; }
        .ext-card-icon {
            width: 6; min-width: 6; height: 4; text-align: center; text-style: bold;
            content-align: center middle; background: $surface-darken-1;
            border-top: solid #585b70;
            border-left: solid #45475a;
            border-bottom: solid #11111b;
            border-right: solid #181825;
            margin-right: 2; padding: 0;
        }
        .ext-icon { width: 100%; height: 100%; text-align: center; content-align: center middle; }
        .ext-loading { width: 6; height: 3; color: $accent; content-align: center middle; }
        .ext-card-info { width: 1fr; height: auto; min-width: 16; }
        .ext-title-row { height: 1; layout: horizontal; }
        .ext-name { width: auto; height: 1; text-style: bold; margin-right: 2; color: $text; }
        .ext-type-badge { display: none; }
        .ext-verified { width: auto; height: 1; color: #5af78e; text-style: bold; }
        .ext-trusted { width: auto; height: 1; color: #5af78e; text-style: bold; margin-left: 1; }
        .ext-desc { width: 100%; height: auto; color: $text-muted; max-height: 2; overflow: hidden; margin-top: 0; }
        .ext-meta { width: 100%; height: 1; color: $text-muted; margin-top: 0; }
        .ext-status { display: none; }
        .ext-busy { color: $accent; }
        .ext-busy-label { color: $warning; text-style: bold; }
        .ext-card-actions { width: auto; min-width: 14; height: auto; layout: horizontal; align: right middle; }
        .ext-card-actions Button {
            min-width: 12; height: 3; min-height: 3; padding: 0 1; margin-left: 1;
            border-top: solid $accent-lighten-2;
            border-left: solid $accent;
            border-bottom: solid $accent-darken-3;
            border-right: solid $accent-darken-2;
            background: $surface;
            color: $accent;
            text-style: bold;
        }
        .ext-card-actions Button:hover {
            background: $accent;
            color: $surface-darken-2;
            border: round $accent;
        }
        .ext-card-actions Button:first-child { margin-left: 0; }
        .ext-card-actions Button:disabled { opacity: 0.7; }
        #ext-actions {
            height: 4; min-height: 4; padding: 0 2;
            border-top: solid #313244;
            background: $surface-darken-1;
            layout: horizontal;
            align: center middle;
            overflow: hidden;
        }
        #ext-actions-left { width: 1fr; height: auto; layout: horizontal; align: center middle; }
        #ext-actions-left Button, #ext-actions Button {
            margin-right: 1; min-width: 11; height: 3; min-height: 3; padding: 0 1;
            border-top: solid #6c7086;
            border-left: solid #585b70;
            border-bottom: solid #11111b;
            border-right: solid #181825;
            background: $surface-alt;
        }
        #ext-actions-left Button:hover, #ext-actions Button:hover {
            border-top: solid $accent-lighten-2;
            border-left: solid $accent;
            border-bottom: solid $accent-darken-3;
            border-right: solid $accent-darken-2;
        }
        #ext-error { color: $error; background: $surface; height: 1; padding: 0 2; display: none; }
        #ext-error.show { display: block; }
        .cct-compact #ext-box { width: 94%; max-height: 90%; }
        .cct-compact #ext-titlebar { height: 5; min-height: 5; }
        .cct-compact #ext-list { min-height: 6; }
        .cct-compact .ext-card { layout: vertical; min-height: 6; padding: 1; }
        .cct-compact .ext-card-icon { display: none; }
        .cct-compact .ext-card-info { width: 100%; }
        .cct-compact .ext-card-actions { width: 100%; layout: horizontal; align: right middle; margin-top: 1; }
        .cct-compact .ext-card-actions Button { width: auto; min-width: 10; padding: 0 1; margin: 0; }
        .cct-compact #ext-actions { padding: 0 1; }
        .cct-compact #ext-actions-left Button { min-width: 9; }
        \"\"\""""

# 2. Update Card info
card_target = """            # Center info
            with Vertical(classes="ext-card-info"):
                # Title row: name + type badge + verified + trusted
                with Horizontal(classes="ext-title-row"):
                    yield Static(name, classes="ext-name")
                    yield Static(f"[{ctype}]", classes="ext-type-badge")
                    if verified:
                        yield Static("✓ Verified", classes="ext-verified")
                    if trusted:
                        yield Static("Trusted", classes="ext-trusted")
                yield Static(desc, classes="ext-desc")
                # Meta row: creator, size, version, category, published date
                pub_meta = f"  ·  pub: {ext['published_at']}" if ext.get("published_at") else ""
                yield Static(f"{creator}  ·  {size}  ·  v{version}  ·  {category}{pub_meta}", classes="ext-meta")
                # Status row
                status_map = {
                    "NOT_INSTALLED": ("○ Not Installed", "text-faint"),
                    "INSTALLED_ENABLED": ("● Enabled", "success"),
                    "INSTALLED_DISABLED": ("○ Disabled", "warning"),
                    "INSTALLING": ("⟳ Installing…", "warning"),
                    "UNINSTALLING": ("⟳ Uninstalling…", "warning"),
                    "ENABLING": ("⟳ Enabling…", "warning"),
                    "DISABLING": ("⟳ Disabling…", "warning"),
                }
                status_text, tone = status_map.get(state, ("Unknown", "text-faint"))
                yield Static(f"[{_hex(tone)}]{status_text}[/]", classes="ext-status" + (" ext-busy-label" if busy else ""), markup=True)"""

card_replacement = """            # Center info
            with Vertical(classes="ext-card-info"):
                # Title row: name + verified trusted badge (Image 8 style)
                with Horizontal(classes="ext-title-row"):
                    yield Static(name, classes="ext-name")
                    if verified and trusted:
                        yield Static("✓ Verified Trusted", classes="ext-verified")
                    elif verified:
                        yield Static("✓ Verified", classes="ext-verified")
                    elif trusted:
                        yield Static("Trusted", classes="ext-trusted")
                yield Static(desc, classes="ext-desc")
                # Clean metadata matching Image 8: Creator • Size • Version • Status
                status_map = {
                    "NOT_INSTALLED": ("○ Not Installed", "text-faint"),
                    "INSTALLED_ENABLED": ("● Enabled", "success"),
                    "INSTALLED_DISABLED": ("○ Disabled", "warning"),
                    "INSTALLING": ("⟳ Installing…", "warning"),
                    "UNINSTALLING": ("⟳ Uninstalling…", "warning"),
                    "ENABLING": ("⟳ Enabling…", "warning"),
                    "DISABLING": ("⟳ Disabling…", "warning"),
                }
                status_text, tone = status_map.get(state, ("Unknown", "text-faint"))
                yield Static(f"{creator}  •  {size}  •  v{version}  •  [{_hex(tone)}]{status_text}[/]", classes="ext-meta", markup=True)"""

# 3. Update Filters in compose()
filter_target = """                with Horizontal(id="ext-filters"):
                    yield Button("All", id="filter-all", classes="ext-filter-btn active")
                    yield Button("Extensions", id="filter-extension", classes="ext-filter-btn")
                    yield Button("Skills", id="filter-skill", classes="ext-filter-btn")
                    yield Button("Commands", id="filter-command", classes="ext-filter-btn")
                    yield Button("Integrations", id="filter-integration", classes="ext-filter-btn")
                    yield Button("MCP", id="filter-mcp", classes="ext-filter-btn")
                    yield Button("Installed", id="filter-installed", classes="ext-filter-btn")
                    yield Button("Updates", id="filter-updates", classes="ext-filter-btn")"""

filter_replacement = """                with Horizontal(id="ext-filters"):
                    yield Button("All", id="filter-all", classes="ext-filter-btn active")
                    yield Button("Installed", id="filter-installed", classes="ext-filter-btn")
                    yield Button("Updates", id="filter-updates", classes="ext-filter-btn")
                    yield Button("MCP Servers", id="filter-mcp", classes="ext-filter-btn")"""

text_n = text.replace('\r\n', '\n')
css_target_n = css_target.replace('\r\n', '\n')
css_repl_n = css_replacement.replace('\r\n', '\n')
card_target_n = card_target.replace('\r\n', '\n')
card_repl_n = card_replacement.replace('\r\n', '\n')
filter_target_n = filter_target.replace('\r\n', '\n')
filter_repl_n = filter_replacement.replace('\r\n', '\n')

ok = True
if css_target_n in text_n:
    text_n = text_n.replace(css_target_n, css_repl_n)
    print("CSS replaced")
else:
    print("CSS target not found")
    ok = False

if card_target_n in text_n:
    text_n = text_n.replace(card_target_n, card_repl_n)
    print("Card replaced")
else:
    print("Card target not found")
    ok = False

if filter_target_n in text_n:
    text_n = text_n.replace(filter_target_n, filter_repl_n)
    print("Filters replaced")
else:
    print("Filters target not found")
    ok = False

if ok:
    with open(r"calc_terminal/ui/extensions_panel.py", "w", encoding="utf-8") as f:
        f.write(text_n)
    print("Successfully updated calc_terminal/ui/extensions_panel.py")

