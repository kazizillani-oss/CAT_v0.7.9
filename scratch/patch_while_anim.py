import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('calc_terminal/fomoji_manager.py', 'r', encoding='utf-8') as f:
    text = f.read().replace('\r\n', '\n')

old_code = '''    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:'''

new_code = '''    deadline = time.time() + timeout
    while time.time() < deadline:
        if progress_anim:
            try:
                progress_anim.update(title="Starting Fomoji server...", progress=0.75)
            except Exception:
                pass
        if proc.poll() is not None:'''

assert old_code in text
text = text.replace(old_code, new_code, 1)

with open('calc_terminal/fomoji_manager.py', 'w', encoding='utf-8') as f:
    f.write(text)

print('SUCCESS: added progress_anim.update inside while loop')

