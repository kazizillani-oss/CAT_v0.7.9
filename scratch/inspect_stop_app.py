import sys

with open('calc_terminal/ui/app.py', 'r', encoding='utf-8') as f:
    text = f.read()

for i, line in enumerate(text.splitlines()):
    if any(k in line for k in ['btn-stop', 'cct-stop-btn', 'cct-streaming-row']):
        sys.stdout.buffer.write(f"{i+1}: {line}\n".encode('utf-8'))

