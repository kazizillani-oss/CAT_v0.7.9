"""CAT Universal File Preview Engine — Spreadsheet Viewer (calc_terminal/viewers/spreadsheet_viewer.py).

High-fidelity visual spreadsheet grid viewer:
- Supports XLSX and CSV.
- Displays visual interactive grid table using Textual's DataTable.
- Parses XLSX multi-sheet workbooks natively via stdlib zipfile and xml.etree.ElementTree.
- Supports sheet selection, column headers, and search filtering.
"""

from __future__ import annotations

import csv
import os
import re
import xml.etree.ElementTree as ET
import zipfile
from typing import Dict, List, Optional

TEXTUAL_AVAILABLE = True
try:
    from textual.containers import Horizontal, Vertical
    from textual.widgets import Button, DataTable, Input, Static
except Exception:
    TEXTUAL_AVAILABLE = False
    Vertical = object  # type: ignore

S_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


class SpreadsheetViewer(Vertical):
    """Visual spreadsheet table viewer for XLSX and CSV."""

    def __init__(self, path: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.path = os.path.abspath(path)
        self._sheets: Dict[str, List[List[str]]] = {}
        self._sheet_names: List[str] = []
        self._active_sheet_idx: int = 0
        self._load_data()

    def compose(self):
        with Horizontal(id="cct-sheet-toolbar", classes="cct-sheet-toolbar"):
            yield Static(os.path.basename(self.path), id="cct-sheet-info", classes="cct-tb-pill")
            yield Input(placeholder="Filter rows...", id="cct-sheet-filter")
            yield Button("Open Externally", id="cct-sheet-open", classes="cct-ctrl")
            yield Button("✕", id="cct-sheet-close", classes="cct-ctrl")
        yield Horizontal(id="cct-sheet-tabs-strip", classes="cct-sheet-tabs-strip")
        try:
            yield DataTable(id="cct-sheet-datatable")
        except Exception:
            yield Static("DataTable unavailable", id="cct-sheet-fallback")

    def on_mount(self) -> None:
        self._load_data()
        self._populate_table()

    def _load_data(self) -> None:
        """Load either XLSX sheets or CSV rows."""
        self._sheets.clear()
        self._sheet_names.clear()
        if not os.path.isfile(self.path):
            return

        ext = os.path.splitext(self.path)[1].lower()
        if ext == ".csv":
            try:
                with open(self.path, "r", encoding="utf-8", errors="replace", newline="") as f:
                    reader = csv.reader(f)
                    rows = [r for r in list(reader)[:500]]
                self._sheets["Sheet1"] = rows
                self._sheet_names = ["Sheet1"]
            except Exception:
                pass
        elif ext in (".xlsx", ".xlsm"):
            self._load_xlsx()

    def _load_xlsx(self) -> None:
        """Parse XLSX workbook, shared strings, and worksheets."""
        try:
            with zipfile.ZipFile(self.path, "r") as z:
                # 1. Shared strings table
                shared_strings = []
                if "xl/sharedStrings.xml" in z.namelist():
                    root_ss = ET.fromstring(z.read("xl/sharedStrings.xml"))
                    for si in root_ss.findall(f"{S_NS}si"):
                        t = si.find(f"{S_NS}t")
                        if t is not None and t.text:
                            shared_strings.append(t.text)
                        else:
                            # Rich text runs
                            text_runs = [r_t.text or "" for r_t in si.findall(f".//{S_NS}t")]
                            shared_strings.append("".join(text_runs))

                # 2. Workbook sheet names
                sheet_map = []
                if "xl/workbook.xml" in z.namelist():
                    wb_root = ET.fromstring(z.read("xl/workbook.xml"))
                    sheets_elem = wb_root.find(f"{S_NS}sheets")
                    if sheets_elem is not None:
                        for s in sheets_elem.findall(f"{S_NS}sheet"):
                            name = s.get("name", "Sheet")
                            sheet_id = s.get("sheetId", "1")
                            sheet_map.append((name, sheet_id))

                # Fallback if sheet map missing
                if not sheet_map:
                    sheet_files = [f for f in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml", f)]
                    sheet_map = [(f"Sheet{i+1}", str(i+1)) for i in range(len(sheet_files))]

                for name, s_id in sheet_map:
                    sheet_filename = f"xl/worksheets/sheet{s_id}.xml"
                    if sheet_filename not in z.namelist():
                        candidates = [f for f in z.namelist() if f.startswith("xl/worksheets/sheet")]
                        if candidates:
                            sheet_filename = candidates[0]
                        else:
                            continue

                    sheet_root = ET.fromstring(z.read(sheet_filename))
                    sheet_data = sheet_root.find(f"{S_NS}sheetData")
                    rows = []
                    if sheet_data is not None:
                        for row_elem in sheet_data.findall(f"{S_NS}row")[:500]:
                            row_cells = []
                            for c in row_elem.findall(f"{S_NS}c"):
                                cell_type = c.get("t")
                                val_elem = c.find(f"{S_NS}v")
                                val = val_elem.text if val_elem is not None else ""
                                if cell_type == "s" and val.isdigit():
                                    idx = int(val)
                                    val = shared_strings[idx] if idx < len(shared_strings) else val
                                row_cells.append(str(val))
                            rows.append(row_cells)

                    self._sheets[name] = rows
                    self._sheet_names.append(name)
        except Exception:
            pass

    def _populate_table(self, filter_text: str = "") -> None:
        """Render rows into Textual DataTable."""
        try:
            table = self.query_one("#cct-sheet-datatable", DataTable)
            table.clear(columns=True)

            sheet_name = self._sheet_names[self._active_sheet_idx] if self._sheet_names else "Sheet1"
            rows = self._sheets.get(sheet_name, [])

            # Filter if requested
            if filter_text:
                q = filter_text.lower()
                rows = [r for r in rows if any(q in str(cell).lower() for cell in r)]

            if not rows:
                table.add_column("Notice")
                table.add_row("No matching data found.")
                return

            max_cols = max(len(r) for r in rows)
            # Default headers A, B, C...
            for col_idx in range(max_cols):
                header = chr(65 + col_idx) if col_idx < 26 else f"Col{col_idx+1}"
                table.add_column(header)

            for r_idx, row in enumerate(rows):
                padded = row + [""] * (max_cols - len(row))
                table.add_row(*padded[:max_cols], label=str(r_idx + 1))

            # Update info pill
            total_rows = len(self._sheets.get(sheet_name, []))
            info = self.query_one("#cct-sheet-info", Static)
            base = os.path.basename(self.path)
            info.update(f"📊 {base} · {sheet_name} ({total_rows} rows)")
        except Exception:
            pass

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "cct-sheet-filter":
            self._populate_table(event.value.strip())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "cct-sheet-close":
            self._close_tab()
        elif bid == "cct-sheet-open":
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
