with open('calc_terminal/ui/theme_css.py', 'r', encoding='utf-8') as f:
    tc = f.read()

# 1. Patch theme_css.py: #cct-right-controls width: 9
old_rc1 = '''#cct-right-controls {
    width: 9;
    min-width: 9;
    max-width: 9;
    height: 1;
    min-height: 1;
    max-height: 1;
    layout: horizontal;
    align-vertical: middle;
    align-horizontal: right;
    margin: 0;
    padding: 0;
    overflow-x: hidden;
    overflow-y: hidden;
    background: transparent;
}'''

new_rc1 = '''#cct-right-controls {
    width: auto;
    height: 1;
    min-height: 1;
    max-height: 1;
    layout: horizontal;
    align-vertical: middle;
    align-horizontal: right;
    align: right middle;
    margin: 0;
    padding: 0;
    background: transparent;
}
#cct-composer-left {
    width: auto;
    height: 1;
    min-height: 1;
    max-height: 1;
    layout: horizontal;
    align-vertical: middle;
    align-horizontal: left;
    align: left middle;
    margin: 0;
    padding: 0;
    background: transparent;
}'''

if old_rc1 in tc:
    tc = tc.replace(old_rc1, new_rc1)
    print("Patched old_rc1 in theme_css.py")
else:
    print("old_rc1 not found in theme_css.py")

# 2. Patch theme_css.py: 3D composer layout rules (lines ~1343-1435)
old_cframe = '''/* ---------------- 3D Skeuomorphic Composer Layout & Clusters (v0.9.000) ---------------- */
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
}'''

new_cframe = '''/* ---------------- 3D Skeuomorphic Composer Layout & Clusters (v0.9.000) ---------------- */
#cct-composer-context-bar {
    width: 100%;
    height: 1;
    min-height: 1;
    max-height: 1;
    background: #141520;
    border-bottom: solid #222436;
    padding: 0 1;
    margin: 0;
    layout: horizontal;
    align: left middle;
}
#cct-context-left {
    width: auto;
    height: 1;
    layout: horizontal;
    align: left middle;
}
#cct-context-spacer {
    width: 1fr;
    height: 1;
}
.cct-context-status, #badge-status {
    width: auto;
    height: 1;
    content-align: right middle;
    color: #a6e3a1;
    text-style: bold;
}
#cct-prompt-row {
    width: 100%;
    height: auto;
    min-height: 2;
    background: #12131d;
    border: none;
    padding: 0 1;
    margin: 0;
    layout: horizontal;
}
#cct-bottom-row {
    width: 100%;
    height: 1;
    min-height: 1;
    max-height: 1;
    background: #161724;
    border: none;
    padding: 0 1;
    margin: 0;
    layout: horizontal;
    align: left middle;
}
#cct-composer-left {
    width: auto;
    height: 1;
    min-height: 1;
    max-height: 1;
    layout: horizontal;
    align: left middle;
    margin: 0;
    padding: 0;
    background: transparent;
}
#cct-toolbar-center {
    width: 1fr;
    height: 1;
    layout: horizontal;
    align: center middle;
}
#cct-center-status {
    width: auto;
    height: 1;
    color: #6e7594;
    content-align: center middle;
}
#cct-right-controls {
    width: auto;
    height: 1;
    min-height: 1;
    max-height: 1;
    layout: horizontal;
    align: right middle;
    margin: 0;
    padding: 0;
    background: transparent;
}
.cct-icon-btn, Button.cct-icon-btn {
    width: auto;
    min-width: 3;
    height: 1;
    min-height: 1;
    max-height: 1;
    border: none;
    background: #24283b;
    color: $accent;
    content-align: center middle;
    align: center middle;
    padding: 0 1;
    margin: 0;
    offset: 0 0;
}
.cct-icon-btn:hover, Button.cct-icon-btn:hover {
    background: $surface-alt;
    color: #ffffff;
    border: none;
}
.cct-icon-btn:focus, Button.cct-icon-btn:focus,
.cct-icon-btn.-active, Button.cct-icon-btn.-active {
    background: $surface-dark;
    color: $accent;
    border: none;
}
Button#btn-send, .cct-icon-send {
    width: auto;
    min-width: 3;
    height: 1;
    min-height: 1;
    max-height: 1;
    border: none;
    background: #e0af68;
    color: #12131d;
    text-style: bold;
    content-align: center middle;
    align: center middle;
    padding: 0 1;
    margin: 0;
    offset: 0 0;
}
Button#btn-send:hover, .cct-icon-send:hover {
    background: #f7d794;
    color: #000000;
    border: none;
}
Button#btn-send:focus, .cct-icon-send:focus,
Button#btn-send.-active, .cct-icon-send.-active {
    background: #c68a4c;
    color: #ffffff;
    border: none;
}
Button#btn-stop, .cct-btn-stop {
    width: auto;
    min-width: 7;
    height: 1;
    min-height: 1;
    max-height: 1;
    border: none;
    background: #ef4444;
    color: #ffffff;
    text-style: bold;
    content-align: center middle;
    align: center middle;
    padding: 0 1;
    margin: 0;
}
Button#btn-stop:hover, .cct-btn-stop:hover {
    background: #dc2626;
    color: #ffffff;
    border: none;
}
Button#btn-mic.cct-mic-active {
    background: #f7768e;
    color: #ffffff;
    text-style: bold;
    border: none;
}'''

if old_cframe in tc:
    tc = tc.replace(old_cframe, new_cframe)
    print("Patched old_cframe in theme_css.py")
else:
    print("old_cframe not found in theme_css.py")

with open('calc_terminal/ui/theme_css.py', 'w', encoding='utf-8') as f:
    f.write(tc)
print("Saved theme_css.py")

# 3. Patch app.py
with open('calc_terminal/ui/app.py', 'r', encoding='utf-8') as f:
    app_text = f.read()

old_app_rc = '''#cct-right-controls {
    width: 9;
    min-width: 9;
    max-width: 9;
    height: 1;
    min-height: 1;
    max-height: 1;
    layout: horizontal;
    align-vertical: middle;
    align-horizontal: right;
    margin: 0;
    padding: 0;
    overflow: hidden;
    background: transparent;
}'''

new_app_rc = '''#cct-right-controls {
    width: auto;
    height: 1;
    min-height: 1;
    max-height: 1;
    layout: horizontal;
    align-vertical: middle;
    align-horizontal: right;
    align: right middle;
    margin: 0;
    padding: 0;
    background: transparent;
}
#cct-composer-left {
    width: auto;
    height: 1;
    min-height: 1;
    max-height: 1;
    layout: horizontal;
    align-vertical: middle;
    align-horizontal: left;
    align: left middle;
    margin: 0;
    padding: 0;
    background: transparent;
}'''

if old_app_rc in app_text:
    app_text = app_text.replace(old_app_rc, new_app_rc)
    print("Patched old_app_rc in app.py")
else:
    print("old_app_rc not found in app.py")

old_app_btn = '''Button.cct-icon-btn,
Button#btn-permissions,
Button#btn-attach,
Button.cct-icon-send,
Button#btn-send {
    height: 1;
    min-height: 1;
    max-height: 1;
    width: 3;
    min-width: 3;
    max-width: 3;
    padding: 0;
    margin: 0;
    border: none;
    content-align: center middle;
    background: transparent;
    offset: 0 0;
}'''

new_app_btn = '''Button.cct-icon-btn,
Button#btn-permissions,
Button#btn-attach,
Button#btn-security,
Button#btn-mic,
Button.cct-icon-send,
Button#btn-send {
    height: 1;
    min-height: 1;
    max-height: 1;
    width: auto;
    min-width: 3;
    padding: 0 1;
    margin: 0;
    border: none;
    content-align: center middle;
    background: transparent;
    offset: 0 0;
}'''

if old_app_btn in app_text:
    app_text = app_text.replace(old_app_btn, new_app_btn)
    print("Patched old_app_btn in app.py")
else:
    print("old_app_btn not found in app.py")

with open('calc_terminal/ui/app.py', 'w', encoding='utf-8') as f:
    f.write(app_text)
print("Saved app.py")
