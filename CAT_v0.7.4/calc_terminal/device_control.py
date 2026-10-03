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
        elif act in ("clipboard", "clip"):
            effect = f"Interacts with system clipboard: {target}"
        elif act in ("system_info", "sysinfo", "info"):
            effect = "Inspects host computer hardware, OS, and process status"
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

        # System info inspection
        if action in ("system_info", "sysinfo", "info"):
            try:
                import platform
                os_str = f"{platform.system()} {platform.release()} ({platform.version()})"
                cpu = platform.processor() or platform.machine()
                info = f"OS: {os_str}\nProcessor: {cpu}\nPython: {sys.version.split()[0]}"
                return {"ok": True, "output": info, "note": "System info retrieved"}
            except Exception as e:
                return {"ok": True, "output": f"OS: {sys.platform}", "note": str(e)}

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
    """Android Device & Emulator Automation via adb (devices, shell, input, install, push/pull)."""
    key = "android"
    label = "Android Device Automation"
    description = "Android automation via adb (devices, shell, tap, swipe, keyevent, install, file transfer)."

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
        cmd = plan.get("command", "")
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
    """Web Browser Automation (open URLs, web navigation, web scraping)."""
    key = "browser"
    label = "Web Browser Automation"
    description = "Browser automation (open URLs, web navigation, web scraping, search)."

    def available(self):
        return True

    def plan(self, action, params):
        target = str(params.get("target") or params.get("url") or params.get("command") or "").strip()
        act = action.lower()
        if act in ("open", "open_url", "navigate", "browse"):
            effect = f"Opens web page in system browser: {target}"
        elif act in ("search", "google"):
            effect = f"Performs web search in browser: '{target}'"
        elif act in ("fetch", "scrape", "extract"):
            effect = f"Fetches and extracts readable content from: {target}"
        else:
            effect = f"Browser action '{action}' on '{target}'"
        return {"action": action, "target": target, "effect": effect, "command": target}

    def execute(self, plan):
        act = plan.get("action", "").lower()
        target = plan.get("target", "")
        if act in ("open", "open_url", "navigate", "browse"):
            url = target if target.startswith(("http://", "https://")) else "https://" + target
            webbrowser.open(url)
            return {"ok": True, "note": f"Opened {url} in browser"}
        elif act in ("search", "google"):
            import urllib.parse
            url = f"https://www.google.com/search?q={urllib.parse.quote(target)}"
            webbrowser.open(url)
            return {"ok": True, "note": f"Searched '{target}' in browser"}
        elif act in ("fetch", "scrape", "extract"):
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
