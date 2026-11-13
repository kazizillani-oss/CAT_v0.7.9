import sys
sys.path.insert(0, '.')
import asyncio
from textual.app import App, ComposeResult
from calc_terminal.ui import theme_css, app as cct_app
from calc_terminal.ui.header import BrandHeader
from calc_terminal.ui.conversation import ConversationView
from scratch.prototype_new_composer import PrototypeComposer

class FullApp(App):
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
        yield ConversationView(id="cct-conversation")
        yield PrototypeComposer()

async def main():
    for w in [100, 50]:
        app = FullApp()
        async with app.run_test(size=(w, 25)) as pilot:
            await pilot.pause(0.05)
            comp = app.query_one(PrototypeComposer)
            conv = app.query_one(ConversationView)
            print(f"=== FullApp Size {w}x25 ===")
            print(f"  Conversation: {conv.region}")
            print(f"  Composer:     {comp.region}")
            print(f"  Context bar:  {comp.query_one('#cct-composer-context-bar').region}")
            print(f"  Prompt row:   {comp.query_one('#cct-prompt-row').region}")
            print(f"  Footer row:   {comp.query_one('#cct-bottom-row').region}")

if __name__ == "__main__":
    asyncio.run(main())
