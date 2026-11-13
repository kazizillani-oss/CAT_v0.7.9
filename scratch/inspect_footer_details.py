import re

with open('calc_terminal/ui/footer.py', 'r', encoding='utf-8') as f:
    text = f.read()

print("Classes in footer.py:")
for m in re.finditer(r'class \w+.*?:', text):
    print(" ", m.group(0))

print("\nIDs in footer.py:")
for m in re.finditer(r'id=["\'][^"\']+["\']', text):
    print(" ", m.group(0))

with open('calc_terminal/ui/composer.py', 'r', encoding='utf-8') as f:
    comp_text = f.read()

print("\nIDs in composer.py:")
for m in re.finditer(r'id=["\'][^"\']+["\']', comp_text):
    print(" ", m.group(0))

