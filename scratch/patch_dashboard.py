with open("calc_terminal/ui/dashboard.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace line 417
target1 = """                w, h = self._get_viewport_size()
                is_portrait = (w < 92) or (w <= 105 and (w / max(1, h)) < 2.3)"""
rep1 = """                w, h = self._get_viewport_size()
                is_portrait = (w < 55) or (w < 90 and (w / max(1, h)) < 1.30)"""

# Replace lines 558-577
target2 = """            is_portrait = (w < 92) or (w <= 105 and (w / max(1, h)) < 2.3)
            self.set_class(is_portrait, "is-portrait")

            # 2. Adjust vertical breathing room based on available height and mode
            try:
                if is_portrait:
                    # Part 3: Minimal portrait welcome area - remove the three lines
                    self.query_one("#cct-empty-version", Static).display = False
                    self.query_one("#cct-empty-tagline", Static).display = False
                    self.query_one("#cct-empty-ready", Static).display = False
                    self.query_one("#cct-empty-suggest", Static).display = False
                    self.query_one("#cct-dash-ai-status", Static).display = (h >= 32)
                else:
                    # In landscape mode: strictly preserve all three lines
                    self.query_one("#cct-empty-version", Static).display = True
                    self.query_one("#cct-empty-tagline", Static).display = True
                    self.query_one("#cct-empty-ready", Static).display = True
                    self.query_one("#cct-empty-suggest", Static).display = (h >= 28)
                    self.query_one("#cct-dash-ai-status", Static).display = (h >= 20)
            except Exception:
                pass"""

rep2 = """            is_portrait = (w < 55) or (w < 90 and (w / max(1, h)) < 1.30)
            is_compact_floating = (h <= 30) or (w <= 95)
            self.set_class(is_portrait, "is-portrait")

            # 2. Adjust vertical breathing room based on available height and mode
            try:
                if is_portrait:
                    # Part 3: Minimal portrait welcome area - remove the verbose lines
                    self.query_one("#cct-empty-version", Static).display = False
                    self.query_one("#cct-empty-tagline", Static).display = False
                    self.query_one("#cct-empty-ready", Static).display = False
                    self.query_one("#cct-empty-suggest", Static).display = False
                    self.query_one("#cct-dash-ai-status", Static).display = (h >= 32)
                elif is_compact_floating:
                    # Floating window / compact mode: remove verbose status header per user spec
                    self.query_one("#cct-empty-version", Static).display = False
                    self.query_one("#cct-empty-tagline", Static).display = False
                    self.query_one("#cct-empty-ready", Static).display = False
                    self.query_one("#cct-empty-suggest", Static).display = False
                    self.query_one("#cct-dash-ai-status", Static).display = (h >= 24)
                else:
                    # In spacious landscape mode: strictly preserve all status lines
                    self.query_one("#cct-empty-version", Static).display = True
                    self.query_one("#cct-empty-tagline", Static).display = True
                    self.query_one("#cct-empty-ready", Static).display = True
                    self.query_one("#cct-empty-suggest", Static).display = (h >= 28)
                    self.query_one("#cct-dash-ai-status", Static).display = (h >= 20)
            except Exception:
                pass"""

# Replace lines 624-654
target3 = """                if is_portrait:
                    # Part 4: Hide Recent Projects & Project Workspace in portrait mode ONLY
                    col_projects.display = False
                    col_workspace.display = False
                    col_notebooks.display = True
                    columns.set_class(True, "mode-portrait-single")
                    columns.set_class(False, "mode-3col")
                    columns.set_class(False, "mode-2col")
                    columns.set_class(False, "mode-1col")
                    columns.set_class(False, "stacked")
                    col_mode = "portrait-single"
                else:
                    # In landscape mode: preserve all three cards
                    col_projects.display = True
                    col_workspace.display = True
                    col_notebooks.display = True
                    columns.set_class(False, "mode-portrait-single")

                    # 3 columns require at least 92 columns width and 22 rows height
                    if w >= 92 and h >= 22:
                        col_mode = "3col"
                    elif w >= 62 and h >= 20:
                        col_mode = "2col"
                    else:
                        col_mode = "1col"

                    columns.set_class(col_mode == "3col", "mode-3col")
                    columns.set_class(col_mode == "2col", "mode-2col")
                    columns.set_class(col_mode == "1col", "mode-1col")
                    columns.set_class(col_mode == "1col", "stacked")"""

rep3 = """                if is_portrait:
                    # Part 4: Hide Recent Projects & Project Workspace in portrait mode ONLY
                    col_projects.display = False
                    col_workspace.display = False
                    col_notebooks.display = True
                    columns.set_class(True, "mode-portrait-single")
                    columns.set_class(False, "mode-3col")
                    columns.set_class(False, "mode-2col")
                    columns.set_class(False, "mode-1col")
                    columns.set_class(False, "stacked")
                    col_mode = "portrait-single"
                else:
                    # In landscape and floating window mode: preserve and show all 3 sections!
                    col_projects.display = True
                    col_workspace.display = True
                    col_notebooks.display = True
                    columns.set_class(False, "mode-portrait-single")

                    # 3 columns in floating and landscape whenever w >= 70
                    if w >= 70 and h >= 16:
                        col_mode = "3col"
                    elif w >= 50 and h >= 16:
                        col_mode = "2col"
                    else:
                        col_mode = "1col"

                    columns.set_class(col_mode == "3col", "mode-3col")
                    columns.set_class(col_mode == "2col", "mode-2col")
                    columns.set_class(col_mode == "1col", "mode-1col")
                    columns.set_class(col_mode == "1col", "stacked")"""

content_norm = content.replace("\r\n", "\n")
t1_norm = target1.replace("\r\n", "\n")
t2_norm = target2.replace("\r\n", "\n")
t3_norm = target3.replace("\r\n", "\n")

assert t1_norm in content_norm, "Target 1 not found"
assert t2_norm in content_norm, "Target 2 not found"
assert t3_norm in content_norm, "Target 3 not found"

content_norm = content_norm.replace(t1_norm, rep1.replace("\r\n", "\n"), 1)
content_norm = content_norm.replace(t2_norm, rep2.replace("\r\n", "\n"), 1)
content_norm = content_norm.replace(t3_norm, rep3.replace("\r\n", "\n"), 1)

if "\r\n" in content:
    content_norm = content_norm.replace("\n", "\r\n")

with open("calc_terminal/ui/dashboard.py", "w", encoding="utf-8") as f:
    f.write(content_norm)

print("SUCCESS: calc_terminal/ui/dashboard.py patched successfully!")

