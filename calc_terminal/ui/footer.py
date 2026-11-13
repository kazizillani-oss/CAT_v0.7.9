"""
CCT UI — ComposerFooter (the composer's BOTTOM STATUS ROW docked inside
StickyComposer: [Attachment] bottom-left, `MODEL: provider · model` +
live context readout in the center, [Microphone] [Send/Stop] bottom-right
— proper separated 3D physical buttons, never touching) and StatusLine
(the compact bar CCTApp docks at the very bottom of the screen). Both
render state and dispatch events/bubble presses to their parent —
neither decides what a click means.

v0.9.000 composer repair: the ⏱ Permissions button and 🛡 Security
mode button were REMOVED from the composer altogether. Permission
management stays fully intact in the header's permission pill
(PermissionModeMenu: Ask Every Time / Full Access / Restricted Access),
the `/permissions` slash command and Alt+P (PermissionsSettingsPanel);
microphone permission is a separate machine-access concern owned by
voice.py's check_permission(), not a footer button.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

TEXTUAL_AVAILABLE = True
try:
    from textual.containers import Horizontal
    from textual.widgets import Static, Button
    from textual.reactive import reactive
except Exception:
    TEXTUAL_AVAILABLE = False

from .events import CommandExecuted


if TEXTUAL_AVAILABLE:

    def _hex_blend(h1, h2, t):
        """Linear interpolate two '#rrggbb' hex colors at t in [0, 1].
        Returns a '#rrggbb' hex string — local helper so the mode badge
        can render its 4-segment gradient bar without reaching into
        theme internals (theme.blend takes RGB tuples, not hex)."""
        a = [int(h1[i:i + 2], 16) for i in (1, 3, 5)]
        b = [int(h2[i:i + 2], 16) for i in (1, 3, 5)]
        return "#" + "".join(f"{int(round(x + (y - x) * t)):02x}"
                             for x, y in zip(a, b))

    def _safe_glyph(emoji, fallback):
        return emoji

    class _Badge(Static):
        """One flat, clickable text badge (no border/background chrome) —
        the `Notebook` / `provider model` / `Workspace` pieces of
        `NOTEBOOK \u00b7 openai/gpt-4o-mini \u00b7 Workspace`."""

        def __init__(self, text, badge_id, on_click=None, classes="cct-badge"):
            super().__init__(text, id=badge_id, classes=classes)
            self._on_click = on_click
            self._text = text

        @property
        def renderable(self):
            return getattr(self, "_renderable", getattr(self, "_text", ""))

        def update(self, renderable):
            self._text = renderable
            super().update(renderable)

        def on_click(self, event):
            event.stop()
            if self._on_click:
                self._on_click()

    class ComposerFooter(Horizontal):
        """The composer's BOTTOM STATUS ROW: [📎 Attach] bottom-left,
        `MODEL: provider · model` + live context status in the center,
        [🎙 Mic] [Send/Stop] bottom-right — one row, one component.
        Permission/security controls are NOT here (moved to the header
        pill + /permissions); see the module docstring."""

        # Holds the AI-mode KEY ("notebook"/"agent"/"build"/"plan" — see
        # ai_modes.py). Kept as a settable attribute so StickyComposer's
        # set_ai_mode/_toggle_notebook syncs stay compatible.
        notebook_mode = reactive("notebook")
        context_tokens = reactive(0)

        # The ACTIVE provider + model render inside `#badge-model`.
        # (provider, model) arrive from StickyComposer — loaded from
        # aicore config, or overridden live while a failover backup
        # provider is the one actually serving.
        _prov = ""
        _mdl = ""
        _model_is_backup = False

        def __init__(self, model_label="no model"):
            super().__init__(id="cct-bottom-row")
            self._model_label = model_label
            try:
                from .. import ai_modes, aicore
                self.notebook_mode = ai_modes.current_mode() or "agent"
                cfg = aicore.load_config() or {}
                self._prov = cfg.get("provider", "OLLAMA")
                self._mdl = cfg.get("model", "deepseek-r1:latest")
            except Exception:
                self.notebook_mode = "agent"
                self._prov = "OLLAMA"
                self._mdl = "deepseek-r1:latest"

        def _mode_badge_markup(self, mode_key):
            from .. import ai_modes
            accent = ai_modes.accent_hex(mode_key)
            m = ai_modes.meta(mode_key)
            raw_icon = m.get("icon", "")
            if raw_icon in ("🛠️", "🛠"):
                raw_icon = "🔨"
            clean_icon = raw_icon.replace("\ufe0f", "")
            safe_icon = _safe_glyph(clean_icon, "[M]")
            try:
                from . import theme_css as _tc
                faint = _tc.current_hex("text-faint")
            except Exception:
                faint = "#6e7594"
            try:
                gs, ge = ai_modes.gradient(mode_key)
                bar = "".join(f"[{_hex_blend(gs, ge, t)}]\u25ae[/]" for t in (0.0, 0.33, 0.66, 1.0))
                return f"{bar} [{gs} b]{safe_icon}[/] [{ge} b]{m['label']}[/] [{faint}]\u25be[/]"
            except Exception:
                return f"[{accent} b]{safe_icon} {m['label']}[/] [{faint}]\u25be[/]"

        def _toggle_notebook(self):
            self.post_message(CommandExecuted("/mode"))

        def watch_notebook_mode(self, value):
            try:
                self.query_one("#badge-notebook", _Badge).update(self._mode_badge_markup(value))
            except Exception:
                pass

        def compose(self):
            # ── BOTTOM LEFT: attachment ONLY (permissions & security removed) ──
            with Horizontal(id="cct-composer-left", classes="cct-toolbar-left"):
                yield Button(_safe_glyph("🔗", "(+)"), id="btn-attach",
                             classes="cct-ctl-btn cct-icon-btn", tooltip="Attach file (Click / Alt+A)")
            # ── BOTTOM CENTER: AI agent mode + model indicator + context status ──
            with Horizontal(id="cct-toolbar-center"):
                yield _Badge(self._mode_badge_markup(self.notebook_mode),
                             "badge-notebook", self._toggle_notebook, classes="cct-badge-mode")
                yield Static("·", classes="cct-badge-sep")
                yield _Badge(self._model_badge_label(80), "badge-model", self._open_model)
                yield Static(self._status_text(80), id="cct-center-status")
            # ── BOTTOM RIGHT: microphone + Send/Stop ──
            with Horizontal(id="cct-right-controls", classes="cct-composer-right cct-toolbar-right"):
                yield Button(_safe_glyph("🎙", "(V)"), id="btn-mic", classes="cct-ctl-btn cct-icon-btn",
                             tooltip="Voice mode (Click / /voice) — separate from AI tool permissions")
                yield Button(_safe_glyph("■", "Stop"), id="btn-stop",
                             classes="cct-ctl-stop cct-btn-stop", tooltip="Stop generating (Esc)")
                yield Button(_safe_glyph("➤", ">"), id="btn-send",
                             classes="cct-ctl-send cct-icon-btn cct-icon-send", tooltip="Send message (Enter)")

        def on_mount(self):
            # IDLE state: [Mic][Send]; the Stop button only mounts
            # visible while a generation is actually running
            # (StickyComposer.set_streaming drives display both ways).
            try:
                self.query_one("#btn-stop", Button).display = False
            except Exception:
                pass
            try:
                from .. import ai_modes, aicore
                current = ai_modes.current_mode() or "agent"
                self.notebook_mode = current
                self.query_one("#badge-notebook", _Badge).update(self._mode_badge_markup(current))
                if not self._mdl or not self._prov:
                    cfg = aicore.load_config() or {}
                    self._prov = cfg.get("provider", "OLLAMA")
                    self._mdl = cfg.get("model", "deepseek-r1:latest")
                self._render_model_badge()
            except Exception:
                pass

        def _status_text(self, w=80):
            if w and w < 75:
                return f"{self.context_tokens}K" if self.context_tokens else "OK"
            return f"Context {self.context_tokens}K" if self.context_tokens else "Context OK"

        def watch_context_tokens(self, value):
            try:
                w = getattr(getattr(self, "size", None), "width", 80)
                status = self.query_one("#cct-center-status", Static)
                status.update(self._status_text(w))
                status.tooltip = "Live context usage for this chat (thousands of tokens)."
            except Exception:
                pass

        @property
        def _clean_model(self):
            clean = self._mdl or ""
            for prefix in ("OLLAMA ", "OPENROUTER ", "OPENAI ", "GEMINI ", 
                           "ANTHROPIC ", "GROQ ", "OPENCODE "):
                if clean.upper().startswith(prefix):
                    clean = clean[len(prefix):]
                    break
            return clean

        def _model_badge_label(self, w):
            """Responsive model indicator text: `MODEL: provider · model`
            shortened at narrow widths so the BADGE collapses before it
            can ever clip the right cluster off-screen."""
            accent = ""
            from . import theme_css as _tc
            accent = _tc.current_hex("accent")
            if not self._mdl and not self._prov:
                return f"[{_tc.current_hex('warning')}]MODEL unavailable[/]"
            prov = self._prov or "—"
            clean = self._clean_model or self._mdl
            base = f"[{_tc.current_hex('text-faint')}]MODEL:[/] "
            if self._model_is_backup:
                base = f"[{_tc.current_hex('warning')}]MODEL (backup):[/] "
            if w and w < 60:
                return f"[b {accent}]{clean[:8]}{'…' if len(clean) > 8 else ''}[/]"
            if w and w < 75:
                return base + f"[b {accent}]{clean[:10]}{'…' if len(clean) > 10 else ''}[/]"
            if w and w < 96:
                return (base + f"[{_tc.current_hex('text-faint')}]{prov.lower()}[/]"
                        f"[{_tc.current_hex('text-faint')}] \u00b7[/] [b {accent}]{clean[:15]}{'…' if len(clean) > 15 else ''}[/]")
            return (base + f"[{_tc.current_hex('text-faint')}]{prov.lower()}[/]"
                    f"[{_tc.current_hex('text-faint')}] \u00b7[/] [b {accent}]{clean}[/]")

        def set_provider_model(self, provider, model, is_backup=False):
            """Single setter the composer uses; re-renders the badge for
            the CURRENT width and records the backup flag. An empty pair
            is preserved: `#badge-model` then renders the honest
            'MODEL unavailable' state (never a stale name)."""
            self._prov = (provider or "").strip()
            self._mdl = (model or "").strip()
            self._model_is_backup = bool(is_backup)
            self._render_model_badge()

        def _render_model_badge(self):
            try:
                w = getattr(getattr(self, "size", None), "width", 80)
                self.query_one("#badge-model", _Badge).update(self._model_badge_label(w))
            except Exception:
                pass

        def set_model_label(self, label):
            """Legacy shim: 'PROVIDER MODEL' string → set_provider_model."""
            text = (label or "").strip()
            parts = text.split(" ", 1)
            if len(parts) == 2:
                self.set_provider_model(parts[0], parts[1])
            elif parts:
                self.set_provider_model("", parts[0])
            else:
                self.set_provider_model("", "")
            self._render_model_badge()

        def _open_model(self):
            self.post_message(CommandExecuted("/model"))

        def on_resize(self, event=None):
            """Responsive footer collapse at narrow viewports: ensures all
            clusters and buttons remain visible and never clip."""
            w = (event.size.width if event else None) or (self.size.width if self.size else 80)
            try:
                center = self.query_one("#cct-center-status", Static)
                center.display = (w >= 50)
                if w >= 50:
                    center.update(self._status_text(w))
            except Exception:
                pass
            try:
                model_badge = self.query_one("#badge-model", _Badge)
                model_badge.display = (w >= 34)
                model_badge.update(self._model_badge_label(w))
            except Exception:
                pass
            try:
                attach_btn = self.query_one("#btn-attach", Button)
                mic_btn = self.query_one("#btn-mic", Button)
                send_btn = self.query_one("#btn-send", Button)
                attach_btn.display = True
                mic_btn.display = True
                send_btn.display = True
            except Exception:
                pass
            try:
                nb_badge = self.query_one("#badge-notebook", _Badge)
                nb_badge.display = True
            except Exception:
                pass
            self._render_model_badge()

    class StatusLine(Static):
        """One compact bottom status line for the whole app — no boxes,
        no oversized labels. `get_fields` is a zero-arg callable
        returning [(label, value, tone), ...]; CCTApp supplies it and
        calls `refresh_status()` when something worth showing changes,
        instead of this widget reaching into backend state itself."""

        def __init__(self, get_fields, id="cct-statusline"):
            super().__init__(id=id)
            self._get_fields = get_fields

        def on_mount(self):
            self.refresh_status()

        def refresh_status(self):
            from . import theme_css
            tone_role = {"ready": "success", "warn": "warning", "err": "error", "": "text-muted"}
            parts = []
            for label, value, tone in self._get_fields():
                color = theme_css.current_hex(tone_role.get(tone, "text-muted"))
                text = f"[{color}]{value}[/]" if not label else f"{label} [{color}]{value}[/]"
                parts.append(text)
            new_text = "   \u00b7   ".join(parts)
            if getattr(self, "_last_rendered_text", None) == new_text:
                return
            self._last_rendered_text = new_text
            self.update(new_text)

else:
    ComposerFooter = None
    StatusLine = None

