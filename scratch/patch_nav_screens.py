with open("calc_terminal/ui/nav_screens.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("$accent-lighten-2", "$accent-light")

with open("calc_terminal/ui/nav_screens.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Updated nav_screens.py successfully!")

