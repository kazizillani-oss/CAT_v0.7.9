"""
Code Pad + Text Editor for Chemistry Calc Terminal (CCT) [BETA].

Feature 1 — a real in-terminal code pad: write code line-by-line, get CCT AI
to generate/insert code for you, run Python snippets, save/load files — all
with its own fixed GitHub-Light syntax highlighting (independent of the
app's own dark/light theme, since that's what was asked for).

Feature 2 — the same engine in "text" mode powers /edit, a plain-text
in-terminal editor (notes, todo lists, snippets) with find/replace.

Feature 6 — /import (and this module's `:import`) reads local text files or
images and hands them to aicore so the AI/agent can actually use their
content, not just their filename.

Design note: CCT has no curses/full-screen UI (it's a plain print()+input()
REPL, like the rest of the app), so this is a *line editor*: you type one
line at a time, and everything starting with ':' is a command (save, run,
ai, list, etc.) rather than a line of content. This matches how every other
part of CCT already works (e.g. /solve, /settings) — no new UI paradigm,
no new dependency.
"""

if __name__ == '__main__':
    print("This is a library file and is not meant to be run directly.")
    print("Please run 'python main.py' or 'python model.py' from the project root directory.")
    import sys
    sys.exit(1)

import os
import re
import sys
import time
import subprocess

from . import theme
from . import aicore
from . import sound
from . import security_scanner
from . import sandbox

DEFAULT_SAVE_DIR = os.path.join(os.path.expanduser("~"), "cct_files")

# --------------------------------------------------------- copy / clipboard --
# Feature request: "we can also copy the code" — works two ways:
#   1. Inside the code pad itself: `:copy` copies the whole buffer.
#   2. From an AI chat reply that contains a fenced code block: `/copycode`
#      copies the most recently *shown* block (the conversation renderer / fallback_cli records it here
#      every time it renders one, so this module stays the single source
#      of truth for "what code did we last show the user").
_LAST_BLOCKS = []


def remember_block(code, lang=""):
    """Called every time a fenced code block is rendered in
    an AI reply, so /copycode always has something sensible to copy."""
    _LAST_BLOCKS.append({"code": code, "lang": lang})
    del _LAST_BLOCKS[:-10]  # keep a short history, most-recent last


def get_last_block():
    return _LAST_BLOCKS[-1] if _LAST_BLOCKS else None


def copy_to_clipboard(text):
    """Best-effort clipboard copy with no required third-party dependency.
    Tries pyperclip first (if installed), then the native OS clipboard
    command for the current platform. Returns (ok: bool, detail: str) —
    `detail` is either the method that worked or why it failed, so the
    caller can show a useful message either way."""
    try:
        import pyperclip
        pyperclip.copy(text)
        return True, "pyperclip"
    except Exception:
        pass

    try:
        if sys.platform.startswith("win"):
            p = subprocess.Popen(["clip"], stdin=subprocess.PIPE, shell=True)
            p.communicate(input=text.encode("utf-16-le"))
            if p.returncode == 0:
                return True, "clip"
        elif sys.platform == "darwin":
            p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            p.communicate(input=text.encode("utf-8"))
            if p.returncode == 0:
                return True, "pbcopy"
        else:
            for cmd in (["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"], ["wl-copy"]):
                try:
                    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
                    p.communicate(input=text.encode("utf-8"))
                    if p.returncode == 0:
                        return True, cmd[0]
                except FileNotFoundError:
                    continue
    except Exception as e:
        return False, str(e)
    return False, "no clipboard tool available (install 'pyperclip', or xclip/xsel/wl-copy on Linux)"

# ------------------------------------------------------------------ syntax --
# Fixed GitHub-Light-style Python highlighting for the code pad, regardless
# of the app's own current theme (dark or light) — the code pad always
# renders code in these colors, only the surrounding chrome (panels, hints)
# follows the app theme.
_PALETTE = theme.SYNTAX_GITHUB_LIGHT
_KEYWORDS = {
    "def", "class", "return", "if", "elif", "else", "for", "while", "in", "is",
    "not", "and", "or", "import", "from", "as", "try", "except", "finally",
    "with", "pass", "break", "continue", "lambda", "yield", "global", "nonlocal",
    "raise", "assert", "del", "async", "await", "True", "False", "None",
}
_BUILTINS = {
    "print", "len", "range", "str", "int", "float", "list", "dict", "set",
    "tuple", "open", "input", "type", "isinstance", "enumerate", "zip", "map",
    "filter", "sorted", "sum", "min", "max", "abs", "round", "super", "self",
}
_TOKEN_RE = re.compile(r"""
      (?P<comment>\#.*$)
    | (?P<string>(\"\"\".*?\"\"\"|'''.*?'''|"[^"\n]*"|'[^'\n]*'))
    | (?P<number>\b\d+\.?\d*\b)
    | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
    | (?P<op>[\+\-\*/%=<>!&|^~:,\.\(\)\[\]\{\}])
""", re.VERBOSE)


def highlight_python(line):
    """Return `line` with GitHub-Light-styled ANSI color codes applied,
    token by token. Best-effort regex highlighting — good enough for a
    terminal code pad, not a full parser."""
    out = []
    pos = 0
    for m in _TOKEN_RE.finditer(line):
        if m.start() > pos:
            out.append(line[pos:m.start()])
        kind = m.lastgroup
        text = m.group()
        if kind == "comment":
            out.append(theme.fg(text, _PALETTE["comment"]))
        elif kind == "string":
            out.append(theme.fg(text, _PALETTE["string"]))
        elif kind == "number":
            out.append(theme.fg(text, _PALETTE["number"]))
        elif kind == "name":
            if text in _KEYWORDS:
                out.append(theme.fg(text, _PALETTE["keyword"], bold=True))
            elif text in _BUILTINS:
                out.append(theme.fg(text, _PALETTE["builtin"]))
            else:
                out.append(theme.fg(text, _PALETTE["plain"]))
        elif kind == "op":
            out.append(theme.fg(text, _PALETTE["operator"]))
        else:
            out.append(text)
        pos = m.end()
    out.append(line[pos:])
    return "".join(out)


def highlight_text(line):
    """Plain-text mode gets no syntax coloring — just the normal app text
    color, so /edit reads like a clean notepad rather than looking like
    mis-highlighted code."""
    return theme.text(line)


# --------------------------------------------------------------- rendering --
def _print_buffer(buffer, mode):
    highlighter = highlight_python if mode == "code" else highlight_text
    if not buffer:
        print(theme.faint("  (empty — start typing lines, or use :ai <prompt>)"))
        return
    gutter_w = len(str(len(buffer)))
    for i, line in enumerate(buffer, 1):
        num = theme.faint(str(i).rjust(gutter_w) + " │ ")
        print(f"  {num}{highlighter(line)}")


def _header(mode, filename, dirty):
    kind = "CODE PAD" if mode == "code" else "TEXT EDITOR"
    title_line = theme.badge("BETA", theme.BG_WARN) + " " + theme.purple(f"▓ {kind} ▓", bold=True)
    fname = filename or "(untitled)"
    dirty_flag = theme.orange(" ●unsaved") if dirty else ""
    lines = [
        title_line,
        theme.dim(f"File: {fname}{dirty_flag}"),
    ]
    if mode == "code":
        lines.append(theme.dim("Syntax: GitHub Light  │  :run executes Python  │  :ai <prompt> asks CAT AI to write code"))
    else:
        lines.append(theme.dim(":find <text>  │  :replace <old> <new>  │  :ai <prompt> asks CAT AI to write/edit text"))
    lines.append(theme.faint(":save [path]  :load <path>  :import <path>  :copy  :list  :clear  :undo  :help  :back"))
    return theme.panel(lines, title="codepad" if mode == "code" else "textedit",
                        color=theme.PURPLE, width=_width())


def _width():
    try:
        from .engine import WIDTH
        return WIDTH
    except Exception:
        return 78


def _print_help(mode):
    rows = [
        (":run", "Execute the buffer as a Python script (code mode only, sandboxed)"),
        (":scan", "Static security scan of the buffer (code mode only)"),
        (":watch <path>", "Live-watch a file on disk, redrawing on change"),
        (":ai <prompt>", "Ask CAT AI to write code/text and append it to the buffer"),
        (":save [path]", "Save the buffer to a file (defaults to ~/cct_files/)"),
        (":load <path>", "Replace the buffer with a file's contents"),
        (":import <path>", "Import a text file (content) or image (sent to AI vision)"),
        (":list", "Reprint the whole buffer with line numbers"),
        (":copy", "Copy the whole buffer to the clipboard (or save as fallback)"),
        (":clear", "Erase the whole buffer (asks to confirm)"),
        (":undo", "Undo the last change to the buffer"),
        (":del <n>", "Delete line n"),
        (":find <text>", "Text mode: list every line containing <text>"),
        (":replace <old> <new>", "Text mode: replace first match on each line"),
        (":theme light|dark", "Switch the whole app's theme"),
        (":back / :exit", "Leave the editor and return home"),
    ]
    lines = [theme.cyan("COMMANDS", bold=True), ""]
    for cmd, desc in rows:
        lines.append(f"  {theme.text(cmd, bold=True):<28} {theme.dim(desc)}")
    print()
    print(theme.panel(lines, title="help", color=theme.CYAN, width=_width()))


def _save_buffer(buffer, path):
    if not path:
        os.makedirs(DEFAULT_SAVE_DIR, exist_ok=True)
        ext = ".py" if _looks_like_code(buffer) else ".txt"
        path = os.path.join(DEFAULT_SAVE_DIR, f"untitled_{int(time.time())}{ext}")
    path = os.path.expanduser(path)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(buffer) + ("\n" if buffer else ""))
        return True, path
    except Exception as e:
        return False, str(e)


def _looks_like_code(buffer):
    text = "\n".join(buffer)
    return bool(re.search(r"^\s*(def |class |import |from |print\()", text, re.M))


def _load_buffer(path):
    path = os.path.expanduser(path)
    content, truncated = aicore.read_text_file_for_context(path)
    if content is None:
        return None, truncated
    lines = content.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines, truncated


def _scan_and_confirm(code):
    """Runs the real static scanner and, for anything above LOW risk,
    shows a permission-card-style prompt before execution — same shape
    as the app's other permission cards (action / reason / risk /
    allow-once / deny), just rendered inline in the code pad."""
    findings = security_scanner.scan_code(code)
    risk = security_scanner.risk_level(findings)
    if risk in ("none", "low"):
        return True
    lines = [
        theme.orange("ACTION", bold=True) + "  Execute this code in the sandbox",
        theme.orange("RISK", bold=True) + f"    {risk.upper()}",
        theme.orange("REASON", bold=True) + "  " + security_scanner.summarize(findings),
    ]
    for f in findings[:6]:
        lines.append("    " + theme.dim(repr(f)))
    lines.append("")
    lines.append(theme.dim("  [Enter] Allow once   [n] Deny"))
    print()
    print(theme.panel(lines, title="permission", color=theme.ORANGE, width=_width()))
    choice = input(theme.dim("  \u25b8 ")).strip().lower()
    return choice != "n"


def _run_python(buffer):
    code = "\n".join(buffer)
    if not code.strip():
        print(theme.orange("  Nothing to run — the buffer is empty."))
        return
    if not _scan_and_confirm(code):
        print(theme.dim("  Cancelled."))
        return
    label = "sandboxed" if sandbox.sandbox_available() else "timeout-only (no rlimit sandbox on this OS)"
    print(theme.dim(f"  Running ({label})..."))
    result = sandbox.run_sandboxed(code, timeout=15)
    if result["stdout"]:
        print(theme.panel([theme.text(l) for l in result["stdout"].rstrip("\n").split("\n")] or [""],
                           title="stdout", color=theme.GREEN, width=_width()))
    if result["timed_out"]:
        sound.play("error")
        print(theme.red("  ✗ Timed out after 15s (possible infinite loop)."))
    elif result["killed_by_limit"]:
        sound.play("error")
        print(theme.red("  ✗ Killed by sandbox resource limit (CPU/memory)."))
    elif result["returncode"] != 0:
        sound.play("error")
        err_lines = (result["stderr"] or "Unknown error").rstrip("\n").split("\n")
        print(theme.panel([theme.red(l) for l in err_lines], title="error",
                           color=theme.RED, width=_width()))
    else:
        sound.play("success")
        if not result["stdout"]:
            print(theme.green("  ✓ Ran with no output."))


def _scan_buffer(buffer):
    code = "\n".join(buffer)
    if not code.strip():
        print(theme.orange("  Nothing to scan — the buffer is empty."))
        return
    findings = security_scanner.scan_code(code)
    risk = security_scanner.risk_level(findings)
    color = {"high": theme.RED, "medium": theme.ORANGE, "low": theme.CYAN, "none": theme.GREEN}[risk]
    lines = [theme.fg(f"RISK: {risk.upper()}", color, bold=True), ""]
    if findings:
        for f in findings:
            lines.append("  " + theme.dim(repr(f)))
    else:
        lines.append(theme.green("  No risky patterns detected."))
    print()
    print(theme.panel(lines, title="security scan", color=color, width=_width()))


def _watch_file(path):
    """Polls a file's mtime and reprints it whenever it changes on disk,
    until the user hits Enter — a real filesystem watch (not a fake
    'watching...' spinner), implemented via polling since that's the
    only portable option without an extra dependency. Guarded by
    stdin_is_interactive() so a piped/non-tty session (where Enter can
    never arrive) doesn't spin forever — same precedent as the
    /sim3d and /atomsim keypress-loop fix."""
    from . import keys
    path = os.path.expanduser(path)
    if not os.path.isfile(path):
        print(theme.red(f"  ✗ No such file: {path}"))
        return
    if not keys.stdin_is_interactive():
        print(theme.orange("  :watch needs a real attached terminal (not piped input) — showing the file once instead."))
        with open(path, encoding="utf-8", errors="replace") as f:
            print(theme.panel([theme.text(l) for l in f.read().splitlines()], title=path, color=theme.CYAN, width=_width()))
        return

    print(theme.dim(f"  Watching {path} — press Enter to stop."))
    last_mtime = None
    try:
        while True:
            if keys.key_available():
                keys.read_key()
                break
            time.sleep(0.4)
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                continue
            if mtime != last_mtime:
                last_mtime = mtime
                with open(path, encoding="utf-8", errors="replace") as f:
                    content = f.read().splitlines()
                theme.clear_screen()
                print(theme.panel([theme.text(l) for l in content], title=f"{path} (live)", color=theme.CYAN, width=_width()))
                print(theme.dim("  Press Enter to stop watching."))
    except (KeyboardInterrupt, EOFError):
        pass
    print(theme.dim("  Stopped watching."))


def _ask_ai_for_content(prompt, mode, buffer):
    config = aicore.load_config()
    if not config.get("provider"):
        print(theme.orange("  No AI provider configured yet — run /ai or /model first."))
        return None
    context = ""
    if buffer:
        context = "Current buffer so far:\n```\n" + "\n".join(buffer) + "\n```\n\n"
    if mode == "code":
        sys_prompt = ("You are a precise coding assistant embedded in a terminal code pad. "
                      "Reply with ONLY the code — no markdown fences, no explanation, no "
                      "commentary — ready to append directly to the buffer as-is.")
    else:
        sys_prompt = ("You are a writing assistant embedded in a terminal text editor. "
                      "Reply with ONLY the plain text to insert — no markdown, no commentary.")
    print(theme.dim("  CAT AI is generating..."))
    t0 = time.time()
    reply = aicore.query_ai(context + "Request: " + prompt, system_prompt=sys_prompt)
    dur = time.time() - t0
    reply = re.sub(r"^```[a-zA-Z]*\n?|```$", "", reply.strip(), flags=re.M).strip()
    print(theme.faint(f"  ({dur:.1f}s, ~{aicore.estimate_tokens(reply)} tok generated)"))
    return reply.split("\n") if reply else None


def run_editor(app, mode="code"):
    """Entry point for /codepad (mode='code') and /edit (mode='text')."""
    buffer = []
    history = []  # undo stack (previous buffer states)
    filename = None
    dirty = False

    def push_undo():
        history.append(list(buffer))
        if len(history) > 30:
            history.pop(0)

    theme.clear_screen()
    print()
    print(_header(mode, filename, dirty))
    print()

    label = "code" if mode == "code" else "text"
    while True:
        try:
            raw = input(theme.dim(f"  {label} ▸ "))
        except (EOFError, KeyboardInterrupt):
            print()
            break

        stripped = raw.strip()
        low = stripped.lower()

        if not stripped:
            continue

        if low in (":back", ":exit", ":q"):
            if dirty:
                confirm = input(theme.orange("  Unsaved changes — leave anyway? (y/N) ▸ ")).strip().lower()
                if confirm != "y":
                    continue
            break

        if low == ":help":
            _print_help(mode)
            continue

        if low == ":list":
            print()
            _print_buffer(buffer, mode)
            print()
            continue

        if low == ":copy":
            if not buffer:
                print(theme.faint("  Nothing to copy — the buffer is empty."))
                continue
            ok, detail = copy_to_clipboard("\n".join(buffer))
            if ok:
                print(theme.green(f"  ✓ Copied {len(buffer)} line(s) to the clipboard (via {detail})."))
            else:
                saved_ok, saved_path = _save_buffer(buffer, None)
                if saved_ok:
                    print(theme.orange(f"  Clipboard unavailable ({detail}).") + " " +
                          theme.green(f"Saved instead to {saved_path} — open it to copy."))
                else:
                    print(theme.red(f"  ✗ Clipboard unavailable ({detail}), and saving a fallback also failed."))
            continue

        if low == ":clear":
            confirm = input(theme.orange("  Erase the whole buffer? (y/N) ▸ ")).strip().lower()
            if confirm == "y":
                push_undo()
                buffer = []
                dirty = True
                print(theme.green("  Buffer cleared."))
            continue

        if low == ":undo":
            if history:
                buffer = history.pop()
                dirty = True
                print(theme.green("  Undone."))
                _print_buffer(buffer, mode)
            else:
                print(theme.faint("  Nothing to undo."))
            continue

        if low.startswith(":del "):
            arg = stripped.split(" ", 1)[1].strip()
            if arg.isdigit() and 1 <= int(arg) <= len(buffer):
                push_undo()
                removed = buffer.pop(int(arg) - 1)
                dirty = True
                print(theme.green(f"  Deleted line {arg}: ") + theme.faint(removed[:60]))
            else:
                print(theme.red(f"  No such line '{arg}'."))
            continue

        if low.startswith(":theme"):
            arg = stripped.split(" ", 1)[1].strip() if " " in stripped else ""
            new_name = theme.set_theme(arg or ("textual-light" if not theme.is_light() else "tokyo-night"))
            print(theme.green(f"  Theme switched to {new_name}."))
            print()
            print(_header(mode, filename, dirty))
            continue

        if low == ":run":
            if mode != "code":
                print(theme.orange("  :run only works in the code pad (/codepad), not the text editor."))
                continue
            _run_python(buffer)
            continue

        if low == ":scan":
            if mode != "code":
                print(theme.orange("  :scan only works in the code pad (/codepad), not the text editor."))
                continue
            _scan_buffer(buffer)
            continue

        if low.startswith(":watch "):
            _watch_file(stripped.split(" ", 1)[1].strip())
            continue

        if low.startswith(":ai"):
            prompt = stripped[3:].strip()
            if not prompt:
                print(theme.orange("  Usage: :ai <what to generate>, e.g. :ai a function that reverses a string"))
                continue
            generated = _ask_ai_for_content(prompt, mode, buffer)
            if generated:
                push_undo()
                buffer.extend(generated)
                dirty = True
                print()
                _print_buffer(buffer, mode)
            continue

        if low.startswith(":save"):
            arg = stripped.split(" ", 1)[1].strip() if " " in stripped else ""
            ok, result = _save_buffer(buffer, arg or filename)
            if ok:
                filename = result
                dirty = False
                print(theme.green(f"  ✓ Saved to {result}"))
            else:
                print(theme.red(f"  ✗ Could not save: {result}"))
            continue

        if low.startswith(":load "):
            path = stripped.split(" ", 1)[1].strip()
            loaded, truncated = _load_buffer(path)
            if loaded is None:
                print(theme.red(f"  ✗ Could not read '{path}'."))
            else:
                push_undo()
                buffer = loaded
                filename = os.path.expanduser(path)
                dirty = False
                mode = "code" if path.lower().endswith((".py", ".pyw")) else mode
                if truncated:
                    print(theme.orange(f"  Loaded (truncated to {aicore.TEXT_FILE_MAX_CHARS} chars)."))
                else:
                    print(theme.green(f"  ✓ Loaded {path}"))
                _print_buffer(buffer, mode)
            continue

        if low.startswith(":import "):
            path = stripped.split(" ", 1)[1].strip()
            _handle_import(path, mode, buffer, push_undo)
            continue

        if mode == "text" and low.startswith(":find "):
            needle = stripped.split(" ", 1)[1]
            hits = [(i, l) for i, l in enumerate(buffer, 1) if needle.lower() in l.lower()]
            if hits:
                for i, l in hits:
                    print(f"  {theme.cyan(str(i) + ':')} {theme.text(l)}")
            else:
                print(theme.faint(f"  No matches for '{needle}'."))
            continue

        if mode == "text" and low.startswith(":replace "):
            rest = stripped.split(" ", 2)
            if len(rest) < 3:
                print(theme.orange("  Usage: :replace <old> <new>"))
                continue
            old, new = rest[1], rest[2]
            push_undo()
            n = 0
            for i, l in enumerate(buffer):
                if old in l:
                    buffer[i] = l.replace(old, new, 1)
                    n += 1
            dirty = dirty or n > 0
            print(theme.green(f"  Replaced in {n} line(s)."))
            continue

        # Anything else typed is just a new line of content.
        push_undo()
        buffer.append(raw)
        dirty = True
        line_no = len(buffer)
        highlighter = highlight_python if mode == "code" else highlight_text
        print(theme.faint(f"  {line_no} │ ") + highlighter(raw))

    app.print_home()


def _handle_import(path, mode, buffer, push_undo):
    path = os.path.expanduser(path.strip())
    if not os.path.exists(path):
        print(theme.red(f"  ✗ File not found: {path}"))
        return
    if aicore.is_image_file(path):
        config = aicore.load_config()
        if not config.get("provider"):
            print(theme.orange("  Image detected, but no AI is configured to analyze it — run /ai or /model first."))
            return
        print(theme.dim(f"  Sending image to {config.get('provider')} for analysis..."))
        result = aicore.query_ai_with_image(
            "Describe this image in detail, and if it contains code, chemistry, "
            "math, or a diagram, extract/transcribe the relevant content precisely.",
            path)
        print()
        print(theme.panel([theme.text(l) for l in result.split("\n")], title="image analysis",
                           color=theme.PURPLE, width=_width()))
        push_undo()
        buffer.append(f"# Imported image: {path}")
        for l in result.split("\n"):
            buffer.append(("# " if mode == "code" else "") + l)
        return
    content, truncated = aicore.read_text_file_for_context(path)
    if content is None:
        print(theme.red(f"  ✗ Could not read '{path}' as text."))
        return
    push_undo()
    buffer.extend(content.split("\n"))
    if truncated:
        print(theme.orange(f"  ✓ Imported {path} (truncated to {aicore.TEXT_FILE_MAX_CHARS} chars)."))
    else:
        print(theme.green(f"  ✓ Imported {path}"))
    _print_buffer(buffer, mode)
