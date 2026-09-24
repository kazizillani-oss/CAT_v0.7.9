"""
cat doctor — diagnose and repair the CAT CLI installation.

Run it either way:

    cat --doctor                       (when `cat` itself is already found)
    python -m calc_terminal.doctor     (always works — uses python.exe)

What it checks, in order:

  1. Which Python / which environment (venv vs global vs Store Python).
  2. Is the CAT package importable, and which version.
  3. Does a `cat` launcher (cat.exe) exist in this interpreter's Scripts
     directory, and is that directory on PATH (process PATH, per-user
     registry PATH, per-machine registry PATH on Windows).
  4. Windows only: the PowerShell built-in alias `cat -> Get-Content`,
     which shadows ANY external cat.exe inside PowerShell sessions
     (cmd.exe has no such conflict). Offer an idempotent $PROFILE fix.
  5. POSIX: warn that /usr/bin/cat (coreutils) exists on essentially all
     Unix shells and will keep winning unless the user aliases it.

Fixes are opt-in flags; nothing is modified without them:

  --fix-path          append the Scripts dir to the USER Path value in
                      the registry (HKCU\\Environment). Existing entries
                      are never rewritten, reordered or removed; the old
                      value is backed up to CCT's logs dir first; a
                      WM_SETTINGCHANGE broadcast tells running shells a
                      change happened (new terminals pick it up).
  --fix-powershell    add a marker-guarded snippet to the PowerShell
                      CurrentUserAllHosts profiles (Windows PowerShell
                      5.1 and PowerShell 7+ if installed) that removes
                      the built-in alias so the external cat.exe wins.
                      Get-Content/gc remain fully available for files.

Exit code: 0 when everything looks healthy, 1 when a problem was found.
"""

import os
import sys

_MARK_BEGIN = "# >>> CAT CLI (added by `cat --doctor --fix-powershell`) >>>"
_MARK_END = "# <<< CAT CLI <<<"

_PS_SNIPPET = f"""{_MARK_BEGIN}
# Lets the CAT app own `cat`; file reading stays on Get-Content/gc/type.
Remove-Item Alias:cat -Force -ErrorAction SilentlyContinue
{_MARK_END}
"""


def _dist_version():
    for dist in ("cct-cli", "cat-cli", "cct-ai-ide", "cat-ai", "cct"):
        try:
            from importlib.metadata import version
            return version(dist)
        except Exception:
            continue
    return None


def _scripts_dirs():
    """Every directory where this interpreter could have dropped the
    launcher: the normal scheme plus the user scheme (pip --user /
    Microsoft Store Python both land there)."""
    dirs = []
    try:
        import sysconfig
        user_scheme = "nt_user" if sys.platform == "win32" else "posix_user"
        for scheme in (None, user_scheme):
            try:
                d = sysconfig.get_path("scripts", scheme)
            except Exception:
                d = None
            if d and d not in dirs:
                dirs.append(d)
    except Exception:
        pass
    return dirs


def _path_entries():
    return [p.strip() for p in os.environ.get("PATH", "").split(os.pathsep)
            if p.strip()]


def _registry_user_path():
    if sys.platform != "win32":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            val, _typ = winreg.QueryValueEx(k, "Path")
            return val
    except FileNotFoundError:
        return ""
    except Exception:
        return None


def _registry_machine_path():
    if sys.platform != "win32":
        return None
    try:
        import winreg
        key = "SYSTEM\\CurrentControlSet\\Control\\" \
              "Session Manager\\Environment"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as k:
            val, _typ = winreg.QueryValueEx(k, "Path")
            return val
    except Exception:
        return None


def _launcher_name():
    return "cat.exe" if sys.platform == "win32" else "cat"


def find_launcher():
    """Return the absolute path of the installed `cat` launcher, or None."""
    name = _launcher_name()
    for d in _scripts_dirs():
        p = os.path.join(d, name)
        if os.path.isfile(p):
            return p
    # Fall back to whatever PATH resolves to right now.
    for d in _path_entries():
        p = os.path.join(d, name)
        if os.path.isfile(p):
            return p
    return None


def _broadcast_settings_change():
    try:
        import ctypes
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0,
            "Environment", SMTO_ABORTIFHUNG, 5000, None)
    except Exception:
        pass


def fix_path(assume_yes=False):
    """Append the Scripts dir to the USER Path (HKCU). Only ever appends;
    never rewrites or removes existing entries."""
    if sys.platform != "win32":
        print("  --fix-path is only implemented for Windows.")
        print("  On Unix, add your Scripts/bin dir to ~/.bashrc / "
              "~/.zshrc manually.")
        return 1

    scripts = _scripts_dirs()
    missing = [d for d in scripts
               if d.lower() not in [e.lower() for e in _path_entries()]]
    user_path = _registry_user_path()
    if user_path is None:
        print("  ! Could not read HKCU\\Environment\\Path (permissions?).")
        return 1

    to_add = []
    for d in missing:
        parts = [p.strip().lower() for p in user_path.split(os.pathsep)
                 if p.strip()]
        if d.lower() not in parts:
            to_add.append(d)

    if not to_add:
        print("  Scripts dir(s) already present in PATH entries:")
        for d in scripts:
            print(f"    {d}")
        print("  Nothing to change. Open a NEW terminal and run `cat`.")
        return 0

    backup_dir = None
    try:
        from .first_run import logs_dir
        backup_dir = logs_dir()
        os.makedirs(backup_dir, exist_ok=True)
        backup = os.path.join(
            backup_dir,
            "path-backup-%s.txt"
            % __import__("time").strftime("%Y%m%d-%H%M%S"))
        with open(backup, "w", encoding="utf-8") as f:
            f.write("Previous HKCU\\Environment\\Path:\n")
            f.write(user_path + "\n")
        print(f"  Backed up current user PATH to: {backup}")
    except Exception:
        pass

    new_value = user_path.rstrip(os.pathsep) + os.pathsep + \
        os.pathsep.join(to_add) if user_path.strip() else \
        os.pathsep.join(to_add)

    if not assume_yes:
        print("  About to APPEND to the *user* PATH (HKCU\\Environment):")
        for d in to_add:
            print(f"    + {d}")
        answer = input("  Proceed? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("  Aborted — nothing was changed.")
            return 1

    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                        winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, "Path", 0, winreg.REG_EXPAND_SZ, new_value)
    _broadcast_settings_change()
    print("  Done. User PATH updated (existing entries untouched).")
    print("  IMPORTANT: open a NEW terminal window, then run `cat`.")
    return 0


def _profile_paths():
    """CurrentUserAllHosts profiles for every PowerShell host installed.

    NEVER hardcode ~\\Documents\\... : Windows redirects Documents to
    OneDrive on many machines, and only PowerShell itself knows where
    $PROFILE really lives. Ask each installed shell directly; fall back
    to the classic paths only if querying fails."""
    paths = []
    for exe in ("powershell", "pwsh"):
        try:
            import subprocess
            out = subprocess.run(
                [exe, "-NoProfile", "-NonInteractive", "-Command",
                 "$PROFILE.CurrentUserAllHosts"],
                capture_output=True, text=True, timeout=20)
            p = (out.stdout or "").strip()
            if out.returncode == 0 and p.lower().endswith(".ps1"):
                if p not in paths:
                    paths.append(p)
        except Exception:
            continue
    if not paths:
        docs = os.path.join(os.path.expanduser("~"), "Documents")
        paths.append(os.path.join(docs, "WindowsPowerShell", "profile.ps1"))
        p7 = os.path.join(docs, "PowerShell", "profile.ps1")
        if os.path.isdir(os.path.dirname(p7)):
            paths.append(p7)
    return paths


def fix_powershell(assume_yes=False):
    """Make external cat.exe beat PowerShell's built-in alias by adding
    an idempotent, marker-guarded Remove-Item line to the user's
    AllHosts profiles. Never touches anything else in the profile."""
    if sys.platform != "win32":
        print("  The PowerShell alias conflict only exists on Windows.")
        return 0

    targets = _profile_paths()
    if not assume_yes:
        print("  This adds a small guarded snippet to these PowerShell"
              " profiles\n  (creating them if they don't exist yet):")
        for p in targets:
            print(f"    {p}")
        answer = input("  Proceed? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("  Aborted — nothing was changed.")
            return 1

    changed = []
    for p in targets:
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            content = ""
            if os.path.isfile(p):
                with open(p, "r", encoding="utf-8-sig") as f:
                    content = f.read()
            if _MARK_BEGIN in content:
                continue
            sep = "" if not content or content.endswith("\n") else "\n"
            with open(p, "a", encoding="utf-8") as f:
                f.write(sep + _PS_SNIPPET)
            changed.append(p)
        except Exception as e:
            print(f"  ! Could not update {p}: {e}")
            return 1
    if changed:
        print("  Updated:")
        for p in changed:
            print(f"    {p}")
        print("  Open a NEW PowerShell window and run `cat`.")
        print("  (Reading files still works: use Get-Content / gc / type.)")
    else:
        print("  Profiles already patched — nothing to do.")
    return 0


def report(fix=False):
    """Print the diagnosis. Returns 0 (healthy) or 1 (problems found).
    With fix=True, offer interactive fixes after the report."""
    # Windows console defaults to cp1252 when redirected — force UTF-8 so
    # host diagnostics (which mention WebView2 → arrows) never crash.
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ok = True
    print("CAT doctor")
    print("=" * 60)

    exe = sys.executable
    venv = getattr(sys, "prefix", "") != getattr(sys, "base_prefix", "")
    env_kind = ("virtualenv/venv: " + sys.prefix) if venv else \
        "global interpreter"
    store = "windowsapps" in exe.lower()
    print(f"[1] Python      : {exe}")
    print(f"    Environment : {env_kind}")
    if store:
        print("                  (Microsoft Store Python)")
    ver = _dist_version()
    print(f"[2] CAT package : "
          + (f"installed, version {ver}" if ver
             else "NOT installed for this interpreter "
                  "(run: pip install -e .)"))
    if not ver:
        ok = False

    launcher = find_launcher()
    scripts = _scripts_dirs()
    print(f"[3] Launcher    : {launcher or 'NOT FOUND'}")
    for d in scripts:
        on_process = d.lower() in [e.lower() for e in _path_entries()]
        upath = _registry_user_path() or ""
        on_user = d.lower() in [p.strip().lower()
                                for p in upath.split(os.pathsep)]
        mpath = _registry_machine_path() or ""
        on_machine = d.lower() in [p.strip().lower()
                                   for p in mpath.split(os.pathsep)]
        state = ("process PATH" if on_process else
                 "user PATH (new terminals OK)" if on_user else
                 "machine PATH (new terminals OK)" if on_machine else
                 "NOT ON PATH")
        print(f"    Scripts dir : {d}")
        print(f"                  -> {state}")
        if not (on_process or on_user or on_machine):
            ok = False
    if not launcher and ver:
        ok = False
        print("    Fix: reinstall with `pip install -e .` from the "
              "CAT project folder.")

    if sys.platform == "win32":
        print("[4] PowerShell  : built-in alias `cat -> Get-Content` "
              "shadows cat.exe")
        prof = _profile_paths()
        patched = any(
            os.path.isfile(p) and _MARK_BEGIN in open(
                p, encoding="utf-8-sig", errors="ignore").read()
            for p in prof)
        print(f"    Profile fix : {'applied' if patched else 'not applied'}"
              f" ({', '.join(prof)})")
        if not patched:
            ok = False
            print("    Effect      : inside PowerShell, typing `cat` runs"
                  " Get-Content,")
            print("                  NOT the CAT app. cmd.exe / Windows"
                  " Terminal (cmd) are unaffected.")
    else:
        print("[4] Unix note   : /usr/bin/cat (coreutils) keeps winning"
              " over cat")
        print("                  in bash/zsh. Use a shell alias"
              " (`alias cat=cat-ai`) or")
        print("                  launch via the full path to your"
              " bin dir.")

    # --- CAT Host (embedded Browser) diagnostics -------------------------
    print("[5] CAT Host    : unified Terminal + Browser window (embedded WebView2/Chromium)")
    try:
        from .host.launcher import get_host_status  # type: ignore
        st = get_host_status()
        if st["available"]:
            print(f"    Engines     : {', '.join(st['engines'])}")
            print(f"    Preferred   : {st['preferred']}")
            if st["webview2_runtime"]:
                print(f"    WebView2    : {st['webview2_runtime']} (Edge WebView2 Runtime — Windows)")
            else:
                print("    WebView2    : not detected (Edge runtime missing — install Edge)")
            # Embedded check: Qt means truly inside CAT window
            has_qt = any("Qt" in e for e in st["engines"])
            if has_qt:
                print("    Mode        : EMBEDDED — Browser renders INSIDE CAT window (QWebEngineView child)")
            elif any("pywebview" in e.lower() or "webview" in e.lower() for e in st["engines"]):
                print("    Mode        : pywebview/WebView2 window (real rendering, standalone window)")
            else:
                print("    Mode        : Playwright external Chromium window (real rendering, but not embedded)")
                print("    Fix         : pip install PySide6  →  true embedded browser inside CAT Host")
        else:
            print(f"    Status      : {st['reason']}")
            print("    Install     : pip install PySide6  (QWebEngineView embedded — the ONLY correct engine for Browser INSIDE CAT)")
            print("                DO NOT use: pywebview/playwright separate-window fallbacks (not embedded)")
            ok = False
    except Exception as e:
        print(f"    Status      : host diagnostics failed ({e})")

    # --- CAT Terminal Tab / Window Identity ---------------------------
    print("[6] Terminal Tab: CAT CLI branding & icon identity")
    try:
        from . import terminal_identity
        ico = terminal_identity.get_icon_path()
        if ico and os.path.isfile(ico):
            print(f"    Icon asset  : {ico} ({os.path.getsize(ico)} bytes)")
        else:
            print("    Icon asset  : missing or unreadable")
            ok = False

        if sys.platform == "win32":
            wt_settings = terminal_identity.find_windows_terminal_settings()
            if wt_settings:
                import json
                try:
                    with open(wt_settings, "r", encoding="utf-8-sig") as f:
                        wt_data = json.load(f)
                    has_wt_profile = any(
                        p.get("guid") == terminal_identity.WT_CAT_GUID or p.get("name") == "CAT CLI"
                        for p in wt_data.get("profiles", {}).get("list", [])
                    )
                    if has_wt_profile:
                        print(f"    Win Terminal: CAT CLI profile configured in {wt_settings}")
                    else:
                        print(f"    Win Terminal: profile NOT found in {wt_settings}")
                        print("                  (run: cat --doctor --fix-terminal)")
                        ok = False
                except Exception as e:
                    print(f"    Win Terminal: error reading settings ({e})")
            else:
                print("    Win Terminal: settings.json not found (default conhost or not installed)")
        print(f"    Default Title: {terminal_identity.DEFAULT_TITLE}")
    except Exception as e:
        print(f"    Terminal Tab: {e}")

    print("Fomoji Identity & Dependencies:")
    try:
        from .fomoji_manager import detect_nodejs, locate_fomoji_server_dir, check_server_reachable
        node_env = detect_nodejs()
        if node_env.installed:
            print(f"    Node.js     : {node_env.node_version} ({node_env.node_path})")
            print(f"    npm         : v{node_env.npm_version} ({node_env.npm_path})")
        else:
            print(f"    Node.js     : Missing (Fomoji offline: {node_env.error})")
        server_dir = locate_fomoji_server_dir()
        if server_dir:
            print(f"    Server Path : {server_dir}")
        else:
            print("    Server Path : Not located")
        is_running = check_server_reachable(timeout=1.5)
        print(f"    Server State: {'Running / Active' if is_running else 'Offline (will auto-start when needed)'}")
    except Exception as e:
        print(f"    Fomoji Check: {e}")

    print("Git Synchronization:")
    try:
        from .git_sync import inspect_repository
        repo_info = inspect_repository()
        if repo_info.is_repo:
            print(f"    Git Branch  : {repo_info.current_branch}")
            print(f"    Git Remote  : {repo_info.remote_url or 'None'}")
            print(f"    Worktree    : {'Changes detected (cat push to sync)' if repo_info.has_changes else 'Clean / In sync'}")
        else:
            print(f"    Git Status  : {repo_info.error}")
    except Exception as e:
        print(f"    Git Status  : {e}")

    print("=" * 60)
    if ok:
        print("Everything looks good. Run `cat` from any terminal.")
        print("On Windows for real browser inside CAT:  cat --host  or  cat --host-browser")
    else:
        print("Problems detected. Suggested fixes:")
        print("  python -m calc_terminal.doctor --fix-path"
              "        # add Scripts dir to user PATH")
        print("  python -m calc_terminal.doctor --fix-powershell"
              "   # let cat.exe beat the PS alias")
        print("  python -m calc_terminal.doctor --fix-terminal"
              "     # configure Windows Terminal profile & icon")
        print("  pip install PySide6                                    # CAT Host embedded browser")

    if fix:
        print()
        if sys.platform == "win32":
            upath = _registry_user_path() or ""
            need_path = any(
                d.lower() not in [p.strip().lower()
                                  for p in upath.split(os.pathsep)]
                for d in scripts)
            if need_path:
                rc = fix_path()
                if rc == 0:
                    ok = True
            patched = any(
                os.path.isfile(p) and _MARK_BEGIN in open(
                    p, encoding="utf-8-sig", errors="ignore").read()
                for p in prof)
            if not patched:
                rc = fix_powershell()
                if rc == 0:
                    ok = True
            rc_term = fix_terminal()
            if rc_term == 0:
                ok = True
    return 0 if ok else 1


def fix_terminal() -> int:
    """Ensure the CAT icon is generated and register the CAT CLI profile in Windows Terminal."""
    try:
        from . import terminal_identity
        ico = terminal_identity.get_icon_path()
        if not ico:
            print("  [x] Could not generate or locate CAT icon (.ico).")
            return 1
        print(f"  [v] CAT icon ready: {ico}")
        if sys.platform == "win32":
            ok, msg = terminal_identity.configure_windows_terminal_profile()
            if ok:
                print(f"  [v] {msg}")
            else:
                print(f"  [!] {msg}")
        return 0
    except Exception as e:
        print(f"  [x] Terminal fix failed: {e}")
        return 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    fix_path_flag = "--fix-path" in argv
    fix_ps_flag = "--fix-powershell" in argv
    fix_terminal_flag = "--fix-terminal" in argv
    yes = "--yes" in argv or "-y" in argv
    if fix_path_flag or fix_ps_flag or fix_terminal_flag:
        rc = 0
        if fix_path_flag:
            rc |= fix_path(assume_yes=yes)
        if fix_ps_flag:
            rc |= fix_powershell(assume_yes=yes)
        if fix_terminal_flag:
            rc |= fix_terminal()
        return rc
    return report(fix="--fix" in argv)


if __name__ == "__main__":
    raise SystemExit(main())

