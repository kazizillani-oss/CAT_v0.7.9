with open('scratch/sync_all_targets.py', 'r', encoding='utf-8') as f:
    txt = f.read()

txt = txt.replace(
    '"commands_data.py",',
    '"commands_data.py",\n    "voice.py",\n    "registry.py",\n    "identity.py",\n    "app.py",\n    "fallback_cli.py",'
)

with open('scratch/sync_all_targets.py', 'w', encoding='utf-8') as f:
    f.write(txt)
print("Updated scratch/sync_all_targets.py")

