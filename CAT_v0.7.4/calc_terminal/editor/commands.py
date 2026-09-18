"""CAT Code Editor — Command Registry (calc_terminal/editor/commands.py).

Centralized registration and execution of all editor, preview, and workbench commands.
UI components, buttons, menus, and shortcuts invoke commands through this registry.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class CATCommand:
    """Definition of an executable command inside CAT IDE."""
    id: str
    title: str
    category: str = "General"
    handler: Optional[Callable[[Optional[dict]], Any]] = None
    can_execute: Optional[Callable[[Optional[dict]], bool]] = None
    default_keybinding: Optional[str] = None
    description: str = ""


class CommandRegistry:
    """Central registry of all CAT IDE commands."""

    def __init__(self) -> None:
        self._commands: Dict[str, CATCommand] = {}
        self._register_defaults()

    def register(self, command: CATCommand) -> None:
        """Register or override a command."""
        self._commands[command.id] = command

    def unregister(self, command_id: str) -> bool:
        """Unregister a command by ID."""
        if command_id in self._commands:
            del self._commands[command_id]
            return True
        return False

    def get(self, command_id: str) -> Optional[CATCommand]:
        """Look up a command by its ID."""
        return self._commands.get(command_id)

    def can_execute(self, command_id: str, context: Optional[dict] = None) -> bool:
        """Check if a command can currently execute."""
        cmd = self.get(command_id)
        if not cmd:
            return False
        if cmd.can_execute is not None:
            try:
                return bool(cmd.can_execute(context))
            except Exception:
                return False
        return cmd.handler is not None

    def execute(self, command_id: str, context: Optional[dict] = None) -> Any:
        """Execute a registered command by its ID."""
        cmd = self.get(command_id)
        if not cmd:
            raise KeyError(f"Command '{command_id}' is not registered.")
        if not self.can_execute(command_id, context):
            return None
        if cmd.handler is None:
            return None
        try:
            sig = inspect.signature(cmd.handler)
            if len(sig.parameters) == 0:
                return cmd.handler()
            return cmd.handler(context)
        except TypeError:
            try:
                return cmd.handler(context)
            except Exception:
                return cmd.handler()

    def list_commands(self, category: Optional[str] = None) -> List[CATCommand]:
        """Return a sorted list of registered commands, optionally filtered by category."""
        cmds = list(self._commands.values())
        if category:
            cmds = [c for c in cmds if c.category.lower() == category.lower()]
        cmds.sort(key=lambda c: (c.category, c.title))
        return cmds

    def _register_defaults(self) -> None:
        """Register default editor, preview, and workbench commands."""
        defaults = [
            # Editor File Actions
            CATCommand("editor.save", "File: Save", "File", default_keybinding="ctrl+s", description="Save the active file to disk"),
            CATCommand("editor.saveAs", "File: Save As...", "File", default_keybinding="ctrl+shift+s", description="Save active file with a new name"),
            CATCommand("editor.closeTab", "View: Close Current Tab", "View", default_keybinding="ctrl+w", description="Close active editor or viewer tab"),
            CATCommand("editor.reopenClosedTab", "View: Reopen Closed Tab", "View", default_keybinding="ctrl+shift+t", description="Reopen recently closed tab"),
            CATCommand("editor.quickOpen", "Go to File... (Quick Open)", "Go", default_keybinding="ctrl+p", description="Quickly open a file from workspace"),
            CATCommand("editor.commandPalette", "View: Command Palette", "View", default_keybinding="ctrl+shift+p", description="Open CAT Command Palette"),
            
            # Editor Navigation & Search
            CATCommand("editor.find", "Edit: Find", "Edit", default_keybinding="ctrl+f", description="Find text in active editor"),
            CATCommand("editor.replace", "Edit: Replace", "Edit", default_keybinding="ctrl+h", description="Find and replace text in active editor"),
            CATCommand("workspace.search", "Search: Find in Files", "Search", default_keybinding="ctrl+shift+f", description="Search text across workspace"),
            CATCommand("editor.goToDefinition", "Go: Go to Definition", "Go", default_keybinding="f12", description="Jump to symbol definition"),
            CATCommand("editor.findReferences", "Go: Find References", "Go", default_keybinding="shift+f12", description="Find all references of symbol"),
            CATCommand("editor.rename", "Edit: Rename Symbol", "Edit", default_keybinding="f2", description="Rename symbol across file"),

            # Line & Text Manipulation
            CATCommand("editor.toggleComment", "Edit: Toggle Line Comment", "Edit", default_keybinding="ctrl+/", description="Comment or uncomment current line"),
            CATCommand("editor.selectNextOccurrence", "Selection: Add Next Occurrence", "Selection", default_keybinding="ctrl+d", description="Select next matching text occurrence"),
            CATCommand("editor.deleteLine", "Edit: Delete Line", "Edit", default_keybinding="ctrl+shift+k", description="Delete entire current line"),
            CATCommand("editor.moveLineUp", "Edit: Move Line Up", "Edit", default_keybinding="alt+up", description="Move active line or selection up"),
            CATCommand("editor.moveLineDown", "Edit: Move Line Down", "Edit", default_keybinding="alt+down", description="Move active line or selection down"),
            CATCommand("editor.copyLineUp", "Edit: Copy Line Up", "Edit", default_keybinding="shift+alt+up", description="Duplicate active line upwards"),
            CATCommand("editor.copyLineDown", "Edit: Copy Line Down", "Edit", default_keybinding="shift+alt+down", description="Duplicate active line downwards"),
            CATCommand("editor.insertLineBelow", "Edit: Insert Line Below", "Edit", default_keybinding="ctrl+enter", description="Insert line below and move cursor"),
            CATCommand("editor.insertLineAbove", "Edit: Insert Line Above", "Edit", default_keybinding="ctrl+shift+enter", description="Insert line above and move cursor"),
            CATCommand("editor.triggerCompletion", "Edit: Trigger Suggestion", "Edit", default_keybinding="ctrl+space", description="Trigger code completion / suggestions"),
            CATCommand("editor.formatDocument", "Edit: Format Document", "Edit", default_keybinding="shift+alt+f", description="Format source code"),

            # Live Preview Commands
            CATCommand("preview.open", "Preview: Run / Open Live Preview", "Preview", default_keybinding="shift+enter", description="Start or reuse local development server and open live preview"),
            CATCommand("preview.reload", "Preview: Reload Live Preview", "Preview", default_keybinding="ctrl+r", description="Reload active live preview"),
            CATCommand("preview.stop", "Preview: Stop Development Server", "Preview", description="Stop the running local development server"),
            CATCommand("preview.restart", "Preview: Restart Development Server", "Preview", description="Restart the local development server"),
            CATCommand("preview.toggleSplit", "View: Toggle Split Editor / Preview", "View", default_keybinding="ctrl+shift+s", description="Toggle side-by-side split between editor and preview"),

            # Workbench & Sidebar
            CATCommand("workbench.action.toggleSidebar", "View: Toggle Primary Sidebar", "View", default_keybinding="ctrl+b", description="Show or hide primary sidebar / explorer"),
            CATCommand("workbench.action.terminal.toggle", "View: Toggle Terminal", "View", default_keybinding="ctrl+`", description="Toggle integrated terminal"),
            CATCommand("workbench.view.explorer", "View: Show Explorer", "View", default_keybinding="ctrl+shift+e", description="Focus workspace file explorer"),
            CATCommand("workbench.view.scm", "View: Show Source Control", "View", default_keybinding="ctrl+shift+g", description="Open source control / git panel"),
            CATCommand("workbench.action.closeOverlays", "View: Close Active Overlays", "View", default_keybinding="escape", description="Dismiss active find bar, popups, or dialogs"),

            # Viewer Controls
            CATCommand("viewer.zoomIn", "Viewer: Zoom In", "Viewer", default_keybinding="ctrl+=", description="Zoom in active viewer"),
            CATCommand("viewer.zoomOut", "Viewer: Zoom Out", "Viewer", default_keybinding="ctrl+-", description="Zoom out active viewer"),
            CATCommand("viewer.fitPage", "Viewer: Fit to Screen", "Viewer", description="Fit document or image to screen"),
            CATCommand("viewer.fitWidth", "Viewer: Fit to Width", "Viewer", description="Fit document or image to width"),
            CATCommand("viewer.fullscreen", "Viewer: Toggle Fullscreen", "Viewer", default_keybinding="f11", description="Toggle fullscreen right pane"),

            # AI Code Actions
            CATCommand("ai.explainSelection", "CAT AI: Explain Selection", "AI", description="Ask CAT AI to explain the selected code"),
            CATCommand("ai.fixSelection", "CAT AI: Fix Selection", "AI", description="Ask CAT AI to fix bugs or errors in selection"),
            CATCommand("ai.refactorSelection", "CAT AI: Refactor Selection", "AI", description="Refactor selected code with AI diff"),
            CATCommand("ai.generateTests", "CAT AI: Generate Unit Tests", "AI", description="Generate unit tests for selected code"),
        ]
        for cmd in defaults:
            self.register(cmd)


# Global singleton registry
_GLOBAL_REGISTRY: Optional[CommandRegistry] = None


def get_command_registry() -> CommandRegistry:
    """Return the global CommandRegistry singleton."""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = CommandRegistry()
    return _GLOBAL_REGISTRY
