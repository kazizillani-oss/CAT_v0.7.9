if __name__ == '__main__':
    print("This is a library file and is not meant to be run directly.")
    print("Please run 'python main.py' or 'python model.py' from the project root directory.")
    import sys
    sys.exit(1)

import math
import os
import random
import re
import sys
import textwrap
import time

from . import theme
from . import fallback_cli
from . import solver
from . import atomsim
from . import graphs
from . import sim3d
from . import gpu3d
from . import aicore
from . import agent
from . import sound
from . import code_editor
from . import engine
from . import game
from . import easter_eggs
from . import memory
from . import pet
from . import reactionsim
from . import report
from . import tui
from . import config as cctconfig
from . import registry
from . import errors
from . import identity
from .engine import run_steps, render_notebook, render_derivation, ENGINE_STEPS, IMAGE_STEPS, DERIVE_STEPS, WIDTH
from .generators import GENERATORS, KINETICS_ORDER
from .formulas import FORMULAS
from .mathtext import compose, mathify
from .derivations import DERIVATIONS, DERIVATION_KEYWORDS

VERSION = identity.APP_VERSION
EDITION = identity.APP_NAME

LOGO = [
    "  ██████╗ █████╗ ████████╗",
    " ██╔════╝██╔══██╗╚══██╔══╝",
    " ██║     ███████║   ██║   ",
    " ██║     ██╔══██║   ██║   ",
    " ╚██████╗██║  ██║   ██║   ",
    "  ╚═════╝╚═╝  ╚═╝   ╚═╝   ",
]

SUGGESTIONS = [
    ("first order", "First Order Rate Constant", "kinetics", "first"),
    ("first order half life", "First Order Half-Life", "kinetics", "halflife"),
    ("first order numerical", "First Order Numerical", "kinetics", "first"),
    ("zero order", "Zero Order Kinetics", "kinetics", "zero"),
    ("second order", "Second Order Kinetics", "kinetics", "second"),
    ("third order", "Third Order Kinetics", "kinetics", "third"),
    ("half life", "Half-Life Numerical", "kinetics", "halflife"),
    ("arrhenius equation", "Arrhenius Equation", "kinetics", "arrhenius"),
    ("activation energy", "Activation Energy Numerical", "kinetics", "arrhenius"),
    ("mole concept", "Mole Concept Numerical", "class 11", "mole"),
    ("molar mass", "Molar Mass Calculation", "class 11", "mole"),
]

# Command-suggestions shared by both in-chat loops (/ai and /agent) — the
# in-chat dropdown always offers these regardless of mode.
_CHAT_COMMANDS = [
    ("/back", "Return to the home dashboard"),
    ("/setup", "Reconfigure your AI provider/model"),
    ("/verify", "Test the current AI connection"),
    ("/memory", "View what CAT remembers about you"),
    ("/workspace", "Detect, open & manage project workspaces"),
    ("/packages", "Installation dashboard + install history"),
]

# Example prompts offered inside /ai — short, conversational questions.
AI_PROMPT_SUGGESTIONS = [
    ("what is a first order reaction", "Quick conceptual answer"),
    ("half life of a first order reaction", "Quick numeric answer"),
    ("explain the arrhenius equation simply", "Quick conceptual answer"),
    ("what's the difference between molarity and molality", "Quick conceptual answer"),
    ("quick mole concept refresher", "Quick conceptual answer"),
    ("/agent", "Switch to the full notebook-style Chemistry Agent"),
]
AI_SUGGESTIONS = _CHAT_COMMANDS + AI_PROMPT_SUGGESTIONS

# Example prompts offered inside /agent — longer, tool-using requests that
# want the full step-by-step notebook treatment.
AGENT_PROMPT_SUGGESTIONS = [
    ("solve ideal gas law with P=1, n=2, T=300", "Symbolic solve + full notebook"),
    ("derive the first order rate law step by step", "Full derivation, notebook format"),
    ("plot the arrhenius graph and export it", "Plot + PNG export"),
    ("plot y = sin(x)*exp(-x/5) from 0 to 20 called Damped Wave", "Custom function plot"),
    ("simulate an iron atom in 3d", "Live 3D Bohr simulation"),
    ("show me the 2p orbital cloud", "Live quantum orbital simulation"),
    ("explain redox titration in detail, step by step", "Long, notebook-style explanation"),
]
AGENT_SUGGESTIONS = _CHAT_COMMANDS + AGENT_PROMPT_SUGGESTIONS

# Moved to commands_data.py in v0.5.9 so the new composer's slash
# CommandPalette can import the exact same list instead of a second,
# hand-maintained copy. Nothing below this line changed behavior.
from .commands_data import COMMANDS


def _colorize_diff_lines(changes_text):
    """Apply green/red ANSI to the git-style +/- diff rows of the File
    changes panel (the Textual chat gets its colors from pygments' diff
    lexer instead — this is the classic terminal's equivalent)."""
    out = []
    for ln in changes_text.split("\n"):
        s = ln.lstrip()
        if s and s[0] in "+-" and not s.startswith("-" * 4):
            out.append((theme.green if s[0] == "+" else theme.red)(ln))
        else:
            out.append(ln)
    return out


class App:
    VERSION = VERSION
    EDITION = EDITION

    def __init__(self):
        self.history = []
        self.autosave = True
        self.precision = 3
        self.sound_enabled = True
        self.running = True
        self.game_high_score = 0
        self.game_best_streak = 0
        self.eggs_found = set()
        sound.set_enabled(self.sound_enabled)
        try:
            from .terminal_identity import set_terminal_title
            set_terminal_title()
        except Exception:
            pass
        self._bind_registry_handlers()

    def _bind_registry_handlers(self):
        """Attach this instance's bound cmd_* methods to the shared
        CommandRegistry (spec section 14) for the subset of commands
        that take no inline trailing arguments — confirmed by direct
        comparison against handle()'s elif chain to call the exact same
        method with no extra logic in between. Commands that parse
        trailing text themselves (e.g. "/bonding furan", "/derive
        first order half life") are deliberately left unbound for now;
        they keep going through their existing elif branch in handle().
        This is real, incremental migration onto the registry — not a
        parallel copy — matched one command at a time, not a blanket
        rewrite of the dispatch chain."""
        reg = registry.get_registry()
        bindings = {
            "/help": self.cmd_help,
            "/calculator": self.cmd_calculator,
            "/formulas": self.cmd_formulas,
            "/kinetics": self.cmd_kinetics,
            "/electrochemistry": self.cmd_electrochemistry,
            "/solve": self.cmd_solve,
            "/atomsim": self.cmd_atomsim,
            "/orbitals": self.cmd_orbitals,
            "/orbitalgrid": self.cmd_orbitalgrid,
            "/graph": self.cmd_graph,
            "/shortcuts": self.cmd_shortcuts,
            "/history": self.cmd_history,
            "/settings": self.cmd_settings,
            "/about": self.cmd_about,
            "/derive": self.cmd_derive,
            # split_optional (spec section 14): zero args or one
            # stripped trailing-text arg, verified 1:1 against the old
            # elif chain in handle() before being added here.
            "/memory": self.cmd_memory,
            "/model": self.cmd_model,
            "/theme": self.cmd_theme,
            "/websearch": self.cmd_websearch,
            "/research": self.cmd_research,
            "/import": self.cmd_import,
            "/react": self.cmd_react,
            "/export": self.cmd_export,
            "/workspace": self.cmd_workspace,
            "/permissions": self.cmd_permissions,
            # remaining plain no-arg commands, same verification approach
            # as the first batch — checked against handle()'s elif chain
            # to confirm each is a direct "self.cmd_X(); return" with
            # nothing else happening in between.
            "/upload": self.cmd_upload,
            "/voice": self.cmd_voice,
            "/sim3d": self.cmd_sim3d,
            "/gpu3d": self.cmd_gpu3d,
            "/ai": self.cmd_ai,
            "/agent": self.cmd_agent,
            "/ai-verify": self.cmd_ai_verify,
            "/game": self.cmd_game,
            "/codepad": self.cmd_codepad,
            "/edit": self.cmd_textedit,
            "/tokens": self.cmd_tokens,
            "/pet": self.cmd_pet,
            "/tui": self.cmd_tui,
            "/composer": self.cmd_composer,
            "/copycode": self.cmd_copycode,
            "/free": self.cmd_free,
            "/latest": self.cmd_latest,
            "/provider": self.cmd_provider,
            "/status": self.cmd_status,
            "/refresh-models": self.cmd_refresh_models,
            # /random wasn't its own method in the old elif branch (it
            # called self.solve(...) inline) — wrapped here so it can be
            # registry-dispatched too, with identical inner logic.
            "/random": lambda: self.solve(random.choice(list(GENERATORS.keys()))),
            # CAT Vision — split_optional so `/vision` and `/vision start` both work
            "/vision": self.cmd_vision,
            "/vscode": self.cmd_vscode,
            # CAT Browser — split_optional so `/browser`, `/browse`, and `/cat` all work
            "/browser": self.cmd_browser,
            "/browse": self.cmd_browser,
            "/cat": self.cmd_browser,
        }
        for name, method in bindings.items():
            spec = reg.get(name)
            if spec is not None:
                spec.handler = method

    # -------------------------------------------------------------- boot --
    def boot(self):
        # Defense-in-depth gate: even if cli.main was bypassed (e.g. direct
        # `App().run()` from a test or old entrypoint), boot still refuses
        # without Fomoji.  Normal launches already passed cli's gate; this
        # second check is just `status()==connected` and costs nothing.
        try:
            from .fomoji_auth import status as _fa_status
            if _fa_status() != "connected":
                # Lazy import theme for the error without breaking boot's
                # normal imports if auth is broken.
                try:
                    from . import theme as _t
                    _t.enable_windows_ansi()
                    print()
                    print(_t.panel([
                        _t.red("CAT IS LOCKED", bold=True),
                        _t.dim("Fomoji authentication required — boot refused."),
                        _t.faint("Run `cat --auth login` and try again."),
                    ], title="locked", color=_t.RED, width=76))
                except Exception:
                    print("CAT IS LOCKED — Fomoji auth required.", file=sys.stderr)
                raise SystemExit(1)
        except SystemExit:
            raise
        except Exception:
            pass

        theme.enable_windows_ansi()
        theme.load_saved_theme()
        theme.clear_screen()
        print()
        theme.reveal_lines(LOGO, delay=0.06, color=theme.CYAN, bold=True)
        print()
        theme.typewriter("  CAT \u2014 Coding Agent Terminal", delay=0.012, color=theme.PURPLE, bold=True)
        print(theme.center(theme.gradient(f"v{VERSION} \u00b7 {EDITION}", theme.ORANGE, theme.PURPLE, bold=True), WIDTH))
        time.sleep(0.15)
        print()
        run_steps(["Booting calc_terminal...", "Loading Notebook Engine..."], step_time=0.28)
        theme.progress_bar("Warming up engine", duration=0.5)
        sound.play("startup")
        print()
        time.sleep(0.2)

    # -------------------------------------------------------------- home --
    def print_home(self):
        theme.clear_screen()
        print(theme.window_titlebar("calc_terminal", WIDTH))
        content_w = WIDTH - 6
        lines = []
        for l in LOGO:
            lines.append(theme.center(theme.gradient(l, theme.CYAN, theme.PURPLE, bold=True), content_w))
        lines.append("")
        lines.append(theme.center(theme.gradient("CAT \u2014 Coding Agent Terminal", theme.CYAN, theme.PURPLE, theme.CYAN, bold=True), content_w))
        lines.append(theme.center(
            theme.dim(f"v{VERSION}  \u00b7  ") + theme.gradient(EDITION, theme.ORANGE, theme.PURPLE, bold=True) +
            theme.dim("  \u00b7  ") + theme.green("\u25cf Ready"),
            content_w))
        lines.append("")
        lines.append(theme.gradient_rule(content_w, theme.FAINT, theme.PURPLE, theme.FAINT))
        reverse_alias = {full: short for short, full in self.SHORT_ALIASES.items()}
        for cmd, desc in COMMANDS[:10]:
            short = reverse_alias.get(cmd, "")
            desc_w = max(1, content_w - 20 - 6)
            if len(desc) > desc_w:
                desc = desc[:desc_w - 1].rstrip() + "\u2026"
            row = theme.cyan(cmd.ljust(20)) + theme.dim(desc.ljust(desc_w)) + theme.faint(short.rjust(4))
            lines.append(row)
        lines.append(theme.faint(f"  \u2026 {len(COMMANDS) - 10} more \u2014 type /help for the full list"))
        print(theme.panel(lines, title=f"v{VERSION} \u00b7 {EDITION}", color=theme.CYAN, width=WIDTH, title_gradient=(theme.CYAN, theme.PURPLE)))
        print()
        print("  " + fallback_cli.status_ribbon([
            ("STATUS", "READY"), ("MODE", "NOTEBOOK"), ("ENGINE", f"VERIFIED v{VERSION}"),
        ]))
        print()

    # -------------------------------------------------------------- loop --
    def run(self):
        self.boot()
        self.print_home()
        while self.running:
            try:
                model_label = None
                effort_label = "ready"
                try:
                    cfg = aicore.load_config()
                    if cfg.get("provider") and (cfg.get("provider") == "ollama" or cfg.get("api_key")):
                        model_label = f"{cfg['provider'].upper()} {cfg.get('model', '')}".strip()
                        usage = aicore.get_session_usage()
                        if usage["requests"]:
                            effort_label = f"{usage['total_tokens']:,} tok used"
                except Exception:
                    model_label = None
                raw = fallback_cli.fallback_input(
                    width=WIDTH, mode_label="NOTEBOOK", model_label=model_label,
                    effort_label=effort_label, suggestions=self._suggestion_items()
                ).strip()
            except (EOFError, KeyboardInterrupt):
                self.cmd_exit()
                break
            if not raw:
                continue
            pet.mark_activity()
            # Show what was typed exactly once, right here, before it's
            # routed anywhere — this used to also get reprinted deeper in
            # handle_question(), which was the 'double text' bug.
            # v0.5.6: adaptive OpenCode-style rendering — rail panel for long
            # questions, right-aligned gradient bubble for short ones.
            fallback_cli.render_user(raw, tag="you", term_width=WIDTH)
            try:
                self.handle(raw)
            except (EOFError, KeyboardInterrupt):
                # A sub-menu (AI setup, code pad, editor, settings, etc.)
                # was reading its own input() and the user hit Ctrl+D/
                # Ctrl+C mid-flow. Previously this bubbled all the way up
                # and killed the whole app with a raw traceback. Now it
                # just cancels back out to the home prompt.
                print()
                print(theme.dim("  ✕ Cancelled — back to the main prompt."))
            except Exception as exc:  # pragma: no cover - defensive
                # Any bug in a command handler should never nuke the
                # whole session. Report it and keep the terminal alive.
                print()
                print(theme.red(f"  ⚠ Something went wrong: {exc}"))
                print(theme.dim("  The terminal is still running — try another command."))

    def _suggestion_items(self):
        """Flatten commands + known question topics into (trigger,
        description) pairs for the live suggestion dropdown."""
        items = []
        reverse_alias = {full: short for short, full in self.SHORT_ALIASES.items()}
        for cmd, desc in COMMANDS:
            short = reverse_alias.get(cmd, "")
            items.append((cmd, desc + (f"  ({short})" if short else "")))
        for trigger, label, category, _key in SUGGESTIONS:
            items.append((trigger, f"{label} \u2014 {category}"))
        return items

    # ----------------------------------------------------------- routing --
    # short aliases so common commands don't need to be typed in full,
    # e.g. "/h" for /help, "/d first order" for /derive
    #
    # This used to be a dict hardcoded here. It's now derived from
    # calc_terminal.registry (spec section 14's "centralized command
    # registry" — one place, not duplicated) via short_alias_map().
    # The mapping itself is byte-for-byte the same table, just defined
    # in one place instead of two.
    SHORT_ALIASES = registry.short_alias_map()

    def handle(self, raw):
        low = raw.lower().strip()
        first_tok = low.split(" ", 1)[0]
        if first_tok in self.SHORT_ALIASES:
            rest = low[len(first_tok):].strip()
            low = self.SHORT_ALIASES[first_tok] + (" " + rest if rest else "")
            raw = low

        if low in ("/exit", "/quit", "exit", "quit"):
            self.cmd_exit()
            return
        if low in ("/clear", "/home"):
            self.print_home()
            return

        # Registry-driven dispatch (spec section 14): for the exact-match,
        # no-inline-argument commands bound in _bind_registry_handlers(),
        # route through the CommandRegistry's spec.handler instead of the
        # elif chain below. Commands that parse trailing text (e.g.
        # "/bonding furan", "/derive first order") are NOT bound, so they
        # fall straight through to their existing branch, unchanged. The
        # old elif branches for the bound commands are left in place as a
        # safety net — if a spec or handler is ever missing, behavior
        # degrades to exactly what it was before this dispatch existed,
        # never to a dead end.
        spec = registry.get_registry().get(low)
        if spec is not None and spec.handler is not None and low == spec.name:
            spec.handler()
            return

        # split_optional arg-taking commands (spec section 14): the
        # exact-match, zero-arg case is already covered by the block
        # above (spec.handler() with no args, same as before). This
        # covers "/X <trailing text>" specifically, matching the old
        # `self.cmd_X(raw.split(" ", 1)[1].strip())` call exactly.
        cmd_tok = low.split(" ", 1)[0]
        arg_spec = registry.get_registry().get(cmd_tok)
        if (arg_spec is not None and arg_spec.handler is not None
                and arg_spec.arg_style == "split_optional"
                and low.startswith(arg_spec.name + " ")):
            arg_spec.handler(raw.split(" ", 1)[1].strip())
            return

        if low == "/help":
            self.cmd_help()
            return
        if low == "/calculator":
            self.cmd_calculator()
            return
        if low == "/formulas":
            self.cmd_formulas()
            return
        if low == "/kinetics":
            self.cmd_kinetics()
            return
        if low in ("/derive", "/derivation", "/derivations"):
            self.cmd_derive()
            return
        if low.startswith(("/derive ", "/derivation ", "/derivations ")):
            arg = raw.split(" ", 1)[1]
            key = self.detect_derivation("derive " + arg) or None
            for pattern, k in DERIVATION_KEYWORDS:
                if re.search(pattern, arg.lower()):
                    key = k
                    break
            if key:
                self.derive(key)
            else:
                self.cmd_derive()
            return
        if low == "/electrochemistry":
            self.cmd_electrochemistry()
            return
        if low == "/solve":
            self.cmd_solve()
            return
        if low == "/atomsim":
            self.cmd_atomsim()
            return
        if low == "/orbitals":
            self.cmd_orbitals()
            return
        if low == "/orbitalgrid":
            self.cmd_orbitalgrid()
            return
        if low == "/bonding" or low.startswith("/bonding "):
            arg = raw.split(" ", 1)[1] if " " in raw else ""
            self.cmd_bonding(arg)
            return
        if low == "/bloch" or low.startswith("/bloch "):
            arg = raw.split(" ", 1)[1] if " " in raw else ""
            self.cmd_bloch(arg)
            return
        if low == "/graph":
            self.cmd_graph()
            return
        if low == "/shortcuts":
            self.cmd_shortcuts()
            return
        if low == "/history":
            self.cmd_history()
            return
        if low == "/settings":
            self.cmd_settings()
            return
        if low == "/about":
            self.cmd_about()
            return
        # v0.7.9: safety / auth / orchestration / integration commands
        if low == "/stats":
            self.cmd_stats()
            return
        if low == "/report" or low.startswith("/report "):
            self.cmd_report(raw.split(" ", 1)[1].strip() if " " in raw else "")
            return
        if low == "/task" or low.startswith("/task "):
            self.cmd_task(raw.split(" ", 1)[1].strip() if " " in raw else "")
            return
        if low == "/auth" or low.startswith("/auth "):
            self.cmd_auth(raw.split(" ", 1)[1].strip() if " " in raw else "")
            return
        if low == "/vscode" or low.startswith("/vscode "):
            self.cmd_vscode(raw.split(" ", 1)[1].strip() if " " in raw else "")
            return
        if low == "/colab" or low.startswith("/colab "):
            self.cmd_colab(raw.split(" ", 1)[1].strip() if " " in raw else "")
            return
        if low == "/random":
            self.solve(random.choice(list(GENERATORS.keys())))
            return
        if low == "/upload":
            self.cmd_upload()
            return
        if low == "/voice":
            self.cmd_voice()
            return
        if low == "/sim3d":
            self.cmd_sim3d()
            return
        if low == "/gpu3d":
            self.cmd_gpu3d()
            return
        if low == "/ai":
            self.cmd_ai()
            return
        if low == "/agent":
            self.cmd_agent()
            return
        if low in ("/ai-verify", "/verify"):
            self.cmd_ai_verify()
            return
        if low == "/memory":
            self.cmd_memory()
            return
        if low.startswith("/memory "):
            self.cmd_memory(raw.split(" ", 1)[1].strip().lower())
            return
        if low in ("/game", "/quiz", "/play"):
            self.cmd_game()
            return
        if low == "/codepad":
            self.cmd_codepad()
            return
        if low == "/edit":
            self.cmd_textedit()
            return
        if low == "/model":
            self.cmd_model()
            return
        if low.startswith("/model "):
            self.cmd_model(raw.split(" ", 1)[1].strip())
            return
        if low in ("/free", "/latest"):
            (self.cmd_free() if low == "/free" else self.cmd_latest())
            return
        if low == "/provider":
            self.cmd_provider()
            return
        if low == "/status":
            self.cmd_status()
            return
        if low in ("/refresh-models", "/model-refresh"):
            self.cmd_refresh_models()
            return
        if low == "/tokens":
            self.cmd_tokens()
            return
        if low == "/theme":
            self.cmd_theme()
            return
        if low.startswith("/theme "):
            self.cmd_theme(raw.split(" ", 1)[1].strip())
            return
        if low.startswith("/websearch "):
            self.cmd_websearch(raw.split(" ", 1)[1].strip())
            return
        if low == "/websearch":
            self.cmd_websearch()
            return
        if low.startswith("/research "):
            self.cmd_research(raw.split(" ", 1)[1].strip())
            return
        if low == "/research":
            self.cmd_research()
            return
        if low.startswith("/import "):
            self.cmd_import(raw.split(" ", 1)[1].strip())
            return
        if low == "/import":
            self.cmd_import()
            return
        if low == "/pet":
            self.cmd_pet()
            return
        if low == "/react":
            self.cmd_react()
            return
        if low.startswith("/react "):
            self.cmd_react(raw.split(" ", 1)[1].strip())
            return
        if low == "/export":
            self.cmd_export()
            return
        if low.startswith("/export "):
            self.cmd_export(raw.split(" ", 1)[1].strip())
            return
        if low == "/tui":
            self.cmd_tui()
            return
        if low == "/composer":
            self.cmd_composer()
            return
        if low == "/copycode":
            self.cmd_copycode()
            return

        # ---- v0.7.7 Autonomous Development Preview commands ----
        if low == "/install" or low.startswith("/install "):
            self.cmd_install(raw.split(" ", 1)[1].strip() if " " in raw else "")
            return
        if low == "/packages" or low.startswith("/packages "):
            self.cmd_packages(raw.split(" ", 1)[1].strip() if " " in raw else "")
            return
        if low == "/pipeline" or low.startswith("/pipeline "):
            self.cmd_pipeline(raw.split(" ", 1)[1].strip() if " " in raw else "")
            return
        if low == "/orchestrate" or low.startswith("/orchestrate "):
            self.cmd_orchestrate(raw.split(" ", 1)[1].strip() if " " in raw else "")
            return

        # ---- CAT Browser (full terminal browser, Fomoji-gated) --------------
        if low in ("/browser", "/browse", "/cat") or low.startswith(("/browser ", "/browse ", "/cat ")):
            self.cmd_browser(raw.split(" ", 1)[1].strip() if " " in raw else "")
            return
        if low == "/devices" or low.startswith("/devices "):
            self.cmd_devices(raw.split(" ", 1)[1].strip() if " " in raw else "")
            return

        # secret stuff — checked before the normal question pipeline so a
        # curious "who made this" or a stray "42" never falls through to
        # "I couldn't match that to a supported topic yet."
        if easter_eggs.check(low, self):
            return

        if low.startswith("/"):
            tok = low.split()[0] if low.split() else low
            print()
            print(theme.red(f"  ✗ Unknown command '{tok}'. Type /help for a list of available commands."))
            print()
            return


        # free-text chemistry question
        self.handle_question(raw)

    # ------------------------------------------------------- free text ---
    def detect_intent(self, text):
        t = text.lower()
        if re.search(r"mole|molar mass|molarity", t):
            return "mole"
        if "zero order" in t:
            return "zero"
        if "third order" in t:
            return "third"
        if "second order" in t:
            return "second"
        if re.search(r"half.?life", t):
            return "halflife"
        if re.search(r"arrhenius|activation energy", t):
            return "arrhenius"
        if "first order" in t:
            return "first"
        return None

    def detect_derivation(self, text):
        """Detect 'derive first order', 'derivation of zero order rate law',
        etc. — routes to the real step-by-step calculus derivation instead
        of a numeric example question."""
        t = text.lower()
        if not re.search(r"deriv", t):
            return None
        for pattern, key in DERIVATION_KEYWORDS:
            if re.search(pattern, t):
                return key
        return None

    def handle_question(self, raw):
        # ---- v0.7.7 autonomous routing (spec sections 1/5/6) ----
        # Install requests go straight to the package manager.
        try:
            from . import mode_detection
            workflow = mode_detection.workflow_kind(raw)
            if workflow == "install":
                self.cmd_install(raw)
                return
            if workflow == "pipeline":
                self.cmd_pipeline(raw)
                return
            # v0.7.8.1 mode lockdown: the selected mode is persistent —
            # typing never auto-switches personas (the old silent
            # re-routing bug). Workflow routing still runs: a deep
            # research request goes through the Research flow, without
            # changing the user's active mode.
            if workflow == "research_deep":
                self.cmd_research(raw)
                return
        except Exception:
            pass

        # The message is already shown once by run() right after it's
        # typed — don't print it again here.
        # v0.5.6: OpenCode-style cleaner thinking spinner (braille) instead
        # of the old multi-line mascot indicator.
        fallback_cli.thinking(label="CCT AI")

        deriv_key = self.detect_derivation(raw)
        if deriv_key:
            self.derive(deriv_key)
            return

        intent = self.detect_intent(raw)
        if intent:
            self.solve(intent)
            return

        # No exact local match -> try the Chemistry Agent if configured.
        # This allows the AI to handle novel topics like "third order" or
        # custom plots before falling back to "Did you mean...".
        config = aicore.load_config()
        provider = config.get("provider")
        ai_ready = provider == "ollama" or bool(config.get("api_key"))
        if provider and ai_ready:
            t0 = time.time()
            final_text, steps, meta = agent.run_agent(raw, mode="ai")
            duration = time.time() - t0
            model_label = f"{provider.upper()} {config.get('model', '')}".strip()
            if steps:
                print(theme.dim(f"  ({len(steps)} tool step(s) run \u2014 type /agent for the full notebook view)"))
            # v0.5.6: adaptive OpenCode-style AI reply (bubble for short,
            # borderless notebook text for long) with a `▣ tag · model · dur`
            # avatar footer.
            fallback_cli.render_ai(final_text, tag="CCT AI", model_label=model_label,
                             duration=duration, term_width=WIDTH)
            if meta.get("suggest_agent"):
                print(theme.orange("  \U0001F4A1 That looked like a big one \u2014 try /agent for the "
                                    "full step-by-step notebook breakdown."))
            print()
            return

        # ambiguous / short input -> smart suggestions
        low = raw.lower()
        matches = [s for s in SUGGESTIONS if low in s[0] or s[0].startswith(low)]
        if not matches:
            words = [w for w in low.split() if len(w) >= 4]
            matches = [s for s in SUGGESTIONS if any(w in s[0] for w in words)]

        if matches:
            print()
            print(theme.dim("  Did you mean:"))
            for i, (key, label, tag, gen) in enumerate(matches[:6], 1):
                print(f"    {theme.cyan(str(i))}  {theme.text(label)}  {theme.faint('['+tag+']')}")
            print(theme.faint("    Type a number to solve it, or press Enter to cancel."))
            choice = input(theme.dim("  \u25b8 ")).strip()
            if choice.isdigit() and 1 <= int(choice) <= min(6, len(matches)):
                self.solve(matches[int(choice) - 1][3])
            return

        print(theme.orange("\n  I couldn't match that to a supported topic yet."))
        print(theme.dim("  Try /kinetics, /formulas, keywords like \"first order\", \"mole concept\","))
        print(theme.dim("  or run /agent (or /ai) to configure a provider for general questions,"))
        print(theme.dim("  live simulations, and custom graphs.\n"))

    # ------------------------------------------------------------ solve --
    def solve(self, intent, prefix=None):
        print()
        run_steps(ENGINE_STEPS)
        nb = GENERATORS[intent]()
        if prefix:
            nb["question"] = f"{prefix} {nb['question']}"
        print()
        render_notebook(nb)
        sound.play("success")
        if self.autosave:
            self.history.insert(0, nb)
            self.history = self.history[:25]
        self.post_notebook_menu(intent)

    def derive(self, key):
        print()
        run_steps(DERIVE_STEPS, step_time=0.28)
        dv = DERIVATIONS[key]()
        print()
        render_derivation(dv)
        sound.play("success")
        print()
        print(theme.faint("  [Enter] continue   [n] numeric example   [h] home"))
        choice = input(theme.dim("  \u25b8 ")).strip().lower()
        if choice == "n" and key in GENERATORS:
            self.solve(key)
        elif choice == "h":
            self.print_home()

    def cmd_derive(self):
        lines = [theme.purple("DERIVATIONS", bold=True), "",
                 theme.dim("Real step-by-step calculus derivations, not numeric examples.")]
        keys = list(DERIVATIONS.keys())
        for i, k in enumerate(keys, 1):
            lines.append(f"{theme.cyan(str(i)+'.')} {theme.text(DERIVATIONS[k]().get('topic', k))}")
        print()
        print(theme.panel(lines, title="derive", color=theme.PURPLE, width=WIDTH))
        choice = input(theme.dim("  \u25b8 ")).strip()
        if choice.isdigit() and 1 <= int(choice) <= len(keys):
            self.derive(keys[int(choice) - 1])
        else:
            self.print_home()

    def post_notebook_menu(self, intent):
        print()
        print(theme.faint("  [Enter] continue   [a] another   [f] view formula   [h] home"))
        choice = input(theme.dim("  \u25b8 ")).strip().lower()
        if choice == "a":
            self.solve(intent)
        elif choice == "f":
            self.cmd_formulas()
        elif choice == "h":
            self.print_home()

    # ------------------------------------------------------------- help --
    def cmd_help(self):
        lines = [theme.purple("COMMANDS", bold=True), ""]
        for cmd, desc in COMMANDS:
            lines.append(theme.cyan(cmd.ljust(20)) + theme.dim(desc))
        lines.append("")
        lines.append(theme.purple("SMART TYPING", bold=True))
        lines.append(theme.dim("Type things like \"first order\", \"half life\", \"mole concept\","))
        lines.append(theme.dim("and calc_terminal will detect the topic and solve a numerical."))
        lines.append("")
        lines.append(theme.purple("LIVE SIMULATIONS", bold=True))
        lines.append(theme.dim("/atomsim  — animated Bohr atom with real proton/neutron/electron counts"))
        lines.append(theme.dim("/orbitals — live Monte-Carlo quantum electron-cloud (1s..3d)"))
        lines.append(theme.dim("/sim3d    — real-time rotatable 3D atom/electron/proton simulation"))
        lines.append(theme.dim("Type /shortcuts for the full key reference inside those views."))
        lines.append("")
        lines.append(theme.purple("CHEMISTRY AGENTIC AI", bold=True))
        lines.append(theme.dim("/agent      — AI that actually solves, plots & simulates via tools,"))
        lines.append(theme.dim("              not just prose (needs a provider — API key or Ollama)"))
        lines.append(theme.dim("/ai-verify  — test your configured provider/model connection"))
        lines.append(theme.dim("Once configured, plain questions are also routed through the agent."))
        lines.append("")
        lines.append(theme.purple("LEARN BY PLAYING", bold=True))
        lines.append(theme.dim("/game — a multiple-choice Element Quiz: symbols, names, atomic"))
        lines.append(theme.dim("numbers & shell structure, with streaks, lives and a speed bonus."))
        lines.append("")
        lines.append(theme.purple("SOUND", bold=True))
        lines.append(theme.dim("Short terminal chimes play on startup, solved results, errors, and"))
        lines.append(theme.dim("simulation starts (and per agent tool call). Toggle in /settings."))
        print()
        print(theme.panel(lines, title="help", color=theme.PURPLE, width=WIDTH))
        print()

    # ------------------------------------------------------- calculator --
    def cmd_calculator(self):
        print()
        print(theme.panel(
            [theme.text("Quick scientific calculator", bold=True),
             theme.dim("Supports + - * / ** () sqrt() log10() log() sin() cos() tan() pi e"),
             theme.dim("Type /back to return home.")],
            title="calculator", color=theme.CYAN, width=WIDTH))
        allowed = re.compile(r"^[0-9+\-*/().\s,a-zA-Z_]*$")
        safe_ns = {
            "sqrt": math.sqrt, "log10": math.log10, "log": math.log,
            "sin": math.sin, "cos": math.cos, "tan": math.tan,
            "pi": math.pi, "e": math.e, "abs": abs, "round": round,
        }
        while True:
            expr = input(theme.dim("  calc \u25b8 ")).strip()
            if not expr:
                continue
            if expr.lower() in ("/back", "back", "/exit"):
                break
            try:
                expr_py = expr.replace("^", "**")
                if not allowed.match(expr_py):
                    raise ValueError("invalid characters")
                result = eval(expr_py, {"__builtins__": {}}, safe_ns)
                if isinstance(result, float):
                    result = round(result, self.precision)
                print("  " + theme.green(f"= {result}", bold=True))
                sound.play("success")
            except Exception:
                print("  " + theme.red("Error \u2014 check the expression"))
                sound.play("error")
        self.print_home()

    # ----------------------------------------------- universal solver ----
    def cmd_solve(self):
        while True:
            print()
            lines = [theme.purple("UNIVERSAL FORMULA CALCULATOR", bold=True), ""]
            cats = {}
            for key, (name, cat, _, _) in solver.FORMULA_LIBRARY.items():
                cats.setdefault(cat, []).append((key, name))
            i = 0
            index_map = []
            for cat in sorted(cats):
                lines.append(theme.cyan(cat, bold=True))
                for key, name in cats[cat]:
                    i += 1
                    index_map.append(key)
                    lines.append(f"  {theme.dim(str(i)+'.')} {theme.text(name)}")
            lines.append("")
            lines.append(theme.faint("Type a number for a library formula,"))
            lines.append(theme.faint("or 'custom' to solve ANY formula you type, or /back."))
            print(theme.panel(lines, title="solve", color=theme.PURPLE, width=WIDTH))
            choice = input(theme.dim("  \u25b8 ")).strip().lower()
            if choice in ("/back", "back", "/exit", ""):
                break
            if choice == "custom":
                self._solve_custom()
                continue
            if choice.isdigit() and 1 <= int(choice) <= len(index_map):
                self._solve_library(index_map[int(choice) - 1])
                continue
            print(theme.red("  Not a valid choice."))
        self.print_home()

    def _solve_library(self, key):
        name, cat, formula_str, var_desc = solver.FORMULA_LIBRARY[key]
        print()
        lines = [theme.purple(name, bold=True) + "  " + theme.faint(f"[{cat}]"), ""]
        for pl in solver.pretty(formula_str).split("\n"):
            lines.append(theme.text(pl, bold=True))
        lines.append("")
        for sym, desc in var_desc.items():
            lines.append(f"  {theme.cyan(sym)} = {theme.dim(desc)}")
        lines.append("")
        lines.append(theme.faint("Enter values for ALL BUT ONE variable (e.g. P=1 n=2 T=300),"))
        lines.append(theme.faint("leave exactly one out — that's what gets solved."))
        print(theme.panel(lines, title="formula", color=theme.CYAN, width=WIDTH))
        raw = input(theme.dim("  values \u25b8 ")).strip()
        known = self._parse_assignments(raw)
        try:
            solve_for, result, name2, cat2, eq = solver.solve_library_formula(key, known)
            run_steps(["Substituting known values...", "Solving symbolically..."], step_time=0.22)
            print()
            result_lines = [theme.dim("Solving:")]
            for pl in solver.pretty(eq).split("\n"):
                result_lines.append(theme.text(pl))
            result_lines.append("")
            result_lines.append(theme.green(f"{solve_for} = {result:.6g}", bold=True))
            print(theme.panel(result_lines, title="result", color=theme.GREEN, width=WIDTH))
            sound.play("success")
        except solver.SolveError as e:
            print(theme.red(f"  {e}"))
            sound.play("error")
        except Exception as e:
            print(theme.red(f"  Error: {e}"))
            sound.play("error")
        input(theme.faint("\n  Press Enter to continue\u2026"))

    def _solve_custom(self):
        print()
        print(theme.panel([
            theme.text("Type ANY formula, e.g.  P*V = n*R*T   or   y = m*x + c", bold=True),
            theme.dim("Known constants available: R, NA, h, c, k_B, F, pi, e, Rinf, a0, me"),
        ], title="custom formula", color=theme.CYAN, width=WIDTH))
        formula_str = input(theme.dim("  formula \u25b8 ")).strip()
        if not formula_str or "=" not in formula_str:
            print(theme.red("  Need a formula containing '='."))
            return
        raw = input(theme.dim("  known values (e.g. m=2 x=3 c=1) \u25b8 ")).strip()
        known = self._parse_assignments(raw)
        solve_for = input(theme.dim("  solve for \u25b8 ")).strip()
        try:
            result, eq = solver.solve_formula(formula_str, known, solve_for)
            run_steps(["Parsing formula...", "Solving symbolically..."], step_time=0.22)
            print()
            result_lines = [theme.dim("Equation:")]
            for pl in solver.pretty(eq).split("\n"):
                result_lines.append(theme.text(pl))
            result_lines.append("")
            result_lines.append(theme.green(f"{solve_for} = {result:.6g}", bold=True))
            print(theme.panel(result_lines, title="result", color=theme.GREEN, width=WIDTH))
            sound.play("success")
        except solver.SolveError as e:
            print(theme.red(f"  {e}"))
            sound.play("error")
        except Exception as e:
            print(theme.red(f"  Error: {e}"))
            sound.play("error")
        input(theme.faint("\n  Press Enter to continue\u2026"))

    @staticmethod
    def _parse_assignments(raw):
        known = {}
        for tok in raw.replace(",", " ").split():
            if "=" in tok:
                k, v = tok.split("=", 1)
                try:
                    known[k.strip()] = float(v.strip())
                except ValueError:
                    pass
        return known

    # ------------------------------------------------------- atom sim ----
    def cmd_atomsim(self):
        print()
        print(theme.panel([
            theme.text("Live Bohr atom & electron simulation", bold=True),
            theme.dim("Enter an element symbol or atomic number (H..Kr, Z=1-36)."),
        ], title="atomsim", color=theme.CYAN, width=WIDTH))
        raw = input(theme.dim("  element \u25b8 ")).strip() or "C"
        z = atomsim.resolve_element(raw)
        if z is None:
            print(theme.red(f"  Unknown element '{raw}'."))
            sound.play("error")
            return
        sound.play("sim_start")
        atomsim.atom_simulation(z)
        self.print_home()

    def cmd_orbitals(self):
        print()
        print(theme.panel([
            theme.text("Live quantum orbital (electron cloud) simulation", bold=True),
            theme.dim("Choose an orbital: " + ", ".join(atomsim.ORBITALS.keys())),
            theme.dim("Real |psi|\u00b2 Monte-Carlo sampling — watch the cloud build up live."),
        ], title="orbitals", color=theme.PURPLE, width=WIDTH))
        raw = input(theme.dim("  orbital \u25b8 ")).strip().lower() or "1s"
        sound.play("sim_start")
        atomsim.orbital_simulation(raw)
        self.print_home()

    def cmd_orbitalgrid(self):
        print()
        print(theme.panel([
            theme.text("Hydrogen orbital reference chart", bold=True),
            theme.dim("Exports a multi-panel PNG of |\u03c8|\u00b2 for a spread of (n,l,m) orbitals,"),
            theme.dim("the same style as the classic textbook probability-density chart."),
        ], title="orbitalgrid", color=theme.PURPLE, width=WIDTH))
        sound.play("sim_start")
        try:
            path = atomsim.snapshot_orbital_grid()
        except Exception as e:
            path = None
        if path:
            print(theme.green(f"  Saved: {path}"))
        else:
            print(theme.red("  matplotlib/numpy/scipy not installed \u2014 export skipped."))
        self.print_home()

    def cmd_bonding(self, arg=""):
        from . import scires
        print()
        names = ", ".join(sorted(scires.MOLECULES.keys()))
        raw = arg.strip().lower()
        if not raw:
            print(theme.panel([
                theme.text("Chemical bonding density map (ELF-style)", bold=True),
                theme.dim(f"Available: {names}"),
                theme.dim("Stylized illustration, not an ab-initio DFT calculation."),
            ], title="bonding", color=theme.GREEN, width=WIDTH))
            raw = input(theme.dim("  molecule \u25b8 ")).strip().lower() or "furan"
        if raw not in scires.MOLECULES:
            print(theme.red(f"  Unknown molecule '{raw}'. Try: {names}"))
            self.print_home()
            return
        sound.play("sim_start")
        try:
            path = scires.render_bonding(raw)
        except Exception:
            path = None
        if path:
            print(theme.green(f"  Saved: {path}"))
        else:
            print(theme.red("  matplotlib/numpy/scipy not installed \u2014 export skipped."))
        self.print_home()

    def cmd_bloch(self, arg=""):
        from . import scires
        print()
        raw = (arg or "").strip()
        theta_deg, phi_deg = 90.0, 0.0  # default: the |+> state
        if raw:
            parts = raw.split()
            try:
                if len(parts) >= 1:
                    theta_deg = float(parts[0])
                if len(parts) >= 2:
                    phi_deg = float(parts[1])
            except ValueError:
                print(theme.red(f"  Couldn't parse '{raw}' as 'theta phi' in degrees, "
                                 f"e.g. /bloch 90 0"))
                self.print_home()
                return
        else:
            print(theme.panel([
                theme.text("Bloch sphere for a single qubit", bold=True),
                theme.dim("|\u03c8\u27e9 = cos(\u03b8/2)|0\u27e9 + e^{i\u03c6}sin(\u03b8/2)|1\u27e9"),
                theme.dim("Examples:  /bloch 0 0 = |0\u27e9   /bloch 90 0 = |+\u27e9   /bloch 90 90 = |+i\u27e9"),
            ], title="bloch", color=theme.CYAN, width=WIDTH))
            typed = input(theme.dim("  \u03b8 \u03c6 (degrees, blank = |+\u27e9) \u25b8 ")).strip()
            if typed:
                parts = typed.split()
                try:
                    if len(parts) >= 1:
                        theta_deg = float(parts[0])
                    if len(parts) >= 2:
                        phi_deg = float(parts[1])
                except ValueError:
                    print(theme.red(f"  Couldn't parse '{typed}' \u2014 using the default |+\u27e9 state."))

        sound.play("sim_start")

        def do_render():
            return scires.render_bloch_sphere(theta_deg, phi_deg)

        try:
            path = do_render()
        except Exception as e:
            retried = {}

            def _retry():
                retried["path"] = do_render()
                return retried["path"]
            ok = errors.error_card("render", e, retry=_retry, width=WIDTH)
            path = retried.get("path") if ok else None
        if path:
            print(theme.green(f"  Saved: {path}"))
        elif path is None and not scires.HAVE_DEPS:
            print(theme.red("  matplotlib/numpy/scipy not installed \u2014 export skipped."))
        self.print_home()

    # ----------------------------------------------------------- graphs --
    def cmd_workspace(self, arg=""):
        """v0.7.7 Workspace Manager — automatic detection (spec section
        1), multi-workspace history (sections 4/5), and generated-file
        browsing (the original behavior, fully preserved):
            /workspace                  -> manager dashboard
            /workspace <category>       -> browse generated files (original)
            /workspace detect           -> re-run automatic detection
            /workspace open <path>      -> open a folder as the workspace
            /workspace list             -> recent + pinned + favorite workspaces
            /workspace add <path> [label] -> add to history + open
            /workspace remove <path>    -> remove from history
            /workspace rename <path> <label> / <old> <new>
            /workspace pin <path>  / unpin <path>
            /workspace fav <path>  / unfav <path>
            /workspace last            -> last opened workspace
            /workspace search <query>  -> search history
            /workspace forget          -> clear all history
        """
        from . import workspace as ws
        from . import projects as projs
        raw = (arg or "").strip()

        # -- original behavior: category browsing (never removed) --------
        cat = raw.lower()
        if cat and cat in ws.CATEGORIES:
            files = ws.list_category(cat)
            lines = [theme.purple(f"WORKSPACE \u2014 {cat}", bold=True), ""]
            if not files:
                lines.append(theme.faint("Nothing here yet."))
            else:
                files.sort(key=lambda f: f["mtime"], reverse=True)
                for f in files[:20]:
                    size_kb = f["size"] / 1024
                    lines.append(f"{theme.cyan(f['name'])}  {theme.faint(f'{size_kb:.0f} KB')}")
            print()
            print(theme.panel(lines, title="workspace", color=theme.PURPLE, width=WIDTH))
            self.print_home()
            return

        parts = raw.split()
        sub = parts[0].lower() if parts else ""
        args_after = parts[1:] if len(parts) > 1 else []

        # -- /workspace detect ------------------------------------------
        if sub == "detect":
            print()
            lines = [theme.purple("WORKSPACE DETECTION", bold=True), ""]
            target = ws.detect_workspace()
            if target:
                lines.append(f"  Detected workspace: {theme.green(target, bold=True)}")
                branch = ws.git_branch(target)
                if branch:
                    lines.append(f"  Git branch: {theme.cyan(branch)}")
            else:
                lines.append(theme.faint("  No workspace detected yet \u2014 "
                                         "use /workspace open <path>."))
            print(theme.panel(lines, title="detect", color=theme.PURPLE, width=WIDTH))
            self.print_home()
            return

        # -- /workspace open <path> -------------------------------------
        if sub == "open":
            path = " ".join(args_after)
            if not path:
                path = input(theme.dim("  Folder to open (full path) \u25b8 ")).strip()
            path = path.strip('"').strip()
            if not path:
                self.print_home()
                return
            expanded = os.path.expanduser(path)
            if not os.path.isdir(expanded):
                print(theme.red(f"  \u2717 '{path}' is not a folder."))
                self.print_home()
                return
            projs.record_opened(expanded)
            ws.set_active_project(expanded)
            print()
            print(theme.green(f"  \u2713 Opened workspace: {expanded}", bold=True))
            branch = ws.git_branch(expanded)
            if branch:
                print(theme.dim(f"  Git branch: {branch}"))
            print(theme.faint("  (The Textual IDE uses /open \u2014 this sets the classic "
                              "workspace and history.)"))
            self.print_home()
            return

        # -- /workspace open-current: detect + open what's found --------
        if sub in ("open-current", "use-current", "this"):
            target = ws.detect_workspace()
            if not target:
                print(theme.orange("  No workspace detected in this directory."))
                self.print_home()
                return
            projs.record_opened(target)
            ws.set_active_project(target)
            print()
            print(theme.green(f"  \u2713 Workspace set: {target}", bold=True))
            self.print_home()
            return

        # -- /workspace list --------------------------------------------
        if sub in ("list", "history", "recent"):
            print()
            lines = [theme.purple("WORKSPACE HISTORY", bold=True), ""]
            rows = projs.workspaces()
            if not rows:
                lines.append(theme.faint("  Nothing yet \u2014 /workspace open <path> or "
                                         "detect a folder first."))
            else:
                for r in rows:
                    marks = ("\U0001f4cc" if r.get("pinned") else "\u00b7") \
                            + (" \u2b50" if r.get("favorite") else "")
                    label = r.get("label") or r["path"]
                    lines.append(f"  {marks} {theme.cyan(label, bold=True)}")
                    lines.append(f"      {theme.faint(r['path'])}")
                    if r.get("opened_at"):
                        import datetime
                        when = datetime.datetime.fromtimestamp(r["opened_at"])
                        lines.append(f"      {theme.faint('last opened ' + when.strftime('%Y-%m-%d %H:%M'))}")
            lines.append("")
            lines.append(theme.faint("Manage: pin/unpin, fav/unfav, rename, remove \u2014 "
                                     "see /workspace for usage."))
            print(theme.panel(lines, title="workspaces", color=theme.PURPLE, width=WIDTH))
            self.print_home()
            return

        # -- /workspace last --------------------------------------------
        if sub == "last":
            target = projs.last_opened()
            print()
            if target:
                print(theme.cyan("  Last opened: ") + theme.green(target, bold=True))
            else:
                print(theme.faint("  No recorded workspaces yet."))
            self.print_home()
            return

        # -- /workspace search <query> ----------------------------------
        if sub == "search":
            query = " ".join(args_after)
            if not query:
                query = input(theme.dim("  Search workspaces by path or label \u25b8 ")).strip()
            print()
            hits = projs.search(query)
            if not hits:
                print(theme.faint(f"  No workspaces match '{query}'."))
            else:
                for h in hits:
                    label = h.get("label") or h["path"]
                    print(f"  {theme.cyan(label)}  {theme.faint(h['path'])}")
            self.print_home()
            return

        # -- /workspace add <path> [label] ------------------------------
        if sub == "add":
            if not args_after:
                print(theme.orange("  Usage: /workspace add <path> [label]"))
                self.print_home()
                return
            path = args_after[0].strip('"')
            label = " ".join(args_after[1:]).strip() or None
            expanded = os.path.expanduser(path)
            if not os.path.isdir(expanded):
                print(theme.red(f"  \u2717 '{path}' is not a folder."))
                self.print_home()
                return
            projs.record_opened(expanded)
            if label:
                projs.rename(expanded, label)
            print(theme.green(f"  \u2713 Added '{label or expanded}' to workspace history."))
            self.print_home()
            return

        # -- /workspace remove <path> -----------------------------------
        if sub in ("remove", "delete", "rm"):
            if not args_after:
                print(theme.orange("  Usage: /workspace remove <path>"))
                self.print_home()
                return
            path = " ".join(args_after).strip('"')
            removed = projs.remove(path)
            if removed:
                print(theme.green(f"  \u2713 Removed '{path}' from workspace history."))
            else:
                print(theme.faint(f"  '{path}' wasn't in workspace history."))
            self.print_home()
            return

        # -- /workspace forget (clear all) ------------------------------
        if sub in ("forget", "clear"):
            projs.clear_recent()
            print(theme.green("  \u2713 Workspace history cleared."))
            self.print_home()
            return

        # -- /workspace rename <path|old-label> <new label> -------------
        if sub == "rename":
            if len(args_after) < 2:
                print(theme.orange("  Usage: /workspace rename <path> <new label>"))
                self.print_home()
                return
            old = args_after[0].strip('"')
            new_label = " ".join(args_after[1:]).strip()
            target = None
            for r in projs.workspaces():
                if r.get("label") == old or r["path"].lower() == old.lower() \
                        or os.path.basename(r["path"]).lower() == old.lower():
                    target = r["path"]
                    break
            if not target:
                print(theme.faint(f"  '{old}' isn't in workspace history."))
                self.print_home()
                return
            projs.rename(target, new_label)
            print(theme.green(f"  \u2713 Renamed to '{new_label}'."))
            self.print_home()
            return

        # -- /workspace pin / unpin / fav / unfav -----------------------
        def _resolve_target(arg_tokens):
            path = " ".join(arg_tokens).strip('"')
            for r in projs.workspaces():
                if r.get("label") == path or r["path"].lower() == path.lower() \
                        or os.path.basename(r["path"]).lower() == path.lower():
                    return r["path"]
            return os.path.abspath(os.path.expanduser(path)) if path else None

        if sub in ("pin", "unpin", "fav", "favorite", "unfav", "unfavorite"):
            target = _resolve_target(args_after)
            if not target:
                print(theme.orange("  Give a path or label from /workspace list."))
                self.print_home()
                return
            if sub in ("pin",):
                if not projs.is_pinned(target):
                    projs.toggle_pin(target)
                print(theme.green(f"  \U0001f4cc Pinned: {target}"))
            elif sub == "unpin":
                if projs.is_pinned(target):
                    projs.toggle_pin(target)
                print(theme.green(f"  \U0001f4cc Unpinned: {target}"))
            elif sub in ("fav", "favorite"):
                if not projs.is_favorite(target):
                    projs.toggle_favorite(target)
                print(theme.green(f"  \u2b50 Favorite: {target}"))
            else:
                if projs.is_favorite(target):
                    projs.toggle_favorite(target)
                print(theme.green(f"  \u2b50 Unfavorited: {target}"))
            self.print_home()
            return

        # -- /workspace (no args): manager dashboard --------------------
        print()
        lines = [theme.purple("WORKSPACE MANAGER", bold=True), ""]
        detected = ws.detect_workspace()
        active = ws.active_project()
        if active:
            lines.append(f"  \u25b8 Active: {theme.green(active, bold=True)}")
        else:
            lines.append("  \u25b8 Active: " + theme.faint("none \u2014 using the configured "
                                                          "workspace directory"))
        if detected:
            branch = ws.git_branch(detected)
            line = f"  \U0001f50d Detected: {theme.cyan(detected)}"
            if branch:
                line += theme.faint(f"  ({branch})")
            lines.append(line)
        lines.append("")
        rows = projs.workspaces()
        if rows:
            lines.append(theme.dim("History (newest first; \U0001f4cc = pinned, \u2b50 = favorite):"))
            for r in rows[:8]:
                marks = ("\U0001f4cc" if r.get("pinned") else "\u00b7") \
                        + (" \u2b50" if r.get("favorite") else "")
                label = r.get("label") or r["path"]
                lines.append(f"  {marks} {theme.cyan(label)}  {theme.faint(r['path'])}")
        lines.append("")
        lines.append(theme.dim("Commands:"))
        lines.append(theme.faint("  /workspace open <path>      open a folder as the workspace"))
        lines.append(theme.faint("  /workspace list             recent, pinned & favorite workspaces"))
        lines.append(theme.faint("  /workspace add/remove/rename/pin/fav/search/last"))
        lines.append(theme.faint("  /workspace <category>       browse generated files (original)"))
        print(theme.panel(lines, title="workspace", color=theme.PURPLE, width=WIDTH))

        # -- original summary of generated files, preserved -------------
        rows = ws.summary()
        lines = [theme.purple("GENERATED FILES", bold=True), ""]
        if not rows:
            lines.append(theme.faint("Nothing generated yet. Try /atomsim, /orbitals, /bonding, or /export."))
        else:
            for cat_name, count, newest, when in rows:
                lines.append(f"{theme.cyan(cat_name):<28} {count} file(s)  \u00b7  newest: {newest} ({when})")
        lines.append("")
        lines.append(theme.faint("Type /workspace <category> to browse one, e.g. /workspace graphs"))
        print(theme.panel(lines, title="generated files", color=theme.PURPLE, width=WIDTH))
        print()

    def cmd_graph(self):
        print()
        lines = [theme.purple("CHEMISTRY GRAPHS", bold=True), ""]
        for i, (key, desc) in enumerate(graphs.PRESETS, 1):
            lines.append(f"{theme.cyan(str(i)+'.')} {theme.text(desc)}")
        lines.append("")
        lines.append(theme.faint("Type a number for an animated terminal graph."))
        print(theme.panel(lines, title="graph", color=theme.CYAN, width=WIDTH))
        choice = input(theme.dim("  \u25b8 ")).strip()
        if not (choice.isdigit() and 1 <= int(choice) <= len(graphs.PRESETS)):
            self.print_home()
            return
        key, _ = graphs.PRESETS[int(choice) - 1]
        xs, ys, title, xlabel, ylabel = graphs.preset_curve(key)
        print()
        graphs.ascii_plot(xs, ys, title, xlabel, ylabel)
        export = input(theme.dim("\n  Export a high-quality PNG too? [y/N] \u25b8 ")).strip().lower()
        if export == "y":
            try:
                path = graphs.export_2d(xs, ys, title, xlabel, ylabel)
                print(theme.green(f"  Saved: {path}"))
                if key in ("radial_prob_1s",):
                    path3d = graphs.export_3d_surface("orbital_3d")
                    print(theme.green(f"  Saved 3D: {path3d}"))
            except Exception as e:
                print(theme.red(f"  Export failed (is matplotlib installed?): {e}"))
        input(theme.faint("\n  Press Enter to continue\u2026"))
        self.print_home()

    # -------------------------------------------------------- shortcuts --
    def cmd_shortcuts(self):
        from . import keys as _keys
        lines = [theme.purple("SHORTCUT KEYS", bold=True), "",
                 theme.cyan("Inside /atomsim and /orbitals live views:", bold=True)]
        for k, desc in _keys.SHORTCUTS_HELP:
            lines.append(f"  {theme.badge(k, theme.BG_INFO)}  {theme.dim(desc)}")
        lines.append("")
        lines.append(theme.cyan("Quick command aliases (type instead of the full command):", bold=True))
        for short, full in self.SHORT_ALIASES.items():
            lines.append(f"  {theme.badge(short, theme.BG_OK)}  {theme.dim('\u2192 ' + full)}")
        lines.append("")
        lines.append(theme.cyan("Anywhere in the terminal:", bold=True))
        lines.append(f"  {theme.badge('/back', theme.BG_INFO)}  {theme.dim('return to the previous menu')}")
        lines.append(f"  {theme.badge('/home or /clear', theme.BG_INFO)}  {theme.dim('jump to the home screen')}")
        lines.append(f"  {theme.badge('Ctrl+C', theme.BG_INFO)}  {theme.dim('quit instantly from anywhere')}")
        lines.append(f"  {theme.badge('a / f / h', theme.BG_INFO)}  {theme.dim('after any solved notebook: another / formula / home')}")
        lines.append("")
        lines.append(theme.faint(f"  \u2728 {len(self.eggs_found)} hidden easter egg(s) found this session \u2014 keep typing, some things aren't in any list."))
        print()
        print(theme.panel(lines, title="shortcuts", color=theme.PURPLE, width=WIDTH))
        print()

    # --------------------------------------------------------- formulas --
    def cmd_formulas(self):
        while True:
            print()
            lines = [theme.purple("FORMULA LIBRARY", bold=True), ""]
            for i, f in enumerate(FORMULAS, 1):
                lines.append(f"{theme.cyan(str(i)+'.')} {theme.text(f['name'])}  {theme.faint('['+f['tag']+']')}")
            lines.append("")
            lines.append(theme.faint("Type a number to expand, or /back to return home."))
            print(theme.panel(lines, title="formulas", color=theme.PURPLE, width=WIDTH))
            choice = input(theme.dim("  \u25b8 ")).strip().lower()
            if choice in ("/back", "back", "/exit", ""):
                break
            if choice.isdigit() and 1 <= int(choice) <= len(FORMULAS):
                self.show_formula(FORMULAS[int(choice) - 1])
            else:
                print(theme.red("  Not a valid choice."))
        self.print_home()

    def show_formula(self, f):
        lines = [theme.purple(f["name"], bold=True) + "  " + theme.faint("[" + f["tag"] + "]"), ""]
        for l in compose(f["formula"]).split("\n"):
            lines.append(theme.text(l, bold=True))
        lines.append("")
        for label, key in [("MEANING", "meaning"), ("VARIABLES", "variables"), ("UNITS", "units"),
                            ("CONDITIONS", "conditions"), ("COMMON MISTAKES", "mistakes"),
                            ("SHORTCUT TRICK", "trick"), ("MEMORY TRICK", "memory"), ("SOLVED EXAMPLE", "example")]:
            lines.append(theme.cyan(label, bold=True))
            for w in textwrap.wrap(f[key], width=WIDTH - 10) or [""]:
                lines.append(theme.dim(w))
            lines.append("")
        print()
        print(theme.panel(lines, title="formula", color=theme.CYAN, width=WIDTH))
        input(theme.faint("  Press Enter to continue\u2026"))

    # --------------------------------------------------------- kinetics --
    def cmd_kinetics(self):
        labels = {
            "zero": ("Zero Order", "R = R0 - kt"),
            "first": ("First Order", "k = (2.303/t) log(R0/R)"),
            "second": ("Second Order", "1/R = 1/R0 + kt"),
            "third": ("Third Order", "1/R\u00b2 = 1/R\u2080\u00b2 + 2kt"),
            "halflife": ("Half-Life", "t1/2 = 0.693/k"),
            "arrhenius": ("Arrhenius Equation", "k = A e^(-Ea/RT)"),
        }
        lines = [theme.purple("CHEMICAL KINETICS", bold=True), ""]
        for i, key in enumerate(KINETICS_ORDER, 1):
            name, formula = labels[key]
            lines.append(f"{theme.cyan(str(i)+'.')} {theme.text(name.ljust(24))} {theme.faint(formula)}")
        lines.append("")
        lines.append(theme.faint(f"{len(KINETICS_ORDER)+1}. Random kinetics numerical"))
        print()
        print(theme.panel(lines, title="kinetics", color=theme.PURPLE, width=WIDTH))
        choice = input(theme.dim("  \u25b8 ")).strip()
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(KINETICS_ORDER):
                self.solve(KINETICS_ORDER[idx - 1])
                return
            if idx == len(KINETICS_ORDER) + 1:
                self.solve(random.choice(KINETICS_ORDER))
                return
        self.print_home()

    # ---------------------------------------------------- electrochemistry --
    def cmd_electrochemistry(self):
        keys = [k for k, v in solver.FORMULA_LIBRARY.items() if v[1] == "Electrochemistry"]
        lines = [theme.purple("ELECTROCHEMISTRY", bold=True), ""]
        for i, key in enumerate(keys, 1):
            name, cat, formula_str, _ = solver.FORMULA_LIBRARY[key]
            lines.append(f"{theme.cyan(str(i)+'.')} {theme.text(name.ljust(28))} {theme.faint(mathify(formula_str))}")
        lines.append("")
        lines.append(theme.faint("Solved symbolically for any unknown, just like /solve."))
        print()
        print(theme.panel(lines, title="electrochemistry", color=theme.PURPLE, width=WIDTH))
        choice = input(theme.dim("  \u25b8 ")).strip()
        if choice.isdigit() and 1 <= int(choice) <= len(keys):
            self._solve_library(keys[int(choice) - 1])
        self.print_home()

    # ----------------------------------------------------------- history --
    def cmd_history(self):
        print()
        if not self.history:
            print(theme.panel([theme.dim("No notebooks yet \u2014 solve a numerical to see it here.")],
                               title="history", color=theme.PURPLE, width=WIDTH))
            print()
            return
        lines = [theme.purple("HISTORY", bold=True), ""]
        for i, nb in enumerate(self.history, 1):
            q = nb["question"]
            q = (q[:60] + "\u2026") if len(q) > 60 else q
            lines.append(f"{theme.cyan(str(i)+'.')} {theme.text(q)}")
            lines.append("   " + theme.faint(nb["topic"] + "  \u00b7  " + nb["final_answer"]))
        lines.append("")
        lines.append(theme.faint("Type a number to reopen, or /back to return home."))
        print(theme.panel(lines, title="history", color=theme.PURPLE, width=WIDTH))
        choice = input(theme.dim("  \u25b8 ")).strip().lower()
        if choice.isdigit() and 1 <= int(choice) <= len(self.history):
            print()
            render_notebook(self.history[int(choice) - 1])
            input(theme.faint("\n  Press Enter to continue\u2026"))
        self.print_home()

    # ---------------------------------------------------------- settings --
    def cmd_permissions(self, arg=""):
        from . import permissions as perm
        print()
        raw = (arg or "").strip().lower()
        if raw:
            if raw not in perm.MODES:
                print(theme.red(f"  Unknown mode '{raw}'. Try: {', '.join(perm.MODES)}"))
                self.print_home()
                return
            perm.manager.set_mode(raw)
            print(theme.green(f"  Permission mode set to {perm.manager.mode_label()}"))
            if raw == "full":
                print(theme.orange("  \u26a0 Full Access lets the AI create, edit, rewrite, delete, "
                                    "execute, and install without asking. Use with care."))
            self.print_home()
            return

        lines = [theme.purple("AI PERMISSIONS", bold=True), ""]
        for m in perm.MODES:
            marker = "\u25cf" if m == perm.manager.mode else "\u25cb"
            lines.append(f"{marker} {perm.MODE_LABELS[m]}" +
                         (theme.faint("  (current)") if m == perm.manager.mode else ""))
        lines.append("")
        lines.append(theme.dim("Ask Every Time  \u2014 every write/execute/shell action prompts, every time"))
        lines.append(theme.dim("Restricted      \u2014 AI can read/analyze/suggest; changes need review"))
        lines.append(theme.dim("Full Access     \u2014 AI acts without asking (visible warning shown)"))
        lines.append("")
        lines.append(theme.faint("Switch with: /permissions ask | restricted | full"))
        print(theme.panel(lines, title="permissions", color=theme.PURPLE, width=WIDTH))
        print()

    # ==================================================== v0.7.7 ============
    # Autonomous Development Preview — package manager, pipeline,
    # orchestrator, and responsible device control.
    # ========================================================================

    def _cli_perm_callback(self, key, action_label, path, reason):
        """Plain-CLI permission callback for pipeline/orchestrator runs
        (the agent tool loop and pipeline share this contract)."""
        from . import packages as pkgs
        print()
        if key == "install_packages":
            parts = action_label.replace("Install ", "", 1).strip()
            try:
                req, mgr = pkgs.resolve_request(parts or "package")
            except Exception:
                req, mgr = None, None
            if req and mgr:
                return self._cli_install_permission_prompt(req, pkgs.MANAGERS[mgr]["label"])
        lines = [theme.orange("PERMISSION REQUESTED", bold=True), "",
                 f"  Action: {theme.text(action_label)}",
                 (f"  Path:   {path}" if path else ""),
                 f"  Reason: {reason or 'Requested by the AI.'}",
                 "",
                 theme.dim("  [Enter] Allow   [a] Always Allow   [n] Deny   [x] Always Deny")]
        print(theme.panel(lines, title="permission", color=theme.ORANGE, width=WIDTH))
        choice = input(theme.dim("  \u25b8 ")).strip().lower()
        if choice in ("a", "always"):
            return "always_allow"
        if choice in ("x", "never"):
            return "always_deny"
        if choice in ("n", "no", "deny"):
            return "deny"
        return "allow"

    def _ensure_build_mode(self):
        """v0.7.7 spec section 4: only Build Mode may install/compile/
        build. Auto-switches with a visible transition when the user
        asks from another mode (spec section 5). Returns True when we
        are (now) in Build mode."""
        from . import ai_modes
        current = ai_modes.current_mode()
        if current == "build":
            return True
        from . import mode_detection
        transition = mode_detection.transition_line(current, "build",
                                                    "package / build responsibility")
        ai_modes.set_mode("build")
        if transition:
            print()
            print(theme.panel([theme.cyan(transition, bold=True)],
                              title="mode transition", color=theme.CYAN,
                              width=WIDTH))
            sound.play("notify")
        return True

    def _cli_install_permission_prompt(self, req, manager_label):
        """Spec section 3's install dialog for the classic terminal:
        Allow Once / Always Allow / Deny / Always Deny / Cancel, with
        the Remember-choice persisted for the exact package+manager."""
        from . import packages as pkgs
        print()
        lines = [theme.orange("PACKAGE INSTALL \u2014 permission required", bold=True),
                 "",
                 f"  Package: {theme.text(req.label(), bold=True)}",
                 f"  Manager: {manager_label}",
                 f"  System change: {theme.text('installs software on this machine', bold=True)}",
                 "",
                 theme.dim("  [1] Allow Once      [2] Always Allow   [3] Deny"),
                 theme.dim("  [4] Always Deny     [5] Cancel"),
                 theme.faint("  Choices are remembered for this package+manager if you pick 2 or 4.")]
        print(theme.panel(lines, title="permission", color=theme.ORANGE, width=WIDTH))
        choice = input(theme.dim("  \u25b8 ")).strip().lower()
        if choice in ("1", "", "y", "yes", "allow"):
            return "allow_once"
        if choice in ("2", "a", "always"):
            pkgs.remember_decision(req.manager, req.name, "allow")
            return "always_allow"
        if choice in ("3", "n", "no", "deny", "d"):
            return "deny"
        if choice in ("4", "ad", "never"):
            pkgs.remember_decision(req.manager, req.name, "deny")
            return "always_deny"
        return "cancel"

    def cmd_install(self, arg=""):
        """v0.7.7 Autonomous Package Manager — the full flow: parse,
        build-mode switch, research (for unknown packages), permission
        (with the temporary mode narrowing), install dashboard,
        auto-verification, summary."""
        from . import packages as pkgs
        from . import permissions as perm
        from . import package_research
        print()
        raw = (arg or "").strip()
        if not raw:
            raw = input(theme.dim("  What should I install? (e.g. requests, numpy, torch) \u25b8 ")).strip()
        if not raw:
            self.print_home()
            return

        self._ensure_build_mode()

        req, manager = pkgs.resolve_request(raw)
        if req is None:
            print(theme.orange(f"  '{raw}' doesn't look like an install request."))
            print(theme.dim("  Try: /install requests   /install numpy   /install NodeJS"))
            self.print_home()
            return

        if manager is None:
            # Spec section 2: unknown package -> research first.
            print(theme.cyan("  \U0001f50d Unknown package \u2014 researching it before installing..."))
            card = package_research.research_card(req)
            if card.get("info") or card.get("alternatives"):
                for line in package_research.render_card(req, card):
                    print(line)
                if card.get("alternatives"):
                    print(theme.faint("  Alternatives in the same family: "
                                      + ", ".join(a["name"] for a in card["alternatives"][:4])))
                print()
                print(theme.dim("  Recommendation: " + card.get("recommendation", "")))
            else:
                print(theme.orange("  Couldn't reach a registry or web search \u2014 installing "
                                   "on your judgment with pip (still approval-gated)."))
            manager = "pip"
        req.manager = manager

        # Spec section 3: temporary permission narrowing.
        flow = perm.install_flow_state()
        try:
            if not flow["allow"]:
                print(theme.red("  \u2717 Installs are completely disabled in Restricted mode "
                                "(v0.7.7 spec section 3)."))
                self.print_home()
                return
            remembered = pkgs.remembered_decision(manager, req.name)
            if remembered == "deny":
                print(theme.red(f"  \u2717 {req.label()} was previously denied (remembered choice) "
                                "\u2014 nothing installed. Use /packages forget to clear."))
                self.print_home()
                return
            decision = "allow_once"
            if remembered != "allow":
                if flow["prompt"]:
                    if flow.get("restore_to"):
                        print(theme.dim("  (permission mode temporarily narrowed to Ask Every Time "
                                        "for this install \u2014 restored afterwards)"))
                    decision = self._cli_install_permission_prompt(req, pkgs.MANAGERS[manager]["label"])
                    if decision in ("deny", "always_deny", "cancel"):
                        perm.manager.decide(manager, decision, "Install " + req.label())
                        verb = {"deny": "Denied", "always_deny": "Denied \u2014 remembered",
                                "cancel": "Cancelled"}[decision]
                        print(theme.orange(f"  {verb} \u2014 nothing was installed."))
                        self.print_home()
                        return
            else:
                print(theme.dim(f"  (approved before \u2014 remembered choice for {req.label()})"))

            # Installation dashboard + auto verification.
            events = []
            result = pkgs.run_install(req, on_event=lambda ev: events.append(ev))
            print()
            for line in pkgs.dashboard_lines(events):
                print(line)
            print()
            print(theme.panel(pkgs.summarize(result, req).splitlines(),
                              title="install result", color=theme.CYAN if result.get("ok") else theme.RED,
                              width=WIDTH))
            pkgs.announce(result, req)
            if result.get("ok"):
                print()
                print(theme.green("  \U0001f9f9 Environment updated \u00b7 dependency conflicts "
                                  "checked \u00b7 verified."))
        finally:
            perm.restore_mode()
            print()
            if flow.get("restore_to"):
                print(theme.dim(f"  Permission mode restored to {perm.MODE_LABELS[flow['restore_to']]}."))
        self.print_home()

    def cmd_packages(self, arg=""):
        """v0.7.7 installation dashboard: supported managers, their
        availability, remembered package decisions, and the persistent
        install history. Subcommands:
            /packages forget <name>     clears a remembered decision
            /packages history           lists past installs (newest first)
            /packages history <query>   searches history by package/manager
            /packages history remove <name>   drops a history record
            /packages history clear     empties the history"""
        from . import packages as pkgs
        raw = (arg or "").strip().lower()

        if raw.startswith("history"):
            import datetime as _dt
            parts = raw.split()
            if len(parts) >= 3 and parts[1] == "remove":
                name = " ".join(parts[2:])
                removed = pkgs.remove_history(name)
                print(theme.green(f"  Removed {removed} history record(s) for "
                                  f"'{name}' (installed package untouched)."))
                self.print_home()
                return
            if len(parts) >= 2 and parts[1] == "clear":
                pkgs.clear_history()
                print(theme.green("  Package history cleared."))
                self.print_home()
                return
            query = " ".join(parts[1:]) if len(parts) > 1 else ""
            records = pkgs.history_search(query)
            print()
            lines = [theme.purple("PACKAGE INSTALL HISTORY", bold=True), ""]
            if query:
                lines.append(theme.dim(f"matching '{query}':"))
                lines.append("")
            if not records:
                lines.append(theme.faint("  Nothing installed yet \u2014 ask CAT to "
                                         "'install <package>' and it lands here."))
            else:
                for r in records:
                    status = theme.green("\u2713") if r.get("ok") else theme.red("\u2717")
                    when = _dt.datetime.fromtimestamp(r.get("installed_at", 0)) \
                        .strftime("%Y-%m-%d %H:%M")
                    version = r.get("version") or "latest"
                    extra = ""
                    if r.get("updated_at") and r.get("updated_at") != r.get("installed_at"):
                        extra = theme.faint(" \u00b7 updated")
                    lines.append(f"  {status} {theme.cyan(r.get('name', '?'))} "
                                 f"{theme.faint(version)}  {theme.dim(r.get('manager', '') + ' \u00b7 ' + when + ' \u00b7 ' + str(r.get('env', '')))}{extra}")
                    if not r.get("ok"):
                        lines.append(theme.faint(f"      failed \u2014 exit {r.get('exit_code', '?')}"))
            lines.append("")
            lines.append(theme.faint("Search: /packages history <query>  \u00b7  Remove: "
                                     "/packages history remove <name>  \u00b7  Clear: "
                                     "/packages history clear"))
            print(theme.panel(lines, title="package history", color=theme.PURPLE,
                              width=WIDTH))
            self.print_home()
            return

        if raw.startswith("forget"):
            parts = raw.split()
            if len(parts) >= 2:
                name = parts[1]
                cleared = [k for k in pkgs.list_remembered() if k[1].lower() == name.lower()]
                for manager, n, _d in cleared:
                    pkgs.forget_decision(manager, n)
                print(theme.green(f"  Cleared {len(cleared)} remembered decision(s) for '{name}'."))
                self.print_home()
                return
        print()
        lines = [theme.purple("AUTONOMOUS PACKAGE MANAGER", bold=True), "",
                 theme.dim("Managers (supported: pip pipx uv conda npm pnpm yarn bun cargo go "
                           "composer vcpkg chocolatey winget apt dnf brew):"), ""]
        for key, spec in pkgs.MANAGERS.items():
            avail = "available" if pkgs.manager_available(key) else "not found"
            mark = "\u25cf" if avail == "available" else "\u25cb"
            lines.append(f"  {mark} {theme.cyan(key.ljust(12))} {theme.faint(spec['label'])}  "
                         f"{theme.green(avail) if avail == 'available' else theme.faint(avail)}")
        remembered = pkgs.list_remembered()
        if remembered:
            lines.append("")
            lines.append(theme.dim("Remembered install decisions (forget with /packages forget <pkg>):"))
            for manager, name, decision in remembered:
                mark = theme.green("allow") if decision == "allow" else theme.red("deny")
                lines.append(f"  {theme.faint(manager + ' / ' + name + ' \u2014 ')}{mark}")
        lines.append("")
        lines.append(theme.faint("Ask CAT 'install <package>' from any mode \u2014 installs are Build-mode work."))
        print(theme.panel(lines, title="packages", color=theme.PURPLE, width=WIDTH))
        print()
        self.print_home()

    def cmd_pipeline(self, arg=""):
        """v0.7.7 AI Execution Pipeline: Planner -> Research -> Build ->
        Testing -> Verification -> Documentation, fully visible."""
        from . import pipeline
        raw = (arg or "").strip()
        if not raw:
            print()
            print(theme.panel([theme.purple("AI EXECUTION PIPELINE", bold=True), "",
                               theme.dim("Runs the full autonomous workflow for one request:"), "",
                               theme.dim("Planner \u2192 Research \u2192 Implementation \u2192 Testing \u2192 "
                                         "Verification \u2192 Documentation \u2192 Completed"),
                               "",
                               theme.faint("Usage: /pipeline <your request>"),
                               theme.faint('e.g.  /pipeline build me a molecule viewer script')],
                              title="pipeline", color=theme.PURPLE, width=WIDTH))
            print()
            self.print_home()
            return

        print()
        print(theme.panel(pipeline.render_task_graph("planner"),
                          title="task graph", color=theme.CYAN, width=WIDTH))
        print()

        def _note(text):
            print(theme.cyan("  \u25b8 ") + text)

        def _message(text):
            print()
            print(text)

        def _todo(todo):
            status_mark = {"pending": theme.faint("\u25cb"),
                           "running": theme.cyan("\u25b8"),
                           "researching": theme.purple("\U0001f50d"),
                           "coding": theme.orange("\U0001f528"),
                           "testing": theme.cyan("\u2699"),
                           "completed": theme.green("\u2713"),
                           "skipped": theme.faint("\u2013"),
                           "failed": theme.red("\u2717")}.get(todo["status"], "\u2022")
            print(f"    {status_mark} {todo['text']}")

        def _stage(stage):
            from . import pipeline as _p
            print()
            for key, label, current in _p.task_graph(stage):
                if current:
                    print(theme.cyan(f"    \u25b8 {label}  {theme.orange('\u25cf CURRENT', bold=True)}"))
                else:
                    print(theme.faint(f"      {label}"))
            print()

        run = pipeline.PipelineRun(raw, mode="agent",
                                   on_note=_note, on_message=_message,
                                   on_todo=_todo, on_stage=_stage,
                                   permission_callback=self._cli_perm_callback)
        run.run()
        print()
        if run.final_text:
            fallback_cli.render_ai(run.final_text, tag="CAT Pipeline",
                                   model_label="planner\u00b7research\u00b7build\u00b7verify",
                                   duration=run.duration, term_width=WIDTH)
        print()
        self.print_home()

    def cmd_orchestrate(self, arg=""):
        """v0.7.7 Agent Orchestrator: the Coordinator monitors a roster
        of specialist agents working one request."""
        from . import orchestrator
        raw = (arg or "").strip()
        if not raw:
            print()
            print(theme.panel([theme.purple("AGENT ORCHESTRATOR", bold=True), "",
                               theme.dim("A Coordinator assigns specialist agents and monitors them:"), "",
                               theme.dim("Planner \u00b7 Research \u00b7 Coding \u00b7 Reviewer \u00b7 "
                                         "Testing \u00b7 Security \u00b7 Documentation \u00b7 Performance \u00b7 UI \u00b7 Architecture"),
                               "",
                               theme.faint("Usage: /orchestrate <your request>")],
                              title="orchestrator", color=theme.PURPLE, width=WIDTH))
            print()
            self.print_home()
            return

        def _agent(key, label, status, summary=""):
            if status == "start":
                print(theme.purple(f"  \u2699 {label} started"))
            else:
                extra = f" \u2014 {summary}" if summary else ""
                print(theme.green(f"  \u2713 {label} done{extra}"))

        print()
        final_text, _steps, _meta, _agents = orchestrator.run_orchestrated(
            raw, mode="agent", on_agent=_agent,
            permission_callback=self._cli_perm_callback)
        print()
        fallback_cli.render_ai(final_text, tag="CAT Orchestrator",
                               model_label="coordinator\u00b7team",
                               duration=0.0, term_width=WIDTH)
        print()
        self.print_home()

    def cmd_devices(self, arg=""):
        """v0.7.7 Responsible Device Control: provider roster and the
        activity log. Every device action requires explicit approval
        and is logged here."""
        from . import device_control as dc
        from . import permissions as perm
        raw = (arg or "").strip()
        if raw:
            # /devices <provider> <action> <target> — a quick approval-
            # gated way to drive an available provider.
            parts = raw.split(None, 2)
            provider_key = parts[0].lower()
            action = parts[1] if len(parts) > 1 else "run"
            target = parts[2] if len(parts) > 2 else ""
            resolved = dc.plan_action(provider_key, action, {"target": target})
            if not resolved["ok"]:
                print(theme.orange(f"  \u2717 {resolved['reason']}"))
                self.print_home()
                return
            plan = resolved["plan"]
            print()
            print(theme.panel([theme.orange("DEVICE ACTION \u2014 approval required", bold=True), "",
                               f"  Provider: {provider_key}",
                               f"  Action:   {action}",
                               f"  Target:   {plan.get('target', '') or target}",
                               f"  Effect:   {plan.get('effect', '')}",
                               "",
                               theme.dim("  [Enter] Allow   [n] Deny")],
                              title="device control", color=theme.ORANGE, width=WIDTH))
            choice = input(theme.dim("  \u25b8 ")).strip().lower()
            if choice == "n":
                dc.log_action(provider_key, action, target, "denied")
                print(theme.orange("  Denied \u2014 nothing ran."))
                self.print_home()
                return
            result = dc.execute_approved(provider_key, plan, {"target": target})
            if result.get("ok"):
                print(theme.green(f"  \u2713 Approved and executed \u2014 "
                                  + str(result.get("note") or result.get("exit_code") or "done")))
            else:
                print(theme.orange("  \u2717 " + str(result.get("note", "execution failed"))))
            self.print_home()
            return

        lines = [theme.purple("RESPONSIBLE DEVICE CONTROL", bold=True), "",
                 theme.dim("Every action affecting a real device requires explicit approval"),
                 theme.dim("and is recorded in the activity log below. Framework is extensible:"),
                 theme.dim("register_provider() in calc_terminal/device_control.py."), ""]
        for p in dc.available_providers():
            mark = "\u25cf" if p["available"] else "\u25cb"
            lines.append(f"  {mark} {theme.cyan(p['key'].ljust(11))} {theme.text(p['label'])}  "
                         + (theme.green("available") if p["available"] else theme.faint("extension point")))
            lines.append(theme.faint("      " + p["description"]))
        log = dc.activity(limit=15)
        if log:
            lines.append("")
            lines.append(theme.dim("Activity log (newest first):"))
            for entry in log:
                mark = theme.green("\u2713") if entry["decision"] == "approved" else theme.red("\u2717")
                lines.append(f"  {mark} {theme.faint(entry['provider'])} / {entry['action']} "
                             f"{entry['target'] or ''} \u2014 {entry['decision']}")
        else:
            lines.append("")
            lines.append(theme.faint("Activity log is empty \u2014 no device actions yet this session."))
        lines.append("")
        lines.append(theme.faint("Try: /devices terminal run 'git status'   \u00b7   "
                                 "permission key: device_control"))
        print(theme.panel(lines, title="devices", color=theme.PURPLE, width=WIDTH))
        print()
        self.print_home()

    def cmd_browser(self, arg=""):
        """CAT Browser — full terminal web browser (Fomoji-gated).

        Usage:
          /browser                  open CAT Browser at home
          /browser https://example.com  open that URL directly
          /browse <same>            alias
          /browser search cats on mars -> DuckDuckGo search
        The browser gate re-checks Fomoji before any network fetch so the
        session cannot be bypassed by collaring this command directly.
        """
        # Quick gating note before the blocking browser loop takes over.
        try:
            from .fomoji_auth import status as _fa_status
            from .fomoji_auth import get_identity as _fa_ident
            from .fomoji_auth import is_skip_enabled as _fa_skip
            if not _fa_skip() and _fa_status() != "connected":
                st = _fa_status()
                print()
                print(theme.red("  CAT Browser is locked — Fomoji authentication required.", bold=True))
                print(theme.dim(f"  Status: {st}  ·  run `cat --auth login` or use /auth inside CAT"))
                print()
                return
            ident = _fa_ident()
            if ident:
                print(theme.dim(f"  Browsing as {ident.get('name')} ({ident.get('fomojiId')}) — type `help` inside the browser.\n"))
        except Exception:
            pass

        # This method is only used when CCTApp is NOT running (fallback REPL).
        # In graphical mode, /browser is handled as a native UI command that
        # pushes BrowserScreen — so this code is the fallback-CLI path only.
        # We keep it but make it launch the graphical browser when Textual is
        # available; otherwise show a message (CLI “Links (6)” presentation
        # is removed from normal flow — see browser_shell.py).
        arg = (arg or "").strip()
        start_url = None
        if arg:
            low = arg.lower()
            if low.startswith("search ") or low.startswith("s "):
                q = arg.split(None, 1)[1].strip() if " " in arg else ""
                if q:
                    from .cat_browser import _search_url
                    start_url = _search_url(q)
                else:
                    start_url = None
            elif low.startswith("open "):
                start_url = arg.split(None, 1)[1].strip().strip('"').strip("'")
            else:
                from .cat_browser import _is_search_query, _search_url
                if " " in arg and _is_search_query(arg):
                    start_url = _search_url(arg)
                else:
                    start_url = arg

        # In fallback CLI with no Textual, we cannot show the graphical browser.
        # Show a clear message instead of dumping the old CLI numbered-links UI.
        try:
            from .ui.browser_shell import TEXTUAL_AVAILABLE as _HAS_UI
        except Exception:
            _HAS_UI = False
        if not _HAS_UI:
            print()
            print(theme.panel([
                theme.text("CAT Browser — graphical mode required", bold=True),
                theme.dim("The normal browser is graphical (tab bar + address bar + viewport)."),
                theme.dim("Textual is not installed in this environment, so the"),
                theme.dim("text-based Links/numbered navigation is no longer shown in normal use."),
                theme.dim("Install the UI and use the graphical browser:"),
                theme.cyan("  pip install textual[syntax]"),
                theme.cyan("  cat browse https://example.com"),
                theme.faint("Developer debug CLI is available via `cat --browser --text` (hidden)."),
            ], title="browser", color=theme.CYAN, width=76))
            print()
            self.print_home()
            return

        # Prefer Host embedded browser (correct architecture) — NOT text, NOT external
        try:
            from .host.launcher import can_launch_host, launch_cat_host, get_host_status
            if can_launch_host():
                launch_cat_host(start_browser_url=start_url or "about:home", start_mode="browser", block=True)
                self.print_home()
                return
            else:
                st = get_host_status()
                print()
                print(theme.panel([
                    theme.text("CAT Browser — embedded engine required", bold=True),
                    theme.dim(f"Reason: {st['reason']}"),
                    theme.dim("Browser INSIDE CAT requires: pip install PySide6"),
                    theme.dim("QWebEngineView child renders Fomoji inside CAT Host window"),
                    theme.cyan("  cat --host-browser http://localhost:3000/connector.html"),
                ], title="browser", color=theme.CYAN, width=76))
                print()
                self.print_home()
                return
        except Exception as e:
            print(theme.red(f"\n  Browser error: {type(e).__name__}: {e}\n"))
        finally:
            self.print_home()


    def cmd_settings(self):
        while True:
            cfg = cctconfig.get_config()
            lines = [theme.purple("SETTINGS", bold=True), ""]
            lines.append(f"{theme.cyan('1.')} Auto-save history .......... "
                         + (theme.green("[ ENABLED ]") if self.autosave else theme.orange("[ DISABLED ]")))
            lines.append(f"{theme.cyan('2.')} Clear history ............... {theme.faint('[ READY ]')}")
            lines.append(f"{theme.cyan('3.')} Decimal precision ........... {theme.faint(str(self.precision) + ' decimals')}")
            lines.append(f"{theme.cyan('4.')} Theme ........................ "
                         + theme.faint(theme.theme_label(theme.get_theme())))
            lines.append(f"{theme.cyan('5.')} Sound effects ................ "
                         + (theme.green("[ ON ]") if self.sound_enabled else theme.orange("[ OFF ]")))
            lines.append(f"{theme.cyan('6.')} Animated responses ........... "
                         + (theme.green("[ ON ]") if engine.ANIMATE else theme.orange("[ OFF ]")))
            lines.append(f"{theme.cyan('7.')} Animation speed .............. "
                         + theme.faint(f"{cfg.animation_speed:.1f}x  (config: ~/.cct_config.json)"))
            lines.append(f"{theme.cyan('8.')} Workspace directory .......... "
                         + theme.faint(cfg.workspace_directory))
            lines.append("")
            lines.append(theme.faint("Type a number to toggle, or /back to return home."))
            print()
            print(theme.panel(lines, title="settings", color=theme.PURPLE, width=WIDTH))
            choice = input(theme.dim("  \u25b8 ")).strip().lower()
            if choice == "1":
                self.autosave = not self.autosave
            elif choice == "2":
                self.history = []
                print(theme.green("  History cleared."))
            elif choice == "4":
                self.cmd_theme()
                cfg.default_theme = theme.get_theme()
                cctconfig.save_config(cfg)
            elif choice == "5":
                self.sound_enabled = not self.sound_enabled
                sound.set_enabled(self.sound_enabled)
                sound.play("notify")
            elif choice == "6":
                engine.set_animation(not engine.ANIMATE)
            elif choice == "7":
                steps = [0.5, 1.0, 1.5, 2.0]
                cur = min(steps, key=lambda s: abs(s - cfg.animation_speed))
                nxt = steps[(steps.index(cur) + 1) % len(steps)]
                cfg.animation_speed = nxt
                cctconfig.save_config(cfg)
                print(theme.green(f"  Animation speed set to {nxt:.1f}x."))
            elif choice == "8":
                raw = input(theme.dim("  new workspace directory \u25b8 ")).strip()
                if raw:
                    cfg.workspace_directory = os.path.expanduser(raw)
                    cctconfig.save_config(cfg)
                    print(theme.green(f"  Workspace directory set to {cfg.workspace_directory}"))
            elif choice in ("/back", "back", "/exit", ""):
                break
            else:
                continue
        self.print_home()

    # -------------------------------------------------------------- about --
    def cmd_about(self):
        config = aicore.load_config()
        cfg = cctconfig.get_config()
        ai_line = (theme.green(f"Configured \u2014 {config['provider']} / {config['model']}")
                   if config.get("provider") else theme.faint("Not configured \u2014 run /agent or /ai"))
        theme_line = theme.faint(theme.theme_label(theme.get_theme()))
        lines = [
            theme.purple(identity.APP_NAME.upper(), bold=True),
            theme.dim(f"{identity.SHORT_NAME} v{VERSION} \u00b7 Notebook Mode"),
            "",
            theme.text("A dedicated AI coding & scientific workspace styled like a modern dev terminal."),
            "",
            theme.cyan("Calculation engine", bold=True),
            theme.dim("Local numerical engine \u00b7 double-precision floating point \u00b7 sympy solver"),
            "",
            theme.cyan("Covers", bold=True),
            theme.dim("Mole Concept \u00b7 Chemical Kinetics \u00b7 Electrochemistry \u00b7 Gas Laws \u00b7"),
            theme.dim("Thermodynamics \u00b7 Equilibrium/Acid-Base \u00b7 Atomic & Quantum Structure"),
            "",
            theme.cyan("Agentic AI", bold=True),
            theme.dim("Status: ") + ai_line,
            "",
            theme.cyan("Current configuration", bold=True),
            theme.dim("Theme: ") + theme_line,
            theme.dim("Workspace: ") + theme.faint(cfg.workspace_directory),
        ]
        print()
        print(theme.panel(lines, title="about", color=theme.PURPLE, width=WIDTH))
        print()

    # ------------------------------------------------ v0.7.9 commands --
    def cmd_stats(self):
        """Real aggregated counts only — no PII by design (spec #6)."""
        from . import auth as _auth
        from . import safety_audit as _audit
        s = _auth.stats()
        retained = len(_audit.list_events(limit=_audit.MAX_EVENTS))
        lines = [
            theme.cyan("CAT Network", bold=True),
            "",
            theme.text(f"  Accounts         : {s['accounts']:,}"),
            theme.text(f"  Active sessions  : {s['active_sessions']:,}"),
            theme.faint(f"  Safety events retained on this device: {retained:,}"),
            "",
            theme.faint("Counts come from this machine's real account store."),
            theme.faint("No usernames/emails/private activity are exposed —"),
            theme.faint("aggregated numbers only, by design."),
        ]
        print()
        print(theme.panel(lines, title="stats", color=theme.CYAN, width=WIDTH))
        print()

    def cmd_report(self, arg=""):
        """Own-account safety report: text view or PDF/txt export."""
        from . import safety_audit as _audit
        arg = (arg or "").strip()
        if arg.lower().startswith(("export", "pdf")):
            parts = arg.split(None, 1)
            out = parts[1].strip() if len(parts) > 1 else os.path.join(
                cctconfig.get_config().workspace_directory,
                time.strftime("cat_safety_report_%Y%m%d_%H%M%S.pdf"))
            path, fmt = _audit.export_pdf(out)
            if fmt == "pdf":
                print(theme.green(f"\n  \u2713 PDF report written to {path}\n"))
            else:
                print(theme.yellow(
                    f"\n  \u26a0 reportlab isn't installed — wrote a UTF-8 text "
                    f"report instead:\n    {path}\n"
                    f"  (pip install reportlab for real PDF export)\n"))
            return
        print()
        print(_audit.render_report())
        print()

    def cmd_task(self, arg=""):
        """Large-task execution with live progress and real states."""
        arg = (arg or "").strip()
        if not arg:
            print(theme.dim("\n  Usage: /task <describe what CAT should do>\n"))
            return
        cfg = aicore.load_config()
        if not cfg.get("provider"):
            print(theme.red("\n  No AI provider configured — run /model first.\n"))
            return
        from . import orchestration as orch_mod
        client = orch_mod.TaskOrchestrator()
        print()
        print(theme.cyan(
            f"\u25b8 Orchestrating task with a dynamic agent team "
            f"(max {client.max_agents})\u2026", bold=True))

        def _activity(text):
            print(theme.dim(f"   {text}"))

        result = client.run(arg, on_activity=_activity)
        print()
        print(theme.cyan("TASK PROGRESS", bold=True))
        for slot in result.agents:
            mark = {"DONE": theme.green("\u2713"),
                    "RUNNING": theme.orange("\u2192"),
                    "FAILED": theme.red("\u2717"),
                    "TIMEOUT": theme.red("\u23f1"),
                    "CANCELLED": theme.yellow("\u229d"),
                    "SKIPPED": theme.yellow("\u229d"),
                    "WAITING": theme.faint("\u25cb")}.get(slot.state, "?")
            suffix = ""
            if slot.state in ("FAILED", "TIMEOUT") and slot.detail:
                suffix = theme.faint(f"  ({slot.detail[:60]})")
            print(f"   [{mark}] {slot.role:<11} {slot.summary}{suffix}")
        if result.changed_files:
            print()
            print(theme.cyan("FILE CHANGES (filesystem-verified)", bold=True))
            for p in result.changed_files[:20]:
                print(f"   ~ {p}")
        print()
        if result.cancelled:
            print(theme.yellow("  Cancelled before completion."))
        elif result.error:
            print(theme.red(f"  Finished with errors: {result.error}"))
        else:
            counts = result.progress_counts()
            print(theme.green(
                f"\u2713 Task complete \u2014 {counts.get('DONE', 0)} agent(s) done, "
                f"{counts.get('FAILED', 0) + counts.get('TIMEOUT', 0)} failed."))
        print()

    def cmd_auth(self, arg=""):
        """Account sign up / sign in / sign out / reset / delete."""
        import getpass
        from . import auth as _auth
        parts = (arg or "").strip().split(None, 1)
        sub = parts[0].lower() if parts else ""
        try:
            if sub == "signup":
                username = input(theme.dim("  Username \u25b8 ")).strip()
                email = input(theme.dim("  Email (optional) \u25b8 ")).strip()
                pw = getpass.getpass(theme.dim("  Password \u25b8 "))
                confirm = getpass.getpass(theme.dim("  Confirm password \u25b8 "))
                if pw != confirm:
                    print(theme.red("\n  Passwords don't match.\n"))
                    return
                info = _auth.sign_up(username, pw, email)
                print(theme.green("\n  \u2713 Account created."))
                print(theme.text("  Recovery key (shown ONCE — save it now): ")
                      + theme.bold(info["recovery_key"]))
                print(theme.faint("  It's the only offline way to reset your password.\n"))
            elif sub in ("signin", "login"):
                username = input(theme.dim("  Username \u25b8 ")).strip()
                pw = getpass.getpass(theme.dim("  Password \u25b8 "))
                token = _auth.sign_in(username, pw)
                self._auth_token = token
                acct = _auth.current_account(token)
                print(theme.green(
                    f"\n  \u2713 Signed in as {acct['username']} "
                    f"(session valid for 7 days).\n"))
            elif sub in ("signout", "logout"):
                token = getattr(self, "_auth_token", None)
                if token and _auth.sign_out(token):
                    self._auth_token = None
                    print(theme.green("\n  \u2713 Signed out.\n"))
                else:
                    print(theme.yellow("\n  No active session here.\n"))
            elif sub == "reset":
                username = input(theme.dim("  Username \u25b8 ")).strip()
                key = getpass.getpass(theme.dim("  Recovery key \u25b8 "))
                reset_token = _auth.request_reset(username, key)
                new = getpass.getpass(theme.dim("  New password \u25b8 "))
                confirm = getpass.getpass(theme.dim("  Confirm password \u25b8 "))
                if new != confirm:
                    print(theme.red("\n  Passwords don't match.\n"))
                    return
                _auth.complete_reset(reset_token, new)
                print(theme.green(
                    "\n  \u2713 Password reset — all previous sessions were signed out.\n"))
            elif sub == "delete":
                token = getattr(self, "_auth_token", None)
                acct = _auth.current_account(token) if token else None
                if not acct:
                    print(theme.red("\n  Sign in first (/auth signin).\n"))
                    return
                print(theme.yellow(
                    f"\n  This permanently deletes '{acct['username']}', "
                    "its sessions and its safety events."))
                if input(theme.dim("  Type DELETE to confirm \u25b8 ")).strip() != "DELETE":
                    print(theme.dim("\n  Cancelled — nothing was deleted.\n"))
                    return
                pw = getpass.getpass(theme.dim("  Confirm your password \u25b8 "))
                removed = _auth.delete_account(token, pw)
                self._auth_token = None
                print(theme.green(
                    f"\n  \u2713 Account deleted ({removed} safety event(s) removed).\n"))
            else:
                print(theme.dim(
                    "\n  Usage: /auth <signup|signin|signout|reset|delete>\n"
                    "  Passwords are stored as salted PBKDF2 hashes — never plaintext.\n"
                    "  Optional: set require_auth_for_ai=true in ~/.cct_config.json\n"
                    "  to make the AI answer only after /auth signin.\n"))
        except Exception as e:
            msg = getattr(e, "message", str(e))
            print(theme.red(f"\n  \u2717 {msg}\n"))

    def cmd_vscode(self, arg=""):
        """VS Code integration: status / open workspace|file|diff + CAT Vision commands."""
        from . import vscode_integration as vsc
        parts = (arg or "").strip().split(None, 1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""
        # Vision subcommands (spec 28)
        if sub in ("vision", "cat-vision", "cat:vision"):
            vsub = rest.split(None, 1)[0].lower() if rest else "open"
            vrest = rest.split(None, 1)[1] if " " in rest else ""
            vision_cmds = {
                "": "CAT: Open CAT Vision",
                "open": "CAT: Open CAT Vision",
                "start": "CAT: Start Vision Session",
                "stop": "CAT: Stop Vision Session",
                "analyze": "CAT: Analyze Current Screen",
                "selection": "CAT: Analyze Selected Region",
                "screenshot": "CAT: Send Screenshot to CAT",
            }
            if vsub in ("start", "stop", "analyze", "selection", "screenshot", "open", ""):
                print()
                print(theme.panel([
                    theme.text(vision_cmds.get(vsub, "CAT Vision"), bold=True),
                    theme.dim("Available in the CAT VS Code panel and via Command Palette (Ctrl+Shift+P)."),
                    theme.dim("Active file + selected code + workspace become the Vision AI context."),
                ], title="vscode vision", color=theme.CYAN, width=WIDTH))
                print()
                return
            print(theme.yellow(f"\n  Unknown /vscode vision subcommand '{vsub}'.\n"))
            return
        if sub in ("", "status"):
            st = vsc.status()
            state = theme.green("available") if st["available"] \
                else theme.red("not found")
            print(theme.dim(
                f"\n  VS Code CLI: {state}"
                + (theme.faint(f"  ({st['cli_path']})") if st["cli_path"] else "")))
            print(theme.faint(
                "  Usage: /vscode open [path] · /vscode file <path> "
                "[line] · /vscode diff <a> <b>"))
            print(theme.faint(
                "         /vscode vision [open|start|stop|analyze|selection|screenshot]\n"))
            return
        if sub == "open":
            ok, msg = (vsc.open_workspace(rest) if rest
                       else vsc.open_workspace_from_current())
        elif sub == "file":
            bits = rest.split()
            line = bits[1] if len(bits) > 1 and bits[1].isdigit() else None
            ok, msg = vsc.open_file(bits[0] if bits else "", line)
        elif sub == "diff":
            bits = rest.split()
            ok, msg = (vsc.open_diff(bits[0], bits[1])
                       if len(bits) >= 2
                       else (False, "Usage: /vscode diff <fileA> <fileB>"))
        else:
            ok, msg = False, f"Unknown /vscode subcommand '{sub}'."
        print(theme.green(f"\n  \u2713 {msg}\n") if ok
              else theme.yellow(f"\n  \u26a0 {msg}\n"))

    def cmd_colab(self, arg=""):
        """Notebook (.ipynb) tools: create / add / exec / export /
        upload-help — local-first, never touches Google credentials."""
        from . import colab_integration as col
        parts = (arg or "").strip().split(None, 2)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""
        try:
            if sub in ("", "status"):
                st = col.status()
                backend = st["execution_backend"] or theme.faint("none installed")
                print(theme.cyan("\n  Notebook / Colab support", bold=True))
                print(theme.dim(
                    f"  Local .ipynb tools : ready\n"
                    f"  Local execution    : {backend}\n"
                    f"  Google permissions : none requested (by design)\n"
                    f"  Google passwords   : never accepted\n"))
                print(theme.faint(
                    "  Usage:\n"
                    "    /colab new <title> [path.ipynb]\n"
                    "    /colab exec <notebook.ipynb>\n"
                    "    /colab script <notebook.ipynb> [out.py]\n"
                    "    /colab upload-help <notebook.ipynb>\n"))
                return
            if sub == "new":
                title = rest or "Untitled notebook"
                target = os.path.join(
                    cctconfig.get_config().workspace_directory,
                    re.sub(r"[^\w\- ]", "", title).strip().replace(" ", "_")
                    + ".ipynb")
                nb = col.create_notebook(title=title,
                                         first_markdown="Created by CAT.")
                path = col.save_notebook(nb, target)
                print(theme.green(f"\n  \u2713 Notebook created: {path}\n"))
            elif sub == "exec":
                result = col.execute_notebook(rest)
                mark = theme.green("\u2713") if result["executed"] \
                    and not result["error_cells"] else theme.red("\u2717")
                print(f"\n  {mark} {result['message']}")
                if result.get("output_path"):
                    print(theme.dim(f"  Saved outputs to {result['output_path']}"))
                print()
            elif sub in ("script", "export"):
                bits = rest.split()
                if not bits:
                    print(theme.red("\n  Usage: /colab script <nb.ipynb> [out.py]\n"))
                    return
                nb = col.load_notebook(bits[0])
                out = bits[1] if len(bits) > 1 else \
                    os.path.splitext(bits[0])[0] + ".py"
                path = col.export_script(nb, out)
                print(theme.green(f"\n  \u2713 Script exported: {path}\n"))
            elif sub == "upload-help":
                print()
                print(col.colab_upload_instructions(rest))
                print()
            else:
                print(theme.yellow(f"\n  Unknown /colab subcommand '{sub}'.\n"))
        except Exception as e:
            print(theme.red(f"\n  \u2717 {e}\n"))

    # ------------------------------------------------------------- upload --
    def cmd_upload(self):
        path = input(theme.dim("  Path to image/PDF (any value works in this prototype) \u25b8 ")).strip()
        print()
        run_steps(IMAGE_STEPS, step_time=0.3)
        print()
        intent = "first"
        prefix = f"(From uploaded image{': ' + path if path else ''})"
        self.solve(intent, prefix=prefix)

    # -------------------------------------------------------------- voice --
    def cmd_voice(self):
        sys.stdout.write("  " + theme.red("\u25cf Listening"))
        sys.stdout.flush()
        for _ in range(3):
            time.sleep(0.35)
            sys.stdout.write(theme.red("."))
            sys.stdout.flush()
        print()
        run_steps(["Processing..."], step_time=0.3)
        recognized = "first order half life numerical"
        print(theme.dim("  Recognized: ") + theme.text(f"\"{recognized}\""))
        self.handle_question(recognized)

    # --------------------------------------------------------------- game --
    def cmd_game(self):
        game.run_game(self)
        self.print_home()

    # ------------------------------------------------------- beta features ---
    def cmd_sim3d(self):
        print()
        print(theme.panel([
            theme.badge("BETA", theme.BG_WARN) + " " + theme.text("Real-time 3D Atomic Simulation", bold=True),
            theme.dim("Real-time calculation of atom, electron, and proton simulation."),
            theme.dim("Includes 3D graphs and real-time consequence mapping."),
            "",
            theme.dim("Enter an element symbol or Z (1-36)."),
        ], title="sim3d", color=theme.CYAN, width=WIDTH))
        raw = input(theme.dim("  element \u25b8 ")).strip() or "C"
        z = atomsim.resolve_element(raw)
        if z is None:
            print(theme.red(f"  Unknown element '{raw}'."))
            sound.play("error")
            return
        sound.play("sim_start")
        sim3d.atom_simulation_3d(z)
        ans = input(theme.dim(
            "  Open a real GPU-rendered 3D view of this atom in your browser? [y/N] "
        )).strip().lower()
        if ans == "y":
            path, err = gpu3d.export_atom_view(z)
            if err:
                print(theme.red(f"  {err}"))
            else:
                print(theme.dim(f"  Opened in browser (also saved: {path})"))
        self.print_home()

    def cmd_gpu3d(self):
        print()
        print(theme.panel([
            theme.badge("BETA", theme.BG_WARN) + " " + theme.text("GPU-Accelerated 3D (opens in browser)", bold=True),
            theme.dim("The terminal itself has no GPU access — this generates a real"),
            theme.dim("WebGL scene (three.js) and opens it in your default browser,"),
            theme.dim("rendered by your actual GPU with mouse orbit/pan/zoom."),
            "",
            theme.cyan("1", bold=True) + theme.dim("  Atom — nucleus + orbiting shell electrons"),
            theme.cyan("2", bold=True) + theme.dim("  Graph — 3D surface for z = f(x, z)"),
            theme.cyan("3", bold=True) + theme.dim("  Scale ladder — Planck length \u2192 observable universe"),
        ], title="gpu3d", color=theme.CYAN, width=WIDTH))
        choice = input(theme.dim("  choice \u25b8 ")).strip()

        if choice == "1":
            raw = input(theme.dim("  element \u25b8 ")).strip() or "C"
            z = atomsim.resolve_element(raw)
            if z is None:
                print(theme.red(f"  Unknown element '{raw}'."))
                sound.play("error")
                self.print_home()
                return
            path, err = gpu3d.export_atom_view(z)
        elif choice == "2":
            expr = input(theme.dim(
                "  z = f(x, z) in JS syntax, e.g. Math.sin(Math.sqrt(x*x+z*z)) \u25b8 ")).strip()
            path, err = gpu3d.export_graph_view(expr or "Math.sin(Math.sqrt(x*x+z*z))")
        else:
            path, err = gpu3d.export_scale_view()

        if err:
            print(theme.red(f"  {err}"))
        else:
            sound.play("sim_start")
            print(theme.green(f"  \u2713 Opened in browser (also saved: {path})"))
        self.print_home()

    def cmd_ai(self):
        # NEW: Run the same agentic loop as /agent, but with AI branding
        config = aicore.load_config()
        if not config.get("provider"):
            print(theme.orange("\n  No AI provider configured yet \u2014 let's set one up first.\n"))
            aicore.setup_ai()
            config = aicore.load_config()
            if not config.get("provider"):
                self.print_home()
                return

        def print_ai_header(conf):
            theme.clear_screen()
            print(theme.panel([
                theme.badge("BETA", theme.BG_WARN) + " " + theme.purple("\u2588 CAT TERMINAL \u2588", bold=True),
                theme.dim(f"CONNECTED: {conf['provider'].upper()} \u2503 MODEL: {conf['model']}"),
                theme.dim("SPECIALIST: QUANTUM CHEMISTRY \u2503 QUICK CONVERSATIONAL ANSWERS"),
                theme.dim("Talks normal, keeps it short \u2014 remembers you across chats (/memory)."),
                theme.dim("Need a full step-by-step notebook breakdown instead? Try /agent."),
                "",
                theme.faint("Commands: /back exit \u2503 /verify test \u2503 /setup reconfigure"),
                theme.faint("/memory what's remembered"),
            ], title="ai chat", color=theme.PURPLE, width=WIDTH, title_gradient=(theme.CYAN, theme.PURPLE)))

        print_ai_header(config)
        raw = ""

        while True:
            try:
                raw = fallback_cli.fallback_input(
                    label="AI", bg_color=theme.BG_AI, suggestions=AI_SUGGESTIONS, width=WIDTH,
                    placeholder="Ask a chemistry question\u2026",
                ).strip()
            except (KeyboardInterrupt, EOFError):
                raw = ""
                break
            if not raw:
                continue
            low = raw.lower()
            if low == "/back":
                break
            if low == "/setup":
                aicore.setup_ai()
                config = aicore.load_config()
                print_ai_header(config)
                continue
            if low == "/verify":
                ok, msg, models = aicore.verify_connection()
                print((theme.green if ok else theme.red)(("  \u2713 " if ok else "  \u2717 ") + msg))
                if models:
                    print(theme.faint("  " + ", ".join(str(m) for m in models[:8])))
                continue
            if low == "/memory":
                self.cmd_memory()
                continue
            if low == "/agent":
                break

            fallback_cli.render_user(raw, tag="you", term_width=WIDTH)
            fallback_cli.thinking(label="CCT AI", model_label=config.get("model"))
            t0 = time.time()
            final_text, steps, meta = agent.run_agent(raw, mode="ai")
            duration = time.time() - t0

            if aicore.is_error_response(final_text) and not steps:
                # a real provider failure, not a normal answer — show
                # the recovery card (spec section 19) instead of
                # rendering the failure text as if it were a chat reply
                retried = {}

                def _retry_ai(_raw=raw, _model_label=None):
                    ft, retry_steps, retry_meta = agent.run_agent(_raw, mode="ai")
                    if aicore.is_error_response(ft) and not retry_steps:
                        raise RuntimeError(ft)
                    retried["text"], retried["steps"], retried["meta"] = ft, retry_steps, retry_meta
                    return ft
                ok = errors.error_card(
                    "ai_provider", RuntimeError(final_text), retry=_retry_ai,
                    extra_actions=[
                        ("Reconnect", lambda: aicore.setup_ai()),
                        ("Switch Provider", lambda: self.cmd_model()),
                    ], width=WIDTH)
                if ok and "text" in retried:
                    # the retry succeeded — actually show that answer,
                    # don't just silently swallow it
                    final_text, steps, meta = retried["text"], retried["steps"], retried["meta"]
                else:
                    print()
                    continue

            model_label = f"{config.get('provider','').upper()} {config.get('model', '')}".strip()
            if steps:
                print(theme.dim(f"  ({len(steps)} tool step(s) run)"))
            # v0.5.6: adaptive OpenCode-style reply with avatar footer.
            fallback_cli.render_ai(final_text, tag="CCT AI", model_label=model_label,
                             duration=duration, term_width=WIDTH)
            changes = meta.get("file_changes") or ""
            if changes:
                print()
                print(theme.panel(_colorize_diff_lines(changes), title="File changes",
                                  color=theme.GREEN, width=WIDTH))
            if meta.get("suggest_agent"):
                print(theme.orange("  \U0001F4A1 That looked like a big one \u2014 try /agent for the "
                                    "full step-by-step notebook breakdown."))
            print()

        if raw.strip().lower() == "/agent":
            self.cmd_agent()
            return
        self.print_home()

    def cmd_ai_verify(self):
        print()
        print(theme.panel([
            theme.text("Verifying AI provider connection...", bold=True),
            theme.dim("Runs a real network round trip \u2014 not just a config-file check."),
        ], title="ai-verify", color=theme.CYAN, width=WIDTH))
        run_steps(["Loading configuration...", "Contacting provider..."], step_time=0.2)
        ok, msg, models = aicore.verify_connection()
        sound.play("success" if ok else "error")
        color = theme.GREEN if ok else theme.RED
        lines = [(theme.green if ok else theme.red)(("\u2713 " if ok else "\u2717 ") + msg, bold=True)]
        if models:
            lines.append("")
            lines.append(theme.dim("Models available:"))
            for m in models[:15]:
                lines.append("  " + theme.cyan("\u2022 ") + theme.text(str(m)))
            if len(models) > 15:
                lines.append(theme.faint(f"  \u2026and {len(models) - 15} more"))
        print()
        print(theme.panel(lines, title="ai-verify result", color=color, width=WIDTH))
        print()

    def cmd_memory(self, sub=None):
        if sub in ("clear", "wipe", "reset", "forget"):
            memory.clear()
            print()
            print(theme.panel([theme.green("\u2713 Memory cleared.", bold=True),
                                theme.dim("CAT no longer remembers any past turns, facts, or activity.")],
                               title="memory", color=theme.CYAN, width=WIDTH))
            print()
            return

        st = memory.stats()
        mem = memory.load()
        lines = [
            theme.purple("WHAT CAT REMEMBERS ABOUT YOU", bold=True),
            theme.dim("Shared by both /ai and /agent \u2014 persists across restarts."),
            "",
        ]
        lines.append(theme.fg("\u25cf STATS", theme.CYAN, bold=True))
        lines.append(f"  {st['turns']} conversation turn(s)  \u2022  {st['facts']} fact(s)  \u2022  "
                      f"{st['activity']} activity event(s)  \u2022  {st['topics']} topic(s)")
        lines.append("")

        facts = mem.get("facts", [])
        if facts:
            lines.append(theme.fg("\u25cf FACTS IT REMEMBERS", theme.CYAN, bold=True))
            for f in facts[-10:]:
                lines.append("  " + theme.dim("\u2022 ") + theme.text(f))
            lines.append("")

        topics = sorted(mem.get("topics", {}).items(), key=lambda kv: kv[1], reverse=True)
        if topics:
            lines.append(theme.fg("\u25cf TOPICS YOU ASK ABOUT MOST", theme.CYAN, bold=True))
            lines.append("  " + ", ".join(f"{k} ({v})" for k, v in topics[:8]))
            lines.append("")

        activity = mem.get("activity", [])[-8:]
        if activity:
            lines.append(theme.fg("\u25cf RECENT ACTIVITY (every movement)", theme.CYAN, bold=True))
            for a in reversed(activity):
                lines.append("  " + theme.dim("\u2022 ") + theme.text(a.get("label", a.get("type", ""))))
            lines.append("")

        if not facts and not topics and not activity:
            lines.append(theme.dim("Nothing remembered yet \u2014 use /ai or /agent a little and it'll build up."))
            lines.append("")

        lines.append(theme.faint("Type /memory clear to wipe all of it."))
        print()
        print(theme.panel(lines, title="memory", color=theme.CYAN, width=WIDTH))
        print()

    # ------------------------------------------------------- agentic ai --
    def cmd_agent(self):
        config = aicore.load_config()
        if not config.get("provider"):
            print(theme.orange("\n  No AI provider configured yet \u2014 let's set one up first.\n"))
            aicore.setup_ai()
            config = aicore.load_config()
            if not config.get("provider"):
                self.print_home()
                return

        theme.clear_screen()
        print(theme.panel([
            theme.badge("BETA", theme.BG_WARN) + " " + theme.purple("\u2588 CAT AGENT \u2588", bold=True),
            theme.dim(f"CONNECTED: {config['provider'].upper()} \u2503 MODEL: {config['model']}"),
            theme.dim("This agent doesn't just talk \u2014 it can SOLVE, PLOT, and SIMULATE for real."),
            theme.dim("Answers are long-form, notebook style \u2014 and it remembers you (/memory)."),
            "",
            theme.text("Try things like:", bold=True),
            theme.dim("  \u2022 \"solve ideal gas law with P=1, n=2, T=300\""),
            theme.dim("  \u2022 \"plot the arrhenius graph and export it\""),
            theme.dim("  \u2022 \"plot y = sin(x)*exp(-x/5) from 0 to 20 called Damped Wave\""),
            theme.dim("  \u2022 \"simulate an iron atom in 3d\"  /  \"show me the 2p orbital cloud\""),
            "",
            theme.faint("Commands: /back exit \u2503 /verify test \u2503 /setup reconfigure"),
            theme.faint("/memory what's remembered \u2503 /team toggle multi-agent mode"),
        ], title="agent", color=theme.PURPLE, width=WIDTH))

        team_mode = False

        while True:
            try:
                raw = fallback_cli.fallback_input(
                    label="AGENT", bg_color=theme.BG_AI, suggestions=AGENT_SUGGESTIONS, width=WIDTH,
                    placeholder="Ask the agent to solve, plot, or simulate\u2026",
                ).strip()
            except (KeyboardInterrupt, EOFError):
                break
            if not raw:
                continue
            low = raw.lower()
            if low == "/back":
                break
            if low == "/setup":
                aicore.setup_ai()
                config = aicore.load_config()
                continue
            if low == "/verify":
                ok, msg, models = aicore.verify_connection()
                print((theme.green if ok else theme.red)(("  \u2713 " if ok else "  \u2717 ") + msg))
                if models:
                    print(theme.faint("  " + ", ".join(str(m) for m in models[:8])))
                continue
            if low == "/memory":
                self.cmd_memory()
                continue
            if low == "/team":
                team_mode = not team_mode
                state = "ON — Researcher \u2192 Planner \u2192 Specialist \u2192 Programmer \u2192 Debugger \u2192 Tester (roles join only when needed)" if team_mode else "OFF — single agent"
                print(theme.dim(f"  Multi-agent mode: {state}"))
                continue

            fallback_cli.render_user(raw, tag="you", term_width=WIDTH)
            model_label = f"{config.get('provider','').upper()} {config.get('model', '')}".strip()

            if team_mode:
                def _on_agent(role_key, role_label, status, _cfg=config):
                    icon = {"researcher": "\U0001F50D", "planner": "\U0001F4CB", "specialist": "\u2699",
                            "programmer": "\U0001F9F1", "debugger": "\U0001F41E",
                            "tester": "\U0001F9EA"}.get(role_key, "\u25CF")
                    if status == "start":
                        print(theme.dim(f"  {icon} {role_label} working\u2026"))
                    else:
                        print(theme.dim(f"  \u2713 {role_label} done"))
                t0 = time.time()
                final_text, steps, meta = agent.run_multi_agent(
                    raw, on_agent=_on_agent, mode="agent")
                duration = time.time() - t0
                if meta.get("active_roles"):
                    print(theme.faint("  team: " + " \u2192 ".join(r.capitalize() for r in meta["active_roles"])))
                if meta.get("team_plan"):
                    print(theme.faint("  plan: " + " \u2192 ".join(meta["team_plan"])))
                dnote = meta.get("debug_note")
                if dnote and dnote.get("risk") not in ("none", None):
                    print(theme.orange(f"  \U0001F41E debugger risk: {dnote['risk']}"))
                if meta.get("tester_ok") is False:
                    print(theme.orange(f"  \u26a0 tester note: {meta.get('tester_note','')}"))
            else:
                fallback_cli.thinking(label="CCT Agent", model_label=config.get("model"))
                t0 = time.time()
                final_text, steps, meta = agent.run_agent(raw, mode="agent")
                duration = time.time() - t0

                if aicore.is_error_response(final_text) and not steps:
                    retried = {}

                    def _retry_agent(_raw=raw):
                        ft, retry_steps, retry_meta = agent.run_agent(_raw, mode="agent")
                        if aicore.is_error_response(ft) and not retry_steps:
                            raise RuntimeError(ft)
                        retried["text"], retried["steps"], retried["meta"] = ft, retry_steps, retry_meta
                        return ft
                    ok = errors.error_card(
                        "ai_provider", RuntimeError(final_text), retry=_retry_agent,
                        extra_actions=[
                            ("Reconnect", lambda: aicore.setup_ai()),
                            ("Switch Provider", lambda: self.cmd_model()),
                        ], width=WIDTH)
                    if ok and "text" in retried:
                        final_text, steps, meta = retried["text"], retried["steps"], retried["meta"]
                    else:
                        print()
                        continue

            if steps:
                print(theme.dim(f"  ({len(steps)} tool step(s) run)"))
            # v0.5.6: adaptive OpenCode-style reply (the agent's answers are
            # usually long/notebook-style, so render_ai picks the borderless
            # path automatically) with the `▣ tag · model · dur` footer.
            fallback_cli.render_ai(final_text, tag="CCT Agent", model_label=model_label,
                             duration=duration, term_width=WIDTH)
            changes = meta.get("file_changes") or ""
            if changes:
                print()
                print(theme.panel(_colorize_diff_lines(changes), title="File changes",
                                  color=theme.GREEN, width=WIDTH))
            print()

        self.print_home()

    # --------------------------------------------------------- code pad ---
    def cmd_codepad(self):
        code_editor.run_editor(self, mode="code")

    def cmd_textedit(self):
        code_editor.run_editor(self, mode="text")

    # ------------------------------------------------------- model/tokens --
    def cmd_model(self, arg=None):
        """/model — model picker with live auto-refresh, search & filters.
        Subcommands: /model refresh, /model search <query>, or switch to an
        explicitly typed model id directly (any model works, even brand-new
        ones not in any list yet)."""
        config = aicore.load_config()
        if not config.get("provider"):
            print(theme.orange("\n  No AI provider configured yet — let's set one up first.\n"))
            aicore.setup_ai()
            return

        arg = (arg or "").strip()
        low_arg = arg.lower()
        if low_arg == "refresh":
            self.cmd_refresh_models()
            return
        if low_arg == "search" or low_arg.startswith("search "):
            query = arg[6:].strip() if low_arg.startswith("search ") else ""
            self._model_picker(query=query)
            return
        if arg:
            ok, msg = aicore.switch_model(arg)
            print()
            print((theme.green if ok else theme.red)(("  ✓ " if ok else "  ✗ ") + msg))
            print()
            return

        self._model_picker()

    # ------------------------------------------------- model picker --------
    _MODEL_FILTERS = [
        ("all", "All"), ("free", "Free"), ("paid", "Paid"), ("latest", "Latest"),
        ("reasoning", "Reasoning"), ("coding", "Coding"), ("vision", "Vision"),
        ("fast", "Fast"), ("long_context", "Long Context"), ("image", "Image"),
        ("speech", "Speech"), ("embedding", "Embedding"), ("experimental", "Experimental"),
    ]

    def _model_picker(self, filter_id="all", query="", auto_refresh=True):
        """Interactive model picker: live/cached/default resolution,
        category filters, search, FREE/PAID badges, NEW/LATEST markers.
        Auto-refreshes from the provider's API when the cache is stale."""
        from .models import manager as _mgr
        config = aicore.load_config()
        provider_id = config.get("provider")
        if not provider_id:
            return
        provider = _mgr.get_provider(provider_id) or {}
        provider_name = provider.get("name", provider_id)
        current_model = config.get("model", "")

        print()
        run_steps(["Loading model registry...", "Checking cache..."], step_time=0.15)

        # Auto-refresh: stale cache -> fetch live from the provider's API
        refresh_note = ""
        if auto_refresh and not _mgr.cache_is_fresh(provider_id):
            print(theme.dim("  Checking for new models..."))
            models, source = _mgr.ensure_fresh(provider_id)
            if source == _mgr.SOURCE_LIVE:
                refresh_note = "  ✓ Updated successfully — new model list downloaded."
            elif source == _mgr.SOURCE_CACHED:
                refresh_note = "  Using cached model list."
            else:
                refresh_note = "  Using cached/default model list."
        else:
            models, source = _mgr.get_models(provider_id)

        entries = _mgr.enrich(provider_id, models)
        new_set = _mgr.new_models(provider_id)
        active_filter = filter_id or "all"
        active_query = query or ""

        while True:
            theme.clear_screen()
            lines = [
                theme.purple("SWITCH MODEL", bold=True),
                theme.dim(f"Provider: {provider_name}  │  Current model: {current_model}"),
                theme.dim(f"Source: {source.upper()}  │  "
                          + (f"Last refresh: {_mgr.get_last_refresh(provider_id)}" if _mgr.get_last_refresh(provider_id) else "No live fetch yet")
                          + f"  │  {len(models)} model(s)"),
            ]
            if refresh_note:
                lines.append(theme.green(refresh_note))
            lines.append("")
            print(theme.panel(lines, title="model", color=theme.PURPLE, width=WIDTH))

            shown = _mgr.apply_filter(entries, active_filter, new_set)
            if active_query:
                q = active_query.lower()
                shown = [e for e in shown if q in " ".join([
                    e["id"].lower(), e.get("family", "").lower(),
                    e.get("category", "").lower(),
                    " ".join(e["capabilities"]),
                    e.get("display_name", "").lower()])]
            shown = shown[:25]
            if not shown:
                print(theme.dim("  No models match — type /back to cancel."))
            for i, e in enumerate(shown, 1):
                badges = " ".join(e.get("badges", []))
                badges_str = f"  {theme.orange(badges)}" if badges else ""
                ctx = ("  " + theme.dim(f"{e.get('context_length', 0):,}")
                       if e.get("context_length") else "")
                print(f"  {theme.cyan(f'{i}.')} {e['id']}{badges_str}{ctx}")
            if len(_mgr.apply_filter(entries, active_filter, new_set)) > 25:
                print(theme.faint(f"  … {len(entries) - 25} more — use /search <query> to narrow down."))

            filter_row = "  ".join(
                theme.cyan(f"[{f_id}]") if f_id == active_filter else theme.dim(f"[{f_id}]")
                for f_id, _ in self._MODEL_FILTERS)
            print()
            print(theme.dim("  Filters: ") + filter_row)
            print(theme.faint("  Type: number to select  ·  /free /latest /vision … to filter  ·  "
                              "/search <query>  ·  /model <name> to type any model  ·  /back to cancel"))
            print()

            choice = input(theme.dim(f"  model ▸ ")).strip()
            low = choice.lower()
            if low in ("/back", "back", ""):
                return
            if low == "/refresh":
                self.cmd_refresh_models()
                return
            if low.startswith("/search") or low.startswith("/s "):
                active_query = choice.split(" ", 1)[1].strip() if " " in choice else ""
                continue
            if low.startswith("/"):
                cand = low.lstrip("/")
                for f_id, _label in self._MODEL_FILTERS:
                    if cand == f_id or (f_id == "long_context" and cand in ("long", "long-context", "context")):
                        active_filter = f_id
                        active_query = ""
                        break
                else:
                    if cand == "model":
                        model_name = input(theme.dim("  Type the exact model id ▸ ")).strip()
                        if model_name:
                            self._apply_model_switch(model_name, provider_id, current_model)
                            return
                continue
            if choice.isdigit() and shown and 1 <= int(choice) <= len(shown):
                self._apply_model_switch(shown[int(choice) - 1]["id"], provider_id, current_model)
                return
            if choice:
                self._apply_model_switch(choice, provider_id, current_model)
                return

    def _apply_model_switch(self, model_name, provider_id, old_model):
        ok, msg = aicore.switch_model(model_name)
        print()
        print((theme.green if ok else theme.red)(("  ✓ " if ok else "  ✗ ") + msg))
        print()

    # ------------------------------------------------------- /free --------
    def cmd_free(self):
        """Show only free models for the current provider."""
        config = aicore.load_config()
        if not config.get("provider"):
            print(theme.orange("\n  No AI provider configured yet — run /model to set one up.\n"))
            return
        self._model_picker(filter_id="free")

    # ------------------------------------------------------- /latest ------
    def cmd_latest(self):
        """Show the newest available models for the current provider."""
        config = aicore.load_config()
        if not config.get("provider"):
            print(theme.orange("\n  No AI provider configured yet — run /model to set one up.\n"))
            return
        self._model_picker(filter_id="latest")

    # ------------------------------------------------------ /provider -----
    def cmd_provider(self):
        """Switch AI provider — the full data-driven list from providers.json."""
        from .models import manager as _mgr
        config = aicore.load_config()
        current = config.get("provider", "")
        providers = _mgr.list_providers()

        print()
        lines = [
            theme.purple("SELECT PROVIDER", bold=True),
            theme.dim(f"Current: {current or 'none'}"),
            "",
        ]
        for i, p in enumerate(providers, 1):
            mark = "▶ " if p["id"] == current else "  "
            lines.append(f"{mark}{theme.cyan(f'{i}.')} {p['name']}  {theme.dim(p.get('country', ''))}")
        print(theme.panel(lines, title="provider", color=theme.PURPLE, width=WIDTH))
        print(theme.faint("Type a number to switch provider, or type a provider id directly. /back to cancel."))
        print()

        choice = input(theme.dim("  provider ▸ ")).strip()
        if choice.lower() in ("/back", "back", ""):
            return
        if choice.isdigit() and 1 <= int(choice) <= len(providers):
            pid = providers[int(choice) - 1]["id"]
        else:
            pid = choice.lower().strip()
        target = _mgr.get_provider(pid)
        if not target:
            print(theme.red(f"  ✗ Unknown provider: {pid}"))
            return

        cfg = dict(config)
        cfg["provider"] = pid
        if target.get("api_endpoint"):
            cfg["base_url"] = target["api_endpoint"]
            cfg["api_url"] = target["api_endpoint"]
        if target.get("api_style"):
            cfg["api_style"] = target["api_style"]
        if target.get("needs_key", True) and not cfg.get("api_key"):
            key = input(theme.dim(f"  API Key for {target['name']} (Enter to skip) ▸ ")).strip()
            if key:
                cfg["api_key"] = key
        fallback = [str(m) for m in target.get("fallback_models", [])]
        if fallback:
            cfg["model"] = fallback[0]
        elif cfg.get("model"):
            cfg.pop("model", None)
        from .providers import provider_manager as _pm
        _pm.save_config(cfg)
        print(theme.green(f"\n  ✓ Switched provider to {target['name']}."))
        print(theme.dim("  Pick a model: "))
        self._model_picker()

    # ------------------------------------------------------- /status ------
    def cmd_status(self):
        """Provider / model / source / last-refresh status panel."""
        from .models import manager as _mgr
        from .providers import provider_manager as _pm
        config = aicore.load_config()
        provider_id = config.get("provider")
        if not provider_id:
            print(theme.orange("\n  No AI provider configured yet — run /model to set one up.\n"))
            return
        st = _pm.get_provider_status(provider_id, config.get("model", ""))
        print()
        source_label = {"live": "Live", "cached": "Cached", "default": "Default"}.get(
            st.get("model_source", ""), st.get("model_source", "—"))
        lines = [
            theme.purple("AI STATUS", bold=True),
            f"  {theme.cyan('Provider:')}        {st.get('provider_name', provider_id)} ({st.get('country', '')})",
            f"  {theme.cyan('Current model:')}   {st.get('current_model') or '(none)'}",
            f"  {theme.cyan('Model source:')}    {source_label}",
            f"  {theme.cyan('Last refresh:')}    {st.get('last_refresh') or '(never — using default list)'}",
            f"  {theme.cyan('Cache age:')}       " + (
                f"{st['cache_age_hours']:.1f} h" if st.get("cache_age_hours") is not None else "—"),
            f"  {theme.cyan('Models visible:')}  {st.get('model_count', 0):,}",
            "",
            theme.dim("  Capabilities:"),
            theme.dim(f"    Listing: {'✓' if st.get('supports_model_listing') else '✗'}   "
                      f"Streaming: {'✓' if st.get('supports_streaming') else '✗'}   "
                      f"Vision: {'✓' if st.get('supports_vision') else '✗'}   "
                      f"Embeddings: {'✓' if st.get('supports_embeddings') else '✗'}"),
            theme.dim(f"    Audio: {'✓' if st.get('supports_audio') else '✗'}   "
                      f"Reasoning: {'✓' if st.get('supports_reasoning') else '✗'}   "
                      f"OpenAI-compatible: {'✓' if st.get('openai_compatible') else '✗'}   "
                      f"Free models: {'✓' if st.get('free_models_available') else '✗'}"),
            "",
            theme.faint("Source is Live when fetched from the provider's API,"),
            theme.faint("Cached when reused from cache/models/, Default when offline."),
        ]
        print(theme.panel(lines, title="status", color=theme.CYAN, width=WIDTH))
        print()

    # ------------------------------------------------- /refresh-models ----
    def cmd_refresh_models(self, arg=None):
        """Force-refresh the model list from the selected provider's API."""
        from .models import manager as _mgr
        config = aicore.load_config()
        provider_id = config.get("provider")
        if not provider_id:
            print(theme.orange("\n  No AI provider configured yet — run /model to set one up.\n"))
            return
        provider = _mgr.get_provider(provider_id) or {}
        print()
        print(theme.dim(f"  Refreshing model list for {provider.get('name', provider_id)} ..."))
        run_steps(["Checking for new models...", "Downloading..."], step_time=0.3)
        models, source = _mgr.refresh_models(provider_id)
        print()
        if models and source == _mgr.SOURCE_LIVE:
            print(theme.green(f"  ✓ Updated successfully — {len(models)} model(s) from the provider's API."))
            cached = _mgr.get_cached(provider_id)
            if cached:
                print(theme.dim(f"  Cached at: {cached[1]}"))
            print(theme.faint("  Tip: /model search <query> to narrow them down."))
        elif models and source == _mgr.SOURCE_CACHED:
            print(theme.orange(f"  ⚠ Couldn't reach the API — using cached list ({len(models)} model(s))."))
        else:
            print(theme.orange(f"  ⚠ Couldn't reach the API — using built-in default list ({len(models)} model(s))."))
        print()

    def cmd_tokens(self):
        usage = aicore.get_session_usage()
        pct = 0.0
        if usage["context_window"]:
            pct = min(100.0, 100.0 * usage["total_tokens"] / usage["context_window"])
        lines = [
            theme.purple("SESSION TOKEN USAGE", bold=True),
            theme.dim(f"Model: {usage['model']}"),
            "",
            f"{theme.cyan('Prompt tokens:')}     {usage['prompt_tokens']:,}",
            f"{theme.cyan('Completion tokens:')} {usage['completion_tokens']:,}",
            f"{theme.cyan('Total used:')}        {usage['total_tokens']:,}",
            f"{theme.cyan('AI requests made:')}  {usage['requests']:,}",
            "",
            f"{theme.dim('Estimated context window:')} {usage['context_window']:,} tokens",
            f"{theme.dim('Estimated remaining:')} {usage['remaining_estimate']:,} tokens ({100 - pct:.1f}% free)",
            "",
            theme.faint("Real usage is read from the provider's response when it reports it;"),
            theme.faint("otherwise estimated at ~4 characters/token."),
        ]
        print()
        print(theme.panel(lines, title="tokens", color=theme.CYAN, width=WIDTH))
        print()

    # ------------------------------------------------------------- theme --
    def cmd_theme(self, arg=None):
        if not arg:
            arg = "textual-light" if not theme.is_light() else "tokyo-night"
        new_name = theme.set_theme(arg)
        print()
        print(theme.panel([
            theme.green(f"✓ Theme switched to {theme.theme_label(new_name)}.", bold=True),
            theme.dim("Applies to panels, chat bubbles, and badges across the whole app."),
            theme.dim("All themes: " + ", ".join(theme.available_themes())),
        ], title="theme", color=theme.CYAN, width=WIDTH))
        print()

    # -------------------------------------------------------- web search --
    def cmd_websearch(self, query=None):
        if not query:
            query = input(theme.dim("  search ▸ ")).strip()
        if not query:
            return
        print()
        run_steps(["Searching the web..."], step_time=0.25)
        results = aicore.web_search(query, max_results=6)
        if not results:
            print(theme.orange("  No results (unreachable, or the query returned nothing)."))
            print()
            return
        lines = [theme.purple(f'Results for "{query}"', bold=True), ""]
        for i, r in enumerate(results, 1):
            lines.append(theme.cyan(f"{i}. {r['title']}", bold=True))
            lines.append(theme.faint(f"   {r['url']}"))
            if r["snippet"]:
                lines.append(theme.dim("   " + textwrap.shorten(r["snippet"], width=WIDTH - 6)))
            lines.append("")
        print(theme.panel(lines, title="websearch", color=theme.CYAN, width=WIDTH))

    def cmd_research(self, topic=None):
        if not topic:
            topic = input(theme.dim("  research topic ▸ ")).strip()
        if not topic:
            return
        print()
        run_steps(["Planning search angles...", "Searching the web...", "Synthesizing findings..."], step_time=0.3)
        summary, sources = aicore.deep_research(topic)
        lines = [theme.purple(f"Deep research: {topic}", bold=True), ""]
        lines.extend(theme.text(l) for l in summary.split("\n"))
        if sources:
            lines.append("")
            lines.append(theme.cyan("SOURCES", bold=True))
            for i, s in enumerate(sources, 1):
                lines.append(theme.faint(f"[{i}] {s['title']} — {s['url']}"))
        print(theme.panel(lines, title="research", color=theme.PURPLE, width=WIDTH))
        print()

    # -------------------------------------------------------------- import --
    def cmd_pet(self):
        print()
        print(theme.panel(
            [theme.text("Your CCT mascot pet — lives right above the prompt.", bold=True), "",
             theme.faint("  Fire off questions quickly and it runs; a normal pace"),
             theme.faint("  and it walks; leave the terminal alone a while and it"),
             theme.faint("  falls asleep. Here's all three, back to back:")],
            title="pet", color=theme.CYAN, width=WIDTH))
        print()
        pet.demo(width=WIDTH)

    # --------------------------------------------------- reaction sim --
    def cmd_react(self, arg=None):
        print()
        if not arg:
            lines = [theme.purple("REACTION SIMULATOR", bold=True), "",
                     theme.text("Type an equation to balance it, e.g.:"),
                     theme.cyan("  Fe + O2 -> Fe2O3"),
                     theme.cyan("  C3H8 + O2 -> CO2 + H2O"),
                     "",
                     theme.faint("Or run a live playback:"),
                     theme.dim("  /react kinetics   — concentration vs time (order 0/1/2)"),
                     theme.dim("  /react equilibrium — A + B ⇌ C + D approach to Keq")]
            print(theme.panel(lines, title="react", color=theme.PURPLE, width=WIDTH))
            arg = input(theme.dim("  ▸ ")).strip()
            if not arg:
                self.print_home()
                return

        if arg.lower().startswith("kinetics"):
            self._react_kinetics()
        elif arg.lower().startswith(("equilibrium", "equil")):
            self._react_equilibrium()
        else:
            self._react_balance(arg)
        print()

    def _react_balance(self, eq):
        try:
            balanced, coeffs, reactants, products = reactionsim.balance_equation(eq)
        except reactionsim.BalanceError as e:
            # already a purpose-built, human-readable message from
            # reactionsim itself — a recovery card would just add
            # ceremony around text that's already clear, and "Retry"
            # doesn't help without different input anyway.
            print(theme.red(f"  \u2717 {e}"))
            return
        except Exception as e:
            # genuinely unexpected — the raw message here could be
            # anything from a Python internals error, so offer View
            # Details instead of dumping it inline by default.
            errors.error_card("balance", e, width=WIDTH)
            return
        lines = [theme.text("Input:  " + eq, bold=False),
                 theme.green("Balanced: " + balanced, bold=True), "",
                 theme.faint("Coefficients: " + ", ".join(str(c) for c in coeffs))]
        print(theme.panel(lines, title="balanced equation", color=theme.GREEN, width=WIDTH))

    def _react_kinetics(self):
        order_in = input(theme.dim("  order (0/1/2) [1] ▸ ")).strip() or "1"
        try:
            order = int(order_in)
        except ValueError:
            order = 1
        k_in = input(theme.dim("  rate constant k [0.1] ▸ ")).strip() or "0.1"
        c0_in = input(theme.dim("  initial [A]0 [1.0] ▸ ")).strip() or "1.0"
        t_in = input(theme.dim("  time span (s) [20] ▸ ")).strip() or "20"
        try:
            k, c0, t_end = float(k_in), float(c0_in), float(t_in)
        except ValueError:
            print(theme.red("  ✗ Enter numeric values."))
            return
        times, series = reactionsim.kinetics_series(order, k, c0, t_end)
        chart = reactionsim.ascii_chart({f"[A] (order {order})": series}, times, height=14, width=54)
        lines = [theme.text(l) for l in chart]
        lines.append("")
        lines.append(theme.faint(f"Integrated with RK4 · k={k} · [A]\u2080={c0} · t=0\u2192{t_end}s"))
        print(theme.panel(lines, title="kinetics playback", color=theme.CYAN, width=WIDTH))

    def _react_equilibrium(self):
        kf_in = input(theme.dim("  forward rate kf [0.5] ▸ ")).strip() or "0.5"
        kb_in = input(theme.dim("  reverse rate kb [0.1] ▸ ")).strip() or "0.1"
        a0_in = input(theme.dim("  initial [A]0 [1.0] ▸ ")).strip() or "1.0"
        b0_in = input(theme.dim("  initial [B]0 [1.0] ▸ ")).strip() or "1.0"
        try:
            kf, kb, a0, b0 = float(kf_in), float(kb_in), float(a0_in), float(b0_in)
        except ValueError:
            print(theme.red("  ✗ Enter numeric values."))
            return
        times, A, B, C, D = reactionsim.equilibrium_series(kf, kb, a0, b0, 0.0, 0.0, 30)
        chart = reactionsim.ascii_chart({"[A]": A, "[B]": B, "[C]": C, "[D]": D}, times, height=14, width=54)
        lines = [theme.text(l) for l in chart]
        keq = (C[-1] * D[-1]) / (A[-1] * B[-1]) if A[-1] * B[-1] > 1e-9 else float("inf")
        lines.append("")
        lines.append(theme.faint(f"A + B \u21cc C + D  ·  kf={kf}, kb={kb}  ·  Keq \u2248 {keq:.4g} at t={times[-1]:.3g}s"))
        print(theme.panel(lines, title="equilibrium playback", color=theme.CYAN, width=WIDTH))

    # ------------------------------------------------------------ export --
    def cmd_export(self, arg=None):
        print()
        if not self.history:
            print(theme.orange("  No notebooks solved yet this session — nothing to export."))
            print()
            return
        fmt = (arg or "").strip().lower()
        if fmt not in ("md", "markdown", "pdf"):
            print(theme.panel(
                [theme.text(f"{len(self.history)} notebook(s) ready to export."), "",
                 theme.dim("  md   — Markdown file"),
                 theme.dim("  pdf  — Formatted PDF" + ("" if report.PDF_AVAILABLE else " (reportlab not installed)"))],
                title="export", color=theme.PURPLE, width=WIDTH))
            fmt = input(theme.dim("  format [md/pdf] \u25b8 ")).strip().lower() or "md"

        def do_export():
            out_dir = report.default_export_dir()
            stamp = time.strftime("%Y%m%d_%H%M%S")
            if fmt in ("pdf",):
                path = os.path.join(out_dir, f"cct_export_{stamp}.pdf")
                report.export_history_pdf(self.history, path)
            else:
                path = os.path.join(out_dir, f"cct_export_{stamp}.md")
                report.export_history_markdown(self.history, path)
            sound.play("success")
            print(theme.green(f"  \u2713 Exported {len(self.history)} notebook(s) to {path}"))

        try:
            do_export()
        except Exception as e:
            sound.play("error")
            errors.error_card("export", e, retry=do_export, width=WIDTH)
        print()

    # --------------------------------------------------------------- tui --
    def cmd_tui(self):
        print()
        config = aicore.load_config()
        stats = {
            "solved": len(self.history),
            "provider": config.get("provider") or "none",
            "model": config.get("model") or "none",
        }
        ok, msg = tui.launch_dashboard(self.history, stats)
        if not ok:
            print(theme.orange(f"  {msg}"))
        print()
        self.print_home()

        print()

    # ---------------------------------------------------------- composer --
    def cmd_composer(self):
        """Launches CCT's primary interface — the Textual chat UI in
        calc_terminal/ui/ (ConversationView + StickyComposer + streaming +
        inline permission cards). Kept as an explicit command so it's
        reachable from inside a fallback-CLI session too (e.g. a session
        that started piped but is now at a real terminal); normally
        main.py launches this UI directly at startup instead of the
        fallback loop. Separate from /tui's read-only history dashboard."""
        print()
        config = aicore.load_config()
        stats = {
            "solved": len(self.history),
            "provider": config.get("provider") or "none",
            "model": config.get("model") or "none",
        }
        from .ui.app import launch_chat_app
        ok, msg = launch_chat_app(self, self.history, stats)
        if not ok:
            print(theme.orange(f"  {msg}"))
        print()
        self.print_home()
        print()

    def cmd_copycode(self):
        block = code_editor.get_last_block()
        if not block:
            print(theme.orange("  No code block has been shown yet — ask /ai or /agent for some code first."))
            print()
            return
        ok, detail = code_editor.copy_to_clipboard(block["code"])
        n_lines = block["code"].count("\n") + 1
        lang = block["lang"] or "code"
        print()
        if ok:
            print(theme.green(f"  ✓ Copied the last {lang} block ({n_lines} line(s)) to the clipboard (via {detail})."))
        else:
            saved_ok, saved_path = code_editor._save_buffer(block["code"].split("\n"), None)
            if saved_ok:
                print(theme.orange(f"  Clipboard unavailable ({detail}).") + " " +
                      theme.green(f"Saved instead to {saved_path} — open it to copy."))
            else:
                print(theme.red(f"  ✗ Clipboard unavailable ({detail}), and saving a fallback also failed."))
        print()

    def cmd_import(self, path=None):
        if not path:
            path = input(theme.dim("  Path to a text file, image, or .zip ▸ ")).strip()
        if not path:
            return
        path = os.path.expanduser(path)
        if not os.path.exists(path):
            print(theme.red(f"  ✗ File not found: {path}"))
            return
        if path.lower().endswith(".zip"):
            self._cmd_import_zip(path)
            return
        agent.add_attachment(path)
        if aicore.is_image_file(path):
            config = aicore.load_config()
            if not config.get("provider"):
                print(theme.orange(f"  ✓ Image noted: {path} (configure /ai or /model to have it analyzed)."))
                return
            print()
            run_steps(["Sending image to AI for analysis..."], step_time=0.3)
            result = aicore.query_ai_with_image(
                "Describe this image in detail; transcribe any code, chemistry, or math it contains.",
                path)
            print(theme.panel([theme.text(l) for l in result.split("\n")], title="import: image",
                               color=theme.PURPLE, width=WIDTH))
        else:
            content, truncated = aicore.read_text_file_for_context(path)
            if content is None:
                print(theme.red(f"  ✗ Could not read '{path}' as text."))
                return
            preview = "\n".join(content.split("\n")[:15])
            note = " (showing first 15 lines; truncated)" if truncated else " (showing first 15 lines)"
            print()
            print(theme.panel(
                [theme.green(f"✓ Imported {path}{note}", bold=True), ""] +
                [theme.text(l) for l in preview.split("\n")],
                title="import: text", color=theme.CYAN, width=WIDTH))
            print(theme.faint("  Available to /ai and /agent now via the read_attachment tool."))
        print()

    def _cmd_import_zip(self, path):
        """Feature 6, continued: open a .zip like the OS file picker in
        the screenshot — list what's inside, extract it, and let the
        user pick one file from it to actually import (text or image),
        registering it as an attachment the AI/agent can read/see."""
        import zipfile
        try:
            with zipfile.ZipFile(path, "r") as zf:
                names = [n for n in zf.namelist() if not n.endswith("/")]
        except zipfile.BadZipFile:
            print(theme.red(f"  ✗ '{path}' is not a valid zip file."))
            return
        if not names:
            print(theme.orange("  Zip archive is empty."))
            return

        extract_dir = os.path.join(
            os.path.dirname(os.path.abspath(path)), ".cct_imports",
            os.path.splitext(os.path.basename(path))[0])
        os.makedirs(extract_dir, exist_ok=True)
        try:
            with zipfile.ZipFile(path, "r") as zf:
                zf.extractall(extract_dir)
        except Exception as e:
            print(theme.red(f"  ✗ Could not extract archive: {e}"))
            return

        agent.add_attachment(path)
        shown = names[:20]
        listing = [theme.green(f"✓ Opened {os.path.basename(path)} — {len(names)} file(s)", bold=True), ""]
        for i, n in enumerate(shown, 1):
            listing.append(theme.text(f"  {i:>2}. {n}"))
        if len(names) > len(shown):
            listing.append(theme.faint(f"  … {len(names) - len(shown)} more"))
        print()
        print(theme.panel(listing, title="import: zip", color=theme.CYAN, width=WIDTH))
        print(theme.faint("  Type a number to import that file too (text/image), or press Enter to skip."))
        choice = input(theme.dim("  ▸ ")).strip()
        if not choice:
            print(theme.faint("  Archive noted as an attachment; ask /agent or /ai about a file inside it by name."))
            print()
            return
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(shown):
                raise ValueError
            chosen_name = shown[idx]
        except ValueError:
            print(theme.red("  ✗ Not a valid selection."))
            return
        self.cmd_import(os.path.join(extract_dir, chosen_name))

    # ----------------------------------------------- CAT Vision — spec 40 --
    def cmd_vision(self, arg=""):
        """CAT Vision — screen sharing + annotation + visual debugging.

        /vision            open Vision dashboard
        /vision start      start capture (browser/PWA prompts for screen)
        /vision stop       stop sharing
        /vision pause      pause capture
        /vision analyze    analyze annotated region
        /vision clear      clear vision session data
        """
        sub = (arg or "").strip().lower()
        if not sub:
            print()
            print(theme.panel([
                theme.purple("CAT VISION", bold=True) + "  " + theme.dim("Share → Annotate → Chat → Analyze → Fix → Verify"),
                "",
                theme.text("Screen sharing + annotation + AI visual debugging.", bold=True),
                theme.dim("Open CAT Vision from the main menu (eye icon) or the PWA at http://localhost:8765"),
                theme.dim("for full getDisplayMedia capture, annotation layer, and chat."),
                "",
                theme.cyan("Commands", bold=True),
                theme.dim("  /vision start     Start capture (browser will prompt for screen/window/tab)"),
                theme.dim("  /vision stop      Stop sharing and clean up streams"),
                theme.dim("  /vision pause     Pause capture"),
                theme.dim("  /vision analyze   Analyze current annotated region"),
                theme.dim("  /vision clear     Clear vision session data"),
                "",
                theme.faint("Browser: getDisplayMedia() requires HTTPS/localhost + user permission."),
                theme.faint("PWA fallback: Upload Screenshot / Capture Image when screen capture unavailable."),
            ], title="vision", color=theme.CYAN, width=WIDTH))
            print()
            # also show live vision status if a session exists
            try:
                from calc_terminal.vision.session import VisionSessionManager
                mgr = VisionSessionManager()
                sessions = mgr.list_sessions()
                if sessions:
                    for s in sessions[-3:]:
                        print(theme.dim(f"  session {s['id'][:8]} · {s['state']} · {s['frame_count']} frames"))
            except Exception:
                pass
            self.print_home()
            return
        if sub in ("start", "stop", "pause", "resume", "analyze", "clear", "screenshot"):
            print()
            print(theme.panel([
                theme.text(f"Vision: {sub}", bold=True),
                theme.dim("This control is handled by the CAT Vision panel / PWA."),
                theme.dim("Open the eye icon in the main menu, or FATTY CAT PWA at http://localhost:8765"),
                theme.dim(f"and use the {sub} controls there (browser manages screen permission)."),
            ], title="vision", color=theme.CYAN, width=WIDTH))
            print()
            self.print_home()
            return
        print(theme.orange(f"\n  Unknown /vision subcommand '{sub}'. Try /vision\n"))
        self.print_home()

    # -------------------------------------------------------------- exit --
    def cmd_exit(self):
        # v0.7.9 unified shutdown: /exit, /quit, exit, quit AND Ctrl+Q
        # all funnel through the ONE idempotent goodbye handler — never
        # a second, hand-rolled farewell panel (that duplication was
        # the double-goodbye glitch).
        try:
            from . import goodbye
            reason = "task" if self.history else "exit"
            goodbye.shutdown_session(self, reason=reason)
        except Exception:
            print()
            print(theme.panel(
                [theme.text("Session saved.", bold=True),
                 theme.dim(f"{len(self.history)} notebook(s) solved this session."),
                 "",
                 theme.purple("Thanks for using CAT \u2014 see you next time.")],
                title="goodbye", color=theme.CYAN, width=WIDTH))
        self.running = False
