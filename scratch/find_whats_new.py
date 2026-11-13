import os

for root, dirs, files in os.walk('.'):
    if any(k in root for k in ('.git', '.venv', 'node_modules', 'dist', 'build')):
        continue
    for f in files:
        if f.endswith(('.py', '.json', '.md', '.ts', '.js', '.txt')):
            fpath = os.path.join(root, f)
            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as fp:
                    for idx, line in enumerate(fp, start=1):
                        low = line.lower()
                        if '2.2.7' in low or "what's new" in low or 'whats_new' in low or 'copilot auto' in low:
                            print(f"{fpath}:{idx}: {line.strip()[:120]}")
            except Exception:
                pass

