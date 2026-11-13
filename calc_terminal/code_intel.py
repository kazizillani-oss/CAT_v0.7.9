"""
CAT Code Intelligence Engine (v0.7.9 Complete Platform Expansion)

AST-based indexing, cross-file symbol lookup, dependency graphs,
project architecture summaries, semantic code search, and dead code detection.
"""

import os
import ast
import re
from typing import Dict, List, Any, Optional, Set

class CodeIntelEngine:
    """AST-powered project inspection and symbol analysis."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._index_cache: Dict[str, Any] = {}
            cls._instance._last_indexed_root: Optional[str] = None
        return cls._instance

    def index_workspace(self, root_dir: str, max_files: int = 1000) -> Dict[str, Any]:
        """Index all Python and key source files in the workspace using AST."""
        if not os.path.isdir(root_dir):
            return {"error": f"Invalid directory: {root_dir}", "files": {}}

        files_map = {}
        all_symbols = {}
        all_imports = {}
        total_lines = 0

        ignore_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules", "dist", "build", ".cat_browser_cache"}

        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".venv")]
            for file in files:
                if len(files_map) >= max_files:
                    break
                if file.endswith((".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".yaml", ".yml", ".md")):
                    fpath = os.path.join(root, file)
                    rel_path = os.path.relpath(fpath, root_dir).replace("\\", "/")
                    try:
                        sz = os.path.getsize(fpath)
                        if sz > 1_000_000:  # skip files > 1MB
                            continue
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        lines = len(content.splitlines())
                        total_lines += lines

                        file_info = {
                            "path": rel_path,
                            "size": sz,
                            "lines": lines,
                            "classes": [],
                            "functions": [],
                            "imports": [],
                        }

                        if file.endswith(".py"):
                            self._extract_python_ast(content, file_info, all_symbols, rel_path)

                        files_map[rel_path] = file_info
                        all_imports[rel_path] = file_info.get("imports", [])
                    except Exception:
                        continue

        index_data = {
            "root_dir": root_dir,
            "total_files": len(files_map),
            "total_lines": total_lines,
            "files": files_map,
            "symbols": all_symbols,
            "imports": all_imports,
        }
        self._index_cache = index_data
        self._last_indexed_root = root_dir
        return index_data

    def _extract_python_ast(self, content: str, file_info: Dict[str, Any], all_symbols: Dict[str, Any], rel_path: str):
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    c_info = {
                        "name": node.name,
                        "line": node.lineno,
                        "doc": ast.get_docstring(node) or "",
                        "methods": [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))],
                        "file": rel_path
                    }
                    file_info["classes"].append(c_info)
                    all_symbols[node.name] = {"type": "class", "file": rel_path, "line": node.lineno}
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    f_info = {
                        "name": node.name,
                        "line": node.lineno,
                        "doc": ast.get_docstring(node) or "",
                        "async": isinstance(node, ast.AsyncFunctionDef),
                        "file": rel_path
                    }
                    file_info["functions"].append(f_info)
                    if node.name not in all_symbols:
                        all_symbols[node.name] = {"type": "function", "file": rel_path, "line": node.lineno}
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        file_info["imports"].append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    for alias in node.names:
                        file_info["imports"].append(f"{mod}.{alias.name}" if mod else alias.name)
        except Exception:
            pass

    def find_symbol(self, name: str, root_dir: Optional[str] = None) -> List[Dict[str, Any]]:
        """Look up symbols (classes, functions, methods) across the workspace."""
        if not self._index_cache or (root_dir and self._last_indexed_root != root_dir):
            if root_dir:
                self.index_workspace(root_dir)

        symbols = self._index_cache.get("symbols", {})
        matches = []
        q = name.lower().strip()
        for sym_name, sym_meta in symbols.items():
            if q in sym_name.lower():
                matches.append({
                    "name": sym_name,
                    "type": sym_meta.get("type"),
                    "file": sym_meta.get("file"),
                    "line": sym_meta.get("line")
                })
        return matches

    def get_dependency_graph(self, root_dir: Optional[str] = None) -> Dict[str, List[str]]:
        """Build file dependency import graph."""
        if not self._index_cache or (root_dir and self._last_indexed_root != root_dir):
            if root_dir:
                self.index_workspace(root_dir)
        return self._index_cache.get("imports", {})

    def get_project_summary(self, root_dir: str) -> Dict[str, Any]:
        """Generate high-level architectural summary of project."""
        idx = self.index_workspace(root_dir)
        files = idx.get("files", {})
        ext_counts: Dict[str, int] = {}
        for path in files:
            ext = os.path.splitext(path)[1] or "no_ext"
            ext_counts[ext] = ext_counts.get(ext, 0) + 1

        all_classes = sum(len(f.get("classes", [])) for f in files.values())
        all_funcs = sum(len(f.get("functions", [])) for f in files.values())

        return {
            "root_dir": root_dir,
            "total_files": idx.get("total_files", 0),
            "total_lines": idx.get("total_lines", 0),
            "file_types": ext_counts,
            "total_classes": all_classes,
            "total_functions": all_funcs,
            "key_modules": [p for p in files if "/" not in p and p.endswith(".py")][:10],
        }

    def search_code(self, query: str, root_dir: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Fast regex/substring code search across workspace files."""
        results = []
        ignore_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules", "dist", "build"}
        pattern = re.compile(re.escape(query), re.IGNORECASE)

        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".venv")]
            for file in files:
                if len(results) >= max_results:
                    break
                if file.endswith((".py", ".js", ".ts", ".html", ".css", ".json", ".md", ".yaml", ".toml")):
                    fpath = os.path.join(root, file)
                    rel = os.path.relpath(fpath, root_dir).replace("\\", "/")
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            for lineno, line in enumerate(f, 1):
                                if pattern.search(line):
                                    results.append({
                                        "file": rel,
                                        "line": lineno,
                                        "text": line.strip()[:140]
                                    })
                                    if len(results) >= max_results:
                                        break
                    except Exception:
                        continue
        return results

    def detect_dead_code(self, root_dir: str) -> Dict[str, Any]:
        """Detect potentially unused internal functions or imports."""
        idx = self.index_workspace(root_dir)
        files = idx.get("files", {})
        defined_funcs = {}
        for rel_path, finfo in files.items():
            for f in finfo.get("functions", []):
                fn = f["name"]
                if not fn.startswith("_"):  # public functions
                    defined_funcs[fn] = {"file": rel_path, "line": f["line"]}

        # Count occurrences in all files
        usage_counts: Dict[str, int] = {fn: 0 for fn in defined_funcs}
        for rel_path, finfo in files.items():
            fpath = os.path.join(root_dir, rel_path)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                for fn in defined_funcs:
                    if fn in content:
                        usage_counts[fn] += 1
            except Exception:
                continue

        # If usage count == 1, it's only mentioned where it's defined
        unused = [
            {"function": fn, "file": meta["file"], "line": meta["line"]}
            for fn, meta in defined_funcs.items()
            if usage_counts.get(fn, 0) <= 1
        ]

        return {
            "total_analyzed_functions": len(defined_funcs),
            "potentially_unused_count": len(unused),
            "candidates": unused[:25]
        }

    def analyze_change_impact(self, filepath: str, root_dir: str) -> Dict[str, Any]:
        """Analyze which files might be affected by changing the given file."""
        idx = self.index_workspace(root_dir)
        imports = idx.get("imports", {})
        rel = os.path.relpath(filepath, root_dir).replace("\\", "/")
        mod_name = os.path.splitext(os.path.basename(rel))[0]

        dependents = []
        for file, file_imports in imports.items():
            if file == rel:
                continue
            for imp in file_imports:
                if mod_name in imp or rel in imp:
                    dependents.append(file)
                    break

        return {
            "target_file": rel,
            "module_name": mod_name,
            "directly_dependent_files": dependents,
            "impact_level": "HIGH" if len(dependents) > 5 else "MEDIUM" if dependents else "LOW"
        }


# Global singleton
code_intel = CodeIntelEngine()

def get_code_intel() -> CodeIntelEngine:
    return code_intel

