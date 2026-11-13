"""Thorough unit tests for newly implemented command suites:
- dev_commands (/files, /tree, /search, /grep, /replace, /rename, /new, /diff, /git, /test, /lint, /format, /typecheck, /run)
- office_commands (/word, /excel, /sheets, /slides, /presentation, /design, /pdf, /office)
- pkg_commands (/pkg, /py, /node)
- skill_commands (/skill)
- mcp (cmd_mcp)
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from calc_terminal import dev_commands
from calc_terminal import office_commands
from calc_terminal import pkg_commands
from calc_terminal import skill_commands
from calc_terminal.mcp import cmd_mcp


class TestNewCommandSuites(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = self.temp_dir.name
        # Create sample files in temp workspace
        Path(self.workspace, "sample.txt").write_text("Hello CAT world!\nLine 2 text.", encoding="utf-8")
        Path(self.workspace, "sub").mkdir(parents=True, exist_ok=True)
        Path(self.workspace, "sub", "test.py").write_text("def test_fn():\n    return 42\n", encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    # --- Dev Commands ---
    def test_cmd_files(self):
        with patch.object(dev_commands, "_get_workspace_root", return_value=self.workspace):
            res = dev_commands.cmd_files("")
            self.assertIn("sample.txt", res)
            self.assertIn("Workspace Files", res)

    def test_cmd_tree(self):
        with patch.object(dev_commands, "_get_workspace_root", return_value=self.workspace):
            res = dev_commands.cmd_tree("")
            self.assertIn("sub", res)

    def test_cmd_search_and_grep(self):
        with patch.object(dev_commands, "_get_workspace_root", return_value=self.workspace):
            res_search = dev_commands.cmd_search("Hello")
            self.assertIn("sample.txt", res_search)

            res_grep = dev_commands.cmd_grep(r"def\s+test_fn")
            self.assertIn("test.py", res_grep)

    def test_cmd_new_and_rename_and_replace(self):
        with patch.object(dev_commands, "_get_workspace_root", return_value=self.workspace):
            # /new
            res_new = dev_commands.cmd_new("created.md")
            self.assertIn("Created file", res_new)
            self.assertTrue(Path(self.workspace, "created.md").exists())
            Path(self.workspace, "created.md").write_text("Hello Markdown", encoding="utf-8")

            # /replace
            res_replace = dev_commands.cmd_replace('Hello Welcome created.md')
            self.assertIn("Replaced", res_replace)
            self.assertIn("Welcome Markdown", Path(self.workspace, "created.md").read_text(encoding="utf-8"))

            # /rename
            res_rename = dev_commands.cmd_rename("created.md renamed.md")
            self.assertIn("Renamed", res_rename)
            self.assertTrue(Path(self.workspace, "renamed.md").exists())
            self.assertFalse(Path(self.workspace, "created.md").exists())

    def test_cmd_dev_tools_help(self):
        # Safe execution without arguments returns help/status
        self.assertIn("Git", dev_commands.cmd_git("status"))
        self.assertTrue(len(dev_commands.cmd_diff("")) > 5)
        self.assertIn("123", dev_commands.cmd_run('-c "print(123)"'))

    # --- Office Commands ---
    def test_office_word(self):
        with patch.object(office_commands, "_get_workspace_root", return_value=self.workspace):
            res = office_commands.cmd_word("create doc1.md")
            self.assertIn("Word Document Created", res)
            self.assertTrue(Path(self.workspace, "doc1.md").exists())

            res_read = office_commands.cmd_word("read doc1.md")
            self.assertIn("Executive Summary", res_read)

    def test_office_excel_and_sheets(self):
        with patch.object(office_commands, "_get_workspace_root", return_value=self.workspace):
            res_excel = office_commands.cmd_excel("create sheet1.csv")
            self.assertIn("Spreadsheet Created", res_excel)
            self.assertTrue(Path(self.workspace, "sheet1.csv").exists())

            res_sheets = office_commands.cmd_sheets("read sheet1.csv")
            self.assertIn("Spreadsheet", res_sheets)

    def test_office_slides_and_presentation(self):
        with patch.object(office_commands, "_get_workspace_root", return_value=self.workspace):
            res_slides = office_commands.cmd_slides("create deck1.md")
            self.assertIn("Slide Deck Created", res_slides)
            self.assertTrue(Path(self.workspace, "deck1.md").exists())

            res_pres = office_commands.cmd_presentation("status")
            self.assertIn("Office Presentation Engine Status", res_pres)

    def test_office_design_and_pdf(self):
        res_design = office_commands.cmd_design("banner Welcome")
        self.assertIn("Welcome", res_design)

        res_pdf = office_commands.cmd_pdf("status")
        self.assertIn("PDF Processing Engine Status", res_pdf)

        res_office = office_commands.cmd_office("")
        self.assertIn("Office & Productivity Suite", res_office)

    # --- Package Commands ---
    def test_pkg_commands(self):
        res_pkg = pkg_commands.cmd_pkg("help")
        self.assertIn("Package Manager Commands", res_pkg)

        res_py = pkg_commands.cmd_py("env")
        self.assertIn("Python Environment", res_py)

        res_node = pkg_commands.cmd_node("env")
        self.assertIn("Node.js", res_node)

    # --- Skill Commands ---
    def test_skill_commands(self):
        res_list = skill_commands.cmd_skill("list")
        self.assertIn("Registered Skills", res_list)

        res_search = skill_commands.cmd_skill("search research")
        self.assertIn("Search Results", res_search)

    # --- MCP Commands ---
    def test_mcp_commands(self):
        res_mcp = cmd_mcp("list")
        self.assertIn("MCP Servers", res_mcp)


if __name__ == "__main__":
    unittest.main()
