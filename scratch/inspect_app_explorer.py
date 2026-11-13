import sys

with open('calc_terminal/ui/app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("--- 1500-1520 ---")
for i in range(1500, 1525):
    sys.stdout.buffer.write(f"{i+1}: {lines[i]}".encode('utf-8'))

print("--- 2460-2485 ---")
for i in range(2458, 2485):
    sys.stdout.buffer.write(f"{i+1}: {lines[i]}".encode('utf-8'))

