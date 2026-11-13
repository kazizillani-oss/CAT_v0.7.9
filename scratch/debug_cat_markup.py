import traceback
from calc_terminal.ui.dashboard import WelcomeDashboard

d = WelcomeDashboard()
try:
    m = d._cat_section_markup(mode_key="build")
    print("Result:", m)
except Exception:
    traceback.print_exc()

