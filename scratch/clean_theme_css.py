import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9"
p = os.path.join(ROOT, "calc_terminal/ui/theme_css.py")
with open(p, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Remove the appended lines from line 2083
lines = lines[:2083]

with open(p, "w", encoding="utf-8") as f:
    f.writelines(lines)
print(f"Truncated back to {len(lines)} lines")

# Check for syntax error
import py_compile
try:
    py_compile.compile(p, doraise=True)
    print("theme_css.py compiles with NO syntax errors!")
except Exception as e:
    print(f"Compile error: {e}")
