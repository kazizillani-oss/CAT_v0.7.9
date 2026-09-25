"""
CCT — project_stats.py: pure functions computing the real, live
numbers the v0.7.2 roadmap's "Project & Workspace Dashboard" section
asks for. No Textual here — ui/dashboard.py renders what this returns.

Every function is capped/bounded and wrapped so a huge or unusual
workspace (a node_modules-sized folder, a symlink loop, a permission-
denied subdirectory) degrades to a partial/best-effort answer instead
of hanging the UI thread — these run synchronously on a call from
ui/dashboard.py's refresh, not in a worker, so a slow scan would
directly freeze the app.

Honest gaps, not fabricated: CPU% and a real "Workspace Health" score
need either `psutil` or continuous sampling this app doesn't do
anywhere else; rather than invent a number, cpu_percent() reports
`None` (not "0%") when it can't measure something real, and
callers show that as "unavailable" instead of a fake reading. Same
for "Indexed Status" — this codebase has no separate file index (the
Explorer's DirectoryTree reads the filesystem directly), so there's
nothing genuine to report; ui/dashboard.py says so rather than
displaying a made-up percentage.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import os
import time

_IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache",
    ".pytest_cache", "dist", "build", ".idea", ".vscode", "tmp", "temp",
    "bin", "obj", ".next", ".nuxt", "coverage", ".cache", ".cct", ".gradle"
}
_LANG_BY_EXT = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".ts": "TypeScript",
    ".tsx": "TypeScript", ".java": "Java", ".c": "C", ".h": "C", ".cpp": "C++",
    ".hpp": "C++", ".cs": "C#", ".go": "Go", ".rs": "Rust", ".rb": "Ruby",
    ".php": "PHP", ".swift": "Swift", ".kt": "Kotlin", ".html": "HTML",
    ".css": "CSS", ".scss": "SCSS", ".json": "JSON", ".yaml": "YAML",
    ".yml": "YAML", ".md": "Markdown", ".sh": "Shell", ".sql": "SQL",
    ".r": "R", ".lua": "Lua", ".dart": "Dart",
}
MAX_SCAN_FILES = 3000  # bounded scan so huge workspaces or cloud drives cannot hang the UI thread
_SCAN_CACHE = {}
_SCAN_TTL = 5.0  # seconds


def scan_workspace(root):
    """One bounded os.walk pass computing size/file-count/language
    histogram/last-modified together, since walking the same tree three
    separate times for three separate stats would be pure waste.
    Results are cached in memory with a short TTL to prevent UI freezes.
    Returns a dict; every count is `None` if `root` isn't a real,
    readable directory rather than a misleading 0."""
    if not root or not os.path.isdir(root):
        return {"total_size": None, "total_files": None, "languages": {},
                "last_modified": None, "truncated": False}

    norm = os.path.normcase(os.path.abspath(root))
    now = time.time()
    cached = _SCAN_CACHE.get(norm)
    if cached and (now - cached[0] < _SCAN_TTL):
        return dict(cached[1])

    total_size = 0
    total_files = 0
    languages = {}
    last_modified = 0.0
    truncated = False
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _IGNORE_DIRS and not d.startswith(".")]
        for name in filenames:
            if total_files >= MAX_SCAN_FILES:
                truncated = True
                break
            path = os.path.join(dirpath, name)
            try:
                st = os.stat(path)
            except OSError:
                continue
            total_size += st.st_size
            total_files += 1
            last_modified = max(last_modified, st.st_mtime)
            ext = os.path.splitext(name)[1].lower()
            lang = _LANG_BY_EXT.get(ext)
            if lang:
                languages[lang] = languages.get(lang, 0) + 1
        if truncated:
            break
    result = {
        "total_size": total_size, "total_files": total_files,
        "languages": dict(sorted(languages.items(), key=lambda kv: -kv[1])[:5]),
        "last_modified": last_modified or None, "truncated": truncated,
    }
    _SCAN_CACHE[norm] = (now, result)
    return result


def human_size(n):
    if n is None:
        return "\u2014"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def human_age(epoch):
    if not epoch:
        return "\u2014"
    delta = time.time() - epoch
    if delta < 60:
        return "just now"
    if delta < 3600:
        return f"{int(delta // 60)}m ago"
    if delta < 86400:
        return f"{int(delta // 3600)}h ago"
    return f"{int(delta // 86400)}d ago"


_GIT_CACHE = {}
_GIT_TTL = 5.0


def git_branch(root):
    """Reads .git/HEAD directly rather than shelling out to `git` — no
    subprocess dependency, and it's the one file that answers "what
    branch" without needing a full git status walk. Returns None if
    `root` isn't a git repo at all (distinct from "detached HEAD",
    which returns the short commit hash instead of a branch name)."""
    if not root:
        return None
    norm = os.path.normcase(os.path.abspath(root))
    now = time.time()
    cached = _GIT_CACHE.get(norm)
    if cached and (now - cached[0] < _GIT_TTL):
        return cached[1]

    head_path = os.path.join(root, ".git", "HEAD")
    try:
        with open(head_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
    except OSError:
        _GIT_CACHE[norm] = (now, None)
        return None
    if content.startswith("ref:"):
        branch = content.split("/")[-1]
    else:
        branch = content[:8]  # detached HEAD: short commit hash
    _GIT_CACHE[norm] = (now, branch)
    return branch


_DEP_FILES = ("requirements.txt", "package.json", "pyproject.toml", "Pipfile")
_DEP_CACHE = {}
_DEP_TTL = 10.0


def dependencies(root):
    """Best-effort dependency list from whichever manifest exists —
    real names read from the actual file, not a fabricated guess.
    package.json is parsed as JSON; the others are read as plain lines/
    TOML-ish text with a conservative regex rather than pulling in a
    TOML parser dependency for one dashboard field. Capped at 12 names
    total so a monorepo's 300-package lockfile doesn't blow out the
    dashboard layout."""
    if not root:
        return []
    norm = os.path.normcase(os.path.abspath(root))
    now = time.time()
    cached = _DEP_CACHE.get(norm)
    if cached and (now - cached[0] < _DEP_TTL):
        return list(cached[1])
    names = []
    req = os.path.join(root, "requirements.txt")
    if os.path.isfile(req):
        try:
            with open(req, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        import re
                        m = re.match(r"^([A-Za-z0-9_.\-]+)", line)
                        if m:
                            names.append(m.group(1))
        except OSError:
            pass
    pkg = os.path.join(root, "package.json")
    if os.path.isfile(pkg):
        try:
            import json
            with open(pkg, "r", encoding="utf-8") as f:
                data = json.load(f)
            names.extend(list(data.get("dependencies", {}).keys()))
            names.extend(list(data.get("devDependencies", {}).keys()))
        except Exception:
            pass
    pyproject = os.path.join(root, "pyproject.toml")
    if os.path.isfile(pyproject):
        try:
            import re
            with open(pyproject, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            for m in re.finditer(r'^\s*"?([A-Za-z0-9_.\-]+)"?\s*=', text, re.MULTILINE):
                if m.group(1).lower() not in ("name", "version", "description",
                                               "authors", "readme", "requires-python"):
                    names.append(m.group(1))
        except OSError:
            pass
    seen, out = set(), []
    for n in names:
        if n.lower() not in seen:
            seen.add(n.lower())
            out.append(n)
        if len(out) >= 12:
            break
    return out


def memory_usage_mb():
    """Real resident-memory reading for THIS process, via stdlib
    `resource` on POSIX (no psutil dependency needed for this one
    number). Returns None on platforms where `resource` doesn't exist
    (Windows) rather than faking a number — see module docstring."""
    try:
        import resource
        rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # macOS reports bytes, Linux reports KB — ru_maxrss's unit is
        # platform-specific by design in the POSIX API itself.
        import sys as _sys
        if _sys.platform == "darwin":
            return rss_kb / (1024 * 1024)
        return rss_kb / 1024
    except Exception:
        return None


def cpu_percent():
    """No portable, dependency-free way to sample process CPU% without
    either `psutil` or maintaining our own two-sample delta over time
    (which nothing in this app currently does) — returns None rather
    than a fabricated number. See module docstring."""
    return None
