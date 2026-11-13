import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('calc_terminal/fomoji_manager.py', 'r', encoding='utf-8') as f:
    text = f.read().replace('\r\n', '\n')

old_code = '''        if check_server_reachable(timeout=1.0):
            return True, "Fomoji server ready"'''

new_code = '''        if progress_anim:
            try:
                progress_anim.update(title=f"Starting Fomoji server on port {port}...", progress=0.75)
            except Exception:
                pass

        if check_server_reachable(timeout=1.0):
            return True, "Fomoji server ready"'''

assert old_code in text
text = text.replace(old_code, new_code, 1)

with open('calc_terminal/fomoji_manager.py', 'w', encoding='utf-8') as f:
    f.write(text)

print('SUCCESS: updated start_fomoji_server with progress_anim.update')

