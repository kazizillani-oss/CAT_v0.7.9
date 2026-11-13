# scratch/update_sidebar_dialogs.py
with open('calc_terminal/ui/sidebar.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Update #cct-recentws-close styling
old_rws_close = """        #cct-recentws-close {
            width: 5; min-width: 5; max-width: 5; height: 3; min-height: 3; max-height: 3; padding: 0;
            content-align: center middle;
            border-top: solid #8a3f4d;
            border-left: solid #7a3542;
            border-bottom: solid #250f14;
            border-right: solid #301319;
            background: #3e1f27;
            color: #ff99a8;
            text-style: bold;
        }
        #cct-recentws-close:hover {
            background: #5a2533;
            border-top: solid #ff8899;
            border-left: solid #ff7788;
            border-bottom: solid #8a3f4d;
            border-right: solid #7a3542;
            color: #ffffff;
        }"""

new_rws_close = """        #cct-recentws-close {
            width: 5; min-width: 5; max-width: 5; height: 3; min-height: 3; max-height: 3; padding: 0;
            content-align: center middle;
            border: tall;
            border-top: tall #d46b7a;
            border-left: tall #b54f5e;
            border-bottom: tall #281419;
            border-right: tall #3e1b23;
            background: #4a1e27;
            color: #ffb8c4;
            text-style: bold;
        }
        #cct-recentws-close:hover {
            background: #6e2534;
            border-top: tall #ff99aa;
            border-left: tall #ff778d;
            border-bottom: tall #381219;
            border-right: tall #4a1922;
            color: #ffffff;
        }"""

assert old_rws_close in code, "old_rws_close not found"
code = code.replace(old_rws_close, new_rws_close, 1)

# 2. Update #cct-recentws-btns styling
old_rws_btns = """        #cct-recentws-btns {
            height: 4; min-height: 4; padding: 0 1;
            margin-top: 1;
            border-top: solid $border;
            layout: horizontal;
            align: right middle;
        }
        #cct-recentws-btns Button {
            margin: 0 1;
            min-width: 10;
            height: 3;
            padding: 0 1;
            border-top: solid #5a6585;
            border-left: solid #4a5270;
            border-bottom: solid #141520;
            border-right: solid #181926;
            background: #252839;
            color: $text;
            text-style: bold;
        }
        #cct-recentws-btns Button:hover {
            border-top: solid $accent-lighten-2;
            border-left: solid $accent;
            border-bottom: solid $accent-darken-3;
            border-right: solid $accent-darken-2;
            background: #343750;
            color: #ffffff;
        }
        #cct-recentws-btns #cct-recentws-clear {
            
        }
        #cct-recentws-btns #cct-recentws-open {
            background: $accent 35%;
            color: #ffffff;
            border-top: solid $accent-lighten-2;
            border-left: solid $accent;
            border-bottom: solid $accent-darken-3;
            border-right: solid $accent-darken-2;
            min-width: 10;
        }
        RecentWorkspacesScreen.is-portrait #cct-recentws-btns,
        .is-portrait #cct-recentws-btns {
            layout: vertical;
            height: auto;
            min-height: 8;
            padding: 0 1;
            margin-top: 1;
            border-top: solid $border;
            align: center middle;
        }
        RecentWorkspacesScreen.is-portrait #cct-recentws-btns Button,
        .is-portrait #cct-recentws-btns Button {
            width: 100%;
            margin: 1 0 0 0;
            min-height: 3;
            height: auto;
        }
        RecentWorkspacesScreen.is-portrait .cct-btn-spacer,
        .is-portrait .cct-btn-spacer {
            display: none;
        }
        .cct-btn-spacer { width: 1fr; }"""

new_rws_btns = """        #cct-recentws-btns {
            height: 4; min-height: 4; padding: 0 1;
            margin-top: 1;
            border-top: solid $border;
            layout: horizontal;
            align: right middle;
        }
        #cct-recentws-btns Button {
            margin: 0 0 0 1;
            min-width: 8;
            height: 3;
            padding: 0 1;
            border: tall;
            border-top: tall #6b7596;
            border-left: tall #565f7c;
            border-bottom: tall #0e0f17;
            border-right: tall #13141f;
            background: #222436;
            color: $text;
            text-style: bold;
        }
        #cct-recentws-btns Button:hover {
            border-top: tall $accent-lighten-2;
            border-left: tall $accent;
            border-bottom: tall $accent-darken-3;
            border-right: tall $accent-darken-2;
            background: #343750;
            color: #ffffff;
        }
        #cct-recentws-btns #cct-recentws-clear {
            
        }
        #cct-recentws-btns #cct-recentws-open {
            background: $accent 35%;
            color: #ffffff;
            border: tall;
            border-top: tall #f7d794;
            border-left: tall #e0af68;
            border-bottom: tall #7a4f15;
            border-right: tall #9e6f28;
            min-width: 8;
        }
        #cct-recentws-btns #cct-recentws-open:hover {
            background: $accent 50%;
            border-top: tall #ffffff;
            border-left: tall #fce4b8;
            border-bottom: tall #8a571c;
            border-right: tall #af7627;
        }
        RecentWorkspacesScreen.is-portrait #cct-recentws-btns,
        .is-portrait #cct-recentws-btns {
            layout: horizontal;
            height: 4;
            min-height: 4;
            padding: 0 1;
            margin-top: 1;
            border-top: solid $border;
            align: center middle;
        }
        RecentWorkspacesScreen.is-portrait #cct-recentws-btns Button,
        .is-portrait #cct-recentws-btns Button {
            width: 1fr;
            margin: 0 1;
            min-height: 3;
            height: 3;
            min-width: 6;
        }
        RecentWorkspacesScreen.is-portrait .cct-btn-spacer,
        .is-portrait .cct-btn-spacer {
            display: none;
        }
        .cct-btn-spacer { width: 1fr; min-width: 0; max-width: 1fr; }"""

assert old_rws_btns in code, "old_rws_btns not found"
code = code.replace(old_rws_btns, new_rws_btns, 1)

# 3. Update #ows-close-btn styling
old_ows_close = """        #ows-close-btn {
            width: 5; min-width: 5; max-width: 5; height: 3; min-height: 3; max-height: 3; padding: 0;
            content-align: center middle;
            border-top: solid #8a3f4d;
            border-left: solid #7a3542;
            border-bottom: solid #250f14;
            border-right: solid #301319;
            background: #3e1f27;
            color: #ff99a8;
            text-style: bold;
        }
        #ows-close-btn:hover {
            background: #5a2533;
            border-top: solid #ff8899;
            border-left: solid #ff7788;
            border-bottom: solid #8a3f4d;
            border-right: solid #7a3542;
            color: #ffffff;
        }"""

new_ows_close = """        #ows-close-btn {
            width: 5; min-width: 5; max-width: 5; height: 3; min-height: 3; max-height: 3; padding: 0;
            content-align: center middle;
            border: tall;
            border-top: tall #d46b7a;
            border-left: tall #b54f5e;
            border-bottom: tall #281419;
            border-right: tall #3e1b23;
            background: #4a1e27;
            color: #ffb8c4;
            text-style: bold;
        }
        #ows-close-btn:hover {
            background: #6e2534;
            border-top: tall #ff99aa;
            border-left: tall #ff778d;
            border-bottom: tall #381219;
            border-right: tall #4a1922;
            color: #ffffff;
        }"""

assert old_ows_close in code, "old_ows_close not found"
code = code.replace(old_ows_close, new_ows_close, 1)

with open('calc_terminal/ui/sidebar.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("sidebar.py updated successfully!")

