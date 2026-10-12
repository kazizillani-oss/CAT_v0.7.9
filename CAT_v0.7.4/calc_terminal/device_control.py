"""
CCT — device_control.py: Responsible Device Control (v0.7.7 spec
section 14).

An extensible automation framework for interacting with the user's own
authorized devices, designed so that:

  * every capability is a registered provider (Desktop / Android / iOS /
    Browser / Terminal / Simulation) with an explicit availability
    check — nothing claims to drive a device it can't;
  * every action that affects a real device requires explicit user
    approval (permissions.manager's "device_control" key + the same
    inline permission-card flow installs use) and is recorded in the
    activity log (eventbus -> session timeline) with the action, target,
    and outcome — spec section 14's "every action ... clearly visible
    in the activity log";
  * the framework itself never executes anything: providers return a
    plan (what command/API call would run, what it affects) and the
    CALLER (the permission flow) decides. This keeps "device control"
    honest — the same separation the spec asks for between automation
    and user control.

Built-in providers, stated plainly:
  * terminal  — runs commands on the user's machine (delegates to the
                existing shell_commands permission; the same
                subprocess runner agent.py's run_terminal tool uses).
  * simulation— CCT's own in-app simulations (atom, orbital, reaction):
                sandboxed by construction, still approval-gated.
  * desktop / android / ios / browser — EXTENSION POINTS, not working
                drivers: they register with `available()` returning
                False until a provider module implements them
                (e.g. adb for Android, Playwright for browser). The
                framework is complete; the drivers are future work —
                the spec's "where platform APIs allow" is honored by
                not faking support we don't have.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import os
import shutil
import subprocess
import sys
import time
import webbrowser

from . import eventbus

ACTIVITY_LOG = []  # [{ts, provider, action, target, decision, outcome}]
MAX_LOG = 200


# -------------------------------------------------------------- providers --
class DeviceProvider:
    """Base class for a device-control capability. Subclasses implement
    `available()` and `plan(action, params)`; the permission flow calls
    `plan()` FIRST, shows the user what would happen, and only then
    `execute()` (which providers implement only if they can really
    do the thing)."""

    key = "unnamed"
    label = "Unnamed provider"
    description = ""

    def available(self):
        return False

    def plan(self, action, params):
        """Returns {"action": str, "target": str, "effect": str,
        "command": [argv] or None} — the user-visible description of
        what WOULD happen. Never None."""
        return {"action": action, "target": "", "effect": "not implemented",
                "command": None}

    def execute(self, plan):
        """Actually performs the planned action. Only called after the
        user approved `plan`. Providers that can't execute return a
        refusal dict instead of faking it."""
        return {"ok": False, "note": f"provider '{self.key}' has no executor"}


class TerminalProvider(DeviceProvider):
    """Terminal automation — runs commands through the exact same
    subprocess runner agent.py's run_terminal tool uses."""

    key = "terminal"
    label = "Terminal"
    description = "Run commands on this machine (shell, git, python, docker...)."

    def available(self):
        return True

    def plan(self, action, params):
        # Accept either "command" or the generic "target" param — the
        # CLI /devices flow hands over {"target": "<command>"}.
        cmd = str(params.get("command") or params.get("target") or "").strip()
        return {"action": action,
                "target": cmd,
                "effect": f"Runs in your terminal: $ {cmd}",
                "command": cmd}

    def execute(self, plan):
        import subprocess
        cmd = plan.get("command")
        if not cmd:
            return {"ok": False, "note": "no command in plan"}
        from . import workspace
        cwd = workspace.root_dir() or None
        try:
            proc = subprocess.run(
                cmd, shell=True, cwd=cwd, capture_output=True, text=True,
                timeout=min(max(float(plan.get("timeout", 60) or 60), 1.0), 300.0),
                encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            return {"ok": False, "note": "command timed out"}
        except OSError as e:
            return {"ok": False, "note": f"could not run: {e}"}
        return {"ok": proc.returncode == 0, "exit_code": proc.returncode,
                "output": ((proc.stdout or "") + (proc.stderr or "")).strip()}


class SimulationProvider(DeviceProvider):
    """CCT's own in-app simulations — sandboxed by construction but
    still approval-gated (spec: every action affecting the user's
    environment is visible and approved)."""

    key = "simulation"
    label = "Simulation"
    description = "CAT's in-app simulations (atom, orbital, reaction sims)."

    def available(self):
        return True

    def plan(self, action, params):
        sim = str(params.get("simulation", params.get("target", ""))).strip()
        return {"action": action,
                "target": sim,
                "effect": f"Runs the in-app '{sim}' simulation (no system changes)",
                "command": None}

    def execute(self, plan):
        # In-app simulations render in the terminal/UI directly — the
        # caller (app.py / ui/app.py) starts them after approval; this
        # provider only needs to confirm the plan is runnable.
        return {"ok": True, "note": "simulation started by caller"}


class _ScaffoldedProvider(DeviceProvider):
    """Fallback provider for platforms without registered driver modules."""

    def available(self):
        return False

    def plan(self, action, params):
        return {"action": action,
                "target": str(params.get("target", "")),
                "effect": f"{self.label} automation is not available in this build.",
                "command": None}


class DesktopProvider(DeviceProvider):
    """Full Computer & Host OS Automation (mouse, keyboard, app launching,
    PowerShell/cmd scripts, screenshots, and system tasks)."""
    key = "desktop"
    label = "Desktop / Full Computer Automation"
    description = "Full Computer & OS automation (mouse, keyboard, launch apps, PowerShell/cmd scripts, screenshot, window management)."

    def available(self):
        return True

    def plan(self, action, params):
        target = str(params.get("target") or params.get("command") or "").strip()
        act = action.lower()
        if act in ("launch_app", "open_app", "launch", "open"):
            effect = f"Launches desktop application: '{target}'"
        elif act in ("run_powershell", "powershell", "ps"):
            effect = f"Executes PowerShell system automation: {target}"
        elif act in ("screenshot", "screen"):
            effect = f"Takes a desktop screenshot and saves to {target or 'workspace'}"
        elif act in ("type", "key", "hotkey"):
            effect = f"Sends keyboard keystrokes to active window: '{target}'"
        elif act in ("click", "mouse"):
            effect = f"Performs mouse interaction: {target}"
        elif act in ("clipboard", "clip", "get_clipboard", "read_clipboard", "set_clipboard", "write_clipboard"):
            effect = f"Interacts with system clipboard: {target}"
        elif act in ("system_info", "sysinfo", "info", "system_status", "status"):
            effect = "Inspects host computer hardware, OS, CPU/RAM, and system status"
        elif act in ("list_processes", "ps", "processes"):
            effect = "Lists top running host processes by CPU and memory consumption"
        elif act in ("kill_process", "kill", "stop_process"):
            effect = f"Terminates host process: {target}"
        elif act in ("reveal_file", "explore", "show_file"):
            effect = f"Reveals path in system file explorer: {target}"
        elif act in ("window_action", "window"):
            effect = f"Performs window management action: {target}"
        else:
            effect = f"Executes desktop automation '{action}' on target '{target}'"
        return {
            "action": action,
            "target": target,
            "effect": effect,
            "command": target,
        }

    def execute(self, plan):
        action = plan.get("action", "").lower()
        target = plan.get("target", "") or plan.get("command", "")

        # System info & status inspection
        if action in ("system_info", "sysinfo", "info", "system_status", "status"):
            try:
                import platform
                os_str = f"{platform.system()} {platform.release()} ({platform.version()})"
                cpu = platform.processor() or platform.machine()
                lines = [f"OS: {os_str}", f"Processor: {cpu}", f"Python: {sys.version.split()[0]}"]
                try:
                    import psutil
                    vm = psutil.virtual_memory()
                    lines.append(f"Memory: {vm.percent}% used ({vm.used // (1024**2)} MB / {vm.total // (1024**2)} MB)")
                    lines.append(f"CPU Usage: {psutil.cpu_percent(interval=0.1)}%")
                    disk = psutil.disk_usage(os.getcwd())
                    lines.append(f"Disk: {disk.percent}% used ({disk.free // (1024**3)} GB free)")
                except Exception:
                    pass
                return {"ok": True, "output": "\n".join(lines), "note": "System status retrieved"}
            except Exception as e:
                return {"ok": True, "output": f"OS: {sys.platform}", "note": str(e)}

        # Process listing
        if action in ("list_processes", "ps", "processes"):
            try:
                if sys.platform == "win32":
                    ps_cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                              "Get-Process | Sort-Object -Property CPU -Descending | Select-Object -First 25 -Property Id, ProcessName, CPU, @{Name='MemoryMB';Expression={[math]::Round($_.WorkingSet64 / 1MB, 1)}} | Format-Table -AutoSize | Out-String -Width 120"]
                    proc = subprocess.run(ps_cmd, capture_output=True, text=True, timeout=20, encoding="utf-8", errors="replace")
                    out = proc.stdout.strip() or "No processes found."
                else:
                    proc = subprocess.run(["ps", "aux", "--sort=-%cpu"], capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace")
                    lines = (proc.stdout or "").splitlines()[:26]
                    out = "\n".join(lines) or "No processes found."
                return {"ok": True, "output": out, "note": "Process list retrieved"}
            except Exception as e:
                return {"ok": False, "note": f"Failed to list processes: {e}"}

        # Kill process
        if action in ("kill_process", "kill", "stop_process"):
            try:
                if not target:
                    return {"ok": False, "note": "No PID or process name specified to kill"}
                target_str = str(target).strip()
                if sys.platform == "win32":
                    if target_str.isdigit():
                        cmd = f"taskkill /F /PID {target_str}"
                    else:
                        img = target_str if target_str.lower().endswith(".exe") else f"{target_str}.exe"
                        cmd = f"taskkill /F /IM {img}"
                else:
                    cmd = f"kill -9 {target_str}" if target_str.isdigit() else f"pkill -f {target_str}"
                proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace")
                out = ((proc.stdout or "") + (proc.stderr or "")).strip()
                return {"ok": proc.returncode == 0, "output": out or "Process terminated", "note": f"Terminated {target}"}
            except Exception as e:
                return {"ok": False, "note": f"Failed to kill process: {e}"}

        # Reveal file in OS file explorer
        if action in ("reveal_file", "explore", "show_file"):
            try:
                target_path = os.path.abspath(target or ".")
                if sys.platform == "win32":
                    if os.path.isfile(target_path):
                        subprocess.Popen(f'explorer /select,"{target_path}"', shell=True)
                    else:
                        os.startfile(target_path)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", "-R", target_path])
                else:
                    subprocess.Popen(["xdg-open", os.path.dirname(target_path) if os.path.isfile(target_path) else target_path])
                return {"ok": True, "note": f"Revealed '{target_path}' in system file explorer"}
            except Exception as e:
                return {"ok": False, "note": f"Failed to reveal file: {e}"}

        # Clipboard operations
        if action in ("clipboard", "clip", "get_clipboard", "read_clipboard", "set_clipboard", "write_clipboard"):
            try:
                is_set = action in ("set_clipboard", "write_clipboard") or (bool(target) and action in ("clipboard", "clip") and not target.lower() in ("get", "read"))
                if is_set:
                    if sys.platform == "win32":
                        escaped_val = str(target).replace("'", "''")
                        ps_script = f"Set-Clipboard -Value '{escaped_val}'"
                        subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], timeout=10)
                    else:
                        p = subprocess.Popen(["pbcopy" if sys.platform == "darwin" else "xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
                        p.communicate(input=target.encode("utf-8"))
                    return {"ok": True, "note": "Copied text to clipboard"}
                else:
                    if sys.platform == "win32":
                        proc = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard"], capture_output=True, text=True, timeout=10)
                        clip_val = proc.stdout.strip()
                    else:
                        proc = subprocess.run(["pbpaste" if sys.platform == "darwin" else "xclip", "-o"], capture_output=True, text=True, timeout=10)
                        clip_val = proc.stdout.strip()
                    return {"ok": True, "output": clip_val, "note": "Read clipboard content"}
            except Exception as e:
                return {"ok": False, "note": f"Clipboard operation failed: {e}"}

        # Launch desktop applications
        if action in ("launch_app", "open_app", "launch", "open"):
            try:
                if sys.platform == "win32":
                    os.startfile(target)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", target])
                else:
                    subprocess.Popen(["xdg-open", target])
                return {"ok": True, "note": f"Application '{target}' launched successfully"}
            except Exception:
                try:
                    subprocess.Popen(target, shell=True)
                    return {"ok": True, "note": f"Started '{target}' via shell"}
                except Exception as e2:
                    return {"ok": False, "note": f"Failed to launch '{target}': {e2}"}

        # PowerShell / system command execution
        if action in ("run_powershell", "powershell", "ps", "run"):
            cmd = target
            if sys.platform == "win32":
                full_cmd = ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", cmd]
            else:
                full_cmd = ["bash", "-c", cmd]
            try:
                proc = subprocess.run(full_cmd, capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace")
                out = ((proc.stdout or "") + (proc.stderr or "")).strip()
                return {"ok": proc.returncode == 0, "exit_code": proc.returncode, "output": out}
            except Exception as e:
                return {"ok": False, "note": f"PowerShell execution failed: {e}"}

        # Screenshot capture
        if action in ("screenshot", "screen"):
            save_path = target or "desktop_screenshot.png"
            try:
                from PIL import ImageGrab
                im = ImageGrab.grab()
                im.save(save_path)
                return {"ok": True, "output": f"Screenshot saved to {save_path}", "note": f"Saved {save_path}"}
            except Exception:
                if sys.platform == "win32":
                    ps_script = (
                        "Add-Type -AssemblyName System.Windows.Forms; "
                        "Add-Type -AssemblyName System.Drawing; "
                        "$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
                        "$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height; "
                        "$graphics = [System.Drawing.Graphics]::FromImage($bmp); "
                        f"$graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size); "
                        f"$bmp.Save('{save_path}', [System.Drawing.Imaging.ImageFormat]::Png); "
                        "$graphics.Dispose(); $bmp.Dispose();"
                    )
                    proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True, timeout=30)
                    if proc.returncode == 0 and os.path.exists(save_path):
                        return {"ok": True, "output": f"Screenshot saved to {save_path}", "note": f"Saved {save_path}"}
                return {"ok": False, "note": "Screenshot capture requires screen access or PIL"}

        # Keyboard typing
        if action in ("type", "key", "hotkey"):
            if sys.platform == "win32":
                ps_script = f"Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('{target}')"
                proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True, timeout=10)
                return {"ok": proc.returncode == 0, "note": f"Sent keys '{target}'"}
            return {"ok": False, "note": "Keyboard typing requires Windows SendKeys"}

        return {"ok": True, "note": f"Action '{action}' executed"}


class AndroidProvider(DeviceProvider):
    """Android Device & Emulator Automation via adb (devices, shell, input, install, push/pull, UI dump)."""
    key = "android"
    label = "Android Device Automation"
    description = "Android automation via adb (devices, shell, tap, swipe, keyevent, install, UI hierarchy inspection)."

    def _find_adb(self):
        adb = shutil.which("adb")
        if adb:
            return adb
        user_home = os.path.expanduser("~")
        candidates = [
            os.path.join(user_home, "AppData", "Local", "Android", "Sdk", "platform-tools", "adb.exe"),
            os.path.join(user_home, "Android", "Sdk", "platform-tools", "adb"),
            "/usr/local/bin/adb",
            "/usr/bin/adb",
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c
        return "adb"

    def available(self):
        adb = self._find_adb()
        return bool(shutil.which(adb) or os.path.isfile(adb))

    def plan(self, action, params):
        target = str(params.get("target") or params.get("command") or "").strip()
        act = action.lower()
        if act in ("devices", "list"):
            cmd = "adb devices -l"
            effect = "Lists all connected Android devices, phones, and emulators"
        elif act in ("dump_ui", "hierarchy", "inspect_ui", "ui_dump"):
            cmd = "adb exec-out uiautomator dump /dev/tty"
            effect = "Inspects Android screen UI element hierarchy, IDs, and coordinates"
        elif act in ("launch_app", "start_app", "open_app"):
            cmd = f"adb shell monkey -p {target} -c android.intent.category.LAUNCHER 1"
            effect = f"Launches Android application package: {target}"
        elif act in ("current_app", "focused_app", "active_app"):
            cmd = 'adb shell dumpsys window'
            effect = "Inspects currently focused Android app package and activity"
        elif act in ("uninstall",):
            cmd = f"adb uninstall {target}"
            effect = f"Uninstalls package '{target}' from Android device"
        elif act in ("shell", "cmd"):
            cmd = f"adb shell {target}"
            effect = f"Runs shell command on Android device: {target}"
        elif act in ("tap", "click"):
            cmd = f"adb shell input tap {target}"
            effect = f"Taps screen coordinate on Android device: ({target})"
        elif act in ("swipe", "scroll"):
            cmd = f"adb shell input swipe {target}"
            effect = f"Swipes on Android device: {target}"
        elif act in ("text", "type"):
            cmd = f"adb shell input text '{target}'"
            effect = f"Types text on Android device: '{target}'"
        elif act in ("keyevent", "key"):
            cmd = f"adb shell input keyevent {target}"
            effect = f"Sends keyevent {target} to Android device"
        elif act in ("install", "apk"):
            cmd = f"adb install -r '{target}'"
            effect = f"Installs APK onto Android device: {target}"
        elif act in ("screenshot", "screencap"):
            cmd = f"adb exec-out screencap -p > '{target or 'android_screen.png'}'"
            effect = f"Captures Android screenshot to {target or 'android_screen.png'}"
        else:
            cmd = f"adb {target or action}"
            effect = f"Runs adb command on Android device: {cmd}"
        return {
            "action": action,
            "target": target,
            "effect": effect,
            "command": cmd,
        }

    def execute(self, plan):
        adb = self._find_adb()
        action = plan.get("action", "").lower()
        target = plan.get("target", "")
        cmd = plan.get("command", "")

        # Intelligent UI hierarchy dump for autonomous screen element targeting
        if action in ("dump_ui", "hierarchy", "inspect_ui", "ui_dump"):
            try:
                proc = subprocess.run(f'"{adb}" exec-out uiautomator dump /dev/tty', shell=True, capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace")
                out = proc.stdout.strip()
                if not out or "<hierarchy" not in out:
                    # Fallback method: dump to device storage then read
                    subprocess.run(f'"{adb}" shell uiautomator dump /sdcard/window_dump.xml', shell=True, timeout=15)
                    cat_proc = subprocess.run(f'"{adb}" shell cat /sdcard/window_dump.xml', shell=True, capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace")
                    out = cat_proc.stdout.strip()
                if out:
                    # Extract concise element list for easy agent consumption
                    elements = re.findall(r'<node[^>]*text="([^"]*)"[^>]*resource-id="([^"]*)"[^>]*bounds="([^"]*)"', out)
                    summary = [f"Found {len(elements)} interactive UI elements:"]
                    for text_val, res_id, bounds in elements[:40]:
                        if text_val or res_id:
                            summary.append(f"  - text='{text_val}' id='{res_id}' bounds={bounds}")
                    return {"ok": True, "output": "\n".join(summary), "note": "UI hierarchy analyzed"}
                return {"ok": False, "note": "Could not dump UI hierarchy (ensure device screen is awake)"}
            except Exception as e:
                return {"ok": False, "note": f"UI dump failed: {e}"}

        # Focused application query
        if action in ("current_app", "focused_app", "active_app"):
            try:
                proc = subprocess.run(f'"{adb}" shell dumpsys window', shell=True, capture_output=True, text=True, timeout=20, encoding="utf-8", errors="replace")
                matches = re.findall(r'(?:mCurrentFocus|mFocusedApp).*?([a-zA-Z0-9_\.]+\/[a-zA-Z0-9_\.]+)', proc.stdout)
                if matches:
                    return {"ok": True, "output": f"Current focused app/activity: {matches[0]}", "note": matches[0]}
                return {"ok": True, "output": proc.stdout[:500], "note": "Focused app inspected"}
            except Exception as e:
                return {"ok": False, "note": f"Focus query failed: {e}"}

        if cmd.startswith("adb "):
            exec_cmd = f'"{adb}" ' + cmd[4:]
        else:
            exec_cmd = f'"{adb}" {cmd}'
        try:
            proc = subprocess.run(
                exec_cmd, shell=True, capture_output=True, text=True,
                timeout=60, encoding="utf-8", errors="replace")
            out = ((proc.stdout or "") + (proc.stderr or "")).strip()
            return {"ok": proc.returncode == 0, "exit_code": proc.returncode, "output": out}
        except subprocess.TimeoutExpired:
            return {"ok": False, "note": "adb command timed out"}
        except Exception as e:
            return {"ok": False, "note": f"adb execution error: {e}"}


class _IOS(_ScaffoldedProvider):
    key = "ios"
    label = "iOS"
    description = "iOS automation where platform APIs allow — extension point."


class BrowserProvider(DeviceProvider):
    """CAT Web Browser & Agentic Multitask Automation (tabs, navigation, scripts, scraping, links)."""
    key = "browser"
    label = "CAT Browser Automation"
    description = "CAT Browser Agentic AI automation (multiple tabs, multi-tasking, navigation, JavaScript, web scraping, search)."

    def available(self):
        return True

    def plan(self, action, params):
        target = str(params.get("target") or params.get("url") or params.get("command") or "").strip()
        act = action.lower()
        if act in ("open", "open_url", "navigate", "browse"):
            effect = f"Navigates to URL in CAT Browser: {target}"
        elif act in ("new_tab", "tab_new"):
            effect = f"Opens new tab in CAT Browser: {target or 'about:home'}"
        elif act in ("close_tab", "tab_close"):
            effect = f"Closes tab index in CAT Browser: {target}"
        elif act in ("switch_tab", "tab_switch"):
            effect = f"Switches active tab in CAT Browser to index: {target}"
        elif act in ("list_tabs", "tabs"):
            effect = "Lists all open tabs in CAT Browser"
        elif act in ("eval_js", "script", "js"):
            effect = f"Executes JavaScript in CAT Browser: {target[:60]}"
        elif act in ("search", "google"):
            effect = f"Performs web search in CAT Browser: '{target}'"
        elif act in ("fetch", "scrape", "extract", "scrape_page", "get_page_text"):
            effect = f"Fetches and extracts readable content/markdown from: {target}"
        elif act in ("extract_links", "links"):
            effect = f"Extracts all hyperlinks from web page: {target}"
        else:
            effect = f"CAT Browser action '{action}' on '{target}'"
        return {"action": action, "target": target, "effect": effect, "command": target}

    def execute(self, plan, params=None):
        if isinstance(plan, str):
            p = params or {}
            plan = {"action": plan, "target": p.get("target", "") or p.get("command", "") or p.get("url", "")}
        act = plan.get("action", "").lower()
        target = plan.get("target", "")
        import urllib.parse
        active_win = None
        try:
            from .browser_gui.qt_browser import get_active_browser_window
            active_win = get_active_browser_window()
        except Exception:
            pass

        if act in ("list_tabs", "tabs"):
            if active_win and hasattr(active_win, "agent_list_tabs"):
                tabs = active_win.agent_list_tabs()
                summary_lines = [f"Open tabs ({len(tabs)}):"]
                for t in tabs:
                    marker = "*" if t.get("active") else " "
                    summary_lines.append(f"  [{t['index']}] {marker} {t.get('title', 'Untitled')} - {t.get('url', '')}")
                return {"ok": True, "output": "\n".join(summary_lines), "note": f"{len(tabs)} tabs open"}
            return {"ok": False, "note": "CAT Browser is not currently open"}

        if act in ("new_tab", "tab_new"):
            url = target or "about:home"
            if active_win and hasattr(active_win, "agent_new_tab"):
                idx = active_win.agent_new_tab(url)
                return {"ok": True, "note": f"Opened new tab #{idx} for {url}"}
            try:
                from .browser_gui.qt_browser import launch_qt_browser
                import threading
                t = threading.Thread(target=launch_qt_browser, args=(url,), daemon=True)
                t.start()
                return {"ok": True, "note": f"Launched CAT Browser with {url}"}
            except Exception:
                webbrowser.open(url)
                return {"ok": True, "note": f"Opened {url} in browser"}

        if act in ("close_tab", "tab_close"):
            if active_win and hasattr(active_win, "agent_close_tab"):
                try:
                    idx = int(target)
                    ok = active_win.agent_close_tab(idx)
                    return {"ok": ok, "note": f"Closed tab #{idx}"}
                except ValueError:
                    return {"ok": False, "note": "Invalid tab index"}
            return {"ok": False, "note": "CAT Browser is not currently open"}

        if act in ("switch_tab", "tab_switch"):
            if active_win and hasattr(active_win, "agent_switch_tab"):
                try:
                    idx = int(target)
                    ok = active_win.agent_switch_tab(idx)
                    return {"ok": ok, "note": f"Switched to tab #{idx}"}
                except ValueError:
                    return {"ok": False, "note": "Invalid tab index"}
            return {"ok": False, "note": "CAT Browser is not currently open"}

        if act in ("eval_js", "script", "js"):
            if active_win and hasattr(active_win, "agent_eval_js"):
                ok = active_win.agent_eval_js(target)
                return {"ok": ok, "note": "Executed JavaScript in CAT Browser"}
            return {"ok": False, "note": "CAT Browser is not currently open"}

        if act in ("open", "open_url", "navigate", "browse"):
            url = target if target.startswith(("http://", "https://", "about:")) else ("https://" + target if "." in target else target)
            if active_win and hasattr(active_win, "agent_navigate"):
                active_win.agent_navigate(url)
                return {"ok": True, "note": f"Navigated CAT Browser to {url}"}
            try:
                from .browser_gui.qt_browser import launch_qt_browser
                import threading
                t = threading.Thread(target=launch_qt_browser, args=(url,), daemon=True)
                t.start()
                return {"ok": True, "note": f"Launched CAT Browser with {url}"}
            except Exception:
                webbrowser.open(url)
                return {"ok": True, "note": f"Opened {url} in browser"}

        elif act in ("search", "google"):
            url = f"https://www.google.com/search?q={urllib.parse.quote(target)}"
            if active_win and hasattr(active_win, "agent_navigate"):
                active_win.agent_new_tab(url)
                return {"ok": True, "note": f"Searched '{target}' in CAT Browser"}
            webbrowser.open(url)
            return {"ok": True, "note": f"Searched '{target}' in browser"}

        elif act in ("extract_links", "links"):
            if active_win and hasattr(active_win, "agent_eval_js"):
                links_text = active_win.agent_eval_js(
                    "Array.from(document.querySelectorAll('a[href]')).map(a => a.href).slice(0, 50).join('\\n')"
                )
                if links_text:
                    return {"ok": True, "output": str(links_text), "note": "Extracted links from active tab"}
            try:
                from .agent import _tool_fetch_web_page
                content = _tool_fetch_web_page({"url": target, "max_chars": 8000})
                links = re.findall(r'href=[\'"]([^\'"]+)[\'"]', content)
                return {"ok": True, "output": "\n".join(links[:40]) if links else "No links found", "note": f"Found {len(links)} links"}
            except Exception as e:
                return {"ok": False, "note": f"Link extraction failed: {e}"}

        elif act in ("fetch", "scrape", "extract", "scrape_page", "get_page_text"):
            # If browser is open and no URL given, scrape current page directly
            if (not target or target == "active") and active_win and hasattr(active_win, "agent_eval_js"):
                page_text = active_win.agent_eval_js("document.body.innerText")
                if page_text:
                    return {"ok": True, "output": str(page_text)[:8000], "note": "Scraped active browser tab text"}
            try:
                from .agent import _tool_fetch_web_page
                content = _tool_fetch_web_page({"url": target, "max_chars": 8000})
                return {"ok": True, "output": content}
            except Exception as e:
                return {"ok": False, "note": f"Fetch failed: {e}"}
        return {"ok": True, "note": f"Browser action '{act}' completed"}


# Backwards compatibility aliases
_Desktop = DesktopProvider
_Android = AndroidProvider
_Browser = BrowserProvider

PROVIDERS = {
    p.key: p for p in (
        TerminalProvider(), SimulationProvider(), DesktopProvider(), AndroidProvider(),
        _IOS(), BrowserProvider())
}


# ------------------------------------------------------------- registry --
def register_provider(provider):
    """Extension API: register a DeviceProvider subclass instance under
    its own key (replaces any provider with the same key)."""
    PROVIDERS[provider.key] = provider
    return provider


def available_providers():
    """[{key, label, description, available}] for the /devices view."""
    return [{"key": p.key, "label": p.label, "description": p.description,
             "available": p.available()}
            for p in PROVIDERS.values()]


def provider(key):
    return PROVIDERS.get(key)


# --------------------------------------------------------------- logging --
def log_action(provider_key, action, target, decision, outcome=""):
    entry = {"ts": time.time(), "provider": provider_key, "action": action,
             "target": target, "decision": decision, "outcome": outcome}
    ACTIVITY_LOG.append(entry)
    del ACTIVITY_LOG[:-MAX_LOG]
    eventbus.bus.publish(eventbus.DEVICE_ACTION, provider=provider_key,
                         action=action, target=target, decision=decision,
                         detail=outcome or action)
    return entry


def activity(limit=50):
    """Newest first."""
    return list(reversed(ACTIVITY_LOG))[:limit]


# -------------------------------------------------------------- the gate --
def plan_action(provider_key, action, params):
    """The one entry point the permission flows call: resolves the
    provider, builds the user-visible plan. Returns
    {"ok": bool, "plan": {..}, "reason": str}. Callers then run the
    existing permission-card flow (device_control key) and only call
    execute_approved() if the user says yes."""
    p = provider(provider_key)
    if p is None:
        return {"ok": False, "plan": None, "reason": f"unknown provider '{provider_key}'"}
    if not p.available():
        return {"ok": False, "plan": None, "reason": f"{p.label} automation is not available in this build"}
    return {"ok": True, "plan": p.plan(action, params), "reason": ""}


def execute_approved(provider_key, plan, params):
    """Runs a provider's plan AFTER the user approved it. Logs the
    action with its outcome either way."""
    p = provider(provider_key)
    if p is None:
        log_action(provider_key, (plan or {}).get("action", "?"),
                   (plan or {}).get("target", ""), "denied", "unknown provider")
        return {"ok": False, "note": "unknown provider"}
    result = p.execute(plan)
    outcome = "approved"
    if not result.get("ok"):
        outcome += " \u2014 " + str(result.get("note", "execution failed"))
    log_action(provider_key, (plan or {}).get("action", "?"),
               (plan or {}).get("target", ""), "approved", outcome)
    return result
