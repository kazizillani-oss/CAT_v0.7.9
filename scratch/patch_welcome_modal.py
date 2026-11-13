import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('calc_terminal/ui/welcome_modal.py', 'r', encoding='utf-8') as f:
    text = f.read().replace('\r\n', '\n')

old_code = '        def _render_bar(self, fraction: float) -> str:'
new_code = '''        def _render_fomoji_line(self) -> str:
            try:
                from ..fomoji_manager import get_fomoji_runtime_state
                state = get_fomoji_runtime_state()
                if state.get("ready"):
                    return f"● Fomoji Server Online (Port {state.get('port', 3000)})"
                elif state.get("status") == "starting":
                    step = state.get("step") or "starting"
                    return f"⟳ Fomoji Server: {step} (Port {state.get('port', 3000)})"
            except Exception:
                pass
            return "○ Fomoji Server Offline"

        def _render_bar(self, fraction: float) -> str:'''

if '_render_fomoji_line' not in text:
    assert old_code in text
    text = text.replace(old_code, new_code, 1)
    with open('calc_terminal/ui/welcome_modal.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('SUCCESS: added _render_fomoji_line to welcome_modal.py')
else:
    print('Already present')

