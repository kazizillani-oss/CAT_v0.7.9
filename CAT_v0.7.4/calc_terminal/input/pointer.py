"""
CAT Input Architecture — pointer.py
Touch hit-target expansion and pointer adaptation.

Expands practical touch target zones for:
- 1-column pane resizers (ExplorerResizeHandle, RightPaneResizeHandle, ComposerResizeHandle)
- Compact toolbar glyphs (▷ Run, ⿻ Fullscreen, ⏻ Stop, ✕ Close)
Without changing their sleek visual appearance.
"""

from __future__ import annotations

from typing import Optional, Tuple
from textual.widget import Widget
from textual.app import App


RESIZER_TOUCH_PADDING = 2  # Extra cells on each side for touch dragging


class TouchHitZone:
    """Provides hit zone expansion for narrow or small interactive controls."""

    @classmethod
    def find_nearby_resizer(cls, app: App, screen_x: int, screen_y: int, tolerance: int = RESIZER_TOUCH_PADDING) -> Optional[Widget]:
        """
        Check if a touch coordinate landed within tolerance cells of any resizer handle.
        Allows touching near a 1-column splitter to drag it naturally.
        Guarantees that interactive inputs, buttons, and composer elements are never hijacked.
        """
        try:
            screen = getattr(app, "screen", None)
            if screen is None:
                return None

            # 1. Guard against redirecting clicks on interactive controls
            widget_at = None
            if hasattr(screen, "get_widget_at"):
                try:
                    widget_at, _ = screen.get_widget_at(screen_x, screen_y)
                except Exception:
                    widget_at = None

            if widget_at is not None:
                # Direct click on a resizer itself is allowed
                if getattr(widget_at, "id", None) in ("cct-explorer-resizer", "cct-rightpane-resizer", "cct-composer-resizer"):
                    return widget_at

                # Never hijack clicks intended for text inputs, buttons, switches, or trees
                from textual.widgets import Input, TextArea, Button, OptionList, Select, Switch, Tree
                if isinstance(widget_at, (Input, TextArea, Button, OptionList, Select, Switch, Tree)):
                    return None

                # Never hijack clicks inside the composer card (editor stack, prompt row, input, footer, etc.)
                ancestors = [widget_at] + list(getattr(widget_at, "ancestors", []))
                for a in ancestors:
                    aid = getattr(a, "id", None)
                    if aid in ("cct-composer", "cct-editor-stack", "cct-prompt-row", "cct-input"):
                        return None

            # 2. Resizers to inspect with directional bounds
            for resizer_id in ("cct-explorer-resizer", "cct-rightpane-resizer", "cct-composer-resizer"):
                resizers = screen.query(f"#{resizer_id}")
                for resizer in resizers:
                    if not resizer.is_attached or not resizer.visible:
                        continue
                    region = resizer.region

                    if resizer_id == "cct-composer-resizer":
                        # Horizontal splitter above composer:
                        # Only expand UPWARD into conversation history (range: region.y - tolerance to region.y + region.height)
                        # NEVER expand downward into the composer card (y >= region.y + region.height)
                        expanded_x = range(region.x, region.x + region.width)
                        expanded_y = range(region.y - tolerance, region.y + region.height)
                    else:
                        # Vertical splitters (explorer, rightpane):
                        # Expand horizontally in X, keep within Y bounds
                        expanded_x = range(region.x - tolerance, region.x + region.width + tolerance)
                        expanded_y = range(region.y, region.y + region.height)

                    if screen_x in expanded_x and screen_y in expanded_y:
                        return resizer
        except Exception:
            pass
        return None

    @classmethod
    def find_nearby_toolbar_control(cls, app: App, screen_x: int, screen_y: int, tolerance: int = 1) -> Optional[Widget]:
        """
        Check if a touch coordinate landed near compact controls (▷, ⿻, ⏻, ✕).
        """
        try:
            screen = getattr(app, "screen", None)
            if screen is None:
                return None

            control_ids = (
                "cct-tb-run", "cct-tb-split", "cct-tb-close", "cct-tb-preview",
                "cct-bv-split", "cct-bv-close", "cct-bv-fullscreen", "cct-bv-reload",
                "btn-send", "btn-attach", "btn-permissions"
            )
            for cid in control_ids:
                matches = screen.query(f"#{cid}")
                for ctrl in matches:
                    if not ctrl.is_attached or not ctrl.visible:
                        continue
                    region = ctrl.region
                    expanded_x = range(region.x - tolerance, region.x + region.width + tolerance)
                    expanded_y = range(region.y - tolerance, region.y + region.height + tolerance)
                    if screen_x in expanded_x and screen_y in expanded_y:
                        return ctrl
        except Exception:
            pass
        return None
