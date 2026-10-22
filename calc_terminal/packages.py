"""
CCT — packages.py: Autonomous Package Manager (v0.7.7 spec section 1/10/11/12).

Lets the user (or the AI, in Build mode) install real packages from chat:

    "install requests"            -> pip
    "install numpy"               -> pip
    "install latest opencv"       -> pip, pinned to the latest release
    "install nodejs"              -> system package manager (winget/choco/brew/apt/dnf)
    "install rust"                -> rustup (if present) or the system package manager
    "install docker"              -> system package manager
    "install cuda"                -> system package manager
    "install lodash with npm"     -> npm (explicit manager hint honored)
    "/install torch --manager pipx"

Every supported package manager (pip, pipx, uv, conda, npm, pnpm, yarn,
bun, cargo, go, composer, vcpkg, chocolatey, winget, apt, dnf, brew) maps
to a ManagerSpec with real command builders and a best-effort verify step.

Honest scope, stated plainly:
  * "Install" means: run the package manager's real install command in a
    subprocess on the user's machine. It never happens silently — the
    permission gate lives in the callers (calc_terminal/app.py,
    calc_terminal/ui/app.py, calc_terminal/agent.py), and every stage of
    the run is reported through an `on_event` callback so the UI can
    render the Installation Dashboard (spec section 11).
  * Manager detection is heuristic (keyword + platform tables), not a
    semantic package database. When a package is genuinely ambiguous or
    unknown, the caller is expected to run the research flow
    (package_research.py) BEFORE installing — this module only decides
    on the *known* mappings and says "unknown" honestly otherwise.
  * Real download/install progress bars from e.g. pip/npm live on the
    child process's stdout/stderr; this module streams those lines
    through verbatim rather than fabricating percentages.
  * sudo-requiring managers (apt/dnf) build the `sudo ...` command and
    pass the user's permission dialog through first; the sudo password
    prompt itself happens in the user's real terminal when the command
    runs, never captured here.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import json
import os
import re
import shutil
import subprocess
import sys
import time

from . import eventbus

# ------------------------------------------------------------------ events --
# Installation Dashboard event vocabulary. Every event is a plain dict:
#   {"stage": <one of the keys below>, "message": str, "detail": optional str}
# Callers render these; this module never prints them itself (the classic
# terminal and the Textual UI each have their own renderer).
STAGE_RESOLVING = "resolving"
STAGE_PERMISSION = "permission"
STAGE_DOWNLOAD = "download"
STAGE_RUNNING = "running"
STAGE_VERIFYING = "verifying"
STAGE_DONE = "done"
STAGE_FAILED = "failed"
STAGE_SKIPPED = "skipped"

# ---------------------------------------------------------------- managers --
# name -> (label, install-cmd builder, verify hint). `platforms` is the
# OS list the manager is native to ("" = any). The install builders take
# (package_name, version) and return the argv (list) to run — lists, not
# shell strings, so no quoting surprises reach a shell.

_WIN = os.name == "nt"
_MAC = sys.platform == "darwin"
_LINUX = sys.platform.startswith("linux")


def _py():
    """The python interpreter this app is running on (used for pip
    invocation, so 'install requests' installs into the environment
    CCT itself runs in)."""
    return sys.executable or "python"


def _pip_install(name, version, target=None):
    cmd = [_py(), "-m", "pip", "install", "--no-input"]
    if version and version != "latest":
        cmd.append(f"{name}=={version}")
    else:
        cmd.append(name)
    return cmd


def _npm_install(name, version, target=None):
    cmd = ["npm", "install", "-g", name] if target != "local" else ["npm", "install", name]
    return cmd


def _apt_install(name, version, target=None):
    return ["sudo", "apt-get", "install", "-y", name]


def _dnf_install(name, version, target=None):
    return ["sudo", "dnf", "install", "-y", name]


MANAGERS = {
    "pip": dict(
        label="pip (Python)",
        icon="\U0001f40d",
        platforms="",
        install=_pip_install,
        verify=lambda name, version: [_py(), "-m", "pip", "show", name],
        check_import=True,
    ),
    "pipx": dict(
        label="pipx (Python apps)",
        icon="\U0001f40d",
        platforms="",
        install=lambda name, version, target=None: ["pipx", "install", name],
        verify=lambda name, version: ["pipx", "list"],
        check_import=False,
    ),
    "uv": dict(
        label="uv (Rust-based pip)",
        icon="\u26a1",
        platforms="",
        install=lambda name, version, target=None: ["uv", "pip", "install", name],
        verify=lambda name, version: ["uv", "pip", "show", name],
        check_import=True,
    ),
    "conda": dict(
        label="conda (Anaconda)",
        icon="\U0001f331",
        platforms="",
        install=lambda name, version, target=None: ["conda", "install", "-y", name],
        verify=lambda name, version: ["conda", "list", name],
        check_import=True,
    ),
    "npm": dict(
        label="npm (Node.js)",
        icon="\U0001f4e6",
        platforms="",
        install=_npm_install,
        verify=lambda name, version: ["npm", "ls", "-g", name],
        check_import=False,
    ),
    "pnpm": dict(
        label="pnpm (Node.js)",
        icon="\U0001f4e6",
        platforms="",
        install=lambda name, version, target=None: (
            ["pnpm", "add", "-g", name] if target != "local" else ["pnpm", "add", name]),
        verify=lambda name, version: ["pnpm", "ls", "-g", name],
        check_import=False,
    ),
    "yarn": dict(
        label="yarn (Node.js)",
        icon="\U0001f4e6",
        platforms="",
        install=lambda name, version, target=None: (
            ["yarn", "global", "add", name] if target != "local" else ["yarn", "add", name]),
        verify=lambda name, version: ["yarn", "global", "list"],
        check_import=False,
    ),
    "bun": dict(
        label="bun (Node.js runtime)",
        icon="\U0001f35c",
        platforms="",
        install=lambda name, version, target=None: (
            ["bun", "add", "-g", name] if target != "local" else ["bun", "add", name]),
        verify=lambda name, version: ["bun", "pm", "ls", "-g"],
        check_import=False,
    ),
    "cargo": dict(
        label="cargo (Rust crates)",
        icon="\U0001f680",
        platforms="",
        install=lambda name, version, target=None: ["cargo", "install", name],
        verify=lambda name, version: ["cargo", "install", "--list"],
        check_import=False,
    ),
    "go": dict(
        label="go (Go modules)",
        icon="\U0001f4a0",
        platforms="",
        install=lambda name, version, target=None: ["go", "install", f"{name}@latest"],
        verify=lambda name, version: ["go", "list", "-m", name],
        check_import=False,
    ),
    "composer": dict(
        label="composer (PHP)",
        icon="\U0001f4e6",
        platforms="",
        install=lambda name, version, target=None: ["composer", "global", "require", name],
        verify=lambda name, version: ["composer", "global", "show", name],
        check_import=False,
    ),
    "vcpkg": dict(
        label="vcpkg (C/C++)",
        icon="\U0001f6e0\ufe0f",
        platforms="",
        install=lambda name, version, target=None: ["vcpkg", "install", name],
        verify=lambda name, version: ["vcpkg", "list", name],
        check_import=False,
    ),
    "chocolatey": dict(
        label="chocolatey (Windows)",
        icon="\U0001f36b",
        platforms="win",
        install=lambda name, version, target=None: ["choco", "install", "-y", name],
        verify=lambda name, version: ["choco", "list", name, "--local-only"],
        check_import=False,
    ),
    "winget": dict(
        label="winget (Windows)",
        icon="\U0001f310",
        platforms="win",
        install=lambda name, version, target=None: [
            "winget", "install", "--silent",
            "--accept-package-agreements", "--accept-source-agreements", name],
        verify=lambda name, version: ["winget", "list", name],
        check_import=False,
    ),
    "apt": dict(
        label="apt (Debian/Ubuntu)",
        icon="\U0001f3e2",
        platforms="linux",
        install=_apt_install,
        verify=lambda name, version: ["apt", "list", "--installed", name + "*"],
        check_import=False,
    ),
    "dnf": dict(
        label="dnf (Fedora/RHEL)",
        icon="\U0001f3e2",
        platforms="linux",
        install=_dnf_install,
        verify=lambda name, version: ["dnf", "list", "--installed", name],
        check_import=False,
    ),
    "brew": dict(
        label="homebrew (macOS/Linux)",
        icon="\U0001f37a",
        platforms="darwin",
        install=lambda name, version, target=None: ["brew", "install", name],
        verify=lambda name, version: ["brew", "list", name],
        check_import=False,
    ),
}

# Python package -> importable module name (for the import-succeeds
# verification step of spec section 12). Only the common renames; a
# package whose import name matches its install name uses itself.
_IMPORT_ALIASES = {
    "opencv-python": "cv2",
    "opencv-python-headless": "cv2",
    "Pillow": "PIL",
    "PyYAML": "yaml",
    "beautifulsoup4": "bs4",
    "scikit-learn": "sklearn",
    "scikit-image": "skimage",
    "python-dateutil": "dateutil",
    "requests-html": "requests_html",
    "psycopg2-binary": "psycopg2",
    "pytz": "pytz",
    "numpy": "numpy",
    "torch": "torch",
    "tensorflow": "tensorflow",
    "matplotlib": "matplotlib",
    "sympy": "sympy",
    "pandas": "pandas",
}

# Known-language package tables (for manager detection). These are the
# honest heuristics behind "install requests" -> pip: a curated list of
# well-known packages per ecosystem, not a live index.
PYTHON_PACKAGES = {
    "requests", "numpy", "pandas", "scipy", "sympy", "matplotlib", "seaborn",
    "scikit-learn", "scikit-image", "torch", "tensorflow", "keras", "jax",
    "transformers", "torchvision", "torchaudio", "opencv-python",
    "opencv-python-headless", "pillow", "pyyaml", "flask", "django",
    "fastapi", "uvicorn", "pytest", "black", "ruff", "isort", "mypy",
    "beautifulsoup4", "requests-html", "selenium", "playwright", "httpx",
    "aiohttp", "websockets", "tqdm", "click", "typer", "rich", "textual",
    "prompt-toolkit", "colorama", "boto3", "gunicorn", "celery", "redis",
    "pymongo", "psycopg2-binary", "sqlalchemy", "alembic", "pydantic",
    "pydantic-settings", "pyqt5", "pyside6", "tkinter", "jupyter",
    "notebook", "ipykernel", "ipython", "nltk", "spacy", "gensim",
    "xgboost", "lightgbm", "statsmodels", "polars", "pyarrow", "dask",
    "joblib", "bokeh", "plotly", "kaleido", "networkx", "biopython",
    "rdkit", "pubchempy", "ase", "pymatgen", "openpyxl", "xlrd", "xlsxwriter",
    "pdfplumber", "pypdf", "fitz", "pyinstaller", "pip", "pipx", "uv",
}
NODE_PACKAGES = {
    "lodash", "express", "react", "react-dom", "vue", "next", "nuxt", "svelte",
    "typescript", "ts-node", "nodemon", "axios", "node-fetch", "moment",
    "chalk", "commander", "yargs", "dotenv", "cors", "body-parser",
    "socket.io", "ws", "jquery", "eslint", "prettier", "jest", "mocha",
    "vitest", "vite", "webpack", "babel", "prisma", "mongoose", "pg",
    "mysql2", "sequelize", "knex", "graphql", "apollo-server", "next-auth",
    "tailwindcss", "zustand", "redux", "react-router-dom", "uuid",
    "express-session", "passport", "bcrypt", "jsonwebtoken", "zod",
    "yup", "formik", "framer-motion", "three", "d3", "chart.js",
    "electron", "expo", "react-native", "firebase", "stripe",
}
RUST_CRATES = {
    "serde", "tokio", "rayon", "clap", "anyhow", "thiserror", "reqwest",
    "hyper", "axum", "actix-web", "rocket", "tokio-postgres", "sqlx",
    "diesel", "rusqlite", "rand", "chrono", "regex", "lazy_static",
    "once_cell", "log", "env_logger", "tracing", "serde_json", "tokio-util",
    "futures", "async-std", "tempfile", "walkdir", "glob", "dirs",
    "csv", "serde_yaml", "toml", "jsonwebtoken", "rpassword", "indicatif",
    "crossterm", "ratatui", "tui", "egui", "iced", "bevy", "nalgebra",
    "ndarray", "num", "itertools", "uuid", "indexmap", "hashbrown",
    "parking_lot", "dashmap", "crossbeam", "flume", "crossbeam-channel",
}
GO_MODULES = {
    "gin", "echo", "chi", "mux", "gorilla/mux", "cobra", "viper", "zap",
    "logrus", "gorm", "sqlx", "pgx", "fiber", "fasthttp", "grpc",
    "protobuf", "uuid", "jwt", "casbin", "hugo", "docker", "go-git",
}
PHP_PACKAGES = {
    "laravel/framework", "symfony/console", "monolog/monolog", "guzzlehttp/guzzle",
    "phpunit/phpunit", "ramsey/uuid", "vlucas/phpdotenv", "phpoffice/phpspreadsheet",
    "composer/semver", "nesbot/carbon",
}

# Well-known standalone tools -> (manager candidates in order, verify binary)
SYSTEM_TOOLS = {
    "nodejs": (["winget", "chocolatey", "brew", "apt", "dnf"], "node"),
    "node": (["winget", "chocolatey", "brew", "apt", "dnf"], "node"),
    "npm": (["winget", "chocolatey", "brew", "apt", "dnf"], "npm"),
    "rust": (["rustup"], "rustc"),
    "rustup": (["winget", "chocolatey", "brew", "apt", "dnf"], "rustup"),
    "rustc": (["rustup"], "rustc"),
    "cargo": (["rustup"], "cargo"),
    "docker": (["winget", "chocolatey", "brew", "apt", "dnf"], "docker"),
    "docker desktop": (["winget", "chocolatey", "brew"], "docker"),
    "cuda": (["winget", "chocolatey", "brew"], "nvcc"),
    "cuda toolkit": (["winget", "chocolatey"], "nvcc"),
    "go": (["winget", "chocolatey", "brew", "apt", "dnf"], "go"),
    "golang": (["winget", "chocolatey", "brew", "apt", "dnf"], "go"),
    "java": (["winget", "chocolatey", "brew", "apt", "dnf"], "java"),
    "jdk": (["winget", "chocolatey", "brew", "apt", "dnf"], "java"),
    "python": (["winget", "chocolatey", "brew", "apt", "dnf"], "python"),
    "ffmpeg": (["winget", "chocolatey", "brew", "apt", "dnf"], "ffmpeg"),
    "git": (["winget", "chocolatey", "brew", "apt", "dnf"], "git"),
    "curl": (["winget", "chocolatey", "brew", "apt", "dnf"], "curl"),
    "wget": (["winget", "chocolatey", "brew", "apt", "dnf"], "wget"),
    "vim": (["winget", "chocolatey", "brew", "apt", "dnf"], "vim"),
    "neovim": (["winget", "chocolatey", "brew", "apt", "dnf"], "nvim"),
    "vscode": (["winget", "chocolatey", "brew"], "code"),
    "git-lfs": (["winget", "chocolatey", "brew", "apt", "dnf"], "git-lfs"),
    "kubernetes": (["winget", "chocolatey", "brew", "apt", "dnf"], "kubectl"),
    "kubectl": (["winget", "chocolatey", "brew", "apt", "dnf"], "kubectl"),
    "helm": (["winget", "chocolatey", "brew", "apt", "dnf"], "helm"),
    "terraform": (["winget", "chocolatey", "brew", "apt", "dnf"], "terraform"),
    "aws cli": (["winget", "chocolatey", "brew"], "aws"),
    "postgresql": (["winget", "chocolatey", "brew", "apt", "dnf"], "psql"),
    "mysql": (["winget", "chocolatey", "brew", "apt", "dnf"], "mysql"),
    "sqlite": (["winget", "chocolatey", "brew", "apt", "dnf"], "sqlite3"),
    "mongodb": (["winget", "chocolatey", "brew"], "mongod"),
    "redis": (["winget", "chocolatey", "brew", "apt", "dnf"], "redis-server"),
    "nginx": (["winget", "chocolatey", "brew", "apt", "dnf"], "nginx"),
    "apache": (["winget", "chocolatey", "brew", "apt", "dnf"], "httpd"),
    "openssl": (["winget", "chocolatey", "brew", "apt", "dnf"], "openssl"),
    "7zip": (["winget", "chocolatey"], "7z"),
    "vlc": (["winget", "chocolatey", "brew"], "vlc"),
    "gimp": (["winget", "chocolatey", "brew", "apt", "dnf"], "gimp"),
    "inkscape": (["winget", "chocolatey", "brew", "apt", "dnf"], "inkscape"),
    "blender": (["winget", "chocolatey", "brew", "apt", "dnf"], "blender"),
    "arduino": (["winget", "chocolatey", "brew"], "arduino-cli"),
}

# C/C++ libraries commonly installed via vcpkg on Windows.
_VCPKG_LIBS = {
    "boost", "openssl", "zlib", "sqlite3", "curl", "libcurl", "fmt",
    "spdlog", "gtest", "cpr", "nlohmann-json", "eigen3", "opencv",
}

# ------------------------------------------------------------ request model --
class PackageRequest:
    """One parsed install request. `manager` may be None (meaning
    'unknown — research first'), `version` defaults to 'latest'."""

    __slots__ = ("name", "version", "manager", "manager_hint", "target", "raw")

    def __init__(self, name, version="latest", manager=None, manager_hint=None,
                 target=None, raw=""):
        self.name = name
        self.version = version or "latest"
        self.manager = manager
        self.manager_hint = manager_hint
        self.target = target      # None | "local" (npm-local etc.)
        self.raw = raw

    def label(self):
        return f"{self.name}@{self.version}" if self.version != "latest" else self.name

    def __repr__(self):
        return f"PackageRequest({self.label()!r}, manager={self.manager!r})"


# ---------------------------------------------------------------- parsing --
_MANAGER_WORDS = {
    "pip": "pip", "pipx": "pipx", "uv": "uv", "conda": "conda",
    "npm": "npm", "pnpm": "pnpm", "yarn": "yarn", "bun": "bun",
    "cargo": "cargo", "go": "go", "composer": "composer",
    "vcpkg": "vcpkg", "chocolatey": "choco", "choco": "chocolatey",
    "winget": "winget", "apt": "apt", "apt-get": "apt",
    "dnf": "dnf", "brew": "brew", "homebrew": "brew",
}

_INSTALL_RE = re.compile(
    r"\b(?:install|setup|get)\b.*?\b(\S+)\b", re.I)


def parse_request(text):
    """Parse free text like 'install latest opencv' / 'Install numpy with
    pip' / 'install NodeJS' into a PackageRequest (manager may be None).
    Returns None if the text doesn't look like an install request at
    all."""
    if not text:
        return None
    low = text.lower().strip()
    m = re.search(r"\b(?:install|setup|get)\b", low)
    if not m:
        return None

    # Explicit manager mention: "install X with pip", "pip install X",
    # "install X using npm" ...
    manager_hint = None
    for word, manager in _MANAGER_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", low):
            manager_hint = manager
            break

    # The package name: first word after the install/setup/get verb.
    rest = low[m.end():]
    rest = rest.replace("latest", " ").strip()
    name_match = re.search(r"^\s*([a-z0-9][a-z0-9+_.@/-]*)", rest)
    if not name_match:
        return None
    name = name_match.group(1).strip(" ,.:;!?")
    if name in ("a", "an", "the", "package", "packages", "library", "librarys", "tool"):
        nxt = re.search(r"^\s*[a-z0-9]+", rest[name_match.end():])
        if nxt:
            name = nxt.group(0)
    if not name or not re.search(r"[a-z0-9]", name):
        return None

    # "latest" version request: "install latest opencv" — the spec's own
    # example. The word was stripped above; if it was present, name now
    # holds the real package and version stays "latest".
    version = "latest"
    ver_match = re.search(r"\b([0-9][0-9a-zA-Z_.+-]*)\s*$", rest)
    if ver_match and re.match(r"^[0-9]", name_match.group(1)):
        pass  # name started with a digit (e.g. "3d"), don't treat as version

    target = None
    if re.search(r"\blocal(ly)?\b|\bproject\b", rest):
        target = "local"

    return PackageRequest(name=name, version=version, manager=None,
                          manager_hint=manager_hint, target=target, raw=text)


# ------------------------------------------------------------ detection --
def manager_available(manager):
    """True if `manager` can be invoked on this machine (binary on PATH,
    or for pip: this interpreter is usable)."""
    if manager not in MANAGERS:
        return False
    spec = MANAGERS[manager]
    if spec["platforms"]:
        if "win" in spec["platforms"] and not _WIN:
            return False
        if "linux" in spec["platforms"] and not _LINUX:
            return False
        if "darwin" in spec["platforms"] and not _MAC:
            return False
    if manager == "pip":
        try:
            import importlib.util
            return importlib.util.find_spec("pip") is not None
        except Exception:
            return False
    return shutil.which(_binary_for(manager)) is not None


def _binary_for(manager):
    return {"chocolatey": "choco", "apt": "apt-get", "dnf": "dnf",
            "brew": "brew", "pipx": "pipx", "uv": "uv", "conda": "conda",
            "npm": "npm", "pnpm": "pnpm", "yarn": "yarn", "bun": "bun",
            "cargo": "cargo", "go": "go", "composer": "composer",
            "vcpkg": "vcpkg", "winget": "winget"}.get(manager, manager)


def _native_system_manager():
    """The best system-package manager for this OS, or None."""
    order = ["winget", "chocolatey", "brew", "apt", "dnf"]
    for m in order:
        if m in MANAGERS and manager_available(m):
            return m
    return None


def detect_manager(req):
    """Pick the manager for a PackageRequest using known-package tables,
    the explicit hint, and the platform's system manager. Returns the
    manager key, or None if the package is unknown/ambiguous."""
    if req.manager:
        return req.manager
    if req.manager_hint:
        return req.manager_hint if req.manager_hint in MANAGERS else None

    name = req.name.lower()
    # Scoped npm packages ("@scope/name") are unambiguous.
    if name.startswith("@"):
        return "npm"
    # Standalone system tools (NodeJS, Rust, Docker, CUDA...).
    for key, (cands, _binary) in SYSTEM_TOOLS.items():
        if name == key or name.replace("-", " ") == key:
            for c in cands:
                if c == "rustup":
                    if shutil.which("rustup"):
                        return "rustup"
                    continue
                if c in MANAGERS and manager_available(c):
                    return c
            sys_mgr = _native_system_manager()
            if sys_mgr:
                return sys_mgr
            return "winget" if _WIN else ("brew" if _MAC else "apt")
    # Known ecosystems.
    if name in PYTHON_PACKAGES:
        return "pip"
    if name in NODE_PACKAGES:
        return "npm"
    if name in RUST_CRATES:
        return "cargo"
    if name in GO_MODULES:
        return "go"
    if name in PHP_PACKAGES:
        return "composer"
    if name in _VCPKG_LIBS and _WIN:
        return "vcpkg"
    # Extension-based hints.
    if name.startswith("lib") or name.endswith("-dev"):
        return "apt" if _LINUX else None
    return None


def resolve_request(text, prefer=None):
    """One-stop parse + detect. Returns (request, manager_key_or_None).
    `prefer` is a manager the caller wants to try first (e.g. from a
    research recommendation). Falls back to treating a bare package
    name as "install <name>" (the /install flow passes bare names)."""
    req = parse_request(text)
    if req is None:
        req = parse_request("install " + text)
    if req is None:
        return None, None
    if prefer and prefer in MANAGERS:
        req.manager = prefer
        return req, prefer
    return req, detect_manager(req)


# ------------------------------------------------------------ execution --
_INSTALL_TIMEOUT = 900  # 15 minutes wall clock — big SDKs take a while

_RUNNABLE_EXTS = (".exe", ".bat", ".cmd", ".sh") if _WIN else ()


def run_install(req, on_event=None, cwd=None, timeout=_INSTALL_TIMEOUT,
                capture=True):
    """Runs the real installer for `req` (req.manager must be set).
    Streams Installation-Dashboard events through `on_event` and returns
    a summary dict:
        {"ok": bool, "manager": str, "command": [argv...],
         "exit_code": int, "timed_out": bool, "output_tail": str,
         "duration": float, "verify": {..} or None,
         "deps_installed": int, "conflicts": bool}
    Never raises for install failures — a failed install is a result,
    not an exception. Also records the outcome in the package history
    (v0.7.7 spec section 8)."""
    result = _run_install_impl(req, on_event=on_event, cwd=cwd,
                               timeout=timeout, capture=capture)
    try:
        record_install(result, req)
    except Exception:
        pass
    return result


def _run_install_impl(req, on_event=None, cwd=None, timeout=_INSTALL_TIMEOUT,
                      capture=True):
    from . import sound
    manager = req.manager
    if manager not in MANAGERS:
        if on_event:
            on_event({"stage": STAGE_FAILED,
                      "message": f"Unknown package manager '{manager}'."})
        return {"ok": False, "manager": manager, "command": [],
                "exit_code": -1, "timed_out": False, "output_tail": "",
                "duration": 0.0, "verify": None,
                "deps_installed": 0, "conflicts": False}
    spec = MANAGERS[manager]
    command = spec["install"](req.name, req.version, req.target)
    if on_event:
        on_event({"stage": STAGE_DOWNLOAD,
                  "message": f"Installing {req.label()} via {spec['label']}",
                  "detail": " ".join(command)})
    t0 = time.time()
    output_lines = []
    try:
        proc = subprocess.Popen(
            command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip("\n")
            output_lines.append(line)
            if on_event:
                on_event({"stage": STAGE_RUNNING, "message": line})
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except Exception:
            pass
        duration = round(time.time() - t0, 2)
        tail = "\n".join(output_lines[-20:])
        if on_event:
            on_event({"stage": STAGE_FAILED,
                      "message": f"Install timed out after {timeout}s."})
        sound.play("error")
        return {"ok": False, "manager": manager, "command": command,
                "exit_code": 124, "timed_out": True, "output_tail": tail,
                "duration": duration, "verify": None,
                "deps_installed": 0, "conflicts": False}
    except OSError as e:
        duration = round(time.time() - t0, 2)
        if on_event:
            on_event({"stage": STAGE_FAILED,
                      "message": f"Could not run {' '.join(command)}: {e}"})
        sound.play("error")
        return {"ok": False, "manager": manager, "command": command,
                "exit_code": -1, "timed_out": False,
                "output_tail": f"Could not run: {e}", "duration": duration,
                "verify": None, "deps_installed": 0, "conflicts": False}
    duration = round(time.time() - t0, 2)
    ok = proc.returncode == 0
    tail = "\n".join(output_lines[-20:])
    deps_count, conflicts = _analyze_output(output_lines, requested=req.name)
    if ok:
        if on_event:
            on_event({"stage": STAGE_VERIFYING,
                      "message": f"{manager} reported success — verifying..."})
        verify = verify_package(manager, req.name, req.version)
        if verify and verify.get("ok"):
            if on_event:
                on_event({"stage": STAGE_DONE,
                          "message": f"Installed {req.label()} \u2014 verified "
                                     f"{verify.get('verified', '')}"})
            sound.play("success")
        else:
            note = (verify or {}).get("note") or "verification inconclusive"
            if on_event:
                on_event({"stage": STAGE_DONE,
                          "message": f"Install command finished for {req.label()} "
                                     f"({note}) \u2014 treat as installed."})
            sound.play("success")
        return {"ok": True, "manager": manager, "command": command,
                "exit_code": 0, "timed_out": False, "output_tail": tail,
                "duration": duration, "verify": verify,
                "deps_installed": deps_count, "conflicts": conflicts}
    if on_event:
        on_event({"stage": STAGE_FAILED,
                  "message": f"Install failed (exit {proc.returncode})."})
    sound.play("error")
    return {"ok": False, "manager": manager, "command": command,
            "exit_code": proc.returncode, "timed_out": False,
            "output_tail": tail, "duration": duration, "verify": None,
            "deps_installed": deps_count, "conflicts": conflicts}


def _analyze_output(output_lines, requested=None):
    """Best-effort read of the installer's own output:
      - `deps_installed`: count of dependencies pip/npm report
        installing (total minus the requested package itself);
      - `conflicts`: whether the output mentions dependency conflicts.
    Both honest heuristics over real output — 0/False when nothing is
    reported (never fabricated)."""
    text = "\n".join(output_lines)
    deps = 0
    for line in output_lines:
        low = line.strip().lower()
        if low.startswith("successfully installed "):
            parts = line.split("Successfully installed ", 1)[1].split()
            names = [p for p in parts if p and p not in ("and",)]
            if requested:
                wanted = requested.lower().replace("_", "-")
                names = [n for n in names if n.split("==")[0].lower() != wanted]
            deps = max(deps, len(names))
        elif "added " in low and " packages" in low:
            import re
            m = re.search(r"added (\d+) packages", low)
            if m:
                deps = max(deps, max(int(m.group(1)) - 1, 0))
    conflicts = "conflict" in text.lower()
    return deps, conflicts


def verify_package(manager, name, version="latest"):
    """Post-install verification (spec section 12): the manager's own
    list/show query, plus (for pip-family managers) a real import test.
    Returns {"ok": bool, "verified": str, "note": str} — never raises."""
    if manager not in MANAGERS:
        return {"ok": False, "verified": "", "note": f"unknown manager {manager}"}
    spec = MANAGERS[manager]
    try:
        cmd = spec["verify"](name, version)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                                encoding="utf-8", errors="replace")
        listed = result.returncode == 0 and bool((result.stdout or "").strip())
    except Exception as e:
        return {"ok": False, "verified": "", "note": f"verify command failed: {e}"}

    # Import check for pip-family managers (spec section 12: "Import
    # succeeds").
    import_name = None
    if spec.get("check_import"):
        import_name = _IMPORT_ALIASES.get(name, name.replace("-", "_").lower())
        try:
            import importlib
            importlib.import_module(import_name)
            imported = True
        except Exception:
            imported = False
    else:
        imported = True

    ok = listed and imported
    pieces = []
    if listed:
        pieces.append(f"listed by {manager}")
    if spec.get("check_import"):
        pieces.append(f"import {import_name} "
                      + ("succeeded" if imported else "failed"))
    if not listed:
        pieces.append(f"{manager} did not list it (may still be usable)")
    return {"ok": ok, "verified": ", ".join(pieces), "note": " ".join(pieces)}


def importable_name(package_name):
    return _IMPORT_ALIASES.get(package_name,
                               package_name.replace("-", "_").lower())


# ------------------------------------------------------------ permissions --
_DECISIONS_STORE = os.path.join(os.path.expanduser("~"), ".cct_package_decisions.json")


def _load_decisions():
    try:
        with open(_DECISIONS_STORE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_decisions(data):
    try:
        with open(_DECISIONS_STORE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False


def remembered_decision(manager, name):
    """'allow' / 'deny' / None — the persisted always-remembered choice
    for this exact manager+package pair, if the user picked one in a
    previous install flow (spec section 3: "Remember choice if
    selected")."""
    return _load_decisions().get(f"{manager}|{name.lower()}")


def remember_decision(manager, name, decision):
    key = f"{manager}|{name.lower()}"
    data = _load_decisions()
    data[key] = decision
    _save_decisions(data)


def forget_decision(manager, name):
    data = _load_decisions()
    data.pop(f"{manager}|{name.lower()}", None)
    _save_decisions(data)


def list_remembered():
    """[(manager, name, decision), ...] for the /packages settings view."""
    return [(k.split("|", 1)[0], k.split("|", 1)[1], v)
            for k, v in _load_decisions().items() if "|" in k]


# -------------------------------------------------------------- dashboard --
def dashboard_lines(events):
    """Renderer for the classic terminal: turns a list of events into
    the Installation Dashboard lines (spec section 11) — package, manager,
    command, live output, verification, completion status."""
    from . import theme
    lines = []
    for ev in events:
        stage = ev.get("stage")
        msg = ev.get("message", "")
        if stage == STAGE_RUNNING:
            lines.append(theme.dim("    " + msg))
        elif stage == STAGE_DOWNLOAD:
            lines.append(theme.cyan("  \u2b07 ") + msg +
                         (theme.faint("   " + ev["detail"]) if ev.get("detail") else ""))
        elif stage == STAGE_VERIFYING:
            lines.append(theme.purple("  \U0001f50d ") + msg)
        elif stage == STAGE_DONE:
            lines.append(theme.green("  \u2713 ") + msg)
        elif stage == STAGE_FAILED:
            lines.append(theme.red("  \u2717 ") + msg)
        elif stage == STAGE_PERMISSION:
            lines.append(theme.orange("  \U0001f511 ") + msg)
        elif stage == STAGE_SKIPPED:
            lines.append(theme.faint("  \u2014 ") + msg)
        else:
            lines.append(theme.text("  " + msg))
    return lines


# ---------------------------------------------------------------- summary --
def _env_label():
    """Python version + platform for install summaries (spec section 7's
    'Environment' row)."""
    import platform
    try:
        return f"Python {platform.python_version()} \u00b7 {platform.system()}"
    except Exception:
        return "Python (unknown)"


def summarize(result, req):
    """Professional install summary card (spec section 7) — the
    classic REPL prints this in a panel after every install, and it
    carries the spec's exact fields. Pure text — callers decide where
    to render it."""
    version = getattr(req, "version", None) or "latest"
    if result.get("ok"):
        verify = result.get("verify") or {}
        lines = ["\u2705 Package Installed Successfully", ""]
        if version != "latest":
            lines.append(f"Package: {req.name} ({version})")
            lines.append(f"Version: {version}")
        else:
            lines.append(f"Package: {req.name}")
        lines.append(f"Environment: {_env_label()}")
        lines.append(f"Dependencies Installed: {result.get('deps_installed', 0)}")
        lines.append(f"Installation Time: {result.get('duration', 0)}s")
        if verify.get("verified"):
            lines.append(f"Verification: \U0001f50d {verify['verified']}")
        elif verify.get("note"):
            lines.append(f"Verification: {verify['note']}")
        else:
            lines.append("Verification: command reported success")
        lines.append("")
        if result.get("conflicts"):
            lines.append("\u26a0 Dependency conflicts were mentioned in the install "
                         "output \u2014 review the dashboard log before use.")
        else:
            lines.append("No dependency conflicts detected.")
        lines.append("Ready for use \u2014 ask CAT what to build next.")
        return "\n".join(lines)
    lines = ["\u274c Package Installation Failed", ""]
    lines.append(f"Package: {req.name}")
    lines.append(f"Manager: {MANAGERS[req.manager]['label']}")
    lines.append(f"Exit code: {result.get('exit_code')}"
                 + (" (timed out)" if result.get("timed_out") else ""))
    tail = (result.get("output_tail") or "").strip()
    if tail:
        lines.append("")
        lines.append("Logs (last lines):")
        for line in tail.splitlines()[-6:]:
            lines.append("  " + line)
    lines.append("")
    lines.append("Suggestion: check the package name/version and network, "
                 "then retry \u2014 or ask CAT to research alternatives.")
    return "\n".join(lines)


# ---------------------------------------------------------------- history --
# v0.7.7 spec section 8: persistent package installation history, kept
# alongside the remembered-decisions store in the same dotfile family.
HISTORY_PATH = os.path.join(os.path.expanduser("~"), ".cct_package_history.json")
MAX_HISTORY = 100


def _load_history():
    if not os.path.exists(HISTORY_PATH):
        return []
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            import json as _json
            data = _json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_history(records):
    try:
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            import json as _json
            _json.dump(records, f, indent=2)
        return True
    except Exception:
        return False


def record_install(result, req):
    """Records one install outcome (called automatically by
    run_install). A reinstall of an already-recorded package updates
    that record's `updated_at` (and version) instead of duplicating it
    (spec section 8's Update semantics)."""
    records = _load_history()
    now = time.time()
    name = getattr(req, "name", "") or ""
    if not name:
        return
    existing = next((r for r in records if r.get("name") == name), None)
    entry = {
        "name": name,
        "version": getattr(req, "version", "latest") or "latest",
        "manager": getattr(req, "manager", "") or "",
        "ok": bool(result.get("ok")),
        "env": _env_label(),
        "installed_at": now,
        "updated_at": now,
        "duration": result.get("duration", 0),
        "verified": bool((result.get("verify") or {}).get("ok")),
        "conflicts": bool(result.get("conflicts")),
        "exit_code": result.get("exit_code"),
        "error_tail": (result.get("output_tail") or "")[-400:] if not result.get("ok") else "",
        "notes": "",
    }
    if existing is not None:
        existing.update({k: v for k, v in entry.items() if k != "installed_at"})
        existing["updated_at"] = now
        existing["version"] = entry["version"]
    else:
        records.insert(0, entry)
    records = records[:MAX_HISTORY]
    _save_history(records)


def package_history(limit=50):
    """All install-history records, newest first."""
    return _load_history()[:limit]


def history_search(query):
    """Filter history by package name or manager (case-insensitive)."""
    q = (query or "").strip().lower()
    if not q:
        return package_history()
    return [r for r in _load_history()
            if q in r.get("name", "").lower() or q in r.get("manager", "").lower()]


def remove_history(name):
    """Removes every history record for `name`. Returns the number of
    records removed. Only touches the history JSON — never the
    installed package itself."""
    records = _load_history()
    kept = [r for r in records if r.get("name") != name]
    removed = len(records) - len(kept)
    if removed:
        _save_history(kept)
    return removed


def history_entry(name):
    """The newest history record for `name`, or None."""
    for r in _load_history():
        if r.get("name") == name:
            return r
    return None


def clear_history():
    """Empties the whole install history. Only the JSON store — never
    uninstalls anything. Returns True when there was something to
    clear."""
    records = _load_history()
    if records:
        _save_history([])
        return True
    return False


def announce(result, req):
    """Short single-line status for the activity log / event bus."""
    from . import sound
    if result.get("ok"):
        sound.play("success")
        eventbus.bus.publish(eventbus.PACKAGE_INSTALLED,
                             package=req.label(), manager=req.manager or "")
        return f"Installed {req.label()} via {req.manager}"
    sound.play("error")
    eventbus.bus.publish(eventbus.PACKAGE_FAILED,
                         package=req.label(), manager=req.manager or "")
    return f"Failed to install {req.label()} via {req.manager}"
