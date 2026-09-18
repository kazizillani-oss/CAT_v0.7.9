"""CAT Live Preview — Diagnostics & Error Mapping (calc_terminal/preview/diagnostics.py).

Unified diagnostic model and error navigation:
- Normalizes errors from browser runtime, dev server, build, and editor.
- Extracts file, line, and column coordinates from error messages.
- Supports jumping from Problems/Console errors directly into the source code.
"""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class SourceLocation:
    """Exact source code target of a diagnostic error."""
    file: str
    line: Optional[int] = None
    column: Optional[int] = None


@dataclass
class Diagnostic:
    """Normalized diagnostic entry across browser, server, build, and editor."""
    id: str
    severity: str  # "info", "warning", "error"
    message: str
    file: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None
    source: str = "editor"  # "browser", "server", "build", "editor"
    timestamp: float = 0.0


# Regex patterns to detect file:line:col in runtime and build errors
# e.g., main.js:42:17, ./src/App.tsx (12:5), File "app.py", line 123
_LOCATION_PATTERNS = [
    re.compile(r'([a-zA-Z0-9_\-\.\/\\]+\.(?:js|jsx|ts|tsx|py|html|css)):(\d+):(\d+)'),
    re.compile(r'([a-zA-Z0-9_\-\.\/\\]+\.(?:js|jsx|ts|tsx|py|html|css)):(\d+)'),
    re.compile(r'File "([^"]+)", line (\d+)'),
    re.compile(r'([a-zA-Z0-9_\-\.\/\\]+\.(?:js|jsx|ts|tsx|py|html|css))\s*\((\d+):(\d+)\)'),
]


def parse_error_location(error_text: str, workspace_root: Optional[str] = None) -> Optional[SourceLocation]:
    """Extract source file, line, and column from an error string."""
    if not error_text:
        return None
    for pattern in _LOCATION_PATTERNS:
        match = pattern.search(error_text)
        if match:
            groups = match.groups()
            raw_path = groups[0]
            line = int(groups[1]) if len(groups) > 1 and groups[1] else None
            col = int(groups[2]) if len(groups) > 2 and groups[2] else None

            # Resolve relative paths against workspace root if provided
            abs_path = raw_path
            if workspace_root and not os.path.isabs(raw_path):
                cand = os.path.join(workspace_root, raw_path)
                if os.path.exists(cand):
                    abs_path = os.path.abspath(cand)

            return SourceLocation(file=abs_path, line=line, column=col)
    return None


class DiagnosticsManager:
    """Collects and organizes diagnostics from all runtime and build systems."""

    def __init__(self) -> None:
        self._diagnostics: List[Diagnostic] = []

    def add(self, severity: str, message: str, file: Optional[str] = None,
            line: Optional[int] = None, column: Optional[int] = None,
            source: str = "editor") -> Diagnostic:
        """Add a new diagnostic item."""
        # Auto-parse location if not explicitly provided
        if not file or line is None:
            loc = parse_error_location(message)
            if loc:
                file = file or loc.file
                line = line if line is not None else loc.line
                column = column if column is not None else loc.column

        diag = Diagnostic(
            id=uuid.uuid4().hex[:8],
            severity=severity.lower(),
            message=message.strip(),
            file=file,
            line=line,
            column=column,
            source=source,
            timestamp=__import__("time").time(),
        )
        self._diagnostics.append(diag)
        if len(self._diagnostics) > 200:
            del self._diagnostics[:-200]
        return diag

    def list_diagnostics(self, severity: Optional[str] = None, source: Optional[str] = None) -> List[Diagnostic]:
        """Return matching diagnostics filtered by severity and/or source."""
        results = list(self._diagnostics)
        if severity:
            results = [d for d in results if d.severity == severity.lower()]
        if source:
            results = [d for d in results if d.source == source.lower()]
        return results

    def clear(self, source: Optional[str] = None) -> None:
        """Clear diagnostics, optionally for a specific source."""
        if source:
            self._diagnostics = [d for d in self._diagnostics if d.source != source.lower()]
        else:
            self._diagnostics.clear()


# Global diagnostics singleton
_GLOBAL_DIAGNOSTICS_MANAGER: Optional[DiagnosticsManager] = None


def get_diagnostics_manager() -> DiagnosticsManager:
    """Return global DiagnosticsManager singleton."""
    global _GLOBAL_DIAGNOSTICS_MANAGER
    if _GLOBAL_DIAGNOSTICS_MANAGER is None:
        _GLOBAL_DIAGNOSTICS_MANAGER = DiagnosticsManager()
    return _GLOBAL_DIAGNOSTICS_MANAGER
