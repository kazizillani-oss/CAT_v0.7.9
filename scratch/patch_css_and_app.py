import re

# Update calc_terminal/ui/app.py
with open("calc_terminal/ui/app.py", "r", encoding="utf-8") as f:
    app_code = f.read()

# 1. Update #cct-composer in app.py
old_composer_css = '''#cct-composer {
    dock: bottom;
    background: #181926;
    border: heavy;
    border-top: heavy #6b7596;
    border-left: heavy #565f7c;
    border-bottom: heavy #3b4261;
    border-right: heavy #4a5278;
    tint: transparent;
    padding: 0 1;
    margin: 0 1 1 1;
    height: auto;
    min-height: 0;
    max-height: 85%;
    width: 1fr;
    layout: vertical;
    overflow: hidden;
    overflow-x: hidden;
    overflow-y: hidden;
    transition: border 120ms, tint 120ms;
}'''

new_composer_css = '''#cct-composer {
    dock: bottom;
    background: #181926;
    border: heavy;
    border-top: heavy #6b7596;
    border-left: heavy #565f7c;
    border-bottom: heavy #0e0f17;
    border-right: heavy #13141f;
    tint: transparent;
    padding: 0;
    margin: 0 1 1 1;
    height: auto;
    min-height: 5;
    max-height: 85%;
    width: 100%;
    layout: vertical;
    overflow: hidden;
    overflow-x: hidden;
    overflow-y: hidden;
    transition: border 120ms, tint 120ms;
}'''

assert old_composer_css in app_code, "Could not find old_composer_css in app.py"
app_code = app_code.replace(old_composer_css, new_composer_css)

# Add 3D frame, voice strip, and tactile cluster CSS to app.py
composer_cluster_css = '''
/* ---------------- 3D Skeuomorphic Composer Layout & Clusters (v0.9.000) ---------------- */
#cct-composer-frame {
    width: 100%;
    height: auto;
    layout: horizontal;
    align: left middle;
    padding: 0 1;
    margin: 0;
    background: transparent;
}
#cct-composer-left {
    width: auto;
    height: 3;
    layout: horizontal;
    align: left middle;
    margin-right: 1;
}
#cct-right-controls {
    width: auto;
    height: 3;
    layout: horizontal;
    align: right middle;
    margin-left: 1;
}
.cct-icon-btn {
    width: 5;
    min-width: 5;
    max-width: 5;
    height: 3;
    min-height: 3;
    max-height: 3;
    border: heavy;
    border-top: heavy #6b7596;
    border-left: heavy #565f7c;
    border-bottom: heavy #0e0f17;
    border-right: heavy #13141f;
    background: #1e2030;
    color: $accent;
    content-align: center middle;
    align: center middle;
    padding: 0;
    margin: 0;
}
.cct-icon-btn:hover {
    background: #24283b;
    border-top: heavy #89b4fa;
    border-left: heavy #89b4fa;
    border-bottom: heavy #0e0f17;
    border-right: heavy #13141f;
    color: #ffffff;
}
.cct-icon-btn:focus,
.cct-icon-btn.-active {
    background: #13141f;
    border-top: heavy #0e0f17;
    border-left: heavy #13141f;
    border-bottom: heavy #6b7596;
    border-right: heavy #565f7c;
    color: $accent;
}
#btn-send {
    color: #e5a035;
    border-top: heavy #e0af68;
    border-left: heavy #c6903f;
    border-bottom: heavy #5c3808;
    border-right: heavy #784a0d;
}
#btn-send:hover {
    background: #e5a035 25%;
    border-top: heavy #f7d794;
    border-left: heavy #f7d794;
    color: #ffffff;
}
#btn-stop {
    color: #f7768e;
    border-top: heavy #f7768e;
    border-left: heavy #f7768e;
    border-bottom: heavy #4c1d25;
    border-right: heavy #63222e;
}
#btn-stop:hover {
    background: #f7768e 30%;
    color: #ffffff;
}
#btn-mic.cct-mic-active {
    background: #f7768e 30%;
    color: #ffffff;
    border-top: heavy #f7768e;
    border-left: heavy #f7768e;
    border-bottom: heavy #4c1d25;
    border-right: heavy #63222e;
}
#cct-voice-strip {
    display: none;
    width: 100%;
    height: 3;
    layout: horizontal;
    align: center middle;
    background: #13141f;
    border-bottom: solid #2a2e42;
    padding: 0 1;
}
#cct-voice-status {
    width: 1fr;
    height: 1;
    content-align: left middle;
}
#cct-voice-actions {
    width: auto;
    height: 3;
    layout: horizontal;
}
.cct-voice-btn {
    height: 3;
    min-height: 3;
    max-height: 3;
    padding: 0 1;
    margin-left: 1;
}
.cct-voice-ok {
    background: #1a3326;
    color: #73daca;
    border: heavy #41a6b5 #0e0f17 #0e0f17 #41a6b5;
}
.cct-voice-cancel {
    background: #331a1a;
    color: #f7768e;
    border: heavy #f7768e #0e0f17 #0e0f17 #f7768e;
}
'''

app_code = app_code.replace("/* ---------------------------------------------------- streaming status -- */", composer_cluster_css + "\n/* ---------------------------------------------------- streaming status -- */")

with open("calc_terminal/ui/app.py", "w", encoding="utf-8") as f:
    f.write(app_code)
print("Updated calc_terminal/ui/app.py CSS")

# Update calc_terminal/ui/theme_css.py
with open("calc_terminal/ui/theme_css.py", "r", encoding="utf-8") as f:
    theme_code = f.read()

old_theme_composer = '''#cct-composer {
    background: #181926;
    border: heavy;
    border-top: heavy #6b7596;
    border-left: heavy #565f7c;
    border-bottom: heavy #3b4261;
    border-right: heavy #4a5278;
    tint: transparent;
    padding: 0;
    margin: 0 1 1 1;
    overflow: hidden;
    overflow-x: hidden;
    overflow-y: hidden;
    transition: border 120ms, tint 120ms;
}'''

new_theme_composer = '''#cct-composer {
    background: #181926;
    border: heavy;
    border-top: heavy #6b7596;
    border-left: heavy #565f7c;
    border-bottom: heavy #0e0f17;
    border-right: heavy #13141f;
    tint: transparent;
    padding: 0;
    margin: 0 1 1 1;
    width: 100%;
    min-height: 5;
    overflow: hidden;
    overflow-x: hidden;
    overflow-y: hidden;
    transition: border 120ms, tint 120ms;
}''' + composer_cluster_css

if old_theme_composer in theme_code:
    theme_code = theme_code.replace(old_theme_composer, new_theme_composer)
    with open("calc_terminal/ui/theme_css.py", "w", encoding="utf-8") as f:
        f.write(theme_code)
    print("Updated calc_terminal/ui/theme_css.py")

print("CSS patch complete.")

