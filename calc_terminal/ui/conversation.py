"""
CCT UI — the single conversation renderer. ConversationView is the ONLY
scrollable region in the primary UI; ConversationItem is the one bubble
renderer for every turn (user, assistant, system/permission notice) —
there is no second bubble implementation anywhere else in this package.

Each turn renders as a `MessageRow` (a full-width flow container) whose
one child is the bubble itself — the row's own CSS (`cct-row-user` /
`cct-row-assistant` / `cct-row-system`) is what pushes the bubble to the
right, left, or center, so ConversationItem doesn't need to know
anything about layout, only content.

Renders `calc_terminal.session.Turn` data and Rich Markdown text (so
fenced code blocks, lists, and bold/italic come from a real Markdown
renderer instead of a hand-rolled ANSI parser). No chemistry/AI logic:
the one backend call this file makes — code_editor.remember_block — is
purely so /copycode still has something to copy, mirroring what the
fallback CLI already does for the same reason.

Per-message mode coloring (accent/border/badge) is painted from a
frozen `mode_snapshot` dict (see `ai_modes.snapshot()` /
`session.Turn.mode_snapshot`) handed in when a bubble is created —
never from `ai_modes.current_mode()`. That snapshot is applied as an
*inline* style override on the widget (`self.styles.border = ...`),
which Textual always resolves ahead of stylesheet/CSS-variable rules,
so a later app-wide `refresh_css()` (fired on every AI-mode switch —
see ui/app.py's `_set_ai_mode`) can repaint the composer and any
brand-new bubble without touching a single already-mounted one. This
is what makes "every message permanently remembers the mode that
created it" true: render from `Message.mode_snapshot`, never from
whatever mode happens to be active right now.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import re
import time

TEXTUAL_AVAILABLE = True
try:
    from textual.containers import VerticalScroll, Horizontal, Vertical
    from textual.widgets import Static, Button
    from textual.geometry import Size
    from rich.markdown import Markdown
    from rich.console import Group
    from rich.text import Text
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
except Exception:
    TEXTUAL_AVAILABLE = False

_FENCE_RE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)

from ..mathtext import render_math as _render_math
from ..mathtext import chem_formula as _chem_formula
from ..mathtext import render_inline as _render_inline
from ..mathtext import find_latex_errors
from . import theme_css

# Chemistry notation worth visually calling out: formulas (element symbols
# with digit/subscript counts, 2+ elements), common electrochemistry/acid-
# base symbols, and unicode subscripts/superscripts on their own.
_FORMULA_RE = re.compile(
    r"\b(?:[A-Z][a-z]?[\u2080-\u2089\d]*){2,}(?:\^?\d*[+\-])?[\u2070-\u2079\u00b9\u00b2\u00b3\u207a\u207b]*"
)
_SYMBOL_RE = re.compile(
    r"\b(?:pH|pOH|pKa|pKb|Ka|Kb|Ksp|Keq|ΔH|ΔS|ΔG|ΔU|Molarity|Molality)\b"
)
_NON_CHEM_WORDS = {
    "URL", "URI", "PM", "AM", "API", "HTML", "CSS", "JSON", "VITE", "NPM", "NODE",
    "HTTP", "HTTPS", "OK", "ID", "CPU", "RAM", "GPU", "IP", "DB", "UI", "OS", "EOF",
    "CLI", "CAT", "AI", "APP", "DEV", "SRC", "DOC", "PORT", "LAN", "WAN", "DNS",
    "DOM", "XML", "SQL", "CSV", "TS", "JS", "PY", "MD", "TXT", "TODO", "FIXME",
    "NOTE", "INFO", "WARN", "ERROR", "FATAL", "DEBUG", "PATH", "HOST", "POST",
    "GET", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "TRUE", "FALSE", "NULL",
    "NONE", "PID", "TTY", "SSH", "SSL", "TLS", "TCP", "UDP", "V8", "ES6", "UTF8",
}
_ALREADY_CODE_RE = re.compile(r"`[^`]*`")


def _is_real_chem_formula(tok: str) -> bool:
    """True only if `tok` is a genuine chemical formula, not an ordinary
    English acronym or programming abbreviation like URL, PM, API, HTML, JSON."""
    if not tok or tok in _NON_CHEM_WORDS:
        return False
    # Pure uppercase letters with no digits/subscripts/superscripts/charges are acronyms
    if tok.isalpha() and tok.isupper():
        return False
    # Must have digits, Unicode subscripts/superscripts, ionic charge, or mixed-case element pattern
    has_digit = any(c.isdigit() or '\u2080' <= c <= '\u2089' or '\u2070' <= c <= '\u2079' or c in '\u00b9\u00b2\u00b3' for c in tok)
    has_charge = any(c in '+-^' for c in tok)
    has_mixed_element = bool(re.search(r'[A-Z][a-z]', tok))
    return bool(has_digit or has_charge or has_mixed_element)


def _highlight_chemistry(text):
    """Wraps recognized chemistry notation in inline-code backticks so
    Markdown renders it in its distinct inline-code color/style —
    without touching fenced code blocks (real code stays real code) or
    spans already inside inline code (no double-wrapping)."""
    if not text:
        return text

    def _process_segment(segment):
        # Skip past existing inline-code spans untouched; only highlight
        # the plain-text parts between them.
        out = []
        last = 0
        for m in _ALREADY_CODE_RE.finditer(segment):
            out.append(_wrap_matches(segment[last:m.start()]))
            out.append(m.group(0))
            last = m.end()
        out.append(_wrap_matches(segment[last:]))
        return "".join(out)

    def _wrap_matches(chunk):
        def _repl(m):
            tok = m.group(0)
            if _is_real_chem_formula(tok):
                return f"`{_chem_formula(tok)}`"
            return tok

        chunk = _FORMULA_RE.sub(_repl, chunk)
        chunk = _SYMBOL_RE.sub(lambda m: f"`{m.group(0)}`", chunk)
        return chunk

    if "```" not in text:
        return _process_segment(text)

    # Leave fenced code blocks completely untouched; only highlight the
    # prose segments around them.
    parts = text.split("```")
    for i in range(0, len(parts), 2):  # even indices are outside fences
        parts[i] = _process_segment(parts[i])
    return "```".join(parts)


def _remember_code_blocks(text):
    """Pulls fenced code blocks out of finished assistant text and hands
    them to code_editor.remember_block, so /copycode keeps working
    exactly like it did against the old print()-based renderer. Lazy
    import: code_editor doesn't depend on ui/, but importing it at
    module load time here would mean every conversation render pulls in
    sandbox/security_scanner/aicore for no reason until a code block
    actually shows up."""
    if "```" not in text:
        return
    from .. import code_editor
    for m in _FENCE_RE.finditer(text):
        lang, code = m.group(1), m.group(2)
        code_editor.remember_block(code.rstrip("\n"), lang)


def _format_timestamp(epoch):
    try:
        return time.strftime("%H:%M", time.localtime(epoch))
    except Exception:
        return ""


def _bevel_colors(hex_color):
    """Computes a lighter top-left highlight and a richer bottom-right shadow from a hex color."""
    try:
        c = str(hex_color).lstrip("#")
        if len(c) == 3:
            c = "".join(ch * 2 for ch in c)
        r = int(c[0:2], 16)
        g = int(c[2:4], 16)
        b = int(c[4:6], 16)
        # Highlight: blend +45% towards white for true luminous highlight
        hr = min(255, int(r + (255 - r) * 0.45))
        hg = min(255, int(g + (255 - g) * 0.45))
        hb = min(255, int(b + (255 - b) * 0.45))
        # Shadow: blend -25% darker so it stays distinct and vibrant, NOT black
        sr = max(0, int(r * 0.75))
        sg = max(0, int(g * 0.75))
        sb = max(0, int(b * 0.75))
        return f"#{hr:02x}{hg:02x}{hb:02x}", f"#{sr:02x}{sg:02x}{sb:02x}"
    except Exception:
        return hex_color or "#38bdf8", hex_color or "#0284c7"


def _current_username() -> str:
    """Returns the user's OS account username, or 'User' as fallback."""
    try:
        import os, getpass
        u = os.environ.get("USERNAME") or os.environ.get("USER")
        if not u:
            u = getpass.getuser()
        if u and str(u).strip():
            return str(u).strip()
    except Exception:
        pass
    return "User"


def _code_theme_for_current_theme():
    """Fenced code blocks in assistant replies get syntax highlighting via
    Rich's pygments integration. Pick a theme that's actually readable
    against CCT's own background instead of Rich's 'monokai' default,
    which was never chosen with this app's dark/light palettes in mind."""
    from .. import theme
    return "friendly" if theme.is_light() else "material"


try:
    from rich.markdown import BlockQuote as _RichBlockQuote
    from rich.segment import Segment as _RichSegment

    class CATBlockQuote(_RichBlockQuote):
        style_name = "dim italic"

        def __rich_console__(self, console, options):
            render_options = options.update(width=max(10, options.max_width - 4))
            lines = console.render_lines(self.elements, render_options, style=self.style)
            new_line = _RichSegment("\n")
            padding = _RichSegment("│ ", console.get_style("dim #64748b"))
            for line in lines:
                yield padding
                yield from line
                yield new_line

    Markdown.elements["blockquote_open"] = CATBlockQuote
except Exception:
    pass


def _parse_activity_and_body(raw_text):
    if not raw_text:
        return [], ""
    raw_lines = raw_text.splitlines()
    act_items = []
    body_lines = []

    _ACT_ICONS = (
        "🔧", "⚡", "🧠", "👁", "ℹ", "⚠", "🔬", "💻", "🔍", "🧪",
        "🪲", "🛡", "🏗", "🎨", "📝", "🎯", "⏳", "✔", "✖", "✅"
    )

    for line in raw_lines:
        s = line.strip()
        if not s:
            if body_lines:
                body_lines.append(line)
            continue
        clean_s = re.sub(r'^[>\s]+', '', s)
        has_tool = any(x in clean_s for x in _ACT_ICONS)
        has_mark = any(x in clean_s for x in ("✔ completed", "✖ failed", "⏳ running", "✅ complete"))

        if has_tool or (s.startswith(">") and has_mark):
            parts = re.split(r'(?<=[.)])\s+(?=[>\s]*[🔧⚡🧠👁ℹ⚠])', clean_s)
            for p in parts:
                p_clean = re.sub(r'^[>\s]+', '', p.strip())
                if p_clean:
                    act_items.append(p_clean)
        else:
            body_lines.append(line)

    return act_items, "\n".join(body_lines).strip()


def _format_activity_item(item, is_light=False, accent="#38bdf8"):
    from rich.markup import escape
    item = item.strip()
    if not item:
        return ""

    status_markup = ""
    if "✔ completed" in item or "✅ complete" in item:
        status_markup = "[bold #10b981]✔ completed[/]" if not is_light else "[bold #059669]✔ completed[/]"
        item = re.sub(r'\s*([—–-]\s*)?(✔ completed|✅ complete)\s*', '', item)
    elif "✖ failed" in item:
        status_markup = "[bold #ef4444]✖ failed[/]" if not is_light else "[bold #dc2626]✖ failed[/]"
        item = re.sub(r'\s*([—–-]\s*)?✖ failed\s*', '', item)
    elif "⏳ running" in item:
        status_markup = "[bold #f59e0b]⏳ running...[/]" if not is_light else "[bold #d97706]⏳ running...[/]"
        item = re.sub(r'\s*([—–-]\s*)?⏳ running(\.\.\.)?\s*', '', item)
    elif any(item.startswith(x) for x in ("🔧", "⚡")) and not any(k in item for k in ("✔", "✖", "✅")):
        status_markup = "[bold #f59e0b]⏳ in progress...[/]" if not is_light else "[bold #d97706]⏳ in progress...[/]"

    parts = item.split(None, 1)
    if not parts:
        return ""
    first = parts[0]
    rest = parts[1] if len(parts) > 1 else ""

    if ord(first[0]) > 255:
        icon = first
    else:
        icon = "⚡"
        rest = item

    rest_clean = rest.replace("**", "").replace("`", "").strip()

    if icon in ("🔧", "⚡"):
        t_parts = rest_clean.split(None, 1)
        tool_name = t_parts[0] if t_parts else ""
        target = t_parts[1] if len(t_parts) > 1 else ""
        target_styled = f"[#94a3b8]{escape(target)}[/]" if not is_light else f"[#475569]{escape(target)}[/]"
        status_part = f"   {status_markup}" if status_markup else ""
        return f"{icon}  [bold {accent}]{escape(tool_name)}[/]  {target_styled}{status_part}".strip()

    if icon == "⚠":
        icon_styled = "[#f59e0b]⚠[/]"
        text_styled = f"[#fde68a]{escape(rest_clean)}[/]" if not is_light else f"[#b45309]{escape(rest_clean)}[/]"
    elif icon in ("👁", "ℹ"):
        icon_styled = f"[#38bdf8]{icon}[/]"
        text_styled = f"[#94a3b8]{escape(rest_clean)}[/]" if not is_light else f"[#475569]{escape(rest_clean)}[/]"
    else:
        icon_styled = f"[{accent}]{icon}[/]"
        text_styled = f"[#cbd5e1]{escape(rest_clean)}[/]" if not is_light else f"[#334155]{escape(rest_clean)}[/]"

    status_part = f"   {status_markup}" if status_markup else ""
    return f"{icon_styled}  {text_styled}{status_part}".strip()


def _build_activity_widget(act_items, is_light=False, accent="#38bdf8"):
    from rich.markup import escape
    from rich.table import Table
    from rich.panel import Panel
    from rich import box

    if not act_items:
        return None

    table = Table.grid(padding=(0, 2))
    table.add_column(justify="left", no_wrap=True)
    table.add_column(justify="left")
    table.add_column(justify="right", no_wrap=True)

    for item in act_items:
        item = item.strip()
        if not item:
            continue

        status_markup = ""
        if "✔ completed" in item or "✅ complete" in item:
            status_markup = "[bold #10b981]✔ completed[/]" if not is_light else "[bold #059669]✔ completed[/]"
            item = re.sub(r'\s*([—–-]\s*)?(✔ completed|✅ complete)\s*', '', item)
        elif "✖ failed" in item:
            status_markup = "[bold #ef4444]✖ failed[/]" if not is_light else "[bold #dc2626]✖ failed[/]"
            item = re.sub(r'\s*([—–-]\s*)?✖ failed\s*', '', item)
        elif "⏳ running" in item:
            status_markup = "[bold #f59e0b]⏳ running...[/]" if not is_light else "[bold #d97706]⏳ running...[/]"
            item = re.sub(r'\s*([—–-]\s*)?⏳ running(\.\.\.)?\s*', '', item)
        elif any(item.startswith(x) for x in ("🔧", "⚡")) and not any(k in item for k in ("✔", "✖", "✅")):
            status_markup = "[bold #f59e0b]⏳ in progress...[/]" if not is_light else "[bold #d97706]⏳ in progress...[/]"

        parts = item.split(None, 1)
        first = parts[0] if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if first and ord(first[0]) > 255:
            icon = first
        else:
            icon = "⚡"
            rest = item

        rest_clean = rest.replace("**", "").replace("`", "").strip()

        if icon in ("🔧", "⚡"):
            t_parts = rest_clean.split(None, 1)
            tool_name = t_parts[0] if t_parts else ""
            target = t_parts[1] if len(t_parts) > 1 else ""
            target_styled = f"[#94a3b8]{escape(target)}[/]" if not is_light else f"[#475569]{escape(target)}[/]"
            table.add_row(
                Text.from_markup(f"{icon}  [bold {accent}]{escape(tool_name)}[/]"),
                Text.from_markup(target_styled),
                Text.from_markup(status_markup),
            )
        else:
            if icon == "⚠":
                icon_styled = "[#f59e0b]⚠[/]"
                text_styled = f"[#fde68a]{escape(rest_clean)}[/]" if not is_light else f"[#b45309]{escape(rest_clean)}[/]"
            elif icon in ("👁", "ℹ"):
                icon_styled = f"[#38bdf8]{icon}[/]"
                text_styled = f"[#94a3b8]{escape(rest_clean)}[/]" if not is_light else f"[#475569]{escape(rest_clean)}[/]"
            else:
                icon_styled = f"[{accent}]{icon}[/]"
                text_styled = f"[#cbd5e1]{escape(rest_clean)}[/]" if not is_light else f"[#334155]{escape(rest_clean)}[/]"

            table.add_row(
                Text.from_markup(f"{icon_styled}"),
                Text.from_markup(text_styled),
                Text.from_markup(status_markup),
            )

    border_color = accent if not is_light else "#64748b"
    return Panel(
        table,
        title=f"[bold {border_color}]⚡ Activity & Tools[/]",
        title_align="left",
        border_style=border_color,
        box=box.SQUARE,
        expand=False,
        padding=(0, 1),
    )


if TEXTUAL_AVAILABLE:

    class WelcomeBanner(Static):
        """The empty-state banner: centered logo + a tip line, matching
        the reference's pre-chat screen. Lives inside ConversationView
        as its first (and only, while empty) item; ConversationView
        removes it the moment a real turn is added."""

        def __init__(self, logo_lines, tip_text, id="cct-welcome"):
            super().__init__("", id=id)
            self._logo_lines = logo_lines
            self._tip_text = tip_text

        def on_mount(self):
            from . import theme_css
            accent = theme_css.current_hex("accent")
            faint = theme_css.current_hex("text-faint")
            logo = "\n".join(f"[{accent} b]{line}[/]" for line in self._logo_lines)
            self.update(f"{logo}\n\n[{faint}]\u25cf Tip  {self._tip_text}[/]")


    def short_model_name(name: str) -> str:
        """Produce clean, compact model name for chip telemetry.
        E.g. 'nvidia/nemotron-3-ultra-550b-a55b' -> 'nemotron-3-ultra'
             'nvidia/nemotron-3.5-lightning-30b-a3b' -> 'nemotron-3.5-lightning'
             'nvidia/llama-3.1-nemotron-70b-instruct' -> 'nemotron-70b'
             'meta/llama-3.1-70b-instruct' -> 'llama-3.1-70b'
        """
        if not name:
            return ""
        m = str(name).strip()
        if "/" in m:
            m = m.split("/", 1)[1]
        m_low = m.lower()
        if "nemotron-3-ultra" in m_low or "nemotron-3-ultra-550b" in m_low:
            return "nemotron-3-ultra"
        if "nemotron-3.5-lightning" in m_low:
            return "nemotron-3.5-lightning"
        if "nemotron-70b" in m_low:
            return "nemotron-70b"
        m = re.sub(r'-(?:\d{4}-\d{2}-\d{2}|\d{8})$', '', m)
        m = re.sub(r'-(?:latest|preview)$', '', m)
        m = re.sub(r'-a[0-9a-f]+$', '', m)
        return m

    class ConversationItem(Static):
        """One turn's bubble. `role` is 'user' | 'assistant' | 'system'.
        Assistant text renders as real Markdown (code fences, lists,
        emphasis, better typography generally) inside a wide bubble;
        user turns render as bold text inside a narrower accent bubble;
        system notes render as plain centered italic text with no
        bubble chrome. Layout (left/right/center) is the owning
        MessageRow's job, not this widget's — it only ever renders its
        own content and reports how it wants to look.
        """

        def __init__(self, turn_id, role, text="", id=None, streaming=False,
                     timestamp=None, show_timestamp=True, meta_lines=None,
                     mode_snapshot=None, attachments=None, contributions=None):
            self.turn_id = turn_id
            self.role = role
            self._text = text
            self._streaming = streaming
            self._timestamp = timestamp if timestamp is not None else time.time()
            self._show_timestamp = show_timestamp
            # Rich-markup lines from thinking.completion_summary_lines()
            # (spec #25's "Message Completion" block) — rendered under
            # the bubble once a turn finishes, empty while streaming.
            self._meta_lines = meta_lines or []
            self._contributions = contributions or []
            # v0.7.6 Patch 1, Fix 6: attached file paths, rendered as
            # small bordered cards inside the bubble (see
            # _attachment_cards). Plain paths — same list the session's
            # Turn carries.
            self._attachments = list(attachments or [])
            # Frozen mode metadata (see module docstring) — a plain dict
            # from ai_modes.snapshot()/Turn.mode_snapshot, or None for
            # bubbles that don't carry mode coloring (e.g. some system
            # notes). Captured once here and never re-read from
            # ai_modes afterwards.
            self._mode_snapshot = mode_snapshot
            classes = f"cct-bubble cct-bubble-{role}"
            super().__init__(self._build_content(), id=id, classes=classes)

        def get_content_width(self, container: Size, viewport: Size) -> int:
            if self.role == "user":
                lines = (self._text or "").splitlines()
                max_line = max((len(l) for l in lines), default=0) if lines else 0
                ts = _format_timestamp(self._timestamp) if self._show_timestamp else ""
                snap = self._mode_snapshot or {}
                ic = snap.get("icon", "")
                lb = snap.get("label", "")
                user_name = _current_username()
                header_text = f"👤 {user_name}  {ts}  {ic} {lb}".strip()
                header_len = len(header_text) + 4
                max_w = max(max_line, header_len, 28)
                max_cap = int(container.width * 0.8) if container and container.width else 80
                return min(max_w + 6, max_cap)
            if self.role == "system":
                raw_text = (self._text or "").strip()
                try:
                    import rich.cells
                    tlen = rich.cells.cell_len(raw_text)
                except Exception:
                    tlen = len(raw_text)
                needed = tlen + 12
                max_w = int(container.width * 0.95) if container and container.width else 95
                return min(max(needed, 38), max_w)
            return super().get_content_width(container, viewport)

        def _mode_badge(self):
            """A small 'created in <mode>' badge, colored with the mode's
            frozen accent — built entirely from `self._mode_snapshot`,
            never from ai_modes.current_mode(). Returns None while
            streaming (nothing's finished yet) or if this bubble carries
            no mode snapshot at all."""
            if self._streaming or not self._mode_snapshot:
                return None
            snap = self._mode_snapshot
            badge = Text(f"{snap['icon']} {snap['label']}", style=f"{snap['accent_hex']} bold")
            badge.justify = "right"
            return badge

        def _attachment_cards(self):
            """v0.7.6 Patch 1, Fix 6: one small rounded card per
            attached file, inside the bubble — icon + filename + size
            (plus the full path, dimmed, when it fits). Rendered as a
            Rich Table so the card gets a real border; returns None
            when there are no attachments.

            v0.7.8.1: attachments arrive as normalized Attachment
            objects (the same objects the AI pipeline consumes) or —
            for legacy callers — plain path strings. Cards now render
            the honest extraction state: 'reading…' while extraction
            runs and the error text when it failed, so the UI never
            claims a file was attached when the model can't read it
            (spec section 10/13)."""
            if not self._attachments:
                return None
            from .attachments import attachment_kind, format_size, _size_label
            from .. import attachments as _core
            from . import theme_css
            faint = theme_css.current_hex("text-faint")
            muted = theme_css.current_hex("text-muted")
            err = theme_css.current_hex("error")
            cards = Table(box=box.ROUNDED, expand=False, show_header=False,
                          show_edge=True, padding=(0, 1))
            for att in self._attachments:
                if isinstance(att, str):
                    icon, kind = attachment_kind(att)
                    name = att.rstrip("/\\").split("/")[-1].split("\\")[-1]
                    size_txt = format_size(att)
                    detail = f"{kind}\u00b7{size_txt}" if size_txt else kind
                    cards.add_row(f"[{muted}]{icon} {name}[/]",
                                  f"[{faint}]{detail}[/]")
                    continue
                path = getattr(att, "path", "") or ""
                icon, _ext_kind = attachment_kind(path)
                kind = getattr(att, "kind", None) or _ext_kind
                name = getattr(att, "name", None) or path.rstrip("/\\").split("/")[-1].split("\\")[-1]
                status = getattr(att, "extraction_status", None)
                size_txt = _size_label(getattr(att, "size", 0))
                if status == _core.STATUS_FAILED:
                    detail = (getattr(att, "error", None) or "could not be read")
                    cards.add_row(f"[{err}]\u26a0 {name}[/]",
                                  f"[{err}]{detail}[/]")
                elif status == _core.STATUS_READY:
                    cards.add_row(f"[{muted}]{icon} {name}[/]",
                                  f"[{faint}]{kind}\u00b7{size_txt}[/]")
                else:
                    cards.add_row(f"[{muted}]{icon} {name}[/]",
                                  f"[{faint}]reading\u2026[/]")
            return cards

        def _format_telemetry(self, meta_lines=None):
            m_lines = meta_lines if meta_lines is not None else self._meta_lines
            if not m_lines and not getattr(self, "_contributions", None):
                return None
            raw_text = " ".join(str(l) for l in m_lines)
            try:
                plain_text = Text.from_markup(raw_text).plain
            except Exception:
                plain_text = re.sub(r'\[/?[a-zA-Z0-9_#=:\s\.\,\-]+\]', '', raw_text)

            # Extract Model
            model_m = re.search(r'Model:\s*([^\s·\]]+)', plain_text, re.IGNORECASE)
            model = model_m.group(1) if model_m else None

            # Extract Time / Duration
            time_m = re.search(r'Time:\s*([^\s·\]]+)', plain_text, re.IGNORECASE)
            duration = time_m.group(1) if time_m else None

            # Extract TTFB
            ttfb_m = re.search(r'TTFB:\s*([^\s·\]]+)', plain_text, re.IGNORECASE)
            ttfb = ttfb_m.group(1) if ttfb_m else None

            # Extract Tokens
            tokens_m = re.search(r'Tokens:\s*([^\s·\]]+)', plain_text, re.IGNORECASE)
            tokens = tokens_m.group(1) if tokens_m else None

            # Extract Calls or Commands
            calls_m = re.search(r'Calls:\s*([^\s·\]]+)', plain_text, re.IGNORECASE)
            calls = calls_m.group(1) if calls_m else None

            cmds_m = re.search(r'Commands\s+used:\s*([^·\]\n]+)', plain_text, re.IGNORECASE)
            cmds = cmds_m.group(1).strip() if cmds_m else None

            # Check for warnings/errors like LaTeX issues
            warnings = [l for l in self._meta_lines if "LaTeX:" in str(l) or "⚠" in str(l) or "error" in str(l).lower()]

            # Determine model contributions
            raw_c_attr = getattr(self, "_contributions", None)
            contribs = []
            if isinstance(raw_c_attr, dict):
                if raw_c_attr.get("main_model") or raw_c_attr.get("pct_main") is not None:
                    contribs.append({
                        "model": raw_c_attr.get("main_model", model or "main"),
                        "is_backup": False,
                        "percent": float(raw_c_attr.get("pct_main", 0.0)),
                        "tokens": raw_c_attr.get("main_tokens", 0),
                    })
                pct_b = float(raw_c_attr.get("pct_backup", 0.0))
                if pct_b > 0 or (raw_c_attr.get("is_backup") and raw_c_attr.get("backup_model")):
                    contribs.append({
                        "model": raw_c_attr.get("backup_model", "backup"),
                        "is_backup": True,
                        "percent": pct_b,
                        "tokens": raw_c_attr.get("backup_tokens", 0),
                        "success": bool(raw_c_attr.get("is_backup")),
                    })
            elif isinstance(raw_c_attr, (list, tuple)):
                contribs = [c for c in raw_c_attr if isinstance(c, dict)]

            if not contribs:
                # Fallback to parsing Contribution line from meta text
                c_match = re.search(r'Contribution:\s*([^·\]\n]+)', plain_text, re.IGNORECASE)
                if c_match:
                    raw_c = c_match.group(1).strip()
                    # e.g., "Backup 100%: nemotron-3.5-lightning" or "Main 0% ... Backup 100%"
                    if "backup 100%" in raw_c.lower():
                        contribs = [
                            {"model": model or "main", "is_backup": False, "percent": 0.0},
                            {"model": model or "backup", "is_backup": True, "percent": 100.0, "success": True},
                        ]

            parts = [Text("✓ Complete", style="green bold")]

            # Model & Contribution Pill
            if contribs:
                main_items = [c for c in contribs if not c.get("is_backup")]
                backup_items = [c for c in contribs if c.get("is_backup")]
                main_pct = sum(c.get("percent", 0.0) for c in main_items)
                backup_pct = sum(c.get("percent", 0.0) for c in backup_items)
                main_m = short_model_name(main_items[0].get("model") if main_items else "")
                backup_m = short_model_name(backup_items[0].get("model") if backup_items else "")

                parts.append(Text(" · ", style="dim"))
                if backup_pct > 0:
                    # Failover took place!
                    if main_pct == 0:
                        parts.append(Text("🛡️ Backup 100%", style="bold #e0af68"))
                        if backup_m:
                            parts.append(Text(f" {backup_m}", style="bold #7aa2f7"))
                        if main_m:
                            parts.append(Text(f" (Main 0% {main_m})", style="dim"))
                        else:
                            parts.append(Text(" (Main 0%)", style="dim"))
                    else:
                        parts.append(Text(f"⚖️ {main_m} ({main_pct:.0f}%)", style="bold #7aa2f7"))
                        parts.append(Text(" · ", style="dim"))
                        parts.append(Text(f"🛡️ {backup_m} (Backup {backup_pct:.0f}%)", style="bold #e0af68"))
                else:
                    # Main model answered completely (normal)
                    chosen_m = main_m or short_model_name(model)
                    parts.append(Text(f"🏷 {chosen_m}", style="bold #7aa2f7"))
                    parts.append(Text(" (Main 100%)", style="dim"))
            elif model:
                parts.append(Text(" · ", style="dim"))
                parts.append(Text(f"🏷 {short_model_name(model)}", style="bold #7aa2f7"))

            # Duration & TTFB
            if duration:
                parts.append(Text(" · ", style="dim"))
                time_str = f"⏱ {duration}"
                if ttfb:
                    time_str += f" (TTFB {ttfb})"
                parts.append(Text(time_str, style="dim"))

            # Tokens
            if tokens:
                parts.append(Text(" · ", style="dim"))
                tok_str = tokens if "token" in tokens.lower() else f"{tokens} tokens"
                parts.append(Text(f"⚡ {tok_str}", style="dim"))

            # Calls / Commands
            if calls:
                parts.append(Text(" · ", style="dim"))
                call_label = f"{calls} call" if calls == "1" else f"{calls} calls"
                parts.append(Text(f"📊 {call_label}", style="dim"))
            elif cmds:
                parts.append(Text(" · ", style="dim"))
                parts.append(Text(f"📊 {cmds}", style="dim"))

            chip_text = Text.assemble(*parts)

            rows = [chip_text]
            for w in warnings:
                try:
                    rows.append(Text.from_markup(w))
                except Exception:
                    rows.append(Text(str(w)))

            tbl = Table(box=box.ROUNDED, expand=False, show_header=False,
                        show_edge=True, padding=(0, 1))
            for r in rows:
                tbl.add_row(r)
            return tbl

        def _build_content(self):
            ts = _format_timestamp(self._timestamp) if self._show_timestamp else ""
            snap = self._mode_snapshot or {}
            accent = snap.get("accent_hex", "#38bdf8")
            hi, sh = _bevel_colors(accent)
            try:
                from .. import theme as _theme
                is_light = _theme.is_light()
                t = _theme.get_theme_obj()
            except Exception:
                is_light = False
                t = None

            if self.role == "user":
                mode_lbl = snap.get("label", "Notebook")
                mode_ic = snap.get("icon", "🐱")
                user_name = _current_username()
                badge_style = f"bold on {accent} #ffffff" if not is_light else f"bold on {accent} #0f172a"
                header_elements = [
                    Text(f" 👤 {user_name} ", style=badge_style),
                    Text(" "),
                    Text(f" {mode_ic} {mode_lbl} ", style=f"{accent} bold"),
                ]
                if ts:
                    header_elements.append(Text(f" {ts}", style="dim"))
                header_row = Text.assemble(*header_elements)
                divider = Text("─" * 46, style=f"{accent} dim")
                body_style = "bold #ffffff" if not is_light else "bold #0f172a"
                body = Text(_render_inline(self._text), style=body_style)
                parts = [header_row, divider, body]
                cards = self._attachment_cards()
                if cards is not None:
                    parts.append(cards)
                return Group(*parts)

            if self.role == "system":
                snap = self._mode_snapshot or {}

                if is_light and t:
                    icon_accent = t.hex("accent")
                    hl_accent = t.hex("accent")
                    text_color = t.hex("text")
                    dim_color = t.hex("text_muted")
                else:
                    accent = snap.get("accent_hex", theme_css.current_hex("accent"))
                    icon_accent = accent
                    hl_accent = accent
                    text_color = "bold"
                    dim_color = "dim"

                txt = (self._text or "").strip()
                if txt.startswith("Theme switched to "):
                    theme_part = txt[len("Theme switched to "):].rstrip(".")
                    return Text.assemble(
                        (" ℹ  ", f"{icon_accent} bold"),
                        ("Theme switched to ", f"{text_color} bold" if is_light else "bold"),
                        (f"{theme_part}", f"{hl_accent} bold"),
                        (".", f"{text_color} bold" if is_light else "bold"),
                        (" ",)
                    )
                elif txt.startswith("Opened folder:"):
                    folder_path = txt[len("Opened folder:"):].strip()
                    return Text.assemble(
                        (" ℹ  ", f"{icon_accent} bold"),
                        ("Opened folder: ", f"{text_color} bold" if is_light else "bold"),
                        (folder_path, f"{dim_color} italic" if is_light else "dim italic"),
                        (" ",)
                    )
                elif txt.startswith("Permission mode:"):
                    mode_part = txt[len("Permission mode:"):].strip()
                    return Text.assemble(
                        (" ℹ  ", f"{icon_accent} bold"),
                        ("Permission mode: ", f"{text_color} bold" if is_light else "bold"),
                        (f"{mode_part}", f"{hl_accent} bold"),
                        (" ",)
                    )
                elif ":" in txt and not txt.startswith("http"):
                    prefix, rest = txt.split(":", 1)
                    return Text.assemble(
                        (" ℹ  ", f"{icon_accent} bold"),
                        (f"{prefix.strip()}: ", f"{text_color} bold" if is_light else "bold"),
                        (f"{rest.strip()}", f"{dim_color}" if is_light else "dim"),
                        (" ",)
                    )
                else:
                    return Text.assemble(
                        (" ℹ  ", f"{icon_accent} bold"),
                        (f"{txt}", f"{text_color} bold" if is_light else "bold"),
                        (" ",)
                    )

            # assistant — real Markdown
            raw_text = self._text or ""
            thought_text = ""
            answer_text = raw_text

            if "<think>" in raw_text:
                parts = raw_text.split("<think>", 1)
                pre_think = parts[0]
                rest = parts[1]
                if "</think>" in rest:
                    thought_part, post_think = rest.split("</think>", 1)
                    thought_text = thought_part.strip()
                    answer_text = (pre_think + post_think).strip()
                else:
                    # Still streaming thinking!
                    thought_text = rest.strip()
                    answer_text = pre_think.strip()

            # Separate activity/tool execution lines from the clean answer body
            act_items, clean_answer = _parse_activity_and_body(answer_text)

            mode_lbl = snap.get("label", "Assistant")
            mode_ic = snap.get("icon", "🤖")
            badge_style = f"bold on {accent} #ffffff" if not is_light else f"bold on {accent} #0f172a"
            header_elements = [
                Text(f" {mode_ic} CAT Bot ", style=badge_style),
                Text(" "),
                Text(f" {mode_lbl} ", style=f"{accent} bold"),
            ]
            if ts and not self._streaming:
                header_elements.append(Text(f"  {ts}", style="dim"))
            header_row = Text.assemble(*header_elements)
            divider = Text("─" * 48, style=f"{accent} dim")

            thought_widget = None
            if thought_text:
                from rich.markup import escape
                th_word_count = len(thought_text.split())
                th_title = f"💭 Thought Process ({th_word_count} words)" if not self._streaming else "💭 Thinking…"
                th_border = accent if not is_light else (t.hex("accent") if t else accent)
                th_text_style = "dim italic" if not is_light else "italic #475569"
                th_lines = [tl for tl in thought_text.splitlines()]
                if self._streaming and "</think>" not in raw_text:
                    th_lines.append("… ▌")
                thought_content = Text("\n".join(th_lines), style=th_text_style)
                thought_widget = Panel(
                    thought_content,
                    title=f"[bold {th_border}]{escape(th_title)}[/]",
                    title_align="left",
                    border_style=th_border,
                    box=box.SQUARE,
                    expand=False,
                    padding=(0, 1),
                )

            activity_widget = None
            if act_items:
                act_border = accent if not is_light else (t.hex("accent") if t else accent)
                activity_widget = _build_activity_widget(act_items, is_light=is_light, accent=act_border)

            body = _highlight_chemistry(_render_math(clean_answer)) or ""
            if self._streaming and (not thought_text or "</think>" in raw_text) and clean_answer:
                body += " \u258c"  # trailing cursor glyph while tokens arrive

            md = None
            if body.strip():
                md = Markdown(body, code_theme=_code_theme_for_current_theme())
            elif not thought_widget and not activity_widget:
                md = Markdown("\u2026", code_theme=_code_theme_for_current_theme())

            parts = [header_row, divider]
            if thought_widget:
                parts.append(thought_widget)
                if activity_widget or md:
                    parts.append(Text(""))
            if activity_widget:
                parts.append(activity_widget)
                if md:
                    parts.append(Text(""))
            if md:
                parts.append(md)

            cards = self._attachment_cards()
            if cards is not None:
                parts.append(cards)
            telemetry = self._format_telemetry()
            if telemetry is not None:
                parts.append(telemetry)
            return Group(*parts)

        def _freeze_mode_style(self):
            snap = self._mode_snapshot or {"accent_hex": "#38bdf8", "icon": "📓", "label": "Notebook"}
            accent = snap.get("accent_hex") or "#38bdf8"
            hi, sh = _bevel_colors(accent)
            try:
                from .. import theme as _theme
                is_light = _theme.is_light()
                t = _theme.get_theme_obj()
            except Exception:
                is_light = False
                t = None

            try:
                if self.role == "user":
                    if is_light:
                        self.styles.background = "#ffffff"
                        self.styles.color = "#0f172a"
                        self.styles.border_top = ("tall", "#ffffff")
                        self.styles.border_left = ("tall", "#e2e8f0")
                        self.styles.border_right = ("tall", "#cbd5e1")
                        self.styles.border_bottom = ("tall", accent)
                    else:
                        rgb = None
                        try:
                            from .. import ai_modes
                            if hasattr(ai_modes, "accent_rgb"):
                                rgb = ai_modes.accent_rgb(snap.get("mode", "notebook"))
                        except Exception:
                            pass
                        if not rgb:
                            try:
                                from textual.color import Color
                                c = Color.parse(accent)
                                rgb = (int(c.r * 255), int(c.g * 255), int(c.b * 255))
                            except Exception:
                                rgb = (56, 189, 248)
                        bg_r = max(14, min(38, int(rgb[0] * 0.12 + 16 * 0.88)))
                        bg_g = max(14, min(38, int(rgb[1] * 0.12 + 18 * 0.88)))
                        bg_b = max(18, min(46, int(rgb[2] * 0.12 + 24 * 0.88)))
                        bg_hex = f"#{bg_r:02x}{bg_g:02x}{bg_b:02x}"
                        self.styles.background = bg_hex
                        self.styles.color = "#f8fafc"
                        self.styles.border_top = ("tall", hi)
                        self.styles.border_left = ("tall", hi)
                        self.styles.border_right = ("tall", sh)
                        self.styles.border_bottom = ("tall", sh)
                    self.styles.padding = (1, 2, 1, 2)
                elif self.role == "assistant":
                    if is_light:
                        self.styles.background = "#ffffff"
                        self.styles.color = "#0f172a"
                        self.styles.border_top = ("tall", "#ffffff")
                        self.styles.border_left = ("tall", "#cbd5e1")
                        self.styles.border_right = ("tall", "#94a3b8")
                        self.styles.border_bottom = ("tall", "#64748b")
                    else:
                        rgb = None
                        try:
                            from .. import ai_modes
                            if hasattr(ai_modes, "accent_rgb"):
                                rgb = ai_modes.accent_rgb(snap.get("mode", "notebook"))
                        except Exception:
                            pass
                        if not rgb:
                            try:
                                from textual.color import Color
                                c = Color.parse(accent)
                                rgb = (int(c.r * 255), int(c.g * 255), int(c.b * 255))
                            except Exception:
                                rgb = (56, 189, 248)
                        bg_r = max(13, min(32, int(rgb[0] * 0.08 + 16 * 0.92)))
                        bg_g = max(14, min(34, int(rgb[1] * 0.08 + 18 * 0.92)))
                        bg_b = max(19, min(42, int(rgb[2] * 0.08 + 24 * 0.92)))
                        bg_hex = f"#{bg_r:02x}{bg_g:02x}{bg_b:02x}"
                        self.styles.background = bg_hex
                        self.styles.color = "#f1f5f9"
                        self.styles.border_top = ("tall", hi)
                        self.styles.border_left = ("tall", hi)
                        self.styles.border_right = ("tall", sh)
                        self.styles.border_bottom = ("tall", sh)
                    self.styles.padding = (1, 2)
                elif self.role == "system":
                    self.styles.background = "#ffffff" if is_light else theme_css.current_hex("surface-alt")
                    self.styles.color = "#1b1f27" if is_light else theme_css.current_hex("text")
                    if is_light:
                        b_top = t.hex("accent") if t else "#005faf"
                        b_bot = t.hex("border") if t else "#8c959f"
                        self.styles.border_top = ("tall", b_top)
                        self.styles.border_left = ("tall", b_top)
                        self.styles.border_right = ("tall", b_bot)
                        self.styles.border_bottom = ("tall", b_bot)
                    else:
                        self.styles.border_top = ("tall", hi)
                        self.styles.border_left = ("tall", hi)
                        self.styles.border_right = ("tall", sh)
                        self.styles.border_bottom = ("tall", sh)
                    self.styles.padding = (0, 2)
            except Exception:
                pass

        def on_enter(self, event) -> None:
            try:
                from .. import theme as _theme
                is_light = _theme.is_light()
                t = _theme.get_theme_obj()
                snap = self._mode_snapshot or {}
                accent = snap.get("accent_hex") or "#38bdf8"
                hi, sh = _bevel_colors(accent)
                self.styles.offset = (0, 0)
                if self.role == "system":
                    if is_light:
                        glow = t.hex("accent_alt") if t else "#007acc"
                        self.styles.border_top = ("tall", glow)
                        self.styles.border_left = ("tall", glow)
                    else:
                        self.styles.border_top = ("tall", "#ffffff")
                        self.styles.border_left = ("tall", hi)
                elif self.role in ("user", "assistant"):
                    if is_light:
                        glow = t.hex("accent_alt") if t else "#007acc"
                        self.styles.border_top = ("tall", glow)
                        self.styles.border_left = ("tall", glow)
                        self.styles.border_right = ("tall", t.hex("border") if t else "#8c959f")
                        self.styles.border_bottom = ("tall", t.hex("accent") if t else "#005faf")
                    else:
                        self.styles.border_top = ("tall", "#ffffff")
                        self.styles.border_left = ("tall", hi)
                        self.styles.border_right = ("tall", sh)
                        self.styles.border_bottom = ("tall", accent)
            except Exception:
                pass

        def on_leave(self, event) -> None:
            try:
                self.styles.offset = (0, 0)
                self._freeze_mode_style()
            except Exception:
                pass

        def on_mount(self):
            self._freeze_mode_style()
            # 3D entrance bloom animation: smooth opacity fade + luminous accent tint pulse
            # Skip animation while streaming to prevent flickering / rendering clash with incoming chunks
            if self.role not in ("user", "assistant") or self._streaming:
                return
            try:
                from textual.color import Color
                snap = self._mode_snapshot or {}
                accent = snap.get("accent_hex") or "#38bdf8"
                self.styles.opacity = 0.0
                self.styles.tint = Color.parse(accent).with_alpha(0.40)
                self.styles.animate("opacity", value=1.0, duration=0.35, easing="out_cubic")
                self.styles.animate("tint", value=Color(0, 0, 0, 0.0), duration=0.45, easing="out_cubic")
            except Exception:
                pass

        # Gesture tracking for chat double-click → edit
        _last_chat_click = 0
        _last_chat_turn = None

        # --------------------------------------------- context menu --
        def on_click(self, event):
            """Right-click opens context menu; double-click triggers
            gesture (spec 23: gesture on chat → edit)."""
            # --- Gesture: double-click chat → edit message ---
            import time as _t
            try:
                if getattr(event, "button", 1) == 1 and self.role in ("user", "assistant"):
                    now = _t.time()
                    if now - ConversationItem._last_chat_click < 0.35 and ConversationItem._last_chat_turn == self.turn_id:
                        ConversationItem._last_chat_click = 0
                        ConversationItem._last_chat_turn = None
                        try:
                            from ..gestures.manager import handle_gesture
                            if handle_gesture("double_click", "chat", app=getattr(self, "app", None), context={"turn_id": self.turn_id}):
                                event.stop()
                                return
                        except Exception:
                            pass
                        # Fallback: direct edit trigger
                        try:
                            from .events import MessageContextAction
                            self.post_message(MessageContextAction("rewrite", self.turn_id))
                            event.stop()
                            return
                        except Exception:
                            pass
                    else:
                        ConversationItem._last_chat_click = now
                        ConversationItem._last_chat_turn = self.turn_id
            except Exception:
                pass
            if getattr(event, "button", None) != 3:
                return
            if self.role not in ("user", "assistant"):
                return
            event.stop()
            from . import context_menu
            if context_menu.MessageContextMenu is None:
                return
            items = (context_menu.AI_MENU_ITEMS if self.role == "assistant"
                     else context_menu.USER_MENU_ITEMS)
            origin = self._click_screen_offset(event)
            self.app.push_screen(
                context_menu.MessageContextMenu(items, origin=origin),
                self._on_context_menu_result,
            )

        def _click_screen_offset(self, event):
            """Best-effort screen-cell coordinate for the click, so the
            context menu can open beside the cursor. Tries the
            coordinate attributes newer Textual versions expose
            directly first, then falls back to this widget's own
            on-screen region plus the event's widget-relative offset —
            works even if a given Textual version doesn't expose
            screen_x/screen_y under those exact names. Not runtime-
            verified in this environment (no network access to install
            textual and click a real terminal)."""
            sx = getattr(event, "screen_x", None)
            sy = getattr(event, "screen_y", None)
            if sx is not None and sy is not None:
                return (sx, sy)
            offset = getattr(event, "screen_offset", None)
            if offset is not None:
                return (offset.x, offset.y)
            try:
                region = self.region
                return (region.x + event.x, region.y + event.y)
            except Exception:
                return (0, 0)

        def _on_context_menu_result(self, action):
            if not action:
                return
            if action == "copy":
                self._copy_text()
                return
            from .events import MessageContextAction
            self.post_message(MessageContextAction(action, self.turn_id))

        def _copy_text(self, skip_flash: bool = False):
            """Copy Text (both menus): real clipboard write via the same
            code_editor.copy_to_clipboard used by /copycode and the code
            pad's :copy — not a placeholder."""
            from .. import code_editor
            rendered = _render_math(self._text) if self.role == "assistant" else self._text
            if self.role == "assistant":
                try:
                    from ..agent import strip_tool_markup
                    rendered = strip_tool_markup(rendered)
                except Exception:
                    pass
            ok, detail = code_editor.copy_to_clipboard(rendered)
            if not skip_flash:
                self._flash_copy_status(ok)

        def _flash_copy_status(self, ok):
            label = "\u2713 Copied" if ok else "\u2717 Copy failed"
            color = "green" if ok else "red"
            banner = Text(label, style=f"{color} bold")
            self.update(Group(self._build_content(), banner))
            try:
                self.styles.animate("opacity", value=0.55, duration=0.08, easing="out_cubic")
                self.set_timer(0.08, lambda: self.styles.animate(
                    "opacity", value=1.0, duration=0.15, easing="out_cubic"))
            except Exception:
                pass
            self.set_timer(1.2, lambda: self.update(self._build_content()))

        def append_chunk(self, fragment):
            self._text += fragment
            now = time.monotonic()
            last = getattr(self, "_last_chunk_update", 0.0)
            if now - last >= 0.065:  # ~15 FPS max update rate while streaming for smooth UI thread responsiveness
                self._last_chunk_update = now
                self.update(self._build_content())
            else:
                if not getattr(self, "_pending_chunk_timer", False):
                    self._pending_chunk_timer = True
                    def _delayed_update():
                        self._pending_chunk_timer = False
                        self._last_chunk_update = time.monotonic()
                        self.update(self._build_content())
                    self.set_timer(0.065, _delayed_update)

        def set_text(self, text, attachments=None):
            """Rewrite (minor-bug-fix spec): updates THIS bubble's own
            text in place — used for the edited USER turn (the prompt
            itself, replaced with what the user typed) rather than
            removing this widget and mounting a new one elsewhere in
            the conversation. v0.7.6 Patch 1: also accepts the edited
            turn's attachments (Fix 6) so the bubble's cards follow
            the edit."""
            self._text = text
            if attachments is not None:
                self._attachments = list(attachments)
            self._timestamp = time.time()
            self.update(self._build_content())

        def reset_for_regenerate(self, mode_snapshot=None):
            """Try Again / Rewrite regeneration (minor-bug-fix spec):
            resets this already-mounted ASSISTANT bubble back to an
            empty streaming state in place, so the upcoming
            MessageChunk/MessageFinished events for this same turn_id
            repaint the existing bubble instead of a brand-new one
            being mounted — which was the literal duplicate-message
            bug being fixed. `mode_snapshot`, when given, replaces the
            frozen mode coloring (e.g. 'Try Again in Build Mode'
            switches modes first) — see the module docstring on why
            mode coloring is always read from a frozen snapshot, never
            live from ai_modes.current_mode()."""
            self._text = ""
            self._streaming = True
            self._meta_lines = []
            self._show_timestamp = False
            if mode_snapshot is not None:
                self._mode_snapshot = mode_snapshot
            self.update(self._build_content())

        def finalize(self, full_text=None, meta_lines=None, contributions=None):
            if full_text is not None:
                self._text = full_text
            if meta_lines is not None:
                self._meta_lines = meta_lines
            if contributions is not None:
                self._contributions = contributions
            self._streaming = False
            self._timestamp = time.time()
            if self.role == "assistant":
                # v0.7.2 roadmap "Error highlighting": surfaced once the
                # reply is complete (not per-chunk while streaming,
                # since a \frac{ opened in one chunk is routinely still
                # unclosed until a later chunk arrives — that's not an
                # error, just mid-stream) rather than on every partial
                # chunk, which would flash false positives constantly.
                latex_errors = find_latex_errors(self._text)
                if latex_errors:
                    self._meta_lines = list(self._meta_lines) + [
                        f"[dim yellow]\u26a0 LaTeX: {'; '.join(latex_errors)}[/]"]
            self.update(self._build_content())
            if self.role == "assistant":
                _remember_code_blocks(self._text)
                self._freeze_mode_style()
                try:
                    from textual.color import Color
                    snap = self._mode_snapshot or {}
                    accent = snap.get("accent_hex") or "#38bdf8"
                    # Completion shimmer pulse: brilliant accent glow that smoothly settles
                    self.styles.tint = Color.parse(accent).with_alpha(0.38)
                    self.styles.animate("tint", value=Color(0, 0, 0, 0.0), duration=0.50, easing="out_cubic")
                except Exception:
                    pass
                try:
                    curr = self.parent
                    while curr is not None and not hasattr(curr, "hide_agent_activity"):
                        curr = getattr(curr, "parent", None)
                    if curr is not None and hasattr(curr, "hide_agent_activity"):
                        curr.hide_agent_activity()
                except Exception:
                    pass

        # --------------------------------------------- theme switching --
        def retheme(self):
            """v0.7.9.0 light-mode audit: re-render this bubble with the
            CURRENT theme's Markdown code theme (material ↔ friendly).
            Called by ConversationView.retheme_items() after /theme —
            without it, old assistant bubbles kept dark code-fence
            backgrounds in light mode ('components styled with the
            previous theme' glitch)."""
            self._freeze_mode_style()
            self.update(self._build_content())

    class MessageRow(Horizontal):
        """Full-width flow container for a message card with bubble and useful action buttons."""

        DEFAULT_CSS = """
        MessageRow {
            width: 100%;
            height: auto;
        }
        MessageRow .cct-msg-card {
            width: auto;
            min-width: 50;
            max-width: 96%;
            height: auto;
        }
        MessageRow .cct-msg-actions {
            height: 1;
            min-height: 1;
            max-height: 1;
            width: auto;
            margin-top: 0;
            padding: 0;
        }
        MessageRow .cct-msg-btn {
            height: 1;
            min-height: 1;
            max-height: 1;
            width: 11;
            min-width: 11;
            max-width: 11;
        }
        """

        def __init__(self, bubble, role, id=None):
            super().__init__(id=id, classes=f"cct-row cct-row-{role}")
            self._bubble = bubble
            self.role = role

        def compose(self):
            with Vertical(classes=f"cct-msg-card cct-msg-card-{self.role}"):
                yield self._bubble
                if self.role in ("user", "assistant"):
                    with Horizontal(classes="cct-msg-actions"):
                        yield Button("\U0001f4cb Copy", classes="cct-msg-btn", id=f"msg-copy-{self._bubble.turn_id}", tooltip="Copy message text")
                        if self.role == "user":
                            yield Button("\u270f Edit", classes="cct-msg-btn", id=f"msg-edit-{self._bubble.turn_id}", tooltip="Edit prompt in composer")
                        elif self.role == "assistant":
                            yield Button("\U0001f504 Retry", classes="cct-msg-btn", id=f"msg-retry-{self._bubble.turn_id}", tooltip="Regenerate turn")

        def on_button_pressed(self, event):
            bid = getattr(event.button, "id", "") or ""
            if bid.startswith("msg-copy-"):
                event.stop()
                btn = event.button
                try:
                    btn.label = "\u2713 Copied"
                    def _restore():
                        try:
                            btn.label = "\U0001f4cb Copy"
                        except Exception:
                            pass
                    btn.set_timer(1.2, _restore)
                except Exception:
                    pass
                if hasattr(self._bubble, "_copy_text"):
                    self._bubble._copy_text(skip_flash=True)
            elif bid.startswith("msg-edit-"):
                event.stop()
                from .events import MessageContextAction
                self.post_message(MessageContextAction("rewrite", self._bubble.turn_id))
            elif bid.startswith("msg-retry-"):
                event.stop()
                from .events import MessageContextAction
                snap = getattr(self._bubble, "_mode_snapshot", None) or {}
                mode = snap.get("mode", "notebook") if isinstance(snap, dict) else "notebook"
                self.post_message(MessageContextAction(f"retry:{mode}", self._bubble.turn_id))

    class ConversationView(VerticalScroll):
        """The ONLY scrollable region in the primary UI. Mounts once per
        session and only ever appends — never re-renders the whole list.
        Streaming mutates the one active ConversationItem in place
        (`append_chunk`), not the view around it."""

        def __init__(self, id="cct-conversation"):
            super().__init__(id=id)
            self._items = {}  # turn_id -> ConversationItem (the bubble, not its row)
            self._welcome = None
            # v0.7.9.6: the welcome SLOT is one widget at a time, so
            # `_welcome` is the live one and `_dashboard` is a typed alias
            # that is non-None only while a WelcomeDashboard occupies the
            # slot. Kept in sync by show_dashboard()/hide_welcome() so
            # CCTApp._cascade_resize can ask "is the dashboard the thing
            # that needs a re-fit?" without reaching into the slot blindly
            # (the previous app-side `getattr(conv, "_dashboard", None)`
            # check could never be true — the attribute did not exist,
            # so the dashboard branch was dead code).
            self._dashboard = None
            # v0.7.9.0: the CAT Agent ASCII activity indicator — a pure
            # UI-state widget driven by real backend state (AgentActivity
            # / MessageStarted / MessageFinished), never model output.
            self._agent_indicator = None
            # v0.7.9 Live Activities: per-turn inline blocks (USER TASK -> LIVE -> RESPONSE)
            self._live_blocks: dict[str, object] = {}
            self._live_container = None

        def on_click(self, event) -> None:
            # Clicking empty chat area or conversation view focuses composer input
            # unless clicking an interactive control like a button or scrollbar
            target = getattr(event, "widget", None)
            if target is not None:
                from textual.widgets import Button
                try:
                    from textual.scrollbar import ScrollBar, ScrollBarCorner
                    scrollbar_types = (ScrollBar, ScrollBarCorner)
                except Exception:
                    scrollbar_types = ()
                targets = [target] + list(getattr(target, "ancestors", []))
                for t in targets:
                    if isinstance(t, Button) or (scrollbar_types and isinstance(t, scrollbar_types)):
                        return
                    t_name = type(t).__name__.lower()
                    if "scrollbar" in t_name or "scroll" in t_name:
                        return
            try:
                from .composer import ComposerInput
                self.app.query_one("#cct-input", ComposerInput).focus()
            except Exception:
                pass

        def on_key(self, event) -> None:
            # Let navigation/scrolling keys scroll the conversation view normally
            key = getattr(event, "key", "") or ""
            char = getattr(event, "character", None)
            if key in ("up", "down", "left", "right", "pageup", "pagedown", "home", "end", "tab", "escape", "ctrl+c"):
                return
            # Printable character, slash command, or backspace: route immediately to composer input!
            if char or (len(key) == 1 and key.isprintable()) or key in ("slash", "backspace"):
                try:
                    from .composer import ComposerInput
                    editor = self.app.query_one("#cct-input", ComposerInput)
                    editor.focus()
                    if key == "backspace":
                        editor.action_delete_left()
                    else:
                        to_insert = char if char else ("/" if key == "slash" else key)
                        editor.insert(to_insert)
                    event.stop()
                    try:
                        event.prevent_default()
                    except Exception:
                        pass
                except Exception:
                    pass

        def show_welcome(self, logo_lines, tip_text):
            self._welcome = WelcomeBanner(logo_lines, tip_text)
            self.mount(self._welcome)

        def hide_welcome(self):
            if self._welcome is not None:
                self._welcome.remove()
                self._welcome = None
            self._dashboard = None

        def show_dashboard(self, dashboard_widget):
            """spec v0.7 Welcome Dashboard: mounted the same way
            WelcomeBanner is (first item in this view, removed the
            moment a real turn or workspace is opened) — a distinct
            widget rather than growing WelcomeBanner itself, so the
            plain pre-v0.7 banner keeps working unmodified for anything
            that doesn't opt into the richer dashboard."""
            self.hide_welcome()
            self._welcome = dashboard_widget
            self.mount(self._welcome)
            # v0.7.9.6: the welcome slot is duck-typed (plain WelcomeBanner,
            # CATChatEmptyState, or the richer WelcomeDashboard all land
            # here). Track the dashboard specifically so callers that need
            # its resize/stats contract can ask a real question instead of
            # feature-sniffing the slot.
            from . import dashboard as _dashboard_mod
            self._dashboard = (
                dashboard_widget
                if _dashboard_mod.WelcomeDashboard is not None
                and isinstance(dashboard_widget, _dashboard_mod.WelcomeDashboard)
                else None)

        def show_empty_state(self, empty_state_widget):
            """v0.7.9.0: the CATChatEmptyState startup centerpiece mounts
            through the SAME welcome slot as the dashboard — first item
            in this view while there are no turns, removed by the one
            hide_welcome() chokepoint before any real message appears.
            It is pure UI state: never a session turn, never a prompt,
            never copyable 'assistant' content."""
            self.show_dashboard(empty_state_widget)

        def update_empty_state_mode(self, mode_key):
            """Forward the ACTUAL current mode to the visible empty state
            (its ready line names the real persona). No-op when chat has
            started or a different welcome widget is shown."""
            if self._welcome is not None and hasattr(self._welcome, "set_mode"):
                try:
                    self._welcome.set_mode(mode_key)
                except Exception:
                    pass

        def repaint_empty_state_theme(self):
            """After a /theme switch: re-read theme colors in place."""
            if self._welcome is not None and hasattr(
                    self._welcome, "repaint_theme"):
                try:
                    self._welcome.repaint_theme()
                except Exception:
                    pass

        def hide_dashboard(self):
            self.hide_welcome()

        def refresh_dashboard_stats(self):
            """v0.7.2 roadmap Project & Workspace Dashboard: called from
            ui/app.py's UI-thread event handlers (on_message_finished,
            on_file_saved, _open_folder) after something that could
            change the numbers. No-op unless the currently-shown
            welcome widget is actually a WelcomeDashboard with stats to
            refresh (e.g. still the plain WelcomeBanner, or no
            workspace open) — checked via duck-typing (hasattr) rather
            than importing WelcomeDashboard here, since this module
            has no other reason to depend on ui/dashboard.py at all."""
            if self._welcome is not None and hasattr(self._welcome, "refresh_stats"):
                self._welcome.refresh_stats()

        def retheme_items(self):
            """v0.7.9.0 light-mode audit: after a /theme switch every
            existing bubble re-renders so Markdown code fences pick the
            current theme's pygments style (material ↔ friendly) — no
            bubble is left wearing the previous theme."""
            for item in list(self._items.values()):
                try:
                    item.retheme()
                except Exception:
                    pass
            try:
                for item in self.query(ConversationItem):
                    try:
                        item.retheme()
                    except Exception:
                        pass
            except Exception:
                pass
            # v0.7.9 Live Activities: re-render activity rows so status colors follow theme
            for blk in list(getattr(self, "_live_blocks", {}).values()):
                try:
                    blk.retheme()
                except Exception:
                    pass

        def _mount_row(self, item):
            row = MessageRow(item, item.role, id=f"row-{item.turn_id}")
            self.mount(row)
            return row

        def add_complete(self, turn_id, role, text, mode_snapshot=None, attachments=None):
            item = ConversationItem(turn_id, role, text, mode_snapshot=mode_snapshot,
                                    attachments=attachments)
            self._items[turn_id] = item
            self._mount_row(item)
            self.scroll_end(animate=True, duration=0.2)
            return item

        def start_streaming(self, turn_id, role="assistant", mode_snapshot=None):
            item = ConversationItem(turn_id, role, "", streaming=True, show_timestamp=False,
                                     mode_snapshot=mode_snapshot)
            self._items[turn_id] = item
            row = self._mount_row(item)
            # Prevent empty bordered box while waiting for first token or during tool execution
            if role == "assistant":
                try:
                    row.display = False
                except Exception:
                    pass
            self.scroll_end(animate=False)
            return item

        def append_chunk(self, turn_id, fragment):
            item = self._items.get(turn_id)
            if item is None:
                return
            try:
                row = self.query_one(f"#row-{turn_id}", MessageRow)
                if not row.display:
                    row.display = True
            except Exception:
                pass
            item.append_chunk(fragment)
            # Throttled scroll_end for buttery smooth streaming without micro-stutter
            now = time.time()
            last_t = getattr(self, "_last_stream_scroll", 0.0)
            if "\n" in fragment or (now - last_t >= 0.1):
                self._last_stream_scroll = now
                try:
                    max_y = getattr(self, "max_scroll_y", 0)
                    cur_y = getattr(self, "scroll_y", 0)
                    if max_y - cur_y <= 4:
                        self.scroll_end(animate=False)
                except Exception:
                    self.scroll_end(animate=False)

        def mount_live_activities(self, turn_id: str, title: str = "LIVE ACTIVITIES"):
            """Mount (or reuse) the LiveActivitiesBlock for turn_id.
            Called from CCTApp.on_message_started *before* the assistant bubble
            is mounted so the order is USER -> LIVE -> ASSISTANT.
            For regeneration, reuse existing block and clear its history."""
            try:
                from .live_activities import LiveActivitiesBlock
            except Exception:
                return None
            if LiveActivitiesBlock is None:
                return None
            existing = self._live_blocks.get(turn_id)
            if existing is not None and getattr(existing, "is_mounted", False):
                try:
                    existing.clear()  # regeneration: start fresh
                except Exception:
                    pass
                return existing
            # create new block
            try:
                block = LiveActivitiesBlock(turn_id=turn_id, title=title)
            except Exception:
                return None
            self._live_blocks[turn_id] = block
            # Mount position: if assistant row for this turn already exists (regeneration),
            # we want live block immediately BEFORE it. Otherwise mount at end
            # (which will be between user row and the soon-to-be-mounted assistant row
            # when called before start_streaming).
            try:
                if turn_id in self._items:
                    # regeneration: assistant row exists, find its index
                    # mount then move: use mount + reordering via children index if available
                    self.mount(block)
                    # try to move live block before the assistant row
                    try:
                        row_id = f"row-{turn_id}"
                        children = list(self.children)
                        # locate indices
                        live_idx = next((i for i, c in enumerate(children) if c is block), None)
                        row_idx = next((i for i, c in enumerate(children) if getattr(c, "id", "") == row_id), None)
                        if live_idx is not None and row_idx is not None and live_idx > row_idx:
                            # Textual 0.44+ has move_child; fallback to remove+mount with before
                            if hasattr(self, "move_child"):
                                self.move_child(block, before=row_idx)
                            else:
                                # fallback: remove and re-mount at position via mount before?
                                block.remove()
                                # mounting again will put at end; need to reorder manually via composition?
                                # simplest: keep as is for fallback (after) — rare path, non-critical
                                self.mount(block)
                    except Exception:
                        pass
                else:
                    self.mount(block)
                self.scroll_end(animate=False)
            except Exception:
                try:
                    self.mount(block)
                except Exception:
                    pass
            return block

        def get_live_block(self, turn_id: str):
            return self._live_blocks.get(turn_id)

        def mark_live_completed(self, turn_id: str):
            blk = self._live_blocks.get(turn_id)
            if blk is not None:
                try:
                    blk.mark_completed()
                except Exception:
                    pass

        def collapse_live(self, turn_id: str):
            blk = self._live_blocks.get(turn_id)
            if blk is not None:
                try:
                    blk._apply_collapsed(True)
                except Exception:
                    pass

        def expand_live(self, turn_id: str):
            blk = self._live_blocks.get(turn_id)
            if blk is not None:
                try:
                    blk._apply_collapsed(False)
                except Exception:
                    pass

        def finish(self, turn_id, full_text=None, meta_lines=None, contributions=None):
            self.hide_agent_activity()
            # mark live block completed (keeps history but allows collapse)
            try:
                self.mark_live_completed(turn_id)
            except Exception:
                pass
            item = self._items.get(turn_id)
            if item is None:
                return
            try:
                row = self.query_one(f"#row-{turn_id}", MessageRow)
                row.display = True
            except Exception:
                pass
            item.finalize(full_text, meta_lines=meta_lines, contributions=contributions)
            self.scroll_end(animate=False)

        # ------------------------------------------- agent activity (UI) --
        def show_agent_activity(self, state="thinking", mode_key=None):
            """Mounts (or re-targets) the CAT Agent ASCII indicator below
            the newest assistant activity. Pure UI: it renders no model
            text and is removed again by finish()/hide_agent_activity().
            Safe to call repeatedly for one turn — the widget is reused,
            only its state line changes.

            v0.7.9.0: `mode_key` (the ACTUAL current AI mode) drives the
            indicator's identity label (CAT Notebook / CAT Build / ...)."""
            indicator = self._agent_indicator
            already_here = (
                indicator is not None and indicator.is_mounted
                and getattr(indicator, "parent", None) is self)
            if self._agent_indicator is None:
                from .cat_agent import CATAgentIndicator
                indicator = CATAgentIndicator(mode_key=mode_key)
                self._agent_indicator = indicator
                try:
                    self.mount(indicator)
                    already_here = True
                except Exception:
                    self._agent_indicator = None
                    return
            elif not already_here:
                try:
                    self.mount(indicator)
                except Exception:
                    pass
            if mode_key:
                try:
                    indicator.set_mode(mode_key)
                except Exception:
                    pass
            try:
                indicator.set_state(state)
            except Exception:
                pass
            self.scroll_end(animate=False)

        def update_agent_activity(self, state):
            """State flip while the same turn keeps running (tool started /
            permission resolved / back to thinking). No-op when the
            indicator isn't shown."""
            if self._agent_indicator is None:
                return
            try:
                self._agent_indicator.set_state(state)
            except Exception:
                pass

        def hide_agent_activity(self):
            """Stops + removes the indicator. Called on MessageFinished —
            which every exit path (success/error/cancel) crosses — so the
            animation can never outlive real work."""
            indicator = self._agent_indicator
            self._agent_indicator = None
            if indicator is None:
                return
            try:
                indicator.stop()
            except Exception:
                pass
            try:
                indicator.remove()
            except Exception:
                pass

        def mount_item(self, widget):
            """Escape hatch for widgets this view doesn't own the class
            of (e.g. a PermissionCard built by permission_panel.py) but
            that still belong in the conversation stream, per the
            redesign brief ('permission requests become part of
            conversation history'). This view still owns placement and
            scrolling; it just doesn't own that widget's rendering, and
            doesn't wrap it in a MessageRow — it's already a full card,
            not a bubble."""
            self.mount(widget)
            self.scroll_end(animate=False)

        def remove_from(self, turn_id):
            """Revert (v0.7.2 spec): removes the row for `turn_id` and
            every widget mounted after it — including non-turn cards
            like PermissionCard (see mount_item's docstring), which
            don't have a turn id of their own. Safe because this view
            only ever appends in chronological order (module
            docstring), so index position in `self.children` already
            matches conversation order without needing per-widget
            timestamps. No-op if `turn_id` isn't currently mounted
            (e.g. it was already removed, or belongs to scrollback
            that was never re-mounted)."""
            target_id = f"row-{turn_id}"
            children = list(self.children)
            idx = next((i for i, c in enumerate(children) if c.id == target_id), None)
            if idx is not None:
                removed_ids = {c.id for c in children[idx:]}
                for child in children[idx:]:
                    child.remove()
                self._items = {tid: item for tid, item in self._items.items()
                                if f"row-{tid}" not in removed_ids}
                # also remove live blocks for reverted turns
                for tid in list(self._live_blocks.keys()):
                    if f"live-{tid}" in removed_ids or f"row-{tid}" in removed_ids:
                        self._live_blocks.pop(tid, None)
                # also remove any live blocks that were mounted after idx (their ids start with live-)
                for child in children[idx:]:
                    cid = getattr(child, "id", "") or ""
                    if cid.startswith("live-"):
                        tid = cid[len("live-"):]
                        self._live_blocks.pop(tid, None)
                return
            # fallback: if no row found, try live block directly (for system reverts)
            live_id = f"live-{turn_id}"
            idx2 = next((i for i, c in enumerate(children) if getattr(c, "id", "") == live_id), None)
            if idx2 is not None:
                for child in children[idx2:]:
                    child.remove()
                self._live_blocks.pop(turn_id, None)
                # clean items that were after it
                remaining = set(c.id for c in self.children if hasattr(c, "id"))
                self._items = {tid: item for tid, item in self._items.items()
                                if f"row-{tid}" in remaining}

        def has_item(self, turn_id):
            """Whether `turn_id` already has a mounted bubble. The one
            place this matters: on_message_started (ui/app.py) uses it
            to decide between mounting a brand-new bubble (normal
            flow) and reusing/resetting the existing one in place (Try
            Again / Rewrite regeneration — see reset_for_regenerate),
            which is the actual fix for the duplicate-message bug."""
            return turn_id in self._items

        def get_item(self, turn_id):
            """Return the ConversationItem for turn_id if mounted, else None."""
            return self._items.get(turn_id)

        def set_text(self, turn_id, text, attachments=None):
            """Rewrite (minor-bug-fix spec): updates the USER bubble's
            own text in place after an edit — see
            ConversationItem.set_text. No-op if `turn_id` isn't
            currently mounted."""
            item = self._items.get(turn_id)
            if item is None:
                return
            item.set_text(text, attachments=attachments)

        def reset_for_regenerate(self, turn_id, mode_snapshot=None):
            """Try Again / Rewrite regeneration (minor-bug-fix spec):
            resets an existing ASSISTANT bubble to a fresh streaming
            state in place — see ConversationItem.reset_for_regenerate.
            Returns the item, or None if `turn_id` isn't currently
            mounted (caller should fall back to appending a normal new
            turn rather than silently doing nothing)."""
            item = self._items.get(turn_id)
            if item is None:
                return None
            item.reset_for_regenerate(mode_snapshot)
            self.scroll_end(animate=False)
            return item

        def clear(self):
            self._items = {}
            self._welcome = None
            self._agent_indicator = None
            self._live_blocks = {}
            for child in list(self.children):
                child.remove()
            # v0.7.9 Live Activities: clear stored activities for this session's turns
            try:
                from .. import activity as _act
                # only clear current session's turns — for now clear all to bound memory,
                # since each clear is a session boundary
                _act.manager.clear_all()
            except Exception:
                pass

else:
    ConversationItem = None
    ConversationView = None
    MessageRow = None
    WelcomeBanner = None
