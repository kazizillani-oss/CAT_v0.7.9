p = "scratch/sync_all_targets.py"
with open(p, "r", encoding="utf-8") as f:
    text = f.read()

old_tail = '''    os.path.join("ui", "nav_screens.py"),
    os.path.join("ui", "memory_center.py"),
]'''

new_tail = '''    os.path.join("ui", "nav_screens.py"),
    os.path.join("ui", "memory_center.py"),
    os.path.join("ui", "thinking.py"),
    os.path.join("web", "cat_runtime.py"),
]'''

if old_tail in text:
    text = text.replace(old_tail, new_tail)
else:
    text = text.replace(old_tail.replace("\n", "\r\n"), new_tail.replace("\n", "\r\n"))

with open(p, "w", encoding="utf-8") as f:
    f.write(text)

print("Updated sync_all_targets.py")

