path = "calc_terminal/ui/extensions_panel.py"
with open(path, "r", encoding="utf-8") as f:
    txt = f.read()

target = """        #ext-titlebar {
            height: 5; min-height: 5; max-height: 5;
            padding: 0 2;
            border-bottom: solid #313244;
            layout: horizontal;
            align: center middle;
            background: $surface-darken-1;
        }
        #ext-title { width: 1fr; text-style: bold; color: $text; }"""

replacement = """        #ext-titlebar {
            height: 5; min-height: 5; max-height: 5;
            padding: 0 2;
            border-bottom: solid #313244;
            layout: horizontal;
            align: center middle;
            background: $surface-darken-1;
        }
        #ext-title { width: 1fr; text-style: bold; color: $text; }
        #ext-close {
            width: 5; min-width: 5; max-width: 5; height: 3; min-height: 3; max-height: 3; padding: 0;
            content-align: center middle;
            border-top: solid #ffa198;
            border-left: solid #ffa198;
            border-bottom: solid #c73859;
            border-right: solid #c73859;
            background: #3e2430;
            color: #ffffff;
        }
        #ext-close:hover {
            background: #5a2c3a;
            border-top: solid #ffffff;
            border-left: solid #ffffff;
            border-bottom: solid #ffa198;
            border-right: solid #ffa198;
        }"""

if target in txt:
    txt = txt.replace(target, replacement, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(txt)
    print("SUCCESS: Patched ext-close in extensions_panel.py")
else:
    print("WARNING: target not found in extensions_panel.py")

