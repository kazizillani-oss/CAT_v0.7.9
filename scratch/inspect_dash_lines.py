with open("calc_terminal/ui/dashboard.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

print("=== Lines 415-440 ===")
for i in range(414, min(440, len(lines))):
    print(f"{i+1:4d}: {lines[i].rstrip()}")

print("\n=== Lines 555-580 ===")
for i in range(554, min(580, len(lines))):
    print(f"{i+1:4d}: {lines[i].rstrip()}")

print("\n=== Lines 620-655 ===")
for i in range(619, min(655, len(lines))):
    print(f"{i+1:4d}: {lines[i].rstrip()}")

