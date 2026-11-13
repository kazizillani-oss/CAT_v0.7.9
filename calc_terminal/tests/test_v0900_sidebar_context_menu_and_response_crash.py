# -*- coding: utf-8 -*-
"""Regression and verification tests for:
1. Sidebar single scrollbar (no double scrollbars) and full bottom expansion.
2. Context menu 'Try Again' agent labels: Aria (Build), Mira (Plan Mode), Qala (Notebook),
   Nova (Agent), Sage (Research), Dex (Debugger), and MENU_WIDTH >= 40.
3. Crash resilience in input submission and assistant response completion.
4. Kitties modal close button tall bevel and Config Kitties button label.
5. Context menu CSS validity without undefined variable errors.
"""
import pytest
from unittest.mock import MagicMock
from calc_terminal.ui.context_menu import AI_MENU_ITEMS, MENU_WIDTH, MessageContextMenu
from calc_terminal.ui.thinking import completion_summary_lines
from calc_terminal.ui.sidebar import Explorer
from calc_terminal.ui.events import MessageFinished
from calc_terminal.ui.agent_menu import AgentModeMenu, _ManageAgentsRow


def test_context_menu_agent_labels():
    items_dict = dict(AI_MENU_ITEMS)
    assert MENU_WIDTH >= 40
    assert "Aria (Build)" in items_dict["retry:build"]
    assert "Mira (Plan Mode)" in items_dict["retry:plan"]
    assert "Qala (Notebook)" in items_dict["retry:notebook"]
    assert "Nova (Agent)" in items_dict["retry:agent"]
    assert "Sage (Research)" in items_dict["retry:research"]
    assert "Dex (Debugger)" in items_dict["retry:debugger"]


def test_completion_summary_crash_resilience():
    # Test None values, missing keys, string percentages, empty contributions
    lines1 = completion_summary_lines(
        provider="nvidia", model="test-model", duration=1.23, tokens=456,
        contributions={"pct_main": None, "pct_backup": None, "main_tokens": 100}
    )
    assert len(lines1) >= 2
    assert "Response Complete" in lines1[0]

    lines2 = completion_summary_lines(
        provider=None, model=None, duration=None, tokens=None,
        contributions=[{"model": "test", "percent": None, "is_backup": True}]
    )
    assert len(lines2) >= 2
    assert "100%" in lines2[1]

    lines3 = completion_summary_lines(
        provider="ollama", model="qwen", duration=0.5,
        contributions=[{"model": "m1", "percent": 60.0}, {"model": "m2", "percent": "invalid"}]
    )
    assert len(lines3) >= 2


def test_sidebar_tree_class_and_css():
    from calc_terminal.ui import theme_css
    css = theme_css.BASE_CSS
    assert "#cct-sidebar.has-tree #cct-sidebar-body" in css
    assert "overflow-y: hidden" in css
    assert ".cct-filetree" in css
    assert "min-height: 0" in css


def test_explorer_has_tree_state():
    explorer = Explorer()
    assert not explorer.has_class("has-tree")
    explorer.close_folder()
    assert not explorer.has_class("has-tree")


def test_agent_menu_close_button_and_config_kitties():
    css = AgentModeMenu.DEFAULT_CSS
    assert "cct-agentmenu-close" in css
    assert "border-left: tall" in css
    assert "border-right: tall" in css
    row = _ManageAgentsRow()
    assert "Config Kitties" in str(row.render())


def test_context_menu_css_no_undefined_variables():
    css = MessageContextMenu.CSS
    assert "$app-background" not in css
    assert "$surface-highlight" not in css
    assert "$surface-dark" not in css
    assert "$surface-alt" not in css
    assert "#cct-ctxmenu-box" in css
