"""
CCT UI — BackupProvidersPanel (v0.7.8.1 full redesign).

Professional management screen for the automatic failover chain: a
prioritized list of backup providers rendered as VS Code Settings-style
cards. When the primary provider exhausts quota / times out / is rate
limited / goes offline, aicore.query_ai/stream_ai walk this list
(priority order) and continue the conversation seamlessly.

Each card shows: logo (provider initial), provider name, model,
priority, API status (🟢/🟡/🔴), latency, last-used (usage), and the
fallback-enabled state. Actions are contextual: one "+ Add Provider"
primary button; when providers exist a compact row (Edit / Test /
On·Off / ↑ / ↓ / Delete) acts on the selected card; Save/Apply persist
and Cancel closes. The failover order is the visible card order.

This screen is pure chrome + persistence plumbing: rows render state
via provider_manager, the buttons edit the in-memory order, and
Save/Apply persist it. The app routes the Main Menu's "Backup
Providers" item here.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import threading
import time

TEXTUAL_AVAILABLE = True
try:
    from textual.screen import Screen
    from textual.containers import Vertical, Horizontal, ScrollableContainer
    from textual.widgets import Static, Button, Input
    from textual.binding import Binding
except Exception:
    TEXTUAL_AVAILABLE = False

if TEXTUAL_AVAILABLE:
    from ..providers import provider_manager as pm
    from . import theme_css

    _STATUS_GLYPH = {
        "connected": "\U0001f7e2",   # 🟢
        "testing": "\U0001f7e1",     # 🟡
        "disconnected": "\u26ab",    # ⚫
        "failed": "\U0001f534",      # 🔴
    }

    _STATUS_LABEL = {
        "connected": "API OK",
        "testing": "Testing",
        "disconnected": "Idle",
        "failed": "Failed",
    }

    _PROVIDER_LOGO = {
        "openai": "\u25cf", "anthropic": "\u2200", "gemini": "\u2728",
        "ollama": "\U0001f9ea", "groq": "\u26a1", "mistral": "\u2191",
        "deepseek": "\U0001f9ed", "cohere": "\U0001f40d", "local": "\U0001f4bb",
    }

    def _logo_for(provider):
        return _PROVIDER_LOGO.get((provider or "").lower(), "\u2699")


    class _ProviderCard(Static):
        """One provider card: logo · provider/model · priority · status ·
        latency · last used · fallback state."""

        def __init__(self, index, entry, selected=False):
            self.index = index
            self.entry = entry
            super().__init__("", classes="bpp-card" + (" bpp-card-sel" if selected else ""))
            self._redraw()

        def _redraw(self):
            pid = self.entry.get("provider") or "?"
            model = self.entry.get("model") or "?"
            status_key = self.entry.get("status") or "disconnected"
            try:
                from ..resilience.health_monitor import get_health_monitor
                h = get_health_monitor().get_health(pid, model)
                if h.status in ("rate_limited", "slow", "local", "healthy", "offline"):
                    status_key = "connected" if h.status in ("healthy", "local") else ("failed" if h.status == "offline" else ("testing" if h.status == "slow" else "disconnected"))
                    if h.latency_ms is not None and self.entry.get("latency_ms") is None:
                        self.entry["latency_ms"] = int(h.latency_ms)
            except Exception:
                pass
            glyph = _STATUS_GLYPH.get(status_key, "\u26ab")
            tone = {
                "connected": "success", "testing": "warning",
                "disconnected": "text-faint", "failed": "error",
            }.get(status_key, "text-faint")
            tone_hex = theme_css.current_hex(tone)
            label = _STATUS_LABEL.get(status_key, "Idle")
            last = self.entry.get("last_used") or 0
            last_txt = time.strftime("%Y-%m-%d %H:%M", time.localtime(last)) if last else "never used"
            enabled = bool(self.entry.get("enabled", True))
            fallback_txt = (f"[{theme_css.current_hex('success')} b]✓ fallback ON[/]"
                            if enabled else
                            f"[{theme_css.current_hex('text-faint')}]· fallback OFF[/]")
            sel = f" [{theme_css.current_hex('accent')} bold]▸[/]" if "bpp-card-sel" in self.classes else ""
            logo = _logo_for(pid)
            line1 = (f"  {logo} [{theme_css.current_hex('text')} b]{pid}[/] / "
                     f"[{theme_css.current_hex('text')}]{model}[/]   "
                     f"[{tone_hex} b]{glyph} {label}[/]{sel}")
            line2 = (f"     [{theme_css.current_hex('text-faint')}]"
                     f"priority {self.index + 1}  ·  {fallback_txt}"
                     f"  ·  latency {self._latency()}"
                     f"  ·  used {last_txt}[/]")
            api_info = f"api_style {self.entry.get('api_style', 'openai')}"
            if self.entry.get("base_url"):
                api_info += f"  ·  {self.entry.get('base_url')}"
            line3 = f"     [{theme_css.current_hex('text-faint')}]{api_info}[/]"
            self.update(f"{line1}\n{line2}\n{line3}")

        def _latency(self):
            lat = self.entry.get("latency_ms")
            if lat is not None:
                return f"{lat}ms"
            return "—"

        def set_selected(self, selected):
            self.set_class(selected, "bpp-card-sel")
            self._redraw()


    class BackupProvidersPanel(Screen):
        """The one screen for the whole failover chain: view, reorder,
        add, edit, remove, test, enable/disable, and persist backup
        providers."""

        CSS = """
        BackupProvidersPanel { align: center middle; background: $app-background 70%; }
        #bpp-box {
            width: 96; max-width: 98%; height: auto; max-height: 90%;
            background: $surface;
            border-top: tall $surface-highlight;
            border-bottom: tall $surface-dark;
            border-left: tall $surface-highlight;
            border-right: tall $surface-dark;
            padding: 0;
            opacity: 0; offset-y: 1;
            overflow: hidden hidden;
            transition: opacity 150ms, offset 180ms;
        }
        #bpp-box.open { opacity: 1; offset-y: 0; }
        #bpp-titlebar {
            height: 3; padding: 0 2;
            align: center middle;
            background: $surface-alt;
            border-bottom: solid $border;
            layout: horizontal;
        }
        #bpp-title { text-style: bold; width: 1fr; color: $text; }
        #bpp-close {
            width: 3; min-width: 3; max-width: 3; height: 1;
            padding: 0; margin: 0; border: none; background: transparent;
            color: $text-muted;
        }
        #bpp-close:hover { color: $error; text-style: bold; }
        #bpp-subtitle { color: $text-faint; height: 2; padding: 0 2; }
        #bpp-list {
            height: auto;
            min-height: 4;
            max-height: 18;
            padding: 1 2;
            overflow-y: auto;
            scrollbar-gutter: stable;
            scrollbar-size: 1 1;
            scrollbar-color: $border $surface;
        }
        .bpp-card {
            height: 5; margin-bottom: 1;
            background: $surface-alt;
            border-top: tall $surface-highlight;
            border-bottom: tall $surface-dark;
            border-left: tall $surface-highlight;
            border-right: tall $surface-dark;
            padding: 0 1;
            transition: background 120ms, border 120ms;
        }
        .bpp-card:hover {
            background: $surface-highlight;
            border-top: tall #ffffff;
            border-left: tall $surface-highlight;
            border-bottom: tall $surface-dark;
            border-right: tall $surface-dark;
        }
        .bpp-card-sel {
            background: $surface-highlight;
            border-top: tall $accent-highlight;
            border-bottom: tall $accent-shadow;
            border-left: tall $accent;
            border-right: tall $accent-shadow;
        }
        .bpp-empty { color: $text-faint; padding: 2 1; }
        #bpp-add-row { height: 4; padding: 0 2; margin-top: 1; }
        #bpp-add-row Button {
            margin-right: 1; width: 1fr; height: 3;
            border: tall $surface-highlight $surface-dark;
            background: $surface-alt;
            color: $text;
            text-style: bold;
            transition: background 100ms, border 100ms, offset 80ms;
        }
        #bpp-add-row Button.cct-btn-primary {
            background: $accent 32%;
            color: #ffffff;
            border: tall $accent-highlight $accent-shadow;
            text-style: bold;
        }
        #bpp-add-row Button:hover {
            border: tall #ffffff $surface-dark;
            background: $surface-highlight;
            color: #ffffff;
        }
        #bpp-add-row Button.cct-btn-primary:hover {
            border: tall #ffffff $accent;
            background: $accent 50%;
            color: #ffffff;
        }
        #bpp-add-row Button:focus {
            border: tall $accent-highlight $accent;
            background-tint: transparent;
        }
        #bpp-add-row Button.-active {
            border: tall $surface-dark $surface-highlight;
            offset-y: 1;
        }
        #bpp-ctx-actions { height: 4; padding: 0 2; margin-top: 1; }
        #bpp-ctx-actions Button {
            margin-right: 1; width: 1fr; min-width: 6; height: 3; padding: 0 1;
            border: tall $surface-highlight $surface-dark;
            background: $surface-alt;
            color: $text;
            text-style: bold;
            transition: background 100ms, border 100ms, offset 80ms;
        }
        #bpp-ctx-actions Button:hover {
            border: tall #ffffff $surface-dark;
            background: $surface-highlight;
            color: #ffffff;
        }
        #bpp-ctx-actions Button:focus {
            border: tall $accent-highlight $accent;
            background-tint: transparent;
        }
        #bpp-ctx-actions Button.-active {
            border: tall $surface-dark $surface-highlight;
            offset-y: 1;
        }
        #bpp-actions {
            height: 4;
            padding: 0 2;
            margin-top: 1;
            margin-bottom: 1;
            border-top: solid $border;
            align: center middle;
        }
        #bpp-actions Button {
            margin-right: 1; width: 1fr; height: 3;
            border: tall $surface-highlight $surface-dark;
            background: $surface-alt;
            color: $text;
            text-style: bold;
            transition: background 100ms, border 100ms, offset 80ms;
        }
        #bpp-actions Button.cct-btn-primary {
            background: $accent 32%;
            color: #ffffff;
            border: tall $accent-highlight $accent-shadow;
            text-style: bold;
        }
        #bpp-actions Button:hover {
            border: tall #ffffff $surface-dark;
            background: $surface-highlight;
            color: #ffffff;
        }
        #bpp-actions Button.cct-btn-primary:hover {
            border: tall #ffffff $accent;
            background: $accent 50%;
            color: #ffffff;
        }
        #bpp-actions Button:focus {
            border: tall $accent-highlight $accent;
            background-tint: transparent;
        }
        #bpp-actions Button.-active {
            border: tall $surface-dark $surface-highlight;
            offset-y: 1;
        }
        #bpp-box.cct-compact #bpp-subtitle { display: none; }
        """

        BINDINGS = [
            Binding("escape", "cancel", "Cancel"),
            Binding("down", "move_down_sel", "Next row"),
            Binding("up", "move_up_sel", "Previous row"),
        ]

        def __init__(self):
            super().__init__()
            self._providers = pm.load_backup_providers()
            self._selected = 0

        def compose(self):
            with Vertical(id="bpp-box"):
                with Horizontal(id="bpp-titlebar"):
                    yield Static("\U0001f4e1  Backup Providers", id="bpp-title")
                    yield Button("\u2715", id="bpp-close", classes="cct-popup-close")
                yield Static(
                    "Automatic failover \u2014 switches to the next enabled provider "
                    "when the primary fails. Ollama provides a reliable local fallback.",
                    id="bpp-subtitle")
                with ScrollableContainer(id="bpp-list"):
                    yield from self._rows()
                with Horizontal(id="bpp-add-row"):
                    yield Button("➕ Add Provider", id="bpp-add",
                                 classes="cct-btn cct-btn-primary")
                    yield Button("🦙 Add Ollama", id="bpp-add-ollama",
                                 classes="cct-btn")
                with Horizontal(id="bpp-ctx-actions"):
                    yield Button("✏ Edit", id="bpp-edit", classes="cct-btn cct-btn-sm")
                    yield Button("⚡ Test", id="bpp-test", classes="cct-btn cct-btn-sm")
                    yield Button("⏻ On/Off", id="bpp-toggle", classes="cct-btn cct-btn-sm")
                    yield Button("▲ Up", id="bpp-up", classes="cct-btn cct-btn-sm")
                    yield Button("▼ Down", id="bpp-down", classes="cct-btn cct-btn-sm")
                    yield Button("🗑 Delete", id="bpp-remove", classes="cct-btn cct-btn-sm")
                with Horizontal(id="bpp-actions"):
                    yield Button("✓ Save", id="bpp-save", classes="cct-btn cct-btn-primary")
                    yield Button("➜ Apply", id="bpp-apply", classes="cct-btn")
                    yield Button("✕ Cancel", id="bpp-cancel", classes="cct-btn")

        def _rows(self):
            if not self._providers:
                yield Static("No backup providers configured.", classes="bpp-empty")
                yield Static("Add a provider to enable automatic failover.",
                             classes="bpp-empty")
                return
            for i, entry in enumerate(self._providers):
                yield _ProviderCard(i, entry, selected=(i == self._selected))

        def _rebuild_list(self):
            try:
                self.query_one("#bpp-list", ScrollableContainer).remove_children()
                for row in self._rows():
                    self.query_one("#bpp-list", ScrollableContainer).mount(row)
                self._refresh_actions()
                self._fit()
            except Exception:
                pass

        def _refresh_actions(self):
            """Contextual row appears only when providers exist; the
            On/Off button mirrors the selected provider's enabled state
            and ↑/↓ need more than one provider."""
            has = bool(self._providers)
            try:
                self.query_one("#bpp-ctx-actions").display = has
            except Exception:
                pass
            if not has:
                return
            entry = self._current()
            try:
                toggle = self.query_one("#bpp-toggle", Button)
                toggle.label = "⏻ Off" if bool(entry.get("enabled", True)) else "⏻ On"
            except Exception:
                pass
            many = len(self._providers) > 1
            for bid in ("bpp-up", "bpp-down"):
                try:
                    self.query_one(f"#{bid}", Button).display = many
                except Exception:
                    pass

        def _fit(self):
            """Re-fit after content changes: content_size is only valid
            after the next layout pass, so always defer one frame."""
            try:
                self.call_after_refresh(
                    lambda: theme_css.fit_dialog(self, "bpp-box", "bpp-list"))
            except Exception:
                pass

        def _refresh_status(self):
            """Legacy no-op kept for callers outside this class."""
            return

        def on_mount(self):
            self.call_after_refresh(lambda: self.query_one("#bpp-box").add_class("open"))
            self.call_after_refresh(self._fit)
            self._refresh_actions()
            try:
                self.query_one("#bpp-list").focus()
            except Exception:
                pass

        def on_resize(self, event):
            self._fit()

        def on_click(self, event):
            widget = getattr(event, "widget", None)
            if isinstance(widget, _ProviderCard):
                if self._providers and widget.index < len(self._providers):
                    self._selected = widget.index
                    self._rebuild_list()
                return
            if widget in (self, None):
                self.dismiss(None)

        def on_key(self, event):
            if event.key == "escape":
                self.dismiss(None)

        def action_cancel(self):
            self.dismiss(None)

        def action_move_down_sel(self):
            if self._providers:
                self._selected = min(self._selected + 1, len(self._providers) - 1)
                self._rebuild_list()

        def action_move_up_sel(self):
            if self._providers:
                self._selected = max(self._selected - 1, 0)
                self._rebuild_list()

        def _current(self):
            if not self._providers:
                return None
            return self._providers[min(self._selected, len(self._providers) - 1)]

        def on_button_pressed(self, event):
            eid = event.button.id
            if eid in ("bpp-cancel", "bpp-close"):
                self.dismiss(None)
            elif eid == "bpp-add":
                self.app.push_screen(_AddProviderForm(), self._on_saved)
            elif eid == "bpp-add-ollama":
                # v0.7.9.5: Quick-add Ollama as a backup provider
                self._add_ollama_backup()
            elif eid == "bpp-edit":
                entry = self._current()
                if entry:
                    self.app.push_screen(_AddProviderForm(entry), self._on_saved)
            elif eid == "bpp-remove":
                if self._providers:
                    del self._providers[self._selected]
                    self._selected = min(self._selected, max(0, len(self._providers) - 1))
                    self._rebuild_list()
            elif eid == "bpp-up":
                if self._selected > 0:
                    self._providers[self._selected], self._providers[self._selected - 1] = \
                        self._providers[self._selected - 1], self._providers[self._selected]
                    self._selected -= 1
                    self._rebuild_list()
            elif eid == "bpp-down":
                if self._selected < len(self._providers) - 1:
                    self._providers[self._selected], self._providers[self._selected + 1] = \
                        self._providers[self._selected + 1], self._providers[self._selected]
                    self._selected += 1
                    self._rebuild_list()
            elif eid == "bpp-test":
                self._test_selected()
            elif eid == "bpp-toggle":
                entry = self._current()
                if entry:
                    entry["enabled"] = not bool(entry.get("enabled", True))
                    self._rebuild_list()
            elif eid == "bpp-save":
                self._persist()
                self.dismiss(None)
            elif eid == "bpp-apply":
                self._persist()

        def _add_ollama_backup(self):
            """Quick-add Ollama as a backup provider, supporting multiple models.
            
            Discovers available models from local Ollama and selects the next
            unconfigured model, allowing users to add multiple local models
            (e.g. deepseek-r1, qwen2.5-coder, gemma4) without getting locked out.
            """
            # Collect models currently configured for Ollama
            configured_models = {
                entry.get("model")
                for entry in self._providers
                if (entry.get("provider") or "").lower() == "ollama" and entry.get("model")
            }
            
            # Try to discover available models from local Ollama
            available = []
            try:
                import requests
                resp = requests.get("http://localhost:11434/api/tags", timeout=3)
                if resp.status_code == 200:
                    data = resp.json()
                    available = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
            except Exception:
                pass
            
            # Prefer unconfigured models from local Ollama
            unconfigured_local = [m for m in available if m not in configured_models]
            
            common_candidates = [
                "llama3.3", "deepseek-r1:latest", "qwen2.5-coder:latest",
                "gemma4:e4b", "llama3.2", "mistral", "phi3", "qwen2.5"
            ]
            unconfigured_common = [m for m in common_candidates if m not in configured_models]
            
            if unconfigured_local:
                # Prioritize coding and reasoning models if available
                preferred = ["qwen2.5", "deepseek", "llama3.3", "gemma", "mistral"]
                chosen_model = None
                for pref in preferred:
                    match = next((m for m in unconfigured_local if pref in m.lower()), None)
                    if match:
                        chosen_model = match
                        break
                if not chosen_model:
                    chosen_model = unconfigured_local[0]
            elif unconfigured_common:
                chosen_model = unconfigured_common[0]
            else:
                # All detected and common models already configured: add custom named model
                chosen_model = f"ollama-model-{len(configured_models) + 1}"
            
            # Add Ollama model entry to backup providers
            ollama_entry = {
                "provider": "ollama",
                "model": chosen_model,
                "api_key": "",
                "base_url": "http://localhost:11434",
                "api_style": "ollama",
                "name": f"Ollama ({chosen_model})",
                "enabled": True,
                "status": "connected" if available else "disconnected",
                "last_used": 0,
                "priority": len(self._providers)
            }
            
            self._providers.append(ollama_entry)
            self._selected = len(self._providers) - 1
            self._rebuild_list()
            
            # Show success message
            try:
                local_cnt = len(available)
                extra = f" ({local_cnt} local models detected)" if local_cnt else ""
                self.app._system_note(
                    f"Added Ollama backup model: '{chosen_model}'{extra}. "
                    f"Total backups: {len(self._providers)}."
                )
            except Exception:
                pass

        def _persist(self):
            pm.save_backup_providers(self._providers)
            try:
                self.app._system_note(
                    f"\u2713 Backup providers saved \u2014 {len(self._providers)} in the failover chain.")
            except Exception:
                pass

        def _test_selected(self):
            entry = self._current()
            if not entry:
                return
            entry["status"] = "testing"
            entry["latency_ms"] = None
            self._rebuild_list()
            config = {
                "provider": entry.get("provider", ""),
                "model": entry.get("model", ""),
                "api_key": entry.get("api_key", ""),
                "base_url": entry.get("base_url", ""),
                "api_style": entry.get("api_style", "openai"),
            }
            start = time.time()

            def _run():
                ok, msg, models = pm.test_provider_connectivity(config)
                entry["status"] = "connected" if ok else "failed"
                if ok:
                    entry["last_used"] = int(time.time())
                    entry["latency_ms"] = int((time.time() - start) * 1000)
                self.app.call_from_thread(self._rebuild_list)
                try:
                    note = self.app._system_note if hasattr(self.app, "_system_note") else None
                    if note:
                        note(f"Backup provider test: {msg}")
                except Exception:
                    pass

            threading.Thread(target=_run, daemon=True).start()

        def _on_saved(self, entry):
            if not entry:
                return
            self._providers.append(entry)
            self._selected = len(self._providers) - 1
            self._rebuild_list()


    class _AddProviderForm(Screen):
        """Add/Edit backup provider popup (v0.7.8.1 redesign): centered
        and animated, equal-width buttons, Test Connection, and an
        Enable-by-default toggle. Pass an existing entry to edit."""

        CSS = """
        _AddProviderForm { align: center middle; background: $app-background 70%; }
        #apf-box {
            width: 62; height: auto; max-height: 92%; background: $surface;
            border: round $border; padding: 0;
            opacity: 0; offset-y: 1;
            transition: opacity 150ms, offset 180ms;
        }
        #apf-box.open { opacity: 1; offset-y: 0; }
        #apf-titlebar { height: 3; padding: 1 2 0 2; border-bottom: solid $border; }
        #apf-title { text-style: bold; width: 1fr; }
        #apf-body { padding: 1 2; overflow-y: auto; scrollbar-gutter: stable; }
        #apf-status { color: $text-faint; height: 1; padding-top: 1; }
        #apf-actions { height: 5; padding: 0 2 1 2; border-top: solid $border; }
        #apf-actions Button { margin-right: 1; width: 1fr; min-width: 10; }
        .apf-hint { color: $text-faint; padding: 0 2 1 2; }
        #apf-box.cct-compact .apf-hint { display: none; }
        """

        BINDINGS = [Binding("escape", "cancel", "Cancel")]

        def __init__(self, entry=None):
            super().__init__()
            self._entry = entry or {}
            self._enabled = bool(entry.get("enabled", True)) if entry else True

        def compose(self):
            with Vertical(id="apf-box"):
                with Horizontal(id="apf-titlebar"):
                    yield Static("Add Backup Provider" if not self._entry
                                 else "Edit Backup Provider", id="apf-title")
                    yield Button("\u2715", id="apf-close", classes="cct-popup-close")
                with Vertical(id="apf-body"):
                    yield Static("Company (provider id, e.g. openai / anthropic / gemini)",
                                 classes="cct-field-label")
                    yield Input(placeholder="openai", id="apf-provider",
                                value=self._entry.get("provider", ""))
                    yield Static("Model", classes="cct-field-label")
                    yield Input(placeholder="gpt-4o-mini", id="apf-model",
                                value=self._entry.get("model", ""))
                    yield Static("API Key", classes="cct-field-label")
                    yield Input(placeholder="sk-...", id="apf-key", password=True,
                                value=self._entry.get("api_key", ""))
                    yield Static("Base URL (optional)", classes="cct-field-label")
                    yield Input(placeholder="https://api.openai.com/v1", id="apf-url",
                                value=self._entry.get("base_url", ""))
                    yield Static("Fallback enabled", classes="cct-field-label")
                    yield Button("\u2713 Enabled" if self._enabled else "\u00d7 Disabled",
                                 id="apf-enable", classes="cct-btn cct-btn-sm")
                    yield Static("", id="apf-status")
                with Horizontal(id="apf-actions"):
                    yield Button("\u2699 Test", id="apf-test", classes="cct-btn")
                    yield Button("Add", id="apf-add", variant="primary", classes="cct-btn")
                    yield Button("Cancel", id="apf-cancel", classes="cct-btn")
                yield Static("Enter to confirm  \u00b7  Esc to cancel", classes="apf-hint")

        def _refresh_enable(self):
            try:
                btn = self.query_one("#apf-enable", Button)
                btn.label = "\u2713 Enabled" if self._enabled else "\u00d7 Disabled"
                btn.variant = "primary" if self._enabled else "default"
            except Exception:
                pass

        def on_mount(self):
            self._refresh_enable()
            self.call_after_refresh(lambda: self.query_one("#apf-box").add_class("open"))
            self.call_after_refresh(self._fit)
            try:
                self.query_one("#apf-provider", Input).focus()
            except Exception:
                pass

        def on_resize(self, event):
            self._fit()

        def _fit(self):
            try:
                self.call_after_refresh(
                    lambda: theme_css.fit_dialog(self, "apf-box", "apf-body"))
            except Exception:
                pass

        def action_cancel(self):
            self.dismiss(None)

        def on_button_pressed(self, event):
            eid = event.button.id
            if eid == "apf-add":
                self._submit()
            elif eid in ("apf-cancel", "apf-close"):
                self.dismiss(None)
            elif eid == "apf-enable":
                self._enabled = not self._enabled
                self._refresh_enable()
            elif eid == "apf-test":
                self._test()

        def on_key(self, event):
            if event.key == "escape":
                self.dismiss(None)

        def on_input_submitted(self, event):
            self._submit()

        def _collect(self):
            provider = self.query_one("#apf-provider", Input).value.strip()
            model = self.query_one("#apf-model", Input).value.strip()
            key = self.query_one("#apf-key", Input).value.strip()
            url = self.query_one("#apf-url", Input).value.strip()
            entry = dict(self._entry)
            entry.update({
                "provider": provider.lower(),
                "model": model,
                "api_key": key,
                "base_url": url,
                "api_style": "ollama" if url.endswith("11434") else "openai",
                "enabled": self._enabled,
                "status": "disconnected",
            })
            return entry

        def _submit(self):
            entry = self._collect()
            if not entry.get("provider") or not entry.get("model"):
                self.query_one("#apf-status", Static).update(
                    f"[{theme_css.current_hex('error')}]\u2717 Provider and model are required[/]")
                return
            self.dismiss(entry)

        def _test(self):
            entry = self._collect()
            if not entry.get("provider") or not entry.get("model"):
                self.query_one("#apf-status", Static).update(
                    f"[{theme_css.current_hex('error')}]\u2717 Provider and model are required[/]")
                return
            status = self.query_one("#apf-status", Static)
            status.update(f"[{theme_css.current_hex('warning')}]\U0001f7e1 Testing\u2026[/]")
            config = {
                "provider": entry.get("provider", ""),
                "model": entry.get("model", ""),
                "api_key": entry.get("api_key", ""),
                "base_url": entry.get("base_url", ""),
                "api_style": entry.get("api_style", "openai"),
            }

            def _run():
                try:
                    ok, msg, _models = pm.connect_provider(config)
                except Exception as e:
                    ok, msg = False, str(e)
                self.app.call_from_thread(
                    lambda: status.update(
                        f"[{theme_css.current_hex('success' if ok else 'error')}]"
                        f"{'\u2713' if ok else '\u2717'} {msg}[/]"))

            threading.Thread(target=_run, daemon=True).start()


    def ensure_provider_configs(config):
        """Merge the user's saved backups into a request config dict —
        convenience for future aicore integrations; kept tiny on purpose."""
        return config

else:
    BackupProvidersPanel = None
    _AddProviderForm = None
