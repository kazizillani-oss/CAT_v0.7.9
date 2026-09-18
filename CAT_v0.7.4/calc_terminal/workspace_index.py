"""
CCT — workspace_index.py: AI Workspace Understanding (v0.7.7 Workspace
Management Preview, spec section 6).

Whenever the workspace changes, CCT indexes it: scans the file tree,
reads the README and configuration files, detects the programming
language(s) and package managers, understands dependencies, and builds
a compact project context the AI (and the header) can use.

The scan is honest and bounded:

  - Never follows .git / node_modules / venv / __pycache__ / dist /
    build (the classic noise folders);
  - file/dir counts are capped; the structure sample is capped;
  - dependency parsing reads real manifests (requirements.txt,
    package.json, Cargo.toml, go.mod, pyproject.toml) and takes the
    top-level names only;
  - every failure degrades to "unknown/empty" — no fabricated data.

Progress is reported through an optional `on_progress(stage,
message)` callback with the spec's exact stages:
    "scanning" -> "Reading Files..." -> "building" -> "ready".
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import os

PROGRESS_STAGES = ("scanning", "reading", "building", "ready")

STAGE_LABELS = {
    "scanning": "\U0001f50d Scanning Workspace...",
    "reading": "\U0001f4d6 Reading Files...",
    "building": "\U0001f9f1 Building Context...",
    "ready": "\u2705 Ready",
}

_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", ".idea", ".vscode", ".tox", ".mypy_cache",
    ".pytest_cache", "target", "bin", "obj", ".next", "out",
}

_LANGUAGE_BY_EXT = {
    ".py": "Python", ".pyw": "Python", ".ipynb": "Python",
    ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".html": "HTML", ".css": "CSS", ".scss": "SCSS", ".sass": "Sass",
    ".json": "JSON", ".yaml": "YAML", ".yml": "YAML", ".toml": "TOML",
    ".xml": "XML", ".md": "Markdown", ".rst": "reStructuredText",
    ".c": "C", ".h": "C", ".cpp": "C++", ".cc": "C++", ".hpp": "C++",
    ".cs": "C#", ".java": "Java", ".kt": "Kotlin", ".kts": "Kotlin",
    ".go": "Go", ".rs": "Rust", ".rb": "Ruby", ".php": "PHP",
    ".swift": "Swift", ".m": "Objective-C", ".scala": "Scala",
    ".sh": "Shell", ".bat": "Batch", ".ps1": "PowerShell",
    ".sql": "SQL", ".r": "R", ".lua": "Lua", ".pl": "Perl",
    ".dart": "Dart", ".vue": "Vue", ".svelte": "Svelte",
    ".ex": "Elixir", ".exs": "Elixir", ".erl": "Erlang",
    ".hs": "Haskell", ".clj": "Clojure", ".zig": "Zig",
}

# Top-level manifest files that reveal package managers / deps.
_CONFIG_FILES = {
    "pyproject.toml": "pyproject.toml (PEP 621)",
    "requirements.txt": "requirements.txt",
    "setup.py": "setup.py",
    "setup.cfg": "setup.cfg",
    "Pipfile": "Pipfile",
    "poetry.lock": "poetry.lock",
    "uv.lock": "uv.lock",
    "package.json": "package.json",
    "package-lock.json": "package-lock.json",
    "pnpm-lock.yaml": "pnpm-lock.yaml",
    "yarn.lock": "yarn.lock",
    "Cargo.toml": "Cargo.toml",
    "go.mod": "go.mod",
    "composer.json": "composer.json",
    "Gemfile": "Gemfile",
    "build.gradle": "build.gradle",
    "pom.xml": "pom.xml",
    "Dockerfile": "Dockerfile",
    "docker-compose.yml": "docker-compose.yml",
    "Makefile": "Makefile",
    ".env.example": ".env.example",
    ".editorconfig": ".editorconfig",
    "tsconfig.json": "tsconfig.json",
    ".eslintrc": ".eslintrc",
    "vite.config.js": "vite.config.js",
    "vite.config.ts": "vite.config.ts",
}

_README_NAMES = ("README.md", "README", "Readme.md", "readme.md",
                 "README.txt", "README.rst")

_MAX_SCAN_FILES = 20000
_MAX_DEPENDENCIES = 40
_MAX_STRUCTURE = 40
_MAX_README_CHARS = 2000


def _scan(path, on_progress=None):
    """Walks the tree once, collecting counts, extension histogram,
    top-level structure, config files, and readmes."""
    file_count = 0
    dir_count = 0
    total_size = 0
    ext_counts = {}
    structure = []
    configs = []
    readme_path = None
    root = path
    for base, dirs, files in os.walk(path):
        dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS)
        rel = os.path.relpath(base, root)
        if rel != ".":
            dir_count += 1
        if rel != "." and len(structure) < _MAX_STRUCTURE:
            structure.append({"type": "dir", "path": rel})
        for name in sorted(files):
            full = os.path.join(base, name)
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            total_size += size
            file_count += 1
            ext = os.path.splitext(name)[1].lower()
            ext_counts[ext] = ext_counts.get(ext, 0) + 1
            if file_count > _MAX_SCAN_FILES:
                return None
            rel_name = name if rel == "." else os.path.join(rel, name)
            if rel == "." and name in _CONFIG_FILES:
                configs.append(name)
            if len(structure) < _MAX_STRUCTURE and rel == "." and name:
                structure.append({"type": "file", "path": name})
            if readme_path is None and name in _README_NAMES:
                readme_path = full
    return {
        "file_count": file_count,
        "dir_count": dir_count,
        "total_size": total_size,
        "ext_counts": ext_counts,
        "structure": structure,
        "configs": sorted(set(configs)),
        "readme_path": readme_path,
    }


def _languages(ext_counts):
    by_lang = {}
    for ext, count in ext_counts.items():
        lang = _LANGUAGE_BY_EXT.get(ext)
        if lang:
            by_lang[lang] = by_lang.get(lang, 0) + count
    ordered = sorted(by_lang.items(), key=lambda kv: -kv[1])
    return [lang for lang, _n in ordered[:6]]


def _read_readme(readme_path):
    if not readme_path:
        return None
    try:
        with open(readme_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read(200000)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        summary_lines = []
        for ln in lines:
            if ln.startswith("#"):
                continue
            if ln.startswith("```"):
                break
            summary_lines.append(ln)
            if len(summary_lines) >= 6:
                break
        snippet = " \u00b7 ".join(summary_lines)
        return snippet[:_MAX_README_CHARS] if snippet else None
    except Exception:
        return None


def _dependencies(path):
    """Top-level dependency names from real manifests. Capped, honest:
    only names that can actually be parsed are listed."""
    deps = []

    def _reqs(full):
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.split("#")[0].strip()
                    if not line:
                        continue
                    name = line.split("==")[0].split(">=")[0].split("<")[0] \
                        .split("[")[0].strip().replace("_", "-")
                    if name and name not in deps:
                        deps.append(name)
        except Exception:
            pass

    def _json(full, keys):
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                import json
                data = json.load(f)
            for key in keys:
                block = data.get(key) or {}
                if isinstance(block, dict):
                    for name in block:
                        if name and name not in deps:
                            deps.append(name)
        except Exception:
            pass

    _METADATA_KEYS = {
        "name", "version", "description", "requires-python",
        "authors", "maintainers", "license", "readme", "homepage",
        "repository", "keywords", "classifiers", "dependencies",
        "optional-dependencies", "url", "author", "license-file",
        "documentation", "issues", "changelog", "build-backend",
        "requires", "build-system", "module", "bin", "edition",
        "rust-version", "publish", "go", "toolchain",
    }

    def _kv(full):
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("[") or not line or "=" not in line:
                        continue
                    key = line.split("=")[0].strip().strip('"')
                    if not key or key in _METADATA_KEYS or key.startswith("."):
                        continue
                    if key not in deps:
                        deps.append(key)
        except Exception:
            pass

    for name, full in (("requirements.txt", None), ("pyproject.toml", None)):
        p = os.path.join(path, name)
        if os.path.isfile(p):
            _reqs(p) if name == "requirements.txt" else _kv(p)
    pkg = os.path.join(path, "package.json")
    if os.path.isfile(pkg):
        _json(pkg, ("dependencies", "devDependencies", "peerDependencies"))
    go_mod = os.path.join(path, "go.mod")
    if os.path.isfile(go_mod):
        _kv(go_mod)
    cargo = os.path.join(path, "Cargo.toml")
    if os.path.isfile(cargo):
        _kv(cargo)
    return deps[:_MAX_DEPENDENCIES]


def _package_managers(path):
    found = []
    names = set(os.listdir(path)) if os.path.isdir(path) else set()
    if "requirements.txt" in names or "pyproject.toml" in names or "setup.py" in names:
        found.append("pip")
    if "Pipfile" in names or "poetry.lock" in names:
        found.append("poetry")
    if "uv.lock" in names:
        found.append("uv")
    if "package.json" in names or "yarn.lock" in names or "pnpm-lock.yaml" in names:
        found.append("npm")
    if "Cargo.toml" in names or "Cargo.lock" in names:
        found.append("cargo")
    if "go.mod" in names:
        found.append("go")
    if "composer.json" in names:
        found.append("composer")
    if "Gemfile" in names:
        found.append("bundler")
    if "pom.xml" in names or "build.gradle" in names:
        found.append("maven")
    return found


def index_project(path, on_progress=None):
    """Builds the project context for `path` (spec section 6). Returns
    a dict with keys: languages, file_count, dir_count, structure,
    configs, readme, package_managers, dependencies, git, description.
    `on_progress(stage, message)` fires once per stage in order:
    scanning -> reading -> building -> ready. Never raises for
    filesystem problems — a broken path yields an honest minimal
    context."""
    import time

    def _progress(stage):
        if on_progress:
            try:
                on_progress(stage, STAGE_LABELS[stage])
            except Exception:
                pass

    ctx = {"path": os.path.abspath(path), "ok": False,
           "languages": [], "file_count": 0, "dir_count": 0,
           "structure": [], "configs": [], "readme": None,
           "package_managers": [], "dependencies": [],
           "git": None, "description": "", "elapsed": 0.0}
    if not os.path.isdir(path):
        return ctx
    _progress("scanning")
    t0 = time.time()
    scan = _scan(path, on_progress)
    if scan is None:
        scan = {"file_count": 0, "dir_count": 0, "total_size": 0,
                "ext_counts": {}, "structure": [], "configs": [],
                "readme_path": None}
    _progress("reading")
    readme = _read_readme(scan["readme_path"])
    _progress("building")
    from . import workspace as ws
    branch = ws.git_branch(path)
    git_status = ws.git_status_summary(path)
    ctx.update({
        "ok": True,
        "languages": _languages(scan["ext_counts"]),
        "file_count": scan["file_count"],
        "dir_count": scan["dir_count"],
        "total_size": scan["total_size"],
        "structure": [s["path"] for s in scan["structure"]],
        "configs": scan["configs"],
        "readme": readme,
        "package_managers": _package_managers(path),
        "dependencies": _dependencies(path),
        "git": {"branch": branch, "status": git_status},
        "elapsed": round(time.time() - t0, 2),
    })
    _progress("ready")
    return ctx


def describe(ctx):
    """One-line human description of an indexed project, for the
    header and the 'Ready' summary."""
    if not ctx or not ctx.get("ok"):
        return "Workspace not indexed"
    langs = ", ".join(ctx["languages"][:3]) if ctx["languages"] else "unknown"
    deps = len(ctx["dependencies"])
    files = ctx["file_count"]
    branch = (ctx.get("git") or {}).get("branch")
    bits = [f"{langs} \u00b7 {files} files"]
    if deps:
        bits.append(f"{deps} dependencies")
    if branch:
        bits.append(f"\U0001f33f {branch}")
    return " \u00b7 ".join(bits)


def summarize_context(ctx):
    """A compact markdown block the AI/chat can show after indexing
    (spec section 6's 'Ready' state, with real content)."""
    if not ctx or not ctx.get("ok"):
        return ("*\u26a0 Couldn't index this workspace (missing or unreadable folder). "
                "The AI will work without project context.*")
    lines = ["\U0001f4c2 **Project Context** \u2014 ready", ""]
    lines.append(f"- **Files**: {ctx['file_count']} files, {ctx['dir_count']} folders")
    if ctx["languages"]:
        lines.append("- **Languages**: " + ", ".join(ctx["languages"]))
    if ctx["package_managers"]:
        lines.append("- **Package managers**: " + ", ".join(ctx["package_managers"]))
    if ctx["dependencies"]:
        deps = ", ".join(ctx["dependencies"][:12])
        more = f" (+{len(ctx['dependencies']) - 12} more)" if len(ctx["dependencies"]) > 12 else ""
        lines.append(f"- **Dependencies**: {deps}{more}")
    if ctx["configs"]:
        lines.append("- **Config files**: " + ", ".join(ctx["configs"][:8]))
    if ctx["readme"]:
        lines.append(f"- **README**: {ctx['readme']}")
    git = ctx.get("git") or {}
    if git.get("branch"):
        lines.append(f"- **Git**: branch `{git['branch']}`")
        st = git.get("status")
        if st:
            summary = f"{st['changed']} modified, {st['added']} added, {st['deleted']} deleted"
            lines.append(f"- **Git status**: {summary}")
    if ctx["structure"]:
        top = ", ".join(ctx["structure"][:12])
        lines.append(f"- **Structure**: {top}")
    lines.append(f"- **Indexed in**: {ctx['elapsed']}s")
    return "\n".join(lines)
