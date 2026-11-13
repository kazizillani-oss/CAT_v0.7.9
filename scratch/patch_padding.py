with open('calc_terminal/ui/theme_css.py', 'r', encoding='utf-8') as f:
    tc = f.read()

tc = tc.replace('''padding: 0 1;
    margin: 0;
    offset: 0 0;''', '''padding: 0;
    margin: 0;
    offset: 0 0;''')

with open('calc_terminal/ui/theme_css.py', 'w', encoding='utf-8') as f:
    f.write(tc)

with open('calc_terminal/ui/app.py', 'r', encoding='utf-8') as f:
    ap = f.read()

ap = ap.replace('''padding: 0 1;
    margin: 0;
    border: none;
    content-align: center middle;''', '''padding: 0;
    margin: 0;
    border: none;
    content-align: center middle;''')

with open('calc_terminal/ui/app.py', 'w', encoding='utf-8') as f:
    f.write(ap)

print("Updated padding in theme_css.py and app.py")

