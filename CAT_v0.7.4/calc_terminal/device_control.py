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

import shutil
import time

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
    """Extension-point providers (desktop/android/ios/browser): they
    exist so the framework is complete and the permission/logging
    machinery is real, but `available()` stays False until an actual
    driver module is implemented."""

    def available(self):
        return False

    def plan(self, action, params):
        return {"action": action,
                "target": str(params.get("target", "")),
                "effect": f"{self.label} automation is not available in this build "
                          "(no driver module registered).",
                "command": None}


class _Desktop(_ScaffoldedProvider):
    key = "desktop"
    label = "Desktop"
    description = "Desktop automation (mouse/keyboard/windows) — extension point."


class _Android(_ScaffoldedProvider):
    key = "android"
    label = "Android"
    description = "Android automation via adb — extension point (drivers: adb)."

    def available(self):
        return bool(shutil.which("adb")) and False  # scaffolded: no driver yet


class _IOS(_ScaffoldedProvider):
    key = "ios"
    label = "iOS"
    description = "iOS automation where platform APIs allow — extension point."


class _Browser(_ScaffoldedProvider):
    key = "browser"
    label = "Browser"
    description = "Browser automation — extension point (drivers: playwright/selenium)."


PROVIDERS = {
    p.key: p for p in (
        TerminalProvider(), SimulationProvider(), _Desktop(), _Android(),
        _IOS(), _Browser())
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
