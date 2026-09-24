"""
CCT first-run initialization system.

Global-install lifecycle:

    cct
     -> main()                     (calc_terminal.cli)
     -> ensure_first_run()         (this module)
     -> initialize_first_run()     (the one-time setup; also exposed to
                                    the world as model.initialize_model()
                                    in the source tree's model.py)
     -> .initialized marker        (written ONLY after success)
     -> existing CCT startup       (calc_terminal.cli._launch)

Every later `cct` launch sees the marker and skips straight to launch.
A failed initialization writes NO marker, so the next launch retries —
never silently claiming success.

Nothing here runs during `pip install`: the package installs code and
resources only; initialization happens inside the application lifecycle,
the first time the user actually runs `cct`.

Storage: a platform-aware application-data directory (never the source
tree, never hard-coded Windows paths). Override for testing/power users
with the CCT_DATA_DIR environment variable:

    Windows   %LOCALAPPDATA%\\CCT
    Linux     $XDG_CONFIG_HOME/cct   (default ~/.config/cct)
    macOS     ~/Library/Application Support/CCT

    <data dir>/
    |-- config.json       seeded defaults (never clobbers user edits)
    |-- models.json       seed copy of the packaged model metadata
    |-- providers.json    seed copy of the packaged provider registry
    |-- cache/            model cache / runtime resources
    |-- logs/             startup + initialization logs
    `-- .initialized      marker; created only by a SUCCESSFUL init
"""

import json
import os
import sys
import time

_MARKER_NAME = ".initialized"
_MARKER_VERSION = 1


# ------------------------------------------------------------- paths ----

def data_dir():
    """The CCT application-data directory for this platform.

    CCT_DATA_DIR (if set) wins — that's how tests simulate a clean
    machine without touching the real profile. Otherwise the directory
    follows each OS's convention: %LOCALAPPDATA% on Windows,
    $XDG_CONFIG_HOME (or ~/.config) on Linux, ~/Library/Application
    Support on macOS. All three match the CCT application-data layout
    (config.json / models.json / providers.json / cache / logs /
    .initialized)."""
    override = os.environ.get("CCT_DATA_DIR", "").strip()
    if override:
        return os.path.abspath(override)
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.join(
            os.path.expanduser("~"), "AppData", "Local")
        return os.path.join(base, "CCT")
    if sys.platform == "darwin":
        return os.path.join(
            os.path.expanduser("~"), "Library", "Application Support", "CCT")
    # Linux / BSD / other Unix
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    base = xdg or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "cct")


def initialized_path():
    return os.path.join(data_dir(), _MARKER_NAME)


def cache_dir():
    return os.path.join(data_dir(), "cache")


def logs_dir():
    return os.path.join(data_dir(), "logs")


def is_initialized():
    """True when a successful first-run initialization has completed."""
    return os.path.isfile(initialized_path())


def mark_initialized():
    """Write the marker. Called ONLY after initialization succeeded."""
    path = initialized_path()
    payload = {
        "version": _MARKER_VERSION,
        "cct_version": _cct_version(),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    os.replace(tmp, path)


def _cct_version():
    try:
        from .app import VERSION
        return VERSION
    except Exception:
        return "0.0.0"


# ------------------------------------------------------------ seeding ----

def _package_resource(relpath):
    """Resolve a packaged resource file to an absolute path. The
    resources live inside the calc_terminal package itself, so this
    works identically from a source checkout and from site-packages."""
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relpath)


def _write_json_if_missing(path, data):
    if os.path.exists(path):
        return False
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return True


def _copy_resource_if_missing(dst, src):
    if os.path.exists(dst) or not os.path.exists(src):
        return
    with open(src, "r", encoding="utf-8") as r, \
         open(dst, "w", encoding="utf-8") as w:
        w.write(r.read())


def seed_defaults():
    """Create the application-data structure and seed the reference
    files. Existing files are never overwritten — the seeds are
    factory defaults, user edits win."""
    root = data_dir()
    os.makedirs(cache_dir(), exist_ok=True)
    os.makedirs(logs_dir(), exist_ok=True)
    try:
        from .config import load_config
        _write_json_if_missing(
            os.path.join(root, "config.json"), load_config().to_dict())
    except Exception:
        # config seeding is best-effort; a broken one must not fail the
        # whole first run
        pass
    _copy_resource_if_missing(
        os.path.join(root, "models.json"),
        _package_resource(os.path.join("models", "model_metadata.json")))
    _copy_resource_if_missing(
        os.path.join(root, "providers.json"),
        _package_resource(os.path.join("providers", "providers.json")))


# ------------------------------------------------------ initialization --

def initialize_first_run():
    """The one-time initialization (exposed from model.py as
    initialize_model()). Returns (ok, message).

    Creates the application-data tree, seeds config/models/providers
    reference files, and — only if every step succeeded — writes the
    .initialized marker. Any failure returns (False, reason) with NO
    marker, so the next `cct` launch retries."""
    try:
        seed_defaults()
        mark_initialized()
        return True, "initialization complete"
    except OSError as e:
        return False, f"cannot prepare application data: {e}"
    except Exception as e:
        return False, f"unexpected error: {type(e).__name__}: {e}"


def print_environment_card():
    """Print the Intelligent First-Run Diagnostic & Environment Card."""
    import shutil
    import platform
    print("=" * 72)
    print("                CAT INTELLIGENT ENVIRONMENT DETECTION")
    print("=" * 72)

    py_ver = platform.python_version()
    os_desc = f"{platform.system()} {platform.release()} ({platform.machine()})"
    git_installed = bool(shutil.which("git"))
    print(f"  Operating System   : {os_desc}")
    print(f"  Python Runtime     : {py_ver}")
    print(f"  Git Version Control: {'Installed (Available)' if git_installed else 'Missing (Optional)'}")

    prof = None
    try:
        from .hardware_analyzer import HardwareAnalyzer
        prof = HardwareAnalyzer.analyze()
        print(f"  CPU Compute        : {prof.cpu_model} ({prof.cpu_threads} logical threads)")
        print(f"  System RAM         : {prof.ram_total_gb:.1f} GB ({prof.ram_available_gb:.1f} GB available)")
        if prof.has_gpu:
            print(f"  GPU Compute        : {prof.gpu_name} ({prof.vram_gb:.1f} GB VRAM via {prof.gpu_backend})")
        else:
            print("  GPU Compute        : CPU / Integrated Memory")
        print(f"  Local AI Tier      : {prof.local_ai_tier.value}")
    except Exception as e:
        print(f"  Hardware Detection : Basic ({e})")

    try:
        from .ollama_download import is_ollama_running, is_ollama_installed
        if is_ollama_running():
            ollama_st = "Running (Active on port 11434)"
        elif is_ollama_installed():
            ollama_st = "Installed (Offline — will auto-launch when needed)"
        else:
            ollama_st = "Not Detected (Optional: install from https://ollama.com)"
        print(f"  Local Ollama Engine: {ollama_st}")
    except Exception:
        pass

    try:
        from .compatibility_engine import ModelCompatibilityEngine
        from .ollama_catalog import all_models
        engine = ModelCompatibilityEngine()
        recs = engine.recommend_models(all_models(include_dynamic=True))
        best_code = recs.get("best_coding", [{}])[0].get("model", {}).get("name", "qwen2.5-coder:3b")
        best_fast = recs.get("best_fast", [{}])[0].get("model", {}).get("name", "smollm2:1.7b")
        ram_tag = f"{prof.ram_total_gb:.0f}GB RAM" if prof else "your device"
        print("-" * 72)
        print("  RECOMMENDED STARTER SETUP FOR YOUR HARDWARE:")
        print(f"    * Primary Coding Model : {best_code} (Optimized for {ram_tag})")
        print(f"    * Fast Edge Autocomplete: {best_fast}")
        print(f"    * Quick Download Command : cat models install {best_code}")
    except Exception:
        pass
    print("=" * 72)


def ensure_first_run():
    """CLI-level first-run orchestrator. Prints the startup banner and
    runs the one-time initialization when needed. Returns an exit code
    (0 = continue to launch, non-zero = stop with an error)."""
    if is_initialized():
        return 0
    print("CAT — Coding Agent Terminal")
    print("Creator: Kazi Zillani")
    print("\nInitializing CAT...")
    print_environment_card()
    print("Preparing required resources...")
    ok, msg = initialize_first_run()
    if not ok:
        print(f"ERROR: first-run initialization failed ({msg}).")
        print("Nothing was marked as initialized — the next launch will retry.")
        print(f"Application data directory: {data_dir()}")
        return 1
    print("✓ CAT core initialized\n")
    return 0