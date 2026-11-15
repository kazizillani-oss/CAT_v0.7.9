"""
CCT UI — ExtensionsPanel (VS Code-style).

Full VS Code-inspired marketplace and component manager for Gestures, Personalize,
Agent Skills, MCP Servers, Custom Commands, and Integrations.

Features:
- 4 Top-Level Categories: Built-in, Installed, MCP Servers, Discover
- Sub-filters: All, My Extensions, Community, Imported Skills, Updates
- Progressive disclosure integration with SkillsEngine and MCP Server registry
- Cards: Tactile 3D tall-bevels, creator @handles, repository attribution, non-clipping action buttons
- GitHub Installation Modal: inspect before installing, path traversal validation
- Preservation of built-ins: Gestures & Personalize (Publisher: Kazi Zillani)
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
        from ..skills import engine as skills_engine_mod
    except Exception:
        skills_engine_mod = None
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
        """VS Code-style card: icon | info | actions with non-clipping tall bevels."""
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
            creator_handle = ext.get("publisher_id") or ext.get("github_username") or ""
            creator_str = f"{creator} ({creator_handle})" if creator_handle and not creator.endswith(creator_handle) else creator
            verified = bool(ext.get("publisher_verified") or ext.get("verified"))
            trusted = bool(ext.get("trusted"))
            version = ext.get("version", "1.0.0")
            category = ext.get("category", "General")
            size = ext.get("size_display") or ext.get("size", "?")
            ctype = str(ext.get("type", "ext")).upper()
            license_name = ext.get("license", "MIT")

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
                busy = getattr(self.screen, "_busy", {}).get(self.ext_id)
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

            # Left icon with 3D tactile box
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
                # Title row: Name + Badge + Verified/Trusted
                with Horizontal(classes="ext-title-row"):
                    yield Static(name, classes="ext-name")
                    yield Static(f"[{ctype}]", classes="ext-type-badge")
                    if ext.get("kind") == "builtin":
                        yield Static("✓ Official Skill", classes="ext-verified")
                    elif verified and trusted:
                        yield Static("✓ Verified Trusted", classes="ext-verified")
                    elif verified:
                        yield Static("✓ Verified", classes="ext-verified")
                    elif trusted:
                        yield Static("Trusted", classes="ext-trusted")

                # Description
                yield Static(desc, classes="ext-desc")

                # Clean metadata: Creator (@handle) • vVersion • Category • License • Status
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
                yield Static(
                    f"{creator_str}  •  v{version}  •  {category}  •  {license_name}  •  [{_hex(tone)}]{status_text}[/]",
                    classes="ext-meta",
                    markup=True
                )

            # Right actions (3 rows tall, never clipped)
            with Horizontal(classes="ext-card-actions"):
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
        #det-titlebar { height: 3; min-height: 3; max-height: 3; padding: 0 2; border-bottom: solid $border; layout: horizontal; align-vertical: middle; background: $surface-dark; }
        #det-title { width: 1fr; text-style: bold; }
        #det-body { height: 1fr; overflow-y: auto; padding: 1 2; }
        .det-icon { width: 100%; height: 3; text-align: center; text-style: bold; }
        .det-name { width: 100%; height: 1; text-style: bold; text-align: center; }
        .det-creator { width: 100%; height: 1; color: $text-muted; text-align: center; }
        .det-verified { width: 100%; height: 1; color: $success; text-align: center; }
        .det-meta { width: 100%; height: auto; color: $text-faint; text-align: center; padding: 1 0; }
        .det-desc { width: 100%; height: auto; color: $text; padding: 1 0; }
        .det-section { width: 100%; height: 1; color: $text-faint; text-style: bold; padding-top: 1; border-top: solid $border; margin-top: 1; }
        #det-actions { height: 4; min-height: 4; max-height: 4; padding: 0 2; border-top: solid $border; layout: horizontal; align: center middle; }
        #det-actions Button { margin-right: 1; height: 3; min-height: 3; }
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
                    yield Button("✕", id="det-close", classes="cct-modal-close-btn")
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
                    if ext.get("repository") or ext.get("url"):
                        yield Static(f"Repository: {ext.get('repository') or ext.get('url')}", classes="det-desc")
                    if ext.get("credits"):
                        yield Static(f"Attribution: {ext.get('credits')}", classes="det-desc")
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
                    compat = ext.get("cat_compatibility", ">=0.9.0")
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
        #gh-titlebar { height: 3; min-height: 3; max-height: 3; padding: 0 2; border-bottom: solid $border; layout: horizontal; align-vertical: middle; background: $surface-dark; }
        #gh-title { width: 1fr; text-style: bold; color: $text; }
        #gh-body { height: auto; padding: 1 2; layout: vertical; }
        .gh-label { width: 100%; height: 1; color: $text-muted; margin-top: 1; }
        .gh-label:first-child { margin-top: 0; }
        #input-gh-url { width: 100%; height: 3; border: tall $border; background: $surface; margin-bottom: 1; }
        #input-gh-url:focus { border: tall $accent; }
        #gh-cat-row { height: auto; layout: horizontal; margin-bottom: 1; }
        .gh-cat-btn { margin-right: 1; height: 3; min-width: 15; padding: 0 1; }
        #gh-preview { width: 100%; height: auto; min-height: 4; border: tall $border; background: $surface-darken-2; padding: 1; margin-top: 1; color: $text; }
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
                    yield Button("✕", id="gh-close", classes="cct-modal-close-btn")
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
        #create-ext-titlebar { height: 3; min-height: 3; max-height: 3; padding: 0 2; border-bottom: solid $border; layout: horizontal; align-vertical: middle; background: $surface-dark; }
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
                    yield Button("✕", id="create-close", classes="cct-modal-close-btn")
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
        """Redesigned Extensions & Component Manager with 4 categories, sub-filters, and tall bevels."""

        CSS = """
        ExtensionsPanel { align: center middle; background: rgba(0, 0, 0, 0.72); }
        #ext-box {
            width: 94; max-width: 96%; height: 86%; max-height: 90%; min-height: 14;
            background: $surface;
            border: tall;
            border-top: tall $surface-highlight;
            border-left: tall $surface-highlight;
            border-bottom: tall $surface-shadow;
            border-right: tall $surface-shadow;
            padding: 0;
            layout: vertical;
            overflow: hidden;
        }
        #ext-titlebar {
            height: 3; min-height: 3; max-height: 3;
            padding: 0 1;
            border-bottom: solid $border;
            layout: horizontal;
            align-vertical: middle;
            background: $surface-dark;
        }
        #ext-title { width: 1fr; text-style: bold; color: $accent; align-vertical: middle; }

        /* Top Category Navigation Tabs — 1fr fluid non-wrapping */
        #ext-tabs-bar {
            height: 3; min-height: 3; max-height: 3;
            width: 100%;
            padding: 0 1;
            border-bottom: solid $border;
            layout: horizontal;
            align: center middle;
            background: $surface-dark;
            overflow: hidden;
        }
        .ext-tab,
        Button.ext-tab,
        Button.ext-tab:focus,
        Button.ext-tab:hover,
        Button.ext-tab.-active {
            height: 3; min-height: 3; max-height: 3;
            width: 1fr;
            min-width: 4;
            padding: 0 1;
            margin: 0;
            border: none;
            border-bottom: tall transparent;
            offset: 0 0;
            background: transparent;
            color: $text-muted;
            text-style: bold;
            text-align: center;
            content-align: center middle;
        }
        .ext-tab:hover,
        Button.ext-tab:hover {
            color: $text;
            background: $surface-alt;
        }
        .ext-tab.active,
        Button.ext-tab.active,
        Button.ext-tab.active:hover,
        Button.ext-tab.active:focus,
        Button.ext-tab.active.-active {
            color: $accent;
            background: $surface;
            border: none;
            border-bottom: tall $accent;
            text-style: bold;
        }

        /* Search Row */
        #ext-search-row {
            height: 3; min-height: 3; max-height: 3;
            padding: 0 1;
            margin-top: 1;
            layout: horizontal;
        }
        #ext-search-input {
            width: 1fr; height: 3; min-height: 3; max-height: 3;
            border: tall;
            border-top: tall $surface-shadow;
            border-left: tall $surface-shadow;
            border-bottom: tall $surface-highlight;
            border-right: tall $surface-highlight;
            background: $surface-alt;
            color: $text;
        }
        #ext-search-input:focus {
            border: tall;
            border-top: tall $accent-dark;
            border-left: tall $accent-dark;
            border-bottom: tall $accent-highlight;
            border-right: tall $accent-highlight;
        }

        /* Sub-filter Chips Bar — fluid 4 chips */
        #ext-subfilters-bar {
            height: 3; min-height: 3; max-height: 3;
            width: 100%;
            padding: 0 1;
            margin: 1 0;
            layout: horizontal;
            align: center middle;
            overflow: hidden;
        }
        .ext-subfilter {
            height: 3; min-height: 3; max-height: 3;
            width: 1fr;
            min-width: 6;
            padding: 0 1;
            margin-right: 1;
            border: tall;
            border-top: tall $surface-highlight;
            border-left: tall $surface-highlight;
            border-bottom: tall $surface-shadow;
            border-right: tall $surface-shadow;
            background: $surface-dark;
            color: $text-faint;
            text-style: bold;
            content-align: center middle;
            text-align: center;
        }
        .ext-subfilter:last-child {
            margin-right: 0;
        }
        .ext-subfilter:hover {
            border-top: tall #ffffff;
            color: $text;
            background: $surface-alt;
        }
        .ext-subfilter.active {
            border: tall $accent;
            background: $surface-active;
            color: $accent;
            text-style: bold;
        }

        #ext-error { color: $error; background: $surface; height: 1; padding: 0 2; display: none; }
        #ext-error.show { display: block; }

        /* Card Scroll Container */
        #ext-list {
            height: 1fr; min-height: 4;
            overflow-y: scroll; scrollbar-gutter: stable; scrollbar-size: 1 1;
            margin: 0 1; padding: 0;
        }
        .ext-card {
            height: auto; min-height: 7; max-height: 8; padding: 1 2;
            border: tall;
            border-top: tall $surface-highlight;
            border-left: tall $surface-highlight;
            border-bottom: tall $surface-shadow;
            border-right: tall $surface-shadow;
            background: $surface-alt;
            margin: 0 0 1 0;
            layout: horizontal;
            align-vertical: middle;
            overflow: hidden;
            transition: border 120ms, background 120ms;
        }
        .ext-card:hover {
            border-top: tall #ffffff;
            border-left: tall $surface-highlight;
            border-bottom: tall $surface-shadow;
            border-right: tall $surface-shadow;
            background: $surface-active;
        }
        .ext-card.ext-busy { background: $surface-active; border: round $accent; }

        /* Icon Container */
        .ext-card-icon {
            width: 6; min-width: 6; height: 5; text-align: center; text-style: bold;
            content-align: center middle; align: center middle; background: $surface-dark;
            border: tall;
            border-top: tall $surface-shadow;
            border-left: tall $surface-shadow;
            border-bottom: tall $surface-highlight;
            border-right: tall $surface-highlight;
            color: $accent;
            margin-right: 2; padding: 0;
        }
        .ext-icon { width: 100%; height: 100%; text-align: center; content-align: center middle; }
        .ext-loading { width: 6; height: 3; color: $accent; content-align: center middle; }

        /* Card Info */
        .ext-card-info { width: 1fr; height: auto; min-width: 20; }
        .ext-title-row { height: 1; layout: horizontal; align-vertical: middle; }
        .ext-name { width: auto; height: 1; text-style: bold; margin-right: 1; color: $text; }
        .ext-type-badge { width: auto; height: 1; color: $accent; text-style: bold; margin-right: 1; }
        .ext-verified { width: auto; height: 1; color: #5af78e; text-style: bold; }
        .ext-trusted { width: auto; height: 1; color: #5af78e; text-style: bold; margin-left: 1; }
        .ext-desc { width: 100%; height: auto; color: $text-muted; max-height: 2; overflow: hidden; margin-top: 0; }
        .ext-meta { width: 100%; height: 1; color: $text-faint; margin-top: 0; }

        /* Actions Container — strictly non-clipping with tall bevels */
        .ext-card-actions {
            width: auto; min-width: 14; height: 3; min-height: 3; max-height: 3;
            layout: horizontal; align: right middle; margin-left: 1;
        }
        .ext-card-actions Button {
            min-width: 12; height: 3; min-height: 3; max-height: 3; padding: 0 1; margin-left: 1;
            border: tall;
            border-top: tall $surface-highlight;
            border-left: tall $surface-highlight;
            border-bottom: tall $surface-shadow;
            border-right: tall $surface-shadow;
            background: $surface;
            color: $accent;
            text-style: bold;
        }
        .ext-card-actions Button:hover {
            border-top: tall #ffffff;
            background: $surface-active;
            color: #ffffff;
        }
        .ext-card-actions Button.-active, .ext-card-actions Button:focus {
            border-top: tall $surface-shadow;
            border-left: tall $surface-shadow;
            border-bottom: tall $surface-highlight;
            border-right: tall $surface-highlight;
            background: $surface-dark;
        }
        .ext-card-actions Button:first-child { margin-left: 0; }
        .ext-card-actions Button:disabled { opacity: 0.7; }

        /* Bottom Action Bar — docked strictly at bottom so it is NEVER clipped */
        #ext-actions {
            dock: bottom;
            height: 4; min-height: 4; max-height: 4; padding: 0 1; margin: 0;
            border-top: solid $border;
            background: $surface;
            layout: horizontal;
            align: center middle;
            overflow: hidden;
        }
        #ext-actions-left { width: 1fr; height: 3; layout: horizontal; align: left middle; }
        #ext-actions-left Button, #ext-actions Button {
            margin-right: 1; min-width: 10; height: 3; min-height: 3; max-height: 3; padding: 0 1;
            border: tall;
            border-top: tall $surface-highlight;
            border-left: tall $surface-highlight;
            border-bottom: tall $surface-shadow;
            border-right: tall $surface-shadow;
            background: $surface-alt;
            color: $text;
            text-style: bold;
        }
        #ext-actions-left Button:hover, #ext-actions Button:hover {
            border-top: tall #ffffff;
            background: $surface-active;
            color: #ffffff;
        }
        #ext-actions #ext-close2 {
            border: tall;
            border-top: tall #ffa0a0;
            border-left: tall #f38ba8;
            border-bottom: tall #7a2d3b;
            border-right: tall #7a2d3b;
            background: #4a1e27;
            color: #ff99a8;
            text-style: bold;
            min-width: 10;
            height: 3; min-height: 3; max-height: 3;
            content-align: center middle;
        }
        #ext-actions #ext-close2:hover {
            border-top: tall #ffffff;
            border-left: tall #ffc2c2;
            border-bottom: tall #9c3b4d;
            border-right: tall #9c3b4d;
            background: #6b2434;
            color: #ffffff;
        }

        /* Portrait Mode and Responsive Scaling */
        ExtensionsPanel.is-portrait #ext-box,
        ExtensionsPanel.is-floating #ext-box,
        .is-portrait #ext-box,
        .is-floating #ext-box {
            width: 96%; max-width: 98%; height: 92%; max-height: 94%; padding: 0;
        }
        ExtensionsPanel.is-portrait .ext-tab,
        .is-portrait .ext-tab {
            min-width: 4; padding: 0;
        }
        ExtensionsPanel.is-portrait .ext-subfilter,
        .is-portrait .ext-subfilter {
            min-width: 4; padding: 0;
        }
        ExtensionsPanel.is-portrait .ext-card,
        .is-portrait .ext-card {
            layout: vertical;
            height: auto;
            min-height: 9;
            padding: 1;
            align-vertical: top;
        }
        ExtensionsPanel.is-portrait .ext-card-icon,
        .is-portrait .ext-card-icon {
            display: none;
        }
        ExtensionsPanel.is-portrait .ext-card-info,
        .is-portrait .ext-card-info {
            width: 100%;
        }
        ExtensionsPanel.is-portrait .ext-card-actions,
        .is-portrait .ext-card-actions {
            width: 100%;
            layout: horizontal;
            align: center middle;
            margin-top: 1;
            margin-left: 0;
        }
        ExtensionsPanel.is-portrait .ext-card-actions Button,
        .is-portrait .ext-card-actions Button {
            width: 1fr;
            min-width: 8;
            height: 3; min-height: 3;
            margin: 0 1;
        }
        ExtensionsPanel.is-portrait #ext-actions,
        ExtensionsPanel.is-floating #ext-actions,
        .is-portrait #ext-actions,
        .is-floating #ext-actions {
            dock: bottom;
            width: 100%;
            height: 4;
            min-height: 3;
            max-height: 4;
            padding: 0 1;
            layout: horizontal;
            align: center middle;
        }
        ExtensionsPanel.is-portrait #ext-actions-left,
        ExtensionsPanel.is-floating #ext-actions-left,
        .is-portrait #ext-actions-left,
        .is-floating #ext-actions-left {
            width: 1fr;
            height: 3;
            layout: horizontal;
            align: left middle;
        }
        ExtensionsPanel.is-portrait #ext-actions-left Button,
        ExtensionsPanel.is-floating #ext-actions-left Button,
        .is-portrait #ext-actions-left Button,
        .is-floating #ext-actions-left Button {
            width: 1fr;
            min-width: 4;
            height: 3; min-height: 3;
            margin: 0 1 0 0;
            padding: 0;
            content-align: center middle;
            text-align: center;
        }
        ExtensionsPanel.is-portrait #ext-actions #ext-close2,
        ExtensionsPanel.is-floating #ext-actions #ext-close2,
        .is-portrait #ext-actions #ext-close2,
        .is-floating #ext-actions #ext-close2 {
            width: auto;
            min-width: 8;
            height: 3; min-height: 3;
            margin-left: 1;
            padding: 0 1;
            content-align: center middle;
            text-align: center;
        }
        """

        BINDINGS = [
            Binding("escape", "cancel", "Cancel"),
            Binding("pageup", "scroll_page_up", "Page Up", show=False),
            Binding("pagedown", "scroll_page_down", "Page Down", show=False),
            Binding("up", "scroll_up", "Scroll Up", show=False),
            Binding("down", "scroll_down", "Scroll Down", show=False),
        ]

        def __init__(self):
            super().__init__()
            self._busy: dict = {}
            self._spinner_index: int = 0
            self._search_query: str = ""
            self._active_tab: str = "builtin"
            self._active_subfilter: str = "all"
            self._spin_timer = None

        def compose(self):
            all_list = ext_mgr.list_extensions() if ext_mgr else []
            installed_cnt = len([e for e in all_list if e.get("installed")])
            mcp_cnt = len([e for e in all_list if e.get("kind") == "mcp" or "mcp" in str(e.get("category", "")).lower()])
            builtin_cnt = len([
                e for e in all_list
                if e.get("kind") == "builtin" or e.get("install_source") == "builtin"
                or any(p in str(e.get("publisher", "")).lower() for p in ("kazi", "morluto", "tt-a1i", "remotion", "microsoft", "nilbuild", "anthropic", "vercel", "cat", "obra", "mattpocock", "nextlevelbuilder", "cloudflare", "addyosmani", "pbakaus", "blader"))
            ])

            with Vertical(id="ext-box"):
                # Titlebar (top cross button removed as requested; only bottom Close button)
                with Horizontal(id="ext-titlebar"):
                    yield Static("▣  Extensions & Component Manager", id="ext-title")

                # Top-level Tabs (4 categories, fluid non-overlapping with dynamic badge counts)
                with Horizontal(id="ext-tabs-bar"):
                    yield Button(f"⭐ Built-in ({builtin_cnt})", id="tab-builtin", classes="ext-tab active")
                    yield Button(f"📦 Installed ({installed_cnt})", id="tab-installed", classes="ext-tab")
                    yield Button(f"🔌 MCP Servers ({mcp_cnt})", id="tab-mcp", classes="ext-tab")
                    yield Button("🌐 Discover", id="tab-discover", classes="ext-tab")

                # Search row
                with Horizontal(id="ext-search-row"):
                    yield Input(placeholder="Search extensions, skills, commands, authors...", id="ext-search-input")

                # Sub-filter chips (4 subfilters, Updates button removed as requested)
                with Horizontal(id="ext-subfilters-bar"):
                    yield Button("All", id="sub-all", classes="ext-subfilter active")
                    yield Button("My Extensions", id="sub-my-ext", classes="ext-subfilter")
                    yield Button("Community", id="sub-community", classes="ext-subfilter")
                    yield Button("Imported Skills", id="sub-skills", classes="ext-subfilter")

                yield Static("", id="ext-error")

                # List of cards
                with VerticalScroll(id="ext-list"):
                    for ext in self._filtered():
                        yield _ExtCard(ext)

                # Bottom actions
                with Horizontal(id="ext-actions"):
                    with Horizontal(id="ext-actions-left"):
                        yield Button("↓ GitHub Install", id="ext-gh-install-btn", classes="cct-btn-sm")
                        yield Button("＋ Create Extension", id="ext-create-btn", classes="cct-btn-sm")
                        yield Button("Enable All", id="ext-enable-all", classes="cct-btn-sm")
                    yield Button("Close", id="ext-close2", variant="primary", classes="cct-btn-sm")

        def on_mount(self):
            self._check_portrait()
            try:
                self.query_one("#ext-search-input", Input).focus()
            except Exception:
                pass

        def on_resize(self, event=None):
            self._check_portrait()

        def _check_portrait(self):
            try:
                w = getattr(self.app.size, "width", 80)
                h = getattr(self.app.size, "height", 25)
                is_portrait = (w < 86) or (w < h * 1.30)
                is_floating = (h < 26) or (w < 76)
                self.set_class(is_portrait, "is-portrait")
                self.set_class(is_floating, "is-floating")

                # Responsive button labels to prevent overflow in narrow or portrait windows
                gh_btn = self.query_one("#ext-gh-install-btn", Button)
                create_btn = self.query_one("#ext-create-btn", Button)
                if w < 76:
                    gh_btn.label = "↓ GitHub"
                    create_btn.label = "＋ Create"
                else:
                    gh_btn.label = "↓ GitHub Install"
                    create_btn.label = "＋ Create Extension"
            except Exception:
                pass

        def on_unmount(self):
            if self._spin_timer:
                try:
                    self._spin_timer.stop()
                except Exception:
                    pass
                self._spin_timer = None

        def _filtered(self):
            try:
                all_exts = ext_mgr.list_extensions(component_type=None) if ext_mgr else []

                # Tab filtering
                if self._active_tab == "builtin":
                    all_exts = [
                        e for e in all_exts
                        if e.get("kind") == "builtin"
                        or e.get("install_source") == "builtin"
                        or any(p in str(e.get("publisher", "")).lower() for p in ("kazi", "morluto", "tt-a1i", "remotion", "microsoft", "nilbuild", "anthropic", "vercel", "cat", "obra", "mattpocock", "nextlevelbuilder", "cloudflare", "addyosmani", "pbakaus", "blader"))
                        or any(p in str(e.get("id", "")).lower() for p in ("skill-creator", "find-skills", "rea", "archify", "remotion", "skillopt", "page-mascot", "frontend-design", "gestures", "personalize", "superpowers", "ts-wizard", "mcp-builder", "ui-ux-pro-max", "cloudflare-security", "addy-agent-skills", "impeccable", "humanizer", "cat-", "brainstorming", "planning", "code-review", "debugging", "testing", "security-audit", "git-workflow", "documentation", "research", "browser-automation", "refactoring", "seo-optimization", "scientific-research"))
                    ]
                elif self._active_tab == "installed":
                    all_exts = [e for e in all_exts if e.get("installed")]
                elif self._active_tab == "mcp":
                    all_exts = [
                        e for e in all_exts
                        if str(e.get("type", "")).lower() in ("mcp", "mcp_component") or e.get("kind") == "mcp" or "mcp" in str(e.get("category", "")).lower()
                    ]
                # Discover tab shows all discoverable extensions

                # Sub-filter filtering
                if self._active_subfilter == "my-ext":
                    all_exts = [e for e in all_exts if e.get("kind") == "custom" or "custom" in str(e.get("category", "")).lower() or e.get("publisher") == "You (Custom)"]
                elif self._active_subfilter == "community":
                    all_exts = [e for e in all_exts if not e.get("publisher_verified") and e.get("kind") != "builtin"]
                elif self._active_subfilter == "skills":
                    all_exts = [e for e in all_exts if str(e.get("type", "")).lower() == "skill"]
                elif self._active_subfilter == "updates":
                    all_exts = [e for e in all_exts if e.get("has_update") or e.get("update_available")]

                # Search query filtering
                query = self._search_query.strip().lower()
                if not query:
                    return all_exts

                out = []
                for ext in all_exts:
                    hay = " ".join([
                        str(ext.get("name", "")),
                        str(ext.get("display_name", "")),
                        str(ext.get("type", "")),
                        str(ext.get("publisher", "")),
                        str(ext.get("publisher_id", "")),
                        str(ext.get("github_username", "")),
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
            try:
                lst = self.query_one("#ext-list", VerticalScroll)
                lst.remove_children()
                for ext in self._filtered():
                    lst.mount(_ExtCard(ext))
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
            if not getattr(self, "_busy", None):
                return
            self._spinner_index = (self._spinner_index + 1) % 4

        def _start_busy(self, ext_id: str, action: str):
            self._busy[ext_id] = action
            self._refresh()

        def _finish_busy(self, ext_id: str):
            try:
                self._busy.pop(ext_id, None)
            except Exception:
                pass
            self._refresh()

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
                if getattr(self, "_search_timer", None):
                    try:
                        self._search_timer.stop()
                    except Exception:
                        pass
                self._search_timer = self.set_timer(0.12, self._refresh)

        def on_click(self, event):
            widget = getattr(event, "widget", None)
            if isinstance(widget, _ExtCard):
                self._open_details(widget.ext_id)

        def on_button_pressed(self, event):
            bid = event.button.id or ""
            if bid in ("ext-close", "ext-close2"):
                self.dismiss(None)
                return

            # Top Tab Clicks
            if bid.startswith("tab-"):
                tab_name = bid.replace("tab-", "")
                self._active_tab = tab_name
                self._active_subfilter = "all"
                for btn in self.query(".ext-tab"):
                    btn.remove_class("active")
                event.button.add_class("active")
                for sub in self.query(".ext-subfilter"):
                    sub.remove_class("active")
                try:
                    self.query_one("#sub-all", Button).add_class("active")
                except Exception:
                    pass
                self._refresh()
                return

            # Sub-filter Clicks
            if bid.startswith("sub-"):
                sub_name = bid.replace("sub-", "")
                self._active_subfilter = sub_name
                for btn in self.query(".ext-subfilter"):
                    btn.remove_class("active")
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

        def action_scroll_page_up(self):
            try:
                self.query_one("#ext-list", VerticalScroll).scroll_page_up()
            except Exception:
                pass

        def action_scroll_page_down(self):
            try:
                self.query_one("#ext-list", VerticalScroll).scroll_page_down()
            except Exception:
                pass

        def action_scroll_up(self):
            try:
                self.query_one("#ext-list", VerticalScroll).scroll_up()
            except Exception:
                pass

        def action_scroll_down(self):
            try:
                self.query_one("#ext-list", VerticalScroll).scroll_down()
            except Exception:
                pass

        def on_key(self, event):
            if event.key == "escape":
                self.dismiss(None)
            elif event.key in ("pageup", "pagedown"):
                try:
                    lst = self.query_one("#ext-list", VerticalScroll)
                    if event.key == "pageup":
                        lst.scroll_page_up()
                    else:
                        lst.scroll_page_down()
                except Exception:
                    pass

else:
    ExtensionsPanel = None
    _DetailsPanel = None
    _CreateExtensionModal = None
    _InstallGitHubModal = None
