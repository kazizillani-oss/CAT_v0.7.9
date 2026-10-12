"""Helpers for mapping a WebEngine view back to the pane that owns its tab."""

from __future__ import annotations


def find_tab_owner(widget):
    """Walk widget parents; ``widget.window()`` skips the embedded browser pane."""
    current = widget
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if callable(getattr(current, "_view_index", None)) and hasattr(current, "tab_bar"):
            return current
        try:
            parent = current.parentWidget()
        except (AttributeError, RuntimeError):
            try:
                parent = current.parent()
            except (AttributeError, RuntimeError):
                return None
        if parent is current:
            return None
        current = parent
    return None


def tab_id_for_view(owner, view) -> str | None:
    """Return the persisted tab ID only when view and state still share an index."""
    try:
        index = owner._view_index(view)
        tabs = owner.state.tabs if owner.state is not None else ()
        if 0 <= index < len(tabs):
            return str(tabs[index].id)
    except (AttributeError, RuntimeError, TypeError):
        return None
    return None


def current_index_after_tab_close(closing_index: int, current_index: int, remaining_count: int) -> int:
    """Keep the same active tab after removing an unrelated tab."""
    if remaining_count <= 0:
        return -1
    if closing_index == current_index:
        return min(closing_index, remaining_count - 1)
    return current_index - (1 if closing_index < current_index else 0)
