with open(r'calc_terminal/commands_data.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
new_lines = [l for l in lines if "] Real-time 3D Atomic Simulation" not in l]
with open(r'calc_terminal/commands_data.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print('Cleaned commands_data.py, line count:', len(new_lines))

