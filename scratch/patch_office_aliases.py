with open(r'calc_terminal/office_commands.py', 'r', encoding='utf-8') as f:
    text = f.read()

text += "\n\n# Aliases\ncmd_sheets = cmd_excel\ncmd_presentation = cmd_slides\n"

with open(r'calc_terminal/office_commands.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Added aliases to office_commands.py")

