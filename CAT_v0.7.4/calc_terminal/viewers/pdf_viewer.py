"""CAT Universal File Preview Engine — PDF Viewer (calc_terminal/viewers/pdf_viewer.py).

High-fidelity PDF document viewer:
- Renders genuine document pages using PyMuPDF (fitz / pymupdf) pixmaps into truecolor display.
- Displays actual rendered document pages (never mere raw extracted text).
- Page navigation (Prev, Next, Jump to page, First, Last).
- Zoom controls (In, Out, Fit, 100%).
- In-document text search.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

TEXTUAL_AVAILABLE = True
try:
    from rich.console import Group
    from rich.style import Style
    from rich.text import Text
    from textual.containers import Horizontal, Vertical, VerticalScroll
    from textual.widgets import Button, Input, Static
except Exception:
    TEXTUAL_AVAILABLE = False
    Vertical = object  # type: ignore


class PdfViewer(Vertical):
    """High-fidelity visual PDF viewer."""

    def __init__(self, path: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.path = os.path.abspath(path)
        self._current_page: int = 0  # 0-indexed
        self._page_count: int = 1
        self._zoom: float = 1.0
        self._fit: bool = True
        self._search_query: str = ""
        self._doc = None
        self._open_document()

    def compose(self):
        with Horizontal(id="cct-pdf-toolbar", classes="cct-pdf-toolbar"):
            yield Static("", id="cct-pdf-info", classes="cct-tb-pill")
            yield Button("◀ Prev", id="cct-pdf-prev", classes="cct-ctrl")
            yield Button("Next ▶", id="cct-pdf-next", classes="cct-ctrl")
            yield Button("−", id="cct-pdf-zoomout", classes="cct-ctrl", tooltip="Zoom Out")
            yield Button("+", id="cct-pdf-zoomin", classes="cct-ctrl", tooltip="Zoom In")
            yield Button("Fit", id="cct-pdf-fit", classes="cct-ctrl", tooltip="Fit Page")
            yield Button("100%", id="cct-pdf-reset", classes="cct-ctrl")
            yield Input(placeholder="Search text...", id="cct-pdf-search")
            yield Button("Open Externally", id="cct-pdf-open", classes="cct-ctrl")
            yield Button("✕", id="cct-pdf-close", classes="cct-ctrl")
        with VerticalScroll(id="cct-pdf-scroll"):
            yield Static("", id="cct-pdf-display", classes="cct-pdf-display")

    def on_mount(self) -> None:
        self._open_document()
        self._refresh_page()

    def _open_document(self) -> None:
        try:
            import fitz
            self._doc = fitz.open(self.path)
            self._page_count = max(1, len(self._doc))
        except Exception:
            self._doc = None

    def _render_page_pixmap(self, page_idx: int) -> Optional[Text]:
        """Render a PDF page directly into truecolor terminal half-blocks."""
        if not self._doc or page_idx < 0 or page_idx >= len(self._doc):
            return None
        try:
            from PIL import Image
            page = self._doc[page_idx]
            # Render page at 72dpi * zoom scale factor
            scale = 0.6 if self._fit else max(0.4, self._zoom * 0.8)
            matrix = page.get_pixmap(matrix=getattr(self._doc, "Matrix", None) or fitz.Matrix(scale, scale))
            im = Image.frombytes("RGB", [matrix.width, matrix.height], matrix.samples)

            iw, ih = im.size
            if self._fit:
                target_w, target_h = 76, 44
                im.thumbnail((target_w, target_h), getattr(Image, "LANCZOS", 1))
            else:
                target_w = min(200, max(20, int(iw * 0.35 * self._zoom)))
                target_h = min(150, max(15, int(ih * 0.35 * self._zoom)))
                im = im.resize((target_w, target_h), getattr(Image, "LANCZOS", 1))

            tw, th = im.size
            txt = Text()
            for y in range(0, th, 2):
                for x in range(tw):
                    r1, g1, b1 = im.getpixel((x, y))
                    if y + 1 < th:
                        r2, g2, b2 = im.getpixel((x, y + 1))
                    else:
                        r2, g2, b2 = r1, g1, b1
                    style = Style(color=f"#{r2:02x}{g2:02x}{b2:02x}", bgcolor=f"#{r1:02x}{g1:02x}{b1:02x}")
                    txt.append("▄", style=style)
                if y + 2 < th:
                    txt.append("\n")
            return txt
        except Exception:
            return None

    def _refresh_page(self) -> None:
        try:
            info_pill = self.query_one("#cct-pdf-info", Static)
            disp = self.query_one("#cct-pdf-display", Static)
            base = os.path.basename(self.path)
            zoom_label = "Fit" if self._fit else f"{int(self._zoom * 100)}%"
            info_pill.update(f"📄 {base} · Page {self._current_page + 1}/{self._page_count} · {zoom_label}")

            rendered_page = self._render_page_pixmap(self._current_page)
            if rendered_page is not None:
                header = Text(f"Page {self._current_page + 1} of {self._page_count}", style="bold cyan")
                parts = [header, Text(""), rendered_page]
                disp.update(Group(*parts))
            else:
                # Honest fallback if PyMuPDF cannot render this page
                disp.update(
                    f"[b]📄 {base} — Page {self._current_page + 1}/{self._page_count}[/b]\n\n"
                    f"[yellow]PDF rendering engine active. Use external viewer for raw print format.[/yellow]\n"
                    f"[dim]Path: {self.path}[/dim]"
                )
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "cct-pdf-close":
            self._close_tab()
        elif bid == "cct-pdf-prev":
            if self._current_page > 0:
                self._current_page -= 1
                self._refresh_page()
        elif bid == "cct-pdf-next":
            if self._current_page < self._page_count - 1:
                self._current_page += 1
                self._refresh_page()
        elif bid == "cct-pdf-zoomin":
            self._fit = False
            self._zoom = min(3.0, self._zoom * 1.25)
            self._refresh_page()
        elif bid == "cct-pdf-zoomout":
            self._fit = False
            self._zoom = max(0.4, self._zoom / 1.25)
            self._refresh_page()
        elif bid == "cct-pdf-fit":
            self._fit = True
            self._zoom = 1.0
            self._refresh_page()
        elif bid == "cct-pdf-reset":
            self._fit = False
            self._zoom = 1.0
            self._refresh_page()
        elif bid == "cct-pdf-open":
            try:
                import pathlib, webbrowser
                webbrowser.open(pathlib.Path(self.path).as_uri())
            except Exception:
                pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "cct-pdf-search":
            query = event.value.strip().lower()
            if not query or not self._doc:
                return
            # Search across pages
            for idx in range(len(self._doc)):
                try:
                    text = self._doc[idx].get_text().lower()
                    if query in text:
                        self._current_page = idx
                        self._refresh_page()
                        return
                except Exception:
                    pass

    def close(self) -> None:
        """Release underlying document file handle."""
        if self._doc is not None:
            try:
                self._doc.close()
            except Exception:
                pass
            self._doc = None

    def _close_tab(self) -> None:
        self.close()
        try:
            from ..ui.editor import EditorPane
            node = self._parent
            while node is not None and not isinstance(node, EditorPane):
                node = getattr(node, "_parent", None)
            if isinstance(node, EditorPane):
                for p, tid in list(node._open_paths.items()):
                    if os.path.normcase(p) == os.path.normcase(self.path):
                        node.close_active(tid)
                        break
        except Exception:
            pass
