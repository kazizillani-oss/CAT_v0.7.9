"""
CAT CLI — CATRootViewport: Shared Responsive Viewport Engine.

Provides unified terminal dimension measuring, responsive breakpoints,
and full-screen layout constraints (100% width/height) to eliminate
the top-left corner shrinkage glitch across Provider, User, and Settings screens.
"""

from typing import Optional, Callable
import shutil

try:
    from textual.screen import Screen
    from textual.containers import Container
    from textual.reactive import reactive
    from textual.events import Resize
    TEXTUAL_OK = True
except ImportError:
    Screen = object  # type: ignore
    Container = object  # type: ignore
    TEXTUAL_OK = False


# Breakpoint definitions
BP_LARGE = 100
BP_MEDIUM = 80
BP_SMALL = 60


def get_terminal_size_class(width: Optional[int] = None) -> str:
    """Return responsive size class ('large', 'medium', 'small', 'very_small')
    based on current terminal or specified width."""
    if width is None:
        try:
            cols, _ = shutil.get_terminal_size((80, 24))
            width = cols
        except Exception:
            width = 80

    if width >= BP_LARGE:
        return "large"
    elif width >= BP_MEDIUM:
        return "medium"
    elif width >= BP_SMALL:
        return "small"
    return "very_small"


if TEXTUAL_OK:
    class CATRootViewport(Container):
        """Root container that guarantees 100% width and height and adapts

        its child layout to the terminal viewport dimensions.
        """
        DEFAULT_CSS = """
        CATRootViewport {
            width: 100%;
            height: 100%;
            min-width: 100%;
            min-height: 100%;
            layout: vertical;
            padding: 0;
            margin: 0;
            overflow: hidden;
        }
        """

        size_class = reactive("large")

        def __init__(self, *children, on_size_change: Optional[Callable[[str], None]] = None, **kwargs):
            super().__init__(*children, **kwargs)
            self._on_size_change = on_size_change

        def on_mount(self) -> None:
            self._update_size_class()

        def on_resize(self, event: Resize) -> None:
            self._update_size_class(event.size.width)

        def _update_size_class(self, width: Optional[int] = None) -> None:
            w = width if width is not None else (self.size.width or 80)
            new_cls = get_terminal_size_class(w)
            if new_cls != self.size_class:
                self.size_class = new_cls
                # Update CSS classes for styling hooks (.viewport-large, etc.)
                for cls_name in ("viewport-large", "viewport-medium", "viewport-small", "viewport-very-small"):
                    self.remove_class(cls_name)
                self.add_class(f"viewport-{new_cls.replace('_', '-')}")
                if self._on_size_change:
                    try:
                        self._on_size_change(new_cls)
                    except Exception:
                        pass


    class CATViewportScreenMixin:
        """Mixin for Textual Screen subclasses ensuring full terminal viewport

        inheritance, proper resize dispatch, and lifecycle cleanup.
        """
        DEFAULT_CSS = """
        Screen {
            width: 100%;
            height: 100%;
            min-width: 100%;
            min-height: 100%;
            padding: 0;
            margin: 0;
        }
        """

        def get_current_size_class(self) -> str:
            w = getattr(self.size, "width", 0) or getattr(getattr(self, "app", None), "size", None)
            if hasattr(w, "width"):
                width_val = w.width
            elif isinstance(w, int) and w > 0:
                width_val = w
            else:
                cols, _ = shutil.get_terminal_size((80, 24))
                width_val = cols
            return get_terminal_size_class(width_val)

        def on_resize(self, event: Resize) -> None:
            size_class = get_terminal_size_class(event.size.width)
            if hasattr(self, "on_viewport_resized"):
                try:
                    self.on_viewport_resized(size_class, event.size.width, event.size.height)
                except Exception:
                    pass

else:
    class CATRootViewport:  # type: ignore
        pass

    class CATViewportScreenMixin:  # type: ignore
        pass
