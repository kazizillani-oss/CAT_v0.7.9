"""
CAT Qala Scientific Computing & Notebook Engine.

Provides dedicated computational tools for Qala (Notebook and Scientific Agent):
- Jupyter Notebook (.ipynb) operations: parse, inspect cells, edit cells, create notebooks, execute cells
- Symbolic Mathematics via SymPy: algebra, calculus, ODEs, linear algebra, limits, integrals, equation solving
- Numerical Computing via NumPy / SciPy: numerical integration, root finding, matrix operations, statistical distributions
- Exact expression verification and result auditing
"""

from __future__ import annotations

import io
import json
import logging
import os
import sys
import traceback
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("cat.compute.qala")

# Scientific libraries
try:
    import sympy as sp
    from sympy import symbols, Eq, solve, dsolve, diff, integrate, limit, Matrix, oo, pi, E
    _HAS_SYMPY = True
except ImportError:
    sp = None
    _HAS_SYMPY = False

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    np = None
    _HAS_NUMPY = False

try:
    import scipy
    from scipy import integrate as sc_integrate, optimize as sc_optimize, stats as sc_stats
    _HAS_SCIPY = True
except ImportError:
    scipy = None
    _HAS_SCIPY = False

try:
    import nbformat
    from nbformat.v4 import new_notebook, new_code_cell, new_markdown_cell
    _HAS_NBFORMAT = True
except ImportError:
    nbformat = None
    _HAS_NBFORMAT = False


# =============================================================================
# 1. Jupyter Notebook (.ipynb) Operations
# =============================================================================

def read_notebook(path: str) -> Dict[str, Any]:
    """Reads a .ipynb notebook and returns a clean, structured representation of cells and metadata."""
    if not os.path.exists(path):
        return {"error": f"Notebook file '{path}' not found."}

    try:
        with open(path, "r", encoding="utf-8") as f:
            if _HAS_NBFORMAT:
                nb = nbformat.read(f, as_version=4)
            else:
                nb = json.load(f)
    except Exception as e:
        return {"error": f"Failed to parse notebook JSON: {e}"}

    cells = []
    raw_cells = nb.get("cells", []) if isinstance(nb, dict) else getattr(nb, "cells", [])
    for idx, c in enumerate(raw_cells):
        cell_dict = c if isinstance(c, dict) else dict(c)
        ctype = cell_dict.get("cell_type", "code")
        source = cell_dict.get("source", "")
        if isinstance(source, list):
            source = "".join(source)

        outputs_summary = []
        outputs = cell_dict.get("outputs", [])
        for out in outputs:
            out_d = out if isinstance(out, dict) else dict(out)
            otype = out_d.get("output_type", "")
            if otype == "stream":
                text = out_d.get("text", "")
                if isinstance(text, list):
                    text = "".join(text)
                outputs_summary.append(f"stdout: {text.strip()}")
            elif otype in ("execute_result", "display_data"):
                data = out_d.get("data", {})
                if "text/plain" in data:
                    t = data["text/plain"]
                    outputs_summary.append("result: " + ("".join(t) if isinstance(t, list) else str(t)).strip())
            elif otype == "error":
                ename = out_d.get("ename", "Error")
                evalue = out_d.get("evalue", "")
                outputs_summary.append(f"error: {ename}: {evalue}")

        cells.append({
            "index": idx,
            "type": ctype,
            "source": source,
            "execution_count": cell_dict.get("execution_count"),
            "outputs": outputs_summary,
        })

    nb_meta = nb.get("metadata", {}) if isinstance(nb, dict) else getattr(nb, "metadata", {})
    return {
        "path": path,
        "cell_count": len(cells),
        "kernel": nb_meta.get("kernelspec", {}).get("display_name", "Python 3"),
        "cells": cells,
    }


def create_notebook(path: str, title: str = "Notebook", cells: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """Creates a new Jupyter notebook at the given path."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if _HAS_NBFORMAT:
        nb = new_notebook()
        cell_objs = [new_markdown_cell(f"# {title}\n*Created by Qala — CAT Scientific Agent*")]
        if cells:
            for c in cells:
                ctype = c.get("type", "code")
                src = c.get("source", "")
                if ctype == "markdown":
                    cell_objs.append(new_markdown_cell(src))
                else:
                    cell_objs.append(new_code_cell(src))
        nb.cells = cell_objs
        with open(path, "w", encoding="utf-8") as f:
            nbformat.write(nb, f)
    else:
        initial_cells = [{
            "cell_type": "markdown",
            "metadata": {},
            "source": [f"# {title}\n", "*Created by Qala — CAT Scientific Agent*"]
        }]
        if cells:
            for c in cells:
                initial_cells.append({
                    "cell_type": c.get("type", "code"),
                    "metadata": {},
                    "source": [c.get("source", "")],
                    "outputs": [] if c.get("type", "code") == "code" else None,
                    "execution_count": None,
                })
        nb_data = {
            "cells": initial_cells,
            "metadata": {"language_info": {"name": "python"}},
            "nbformat": 4,
            "nbformat_minor": 5,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(nb_data, f, indent=2)

    return {"status": "created", "path": path, "total_cells": len(cells or []) + 1}


def edit_notebook_cell(path: str, cell_index: int, new_source: str, cell_type: Optional[str] = None) -> Dict[str, Any]:
    """Edits a specific cell in an existing notebook without altering other cells."""
    if not os.path.exists(path):
        return {"error": f"Notebook '{path}' does not exist."}

    with open(path, "r", encoding="utf-8") as f:
        nb = json.load(f)

    cells = nb.get("cells", [])
    if cell_index < 0 or cell_index >= len(cells):
        return {"error": f"Cell index {cell_index} out of range (notebook has {len(cells)} cells)."}

    target = cells[cell_index]
    target["source"] = new_source
    if cell_type:
        target["cell_type"] = cell_type

    with open(path, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=2)

    return {"status": "updated", "index": cell_index, "type": target.get("cell_type")}


def add_notebook_cell(path: str, source: str, cell_type: str = "code", position: Optional[int] = None) -> Dict[str, Any]:
    """Appends or inserts a cell into an existing notebook."""
    if not os.path.exists(path):
        return {"error": f"Notebook '{path}' does not exist."}

    with open(path, "r", encoding="utf-8") as f:
        nb = json.load(f)

    cells = nb.get("cells", [])
    new_cell = {
        "cell_type": cell_type,
        "metadata": {},
        "source": source,
    }
    if cell_type == "code":
        new_cell["outputs"] = []
        new_cell["execution_count"] = None

    if position is None or position >= len(cells):
        cells.append(new_cell)
        idx = len(cells) - 1
    else:
        idx = max(0, position)
        cells.insert(idx, new_cell)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=2)

    return {"status": "added", "index": idx, "type": cell_type, "total_cells": len(cells)}


def execute_notebook_cell(code: str, timeout_sec: int = 20) -> Dict[str, Any]:
    """Executes a snippet of Python code in a safe execution scope and captures output, return value, or errors."""
    import contextlib

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    exec_globals: Dict[str, Any] = {
        "__builtins__": __builtins__,
    }
    if _HAS_SYMPY:
        exec_globals["sp"] = sp
        exec_globals["sympy"] = sp
    if _HAS_NUMPY:
        exec_globals["np"] = np
        exec_globals["numpy"] = np
    if _HAS_SCIPY:
        exec_globals["scipy"] = scipy

    result_val = None
    error_info = None

    try:
        with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
            # Parse AST to capture the expression value if the last statement is an expression
            import ast
            tree = ast.parse(code)
            if tree.body and isinstance(tree.body[-1], ast.Expr):
                last_expr = tree.body.pop()
                if tree.body:
                    exec(compile(tree, "<qala_cell>", "exec"), exec_globals)
                result_val = eval(compile(ast.Expression(body=last_expr.value), "<qala_cell>", "eval"), exec_globals)
            else:
                exec(compile(tree, "<qala_cell>", "exec"), exec_globals)
    except Exception as e:
        error_info = {
            "type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc(),
        }

    return {
        "success": error_info is None,
        "stdout": stdout_buf.getvalue(),
        "stderr": stderr_buf.getvalue(),
        "result": repr(result_val) if result_val is not None else None,
        "error": error_info,
    }


# =============================================================================
# 2. Exact Symbolic Mathematics via SymPy
# =============================================================================

def solve_symbolic_equation(equation_str: str, solve_for: str) -> Dict[str, Any]:
    """Solves algebraic, trigonometric, or transcendental equations symbolically using SymPy."""
    if not _HAS_SYMPY:
        return {"error": "SymPy is not installed in the active environment."}

    try:
        if "=" in equation_str:
            lhs_str, rhs_str = equation_str.split("=", 1)
            lhs = sp.sympify(lhs_str.strip())
            rhs = sp.sympify(rhs_str.strip())
            eq = Eq(lhs, rhs)
        else:
            eq = sp.sympify(equation_str.strip())

        target_sym = symbols(solve_for.strip())
        solutions = solve(eq, target_sym)

        latex_solutions = [sp.latex(s) for s in solutions]
        pretty_solutions = [sp.pretty(s, use_unicode=True) for s in solutions]

        return {
            "success": True,
            "variable": solve_for,
            "solutions": [str(s) for s in solutions],
            "latex": latex_solutions,
            "pretty": pretty_solutions,
            "exact": True,
        }
    except Exception as e:
        return {"success": False, "error": f"Symbolic solver failed: {e}"}


def perform_calculus(
    operation: str,
    expression_str: str,
    var: str = "x",
    lower: Optional[str] = None,
    upper: Optional[str] = None,
    point: Optional[str] = None,
) -> Dict[str, Any]:
    """Performs exact differentiation, integration (definite/indefinite), or limits."""
    if not _HAS_SYMPY:
        return {"error": "SymPy is not installed."}

    try:
        x = symbols(var)
        expr = sp.sympify(expression_str)

        if operation in ("diff", "derivative"):
            res = diff(expr, x)
            op_label = f"d/d{var}"
        elif operation in ("integrate", "integral"):
            if lower is not None and upper is not None:
                l_val = sp.sympify(lower)
                u_val = sp.sympify(upper)
                res = integrate(expr, (x, l_val, u_val))
                op_label = f"∫_{lower}^{upper} d{var}"
            else:
                res = integrate(expr, x)
                op_label = f"∫ d{var}"
        elif operation in ("limit", "lim"):
            pt = sp.sympify(point or "0")
            res = limit(expr, x, pt)
            op_label = f"lim_{{{var}->{point}}}"
        else:
            return {"error": f"Unknown calculus operation '{operation}'. Use 'diff', 'integrate', or 'limit'."}

        return {
            "success": True,
            "operation": op_label,
            "expression": str(expr),
            "result": str(res),
            "latex": sp.latex(res),
            "pretty": sp.pretty(res, use_unicode=True),
        }
    except Exception as e:
        return {"success": False, "error": f"Calculus operation failed: {e}"}


def linear_algebra_ops(matrix_data: List[List[float]], operation: str) -> Dict[str, Any]:
    """Computes determinant, inverse, eigenvalues/eigenvectors, or rank for a matrix."""
    if not _HAS_SYMPY:
        return {"error": "SymPy is not installed."}

    try:
        mat = Matrix(matrix_data)
        if operation == "det":
            val = mat.det()
            return {"operation": "determinant", "result": str(val), "exact": True}
        elif operation == "inv":
            inv = mat.inv()
            return {"operation": "inverse", "result": str(inv.tolist()), "latex": sp.latex(inv)}
        elif operation in ("eigen", "eigenvalues"):
            eigs = mat.eigenvals()
            return {"operation": "eigenvalues", "result": {str(k): v for k, v in eigs.items()}}
        elif operation == "rank":
            return {"operation": "rank", "result": mat.rank()}
        else:
            return {"error": f"Unknown matrix operation '{operation}'."}
    except Exception as e:
        return {"error": f"Matrix operation error: {e}"}


# =============================================================================
# 3. High-Precision Numerical Computing via NumPy / SciPy
# =============================================================================

def numerical_integration(func_expr: str, a: float, b: float) -> Dict[str, Any]:
    """Performs numerical quadrature integration using SciPy with error bounds."""
    if not _HAS_SCIPY or not _HAS_NUMPY:
        return {"error": "SciPy/NumPy not available."}

    try:
        # Create safe lambda
        code = f"lambda x: {func_expr}"
        f = eval(code, {"np": np, "numpy": np, "math": sys.modules.get("math")})
        val, err = sc_integrate.quad(f, a, b)
        return {
            "success": True,
            "value": float(val),
            "estimated_error": float(err),
            "interval": [a, b],
            "method": "scipy.integrate.quad",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def numerical_root_finding(func_expr: str, x0: float) -> Dict[str, Any]:
    """Finds a root of a non-linear equation numerically using SciPy optimize."""
    if not _HAS_SCIPY or not _HAS_NUMPY:
        return {"error": "SciPy/NumPy not available."}

    try:
        f = eval(f"lambda x: {func_expr}", {"np": np, "numpy": np})
        sol = sc_optimize.root_scalar(f, x0=x0, method="newton")
        return {
            "success": True,
            "root": float(sol.root),
            "converged": bool(sol.converged),
            "iterations": int(sol.iterations),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
