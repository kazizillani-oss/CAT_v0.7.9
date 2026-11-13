# Script to execute Command Cleanup and Version Update for CAT CLI v0.9.000

import re
import os

print("Applying Command Cleanup and Version Update to v0.9.000...")

# 1. Update identity.py
with open("calc_terminal/identity.py", "r", encoding="utf-8") as f:
    text = f.read()

text = re.sub(r'APP_VERSION\s*=\s*"[^"]+"', 'APP_VERSION = "0.9.000"', text)
with open("calc_terminal/identity.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Updated calc_terminal/identity.py -> 0.9.000")

# 2. Update __init__.py
with open("calc_terminal/__init__.py", "r", encoding="utf-8") as f:
    text = f.read()

text = re.sub(r'__version__\s*=\s*"[^"]+"', '__version__ = "0.9.000"', text)
with open("calc_terminal/__init__.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Updated calc_terminal/__init__.py -> 0.9.000")

# 3. Update pyproject.toml
with open("pyproject.toml", "r", encoding="utf-8") as f:
    text = f.read()

text = re.sub(r'version\s*=\s*"[^"]+"', 'version = "0.9.000"', text)
text = re.sub(r'description\s*=\s*"CAT CLI [^"]+"', 'description = "CAT CLI v0.9.000 - Coding Agent Terminal / terminal AI coding agent"', text)
with open("pyproject.toml", "w", encoding="utf-8") as f:
    f.write(text)
print("Updated pyproject.toml -> 0.9.000")

# 4. Update cat-cli/package.json
if os.path.exists("cat-cli/package.json"):
    with open("cat-cli/package.json", "r", encoding="utf-8") as f:
        text = f.read()
    text = re.sub(r'"version":\s*"[^"]+"', '"version": "0.9.000"', text)
    with open("cat-cli/package.json", "w", encoding="utf-8") as f:
        f.write(text)
    print("Updated cat-cli/package.json -> 0.9.000")

# 5. Clean commands_data.py
# Remove: kinetics, electrochemistry, atomsim, orbitals, orbitalgrid, bonding, graph, random, game, sim3d, gpu3d
# Update /voice description
with open("calc_terminal/commands_data.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
useless_prefixes = [
    '("/kinetics"',
    '("/electrochemistry"',
    '("/atomsim"',
    '("/orbitals"',
    '("/orbitalgrid"',
    '("/bonding"',
    '("/graph"',
    '("/game"',
    '("/random"',
    '("/sim3d"',
    '("/gpu3d"',
]

for line in lines:
    stripped = line.strip()
    if any(stripped.startswith(prefix) for prefix in useless_prefixes):
        continue
    if '("/voice"' in stripped:
        new_lines.append('    ("/voice", "Real-time microphone input, live waveform & speech transcription"),\n')
        continue
    new_lines.append(line)

with open("calc_terminal/commands_data.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)
print("Updated calc_terminal/commands_data.py (removed 11 useless commands, updated /voice)")

# 6. Clean registry.py
with open("calc_terminal/registry.py", "r", encoding="utf-8") as f:
    reg_text = f.read()

# In CATEGORY_MAP: remove the entries
for cmd in ["/kinetics", "/electrochemistry", "/random", "/atomsim", "/orbitals", "/orbitalgrid", "/bonding", "/sim3d", "/gpu3d", "/graph", "/game"]:
    reg_text = re.sub(rf'"{cmd}":\s*"[^"]+",?\s*', '', reg_text)

# In RICH_METADATA: remove entries for atomsim, orbitals, orbitalgrid, bonding
for block in [r'"/atomsim":\s*dict\([^)]+\),?\s*', r'"/orbitals":\s*dict\([^)]+\),?\s*', r'"/orbitalgrid":\s*dict\([^)]+\),?\s*', r'"/bonding":\s*dict\([^)]+\),?\s*']:
    reg_text = re.sub(block, '', reg_text)

# Add /voice to RICH_METADATA if not present
if '"/voice":' not in reg_text:
    voice_meta = '''    "/voice": dict(
        icon="\\U0001f399", permissions=["microphone"],
        ai_modes=["notebook", "agent", "build", "plan", "research", "debugger"],
        examples=["/voice"],
        autocomplete_keywords=["voice", "speech", "mic", "microphone", "audio", "dictate"],
    ),
'''
    reg_text = reg_text.replace("RICH_METADATA = {\n", "RICH_METADATA = {\n" + voice_meta)

with open("calc_terminal/registry.py", "w", encoding="utf-8") as f:
    f.write(reg_text)
print("Updated calc_terminal/registry.py (cleaned categories & metadata, added /voice)")

# 7. Clean palette.py
with open("calc_terminal/ui/palette.py", "r", encoding="utf-8") as f:
    pal_text = f.read()

pal_text = pal_text.replace('"/kinetics", "/orbitals"', '')
pal_text = pal_text.replace('("second order kinetics rate constant", "Integrated rate equation derivation"),', '("real-time voice transcription", "Speak coding instructions via microphone"),')
with open("calc_terminal/ui/palette.py", "w", encoding="utf-8") as f:
    f.write(pal_text)
print("Updated calc_terminal/ui/palette.py")

# 8. Clean test_v5_3d_cursor_and_floating.py
with open("calc_terminal/tests/test_v5_3d_cursor_and_floating.py", "r", encoding="utf-8") as f:
    test_text = f.read()

test_text = test_text.replace('("/electrochemistry", "Cell potential & Nernst numericals")', '("/solve", "Universal formula calculator")')
test_text = test_text.replace('("/sim3d", "3D molecular simulation")', '("/formulas", "Browse formula library")')
test_text = test_text.replace('color_sim = palette._get_item_color("/sim3d", "#89b4fa")', 'color_sim = palette._get_item_color("/formulas", "#89b4fa")')
with open("calc_terminal/tests/test_v5_3d_cursor_and_floating.py", "w", encoding="utf-8") as f:
    f.write(test_text)
print("Updated calc_terminal/tests/test_v5_3d_cursor_and_floating.py")

print("Part A finished successfully!")

