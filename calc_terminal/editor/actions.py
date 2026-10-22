"""CAT Code Editor — Editor Actions (calc_terminal/editor/actions.py).

Concrete editor manipulation routines:
- Toggle line comment
- Delete line
- Move line up / down
- Copy line up / down
- Insert line below / above
- Select next matching occurrence
"""

from __future__ import annotations

from typing import Any, Optional

_COMMENT_PREFIXES = {
    "python": "# ",
    "bash": "# ",
    "sh": "# ",
    "yaml": "# ",
    "yml": "# ",
    "toml": "# ",
    "javascript": "// ",
    "typescript": "// ",
    "json": "// ",
    "rust": "// ",
    "go": "// ",
    "java": "// ",
    "c": "// ",
    "cpp": "// ",
    "css": "/* ",
    "sql": "-- ",
    "html": "<!-- ",
}


def toggle_line_comment(area: Any, language: Optional[str] = None) -> bool:
    """Toggle comment on the current line or selection in a TextArea."""
    if not hasattr(area, "text") or not hasattr(area, "cursor_location"):
        return False
    lang = (language or getattr(area, "language", "") or "").lower()
    prefix = _COMMENT_PREFIXES.get(lang, "# ")
    suffix = " -->" if prefix == "<!-- " else (" */" if prefix == "/* " else "")

    lines = area.text.splitlines() or [""]
    row, col = area.cursor_location
    if row < 0 or row >= len(lines):
        return False

    line = lines[row]
    stripped = line.lstrip()
    indent = line[:len(line) - len(stripped)]

    if suffix:
        if stripped.startswith(prefix.strip()) and stripped.endswith(suffix.strip()):
            uncommented = stripped[len(prefix.strip()):-len(suffix.strip())].strip()
            lines[row] = indent + uncommented
        else:
            lines[row] = indent + prefix + stripped + suffix
    else:
        if stripped.startswith(prefix):
            lines[row] = indent + stripped[len(prefix):]
        elif stripped.startswith(prefix.strip()):
            lines[row] = indent + stripped[len(prefix.strip()):]
        else:
            lines[row] = indent + prefix + stripped

    new_text = "\n".join(lines)
    area.text = new_text
    try:
        area.move_cursor((row, min(col, len(lines[row]))))
    except Exception:
        pass
    return True


def delete_line(area: Any) -> bool:
    """Delete the active line in a TextArea."""
    if not hasattr(area, "text") or not hasattr(area, "cursor_location"):
        return False
    lines = area.text.splitlines() or [""]
    row, col = area.cursor_location
    if row < 0 or row >= len(lines):
        return False

    if len(lines) == 1:
        lines = [""]
        target_row = 0
    else:
        lines.pop(row)
        target_row = min(row, len(lines) - 1)

    area.text = "\n".join(lines)
    try:
        area.move_cursor((target_row, min(col, len(lines[target_row]))))
    except Exception:
        pass
    return True


def move_line_up(area: Any) -> bool:
    """Swap the active line with the line above it."""
    if not hasattr(area, "text") or not hasattr(area, "cursor_location"):
        return False
    lines = area.text.splitlines() or [""]
    row, col = area.cursor_location
    if row <= 0 or row >= len(lines):
        return False

    lines[row - 1], lines[row] = lines[row], lines[row - 1]
    area.text = "\n".join(lines)
    try:
        area.move_cursor((row - 1, min(col, len(lines[row - 1]))))
    except Exception:
        pass
    return True


def move_line_down(area: Any) -> bool:
    """Swap the active line with the line below it."""
    if not hasattr(area, "text") or not hasattr(area, "cursor_location"):
        return False
    lines = area.text.splitlines() or [""]
    row, col = area.cursor_location
    if row < 0 or row >= len(lines) - 1:
        return False

    lines[row + 1], lines[row] = lines[row], lines[row + 1]
    area.text = "\n".join(lines)
    try:
        area.move_cursor((row + 1, min(col, len(lines[row + 1]))))
    except Exception:
        pass
    return True


def copy_line_up(area: Any) -> bool:
    """Duplicate current line upwards."""
    if not hasattr(area, "text") or not hasattr(area, "cursor_location"):
        return False
    lines = area.text.splitlines() or [""]
    row, col = area.cursor_location
    if row < 0 or row >= len(lines):
        return False

    lines.insert(row, lines[row])
    area.text = "\n".join(lines)
    try:
        area.move_cursor((row, col))
    except Exception:
        pass
    return True


def copy_line_down(area: Any) -> bool:
    """Duplicate current line downwards."""
    if not hasattr(area, "text") or not hasattr(area, "cursor_location"):
        return False
    lines = area.text.splitlines() or [""]
    row, col = area.cursor_location
    if row < 0 or row >= len(lines):
        return False

    lines.insert(row + 1, lines[row])
    area.text = "\n".join(lines)
    try:
        area.move_cursor((row + 1, col))
    except Exception:
        pass
    return True


def insert_line_below(area: Any) -> bool:
    """Insert a new line below and move cursor to it."""
    if not hasattr(area, "text") or not hasattr(area, "cursor_location"):
        return False
    lines = area.text.splitlines() or [""]
    row, col = area.cursor_location
    if row < 0 or row >= len(lines):
        row = len(lines) - 1

    current_line = lines[row] if row < len(lines) else ""
    indent = current_line[:len(current_line) - len(current_line.lstrip())]

    lines.insert(row + 1, indent)
    area.text = "\n".join(lines)
    try:
        area.move_cursor((row + 1, len(indent)))
    except Exception:
        pass
    return True


def insert_line_above(area: Any) -> bool:
    """Insert a new line above and move cursor to it."""
    if not hasattr(area, "text") or not hasattr(area, "cursor_location"):
        return False
    lines = area.text.splitlines() or [""]
    row, col = area.cursor_location
    if row < 0:
        row = 0

    current_line = lines[row] if row < len(lines) else ""
    indent = current_line[:len(current_line) - len(current_line.lstrip())]

    lines.insert(row, indent)
    area.text = "\n".join(lines)
    try:
        area.move_cursor((row, len(indent)))
    except Exception:
        pass
    return True


def select_next_occurrence(area: Any) -> bool:
    """Select next matching occurrence of current selection or word under cursor."""
    if not hasattr(area, "text") or not hasattr(area, "cursor_location"):
        return False
    sel = getattr(area, "selected_text", None)
    if not sel:
        # Get word under cursor
        lines = area.text.splitlines() or [""]
        row, col = area.cursor_location
        if row < len(lines):
            line = lines[row]
            start = col
            while start > 0 and (line[start - 1].isalnum() or line[start - 1] == "_"):
                start -= 1
            end = col
            while end < len(line) and (line[end].isalnum() or line[end] == "_"):
                end += 1
            sel = line[start:end]
            if sel and hasattr(area, "selection"):
                try:
                    area.selection = area.selection.__class__((row, start), (row, end))
                except Exception:
                    pass

    if not sel:
        return False

    # Find next occurrence after cursor
    full_text = area.text
    lines = full_text.splitlines() or [""]
    cur_row, cur_col = area.cursor_location
    n = len(lines)
    for i in range(n + 1):
        row = (cur_row + i) % n if n else 0
        line = lines[row] if row < len(lines) else ""
        search_from = cur_col + len(sel) if i == 0 else 0
        col = line.find(sel, search_from)
        if col == -1 and i == 0:
            col = line.find(sel)
        if col != -1:
            try:
                area.move_cursor((row, col))
                if hasattr(area, "selection"):
                    area.selection = area.selection.__class__((row, col), (row, col + len(sel)))
                area.scroll_cursor_visible()
                return True
            except Exception:
                pass
    return False
