import asyncio
from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal, Container
from textual.widgets import Static, Button, TextArea
from textual.reactive import reactive
from calc_terminal.ui import theme_css, app as cct_app
from calc_terminal.ui.header import BrandHeader
from calc_terminal.ui.composer import PromptIndicator, ComposerInput
from calc_terminal.ui.command_palette import CommandPalette
from calc_terminal.ui.attachments import AttachmentBar
from calc_terminal.ui.permission_panel import PermissionsSettingsPanel
from calc_terminal import aicore, ai_modes

def _safe_glyph(emoji: str, fallback: str) -> str:
    return emoji

class PrototypeBadge(Static):
    def __init__(self, text, badge_id, on_click=None, classes="cct-badge"):
        super().__init__(text, id=badge_id, classes=classes)
        self._on_click = on_click
    def on_click(self, event):
        event.stop()
        if self._on_click:
            self._on_click()

class PrototypeFooter(Horizontal):
    notebook_mode = reactive("build")
    context_tokens = reactive(0)

    def __init__(self, model_label="no model"):
        super().__init__(id="cct-bottom-row", classes="cct-composer-toolbar")
        self._model_label = model_label

    def compose(self) -> ComposeResult:
        with Horizontal(id="cct-composer-left", classes="cct-toolbar-left"):
            yield Button(_safe_glyph("🔗", "(+)"), id="btn-attach", classes="cct-icon-btn", tooltip="Attach file (Alt+A)")
            yield Button(_safe_glyph("⏱", "(P)"), id="btn-permissions", classes="cct-icon-btn", tooltip="Permissions (Alt+P)")
            yield Button(_safe_glyph("🛡️", "[S]"), id="btn-security", classes="cct-icon-btn", tooltip="Security mode (Click to cycle)")
        with Horizontal(id="cct-toolbar-center"):
            yield Static("Context OK", id="cct-center-status")
        with Horizontal(id="cct-right-controls", classes="cct-composer-right cct-toolbar-right"):
            yield Button(_safe_glyph("🎙", "(V)"), id="btn-mic", classes="cct-icon-btn", tooltip="Voice mode (/voice)")
            yield Button(_safe_glyph("■", "Stop"), id="btn-stop", classes="cct-icon-btn cct-btn-stop", tooltip="Stop response (Esc)")
            yield Button(_safe_glyph("➤", ">"), id="btn-send", classes="cct-icon-btn cct-icon-send", tooltip="Send message (Enter)")

    def set_model_label(self, label):
        self._model_label = label

class PrototypeComposer(Vertical):
    notebook_mode = reactive("build")

    def __init__(self, id="cct-composer", model_label="no model"):
        super().__init__(id=id)
        self._model_label = model_label

    def _get_provider_and_model(self):
        cfg = aicore.load_config()
        p = (cfg.get("provider") or "OLLAMA").upper()
        m = cfg.get("model") or "deepseek-r1:latest"
        return p, m

    def _mode_badge_markup(self, mode_key):
        accent = ai_modes.accent_hex(mode_key)
        m = ai_modes.meta(mode_key)
        raw_icon = m.get('icon', '🔨').replace('\ufe0f', '')
        return f"[{accent} b]{raw_icon} {m['label']}[/]"

    def compose(self) -> ComposeResult:
        # Tier 1: Context Header Bar
        prov, mdl = self._get_provider_and_model()
        with Horizontal(id="cct-composer-context-bar"):
            with Horizontal(id="cct-context-left"):
                yield PrototypeBadge(self._mode_badge_markup(self.notebook_mode), "badge-notebook")
                yield Static("·", classes="cct-badge-sep")
                yield PrototypeBadge(f"[{prov}]", "badge-provider")
                yield Static("·", classes="cct-badge-sep")
                yield PrototypeBadge(f"[bold]{mdl}[/]", "badge-model")
            yield Static(id="cct-context-spacer")
            yield Static("[bold #a6e3a1]● Ready[/]", id="badge-status", classes="cct-context-status")

        # Tier 2: Recessed Input Well
        with Horizontal(id="cct-prompt-row"):
            yield PromptIndicator()
            with Container(id="cct-editor-stack"):
                editor = ComposerInput(id="cct-input", composer_ref=self)
                editor.show_line_numbers = False
                editor.highlight_cursor_line = False
                yield editor

        # Hidden strips
        with Horizontal(id="cct-voice-strip"):
            yield Static("🎙 [REC 00:00]", id="cct-voice-status")
        with Horizontal(id="cct-streaming-row"):
            yield Static("", id="cct-streaming-status")
            yield Button("■ Stop", id="btn-streaming-stop")

        yield Static("", id="cct-edit-banner")
        yield Static("", id="cct-latex-preview")
        yield CommandPalette()
        yield AttachmentBar()

        # Tier 3: Bottom Control Toolbar
        yield PrototypeFooter(model_label=self._model_label)
        yield PermissionsSettingsPanel()

    def on_mount(self):
        try:
            self.query_one("#btn-stop").display = False
            self.query_one("#cct-voice-strip").display = False
            self.query_one("#cct-streaming-row").display = False
        except Exception:
            pass

class PrototypeApp(App):
    CSS = theme_css.BASE_CSS + cct_app._COMPONENT_CSS + """
    #cct-composer-context-bar {
        height: 1;
        min-height: 1;
        max-height: 1;
        width: 100%;
        background: #141520;
        border-bottom: solid #222436;
        padding: 0 1;
        layout: horizontal;
        align: left middle;
    }
    #cct-context-left {
        width: auto;
        height: 1;
        layout: horizontal;
        align: left middle;
    }
    #cct-context-spacer {
        width: 1fr;
        height: 1;
    }
    .cct-context-status {
        width: auto;
        height: 1;
        content-align: right middle;
    }
    #cct-prompt-row {
        height: auto;
        min-height: 2;
        width: 100%;
        background: #12131d;
        border: none;
        padding: 0 1;
        layout: horizontal;
    }
    #cct-bottom-row {
        height: 1;
        min-height: 1;
        max-height: 1;
        width: 100%;
        background: #161724;
        border: none;
        padding: 0 1;
        layout: horizontal;
        align: left middle;
    }
    #cct-composer-left {
        width: auto;
        height: 1;
        layout: horizontal;
        align: left middle;
    }
    #cct-toolbar-center {
        width: 1fr;
        height: 1;
        layout: horizontal;
        align: center middle;
    }
    #cct-right-controls {
        width: auto;
        height: 1;
        layout: horizontal;
        align: right middle;
        margin-right: 0;
    }
    Button.cct-icon-btn, Button#btn-attach, Button#btn-permissions, Button#btn-security, Button#btn-mic, Button#btn-send {
        height: 1;
        min-height: 1;
        max-height: 1;
        border: none;
        padding: 0 1;
        margin: 0;
        min-width: 3;
    }
    Button#btn-send {
        background: #e0af68;
        color: #12131d;
        text-style: bold;
    }
    """
    def get_css_variables(self):
        v = super().get_css_variables()
        v.update(theme_css.css_variables())
        return v
    def compose(self) -> ComposeResult:
        yield BrandHeader()
        yield PrototypeComposer()

async def main():
    for w, h in [(100, 30), (50, 30)]:
        app = PrototypeApp()
        async with app.run_test(size=(w, h)) as pilot:
            hdr = app.query_one(BrandHeader)
            hdr.on_resize()
            comp = app.query_one(PrototypeComposer)
            await pilot.pause(0.05)
            print(f"=== Prototype Size {w}x{h} ===")
            print(f"Header: {hdr.region}")
            print(f"Composer: {comp.region}")
            ctx_bar = comp.query_one("#cct-composer-context-bar")
            prompt_row = comp.query_one("#cct-prompt-row")
            footer = comp.query_one("#cct-bottom-row")
            print(f"  Context bar: {ctx_bar.region}")
            print(f"  Prompt row:  {prompt_row.region}")
            print(f"  Footer:      {footer.region}")
            for wid in ["badge-notebook", "badge-provider", "badge-model", "badge-status",
                        "btn-attach", "btn-permissions", "btn-security", "btn-mic", "btn-send"]:
                try:
                    w_obj = comp.query_one(f"#{wid}")
                    print(f"    {wid}: region={w_obj.region}, display={w_obj.display}")
                except Exception as e:
                    print(f"    {wid}: NOT FOUND {e}")

if __name__ == "__main__":
    asyncio.run(main())
