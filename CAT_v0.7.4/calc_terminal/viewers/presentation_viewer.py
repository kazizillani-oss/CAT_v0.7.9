"""CAT Universal File Preview Engine — PPTX Presentation Viewer (calc_terminal/viewers/presentation_viewer.py).

High-fidelity visual PPTX slide viewer:
- Renders visual presentation slide cards (titles, bullet points, layout cards).
- Parses PresentationML (ppt/slides/slide*.xml) natively via stdlib zipfile and xml.etree.ElementTree.
- Supports slide-by-slide slideshow navigation (Prev, Next, Jump).
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
import zipfile
from typing import List, Optional

TEXTUAL_AVAILABLE = True
try:
    from rich.console import Group
    from rich.panel import Panel
    from rich.text import Text
    from textual.containers import Horizontal, Vertical, VerticalScroll
    from textual.widgets import Button, Static
except Exception:
    TEXTUAL_AVAILABLE = False
    Vertical = object  # type: ignore

P_NS = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
A_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


class PresentationViewer(Vertical):
    """Visual PPTX slide viewer tab."""

    def __init__(self, path: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.path = os.path.abspath(path)
        self._current_slide: int = 0
        self._slide_count: int = 1
        self._slides_data: List[dict] = []
        self._load_presentation()

    @property
    def slide_count(self) -> int:
        return self._slide_count

    def compose(self):
        with Horizontal(id="cct-pptx-toolbar", classes="cct-pptx-toolbar"):
            yield Static(os.path.basename(self.path), id="cct-pptx-info", classes="cct-tb-pill")
            yield Button("◀ Prev Slide", id="cct-pptx-prev", classes="cct-ctrl")
            yield Button("Next Slide ▶", id="cct-pptx-next", classes="cct-ctrl")
            yield Button("Open Externally", id="cct-pptx-open", classes="cct-ctrl")
            yield Button("✕", id="cct-pptx-close", classes="cct-ctrl")
        with VerticalScroll(id="cct-pptx-scroll"):
            yield Static("", id="cct-pptx-display", classes="cct-pptx-display")

    def on_mount(self) -> None:
        self._load_presentation()
        self._refresh_slide()

    def _load_presentation(self) -> None:
        """Parse all slides from PPTX package."""
        self._slides_data.clear()
        if not os.path.isfile(self.path):
            return
        try:
            with zipfile.ZipFile(self.path, "r") as pptx_zip:
                slide_files = [
                    f for f in pptx_zip.namelist()
                    if re.match(r"ppt/slides/slide\d+\.xml", f)
                ]
                # Sort numerically: slide1, slide2...
                slide_files.sort(key=lambda s: int(re.search(r"\d+", s).group(0)))
                self._slide_count = max(1, len(slide_files))

                for s_file in slide_files:
                    xml_data = pptx_zip.read(s_file)
                    root = ET.fromstring(xml_data)
                    slide_info = {"title": "", "bullets": []}

                    # Extract text boxes and shapes
                    for sp in root.findall(f".//{P_NS}sp"):
                        text_runs = []
                        for t in sp.findall(f".//{A_NS}t"):
                            if t.text:
                                text_runs.append(t.text)
                        full_text = " ".join(text_runs).strip()
                        if full_text:
                            if not slide_info["title"]:
                                slide_info["title"] = full_text
                            else:
                                slide_info["bullets"].append(full_text)

                    if not slide_info["title"] and slide_info["bullets"]:
                        slide_info["title"] = slide_info["bullets"].pop(0)

                    self._slides_data.append(slide_info)
        except Exception:
            pass

    def _refresh_slide(self) -> None:
        try:
            info = self.query_one("#cct-pptx-info", Static)
            disp = self.query_one("#cct-pptx-display", Static)
            base = os.path.basename(self.path)
            total = len(self._slides_data) or self._slide_count
            info.update(f"📊 {base} · Slide {self._current_slide + 1}/{total}")

            if self._slides_data and 0 <= self._current_slide < len(self._slides_data):
                data = self._slides_data[self._current_slide]
                title = data.get("title") or f"Slide {self._current_slide + 1}"
                bullets = data.get("bullets", [])

                body_lines = []
                body_lines.append(Text(f"📌 {title}", style="bold yellow"))
                body_lines.append(Text(""))
                for b in bullets:
                    body_lines.append(Text(f"  • {b}", style="white"))

                panel = Panel(
                    Group(*body_lines),
                    title=f"[bold green]Slide {self._current_slide + 1} / {total}[/bold green]",
                    border_style="yellow",
                    padding=(2, 4),
                )
                disp.update(panel)
            else:
                disp.update(f"[b]📊 {base}[/b]\n[dim]Slide {self._current_slide + 1} / {total}[/dim]")
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "cct-pptx-close":
            self._close_tab()
        elif bid == "cct-pptx-prev":
            if self._current_slide > 0:
                self._current_slide -= 1
                self._refresh_slide()
        elif bid == "cct-pptx-next":
            total = len(self._slides_data) or self._slide_count
            if self._current_slide < total - 1:
                self._current_slide += 1
                self._refresh_slide()
        elif bid == "cct-pptx-open":
            try:
                import pathlib, webbrowser
                webbrowser.open(pathlib.Path(self.path).as_uri())
            except Exception:
                pass

    def _close_tab(self) -> None:
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
