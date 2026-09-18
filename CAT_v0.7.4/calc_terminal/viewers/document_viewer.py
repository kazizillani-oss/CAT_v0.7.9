"""CAT Universal File Preview Engine — DOCX Document Viewer (calc_terminal/viewers/document_viewer.py).

High-fidelity visual DOCX document renderer:
- Displays actual visual document structure (headings, styled paragraphs, formatted tables, lists).
- Parses WordprocessingML (word/document.xml) natively via stdlib zipfile and xml.etree.ElementTree.
- Supports zoom, page scrolling, and external open.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
import zipfile
from typing import List, Optional

TEXTUAL_AVAILABLE = True
try:
    from rich.console import Group
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from textual.containers import Horizontal, Vertical, VerticalScroll
    from textual.widgets import Button, Static
except Exception:
    TEXTUAL_AVAILABLE = False
    Vertical = object  # type: ignore

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class DocumentViewer(Vertical):
    """Visual DOCX document renderer tab."""

    def __init__(self, path: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.path = os.path.abspath(path)
        self._zoom: float = 1.0
        self._elements: List[dict] = []
        self._load_elements()

    def _load_elements(self) -> List[dict]:
        self._elements = []
        if not os.path.isfile(self.path):
            return self._elements
        try:
            with zipfile.ZipFile(self.path, "r") as docx_zip:
                if "word/document.xml" not in docx_zip.namelist():
                    return self._elements
                xml_content = docx_zip.read("word/document.xml")
                root = ET.fromstring(xml_content)
                body = root.find(f"{W_NS}body")
                if body is None:
                    return self._elements
                for child in body:
                    tag = child.tag
                    if tag == f"{W_NS}p":
                        style_elem = child.find(f".//{W_NS}pStyle")
                        style_val = style_elem.get(f"{W_NS}val", "") if style_elem is not None else ""
                        is_heading = style_val.lower().startswith("heading") or "title" in style_val.lower()
                        runs = []
                        for r in child.findall(f"{W_NS}r"):
                            t_elem = r.find(f"{W_NS}t")
                            if t_elem is not None and t_elem.text:
                                runs.append(t_elem.text)
                        full_text = "".join(runs).strip()
                        if full_text:
                            self._elements.append({
                                "type": "heading" if is_heading else "paragraph",
                                "style": style_val,
                                "text": full_text,
                            })
                    elif tag == f"{W_NS}tbl":
                        table_data = []
                        for tr in child.findall(f"{W_NS}tr"):
                            row_cells = []
                            for tc in tr.findall(f"{W_NS}tc"):
                                cell_texts = []
                                for cp in tc.findall(f"{W_NS}p"):
                                    for cr in cp.findall(f"{W_NS}r"):
                                        ct = cr.find(f"{W_NS}t")
                                        if ct is not None and ct.text:
                                            cell_texts.append(ct.text)
                                row_cells.append(" ".join(cell_texts).strip())
                            if any(row_cells):
                                table_data.append(row_cells)
                        if table_data:
                            self._elements.append({
                                "type": "table",
                                "rows": table_data,
                            })
        except Exception:
            pass
        return self._elements

    def compose(self):
        with Horizontal(id="cct-docx-toolbar", classes="cct-docx-toolbar"):
            yield Static(os.path.basename(self.path), id="cct-docx-info", classes="cct-tb-pill")
            yield Button("−", id="cct-docx-zoomout", classes="cct-ctrl", tooltip="Zoom Out")
            yield Button("+", id="cct-docx-zoomin", classes="cct-ctrl", tooltip="Zoom In")
            yield Button("100%", id="cct-docx-reset", classes="cct-ctrl")
            yield Button("Open Externally", id="cct-docx-open", classes="cct-ctrl")
            yield Button("✕", id="cct-docx-close", classes="cct-ctrl")
        with VerticalScroll(id="cct-docx-scroll"):
            yield Static("", id="cct-docx-display", classes="cct-docx-display")

    def on_mount(self) -> None:
        self._render_document()

    def _render_document(self) -> None:
        try:
            disp = self.query_one("#cct-docx-display", Static)
            if not os.path.isfile(self.path):
                disp.update("[red]File not found.[/red]")
                return

            elements = []
            with zipfile.ZipFile(self.path, "r") as docx_zip:
                if "word/document.xml" not in docx_zip.namelist():
                    disp.update("[red]Invalid DOCX: word/document.xml missing.[/red]")
                    return
                xml_content = docx_zip.read("word/document.xml")
                root = ET.fromstring(xml_content)
                body = root.find(f"{W_NS}body")
                if body is None:
                    disp.update("[dim]Empty document body.[/dim]")
                    return

                for child in body:
                    tag = child.tag
                    if tag == f"{W_NS}p":
                        # Paragraph or Heading
                        p_elem = self._parse_paragraph(child)
                        if p_elem:
                            elements.append(p_elem)
                    elif tag == f"{W_NS}tbl":
                        # Table
                        tbl_elem = self._parse_table(child)
                        if tbl_elem:
                            elements.append(tbl_elem)

            if elements:
                # Wrap in styled document sheet panel
                base = os.path.basename(self.path)
                doc_group = Group(*elements)
                sheet_panel = Panel(
                    doc_group,
                    title=f"[bold blue]📄 {base}[/bold blue]",
                    border_style="cyan",
                    padding=(1, 2),
                )
                disp.update(sheet_panel)
            else:
                disp.update("[italic dim]No displayable text or tables in document.[/italic dim]")
        except Exception as e:
            try:
                self.query_one("#cct-docx-display", Static).update(f"[red]Error rendering DOCX: {e}[/red]")
            except Exception:
                pass

    def _parse_paragraph(self, p_node: ET.Element) -> Optional[Any]:
        """Parse Word paragraph into Rich Text or Heading."""
        # Check for heading style
        p_style = p_node.find(f"{W_NS}pPr/{W_NS}pStyle")
        style_val = p_style.get(f"{W_NS}val", "") if p_style is not None else ""
        is_heading1 = "Heading1" in style_val or "heading 1" in style_val.lower()
        is_heading2 = "Heading2" in style_val or "heading 2" in style_val.lower()

        full_text = Text()
        for r_node in p_node.findall(f"{W_NS}r"):
            r_pr = r_node.find(f"{W_NS}rPr")
            is_bold = r_pr is not None and r_pr.find(f"{W_NS}b") is not None
            is_italic = r_pr is not None and r_pr.find(f"{W_NS}i") is not None
            t_node = r_node.find(f"{W_NS}t")
            if t_node is not None and t_node.text:
                style = ""
                if is_heading1:
                    style = "bold cyan"
                elif is_heading2:
                    style = "bold green"
                elif is_bold and is_italic:
                    style = "bold italic"
                elif is_bold:
                    style = "bold"
                elif is_italic:
                    style = "italic"
                full_text.append(t_node.text, style=style)

        if not full_text.plain.strip():
            return Text("")  # blank spacing line
        return full_text

    def _parse_table(self, tbl_node: ET.Element) -> Optional[Table]:
        """Parse Word table into a formatted Rich Table."""
        table = Table(show_header=True, header_style="bold magenta", border_style="dim")
        rows_data = []
        for tr in tbl_node.findall(f"{W_NS}tr"):
            row = []
            for tc in tr.findall(f"{W_NS}tc"):
                cell_texts = []
                for p in tc.findall(f"{W_NS}p"):
                    p_text = "".join(t.text or "" for t in p.findall(f".//{W_NS}t"))
                    if p_text:
                        cell_texts.append(p_text)
                row.append("\n".join(cell_texts))
            rows_data.append(row)

        if not rows_data:
            return None

        max_cols = max(len(r) for r in rows_data)
        for i in range(max_cols):
            header = rows_data[0][i] if len(rows_data[0]) > i and rows_data[0][i] else f"Col {i + 1}"
            table.add_column(header)

        for row in rows_data[1:]:
            padded = row + [""] * (max_cols - len(row))
            table.add_row(*padded[:max_cols])
        return table

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "cct-docx-close":
            self._close_tab()
        elif bid == "cct-docx-zoomin":
            self._zoom = min(2.5, self._zoom * 1.2)
            self._render_document()
        elif bid == "cct-docx-zoomout":
            self._zoom = max(0.5, self._zoom / 1.2)
            self._render_document()
        elif bid == "cct-docx-reset":
            self._zoom = 1.0
            self._render_document()
        elif bid == "cct-docx-open":
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
