"""
CAT CLI — Dev & Workspace Commands.

Real implementations of 30+ development, file, git, testing, linting,
formatting, and process execution commands.
"""

from __future__ import annotations

import fnmatch
import os
import re
import shutil
import subprocess
import sys
import time
from typing import List, Tuple, Optional


def _get_workspace_root() -> str:
    try:
        from . import workspace as ws
        return ws.root_dir() if hasattr(ws, "root_dir") else os.getcwd()
    except Exception:
        return os.getcwd()


def cmd_files(arg: str = "") -> str:
    """Lists files in the workspace with sizes and modification dates."""
    root = _get_workspace_root()
    pattern = arg.strip() or "*"
    entries = []
    
    ignore_dirs = {".git", ".venv", "__pycache__", "node_modules", ".pytest_cache", "build", "dist"}
    
    for r, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for f in files:
            if fnmatch.fnmatch(f, pattern) or fnmatch.fnmatch(os.path.join(r, f), pattern):
                p = os.path.join(r, f)
                rel = os.path.relpath(p, root)
                try:
                    st = os.stat(p)
                    size = st.st_size
                    mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))
                    size_str = f"{size / 1024:.1f} KB" if size >= 1024 else f"{size} B"
                    entries.append((rel, size_str, mtime))
                except Exception:
                    entries.append((rel, "?", "?"))
                if len(entries) >= 100:
                    break
        if len(entries) >= 100:
            break

    if not entries:
        return f"📁 No files matching '{pattern}' found in workspace."

    lines = [
        f"📁 **Workspace Files** ({len(entries)} items, matching `{pattern}`):",
        "",
        "| File | Size | Modified |",
        "| :--- | :--- | :--- |",
    ]
    for rel, size_str, mtime in sorted(entries, key=lambda x: x[0])[:60]:
        lines.append(f"| `{rel}` | {size_str} | {mtime} |")
    if len(entries) > 60:
        lines.append(f"\n_... and {len(entries) - 60} more files._")
    return "\n".join(lines)


def cmd_tree(arg: str = "") -> str:
    """Renders a clean directory tree of the workspace."""
    root = _get_workspace_root()
    depth_limit = int(arg.strip()) if arg.strip().isdigit() else 3
    ignore_dirs = {".git", ".venv", "__pycache__", "node_modules", "build", "dist", ".gemini"}

    lines = [f"📂 **{os.path.basename(root) or root}**"]

    def _walk(curr_dir: str, prefix: str = "", depth: int = 1):
        if depth > depth_limit:
            return
        try:
            items = sorted(os.listdir(curr_dir))
        except Exception:
            return
        items = [i for i in items if i not in ignore_dirs]
        total = len(items)
        for idx, item in enumerate(items):
            is_last = (idx == total - 1)
            p = os.path.join(curr_dir, item)
            connector = "└── " if is_last else "├── "
            new_prefix = prefix + ("    " if is_last else "│   ")
            if os.path.isdir(p):
                lines.append(f"{prefix}{connector}📁 {item}/")
                _walk(p, new_prefix, depth + 1)
            else:
                lines.append(f"{prefix}{connector}📄 {item}")

    _walk(root)
    if len(lines) > 80:
        lines = lines[:80] + ["\n_... tree truncated for display._"]
    return "```\n" + "\n".join(lines) + "\n```"


def cmd_search(text: str) -> str:
    """Searches workspace files for literal text."""
    if not text.strip():
        return "Usage: `/search <text>`"
    root = _get_workspace_root()
    query = text.strip()
    matches = []
    ignore_dirs = {".git", ".venv", "__pycache__", "node_modules", "build", "dist"}

    for r, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for f in files:
            p = os.path.join(r, f)
            rel = os.path.relpath(p, root)
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as file:
                    for lno, line in enumerate(file, 1):
                        if query.lower() in line.lower():
                            matches.append((rel, lno, line.strip()))
                            if len(matches) >= 50:
                                break
            except Exception:
                pass
            if len(matches) >= 50:
                break
        if len(matches) >= 50:
            break

    if not matches:
        return f"🔍 No occurrences of `{query}` found in workspace."

    out = [f"🔍 **Search Results for `{query}`** ({len(matches)} matches):", ""]
    for rel, lno, line in matches[:40]:
        disp = (line[:75] + "…") if len(line) > 75 else line
        out.append(f"- `{rel}:{lno}`: `{disp}`")
    return "\n".join(out)


def cmd_grep(pattern: str) -> str:
    """Searches workspace files using regular expressions."""
    if not pattern.strip():
        return "Usage: `/grep <regex>`"
    try:
        rx = re.compile(pattern.strip(), re.IGNORECASE)
    except Exception as e:
        return f"❌ Invalid regex pattern: `{e}`"

    root = _get_workspace_root()
    matches = []
    ignore_dirs = {".git", ".venv", "__pycache__", "node_modules", "build", "dist"}

    for r, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for f in files:
            p = os.path.join(r, f)
            rel = os.path.relpath(p, root)
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as file:
                    for lno, line in enumerate(file, 1):
                        if rx.search(line):
                            matches.append((rel, lno, line.strip()))
                            if len(matches) >= 50:
                                break
            except Exception:
                pass
            if len(matches) >= 50:
                break
        if len(matches) >= 50:
            break

    if not matches:
        return f"🔍 No regex matches for `{pattern}` found."

    out = [f"🔍 **Grep Results for `{pattern}`** ({len(matches)} matches):", ""]
    for rel, lno, line in matches[:40]:
        disp = (line[:75] + "…") if len(line) > 75 else line
        out.append(f"- `{rel}:{lno}`: `{disp}`")
    return "\n".join(out)


def cmd_replace(arg: str) -> str:
    """Finds and replaces text across files. Usage: /replace old new [glob]"""
    parts = arg.strip().split()
    if len(parts) < 2:
        return "Usage: `/replace <old_string> <new_string> [file_glob]`"
    old_str = parts[0]
    new_str = parts[1]
    pattern = parts[2] if len(parts) > 2 else "*.py"

    root = _get_workspace_root()
    replaced_count = 0
    modified_files = []
    ignore_dirs = {".git", ".venv", "__pycache__", "node_modules", "build", "dist"}

    for r, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for f in files:
            if fnmatch.fnmatch(f, pattern):
                p = os.path.join(r, f)
                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as file:
                        c = file.read()
                    if old_str in c:
                        cnt = c.count(old_str)
                        new_c = c.replace(old_str, new_str)
                        with open(p, "w", encoding="utf-8") as file:
                            file.write(new_c)
                        replaced_count += cnt
                        modified_files.append((os.path.relpath(p, root), cnt))
                except Exception:
                    pass

    if not modified_files:
        return f"ℹ️ String `{old_str}` not found in files matching `{pattern}`."

    out = [f"✅ Replaced {replaced_count} occurrences across {len(modified_files)} files:"]
    for mf, cnt in modified_files[:20]:
        out.append(f"- `{mf}` ({cnt} replacements)")
    return "\n".join(out)


def cmd_rename(arg: str) -> str:
    """Renames a file or directory."""
    parts = arg.strip().split()
    if len(parts) != 2:
        return "Usage: `/rename <old_path> <new_path>`"
    root = _get_workspace_root()
    src = os.path.join(root, parts[0])
    dst = os.path.join(root, parts[1])

    if not os.path.exists(src):
        return f"❌ Source not found: `{parts[0]}`"
    if os.path.exists(dst):
        return f"❌ Target already exists: `{parts[1]}`"

    try:
        os.rename(src, dst)
        return f"✅ Renamed `{parts[0]}` → `{parts[1]}`"
    except Exception as e:
        return f"❌ Rename failed: {e}"


def cmd_new(arg: str) -> str:
    """Creates a new file or directory."""
    p_str = arg.strip()
    if not p_str:
        return "Usage: `/new <file_or_dir_path>`"
    root = _get_workspace_root()
    target = os.path.join(root, p_str)

    if os.path.exists(target):
        return f"ℹ️ Target `{p_str}` already exists."

    try:
        if p_str.endswith("/") or p_str.endswith("\\"):
            os.makedirs(target, exist_ok=True)
            return f"✅ Created directory `{p_str}`"
        else:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write("")
            return f"✅ Created file `{p_str}`"
    except Exception as e:
        return f"❌ Creation failed: {e}"


def cmd_git(arg: str) -> str:
    """Runs git commands directly inside the workspace."""
    root = _get_workspace_root()
    cmd = arg.strip() or "status"
    full_cmd = f"git {cmd}"
    try:
        res = subprocess.run(
            full_cmd,
            cwd=root,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        out = (res.stdout or res.stderr or "✓ Clean").strip()
        return f"**Git Output (`{full_cmd}`):**\n```\n{out}\n```"
    except Exception as e:
        return f"❌ Git execution failed: {e}"


def cmd_diff(arg: str = "") -> str:
    """Shows git diff for workspace or specific file."""
    root = _get_workspace_root()
    f_arg = arg.strip()
    cmd = f"git diff {f_arg}"
    try:
        res = subprocess.run(
            cmd,
            cwd=root,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        out = res.stdout.strip()
        if not out:
            return "✓ Working tree is clean (no diffs)."
        lines = out.splitlines()
        if len(lines) > 80:
            out = "\n".join(lines[:80]) + "\n\n... diff truncated."
        return f"```diff\n{out}\n```"
    except Exception as e:
        return f"❌ Diff failed: {e}"


def cmd_test(arg: str = "") -> str:
    """Runs test suite (pytest or unittest) in the workspace."""
    root = _get_workspace_root()
    test_cmd = f"python -m pytest {arg}" if arg.strip() else "python -m unittest discover -s ."
    try:
        res = subprocess.run(
            test_cmd,
            cwd=root,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=45
        )
        out = (res.stdout + "\n" + res.stderr).strip()
        badge = "✅ **Tests Passed**" if res.returncode == 0 else "❌ **Tests Failed**"
        return f"{badge} (`{test_cmd}`):\n```\n{out[:2000]}\n```"
    except subprocess.TimeoutExpired:
        return "⏱️ Tests timed out after 45s."
    except Exception as e:
        return f"❌ Test execution failed: {e}"


def cmd_lint(arg: str = "") -> str:
    """Runs linting checks (ruff, flake8, or syntax compile)."""
    root = _get_workspace_root()
    # Check if ruff or flake8 is installed, otherwise python syntax check
    cmd = f"ruff check {arg}" if shutil.which("ruff") else f"python -m py_compile {arg or 'calc_terminal'}"
    try:
        res = subprocess.run(
            cmd,
            cwd=root,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        out = (res.stdout or res.stderr or "✓ No issues found.").strip()
        badge = "✅ **Lint Clean**" if res.returncode == 0 else "⚠️ **Lint Warnings/Errors**"
        return f"{badge} (`{cmd}`):\n```\n{out[:1500]}\n```"
    except Exception as e:
        return f"❌ Lint failed: {e}"


def cmd_format(arg: str = "") -> str:
    """Formats code using black or ruff format."""
    root = _get_workspace_root()
    cmd = f"ruff format {arg}" if shutil.which("ruff") else f"black {arg or '.'}"
    try:
        res = subprocess.run(
            cmd,
            cwd=root,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        out = (res.stdout or res.stderr or "✓ Formatted").strip()
        return f"**Format Result (`{cmd}`):**\n```\n{out}\n```"
    except Exception as e:
        return f"❌ Format failed: {e}"


def cmd_typecheck(arg: str = "") -> str:
    """Runs type checking (mypy / pyright)."""
    root = _get_workspace_root()
    cmd = f"mypy {arg or '.'}" if shutil.which("mypy") else f"pyright {arg or '.'}"
    try:
        res = subprocess.run(
            cmd,
            cwd=root,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        out = (res.stdout or res.stderr or "✓ Type check clean.").strip()
        return f"**Type Check (`{cmd}`):**\n```\n{out[:1500]}\n```"
    except Exception as e:
        return f"❌ Typecheck tool not found or failed: {e}"


def cmd_run(arg: str) -> str:
    """Executes a python script or shell command in workspace."""
    if not arg.strip():
        return "Usage: `/run <script.py or command>`"
    root = _get_workspace_root()
    cmd = f"python {arg}" if arg.strip().endswith(".py") else arg
    try:
        res = subprocess.run(
            cmd,
            cwd=root,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30
        )
        out = (res.stdout + ("\n" + res.stderr if res.stderr else "")).strip()
        status = "✅ Completed (code 0)" if res.returncode == 0 else f"⚠️ Exited with code {res.returncode}"
        return f"**Run Output (`{cmd}`):** {status}\n```\n{out[:2500]}\n```"
    except subprocess.TimeoutExpired:
        return "⏱️ Execution timed out after 30s."
    except Exception as e:
        return f"❌ Execution failed: {e}"

