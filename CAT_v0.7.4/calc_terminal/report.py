"""
CCT Report Generator — exports solved notebooks (from session history)
to a real Markdown file and a real PDF (via reportlab, already a
dependency). This is a straight, faithful export of the same
Question/Given/Find/Formula/Substitution/Calculation/Units/Verification
/Answer structure already rendered on screen — not a separate "fake"
summary.
"""

import os
import re

from .mathtext import compose, mathify

PDF_AVAILABLE = True
try:
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem, HRFlowable
    )
except Exception:
    PDF_AVAILABLE = False


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _plain(s):
    return _ANSI_RE.sub("", str(s))


def _notebook_to_markdown(nb, index):
    lines = [f"## {index}. {nb.get('topic', 'Notebook')}", ""]
    lines.append(f"**Question:** {_plain(nb.get('question', ''))}")
    lines.append("")
    lines.append("**Given data:**")
    for g in nb.get("given", []):
        lines.append(f"- {_plain(g)}")
    lines.append("")
    lines.append(f"**Find:** {_plain(nb.get('find', ''))}")
    lines.append("")
    lines.append("**Formula:**")
    lines.append("```")
    lines.append(_plain(compose(nb.get("formula", []))))
    lines.append("```")
    lines.append("")
    lines.append("**Substitution:**")
    lines.append("```")
    lines.append(_plain(compose(nb.get("substitution", []))))
    lines.append("```")
    lines.append("")
    calc = nb.get("calculation", [])
    if calc:
        lines.append("**Calculation:**")
        for i, c in enumerate(calc, 1):
            lines.append(f"{i}. {_plain(mathify(c))}")
        lines.append("")
    if nb.get("unit"):
        lines.append(f"**Units:** {_plain(mathify(nb['unit']))}")
        lines.append("")
    if nb.get("verification"):
        lines.append(f"**Verification:** {_plain(mathify(nb['verification']))}")
        lines.append("")
    lines.append(f"**Final answer:** {_plain(nb.get('final_answer', ''))}")
    lines.append("")
    lines.append("---")
    lines.append("")
    return lines


def export_history_markdown(history, path, title="CAT Notebook Export"):
    if not history:
        raise ValueError("No history to export.")
    lines = [f"# {title}", ""]
    lines.append(f"_{len(history)} notebook(s), exported from Chemistry Calc Terminal_")
    lines.append("")
    for i, nb in enumerate(history, 1):
        lines.extend(_notebook_to_markdown(nb, i))
    text = "\n".join(lines)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def export_history_pdf(history, path, title="CAT Notebook Export"):
    if not PDF_AVAILABLE:
        raise RuntimeError("reportlab is not installed — run: pip install reportlab")
    if not history:
        raise ValueError("No history to export.")

    doc = SimpleDocTemplate(path, pagesize=LETTER,
                             topMargin=0.7 * inch, bottomMargin=0.7 * inch,
                             leftMargin=0.75 * inch, rightMargin=0.75 * inch)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], textColor=colors.HexColor("#3b2a86"))
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=colors.HexColor("#1f6fb2"),
                         spaceBefore=14)
    body = ParagraphStyle("body", parent=styles["BodyText"], leading=15)
    mono = ParagraphStyle("mono", parent=styles["Code"], backColor=colors.HexColor("#f4f4f8"),
                           borderPadding=6, leading=13)
    answer = ParagraphStyle("answer", parent=styles["BodyText"],
                             textColor=colors.HexColor("#0a7d3c"), fontName="Helvetica-Bold")

    def esc(s):
        return (_plain(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    story = [Paragraph(esc(title), h1),
             Paragraph(f"{len(history)} notebook(s) — Chemistry Calc Terminal", body),
             Spacer(1, 12)]

    for i, nb in enumerate(history, 1):
        story.append(Paragraph(f"{i}. {esc(nb.get('topic', 'Notebook'))}", h2))
        story.append(Paragraph(f"<b>Question:</b> {esc(nb.get('question', ''))}", body))
        given = nb.get("given", [])
        if given:
            story.append(Paragraph("<b>Given data:</b>", body))
            story.append(ListFlowable(
                [ListItem(Paragraph(esc(g), body)) for g in given], bulletType="bullet"))
        story.append(Paragraph(f"<b>Find:</b> {esc(nb.get('find', ''))}", body))
        story.append(Paragraph("<b>Formula:</b>", body))
        story.append(Paragraph(esc(compose(nb.get("formula", []))).replace("\n", "<br/>"), mono))
        story.append(Paragraph("<b>Substitution:</b>", body))
        story.append(Paragraph(esc(compose(nb.get("substitution", []))).replace("\n", "<br/>"), mono))
        calc = nb.get("calculation", [])
        if calc:
            story.append(Paragraph("<b>Calculation:</b>", body))
            story.append(ListFlowable(
                [ListItem(Paragraph(esc(mathify(c)), body)) for c in calc], bulletType="1"))
        if nb.get("unit"):
            story.append(Paragraph(f"<b>Units:</b> {esc(mathify(nb['unit']))}", body))
        if nb.get("verification"):
            story.append(Paragraph(f"<b>Verification:</b> {esc(mathify(nb['verification']))}", body))
        story.append(Paragraph(f"Final answer: {esc(nb.get('final_answer', ''))}", answer))
        story.append(HRFlowable(width="100%", color=colors.HexColor("#dddddd"), spaceBefore=10, spaceAfter=10))

    doc.build(story)
    return path


def default_export_dir():
    """Notebook exports go into the shared Project Workspace now (spec
    section 16, calc_terminal/workspace.py) instead of report.py's own
    ~/CCT_exports — which, before this, was a *different* directory
    from scires.py's ~/cct_exports (different casing, never the same
    folder). Falls back to the old location only if the workspace
    module can't be imported, so a broken workspace config never
    blocks an export outright.

    STRICT FIX v0.7.9.6: explicit ensure=True — this is a WRITE path
    (the user explicitly requested an export), so directory creation
    is authorized here. Read paths (summary/list_category) use
    ensure=False and never create."""
    try:
        from . import workspace
        return workspace.category_dir("reports", ensure=True)
    except Exception:
        d = os.path.join(os.path.expanduser("~"), "CCT_exports")
        os.makedirs(d, exist_ok=True)
        return d
