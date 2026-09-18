
import sys
sys.path.insert(0,".")
from calc_terminal import fallback_cli
raw = fallback_cli.fallback_input(width=78, show_tip=True, mode_label="NOTEBOOK", model_label="TEST MODEL", effort_label="ready", animate=False)
sys.stderr.write("RESULT:" + repr(raw) + chr(10))
