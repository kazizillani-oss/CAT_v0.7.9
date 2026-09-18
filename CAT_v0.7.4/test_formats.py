"""v0.7.8.2: extraction matrix for the formats the brief demands."""
import os
import sys
import tempfile

sys.path.insert(0, ".")

from calc_terminal import attachments as _att

fails = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


tmp = tempfile.mkdtemp()
files = {
    "main.py": "import os\nprint('hi')\n",
    "app.js": "console.log('hi');\n",
    "data.json": '{"name": "cct", "tags": ["a", "b"]}\n',
    "notes.md": "# Title\nSome body text.\n",
    "readme.txt": "plain text content\n",
    "table.csv": "a,b,c\n1,2,3\n4,5,6\n",
    "page.html": "<html><body><h1>Hi</h1></body></html>\n",
    "style.css": "body { color: red; }\n",
    "conf.yaml": "name: cct\nversion: 1\n",
    "logfile.log": "INFO: started\nERROR: boom\n",
}
for name, content in files.items():
    with open(os.path.join(tmp, name), "w", encoding="utf-8") as f:
        f.write(content)

# text/code/data formats
for name in files:
    att = _att.AttachmentManager.create(os.path.join(tmp, name))
    check(f"{name} extracts", att.extraction_status == _att.STATUS_READY, att.error or "")
    check(f"{name} has real content", bool(att.content and att.content.strip()),
          (att.content or "")[:40].replace("\n", "\\n"))

# CSV gets a real parse (header + rows)
att = _att.AttachmentManager.create(os.path.join(tmp, "table.csv"))
check("csv parsed", att.content and "columns" in att.content and "first rows" in att.content)

# JSON pretty parse
att = _att.AttachmentManager.create(os.path.join(tmp, "data.json"))
check("json parsed", att.content and '"cct"' in att.content)

# PDF: honest result either way (text layer or explicit note), never silent
pdf_path = os.path.join(tmp, "doc.pdf")
with open(pdf_path, "wb") as f:
    f.write(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
            b"2 0 obj\n<< /Type /Page /Parent 1 0 R /Contents 3 0 R >>\nendobj\n"
            b"3 0 obj\n<< /Length 44 >>\nstream\nBT /F1 12 Tf 72 720 Td (Hello PDF) Tj ET\nendstream\nendobj\n"
            b"trailer\n<< /Root 1 0 R >>\n%%EOF\n")
att = _att.AttachmentManager.create(pdf_path)
check("pdf extracts", att.extraction_status == _att.STATUS_READY, att.error or "")
check("pdf honest content", att.content and ("PDF" in att.content or "attachment" in att.content))

# DOCX: kind=document, honest metadata block (no fake text)
docx_path = os.path.join(tmp, "letter.docx")
with open(docx_path, "wb") as f:
    f.write(b"PK\x03\x04" + os.urandom(200))
att = _att.AttachmentManager.create(docx_path)
check("docx honest", att.extraction_status == _att.STATUS_READY
      and "content not readable as text" in att.content, att.error or "")

# Unknown binary: honest, never pretend
bin_path = os.path.join(tmp, "blob.bin")
with open(bin_path, "wb") as f:
    f.write(os.urandom(64))
att = _att.AttachmentManager.create(bin_path)
check("binary honest", "content not readable as text" in att.content)

# Missing file
att = _att.AttachmentManager.create(os.path.join(tmp, "ghost.py"))
check("missing fails honestly", att.extraction_status == _att.STATUS_FAILED and att.error)

# Oversized text is capped, not lost
big_path = os.path.join(tmp, "big.log")
with open(big_path, "w", encoding="utf-8") as f:
    f.write("x" * 50000)
att = _att.AttachmentManager.create(big_path)
check("large file capped", att.content and len(att.content) <= _att.TEXT_FILE_MAX_CHARS + 100)
check("large file not empty", len(att.content) > 10000)

# Folder listing works
att = _att.AttachmentManager.create(tmp)
check("folder extracts", att.kind == "folder" and att.extraction_status == _att.STATUS_READY,
      att.error or "")
check("folder lists files", att.content and "main.py" in att.content)

print()
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
print("FORMAT MATRIX ALL PASSED")
