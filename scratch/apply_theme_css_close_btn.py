PATH = r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9\calc_terminal\ui\theme_css.py"

with open(PATH, "r", encoding="utf-8") as f:
    code = f.read()

target = """/* 3D Skeuomorphic Modal Close Button */
.cct-modal-close-btn,
Button.cct-modal-close-btn {
    height: 3; min-height: 3; max-height: 3;
    min-width: 9; max-width: 12;
    padding: 0 1;
    margin: 0;
    border: tall;
    border-top: tall #ffa198;
    border-left: tall #ffa198;
    border-bottom: tall #b8324f;
    border-right: tall #b8324f;"""

replacement = """/* 3D Skeuomorphic Modal Close Button */
.cct-modal-close-btn,
Button.cct-modal-close-btn {
    height: 3; min-height: 3; max-height: 3;
    min-width: 9; max-width: 12;
    padding: 0 1;
    margin: 0;
    border: tall;
    border-top: tall #ffa198;
    border-left: tall #ffa198;
    border-bottom: tall #c73859;
    border-right: tall #c73859;"""

assert target in code, "target not found"
code = code.replace(target, replacement)

with open(PATH, "w", encoding="utf-8") as f:
    f.write(code)

print("theme_css.py updated successfully.")

