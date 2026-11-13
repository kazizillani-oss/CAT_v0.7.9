with open('calc_terminal/ui/app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i in range(2400, 2460):
    print(f"{i+1}: {lines[i]}", end="")

