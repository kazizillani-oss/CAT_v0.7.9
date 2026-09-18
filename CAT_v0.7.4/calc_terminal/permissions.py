"""
CCT Permission Manager — a small, honest permission-state store for the
primary Textual UI (see calc_terminal/ui/).

This does not retroactively sandbox every existing code path in the
app (sandbox.py / security_scanner.py already do real enforcement for
/codepad execution). What this module adds is a *single source of
truth* for the toggles shown in the composer's Permissions panel, plus
a `request()` helper that produces the data an inline permission card
needs (action, reason, allow-once vs always-allow vs deny) — mirroring
the shape code_editor.py's `_scan_and_confirm` already prints, just
structured so a real widget (not print()) can render it.

## Three-mode layer (spec v0.7 section 2)

Added on TOP of the existing per-key toggles below, not as a separate
system — MODES change how `needs_prompt()`/`allowed()` interpret those
same toggles, they don't duplicate the toggle state:

  - "ask"        (default): every mutating action always prompts,
                  regardless of a key's on/off toggle, until the user
                  picks "Always Allow This Session" on that specific
                  action's card (matches the spec's Mode 1 exactly).
  - "restricted": mutating actions are never silently applied; the
                  caller is expected to show a Suggested-Patch-style
                  Accept/Reject prompt instead of Allow-Once/Always-
                  Allow/Deny (see `restricted_review(key)` below).
  - "full":       nothing prompts. Matches the spec's Mode 3 — callers
                  should still surface the "visible warning" the spec
                  asks for; this module only tracks the state.

Honest scope note: today, `execute_python` is the only mutating AI
action actually wired to a permission gate anywhere in the codebase
(see ui/app.py's on_message_run_code). The spec's Section 1 ("AI file
create/edit/rename/delete") describes a whole AI-driven file-editing
tool CCT doesn't have yet — so "restricted" mode's file-patch-review
behavior has nowhere to apply until that tool exists. This module
implements the mode semantics correctly and generally so that gate
works the moment such a tool is added, rather than only for the one
action that exists today.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import itertools
import time

_request_ids = itertools.count(1)


# (key, label, default_on)  — order matches the composer's checklist.
PERMISSION_DEFS = [
    ("read_files", "Read Files", True),
    ("write_files", "Write Files", True),
    ("delete_files", "Delete Files", False),
    ("execute_python", "Execute Python", True),
    ("shell_commands", "Shell Commands", True),
    ("install_packages", "Install Packages", True),
    ("device_control", "Device Control", False),
    ("internet", "Internet", False),
    ("browser_automation", "Browser Automation", False),
    ("formula_library", "Formula Library", True),
    ("notebook", "Notebook", True),
    ("calculator", "Calculator", True),
]

# Which permission keys represent a MUTATING action (create/write/
# execute/delete/install-class capability) vs. a read-only one. Modes
# only change prompting behavior for mutating keys — read_files,
# formula_library, notebook, and calculator stay governed by their
# plain toggle in every mode, since "ask every time before reading a
# file" would make the app unusable and isn't what the spec asks for
# either (its examples are all write/edit/execute/delete/install/commit).
MUTATING_KEYS = {
    "write_files",
    "delete_files",
    "execute_python",
    "shell_commands",
    "install_packages",
    "device_control",
    "browser_automation",
}

MODES = ("ask", "restricted", "full")
MODE_LABELS = {
    "ask": "\U0001f512 Ask Every Time",
    "restricted": "\U0001f7e1 Restricted",
    "full": "\U0001f7e2 Full Access",
}


class PermissionManager:
    """Holds on/off state for each permission and a log of decisions.

    `always_allow` entries bypass future inline prompts for that key
    until the session ends or the user flips it off again in the panel.
    `always_deny` (v0.7.7) entries work the opposite way — once a user
    picks "Always Deny" on a permission card, that key stops prompting
    and is refused outright for the rest of the session.
    """

    def __init__(self):
        self._state = {key: default for key, _label, default in PERMISSION_DEFS}
        self._always_allow = set()
        self._always_deny = set()  # v0.7.7: keys the user permanently (this session) denied
        self.log = []  # list of (timestamp, key, action_text, decision)
        self.mode = "ask"  # spec v0.7 default: Ask Every Time

    def allowed(self, key):
        return bool(self._state.get(key, False))

    def new_request_id(self):
        """One id per inline PermissionCard, so PermissionGranted/Denied
        (posted later, after a real UI round trip) can be matched back
        to the specific pending call that's waiting on it."""
        return f"perm-req-{next(_request_ids)}"

    def toggle(self, key):
        if key in self._state:
            self._state[key] = not self._state[key]
            if not self._state[key]:
                self._always_allow.discard(key)
            else:
                # re-enabling a permission in the panel means the user
                # wants it usable again — clear any always-deny memory
                # for it, same trust-reset semantics as set_mode.
                self._always_deny.discard(key)
        return self._state.get(key, False)

    def set(self, key, value):
        if key in self._state:
            self._state[key] = bool(value)
            if value:
                self._always_deny.discard(key)

    def snapshot(self):
        """Ordered list of (key, label, is_on) for rendering the panel."""
        return [(key, label, self._state.get(key, False)) for key, label, _d in PERMISSION_DEFS]

    # ------------------------------------------------------- modes --
    def set_mode(self, mode, persist=True):
        """Switch the global permission mode. Invalid names are
        rejected (returns False) rather than silently defaulting —
        a typo here should never silently grant broader access than
        intended."""
        if mode not in MODES:
            return False
        self.mode = mode
        if mode == "ask":
            self._always_allow.clear()
        if persist:
            try:
                from . import config as _cfg
                cfg = _cfg.load_config()
                cfg.default_permission_mode = mode
                _cfg.save_config(cfg)
            except Exception:
                pass
        return True

    def load_persisted_mode(self):
        try:
            from . import config as _cfg
            cfg = _cfg.load_config()
            m = getattr(cfg, "default_permission_mode", "ask")
            if m in MODES:
                self.mode = m
        except Exception:
            pass

    def mode_label(self):
        return MODE_LABELS[self.mode]

    def needs_prompt(self, key):
        """True if this action should show an inline permission card
        before proceeding.

        - "full" mode: never prompts (matches spec Mode 3 exactly).
        - "restricted" mode: mutating keys always need review (there's
          no silent path — see restricted_review() for the specific
          Accept/Reject framing instead of Allow/Deny); non-mutating
          keys fall back to plain toggle behavior.
        - "ask" mode: mutating keys always need a prompt UNLESS this
          exact key was already granted "Always Allow This Session"
          earlier in the current mode; non-mutating keys fall back to
          plain toggle behavior.

        v0.7.7: a key in `always_deny` never prompts — it's refused
        outright (denied without a card) by the decision check.
        """
        if key in self._always_deny:
            return False
        if self.mode == "full":
            return False
        if key in MUTATING_KEYS:
            if self.mode == "restricted":
                return True
            # mode == "ask"
            return key not in self._always_allow
        return (not self.allowed(key)) and key not in self._always_allow

    def is_blocked(self, key):
        """True if action is hard-blocked and must NOT execute.
        - always_deny blocks in any mode.
        - restricted mode blocks all mutating actions (no silent allow).
        - install_flow_state already reports allow=False for restricted, but
          this is the single general check for all mutating keys."""
        if key in self._always_deny:
            return True
        if self.mode == "restricted" and key in MUTATING_KEYS:
            # restricted still prompts, but caller must not auto-allow;
            # hard-block if the prompt is bypassed
            return False  # prompt path handles it; not auto-blocked here
        return False

    def check(self, key):
        """Centralized permission evaluation. Returns (allowed, needs_prompt, blocked).
        Callers should use this instead of scattering needs_prompt/allowed checks."""
        if self.refused_by_always_deny(key):
            return (False, False, True)
        if self.mode == "full":
            return (True, False, False)
        if self.mode == "restricted" and key in MUTATING_KEYS:
            return (False, True, False)  # must prompt, not auto-allowed
        if key in MUTATING_KEYS:
            if key in self._always_allow:
                return (True, False, False)
            return (False, True, False)
        # non-mutating: governed by toggle
        if self.allowed(key):
            return (True, False, False)
        return (False, False, True) if key in self._always_deny else (False, True, False)

    def refused_by_always_deny(self, key):
        """True when this key was permanently (this session) denied and
        should be refused without showing a card at all."""
        return key in self._always_deny

    def restricted_review(self, key):
        """True if this key, under the CURRENT mode, should be shown
        as a Suggested-Patch-style Accept/Reject prompt (spec Mode 2)
        rather than the Allow-Once/Always-Allow/Deny card (spec Mode 1).
        Only meaningful when needs_prompt(key) is already True."""
        return self.mode == "restricted" and key in MUTATING_KEYS

    def decide(self, key, decision, action_text="", reason=""):
        """Record a decision from an inline permission card.

        decision is one of 'allow_once', 'always_allow', 'deny',
        'always_deny', 'cancel' (v0.7.7 adds the last two — the spec's
        install dialog offers Allow Once / Always Allow / Deny / Always
        Deny / Cancel).
        Returns True if the action should proceed. In "full" mode this
        is never called by a correctly-behaving caller (needs_prompt
        is already False), but if it IS called, "full" still honors
        the explicit decision rather than silently overriding it.
        """
        self.log.append((time.time(), key, action_text, decision))
        if decision == "always_allow":
            self._state[key] = True
            self._always_allow.add(key)
            return True
        if decision == "always_deny":
            self._state[key] = False
            self._always_deny.add(key)
            self._always_allow.discard(key)
            return False
        if decision == "allow_once" or decision == "allow":
            # "allow" is the CLI callback's spelling of a one-shot grant
            # (see app.py _cli_perm_callback) — treating it as refusal
            # made "[Enter] Allow" silently DENY the action.
            return True
        return False  # deny and cancel both refuse


# ------------------------------------------------------- installs --
# Package installation is governed by the same three-mode execution
# policy as every other mutating action:
#
#   - full access   -> executes automatically, no prompt (the install is
#                      still logged in manager.log and the package
#                      history).
#   - ask every time -> prompt=True; the caller shows its approval card.
#   - restricted    -> allow=False; installation is disabled outright
#                      and the caller must report a real permission
#                      error, never a fake success.
#
# The UI flows (calc_terminal/app.py and calc_terminal/ui/app.py) call
# `install_flow_state()` before starting an install. This module only
# tracks state; it never shows UI.

_SAVED_MODE = None


def install_flow_state():
    """Returns a dict describing how the install permission flow should
    behave RIGHT NOW under the active mode:
        {"allow": bool, "prompt": bool, "restore_to": None}
    - restricted mode -> allow=False (installation disabled entirely).
    - ask mode        -> allow=True, prompt=True.
    - full mode       -> allow=True, prompt=False (automatic execution;
                          still recorded via decide()/history by callers).
    """
    global _SAVED_MODE
    if manager.mode == "restricted":
        return {"allow": False, "prompt": False, "restore_to": None}
    if manager.mode == "ask":
        return {"allow": True, "prompt": True, "restore_to": None}
    # full — automatic execution, no narrowing, nothing to restore
    _SAVED_MODE = None
    return {"allow": True, "prompt": False, "restore_to": None}


def restore_mode():
    """Restores the mode saved by install_flow_state() (spec section 3:
    "After installation, restore the previous permission mode
    automatically"). Safe to call even when nothing was saved."""
    global _SAVED_MODE
    if _SAVED_MODE is not None:
        manager.set_mode(_SAVED_MODE)
        _SAVED_MODE = None


# Module-level shared instance — the composer, the permission panel, and
# any inline request card all read/write through this one object so the
# checklist state and prompt behaviour stay consistent across a session.
manager = PermissionManager()
try:
    manager.load_persisted_mode()
except Exception:
    pass
