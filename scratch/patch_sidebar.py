with open("calc_terminal/ui/sidebar.py", "r", encoding="utf-8") as f:
    text = f.read()

# Update close buttons to compact "✕"
text = text.replace('yield Button("✕ Close", id="cct-recentws-close", classes="cct-modal-close-btn")', 'yield Button("✕", id="cct-recentws-close", classes="cct-modal-close-btn")')
text = text.replace('yield Button("✕ Close", id="ows-close-btn", classes="cct-modal-close-btn")', 'yield Button("✕", id="ows-close-btn", classes="cct-modal-close-btn")')

# Replace $accent-lighten-2 with $accent-light
text = text.replace("$accent-lighten-2", "$accent-light")

with open("calc_terminal/ui/sidebar.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Updated sidebar.py successfully!")

