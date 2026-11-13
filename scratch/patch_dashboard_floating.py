with open(r"calc_terminal/ui/dashboard.py", "r", encoding="utf-8") as f:
    text = f.read()

target = """                if is_portrait:
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
                    columns.set_class(col_mode == "1col", "stacked")

                self._col_mode = col_mode"""

replacement = """                if is_portrait:
                    # Portrait mode: Single centered CAT card
                    col_projects.display = False
                    col_workspace.display = False
                    col_notebooks.display = True
                    columns.set_class(True, "mode-portrait-single")
                    columns.set_class(False, "mode-floating-single")
                    columns.set_class(False, "mode-3col")
                    columns.set_class(False, "mode-2col")
                    columns.set_class(False, "mode-1col")
                    columns.set_class(False, "stacked")
                    col_mode = "portrait-single"
                elif is_compact_floating:
                    # Floating window mode: Remove recent projects and project & workspace per user spec
                    col_projects.display = False
                    col_workspace.display = False
                    col_notebooks.display = True
                    columns.set_class(True, "mode-floating-single")
                    columns.set_class(False, "mode-portrait-single")
                    columns.set_class(False, "mode-3col")
                    columns.set_class(False, "mode-2col")
                    columns.set_class(False, "mode-1col")
                    columns.set_class(False, "stacked")
                    col_mode = "floating-single"
                else:
                    # Spacious landscape: Show all 3 sections!
                    col_projects.display = True
                    col_workspace.display = True
                    col_notebooks.display = True
                    columns.set_class(False, "mode-portrait-single")
                    columns.set_class(False, "mode-floating-single")

                    if w >= 70 and h >= 16:
                        col_mode = "3col"
                    elif w >= 50 and h >= 16:
                        col_mode = "2col"
                    else:
                        col_mode = "1col"

                    columns.set_class(col_mode == "3col", "mode-3col")
                    columns.set_class(col_mode == "2col", "mode-2col")
                    columns.set_class(col_mode == "1col", "mode-1col")
                    columns.set_class(col_mode == "1col", "stacked")

                self._col_mode = col_mode"""

text_n = text.replace('\r\n', '\n')
target_n = target.replace('\r\n', '\n')
replacement_n = replacement.replace('\r\n', '\n')

if target_n in text_n:
    text_n = text_n.replace(target_n, replacement_n)
    with open(r"calc_terminal/ui/dashboard.py", "w", encoding="utf-8") as f:
        f.write(text_n)
    print("Successfully patched calc_terminal/ui/dashboard.py")
else:
    print("Error: Target not found in dashboard.py")

