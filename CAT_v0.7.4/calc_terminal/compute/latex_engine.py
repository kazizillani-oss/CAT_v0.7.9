"""
CAT LaTeX Mathematics Engine.

Provides reusable LaTeX authoring, validation, terminal rendering, and PDF compilation:
- Expression validation: checks syntax of fractions, integrals, matrices, etc.
- Terminal rendering: renders LaTeX expressions into clean Unicode mathematical notation
- Source export: generates complete stand-alone LaTeX documents or snippet fragments
- PDF compilation: auto-detects installed LaTeX engines (tectonic, latexmk, pdflatex, xelatex),
  runs constrained compilation, and provides helpful instructions if missing.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple


# Greek symbol mapping for terminal rendering
_GREEK_SYMBOLS = {
    r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ",
    r"\epsilon": "ε", r"\zeta": "ζ", r"\eta": "η", r"\theta": "θ",
    r"\iota": "ι", r"\kappa": "κ", r"\lambda": "λ", r"\mu": "μ",
    r"\nu": "ν", r"\xi": "ξ", r"\pi": "π", r"\rho": "ρ",
    r"\sigma": "σ", r"\tau": "τ", r"\upsilon": "υ", r"\phi": "φ",
    r"\chi": "χ", r"\psi": "ψ", r"\omega": "ω",
    r"\Gamma": "Γ", r"\Delta": "Δ", r"\Theta": "Θ", r"\Lambda": "Λ",
    r"\Xi": "Ξ", r"\Pi": "Π", r"\Sigma": "Σ", r"\Upsilon": "Υ",
    r"\Phi": "Φ", r"\Psi": "Ψ", r"\Omega": "Ω",
}

_MATH_OPERATORS = {
    r"\int": "∫", r"\iint": "∬", r"\iiint": "∭", r"\oint": "∮",
    r"\sum": "∑", r"\prod": "∏", r"\partial": "∂", r"\nabla": "∇",
    r"\infty": "∞", r"\pm": "±", r"\mp": "∓", r"\times": "×",
    r"\div": "÷", r"\approx": "≈", r"\neq": "≠", r"\leq": "≤",
    r"\geq": "≥", r"\ll": "≪", r"\gg": "≫", r"\in": "∈",
    r"\notin": "∉", r"\subset": "⊂", r"\subseteq": "⊆",
    r"\cup": "∪", r"\cap": "∩", r"\forall": "∀", r"\exists": "∃",
    r"\to": "→", r"\rightarrow": "→", r"\leftarrow": "←",
    r"\Rightarrow": "⇒", r"\Leftarrow": "⇐", r"\Leftrightarrow": "⇔",
    r"\sqrt": "√", r"\cdot": "·", r"\hbar": "ℏ",
}

# Subscript and superscript translation
_SUB_DIGITS = {"0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉", "+": "₊", "-": "₋", "=": "₌", "(": "₍", ")": "₎", "a": "ₐ", "e": "ₑ", "i": "ᵢ", "o": "ₒ", "r": "ᵣ", "u": "ᵤ", "v": "ᵥ", "x": "ₓ"}
_SUP_DIGITS = {"0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "+": "⁺", "-": "⁻", "=": "⁼", "(": "⁽", ")": "⁾", "n": "ⁿ", "i": "ⁱ"}


def validate_latex(latex_str: str) -> Tuple[bool, Optional[str]]:
    """Validates basic syntax and bracket balancing of a LaTeX mathematical expression."""
    if not latex_str or not latex_str.strip():
        return False, "Empty LaTeX string."

    s = latex_str.strip()
    # Check brace matching
    stack = []
    for i, ch in enumerate(s):
        if ch in ("{", "[", "("):
            stack.append((ch, i))
        elif ch in ("}", "]", ")"):
            if not stack:
                return False, f"Unmatched closing delimiter '{ch}' at position {i}."
            top_ch, _ = stack.pop()
            matches = {"}": "{", "]": "[", ")": "("}
            if matches[ch] != top_ch:
                return False, f"Mismatched delimiter: opened with '{top_ch}' but closed with '{ch}' at position {i}."

    if stack:
        unclosed, pos = stack[-1]
        return False, f"Unclosed delimiter '{unclosed}' opened at position {pos}."

    # Check environments (\begin{...} / \end{...})
    begins = re.findall(r"\\begin\{([a-zA-Z0-9*]+)\}", s)
    ends = re.findall(r"\\end\{([a-zA-Z0-9*]+)\}", s)
    if len(begins) != len(ends):
        return False, f"Mismatched environments: {len(begins)} \\begin vs {len(ends)} \\end statements."

    return True, None


def render_to_terminal_unicode(latex_str: str) -> str:
    """Converts common LaTeX mathematical notation into beautiful, readable Unicode text."""
    s = latex_str.strip()
    # Strip enclosing math delimiters
    if s.startswith("$$") and s.endswith("$$"):
        s = s[2:-2].strip()
    elif s.startswith("$") and s.endswith("$"):
        s = s[1:-1].strip()
    elif s.startswith("\\[") and s.endswith("\\]"):
        s = s[2:-2].strip()

    # Replace Greek letters
    for cmd, sym in _GREEK_SYMBOLS.items():
        s = re.sub(re.escape(cmd) + r"(?![a-zA-Z])", sym, s)

    # Replace math operators
    for cmd, sym in _MATH_OPERATORS.items():
        s = re.sub(re.escape(cmd) + r"(?![a-zA-Z])", sym, s)

    # Fractions: \frac{num}{den} -> (num) / (den) or stacked
    frac_pat = re.compile(r"\\frac\{([^{}]+)\}\{([^{}]+)\}")
    while frac_pat.search(s):
        s = frac_pat.sub(r"(\1 / \2)", s)

    # Square roots: \sqrt{arg} or \sqrt[n]{arg}
    s = re.sub(r"\\sqrt\[(\d+)\]\{([^{}]+)\}", r"ⁿ√(\2)", s)
    s = re.sub(r"\\sqrt\{([^{}]+)\}", r"√(\1)", s)

    # Superscripts: ^{123} or ^2
    def _rep_sup(m):
        content = m.group(1) or m.group(2)
        return "".join(_SUP_DIGITS.get(c, c) for c in content)
    s = re.sub(r"\^\{([^{}]+)\}", _rep_sup, s)
    s = re.sub(r"\^([0-9a-zA-Z])", _rep_sup, s)

    # Subscripts: _{123} or _2
    def _rep_sub(m):
        content = m.group(1) or m.group(2)
        return "".join(_SUB_DIGITS.get(c, c) for c in content)
    s = re.sub(r"_\{([^{}]+)\}", _rep_sub, s)
    s = re.sub(r"_([0-9a-zA-Z])", _rep_sub, s)

    # Text blocks: \text{...} or \mathrm{...}
    s = re.sub(r"\\(?:text|mathrm|mathbf|mathit)\{([^{}]+)\}", r"\1", s)

    # Left / right delimiters
    s = re.sub(r"\\(?:left|right)[.()[\]|]", lambda m: m.group(0)[-1] if m.group(0)[-1] != "." else "", s)

    # Spacing commands
    s = re.sub(r"\\[,;! ]", " ", s)
    s = re.sub(r"\\quad", "  ", s)
    s = re.sub(r"\\qquad", "    ", s)

    return s.strip()


def detect_latex_compiler() -> Optional[str]:
    """Detects available LaTeX compiler on the system PATH."""
    for cmd in ("tectonic", "latexmk", "pdflatex", "xelatex", "lualatex"):
        if shutil.which(cmd):
            return cmd
    return None


def get_compiler_installation_instructions() -> str:
    """Returns platform-specific instructions on installing a modern, lightweight LaTeX compiler."""
    return (
        "No LaTeX compiler was found on your system PATH.\n"
        "To compile LaTeX documents to PDF, install one of the following:\n"
        "  1. Tectonic (Recommended — lightweight, self-contained, auto-downloads packages):\n"
        "     • Windows (winget): `winget install tectonic` or `cargo install tectonic`\n"
        "     • macOS: `brew install tectonic`\n"
        "     • Linux: `cargo install tectonic` or distribution package manager\n"
        "  2. TeX Live / MiKTeX:\n"
        "     • Windows: Install MiKTeX from https://miktex.org/\n"
        "     • macOS: `brew install --cask mactex-no-gui`\n"
        "     • Ubuntu/Debian: `sudo apt install texlive-latex-base`\n"
    )


def compile_latex_to_pdf(
    latex_content: str,
    output_pdf_path: str,
    timeout_seconds: int = 30,
) -> Dict[str, Any]:
    """Compiles a complete LaTeX document or fragment into a PDF using an installed compiler.

    Guarantees:
    - Never leaves temporary build files lying around
    - Constrained process with timeout
    - Honest error diagnostics on compilation failure
    - Non-destructive execution
    """
    compiler = detect_latex_compiler()
    if not compiler:
        return {
            "success": False,
            "error": "CompilerNotFound",
            "message": get_compiler_installation_instructions(),
        }

    # Ensure document has preamble if missing
    if r"\begin{document}" not in latex_content:
        latex_content = (
            "\\documentclass[11pt]{article}\n"
            "\\usepackage{amsmath,amssymb,amsfonts,bm}\n"
            "\\usepackage[utf8]{inputenc}\n"
            "\\usepackage{geometry}\n"
            "\\geometry{margin=1in}\n"
            "\\begin{document}\n"
            f"{latex_content}\n"
            "\\end{document}\n"
        )

    with tempfile.TemporaryDirectory(prefix="cat_latex_") as tmp_dir:
        tex_path = os.path.join(tmp_dir, "document.tex")
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(latex_content)

        cmd = []
        if compiler == "tectonic":
            cmd = ["tectonic", "-o", tmp_dir, tex_path]
        elif compiler == "latexmk":
            cmd = ["latexmk", "-pdf", "-interaction=nonstopmode", "-outdir=" + tmp_dir, tex_path]
        elif compiler in ("pdflatex", "xelatex", "lualatex"):
            cmd = [compiler, "-interaction=nonstopmode", "-output-directory=" + tmp_dir, tex_path]

        try:
            res = subprocess.run(
                cmd,
                cwd=tmp_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_seconds,
            )
            generated_pdf = os.path.join(tmp_dir, "document.pdf")
            if res.returncode == 0 and os.path.exists(generated_pdf):
                os.makedirs(os.path.dirname(os.path.abspath(output_pdf_path)), exist_ok=True)
                shutil.copy2(generated_pdf, output_pdf_path)
                return {
                    "success": True,
                    "compiler": compiler,
                    "pdf_path": output_pdf_path,
                    "file_size_bytes": os.path.getsize(output_pdf_path),
                }
            else:
                return {
                    "success": False,
                    "compiler": compiler,
                    "error": "CompilationFailed",
                    "stdout": res.stdout[-1500:] if res.stdout else "",
                    "stderr": res.stderr[-1000:] if res.stderr else "",
                }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "compiler": compiler,
                "error": "TimeoutExpired",
                "message": f"Compilation timed out after {timeout_seconds} seconds.",
            }
        except Exception as e:
            return {
                "success": False,
                "compiler": compiler,
                "error": "ExecutionError",
                "message": str(e),
            }
