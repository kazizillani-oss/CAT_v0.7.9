import xml.etree.ElementTree as ET
import sys

sys.stdout.reconfigure(encoding='utf-8')

tree = ET.parse('scratch/live_landscape.svg')
root = tree.getroot()

print("=== LANDSCAPE TEXT (y < 150) ===")
for el in root.iter('{http://www.w3.org/2000/svg}text'):
    y = float(el.attrib.get('y', 999))
    if y < 150:
        content = ''.join(el.itertext())
        print(f"y={y}: {repr(content)}")

# Check rects
print("\n=== LANDSCAPE RECTS (y < 150) ===")
for el in root.iter('{http://www.w3.org/2000/svg}rect'):
    y = float(el.attrib.get('y', 999))
    if y < 150:
        print(f"y={y}, x={el.attrib.get('x')}, w={el.attrib.get('width')}, h={el.attrib.get('height')}, fill={el.attrib.get('fill')}")

tree_p = ET.parse('scratch/live_portrait.svg')
root_p = tree_p.getroot()

print("\n=== PORTRAIT TEXT (y < 150) ===")
for el in root_p.iter('{http://www.w3.org/2000/svg}text'):
    y = float(el.attrib.get('y', 999))
    if y < 150:
        content = ''.join(el.itertext())
        print(f"y={y}: {repr(content)}")

print("\n=== PORTRAIT RECTS (y < 150) ===")
for el in root_p.iter('{http://www.w3.org/2000/svg}rect'):
    y = float(el.attrib.get('y', 999))
    if y < 150:
        print(f"y={y}, x={el.attrib.get('x')}, w={el.attrib.get('width')}, h={el.attrib.get('height')}, fill={el.attrib.get('fill')}")

