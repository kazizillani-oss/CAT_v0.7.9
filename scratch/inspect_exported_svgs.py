import xml.etree.ElementTree as ET, sys

def check_svg(path):
    print(f"=== {path} ===")
    tree = ET.parse(path)
    root = tree.getroot()
    lines = []
    for elem in root.iter():
        if elem.tag.endswith('text') and elem.text and elem.text.strip():
            lines.append(elem.text.strip())
    sys.stdout.buffer.write((' | '.join(lines[:25]) + '\n').encode('utf-8'))
    sys.stdout.buffer.write((' | '.join(lines[-25:]) + '\n').encode('utf-8'))

check_svg('C:/Users/ADMIN/.gemini/antigravity/brain/6044f886-d0e4-4199-9ee7-c7349e91cb18/composer_and_header_portrait_verified.svg')
check_svg('C:/Users/ADMIN/.gemini/antigravity/brain/6044f886-d0e4-4199-9ee7-c7349e91cb18/composer_and_header_landscape_verified.svg')

