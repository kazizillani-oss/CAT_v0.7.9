"""
CCT UI — ExtensionsPanel (VS Code-style).

Full VS Code-inspired marketplace and component manager for Gestures, Personalize,
Skills, Custom Commands, and Integrations.

Features:
- Categories/filters: All, Extensions, Skills, Commands, Integrations
- Search: name, creator, category, keywords
- Cards: icon, name, type badge, description, creator, verified, size, version,
  category, trusted, published date, Install/Enable/Disable/Uninstall
- Details page with rich metadata: Type, Original Published Date, Installed Date,
  Source URL, Permissions required, Dependencies, Compatibility, Check for Updates
- GitHub Installation Modal: inspect before installing, path traversal validation,
  instant subsystem registration
- Preserves Gestures & Personalize built-ins (Publisher: Kazi Zillani ✓ Verified)
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import time

TEXTUAL_AVAILABLE = True
try:
    from textual.screen import Screen
    from textual.containers import Vertical, Horizontal, VerticalScroll
    from textual.widgets import Static, Button, Input, LoadingIndicator
    from textual.binding import Binding
except Exception:
    TEXTUAL_AVAILABLE = False
    LoadingIndicator = None

if TEXTUAL_AVAILABLE:
    try:
        from .. import extensions as ext_mgr
    except Exception:
        ext_mgr = None
    try:
        from .. import extension_installer
    except Exception:
        extension_installer = None
    try:
        from . import theme_css
    except Exception:
        theme_css = None

    def _hex(role):
        try:
            return theme_css.current_hex(role) if theme_css else "#888"
        except Exception:
            return "#888"

    class _ExtCard(Horizontal):
        """VS Code-style card: icon | info | actions"""
        def __init__(self, ext):
            super().__init__(classes="ext-card")
            self.ext = ext
            self.ext_id = ext.get("id") or ext.get("key")

        def compose(self):
            ext = self.ext
            name = ext.get("display_name") or ext.get("name") or ext.get("id")
            desc = ext.get("description", "")
            icon = ext.get("icon", "▣")
            creator = ext.get("publisher") or ext.get("creator") or "Unknown"
            verified = bool(ext.get("publisher_verified") or ext.get("verified"))
            trusted = bool(ext.get("trusted"))
            version = ext.get("version", "1.0.0")
            category = ext.get("category", "General")
            size = ext.get("size_display") or ext.get("size", "?")
            ctype = str(ext.get("type", "ext")).upper()
            state = ext.get("state") or (
                "INSTALLED_ENABLED" if ext.get("enabled") and ext.get("installed")
                else "NOT_INSTALLED" if not ext.get("installed")
                else "INSTALLED_DISABLED"
            )
            if ext.get("installed") and ext.get("enabled"):
                state = "INSTALLED_ENABLED"
            elif ext.get("installed") and not ext.get("enabled"):
                state = "INSTALLED_DISABLED"
            elif not ext.get("installed"):
                state = "NOT_INSTALLED"

            busy = None
            try:
                busy = getattr(self.screen, "_busy", {}).get(self.ext_id)  # type: ignore
            except Exception:
                busy = None
            if busy:
                _busy_map = {
                    "install": "INSTALLING",
                    "uninstall": "UNINSTALLING",
                    "enable": "ENABLING",
                    "disable": "DISABLING",
                }
                state = _busy_map.get(busy, "INSTALLING")

            # Left icon
            with Vertical(classes="ext-card-icon"):
                if state in ("INSTALLING", "UNINSTALLING"):
                    if LoadingIndicator:
                        yield LoadingIndicator(classes="ext-loading")
                    else:
                        yield Static("⟳", classes="ext-icon ext-busy")
                else:
                    yield Static(icon, classes="ext-icon")

            # Center info
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
                yield Static(f"[{_hex(tone)}]{status_text}[/]", classes="ext-status" + (" ext-busy-label" if busy else ""), markup=True)

            # Right actions
            with Vertical(classes="ext-card-actions"):
                if busy:
                    if busy == "install":
                        yield Button("⟳ Installing…", id=f"ext-busy-{self.ext_id}", variant="primary", classes="cct-btn-sm", disabled=True)
                    elif busy == "uninstall":
                        yield Button("⟳ Removing…", id=f"ext-busy-{self.ext_id}", variant="error", classes="cct-btn-sm", disabled=True)
                    elif busy == "enable":
                        yield Button("⟳ Enabling…", id=f"ext-busy-{self.ext_id}", variant="primary", classes="cct-btn-sm", disabled=True)
                    elif busy == "disable":
                        yield Button("⟳ Disabling…", id=f"ext-busy-{self.ext_id}", classes="cct-btn-sm", disabled=True)
                    else:
                        yield Button("⟳ Working…", id=f"ext-busy-{self.ext_id}", disabled=True, classes="cct-btn-sm")
                else:
                    if state == "NOT_INSTALLED":
                        yield Button("Install", id=f"ext-install-{self.ext_id}", variant="primary", classes="cct-btn-sm")
                    elif state == "INSTALLED_DISABLED":
                        yield Button("Enable", id=f"ext-enable-{self.ext_id}", variant="primary", classes="cct-btn-sm")
                        yield Button("Uninstall", id=f"ext-uninstall-{self.ext_id}", variant="error", classes="cct-btn-sm")
                    elif state == "INSTALLED_ENABLED":
                        yield Button("Disable", id=f"ext-disable-{self.ext_id}", classes="cct-btn-sm")
                        yield Button("Uninstall", id=f"ext-uninstall-{self.ext_id}", variant="error", classes="cct-btn-sm")
                    else:
                        yield Button("Install", id=f"ext-install-{self.ext_id}", variant="primary", classes="cct-btn-sm")

        def on_click(self, event):
            if getattr(event, "widget", None) is self:
                try:
                    self.screen._open_details(self.ext_id)
                except Exception:
                    pass

    class _DetailsPanel(Screen):
        """Extension details page (VS Code style with rich metadata)."""
        CSS = """
        _DetailsPanel { align: center middle; background: $surface-darken-2 70%; }
        #det-box { width: 76; max-width: 96%; height: auto; max-height: 48; background: $surface; border: tall $border; padding: 0; layout: vertical; overflow: hidden; }
        #det-titlebar { height: 5; min-height: 5; max-height: 5; padding: 0 2; border-bottom: solid $border; layout: horizontal; align: center middle; }
        #det-title { width: 1fr; text-style: bold; }
        #det-body { height: 1fr; overflow-y: auto; padding: 1 2; }
        .det-icon { width: 100%; height: 3; text-align: center; text-style: bold; }
        .det-name { width: 100%; height: 1; text-style: bold; text-align: center; }
        .det-creator { width: 100%; height: 1; color: $text-muted; text-align: center; }
        .det-verified { width: 100%; height: 1; color: $success; text-align: center; }
        .det-meta { width: 100%; height: auto; color: $text-faint; text-align: center; padding: 1 0; }
        .det-desc { width: 100%; height: auto; color: $text; padding: 1 0; }
        .det-section { width: 100%; height: 1; color: $text-faint; text-style: bold; padding-top: 1; border-top: solid $border; margin-top: 1; }
        #det-actions { height: auto; padding: 1 2; border-top: solid $border; layout: horizontal; }
        #det-actions Button { margin-right: 1; }
        """

        def __init__(self, ext_id):
            super().__init__()
            self.ext_id = ext_id
            self.ext = ext_mgr.get_metadata(ext_id) if ext_mgr else None
            self._busy = None

        def compose(self):
            ext = self.ext or {}
            name = ext.get("display_name") or ext.get("name") or self.ext_id
            icon = ext.get("icon", "▣")
            desc = ext.get("description", "")
            creator = ext.get("publisher") or ext.get("creator") or "Unknown"
            verified = bool(ext.get("publisher_verified") or ext.get("verified"))
            trusted = bool(ext.get("trusted"))
            version = ext.get("version", "1.0.0")
            size = ext.get("size_display") or ext.get("size", "?")
            category = ext.get("category", "General")
            ctype = str(ext.get("type", "extension")).upper()
            state = ext.get("state") or "NOT_INSTALLED"
            if self._busy:
                state = {"install":"INSTALLING","uninstall":"UNINSTALLING","enable":"ENABLING","disable":"DISABLING"}.get(self._busy, state)

            with Vertical(id="det-box"):
                with Horizontal(id="det-titlebar"):
                    yield Static(f"{icon}  {name}  [{ctype}]", id="det-title")
                    yield Button("✕ Close", id="det-close", classes="cct-modal-close-btn")
                with VerticalScroll(id="det-body"):
                    if state in ("INSTALLING", "UNINSTALLING") and LoadingIndicator:
                        yield LoadingIndicator(classes="det-loading")
                    yield Static(icon, classes="det-icon")
                    yield Static(f"{name} ({self.ext_id})", classes="det-name")
                    yield Static(f"Type: {ctype}  ·  Category: {category}", classes="det-creator")
                    if verified:
                        yield Static("✓ Verified Publisher", classes="det-verified")
                    else:
                        yield Static("Community Extension", classes="det-creator")
                    if trusted:
                        yield Static("Trusted & Sandboxed", classes="det-verified")
                    yield Static(f"{size}  ·  v{version}", classes="det-meta")
                    yield Static(desc, classes="det-desc")

                    yield Static("Publisher & Attribution", classes="det-section")
                    pub_type = ext.get("publisher_type", "individual")
                    yield Static(f"Publisher: {creator} ({pub_type})", classes="det-desc")
                    if ext.get("published_at"):
                        yield Static(f"Original Publication: {ext['published_at']}", classes="det-desc")
                    if ext.get("install_time"):
                        t_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ext['install_time']))
                        yield Static(f"Installed on this Host: {t_str}", classes="det-desc")
                    yield Static(f"Source: {ext.get('install_source', 'local')}", classes="det-desc")

                    yield Static("Capabilities & Permissions", classes="det-section")
                    perms = ext.get("permissions", [])
                    yield Static(f"Permissions: {', '.join(perms) if perms else 'None (restricted sandbox)'}", classes="det-desc")

                    if ext.get("dependencies"):
                        yield Static("Dependencies", classes="det-section")
                        yield Static(f"Requires: {', '.join(ext['dependencies'])}", classes="det-desc")

                    yield Static("Compatibility", classes="det-section")
                    compat = ext.get("cat_compatibility", ">=0.7.0")
                    yield Static(f"CAT Version: {compat}", classes="det-desc")

                with Horizontal(id="det-actions"):
                    if self._busy:
                        yield Button("⟳ Working…", id="det-busy-btn", disabled=True)
                        yield Button("Close", id="det-close2", classes="cct-ctrl", disabled=True)
                    else:
                        if state == "NOT_INSTALLED":
                            yield Button("Install", id="det-install", variant="primary")
                        elif state == "INSTALLED_DISABLED":
                            yield Button("Enable", id="det-enable", variant="primary")
                            yield Button("Uninstall", id="det-uninstall", variant="error")
                        elif state == "INSTALLED_ENABLED":
                            yield Button("Disable", id="det-disable")
                            yield Button("Check Updates", id="det-update", classes="cct-ctrl")
                            yield Button("Uninstall", id="det-uninstall", variant="error")
                        yield Button("Close", id="det-close2", classes="cct-ctrl")

        def _finish_det(self, action: str):
            try:
                if action == "install" and ext_mgr:
                    ext_mgr.install(self.ext_id)
                    self.app._system_note(f"✓ {self.ext_id} installed")
                    self.dismiss("installed")
                elif action == "enable" and ext_mgr:
                    ext_mgr.enable(self.ext_id)
                    self.app._system_note(f"✓ {self.ext_id} enabled")
                    self.dismiss("enabled")
                elif action == "disable" and ext_mgr:
                    ext_mgr.disable(self.ext_id)
                    self.app._system_note(f"✓ {self.ext_id} disabled")
                    self.dismiss("disabled")
                elif action == "uninstall" and ext_mgr:
                    ok, msg = ext_mgr.uninstall(self.ext_id)
                    if ok:
                        self.app._system_note(f"✓ {self.ext_id} uninstalled")
                        self.dismiss("uninstalled")
                    else:
                        self.app._system_note(msg)
            except Exception:
                try:
                    self.dismiss(None)
                except Exception:
                    pass

        def on_button_pressed(self, event):
            bid = event.button.id
            if bid in ("det-close", "det-close2"):
                self.dismiss(None)
            elif bid == "det-install":
                self._busy = "install"
                self.set_timer(0.4, lambda: self._finish_det("install"))
            elif bid == "det-enable":
                self._busy = "enable"
                self.set_timer(0.3, lambda: self._finish_det("enable"))
            elif bid == "det-disable":
                self._busy = "disable"
                self.set_timer(0.3, lambda: self._finish_det("disable"))
            elif bid == "det-uninstall":
                self._busy = "uninstall"
                self.set_timer(0.4, lambda: self._finish_det("uninstall"))
            elif bid == "det-update":
                if ext_mgr:
                    has_up, cur_v, new_v, det = ext_mgr.check_for_updates(self.ext_id)
                    if has_up:
                        self.app._system_note(f"Update available: v{cur_v} -> v{new_v}")
                    else:
                        self.app._system_note(f"'{self.ext_id}' is already up to date (v{cur_v})")

        def on_key(self, event):
            if event.key == "escape":
                self.dismiss(None)

    class _InstallGitHubModal(Screen):
        """Modal dialog to inspect and install Skills and Extensions from GitHub or Catalogue."""
        CSS = """
        _InstallGitHubModal { align: center middle; background: rgba(0, 0, 0, 0.7); }
        #gh-box {
            width: 76; max-width: 96%; height: auto; max-height: 46;
            background: $surface; border: tall $border; padding: 0;
            layout: vertical; overflow: hidden;
        }
        #gh-titlebar { height: 5; min-height: 5; padding: 0 2; border-bottom: solid $border; layout: horizontal; align: center middle; }
        #gh-title { width: 1fr; text-style: bold; color: $text; }
        #gh-body { height: auto; padding: 1 2; layout: vertical; }
        .gh-label { width: 100%; height: 1; color: $text-muted; margin-top: 1; }
        .gh-label:first-child { margin-top: 0; }
        #input-gh-url { width: 100%; height: 3; border: tall $border; background: $surface; margin-bottom: 1; }
        #input-gh-url:focus { border: tall $accent; }
        #gh-cat-row { height: auto; layout: horizontal; margin-bottom: 1; }
        .gh-cat-btn { margin-right: 1; height: 3; min-width: 15; padding: 0 1; }
        #gh-preview { width: 100%; height: auto; min-height: 4; border: tall $border; background: $surface-darken-1; padding: 1; margin-top: 1; color: $text; }
        #gh-error { width: 100%; height: 1; color: $error; display: none; margin-top: 1; }
        #gh-error.show { display: block; }
        #gh-actions { height: 4; min-height: 4; padding: 0 2; border-top: solid $border; background: $surface; layout: horizontal; align: right middle; }
        #gh-actions Button { margin-left: 1; min-width: 14; height: 3; }
        """

        def __init__(self):
            super().__init__()
            self._inspected = None

        def compose(self):
            with Vertical(id="gh-box"):
                with Horizontal(id="gh-titlebar"):
                    yield Static("↓  Install from GitHub / Catalogue", id="gh-title")
                    yield Button("✕ Close", id="gh-close", classes="cct-modal-close-btn")
                with Vertical(id="gh-body"):
                    yield Static("GitHub Repository URL or Slug *", classes="gh-label")
                    yield Input(placeholder="e.g. owner/repo or https://github.com/owner/repo", id="input-gh-url")
                    yield Static("Or select from Curated Catalogue:", classes="gh-label")
                    with Horizontal(id="gh-cat-row"):
                        yield Button("🐙 GitHub Skill", id="pick-gh-skill", classes="gh-cat-btn")
                        yield Button("🌿 Git Flow", id="pick-git-flow", classes="gh-cat-btn")
                        yield Button("📚 arXiv Assistant", id="pick-arxiv", classes="gh-cat-btn")
                    yield Static("Inspection Summary: Enter repository URL and click 'Inspect Repository'", id="gh-preview")
                    yield Static("", id="gh-error")
                with Horizontal(id="gh-actions"):
                    yield Button("Cancel", id="gh-cancel")
                    yield Button("Inspect", id="gh-inspect-btn")
                    yield Button("Install Component", id="gh-submit", variant="primary", disabled=True)

        def on_button_pressed(self, event):
            bid = event.button.id or ""
            inp = self.query_one("#input-gh-url", Input)
            prev = self.query_one("#gh-preview", Static)
            err = self.query_one("#gh-error", Static)

            if bid in ("gh-close", "gh-cancel"):
                self.dismiss(None)
                return

            if bid == "pick-gh-skill":
                inp.value = "github-issue-investigator"
                self._do_inspect("github-issue-investigator")
                return

            if bid == "pick-git-flow":
                inp.value = "git-workflow-pro"
                self._do_inspect("git-workflow-pro")
                return

            if bid == "pick-arxiv":
                inp.value = "arxiv-researcher"
                self._do_inspect("arxiv-researcher")
                return

            if bid == "gh-inspect-btn":
                url = inp.value.strip()
                if not url:
                    err.update("Please enter a GitHub repository URL or slug.")
                    err.add_class("show")
                    return
                self._do_inspect(url)
                return

            if bid == "gh-submit":
                if not self._inspected:
                    return
                if ext_mgr:
                    ok, msg = ext_mgr.install_from_github(inp.value.strip())
                    if ok:
                        self.dismiss(("installed", self._inspected.id, self._inspected.name))
                    else:
                        err.update(msg)
                        err.add_class("show")

        def _do_inspect(self, target: str):
            prev = self.query_one("#gh-preview", Static)
            err = self.query_one("#gh-error", Static)
            err.remove_class("show")
            submit_btn = self.query_one("#gh-submit", Button)

            if not extension_installer:
                err.update("Installer engine unavailable.")
                err.add_class("show")
                return

            prev.update(f"Inspecting '{target}'...")
            insp = extension_installer.inspect_repository(target)
            if not insp.valid:
                err.update(insp.error or "Failed to inspect repository.")
                err.add_class("show")
                submit_btn.disabled = True
                self._inspected = None
                return

            self._inspected = insp
            summary = (
                f"✓ Valid CAT {insp.component_type.upper()}: '{insp.name}' (v{insp.version})\n"
                f"  Author: {insp.publisher}  ·  Category: {insp.category}\n"
                f"  Permissions: {', '.join(insp.permissions) if insp.permissions else 'None (sandboxed)'}\n"
                f"  Compatibility: {insp.compatibility_notes}"
            )
            prev.update(summary)
            submit_btn.disabled = False

        def on_key(self, event):
            if event.key == "escape":
                self.dismiss(None)

    class _CreateExtensionModal(Screen):
        """Modal dialog to create and add a custom extension."""
        CSS = """
        _CreateExtensionModal { align: center middle; background: rgba(0, 0, 0, 0.7); }
        #create-ext-box {
            width: 72; max-width: 96%; height: auto; max-height: 44;
            background: $surface; border: tall $border; padding: 0;
            layout: vertical; overflow: hidden;
        }
        #create-ext-titlebar { height: 5; min-height: 5; max-height: 5; padding: 0 2; border-bottom: solid $border; layout: horizontal; align: center middle; }
        #create-ext-title { width: 1fr; text-style: bold; color: $text; }
        #create-ext-body { height: auto; padding: 1 2; layout: vertical; }
        .create-field-label { width: 100%; height: 1; color: $text-muted; margin-top: 1; }
        .create-field-label:first-child { margin-top: 0; }
        #create-ext-body Input { width: 100%; height: 3; border: tall $border; background: $surface; }
        #create-ext-body Input:focus { border: tall $accent; }
        #create-ext-row { height: auto; layout: horizontal; }
        #create-ext-row > Vertical { width: 1fr; margin-right: 1; }
        #create-ext-row > Vertical:last-child { margin-right: 0; }
        #create-ext-error { width: 100%; height: 1; color: $error; display: none; margin-top: 1; }
        #create-ext-error.show { display: block; }
        #create-ext-actions { height: 4; min-height: 4; padding: 0 2; border-top: solid $border; background: $surface; layout: horizontal; align: right middle; }
        #create-ext-actions Button { margin-left: 1; min-width: 12; height: 3; }
        """

        def compose(self):
            with Vertical(id="create-ext-box"):
                with Horizontal(id="create-ext-titlebar"):
                    yield Static("⚡  Create Custom Extension", id="create-ext-title")
                    yield Button("✕ Close", id="create-close", classes="cct-modal-close-btn")
                with Vertical(id="create-ext-body"):
                    yield Static("Extension Name *", classes="create-field-label")
                    yield Input(placeholder="e.g. Code Formatter Pro", id="input-ext-name")
                    with Horizontal(id="create-ext-row"):
                        with Vertical():
                            yield Static("Extension ID (slug) *", classes="create-field-label")
                            yield Input(placeholder="e.g. code_formatter", id="input-ext-id")
                        with Vertical():
                            yield Static("Icon (emoji/symbol)", classes="create-field-label")
                            yield Input(value="⚡", placeholder="⚡", id="input-ext-icon")
                    yield Static("Description", classes="create-field-label")
                    yield Input(placeholder="e.g. Formats code with custom rules", id="input-ext-desc")
                    yield Static("Category", classes="create-field-label")
                    yield Input(value="Productivity", placeholder="Category", id="input-ext-cat")
                    yield Static("", id="create-ext-error")
                with Horizontal(id="create-ext-actions"):
                    yield Button("Cancel", id="create-cancel")
                    yield Button("Create & Add", id="create-submit", variant="primary")

        def on_button_pressed(self, event):
            bid = event.button.id or ""
            if bid in ("create-close", "create-cancel"):
                self.dismiss(None)
                return
            if bid == "create-submit":
                name = self.query_one("#input-ext-name", Input).value.strip()
                raw_id = self.query_one("#input-ext-id", Input).value.strip()
                desc = self.query_one("#input-ext-desc", Input).value.strip()
                icon = self.query_one("#input-ext-icon", Input).value.strip() or "⚡"
                cat = self.query_one("#input-ext-cat", Input).value.strip() or "Productivity"
                err = self.query_one("#create-ext-error", Static)

                if not name:
                    err.update("Please enter an extension name.")
                    err.add_class("show")
                    return
                import re
                ext_id = raw_id.lower().replace("-", "_").replace(" ", "_") if raw_id else name.lower().replace("-", "_").replace(" ", "_")
                ext_id = re.sub(r"[^a-z0-9_]", "", ext_id)
                if not ext_id:
                    err.update("Please enter a valid extension ID.")
                    err.add_class("show")
                    return

                if ext_mgr:
                    ok, res = ext_mgr.create_extension(
                        extension_id=ext_id,
                        name=name,
                        description=desc,
                        icon=icon,
                        publisher="You (Custom)",
                        category=cat,
                        version="1.0.0"
                    )
                    if ok:
                        self.dismiss(("created", ext_id, name))
                    else:
                        err_msg = res if isinstance(res, str) else (res or {}).get("message", "Failed to create extension.")
                        err.update(err_msg)
                        err.add_class("show")
                else:
                    self.dismiss(None)

        def on_key(self, event):
            if event.key == "escape":
                self.dismiss(None)

    class ExtensionsPanel(Screen):
        """VS Code-style Extensions marketplace — with category filters and GitHub installer."""

        CSS = """
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
        .ext-card { height: auto; min-height: 6; padding: 1 2; border: tall $border; background: $surface; margin: 0 0 1 0; layout: horizontal; overflow: hidden; }
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
        .ext-card-actions Button { min-width: 12; height: 3; min-height: 3; padding: 0 1; margin-left: 1; }
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
        """

        BINDINGS = [Binding("escape", "cancel", "Cancel")]

        def __init__(self):
            super().__init__()
            self._busy: dict = {}
            self._spinner_index: int = 0
            self._search_query: str = ""
            self._current_filter: str = "all"
            self._busy_timer = None

        def compose(self):
            with Vertical(id="ext-box"):
                with Horizontal(id="ext-titlebar"):
                    yield Static("▣  Extensions & Component Manager", id="ext-title")
                    yield Button("✕ Close", id="ext-close", classes="cct-modal-close-btn")
                with Vertical(id="ext-search"):
                    yield Input(placeholder="Search extensions, skills, commands...", id="ext-search-input")
                with Horizontal(id="ext-filters"):
                    yield Button("All", id="filter-all", classes="ext-filter-btn active")
                    yield Button("Extensions", id="filter-extension", classes="ext-filter-btn")
                    yield Button("Skills", id="filter-skill", classes="ext-filter-btn")
                    yield Button("Commands", id="filter-command", classes="ext-filter-btn")
                    yield Button("Integrations", id="filter-integration", classes="ext-filter-btn")
                yield Static("", id="ext-error")
                with VerticalScroll(id="ext-list"):
                    for ext in self._filtered():
                        yield _ExtCard(ext)
                with Horizontal(id="ext-actions"):
                    with Horizontal(id="ext-actions-left"):
                        yield Button("↓ GitHub Install", id="ext-gh-install-btn", classes="cct-btn-sm")
                        yield Button("＋ Create Extension", id="ext-create-btn", classes="cct-btn-sm")
                        yield Button("Enable All", id="ext-enable-all", classes="cct-btn-sm")
                        yield Button("Disable All", id="ext-disable-all", classes="cct-btn-sm")
                    yield Button("Close", id="ext-close2", variant="primary", classes="cct-btn-sm")

        def on_mount(self):
            try:
                self.query_one("#ext-box").add_class("open")
            except Exception:
                pass
            if self.size.width < 86:
                try:
                    self.query_one("#ext-box").add_class("cct-compact")
                except Exception:
                    pass
            try:
                self.query_one("#ext-search-input", Input).focus()
            except Exception:
                pass
            try:
                from . import design_system
                design_system.stop_timer(getattr(self, "_spin_timer", None))
                self._spin_timer = self.set_interval(0.12, self._tick_spinner)
            except Exception:
                try:
                    self._spin_timer = self.set_interval(0.12, self._tick_spinner)
                except Exception:
                    self._spin_timer = None

        def on_unmount(self):
            try:
                from . import design_system
                design_system.stop_timer(getattr(self, "_spin_timer", None))
            except Exception:
                pass
            self._spin_timer = None

        def _filtered(self):
            try:
                query = ""
                try:
                    query = self.query_one("#ext-search-input", Input).value.strip().lower()
                except Exception:
                    query = getattr(self, "_search_query", "") or ""

                ftype = None if self._current_filter == "all" else self._current_filter
                all_exts = ext_mgr.list_extensions(component_type=ftype) if ext_mgr else []
                if not query:
                    return all_exts
                out = []
                for ext in all_exts:
                    hay = " ".join([
                        str(ext.get("name", "")),
                        str(ext.get("display_name", "")),
                        str(ext.get("type", "")),
                        str(ext.get("publisher", "")),
                        str(ext.get("creator", "")),
                        str(ext.get("category", "")),
                        str(ext.get("description", "")),
                        " ".join(ext.get("keywords", [])),
                    ]).lower()
                    if query in hay:
                        out.append(ext)
                return out
            except Exception:
                return ext_mgr.list_extensions() if ext_mgr else []

        def _refresh(self, msg=None):
            _saved_y = 0
            try:
                lst = self.query_one("#ext-list", VerticalScroll)
                try:
                    _saved_y = lst.scroll_y
                except Exception:
                    _saved_y = 0
                lst.remove_children()
                for ext in self._filtered():
                    lst.mount(_ExtCard(ext))
                try:
                    lst.scroll_y = _saved_y
                except Exception:
                    pass
            except Exception:
                pass
            if msg:
                try:
                    self.app._system_note(msg)
                except Exception:
                    pass

        def _show_error(self, msg=""):
            try:
                lbl = self.query_one("#ext-error", Static)
                if msg:
                    lbl.update(msg)
                    lbl.add_class("show")
                else:
                    lbl.remove_class("show")
            except Exception:
                pass

        def _open_details(self, ext_id):
            try:
                self.app.push_screen(_DetailsPanel(ext_id), lambda res: self._refresh())
            except Exception as e:
                self._show_error(str(e))

        def _tick_spinner(self):
            if not getattr(self, "_busy", None) or not self._busy:
                return
            self._spinner_index = (self._spinner_index + 1) % 4

        def _start_busy(self, ext_id: str, action: str):
            self._busy[ext_id] = action
            self._refresh()
            try:
                for card in self.query("#ext-list _ExtCard"):
                    if getattr(card, "ext_id", None) == ext_id:
                        card.add_class("ext-busy")
            except Exception:
                pass

        def _finish_busy(self, ext_id: str):
            try:
                self._busy.pop(ext_id, None)
            except Exception:
                pass
            try:
                self._refresh()
            except Exception:
                pass

        def _do_install(self, ext_id: str):
            try:
                if ext_mgr:
                    ok, msg = ext_mgr.install(ext_id)
                    self._finish_busy(ext_id)
                    self._refresh(msg)
                    if not ok:
                        self._show_error(msg)
                    else:
                        self._show_error("")
            except Exception as e:
                self._finish_busy(ext_id)
                self._show_error(str(e))

        def _do_uninstall(self, ext_id: str):
            try:
                if ext_mgr:
                    ok, msg = ext_mgr.uninstall(ext_id)
                    self._finish_busy(ext_id)
                    self._refresh(msg)
                    if not ok:
                        self._show_error(msg)
                    else:
                        self._show_error("")
            except Exception as e:
                self._finish_busy(ext_id)
                self._show_error(str(e))

        def _do_enable(self, ext_id: str):
            try:
                if ext_mgr:
                    ok, msg = ext_mgr.enable(ext_id)
                    self._finish_busy(ext_id)
                    self._refresh(msg)
                    if not ok:
                        self._show_error(msg)
                    else:
                        self._show_error("")
            except Exception as e:
                self._finish_busy(ext_id)
                self._show_error(str(e))

        def _do_disable(self, ext_id: str):
            try:
                if ext_mgr:
                    ok, msg = ext_mgr.disable(ext_id)
                    self._finish_busy(ext_id)
                    self._refresh(msg)
                    if not ok:
                        self._show_error(msg)
                    else:
                        self._show_error("")
            except Exception as e:
                self._finish_busy(ext_id)
                self._show_error(str(e))

        def on_input_changed(self, event):
            if getattr(event.input, "id", "") == "ext-search-input":
                self._search_query = event.value
                self._refresh()

        def on_click(self, event):
            widget = getattr(event, "widget", None)
            if isinstance(widget, _ExtCard):
                self._open_details(widget.ext_id)

        def on_button_pressed(self, event):
            bid = event.button.id or ""
            if bid in ("ext-close", "ext-close2"):
                self.dismiss(None)
                return

            # Filter buttons
            if bid.startswith("filter-"):
                ftype = bid.replace("filter-", "")
                self._current_filter = ftype
                for b in self.query(".ext-filter-btn"):
                    b.remove_class("active")
                event.button.add_class("active")
                self._refresh()
                return

            if bid == "ext-create-btn":
                self.app.push_screen(_CreateExtensionModal(), self._on_created_extension)
                return

            if bid == "ext-gh-install-btn":
                self.app.push_screen(_InstallGitHubModal(), self._on_installed_component)
                return

            if bid == "ext-enable-all":
                if ext_mgr:
                    for ext in ext_mgr.list_extensions():
                        if ext.get("installed") and not ext.get("enabled"):
                            ext_mgr.enable(ext["id"])
                self._refresh("✓ All extensions enabled")
                return

            if bid == "ext-disable-all":
                if ext_mgr:
                    for ext in ext_mgr.list_extensions():
                        if ext.get("enabled"):
                            ext_mgr.disable(ext["id"])
                self._refresh("✓ All extensions disabled")
                return

            if bid.startswith("ext-install-"):
                key = bid.replace("ext-install-", "")
                if key in self._busy:
                    return
                self._start_busy(key, "install")
                try:
                    self.set_timer(0.4, lambda: self._do_install(key))
                except Exception:
                    self._do_install(key)
                return

            if bid.startswith("ext-enable-"):
                key = bid.replace("ext-enable-", "")
                if key in self._busy:
                    return
                self._start_busy(key, "enable")
                try:
                    self.set_timer(0.3, lambda: self._do_enable(key))
                except Exception:
                    self._do_enable(key)
                return

            if bid.startswith("ext-disable-"):
                key = bid.replace("ext-disable-", "")
                if key in self._busy:
                    return
                self._start_busy(key, "disable")
                try:
                    self.set_timer(0.3, lambda: self._do_disable(key))
                except Exception:
                    self._do_disable(key)
                return

            if bid.startswith("ext-uninstall-"):
                key = bid.replace("ext-uninstall-", "")
                if key in self._busy:
                    return
                self._start_busy(key, "uninstall")
                try:
                    self.set_timer(0.4, lambda: self._do_uninstall(key))
                except Exception:
                    self._do_uninstall(key)
                return

        def _on_created_extension(self, res):
            if res and isinstance(res, tuple) and res[0] == "created":
                self._refresh(f"✓ Extension '{res[2]}' created & added!")

        def _on_installed_component(self, res):
            if res and isinstance(res, tuple) and res[0] == "installed":
                self._refresh(f"✓ Component '{res[2]}' installed successfully!")

        def action_cancel(self):
            self.dismiss(None)

        def on_key(self, event):
            if event.key == "escape":
                self.dismiss(None)

else:
    ExtensionsPanel = None
    _DetailsPanel = None
    _CreateExtensionModal = None
    _InstallGitHubModal = None
