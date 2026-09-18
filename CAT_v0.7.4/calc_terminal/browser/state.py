"""CAT browser/ — the UI state model (spec section 22).

One place owns the vocabulary for the right pane. The UI derives its
layout from these states instead of scattered booleans:

    WorkspaceMode   CODE | PREVIEW          what the right pane shows
    PaneMode        DEFAULT | FULLSCREEN    right pane vs whole window
    PreviewState    STOPPED | STARTING | RUNNING | ERROR
    ServerState     STOPPED | STARTING | RUNNING | ERROR
    EditorState     EMPTY | HAS_TABS        editor tab strip state
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple


class WorkspaceMode(Enum):
    CODE = "code"
    PREVIEW = "preview"
    SPLIT = "split"


class PaneMode(Enum):
    DEFAULT = "default"
    FULLSCREEN = "fullscreen"


class PreviewState(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


class ServerState(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


class EditorState(Enum):
    EMPTY = "empty"
    HAS_TABS = "has_tabs"


@dataclass
class PreviewSnapshot:
    """One immutable view of a loaded page — everything the preview
    panel renders. Produced by BrowserEngine after every navigation /
    reload / hot update."""
    url: str = ""
    title: str = ""
    ok: bool = True
    error: str = ""
    # Structured outline extracted from the LIVE DOM (headings, text,
    # links, buttons...) so the terminal can show what Chromium sees.
    outline_lines: Tuple[str, ...] = ()
    console_tail: Tuple[str, ...] = ()      # recent browser console lines
    js_errors: Tuple[str, ...] = ()
    elements: int = 0
    images_loaded: int = 0
    images_broken: int = 0
    status_code: Optional[int] = None
    extra: dict = field(default_factory=dict)

    @property
    def summary_line(self):
        if not self.ok and self.error:
            return f"✗ {self.error}"
        bits = [f"{self.elements} elements"]
        if self.images_loaded or self.images_broken:
            bits.append(f"{self.images_loaded}✓/{self.images_broken}✗ images")
        return " · ".join(bits)
