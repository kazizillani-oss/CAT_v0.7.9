import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('calc_terminal/ui/startup_loader.py', 'r', encoding='utf-8') as f:
    text = f.read().replace('\r\n', '\n')

old_code = '    def _render_bar(self, fraction: float) -> str:'
new_code = '''    def _render_fomoji_badge(self) -> str:
        try:
            from ..fomoji_manager import get_fomoji_runtime_state
            state = get_fomoji_runtime_state()
            if state.get("ready"):
                return f"[#a6e3a1]● Fomoji Server Online (Port {state.get('port', 3000)})[/]"
            elif state.get("status") == "starting":
                step = state.get("step") or "starting"
                return f"[#f9e2af]⟳ Fomoji Server: {step} (Port {state.get('port', 3000)})[/]"
        except Exception:
            pass
        return "[dim]○ Fomoji Server Offline[/dim]"

    def _render_bar(self, fraction: float) -> str:'''

if '_render_fomoji_badge' not in text:
    assert old_code in text
    text = text.replace(old_code, new_code, 1)
    with open('calc_terminal/ui/startup_loader.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('SUCCESS: added _render_fomoji_badge to startup_loader.py')
else:
    print('Already present')
