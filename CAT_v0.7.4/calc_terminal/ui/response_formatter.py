"""
CAT Response Formatter.

Formats AI model responses into clean, elegant, high-readability terminal representations:
- Markdown table formatting
- Code blocks with syntax highlighting indicators
- Mathematical notation and LaTeX conversion
- Tool output summaries
- Collapsible detail views
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


class ResponseFormatter:
    """Terminal-optimized output formatter."""

    def __init__(self):
        pass

    def format_response(self, text: str, include_math_render: bool = True) -> str:
        """Processes raw markdown and formats math and code blocks for terminal reading."""
        if not text:
            return ""

        out = text

        # Format inline and block LaTeX if requested
        if include_math_render:
            try:
                from ..compute import latex_engine
                # Replace $$ ... $$ blocks with formatted Unicode
                def _rep_block(m):
                    latex = m.group(1).strip()
                    rendered = latex_engine.render_to_terminal_unicode(latex)
                    return f"\n  {rendered}\n"
                out = re.sub(r"\$\$([^\$]+)\$\$", _rep_block, out)
            except Exception:
                pass

        # Clean trailing whitespace on lines
        lines = [l.rstrip() for l in out.splitlines()]
        return "\n".join(lines)

    def format_tool_summary(self, steps: List[Any]) -> str:
        """Formats executed tool steps into a clean, concise bulleted summary."""
        if not steps:
            return "No external tools were run."

        lines = ["### Executed Operations:"]
        for step in steps:
            if isinstance(step, (list, tuple)) and len(step) >= 2:
                name = step[0]
                args = step[1] if isinstance(step[1], dict) else {}
                target = (
                    args.get("path")
                    or args.get("command")
                    or args.get("query")
                    or args.get("url")
                    or args.get("target_kitty")
                    or ""
                )
                tgt_str = f" `{target}`" if target else ""
                lines.append(f"- **{name}**{tgt_str}")
        return "\n".join(lines)


response_formatter = ResponseFormatter()
