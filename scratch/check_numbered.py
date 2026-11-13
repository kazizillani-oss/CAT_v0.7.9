import sys
sys.stdout.reconfigure(encoding='utf-8')

from calc_terminal.ui.cat_greeting import GREETINGS_NUMBERED
print("Length of GREETINGS_NUMBERED:", len(GREETINGS_NUMBERED))
print("Last 5 items:", GREETINGS_NUMBERED[-5:])

