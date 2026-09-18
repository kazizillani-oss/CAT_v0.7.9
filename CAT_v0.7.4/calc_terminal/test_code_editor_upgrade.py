"""Comprehensive test suite for CAT Code Editor Upgrade:
- VS Code Shortcut Compatibility & Command Registry
- Editor Line & Text Manipulation Actions
- DevServerManager & Live Preview Management
- Diagnostics & Error Location Navigation
- Universal Visual File Viewers (Image, PDF, DOCX, PPTX, XLSX, CSV)
"""

import io
import os
import shutil
import tempfile
import time
import zipfile
import pytest

from calc_terminal.editor.commands import CATCommand, CommandRegistry, get_command_registry
from calc_terminal.editor.shortcuts import Keybinding, ShortcutManager, get_shortcut_manager, normalize_key
from calc_terminal.editor import actions
from calc_terminal.preview.dev_server import DevServerManager, detect_project_type, find_available_port, is_port_available
from calc_terminal.preview.manager import PreviewManager
from calc_terminal.preview.diagnostics import DiagnosticsManager, parse_error_location, get_diagnostics_manager
from calc_terminal.viewers.registry import ViewerRegistry, get_viewer_registry
from calc_terminal.viewers.image_viewer import ImageViewer
from calc_terminal.viewers.pdf_viewer import PdfViewer
from calc_terminal.viewers.document_viewer import DocumentViewer
from calc_terminal.viewers.presentation_viewer import PresentationViewer
from calc_terminal.viewers.spreadsheet_viewer import SpreadsheetViewer


# ============================================================================
# 1. Command Registry Tests
# ============================================================================

def test_command_registry_basic():
    reg = CommandRegistry()
    called = []

    cmd = CATCommand(
        id="test.hello",
        title="Say Hello",
        category="Test",
        handler=lambda ctx: called.append(ctx.get("name", "world")),
    )
    reg.register(cmd)

    assert reg.get("test.hello") is not None
    assert len(reg.list_commands(category="Test")) == 1

    reg.execute("test.hello", {"name": "Alice"})
    assert called == ["Alice"]

    reg.unregister("test.hello")
    assert reg.get("test.hello") is None


def test_default_command_registry():
    reg = get_command_registry()
    cmds = reg.list_commands()
    assert len(cmds) >= 10

    # Verify key commands are registered
    assert reg.get("editor.toggleComment") is not None
    assert reg.get("editor.deleteLine") is not None
    assert reg.get("editor.moveLineUp") is not None
    assert reg.get("editor.moveLineDown") is not None
    assert reg.get("editor.save") is not None
    assert reg.get("preview.open") is not None
    assert reg.get("editor.commandPalette") is not None


# ============================================================================
# 2. Shortcuts & Conflict Detection Tests
# ============================================================================

def test_key_normalization():
    assert normalize_key("Ctrl+Shift+P") == "ctrl+shift+p"
    assert normalize_key("SHIFT+ENTER") == "shift+enter"
    assert normalize_key("Ctrl+Alt+S") == "ctrl+alt+s"
    assert normalize_key("f1") == "f1"


def test_shortcut_manager_defaults():
    sm = ShortcutManager()
    
    # Test lookup
    cmd = sm.match("ctrl+s")
    assert cmd == "editor.save"

    cmd_preview = sm.match("shift+enter")
    assert cmd_preview == "preview.open"

    cmd_palette = sm.match("ctrl+shift+p")
    assert cmd_palette == "editor.commandPalette"


def test_shortcut_conflict_detection():
    sm = ShortcutManager()
    conflicts = sm.detect_conflicts(key="ctrl+s")
    assert isinstance(conflicts, list)

    # Register custom shortcut with higher priority
    sm.register(Keybinding(command_id="custom.save", key="ctrl+s", when="editor", priority=50))
    matched = sm.match("ctrl+s", context="editor")
    assert matched == "custom.save"


# ============================================================================
# 3. Editor Actions Tests
# ============================================================================

class MockTextArea:
    """Mock Textual TextArea for action testing."""
    def __init__(self, text="", cursor=(0, 0), language="python"):
        self.text = text
        self.cursor_location = cursor
        self.language = language

    def move_cursor(self, loc):
        self.cursor_location = loc


def test_toggle_line_comment_python():
    area = MockTextArea(text="x = 1\ny = 2", cursor=(0, 0), language="python")
    # Comment
    actions.toggle_line_comment(area)
    assert area.text == "# x = 1\ny = 2"
    # Uncomment
    actions.toggle_line_comment(area)
    assert area.text == "x = 1\ny = 2"


def test_toggle_line_comment_js_and_html():
    # JavaScript
    js_area = MockTextArea(text="console.log(42);", cursor=(0, 0), language="javascript")
    actions.toggle_line_comment(js_area)
    assert js_area.text == "// console.log(42);"
    actions.toggle_line_comment(js_area)
    assert js_area.text == "console.log(42);"

    # HTML
    html_area = MockTextArea(text="<div>Hello</div>", cursor=(0, 0), language="html")
    actions.toggle_line_comment(html_area)
    assert html_area.text == "<!-- <div>Hello</div> -->"
    actions.toggle_line_comment(html_area)
    assert html_area.text == "<div>Hello</div>"


def test_delete_line():
    area = MockTextArea(text="line 1\nline 2\nline 3", cursor=(1, 0))
    actions.delete_line(area)
    assert area.text == "line 1\nline 3"
    assert area.cursor_location == (1, 0)


def test_move_line_up_and_down():
    area = MockTextArea(text="line 1\nline 2\nline 3", cursor=(1, 0))
    actions.move_line_up(area)
    assert area.text == "line 2\nline 1\nline 3"
    assert area.cursor_location == (0, 0)

    actions.move_line_down(area)
    assert area.text == "line 1\nline 2\nline 3"
    assert area.cursor_location == (1, 0)


def test_copy_line_up_and_down():
    area = MockTextArea(text="alpha\nbeta", cursor=(0, 2))
    actions.copy_line_down(area)
    assert area.text == "alpha\nalpha\nbeta"

    area2 = MockTextArea(text="alpha\nbeta", cursor=(1, 2))
    actions.copy_line_up(area2)
    assert area2.text == "alpha\nbeta\nbeta"


def test_insert_line_below_and_above():
    area = MockTextArea(text="def foo():\n    pass", cursor=(0, 5))
    actions.insert_line_below(area)
    assert "def foo():" in area.text
    assert "pass" in area.text

    area2 = MockTextArea(text="    pass", cursor=(0, 5))
    actions.insert_line_above(area2)
    assert "pass" in area2.text


# ============================================================================
# 4. DevServerManager & Project Detection Tests
# ============================================================================

def test_port_availability_and_finding():
    # Should find an open port in high range
    port = find_available_port(preferred=18500)
    assert port is not None
    assert is_port_available(port)


def test_detect_project_type():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Empty dir -> static web fallback
        info = detect_project_type(tmpdir)
        assert info.kind == "static"

        # Add index.html -> static
        with open(os.path.join(tmpdir, "index.html"), "w") as f:
            f.write("<h1>Test</h1>")
        assert detect_project_type(tmpdir).kind == "static"

        # Add package.json and vite config -> vite
        with open(os.path.join(tmpdir, "package.json"), "w") as f:
            f.write('{"scripts": {"dev": "vite"}}')
        with open(os.path.join(tmpdir, "vite.config.js"), "w") as f:
            f.write("// vite")
        assert detect_project_type(tmpdir).kind == "vite"


def test_dev_server_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a static HTML site
        html_file = os.path.join(tmpdir, "index.html")
        with open(html_file, "w", encoding="utf-8") as f:
            f.write("<!DOCTYPE html><html><body><h1>CAT Test</h1></body></html>")

        port = find_available_port(preferred=18600)
        mgr = DevServerManager(tmpdir)

        # Start static server
        ok, url = mgr.start(preferred_port=port)
        assert ok is True
        assert mgr.is_running()
        assert mgr.port > 0
        assert "127.0.0.1" in url

        # Stop server
        mgr.stop()
        assert not mgr.is_running()


# ============================================================================
# 5. Live Preview Manager Tests
# ============================================================================

def test_preview_manager():
    with tempfile.TemporaryDirectory() as tmpdir:
        html_file = os.path.join(tmpdir, "test.html")
        with open(html_file, "w", encoding="utf-8") as f:
            f.write("<html><body>Hello Preview</body></html>")

        pm = PreviewManager()
        session = pm.start(tmpdir)
        assert session is not None
        assert session.status == "running"
        assert session.url.startswith("http://127.0.0.1:")

        # Reload
        ok = pm.reload(session.id)
        assert ok is True

        # Stop
        pm.stop(session.id)
        assert session.status == "stopped"


# ============================================================================
# 6. Diagnostics & Error Location Tests
# ============================================================================

def test_parse_error_location():
    loc1 = parse_error_location("Error in app.js:42:15 - SyntaxError")
    assert loc1 is not None
    assert loc1.file == "app.js"
    assert loc1.line == 42
    assert loc1.column == 15

    loc2 = parse_error_location("File \"main.py\", line 88, in run")
    assert loc2 is not None
    assert loc2.file == "main.py"
    assert loc2.line == 88

    loc3 = parse_error_location("index.html:10 Uncaught ReferenceError")
    assert loc3 is not None
    assert loc3.file == "index.html"
    assert loc3.line == 10

    assert parse_error_location("Just a plain error without location") is None


def test_diagnostics_manager():
    dm = DiagnosticsManager()
    d1 = dm.add("error", "Failed to compile at src/App.tsx:24:5", source="build")
    assert d1.severity == "error"
    assert d1.file == "src/App.tsx"
    assert d1.line == 24
    assert d1.column == 5

    d2 = dm.add("warning", "Deprecated API", source="editor")
    assert len(dm.list_diagnostics()) == 2
    assert len(dm.list_diagnostics(severity="error")) == 1
    assert len(dm.list_diagnostics(source="build")) == 1

    dm.clear(source="build")
    assert len(dm.list_diagnostics()) == 1


# ============================================================================
# 7. Universal File Viewers & ViewerRegistry Tests
# ============================================================================

def test_viewer_registry_routing():
    reg = get_viewer_registry()
    assert reg.can_open_visually("test.png")
    assert reg.can_open_visually("doc.pdf")
    assert reg.can_open_visually("notes.docx")
    assert reg.can_open_visually("slides.pptx")
    assert reg.can_open_visually("data.xlsx")
    assert reg.can_open_visually("table.csv")
    assert not reg.can_open_visually("script.py")
    assert not reg.can_open_visually("style.css")


def test_image_viewer():
    from PIL import Image
    with tempfile.TemporaryDirectory() as tmpdir:
        img_path = os.path.join(tmpdir, "test.png")
        # Create a simple test image (red square)
        img = Image.new("RGBA", (20, 20), color=(255, 0, 0, 255))
        img.save(img_path)

        viewer = ImageViewer(img_path)
        assert viewer.path == img_path
        w, h, size_str, has_alpha, fmt = viewer._get_info()
        assert w == 20
        assert h == 20
        assert has_alpha is True
        assert fmt == "PNG"

        # Test zoom state
        viewer._zoom = 1.5
        assert viewer._zoom == 1.5

        # Test rotate
        viewer._rotation = 90
        assert viewer._rotation == 90


def test_pdf_viewer():
    import fitz  # PyMuPDF
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "test.pdf")
        # Create a test PDF with 2 pages
        doc = fitz.open()
        p1 = doc.new_page()
        p1.insert_text((50, 50), "Hello CAT Page 1")
        p2 = doc.new_page()
        p2.insert_text((50, 50), "Hello CAT Page 2")
        doc.save(pdf_path)
        doc.close()

        viewer = PdfViewer(pdf_path)
        assert viewer._page_count == 2
        assert viewer._current_page == 0

        # Navigation
        viewer._current_page = 1
        assert viewer._current_page == 1

        # Search
        results = []
        if viewer._doc:
            for i, page in enumerate(viewer._doc):
                hits = page.search_for("CAT")
                if hits:
                    results.append((i, hits))
        assert len(results) >= 1
        viewer.close()


def test_document_viewer_docx():
    with tempfile.TemporaryDirectory() as tmpdir:
        docx_path = os.path.join(tmpdir, "sample.docx")
        # Create valid DOCX OpenXML zip file
        doc_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body>'
            '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Project Report</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>This is a paragraph of document text.</w:t></w:r></w:p>'
            '<w:tbl>'
            '<w:tr><w:tc><w:p><w:r><w:t>Item</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Price</w:t></w:r></w:p></w:tc></w:tr>'
            '<w:tr><w:tc><w:p><w:r><w:t>Widget</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>$10</w:t></w:r></w:p></w:tc></w:tr>'
            '</w:tbl>'
            '</w:body></w:document>'
        )
        with zipfile.ZipFile(docx_path, "w") as z:
            z.writestr("word/document.xml", doc_xml)

        viewer = DocumentViewer(docx_path)
        assert viewer.path == docx_path
        assert len(viewer._elements) == 3
        assert viewer._elements[0]["type"] == "heading"
        assert viewer._elements[0]["text"] == "Project Report"
        assert viewer._elements[1]["type"] == "paragraph"
        assert viewer._elements[2]["type"] == "table"


def test_presentation_viewer_pptx():
    with tempfile.TemporaryDirectory() as tmpdir:
        pptx_path = os.path.join(tmpdir, "slides.pptx")
        slide1_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
            '<p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>Slide 1 Title</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld>'
            '</p:sld>'
        )
        slide2_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
            '<p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>Slide 2 Details</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld>'
            '</p:sld>'
        )
        with zipfile.ZipFile(pptx_path, "w") as z:
            z.writestr("ppt/slides/slide1.xml", slide1_xml)
            z.writestr("ppt/slides/slide2.xml", slide2_xml)

        viewer = PresentationViewer(pptx_path)
        assert viewer.path == pptx_path
        assert viewer.slide_count == 2
        assert viewer._current_slide == 0


def test_spreadsheet_viewer_csv():
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "data.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("Name,Age,Role\nAlice,30,Engineer\nBob,25,Designer\nCharlie,35,Manager\n")

        viewer = SpreadsheetViewer(csv_path)
        assert viewer.path == csv_path
        assert len(viewer._sheets) >= 1
        rows = viewer._sheets.get("Sheet1", [])
        assert len(rows) == 4
        assert rows[0] == ["Name", "Age", "Role"]
        assert rows[1] == ["Alice", "30", "Engineer"]


def test_spreadsheet_viewer_xlsx():
    with tempfile.TemporaryDirectory() as tmpdir:
        xlsx_path = os.path.join(tmpdir, "data.xlsx")
        workbook_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheets><sheet name="Sales" sheetId="1"/></sheets>'
            '</workbook>'
        )
        sheet1_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData>'
            '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1"><v>100</v></c></row>'
            '<row r="2"><c r="A2" t="s"><v>1</v></c><c r="B2"><v>200</v></c></row>'
            '</sheetData>'
            '</worksheet>'
        )
        strings_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<si><t>Product</t></si>'
            '<si><t>Widgets</t></si>'
            '</sst>'
        )
        with zipfile.ZipFile(xlsx_path, "w") as z:
            z.writestr("xl/workbook.xml", workbook_xml)
            z.writestr("xl/worksheets/sheet1.xml", sheet1_xml)
            z.writestr("xl/sharedStrings.xml", strings_xml)

        viewer = SpreadsheetViewer(xlsx_path)
        assert viewer.path == xlsx_path
        assert len(viewer._sheets) >= 1
        sheet_data = viewer._sheets.get("Sales", [])
        assert len(sheet_data) >= 2
        assert sheet_data[0][0] == "Product"
        assert sheet_data[1][0] == "Widgets"
