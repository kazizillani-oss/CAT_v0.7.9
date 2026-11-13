import traceback
from calc_terminal.ui.dashboard import WelcomeDashboard

dash = WelcomeDashboard(logo_lines=[], version="0.7.9.0", model_label="test", notebook_count=1)
try:
    # Test without try/except in _cat_section_markup
    w, h = dash._get_viewport_size()
    print("w, h:", w, h)
except Exception:
    traceback.print_exc()

try:
    markup = dash._cat_section_markup(mode_key="build")
    print("Markup:", repr(markup))
except Exception:
    traceback.print_exc()

