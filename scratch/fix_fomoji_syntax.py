import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('calc_terminal/fomoji_manager.py', 'r', encoding='utf-8') as f:
    text = f.read().replace('\r\n', '\n')

bad_pattern = '''@dataclass

_FOMOJI_RUNTIME_STATE: Dict[str, Any] = {'''

good_pattern = '''_FOMOJI_RUNTIME_STATE: Dict[str, Any] = {'''

if bad_pattern in text:
    # Remove it and place snippet right after imports
    idx_bad = text.find(bad_pattern)
    end_of_snippet = text.find('class NodeEnvironment:')
    snippet_content = text[idx_bad + len('@dataclass\n\n'):end_of_snippet]
    text = text[:idx_bad] + '@dataclass\n' + text[end_of_snippet:]
    
    # Now place snippet_content before @dataclass
    idx_dc = text.find('@dataclass')
    text = text[:idx_dc] + snippet_content + '\n' + text[idx_dc:]
    with open('calc_terminal/fomoji_manager.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('SUCCESS: repositioned FOMOJI snippet before @dataclass')
else:
    print('Pattern not matched')

