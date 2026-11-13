import re

for p in ['calc_terminal/ui/app.py', 'calc_terminal/ui/theme_css.py', 'calc_terminal/ui/composer.py']:
    with open(p, 'r', encoding='utf-8') as f:
        text = f.read()
    matches = re.findall(r'([^{}]*(?:streaming-row|btn-stop|cct-stop-btn)[^{]*\{[^}]*\})', text)
    print(f"=== {p} ===")
    for m in matches:
        print(m)
        print("---")

