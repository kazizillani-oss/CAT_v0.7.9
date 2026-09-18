"""
CAT Project Graph & Workspace Intelligence per §13:
- Module dependency graph, symbol definitions, call hierarchies, external imports, test mappings
- AST-based parsing for Python source files
- Incrementally updated symbol and dependency index
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class SymbolInfo:
    name: str
    kind: str  # function, class, method, variable, import
    file_path: str
    line_number: int
    docstring: Optional[str] = None
    parameters: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "docstring": self.docstring,
            "parameters": self.parameters,
        }


@dataclass
class FileNode:
    file_path: str
    symbols: List[SymbolInfo] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    imported_by: List[str] = field(default_factory=list)
    is_test_file: bool = False
    associated_sources: List[str] = field(default_factory=list)


class ProjectGraph:
    """Incrementally updated semantic graph of project codebase."""

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = os.path.abspath(workspace_root or os.getcwd())
        self.files: Dict[str, FileNode] = {}
        self.symbol_index: Dict[str, List[SymbolInfo]] = {}

    def scan_directory(self, root_dir: Optional[str] = None, max_files: int = 500):
        """Scan workspace and construct symbol and dependency graph."""
        scan_root = os.path.abspath(root_dir or self.workspace_root)
        count = 0
        for dirpath, dirnames, filenames in os.walk(scan_root):
            # Skip hidden and cache dirs
            dirnames[:] = [d for d in dirnames if not d.startswith((".", "__pycache__", "node_modules", "venv", ".venv"))]
            for fname in filenames:
                if fname.endswith(".py"):
                    full_path = os.path.join(dirpath, fname)
                    self.index_file(full_path)
                    count += 1
                    if count >= max_files:
                        break
            if count >= max_files:
                break
        self._resolve_dependencies()

    def index_file(self, file_path: str):
        """Parse file via AST and extract symbols and imports."""
        norm_path = os.path.normpath(file_path)
        rel_path = os.path.relpath(norm_path, self.workspace_root) if norm_path.startswith(self.workspace_root) else norm_path
        is_test = "test" in os.path.basename(norm_path).lower()

        node = FileNode(file_path=norm_path, is_test_file=is_test)
        try:
            with open(norm_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            tree = ast.parse(content, filename=norm_path)
        except Exception:
            self.files[norm_path] = node
            return

        for stmt in ast.walk(tree):
            if isinstance(stmt, ast.FunctionDef) or isinstance(stmt, ast.AsyncFunctionDef):
                params = [a.arg for a in stmt.args.args]
                doc = ast.get_docstring(stmt)
                sym = SymbolInfo(
                    name=stmt.name,
                    kind="function",
                    file_path=norm_path,
                    line_number=stmt.lineno,
                    docstring=doc,
                    parameters=params,
                )
                node.symbols.append(sym)
                self.symbol_index.setdefault(sym.name, []).append(sym)
            elif isinstance(stmt, ast.ClassDef):
                doc = ast.get_docstring(stmt)
                sym = SymbolInfo(
                    name=stmt.name,
                    kind="class",
                    file_path=norm_path,
                    line_number=stmt.lineno,
                    docstring=doc,
                )
                node.symbols.append(sym)
                self.symbol_index.setdefault(sym.name, []).append(sym)
            elif isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    node.imports.append(alias.name)
            elif isinstance(stmt, ast.ImportFrom):
                if stmt.module:
                    node.imports.append(stmt.module)

        self.files[norm_path] = node

    def _resolve_dependencies(self):
        """Cross-reference imports to determine internal file dependencies."""
        for path, node in self.files.items():
            for imp in node.imports:
                for target_path in self.files.keys():
                    # Check if imported module matches target file path
                    mod_name = os.path.splitext(os.path.basename(target_path))[0]
                    if imp.endswith(mod_name) and target_path != path:
                        if path not in self.files[target_path].imported_by:
                            self.files[target_path].imported_by.append(path)
                        if node.is_test_file and target_path not in node.associated_sources:
                            node.associated_sources.append(target_path)

    def find_symbols(self, name_query: str) -> List[SymbolInfo]:
        """Find symbols matching name query."""
        results = []
        q = name_query.lower()
        for sym_name, syms in self.symbol_index.items():
            if q in sym_name.lower():
                results.extend(syms)
        return results

    def get_file_dependencies(self, file_path: str) -> List[str]:
        norm = os.path.normpath(file_path)
        node = self.files.get(norm)
        return node.imports if node else []

    def get_file_dependents(self, file_path: str) -> List[str]:
        norm = os.path.normpath(file_path)
        node = self.files.get(norm)
        return node.imported_by if node else []

    def get_test_files_for_source(self, source_path: str) -> List[str]:
        norm = os.path.normpath(source_path)
        base = os.path.splitext(os.path.basename(norm))[0]
        matching_tests = []
        for path, node in self.files.items():
            if node.is_test_file:
                test_base = os.path.basename(path).lower()
                if base.lower() in test_base or norm in node.associated_sources:
                    matching_tests.append(path)
        return matching_tests

    def summarize(self) -> Dict[str, Any]:
        return {
            "total_files_indexed": len(self.files),
            "total_symbols": sum(len(s) for s in self.symbol_index.values()),
            "test_files_count": sum(1 for n in self.files.values() if n.is_test_file),
        }


project_graph = ProjectGraph()
