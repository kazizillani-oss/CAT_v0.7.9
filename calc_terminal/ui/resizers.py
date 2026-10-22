"""
CAT v0.7.9.0 — resizers.py: real draggable split-pane handles.

Two independent resizable areas (spec sections 12, 15-16):

  1. ExplorerResizeHandle — the vertical divider between the FILE
     EXPLORER and the MAIN CHAT AREA. Drag left => explorer narrower,
     drag right => explorer wider. Clamped to [MIN, max % of shell].

  2. ComposerResizeHandle — the subtle horizontal grip between the chat
     history and the CHAT COMPOSER. Drag up => taller composer, drag
     down => shorter. Clamped so a usable message area always remains.

Both are plain Textual widgets using capture_mouse() drags — no timers,
no busy loops. Chosen sizes persist to ~/.cct_ui_layout.json so they
survive restarts, and are re-clamped when the window itself resizes.

The handles exist to keep the layout architecture honest: the composer
is a flow child of the main chat column (NEVER docked/positioned across
the whole screen), so it can never overlap the explorer again.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import json
import os

TEXTUAL_AVAILABLE = True
try:
    from textual.widgets import Static
    from textual.containers import Vertical
except Exception:
    TEXTUAL_AVAILABLE = False

LAYOUT_PATH = os.path.join(os.path.expanduser("~"), ".cct_ui_layout.json")

# ---- Explorer width bounds ------------------------------------------------
EXPLORER_MIN_WIDTH = 14      # never disappears by accident while dragging
EXPLORER_MAX_FRACTION = 0.55 # never wider than ~half the shell
EXPLORER_DEFAULT_WIDTH = 32

# ---- Composer height bounds ----------------------------------------------
COMPOSER_MIN_HEIGHT = 5      # input + footer stay usable
COMPOSER_MAX_FRACTION = 0.35 # compact bounds — chat history keeps majority of shell
COMPOSER_MARGIN_ROWS = 2     # composer's vertical margin rows (1 top + 1 bottom)

# ---- Right pane (Code / Preview) width bounds ------------------------------
RIGHTPANE_MIN_WIDTH = 24     # code/preview stays usable
RIGHTPANE_MAX_FRACTION = 0.60
RIGHTPANE_DEFAULT_WIDTH = 44
CHAT_MIN_FRACTION = 0.25     # chat column keeps at least this much of the shell


def load_layout():
    """Persisted {explorer_width, composer_height, rightpane_width}
    (ints or None)."""
    data = {}
    try:
        with open(LAYOUT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        pass
    out = {}
    for key in ("explorer_width", "composer_height", "rightpane_width"):
        try:
            v = data.get(key)
            if key == "composer_height" and (v is None or int(v) <= COMPOSER_MIN_HEIGHT or int(v) > 14):
                out[key] = None
            else:
                out[key] = int(v) if v else None
        except Exception:
            out[key] = None
    return out


def save_layout(explorer_width=None, composer_height=None,
                rightpane_width=None):
    try:
        current = {}
        if os.path.exists(LAYOUT_PATH):
            with open(LAYOUT_PATH, "r", encoding="utf-8") as f:
                current = json.load(f)
        if explorer_width is not None:
            current["explorer_width"] = int(explorer_width)
        if composer_height is not None:
            current["composer_height"] = int(composer_height)
        if rightpane_width is not None:
            current["rightpane_width"] = int(rightpane_width)
        with open(LAYOUT_PATH, "w", encoding="utf-8") as f:
            json.dump(current, f)
    except Exception:
        pass


if TEXTUAL_AVAILABLE:

    class _DragHandle(Static):
        """Shared mouse-drag plumbing: capture on press, track moves,
        release + persist on drop. Subclasses implement `_apply(x, y)`
        and `_persist()`."""

        def __init__(self, renderable="", **kwargs):
            super().__init__(renderable, **kwargs)
            self._dragging = False

        def _apply(self, event):
            raise NotImplementedError

        def _persist(self):
            return

        def on_mouse_down(self, event):
            event.stop()
            self._dragging = True
            self.add_class("dragging")
            # Grab the pointer even when it leaves this 1-cell widget —
            # that's what makes dragging past the handle smooth.
            self.capture_mouse()

        def on_mouse_move(self, event):
            if not self._dragging:
                return
            event.stop()
            self._apply(event)

        def on_mouse_up(self, event):
            if not self._dragging:
                return
            event.stop()
            self._dragging = False
            self.remove_class("dragging")
            try:
                # NOTE: Widget.release_mouse() takes no arguments.
                self.release_mouse()
            except Exception:
                pass
            self._persist()

        def on_unmount(self):
            self._dragging = False

    class ExplorerResizeHandle(_DragHandle):
        """1-column divider between Explorer and the main area."""

        DEFAULT_CSS = """
        ExplorerResizeHandle {
            width: 1;
            height: 100%;
            background: $border;
            transition: background 100ms;
        }
        ExplorerResizeHandle:hover,
        ExplorerResizeHandle.dragging {
            background: $accent;
        }
        """

        def __init__(self, shell, **kwargs):
            super().__init__(id="cct-explorer-resizer", **kwargs)
            self._shell = shell

        def _clamp(self, width):
            total = max(10, self._shell.size.width) if self._shell.is_attached \
                else EXPLORER_DEFAULT_WIDTH * 2
            ceiling = max(EXPLORER_MIN_WIDTH + 4,
                          int(total * EXPLORER_MAX_FRACTION))
            return max(EXPLORER_MIN_WIDTH, min(ceiling, width))

        def _apply(self, event):
            explorer = self._shell.explorer
            left_edge = explorer.region.x if explorer.region.x >= 0 else 0
            target = event.screen_x - left_edge
            explorer.set_width(self._clamp(target))
            self._shell.sync_resizer()
            try:
                if not self._shell._fullscreen:
                    self._shell._relayout()
            except Exception:
                pass

        def _persist(self):
            save_layout(explorer_width=self._shell.explorer.width)

    class ComposerResizeHandle(_DragHandle):
        """Subtle full-width grip between chat history and composer."""

        DEFAULT_CSS = """
        ComposerResizeHandle {
            width: 100%;
            height: 1;
            color: $text-faint;
            content-align: center middle;
            background: transparent;
            transition: color 100ms;
        }
        ComposerResizeHandle:hover,
        ComposerResizeHandle.dragging {
            color: $accent;
            background: transparent;
        }
        """

        GRIP = "\u2500 \u00b7 \u2500 \u00b7 \u2500 \u00b7 \u2500"

        def __init__(self, shell, **kwargs):
            super().__init__(self.GRIP, id="cct-composer-resizer", **kwargs)
            self._shell = shell

        def reset_to_default(self):
            """Reset composer to normal default compact height."""
            from .composer import StickyComposer
            try:
                composer = self._shell.query_one(StickyComposer)
                composer.set_explicit_height(None)
            except Exception:
                pass
            save_layout(composer_height=None)
            try:
                self._shell._do_resize_layout()
            except Exception:
                pass
            try:
                conv = self._shell.query_one("#cct-conversation")
                if conv and getattr(conv, "_dashboard", None):
                    conv._dashboard.fit_to_viewport()
                    if hasattr(self, "call_after_refresh"):
                        self.call_after_refresh(conv._dashboard.fit_to_viewport)
            except Exception:
                pass

        def on_click(self, event):
            import time
            now = time.monotonic()
            if hasattr(self, "_last_click_time") and (now - self._last_click_time) < 0.6:
                self._last_click_time = 0.0
                event.stop()
                self.reset_to_default()
                return
            self._last_click_time = now

        def on_mouse_down(self, event):
            import time
            now = time.monotonic()
            if hasattr(self, "_last_down_time") and (now - self._last_down_time) < 0.8:
                # Double-click resets to normal default compact height
                self._last_down_time = 0.0
                event.stop()
                self._dragging = False
                self.remove_class("dragging")
                try:
                    self.release_mouse()
                except Exception:
                    pass
                self.reset_to_default()
                return
            self._last_down_time = now
            super().on_mouse_down(event)

        def _bounds(self):
            """(min_height, max_height) for the composer inside the main
            column right now."""
            try:
                main = self._shell.query_one("#cct-workspace-main", Vertical)
                available = max(20, main.region.height)
            except Exception:
                available = 20
            # Reserve at least 18 rows for chat column / dashboard so it never overlaps or gets cut off
            max_chat_room = max(18, int(available * 0.65))
            max_h = max(COMPOSER_MIN_HEIGHT, min(8, available - max_chat_room))
            return COMPOSER_MIN_HEIGHT, max(COMPOSER_MIN_HEIGHT, max_h)

        def _apply(self, event):
            from .composer import StickyComposer
            try:
                composer = self._shell.query_one(StickyComposer)
            except Exception:
                return
            # Derive the new height from the MAIN COLUMN's static
            # geometry (never from the composer's live region — reading
            # a widget you are simultaneously resizing feeds the next
            # layout pass back into the math and oscillates).
            try:
                main = self._shell.query_one("#cct-workspace-main", Vertical)
                main_bottom = main.region.y + main.region.height
            except Exception:
                return
            lo, hi = self._bounds()
            # Rows reserved below the drag point: the grip row itself +
            # the composer's bottom margin. Height grows as the handle
            # is dragged up, shrinks as it is dragged down.
            target = int(main_bottom - COMPOSER_MARGIN_ROWS - event.screen_y)
            if target <= lo + 1:
                composer.set_explicit_height(None)
            else:
                target = max(lo, min(hi, target))
                composer.set_explicit_height(target)
            try:
                self._shell._do_resize_layout()
            except Exception:
                pass
            try:
                conv = self._shell.query_one("#cct-conversation")
                if conv and getattr(conv, "_dashboard", None):
                    conv._dashboard.fit_to_viewport()
                    if hasattr(self, "call_after_refresh"):
                        self.call_after_refresh(conv._dashboard.fit_to_viewport)
            except Exception:
                pass

        def _persist(self):
            from .composer import StickyComposer
            try:
                composer = self._shell.query_one(StickyComposer)
            except Exception:
                return
            h = getattr(composer, "_explicit_height", None)
            save_layout(composer_height=h)

    class RightPaneResizeHandle(_DragHandle):
        """v0.7.10: 1-column divider between the CHAT column and the
        CODE / PREVIEW pane. Drag left => right pane wider, right =>
        narrower. Mirrors ExplorerResizeHandle's contract and persists
        to the same layout file (rightpane_width)."""

        DEFAULT_CSS = """
        RightPaneResizeHandle {
            width: 1;
            height: 100%;
            background: $border;
            transition: background 100ms;
        }
        RightPaneResizeHandle:hover,
        RightPaneResizeHandle.dragging {
            background: $accent;
        }
        """

        def __init__(self, shell, **kwargs):
            super().__init__(id="cct-rightpane-resizer", **kwargs)
            self._shell = shell

        def _clamp(self, width):
            total = max(20, self._shell.size.width) if self._shell.is_attached \
                else RIGHTPANE_DEFAULT_WIDTH * 2
            ceiling = max(RIGHTPANE_MIN_WIDTH + 4,
                          int(total * RIGHTPANE_MAX_FRACTION))
            return max(RIGHTPANE_MIN_WIDTH, min(ceiling, width))

        def _apply(self, event):
            pane = self._shell.right_pane
            if pane is None:
                return
            # Width grows as the handle moves LEFT of its own right edge.
            right_edge = pane.region.x + pane.region.width
            target = right_edge - event.screen_x
            # Route through the shell's width owner (clamps + remembers
            # the value for persistence). The raw Vertical container has
            # no set_width of its own.
            self._shell.set_right_width(target)
            self._shell.sync_right_resizer()

        def _persist(self):
            # The shell remembers the last clamped width — never depend
            # on a layout pass having landed for the live region read.
            save_layout(rightpane_width=getattr(self._shell,
                                                "_rightpane_width", None))

    class SplitPreviewResizer(_DragHandle):
        """v0.7.9 split view divider between editor and preview inside right pane.
        Drag left => preview wider, right => editor wider. Only visible in SPLIT mode."""

        DEFAULT_CSS = """
        SplitPreviewResizer {
            width: 1;
            height: 100%;
            background: $border;
            transition: background 100ms;
        }
        SplitPreviewResizer:hover,
        SplitPreviewResizer.dragging {
            background: $accent;
        }
        """

        def __init__(self, shell, **kwargs):
            super().__init__(id="cct-split-resizer", **kwargs)
            self._shell = shell

        def _apply(self, event):
            # Adjust split ratio based on handle position inside right pane
            right = self._shell.right_pane
            if right is None:
                return
            # Right pane's left edge
            left_edge = right.region.x if right.region.x >=0 else 0
            total_w = max(20, right.region.width)
            # Position of handle relative to right pane left
            pos = event.screen_x - left_edge
            # Clamp so both editor and preview keep min width
            min_w = 12
            pos = max(min_w, min(total_w - min_w, pos))
            ratio = pos / max(1, total_w)
            # Apply as widths to editor and preview
            try:
                editor = self._shell.editor
                preview = self._shell.preview_panel
                if editor and preview:
                    # Use integer widths based on total
                    ed_w = max(min_w, int(total_w * ratio))
                    pv_w = max(min_w, total_w - ed_w - 1)  # -1 for handle
                    editor.styles.width = ed_w
                    preview.styles.width = pv_w
            except Exception:
                pass

        def _persist(self):
            pass

else:

    _DragHandle = None
    ExplorerResizeHandle = None
    ComposerResizeHandle = None
    RightPaneResizeHandle = None
    SplitPreviewResizer = None
