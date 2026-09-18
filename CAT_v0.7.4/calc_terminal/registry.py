"""
CCT centralized command registry (spec section 14).

Before this module, commands existed as: an entry in
commands_data.py's COMMANDS list (name + one-line description only),
a separate elif branch in app.py's dispatch chain, a separate entry
in fallback_cli.py, and sometimes a separate tool entry in agent.py's
TOOLS dict for AI-mode invocation — four places to touch per command,
with no shared notion of category, aliases, icon, shortcut, required
permissions, which AI modes can invoke it, or example usage. That's
the exact "hardcoded across multiple files" problem section 14 names.

This module gives every command ONE CommandSpec with all of those
fields, and ONE registry to look them up by name, alias, category, or
free-text search (for autocomplete). It does not yet replace app.py's
dispatch chain (that's real surgery — see CHANGELOG_v0.6.3) but it IS
the real source of truth for the palette/help text: `bootstrap()`
below builds full CommandSpec entries for every command in
commands_data.COMMANDS right now (migrating the existing data, not
duplicating it) and layers on rich metadata for the commands that
already have it elsewhere in the codebase (permissions.py's keys,
agent.py's TOOLS, the SHORT_ALIASES map in app.py) so those fields are
real, not guessed.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class CommandSpec:
    name: str                                  # canonical, e.g. "/atomsim"
    description: str = ""
    category: str = "general"
    aliases: list = field(default_factory=list)
    icon: str = "\u2022"                        # bullet by default
    shortcut: Optional[str] = None              # e.g. "Ctrl+Shift+N"
    permissions: list = field(default_factory=list)   # keys from permissions.PERMISSION_DEFS
    ai_modes: list = field(default_factory=lambda: ["notebook"])  # which AI modes may invoke it
    examples: list = field(default_factory=list)
    autocomplete_keywords: list = field(default_factory=list)
    handler: Optional[Callable] = None          # bound at registration time by app.py, if any
    arg_style: Optional[str] = None             # None | "split_optional" — see ARG_STYLE_MAP below


# name -> category, used to bootstrap from the existing flat COMMANDS list
CATEGORY_MAP = {
    "/help": "general", "/about": "general", "/shortcuts": "general", "/settings": "general",
    "/history": "general", "/memory": "general", "/upload": "general", "/voice": "general",
    "/permissions": "general", "/browser": "general", "/browse": "general", "/cat": "general",
    "/calculator": "calculation", "/solve": "calculation", "/formulas": "calculation",
    "/kinetics": "calculation", "/electrochemistry": "calculation", "/random": "calculation",
    "/derive": "calculation",
    "/atomsim": "simulation", "/orbitals": "simulation", "/orbitalgrid": "simulation",
    "/bonding": "simulation", "/bloch": "simulation", "/sim3d": "simulation", "/gpu3d": "simulation", "/graph": "simulation",
    "/ai": "ai", "/agent": "ai", "/ai-verify": "ai",
    "/mode": "ai", "/notebook": "ai", "/build": "ai", "/plan": "ai",
    "/game": "misc",
}

# hand-authored rich metadata for the commands that most need it right
# now (the ones this session touched, plus the highest-traffic core
# ones) — everything else in commands_data.COMMANDS still gets a real
# CommandSpec via bootstrap(), just without hand-tuned icon/shortcut/
# examples yet. That gap is intentional and tracked, not hidden.
RICH_METADATA = {
    "/atomsim": dict(
        icon="\u269b", aliases=["/at"], permissions=["execute_python"],
        ai_modes=["notebook", "agent", "build"],
        examples=["/atomsim Fe", "/atomsim 26"],
        autocomplete_keywords=["atom", "nucleus", "proton", "neutron", "bohr", "element"],
    ),
    "/orbitals": dict(
        icon="\u2601", aliases=["/o"], permissions=["execute_python"],
        ai_modes=["notebook", "agent", "build"],
        examples=["/orbitals 2p", "/orbitals 3d"],
        autocomplete_keywords=["orbital", "electron cloud", "probability density", "psi"],
    ),
    "/orbitalgrid": dict(
        icon="\U0001f4ca", permissions=["execute_python"],
        ai_modes=["notebook", "agent", "build"],
        examples=["/orbitalgrid"],
        autocomplete_keywords=["orbital grid", "hydrogen wave function", "reference chart"],
    ),
    "/bonding": dict(
        icon="\U0001f9ea", permissions=["execute_python"],
        ai_modes=["notebook", "agent", "build"],
        examples=["/bonding furan", "/bonding water"],
        autocomplete_keywords=["elf", "electron localization", "bonding", "molecule density"],
    ),
    "/bloch": dict(
        icon="\u269b", permissions=["execute_python"],
        ai_modes=["notebook", "agent", "build"],
        examples=["/bloch", "/bloch 90 0", "/bloch 90 90"],
        autocomplete_keywords=["bloch sphere", "qubit", "quantum state", "superposition"],
    ),
    "/solve": dict(
        icon="\U0001f9ee", aliases=["/s"], permissions=["calculator"],
        ai_modes=["notebook", "agent", "build", "plan"],
        examples=["/solve"],
        autocomplete_keywords=["solve", "formula", "algebra"],
    ),
    "/settings": dict(
        icon="\u2699", permissions=[],
        ai_modes=["notebook", "agent", "build", "plan"],
        examples=["/settings"],
        autocomplete_keywords=["settings", "config", "preferences"],
    ),
    "/mode": dict(
        icon="\U0001f501", permissions=[],
        ai_modes=["notebook", "agent", "build", "plan"],
        examples=["/mode", "/mode build"],
        autocomplete_keywords=["mode", "ai mode", "persona", "notebook", "agent", "build", "plan"],
    ),
    "/notebook": dict(
        icon="\U0001f4d8", permissions=[],
        ai_modes=["notebook", "agent", "build", "plan"],
        examples=["/notebook"],
        autocomplete_keywords=["notebook mode", "chemistry", "physics", "math", "daily ai"],
    ),
    "/agent": dict(
        icon="\u2699", permissions=["execute_python"],
        ai_modes=["notebook", "agent", "build", "plan"],
        examples=["/agent"],
        autocomplete_keywords=["agent mode", "autonomous", "tool use", "simulate", "solve"],
    ),
    "/build": dict(
        icon="\U0001f528", permissions=[],
        ai_modes=["notebook", "agent", "build", "plan"],
        examples=["/build"],
        autocomplete_keywords=["build mode", "code", "software", "debug", "architecture", "api"],
    ),
    "/plan": dict(
        icon="\U0001f9ed", permissions=[],
        ai_modes=["notebook", "agent", "build", "plan"],
        examples=["/plan"],
        autocomplete_keywords=["plan mode", "roadmap", "brainstorm", "prototype", "study plan"],
    ),
    "/research": dict(
        icon="\U0001f50d", permissions=[],
        ai_modes=["notebook", "research", "agent", "build", "plan"],
        examples=["/research"],
        autocomplete_keywords=["research mode", "deep research", "web search", "literature"],
    ),
    "/debug": dict(
        icon="\U0001f41b", permissions=[],
        ai_modes=["notebook", "debugger", "agent", "build", "plan"],
        examples=["/debug"],
        autocomplete_keywords=["debugger mode", "debug", "fix", "error", "traceback"],
    ),
    "/install": dict(
        icon="\U0001f4e6", permissions=["install_packages"],
        ai_modes=["build"],
        examples=["/install requests", "/install numpy", "/install torch"],
        autocomplete_keywords=["install", "package", "pip", "npm", "dependency", "library"],
    ),
    "/packages": dict(
        icon="\U0001f4e6", permissions=["install_packages"],
        ai_modes=["build"],
        examples=["/packages", "/packages forget numpy"],
        autocomplete_keywords=["package manager", "dashboard", "remembered decisions", "forget"],
    ),
    "/pipeline": dict(
        icon="\U0001f5fa", permissions=[],
        ai_modes=["notebook", "agent", "build", "plan"],
        examples=["/pipeline build me a molecule viewer script"],
        autocomplete_keywords=["pipeline", "planner", "research", "build", "verify", "stages"],
    ),
    "/orchestrate": dict(
        icon="\U0001f465", permissions=[],
        ai_modes=["notebook", "agent", "build", "plan"],
        examples=["/orchestrate build a chemistry dashboard"],
        autocomplete_keywords=["orchestrator", "coordinator", "specialists", "team", "agents"],
    ),
    "/devices": dict(
        icon="\U0001f4f1", permissions=["device_control"],
        ai_modes=["notebook", "agent", "build", "plan"],
        examples=["/devices", "/devices terminal run 'git status'"],
        autocomplete_keywords=["devices", "device control", "terminal", "android", "desktop"],
    ),
    "/workspace": dict(
        icon="\U0001f5c2", permissions=[],
        ai_modes=["notebook", "agent", "build", "plan"],
        examples=["/workspace", "/workspace open C:\\projects\\app",
                  "/workspace list", "/workspace detect"],
        autocomplete_keywords=["workspace", "detect", "open folder", "recent",
                               "pinned", "favorite", "rename", "search"],
    ),
    "/browser": dict(
        icon="\U0001f30d", aliases=["/browse", "/cat"], permissions=[],
        ai_modes=["notebook", "agent", "build", "plan"],
        examples=["/browser", "/cat", "/cat https://example.com", "/cat search cats on mars"],
        autocomplete_keywords=["browser", "browse", "cat", "web", "surf", "terminal browser", "duckduckgo", "fomoji browser"],
    ),
    "/browse": dict(
        icon="\U0001f30d", aliases=[], permissions=[],
        ai_modes=["notebook", "agent", "build", "plan"],
        examples=["/browse https://example.com", "/browse search cats"],
        autocomplete_keywords=["browse", "browser", "surf", "open url", "search"],
    ),
    "/cat": dict(
        icon="\U0001f30d", aliases=[], permissions=[],
        ai_modes=["notebook", "agent", "build", "plan"],
        examples=["/cat", "/cat https://example.com", "/cat search cats on mars"],
        autocomplete_keywords=["cat", "browser", "browse", "web", "chromium", "qt webengine"],
    ),
}


# Canonical alias -> full-command table (spec section 14: one place,
# not duplicated). This WAS a hardcoded dict living only in app.py's
# App.SHORT_ALIASES class attribute; app.py now derives that attribute
# from short_alias_map() below instead of declaring its own copy — the
# mapping itself hasn't changed, only where it's defined.
ALIAS_TABLE = {
    "/h": "/help", "/c": "/calculator", "/s": "/solve", "/f": "/formulas",
    "/k": "/kinetics", "/d": "/derive", "/g": "/graph", "/a": "/about",
    "/gm": "/game", "/pg": "/game",
    "/e": "/electrochemistry", "/r": "/random", "/x": "/exit",
    "/o": "/orbitals", "/u": "/upload", "/v": "/voice", "/3": "/sim3d",
    "/ag": "/agent", "/y": "/history", "/st": "/settings", "/sh": "/shortcuts",
    "/at": "/atomsim", "/vf": "/verify", "/?": "/help", "/m": "/memory",
    "/cp": "/codepad", "/tk": "/tokens", "/th": "/theme", "/ws": "/websearch",
    "/rs": "/research", "/im": "/import", "/pt": "/pet", "/cc": "/copycode",
    "/rx": "/react", "/ex": "/export", "/tu": "/tui", "/co": "/composer",
    "/br": "/browser", "/bw": "/browse", "/cat": "/browser",
}


def short_alias_map():
    """Return the alias -> canonical-command dict, exactly the shape
    app.py's SHORT_ALIASES used to hardcode."""
    return dict(ALIAS_TABLE)


class CommandRegistry:
    def __init__(self):
        self._by_name = {}
        self._by_alias = {}

    def register(self, spec: CommandSpec):
        self._by_name[spec.name] = spec
        for alias in spec.aliases:
            self._by_alias[alias] = spec.name

    def get(self, name_or_alias):
        if name_or_alias in self._by_name:
            return self._by_name[name_or_alias]
        canonical = self._by_alias.get(name_or_alias)
        return self._by_name.get(canonical) if canonical else None

    def all(self):
        return list(self._by_name.values())

    def by_category(self, category):
        return [s for s in self._by_name.values() if s.category == category]

    def categories(self):
        seen = []
        for s in self._by_name.values():
            if s.category not in seen:
                seen.append(s.category)
        return seen

    def usable_in_mode(self, ai_mode):
        return [s for s in self._by_name.values() if ai_mode in s.ai_modes]

    def search(self, query):
        """Free-text match against name, description, and autocomplete
        keywords — what a command-palette type-ahead would call."""
        q = query.strip().lower()
        if not q:
            return self.all()
        out = []
        for s in self._by_name.values():
            hay = " ".join([s.name, s.description] + s.autocomplete_keywords).lower()
            if q in hay:
                out.append(s)
        return out


# Commands matching this exact pattern in app.py's old elif chain:
#   if low == "/X": self.cmd_X(); return
#   if low.startswith("/X "): self.cmd_X(raw.split(" ", 1)[1].strip()); return
# i.e. zero args or one stripped trailing-text arg, same method either
# way. Verified against app.py line-by-line before being added here —
# see CHANGELOG_v0.6.3_architecture.md.
ARG_STYLE_MAP = {
    "/memory": "split_optional",
    "/model": "split_optional",
    "/theme": "split_optional",
    "/websearch": "split_optional",
    "/research": "split_optional",
    "/import": "split_optional",
    "/react": "split_optional",
    "/export": "split_optional",
    "/workspace": "split_optional",
    "/permissions": "split_optional",
    "/browser": "split_optional",
    "/browse": "split_optional",
    "/cat": "split_optional",
    "/vision": "split_optional",
    "/vscode": "split_optional",
}


def bootstrap():
    """Build a full CommandRegistry from commands_data.COMMANDS (the
    existing real command list), layering in RICH_METADATA where it
    exists. Real migration of real data, not a mock catalog."""
    from . import commands_data
    reverse_alias = {}
    for alias, full in ALIAS_TABLE.items():
        reverse_alias.setdefault(full, []).append(alias)

    reg = CommandRegistry()
    for name, desc in commands_data.COMMANDS:
        extra = dict(RICH_METADATA.get(name, {}))
        category = CATEGORY_MAP.get(name, "general")
        canonical_aliases = reverse_alias.get(name, [])
        hand_aliases = extra.pop("aliases", [])
        merged_aliases = list(dict.fromkeys(canonical_aliases + hand_aliases))  # dedup, preserve order
        arg_style = ARG_STYLE_MAP.get(name)
        spec = CommandSpec(name=name, description=desc, category=category,
                            aliases=merged_aliases, arg_style=arg_style, **extra)
        reg.register(spec)
    return reg


_registry = None


def get_registry():
    global _registry
    if _registry is None:
        _registry = bootstrap()
    return _registry
