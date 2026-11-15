import os

path = r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9\calc_terminal\ui\sidebar.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

target = """            seen_paths = set()
            max_ws = 2 if self._workspace_root else 5
            workspaces = projects.workspaces()[:max_ws]
            if workspaces:
                container.mount(Static("[b]Workspaces[/b]",
                                       classes="cct-sidebar-project-header"))
                for w in workspaces:
                    p = w["path"]
                    seen_paths.add(os.path.abspath(p))
                    marks = ("\\U0001f4cc" if w.get("pinned") else "") \\
                            + ("\\u2b50" if w.get("favorite") else "")
                    prefix = (marks + " ") if marks else "\\U0001f4c2"
                    container.mount(_ProjectRow(
                        p, prefix=prefix,
                        on_delete=lambda path=p: self._remove_workspace(path)))
            pinned = [p for p in projects.pinned() if os.path.abspath(p) not in seen_paths]
            for p in pinned:
                seen_paths.add(os.path.abspath(p))
            max_rec = 2 if self._workspace_root else 5
            recent = [p for p in projects.recent() if os.path.abspath(p) not in seen_paths][:max_rec]"""

replacement = """            def _norm_path(p_str):
                try:
                    return os.path.normcase(os.path.abspath(os.path.realpath(os.path.normpath(p_str))))
                except Exception:
                    return str(p_str).strip().lower()

            seen_paths = set()
            if self._workspace_root:
                seen_paths.add(_norm_path(self._workspace_root))

            max_ws = 2 if self._workspace_root else 5
            workspaces = []
            for w in projects.workspaces():
                np = _norm_path(w.get("path", ""))
                if np and np not in seen_paths:
                    workspaces.append(w)
                    seen_paths.add(np)
            workspaces = workspaces[:max_ws]

            if workspaces:
                container.mount(Static("[b]Workspaces[/b]",
                                       classes="cct-sidebar-project-header"))
                for w in workspaces:
                    p = w["path"]
                    marks = ("\\U0001f4cc" if w.get("pinned") else "") \\
                            + ("\\u2b50" if w.get("favorite") else "")
                    prefix = (marks + " ") if marks else "\\U0001f4c2"
                    container.mount(_ProjectRow(
                        p, prefix=prefix,
                        on_delete=lambda path=p: self._remove_workspace(path)))

            pinned_list = []
            for p in projects.pinned():
                np = _norm_path(p)
                if np and np not in seen_paths:
                    pinned_list.append(p)
                    seen_paths.add(np)

            max_rec = 2 if self._workspace_root else 5
            recent_list = []
            for p in projects.recent():
                np = _norm_path(p)
                if np and np not in seen_paths:
                    recent_list.append(p)
                    seen_paths.add(np)
            recent = recent_list[:max_rec]"""

if target in content:
    content = content.replace(target, replacement, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Successfully patched sidebar.py!")
else:
    print("Target not found!")
