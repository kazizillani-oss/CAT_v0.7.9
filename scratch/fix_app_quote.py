with open('calc_terminal/ui/app.py', 'r', encoding='utf-8') as f:
    text = f.read()

bad_line = '''self._system_note(f"✓ Model `{model_name}` responded in {res['duration_ms']}ms: "{res['response']}"")'''
good_line = '''self._system_note(f"✓ Model `{model_name}` responded in {res['duration_ms']}ms: '{res.get('response', '')}'")'''

if bad_line in text:
    text = text.replace(bad_line, good_line)
else:
    # Also look for unicode escaped or generic
    import re
    text = re.sub(
        r'self\._system_note\(f"\\u2713 Model `\{model_name\}` responded in \{res\[\'duration_ms\'\]\}ms: "\{res\[\'response\'\]\}"',
        r"self._system_note(f\"✓ Model `{model_name}` responded in {res['duration_ms']}ms: '{res.get('response', '')}'\"",
        text
    )

with open('calc_terminal/ui/app.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Fixed line in app.py")

