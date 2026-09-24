"""
CAT — global command-line entry point (`cat`).

This module is what the installed console script calls:

    cat = calc_terminal.cli:main

It makes CAT launchable from any working directory (no `python main.py`,
no need to be inside the source repository), supports normal CLI
behavior (`--help`, `--version`, an optional project/workspace path),
and then hands off to the exact same launch flow the classic
`python main.py` used: fallback REPL when Textual/attached-terminal
aren't available, primary chat UI otherwise.
"""

import argparse
import os
import sys

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stdin, "reconfigure"):
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# -----------------------------------------------------------------------------
# Command-safety contract constants
# -----------------------------------------------------------------------------
SAFETY_READ_ONLY = "read-only"
SAFETY_STATE_CHANGING = "state-changing"
SAFETY_INTERACTIVE = "interactive"

CAT_GITHUB_REPO = "kazizillani-oss/CAT_v0.7.9"
CAT_RELEASES_API_URL = f"https://api.github.com/repos/{CAT_GITHUB_REPO}/releases/latest"


def get_command_safety(argv=None) -> dict:
    """Classifies CLI arguments under the centralized command-safety contract.

    Returns a dict with:
      classification: "read-only" | "state-changing" | "interactive"
      safe_to_automate: bool
      changes_state: bool | None
      reason: str
    """
    args = list(sys.argv[1:] if argv is None else argv)

    # 1. READ-ONLY / SAFE TO AUTOMATE
    if args in (["--version"], ["-v"], ["version"]):
        return {
            "classification": SAFETY_READ_ONLY,
            "safe_to_automate": True,
            "changes_state": False,
            "reason": "Prints CAT version information and exits without modifying state.",
        }

    if args in (["--debug"], ["debug"]):
        return {
            "classification": SAFETY_READ_ONLY,
            "safe_to_automate": True,
            "changes_state": False,
            "reason": "Prints read-only runtime diagnostics and exits without modifying state.",
        }

    if len(args) >= 2 and args[0] in ("update", "--update") and args[1] in ("--check", "check"):
        return {
            "classification": SAFETY_READ_ONLY,
            "safe_to_automate": True,
            "changes_state": False,
            "reason": "Queries remote release metadata to check for updates without installing or modifying files.",
        }

    if args in (["--help"], ["-h"], ["help"]):
        return {
            "classification": SAFETY_READ_ONLY,
            "safe_to_automate": True,
            "changes_state": False,
            "reason": "Displays command-line help documentation and exits without modifying state.",
        }

    # 2. STATE-CHANGING / NOT SAFE FOR UNATTENDED AUTOMATION
    if args and args[0] in ("update", "--update"):
        return {
            "classification": SAFETY_STATE_CHANGING,
            "safe_to_automate": False,
            "changes_state": True,
            "reason": "Update operation modifies installation files, binary executables, or configurations.",
        }

    if args and args[0] in ("rollback", "--rollback"):
        return {
            "classification": SAFETY_STATE_CHANGING,
            "safe_to_automate": False,
            "changes_state": True,
            "reason": "Rollback operation reverts installation or workspace state to a prior snapshot.",
        }

    if args and args[0] in ("repair", "--repair"):
        return {
            "classification": SAFETY_STATE_CHANGING,
            "safe_to_automate": False,
            "changes_state": True,
            "reason": "Repair operation repairs or modifies filesystem permissions, directory structures, or configurations.",
        }

    # 3. INTERACTIVE / WORKSPACE / COMPLEX COMMANDS
    return {
        "classification": SAFETY_INTERACTIVE,
        "safe_to_automate": False,
        "changes_state": None,
        "reason": "Interactive TUI session, workspace launcher, or interactive subsystem requiring user control.",
    }


def _usage(prog: str = None) -> str:
    if not prog:
        raw_prog = os.path.basename(sys.argv[0] if sys.argv else "cat").lower()
        prog = "cct" if "cct" in raw_prog else "cat"
    alt_prog = "cat" if prog == "cct" else "cct"

    return (
        f"usage: {prog} [path] [options]\n"
        "\n"
        "CAT CLI v0.8.b [beta] \u2014 Coding Agent Terminal / terminal AI coding agent.\n"
        "Protected by Fomoji authentication — no valid Fomoji identity = no access.\n"
        "\n"
        "positional arguments:\n"
        "  path            project/workspace directory to open (defaults to\n"
        "                  the current working directory)\n"
        "\n"
        "options:\n"
        "  -h, --help      show this help message and exit\n"
        "  -v, --version   print the CAT version and exit\n"
        "  --debug         display read-only runtime diagnostics and environment info\n"
        "  --doctor        diagnose the CLI install (PATH, launcher,\n"
        "  push [msg]      stage intended files, create verified commit and push to GitHub\n"
        "  publish [msg]   same as push — synchronized GitHub update workflow\n"
        "  update --check  check for newer releases from official GitHub repository\n"
        "  --auth <cmd>    Fomoji auth: status | login | logout | whoami\n"
        "  browse [url]    open CAT Browser (real HTML/CSS/JS via QWebEngineView)\n"
        "  --browser [url] same as `browse`\n"
        "  fatty, web      launch Fatty CAT in CAT Browser (starts server on :8765)\n"
        "  server          start Fatty CAT server in foreground (:8765)\n"
        "  vision          CAT Vision commands: start | stop | pause | analyze | screenshot | clear\n"
        "  models          dynamic AI models: [--provider <id>] [--new] [--updated] [--deprecated] [refresh]\n"
        "  providers       manage AI providers: list | audit | refresh | status | test | backup\n"
        "  offline         activate Emergency Local Mode (zero cloud, Ollama local only)\n"
        "\n"
        "Automation safety:\n"
        "  Read-only (safe to automate):\n"
        f"    {prog} --version\n"
        f"    {prog} --debug\n"
        f"    {prog} update --check\n"
        "\n"
        "  State-changing (not safe for unattended automation):\n"
        f"    {prog} update\n"
        f"    {prog} rollback\n"
        f"    {prog} repair\n"
        "\n"
        "  State-changing commands should not be run unattended unless the caller\n"
        "  explicitly provides its own approval/control mechanism.\n"
        f"  (The exact same safety contract applies to '{alt_prog}'.)\n"
        "\n"
        "examples:\n"
        f"  {prog}                 open CAT in the current directory\n"
        f"  {prog} .               same as above\n"
        f"  {prog} my-project      open CAT with my-project as the workspace\n"
        f"  {prog} /path/to/proj   open CAT with an absolute workspace path\n"
        f"  {prog} --debug         view read-only system and runtime diagnostics\n"
        f"  {prog} update --check  check for available releases\n"
        f"  {prog} --auth login    pair this device with your Fomoji identity\n"
        f"  {prog} --auth status   check Fomoji session\n"
        f"  {prog} models          list dynamically registered AI models\n"
        f"  {prog} providers status check real-time provider health\n"
        f"  {prog} offline         switch to local-only emergency fallback mode\n"
        f"  {prog} fatty           launch Fatty CAT (opens browser + starts server)\n"
        f"  {prog} browse https://example.com   open CAT Browser at a URL\n"
    )


def _version():
    """Best-effort version: source-tree constant first (reflects active code
    and beta releases), then installed-distribution metadata, then static fallback."""
    try:
        from .identity import APP_VERSION
        if APP_VERSION:
            return APP_VERSION
    except Exception:
        pass
    for dist in ("cct-cli", "cat-cli", "cct-ai-ide", "cct"):
        try:
            from importlib.metadata import version as _dist_version
            return _dist_version(dist)
        except Exception:
            continue
    try:
        from .app import VERSION
        return VERSION
    except Exception:
        return "0.8.b"


def _format_context(ctx: int) -> str:
    if not ctx or ctx <= 0:
        return "-"
    if ctx >= 1_000_000:
        val = f"{ctx / 1_000_000:.2f}".rstrip("0").rstrip(".")
        return f"{val}M"
    if ctx >= 1000:
        return f"{ctx // 1000}K"
    return str(ctx)


def _models_cli(argv: list[str]) -> int:
    """Full-featured CAT Model Center CLI: list, search, info, install, remove, benchmark, recommend."""
    args = argv[1:]
    sub = args[0].lower() if args else "list"

    if sub in ("--help", "-h", "help"):
        print("Usage: cat models [command] [options]")
        print("\nCommands:")
        print("  list (default)      List available models with device compatibility")
        print("  search <query>      Search models by name, family, capability, or category")
        print("  info <name>         Detailed model specs, hardware analysis & benchmarks")
        print("  install <name>      Download / pull model into local Ollama engine")
        print("  remove <name>       Delete local model from Ollama engine")
        print("  benchmark [name]    Run benchmark suite on model, or view leaderboard")
        print("  recommend           Device-specific model recommendations based on hardware")
        print("  refresh             Discover live models from active cloud/local providers")
        print("\nOptions:")
        print("  --category <cat>    Filter by category (coding, reasoning, vision, small, large)")
        print("  --provider <id>     Filter models by provider (ollama, openai, anthropic, etc.)")
        print("  --new, -n           Show newly discovered models")
        return 0

    from .hardware_analyzer import HardwareAnalyzer
    from .compatibility_engine import ModelCompatibilityEngine
    from .benchmark_system import CATBenchmarkSystem
    import calc_terminal.ollama_catalog as catalog
    import calc_terminal.ollama_download as ollama

    # Dynamic sync with local Ollama if running
    installed_local = []
    if ollama.is_ollama_running():
        installed_local = ollama.installed_models()
        catalog.register_installed_models(installed_local)

    # 1. RECOMMEND COMMAND
    if sub in ("recommend", "rec", "hardware"):
        print("=" * 72)
        print("          CAT HARDWARE ANALYZER & MODEL RECOMMENDATION ENGINE")
        print("=" * 72)
        engine = ModelCompatibilityEngine()
        recs = engine.recommend_models(catalog.all_models(include_dynamic=True))
        prof = engine.profile

        print(f"  System CPU  : {prof.cpu_model} ({prof.cpu_threads} threads)")
        print(f"  System RAM  : {prof.ram_total_gb:.1f} GB ({prof.ram_available_gb:.1f} GB available)")
        if prof.has_gpu:
            print(f"  GPU Compute : {prof.gpu_name} ({prof.vram_gb:.1f} GB VRAM via {prof.gpu_backend})")
        else:
            print("  GPU Compute : None detected (CPU / System RAM execution)")
        print(f"  AI Capability: {prof.local_ai_tier.value}")
        print("-" * 72)

        for cat_name, title in [
            ("best_coding", "Recommended for Coding & Software Engineering:"),
            ("best_reasoning", "Recommended for Complex Reasoning & Math:"),
            ("best_fast", "Recommended for Fast On-Device Chat & Autocomplete:"),
        ]:
            print(f"\n  {title}")
            m_list = recs.get(cat_name, [])
            if not m_list:
                print("    (No specific model found in catalog)")
            for item in m_list[:3]:
                m = item["model"]
                c = item["compat"]
                inst = " [INSTALLED]" if m["name"] in installed_local else ""
                print(f"    * {m['name']:<24} {c.tier_label_ascii:<16} | {m['desc']}{inst}")

        print("\n" + "=" * 72)
        return 0

    # 2. SEARCH COMMAND
    if sub in ("search", "find"):
        query = args[1] if len(args) > 1 else ""
        if not query:
            print("Usage: cat models search <query>")
            return 1
        matches = catalog.search_models(query=query)
        print(f"\nCAT Model Search for '{query}' ({len(matches)} results):\n")
        engine = ModelCompatibilityEngine()
        header = f"{'Model Name':<28} | {'Params':<8} | {'Size':<8} | {'Compatibility':<16} | {'Installed'}"
        print(header)
        print("-" * len(header))
        for m in matches[:25]:
            compat = engine.evaluate(m)
            inst = "YES" if m["name"] in installed_local else "-"
            print(f"{m['name']:<28} | {m.get('params','?'):<8} | {m.get('size_gb',0):.1f} GB  | {compat.tier_label_ascii:<16} | {inst}")
        return 0

    # 3. INFO COMMAND
    if sub in ("info", "inspect", "show"):
        name = args[1] if len(args) > 1 else ""
        if not name:
            print("Usage: cat models info <model_name>")
            return 1
        m = catalog.get_model(name)
        if not m:
            # Fallback to local inspect
            m = {"name": name, "params": "Unknown", "size_gb": 4.0, "family": "unknown", "desc": "Custom model", "context": 8192, "caps": ["chat"]}

        engine = ModelCompatibilityEngine()
        compat = engine.evaluate(m)
        bench = CATBenchmarkSystem()
        bench_score = bench.get_score_for_model(name)

        print("=" * 72)
        print(f"                      MODEL INFO: {m['name']}")
        print("=" * 72)
        print(f"  Family          : {m.get('family', 'Unknown')}")
        print(f"  Parameters      : {m.get('params', 'Unknown')}")
        print(f"  Disk Size       : {m.get('size_gb', 0):.1f} GB")
        print(f"  Context Window  : {m.get('context', 8192)} tokens")
        print(f"  Capabilities    : {', '.join(m.get('caps', []))}")
        print(f"  Description     : {m.get('desc', '')}")
        print("-" * 72)
        print("  DEVICE COMPATIBILITY ANALYSIS:")
        print(f"    Rating        : {compat.tier_label_ascii}")
        print(f"    Total Memory  : {compat.total_memory_gb:.1f} GB (Weights: {compat.weights_gb:.1f} GB, KV Cache: {compat.kv_cache_gb:.1f} GB)")
        print(f"    VRAM Usage    : {compat.vram_used_gb:.1f} GB")
        print(f"    RAM Offload   : {compat.ram_offload_gb:.1f} GB")
        print(f"    Est. Speed    : {compat.estimated_tps:.1f} tokens/sec")
        print(f"    Summary       : {compat.summary}")
        if compat.details:
            for d in compat.details:
                print(f"    * {d}")
        print("-" * 72)
        print("  BENCHMARK SCORES & METRICS:")
        if bench_score:
            src = bench_score.source.value if hasattr(bench_score.source, "value") else str(bench_score.source)
            print(f"    Source Attribution : [{src}]")
            print(f"    Overall Score      : {bench_score.overall:5.1f} / 100")
            print(f"    Coding Capability  : {bench_score.coding:5.1f} / 100")
            print(f"    Reasoning & Math   : {bench_score.reasoning:5.1f} / 100")
            print(f"    Tool Use Execution : {bench_score.tool_use:5.1f} / 100")
            print(f"    Agentic Tasks      : {bench_score.agent_tasks:5.1f} / 100")
            print(f"    Inference Speed    : {bench_score.speed:5.1f} / 100")
            print(f"    Stability & Context: {bench_score.stability:5.1f} / 100")
        else:
            print("    No CAT benchmarks recorded for this model yet.")
            print(f"    Run `cat models benchmark {m['name']}` to benchmark on this machine.")
        print("=" * 72)
        return 0

    # 4. INSTALL / PULL COMMAND
    if sub in ("install", "pull", "get", "download"):
        name = args[1] if len(args) > 1 else ""
        if not name:
            print("Usage: cat models install <model_name>")
            return 1
        if not ollama.is_ollama_running():
            print("Error: Local Ollama service is not running. Please start Ollama first.", file=sys.stderr)
            return 1
        print(f"Pulling model '{name}' from Ollama library...")
        ok, msg = ollama.pull_model(name)
        if ok:
            print(f"Successfully installed '{name}'.")
            return 0
        else:
            print(f"Failed to install '{name}': {msg}", file=sys.stderr)
            return 1

    # 5. REMOVE / DELETE COMMAND
    if sub in ("remove", "delete", "rm"):
        name = args[1] if len(args) > 1 else ""
        if not name:
            print("Usage: cat models remove <model_name>")
            return 1
        if not ollama.is_ollama_running():
            print("Error: Local Ollama service is not running.", file=sys.stderr)
            return 1
        print(f"Removing model '{name}' from local Ollama...")
        ok, msg = ollama.delete_model(name)
        if ok:
            print(f"Successfully removed '{name}'.")
            return 0
        else:
            print(f"Failed to remove '{name}': {msg}", file=sys.stderr)
            return 1

    # 6. BENCHMARK COMMAND
    if sub in ("benchmark", "bench"):
        bench = CATBenchmarkSystem()
        if len(args) > 1 and not args[1].startswith("-"):
            name = args[1]
            print(f"Running CAT Benchmark Suite on model '{name}'...")
            res = bench.run_full_benchmark(name)
            print(f"\nBenchmark Complete for '{name}':")
            for cat_k, score in res.items():
                print(f"  - {cat_k:<16} : {score.score:.1f}/100 [{score.source}]")
            return 0
        else:
            print(bench.format_leaderboard())
            print("\nTo benchmark a specific model: cat models benchmark <name>")
            return 0

    # 7. LIST COMMAND (DEFAULT)
    # Parse options: --category, --provider, refresh
    cat_filter = None
    provider_filter = None
    state_filter = None
    refresh_requested = False

    i = 0
    while i < len(args):
        a = args[i]
        if a in ("--category", "-c") and i + 1 < len(args):
            cat_filter = args[i + 1]
            i += 2
        elif a in ("--provider", "-p") and i + 1 < len(args):
            provider_filter = args[i + 1]
            i += 2
        elif a in ("--new", "-n"):
            state_filter = "new"
            i += 1
        elif a in ("refresh", "--refresh", "-r"):
            refresh_requested = True
            i += 1
        elif a in ("list",):
            i += 1
        else:
            if not cat_filter and a in catalog.categories():
                cat_filter = a
            i += 1

    if refresh_requested:
        print("Refreshing models from AI providers and local engine...")
        try:
            from .providers.discovery_manager import get_discovery_manager
            dm = get_discovery_manager()
            res = dm.discover_all(timeout=6.0)
            total_discovered = sum(len(m) for m in res.values())
            print(f"Discovery complete: {total_discovered} models found across {len(res)} providers.\n")
        except Exception as e:
            print(f"cat models: refresh note: {e}", file=sys.stderr)

    # If provider specified, query dynamic registry
    if provider_filter and provider_filter != "ollama":
        try:
            from .models.dynamic_registry import get_dynamic_registry
            reg = get_dynamic_registry()
            models = reg.list_models(provider=provider_filter, state=state_filter)
            print(f"CAT Dynamic Model Registry ({len(models)} models for provider '{provider_filter}'):\n")
            header = f"{'Provider':<14} | {'Model ID':<34} | {'Context':<8} | {'State':<10} | {'Capabilities'}"
            print(header)
            print("-" * len(header))
            for m in models:
                caps = ", ".join(m.capabilities[:4])
                ctx = _format_context(m.context_window)
                print(f"{m.provider:<14} | {m.model_id:<34} | {ctx:<8} | {m.availability_state:<10} | {caps}")
            return 0
        except Exception as e:
            print(f"cat models: failed to query registry: {e}", file=sys.stderr)
            return 1

    engine = ModelCompatibilityEngine()
    models_to_display = catalog.search_models(category=cat_filter)
    title_suffix = f" [Category: {cat_filter}]" if cat_filter else ""
    print(f"CAT Local & Curated Models ({len(models_to_display)} models){title_suffix}:\n")

    header = f"{'Model Name':<28} | {'Params':<8} | {'Size':<8} | {'Compatibility':<16} | {'Status'}"
    print(header)
    print("-" * len(header))

    for m in models_to_display:
        compat = engine.evaluate(m)
        is_inst = m["name"] in installed_local
        status_str = "INSTALLED" if is_inst else "Available"
        print(f"{m['name']:<28} | {m.get('params','?'):<8} | {m.get('size_gb',0):.1f} GB  | {compat.tier_label_ascii:<16} | {status_str}")

    print("\nCommands:")
    print("  cat models recommend        Get hardware-tailored recommendations")
    print("  cat models info <name>      Inspect model memory footprint & details")
    print("  cat models install <name>   Download model into local Ollama engine")
    print("  cat models benchmark        View standard benchmark leaderboard")
    return 0


def _providers_cli(argv: list[str]) -> int:
    args = argv[1:]
    sub = args[0] if args else "list"

    if sub in ("--help", "-h", "help"):
        print("Usage: cat providers [command]")
        print("\nCommands:")
        print("  status          Real-time provider health, latencies & backup failover pool")
        print("  backup          Manage dynamic backup provider pool (list|add|remove|reorder|toggle|test)")
        print("  test [id]       Test connectivity, models, and response latency for a provider")
        print("  list (default)  List all registered providers and model counts")
        print("  audit           Comprehensive audit of providers, model coverage & status")
        print("  refresh         Trigger parallel model discovery across all providers")
        return 0

    if sub in ("status", "health"):
        try:
            from .resilience.health_monitor import get_health_monitor
            from .providers import provider_manager as pm
            from . import aicore
            mon = get_health_monitor()
            prim = aicore.load_config() or {}
            p_prov = prim.get("provider", "Not configured")
            p_model = prim.get("model", "")
            p_badge, p_label = mon.get_status_badge(p_prov, p_model)
            p_health = mon.get_health(p_prov, p_model)
            p_lat = f"{p_health.latency_ms}ms" if p_health.latency_ms else "—"

            print("=" * 74)
            print("                 CAT AI PROVIDER RESILIENCE & HEALTH REPORT")
            print("=" * 74)
            print("  PRIMARY PROVIDER:")
            print(f"    {p_badge} {p_prov:<16} model: {p_model:<22} [{p_label}]  latency: {p_lat}")
            print("-" * 74)
            print("  BACKUP PROVIDERS (Automatic Failover Pool):")
            backups = pm.load_backup_providers()
            if not backups:
                print("    No backup providers configured. Use `cat providers backup add <provider>`")
            else:
                print(f"    {'#':<3} | {'Provider':<14} | {'Model':<22} | {'Health / Status':<16} | {'State'}")
                print("    " + "-" * 68)
                for i, b in enumerate(backups):
                    bp = b.get("provider", "?")
                    bm = b.get("model", "?")
                    glyph, lbl = mon.get_status_badge(bp, bm)
                    en = "✓ Enabled" if b.get("enabled", True) else "✗ Disabled"
                    b_health = mon.get_health(bp, bm)
                    lat_str = f" ({b_health.latency_ms}ms)" if b_health.latency_ms else ""
                    stat_str = f"{glyph} {lbl}{lat_str}"
                    print(f"    {i+1:<3} | {bp:<14} | {bm:<22} | {stat_str:<16} | {en}")
            print("=" * 74)
            print("Commands: cat providers test [id] | cat providers backup [list|add|remove|reorder]")
            return 0
        except Exception as e:
            print(f"cat providers status: error: {e}", file=sys.stderr)
            return 1

    elif sub in ("test", "check"):
        try:
            from .providers import provider_manager as pm
            target = args[1] if len(args) > 1 else ""
            if not target:
                from . import aicore
                cfg = aicore.load_config() or {}
                target = cfg.get("provider", "")
                model = cfg.get("model", "")
            else:
                target = target.strip().lower()
                # Find configured backup or default
                backups = pm.load_backup_providers()
                matched = next((b for b in backups if b.get("provider", "").lower() == target), None)
                if matched:
                    cfg = dict(matched)
                    model = cfg.get("model", "")
                else:
                    cfg = {"provider": target, "model": "default"}
                    model = "default"

            if not target:
                print("cat providers test: specify a provider (e.g. `cat providers test groq` or `cat providers test ollama`)")
                return 1

            print(f"Testing provider '{target}' ({model})...")
            ok, msg, models = pm.test_provider_connectivity(cfg)
            status = "READY" if ok else "FAILED"
            glyph = "✓" if ok else "✗"
            print(f"  {glyph} Status: {status}")
            print(f"  Details: {msg}")
            if models:
                disp_models = models[:6]
                print(f"  Models detected: {len(models)} ({', '.join(disp_models)}{'...' if len(models) > 6 else ''})")
            return 0 if ok else 1
        except Exception as e:
            print(f"cat providers test: error: {e}", file=sys.stderr)
            return 1

    elif sub == "backup":
        try:
            from .providers import provider_manager as pm
            b_cmd = args[1] if len(args) > 1 else "list"

            if b_cmd in ("list", "ls"):
                backups = pm.load_backup_providers()
                print(f"CAT Backup Provider Pool ({len(backups)} configured):")
                print(f"  {'#':<3} | {'Provider':<16} | {'Model':<24} | {'Status':<12} | {'State'}")
                print("  " + "-" * 66)
                for i, b in enumerate(backups):
                    bp = b.get("provider", "?")
                    bm = b.get("model", "?")
                    st = b.get("status", "disconnected")
                    en = "Enabled" if b.get("enabled", True) else "Disabled"
                    print(f"  {i+1:<3} | {bp:<16} | {bm:<24} | {st:<12} | {en}")
                print("\nSubcommands:")
                print("  cat providers backup add <provider> [model]")
                print("  cat providers backup remove <index_or_provider>")
                print("  cat providers backup reorder <from_1_based> <to_1_based>")
                print("  cat providers backup enable <index_or_provider>")
                print("  cat providers backup disable <index_or_provider>")
                print("  cat providers backup test [index_or_provider]")
                return 0

            elif b_cmd == "add":
                if len(args) < 3:
                    print("Usage: cat providers backup add <provider> [model]")
                    return 1
                prov = args[2].strip().lower()
                model = args[3].strip() if len(args) > 3 else ("llama3.3" if prov == "ollama" else "default")
                entry = {
                    "provider": prov,
                    "model": model,
                    "enabled": True,
                    "api_style": "ollama" if prov == "ollama" else "openai",
                    "base_url": "http://localhost:11434" if prov == "ollama" else "",
                }
                ok = pm.add_backup_provider(entry)
                if ok:
                    print(f"✓ Added '{prov}' ({model}) to backup pool.")
                    return 0
                print(f"✗ Failed to add '{prov}' to backup pool.", file=sys.stderr)
                return 1

            elif b_cmd in ("remove", "rm", "delete"):
                if len(args) < 3:
                    print("Usage: cat providers backup remove <index_or_provider>")
                    return 1
                target = args[2].strip()
                if target.isdigit():
                    target_idx = int(target) - 1
                    ok = pm.remove_backup_provider(target_idx)
                else:
                    ok = pm.remove_backup_provider(target)
                if ok:
                    print(f"✓ Removed backup provider '{args[2]}'.")
                    return 0
                print(f"✗ Backup provider '{args[2]}' not found.", file=sys.stderr)
                return 1

            elif b_cmd in ("reorder", "move"):
                if len(args) < 4:
                    print("Usage: cat providers backup reorder <from_1_based> <to_1_based>")
                    return 1
                try:
                    f_idx = int(args[2]) - 1
                    t_idx = int(args[3]) - 1
                    ok = pm.reorder_backup_provider(f_idx, t_idx)
                    if ok:
                        print(f"✓ Reordered backup priority position {args[2]} → {args[3]}.")
                        return 0
                    print("✗ Invalid index specified.", file=sys.stderr)
                    return 1
                except ValueError:
                    print("✗ Indices must be integers.", file=sys.stderr)
                    return 1

            elif b_cmd in ("enable", "disable"):
                if len(args) < 3:
                    print(f"Usage: cat providers backup {b_cmd} <index_or_provider>")
                    return 1
                target = args[2].strip()
                enabled = (b_cmd == "enable")
                if target.isdigit():
                    target_idx = int(target) - 1
                    ok = pm.set_backup_provider_enabled(target_idx, enabled)
                else:
                    ok = pm.set_backup_provider_enabled(target, enabled)
                if ok:
                    print(f"✓ {b_cmd.capitalize()}d backup provider '{args[2]}'.")
                    return 0
                print(f"✗ Backup provider '{args[2]}' not found.", file=sys.stderr)
                return 1

            elif b_cmd == "test":
                target = args[2].strip() if len(args) > 2 else "1"
                backups = pm.load_backup_providers()
                if not backups:
                    print("No backup providers configured.")
                    return 1
                if target.isdigit():
                    idx = int(target) - 1
                    entry = backups[idx] if 0 <= idx < len(backups) else None
                else:
                    entry = next((b for b in backups if b.get("provider", "").lower() == target.lower()), None)
                if not entry:
                    print(f"Backup provider '{target}' not found.", file=sys.stderr)
                    return 1
                print(f"Testing backup provider '{entry.get('provider')}' ({entry.get('model')})...")
                ok, msg, models = pm.test_provider_connectivity(entry)
                glyph = "✓" if ok else "✗"
                print(f"  {glyph} Status: {'READY' if ok else 'FAILED'}")
                print(f"  Details: {msg}")
                return 0 if ok else 1

            else:
                print(f"cat providers backup: unknown subcommand '{b_cmd}'. Use: list | add | remove | reorder | enable | disable | test")
                return 1
        except Exception as e:
            print(f"cat providers backup: error: {e}", file=sys.stderr)
            return 1

    try:
        from .models.dynamic_registry import get_dynamic_registry
        from .providers.discovery_manager import get_discovery_manager
        registry = get_dynamic_registry()
        dm = get_discovery_manager()
    except Exception as e:
        print(f"cat providers: initialization error: {e}", file=sys.stderr)
        return 1

    if sub == "audit":
        audit = registry.get_audit_summary()
        status_map = dm.get_all_provider_status()
        print("=" * 72)
        print("                   CAT AI PROVIDER & MODEL AUDIT REPORT")
        print("=" * 72)
        print(f"  Total Models in Dynamic Registry : {audit.get('total_models', 0)}")
        print(f"  Registered Providers             : {audit.get('total_providers', 0)}")
        print(f"  Verified Active Models           : {audit.get('models_by_state', {}).get('available', 0)}")
        print(f"  Newly Discovered Models          : {audit.get('models_by_state', {}).get('new', 0)}")
        print(f"  Deprecated Models                : {audit.get('models_by_state', {}).get('deprecated', 0)}")
        print("-" * 72)
        print(f"  {'Provider':<18} | {'Status':<10} | {'Models':<8} | {'Sample Flagship Models'}")
        print("-" * 72)
        by_prov = audit.get("models_by_provider", {})
        for pid in sorted(by_prov.keys()):
            cnt = by_prov[pid]
            pstatus = status_map.get(pid, {}).get("status", "registered")
            prov_models = registry.list_models(provider=pid)
            sample_ids = [m.model_id for m in prov_models[:2]]
            sample_str = ", ".join(sample_ids)
            print(f"  {pid:<18} | {pstatus:<10} | {cnt:<8} | {sample_str}")
        print("=" * 72)
        return 0

    elif sub in ("refresh", "discover", "update"):
        print("Initiating dynamic discovery across AI providers...")
        res = dm.discover_all(timeout=6.0)
        print("\nDiscovery Results:")
        print(f"  {'Provider':<18} | {'Discovered':<14} | {'Status'}")
        print("-" * 52)
        for pid, models in sorted(res.items()):
            status_desc = f"{len(models)} models" if models else "0 models"
            st = "OK" if models else "Degraded / Offline"
            print(f"  {pid:<18} | {status_desc:<14} | {st}")
        total = sum(len(m) for m in res.values())
        print("-" * 52)
        print(f"Total discovered models: {total}.")
        return 0

    elif sub in ("list", "ls"):
        by_prov = registry.get_audit_summary().get("models_by_provider", {})
        print(f"CAT AI Providers ({len(by_prov)} providers registered):\n")
        print(f"  {'Provider ID':<22} | {'Registered Models'}")
        print("-" * 48)
        for pid in sorted(by_prov.keys()):
            print(f"  {pid:<22} | {by_prov[pid]} models")
        print(f"\nRun `cat models --provider <id>` to inspect models for a provider.")
        print(f"Run `cat providers status` to check real-time health and backup failover.")
        print(f"Run `cat providers audit` for full diagnostic report.")
        return 0

    else:
        print(f"cat providers: unknown command '{sub}'. Use: status | backup | test | list | audit | refresh")
        return 1


def _offline_cli(argv: list[str]) -> int:
    """Switch CAT to Emergency Local Mode."""
    try:
        from .resilience.orchestrator import get_orchestrator
        orch = get_orchestrator()
        ok, msg = orch.enable_emergency_offline_mode()
        glyph = "✓" if ok else "⚠"
        print("=" * 72)
        print("                       CAT EMERGENCY LOCAL MODE")
        print("=" * 72)
        print(f"  {glyph} {msg}")
        print("  - All third-party cloud AI network queries are strictly disabled.")
        print("  - Local inference will be used as the primary and backup engine.")
        print("=" * 72)
        return 0 if ok else 1
    except Exception as e:
        print(f"cat offline: error: {e}", file=sys.stderr)
        return 1


def _parse_version_tuple(v_str: str) -> tuple:
    """Convert version string like '0.7.9.0' or 'v0.8.0' to a comparable integer tuple."""
    import re
    cleaned = v_str.strip().lstrip("vV")
    parts = []
    for part in re.split(r"[.\-+]", cleaned):
        digits = re.match(r"^\d+", part)
        if digits:
            parts.append(int(digits.group(0)))
        else:
            break
    if not parts:
        raise ValueError(f"Invalid non-semver version string: '{v_str}'")
    return tuple(parts)


def _debug_cli(argv: list[str]) -> int:
    """Print deterministic diagnostic runtime and environment information (read-only)."""
    import platform
    ver = _version()
    py_ver = sys.version.replace("\n", " ")
    py_exe = sys.executable
    plat = f"{platform.system()} ({sys.platform}) {platform.release()}"
    arch = platform.machine() or "unknown"
    cwd = os.getcwd()

    raw_prog = os.path.basename(sys.argv[0] if sys.argv else "cat").lower()
    prog = "cct" if "cct" in raw_prog else "cat"

    print("=" * 72)
    print("                CAT DIAGNOSTIC ENVIRONMENT & RUNTIME")
    print("=" * 72)
    print(f"  Command           : {prog} {' '.join(argv)}")
    print(f"  Automation Safety : {SAFETY_READ_ONLY} (safe to automate, changes_state=False)")
    print(f"  CAT Version       : {ver}")
    print(f"  Python Version    : {py_ver}")
    print(f"  Python Executable : {py_exe}")
    print(f"  Platform          : {plat}")
    print(f"  Architecture      : {arch}")
    print(f"  Working Directory : {cwd}")
    print("  Available Scripts : cat (calc_terminal.cli:main), cct (calc_terminal.cli:main)")
    print("  Mode              : Read-only diagnostics (no files, config, or state modified)")
    print("=" * 72)
    return 0


def _update_check_cli(argv: list[str]) -> int:
    """Perform read-only release check against official GitHub releases."""
    import json
    import urllib.request
    import urllib.error

    raw_prog = os.path.basename(sys.argv[0] if sys.argv else "cat").lower()
    prog = "cct" if "cct" in raw_prog else "cat"

    current_ver_str = _version()
    try:
        current_tuple = _parse_version_tuple(current_ver_str)
    except Exception as e:
        print(f"{prog} update --check: error: cannot parse installed version '{current_ver_str}': {e}", file=sys.stderr)
        return 1

    print("Checking for CAT updates from official repository...")
    print(f"  Source: {CAT_RELEASES_API_URL}")

    req = urllib.request.Request(
        CAT_RELEASES_API_URL,
        headers={
            "User-Agent": f"CAT-CLI/{current_ver_str}",
            "Accept": "application/vnd.github.v3+json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"{prog} update --check: HTTP error {e.code}: {e.reason}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"{prog} update --check: network error: {e.reason}", file=sys.stderr)
        return 1
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"{prog} update --check: malformed release metadata: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"{prog} update --check: unexpected error: {e}", file=sys.stderr)
        return 1

    tag_name = data.get("tag_name")
    if not tag_name:
        print(f"{prog} update --check: error: release metadata is missing 'tag_name'", file=sys.stderr)
        return 1

    latest_ver_str = tag_name.lstrip("vV")
    try:
        latest_tuple = _parse_version_tuple(latest_ver_str)
    except Exception as e:
        print(f"{prog} update --check: error: unparseable remote version '{tag_name}': {e}", file=sys.stderr)
        return 1

    print("\nCAT Release Check (Read-Only)")
    print("-" * 40)
    print(f"  Installed Version : {current_ver_str}")
    print(f"  Latest Version    : {latest_ver_str} ({tag_name})")

    if latest_tuple > current_tuple:
        print(f"  Update Available  : YES ({current_ver_str} -> {latest_ver_str})")
        print(f"  Release URL       : {data.get('html_url', f'https://github.com/{CAT_GITHUB_REPO}/releases')}")
    else:
        print("  Update Available  : NO (CAT is up to date)")

    print("  Status            : Read-only check complete — no installation was performed.")
    print("-" * 40)
    return 0


def _state_changing_disabled(cmd: str, argv: list[str]) -> int:
    """State-changing commands (update, rollback, repair) are not enabled in this public build.
    Returns non-zero exit code with informative guidance."""
    raw_prog = os.path.basename(sys.argv[0] if sys.argv else "cat").lower()
    prog = "cct" if "cct" in raw_prog else "cat"

    print(f"{prog}: error: state-changing operation '{cmd}' is not enabled in this public CLI build.", file=sys.stderr)
    if cmd == "update":
        print("  To safely check for available releases without altering your system, run:", file=sys.stderr)
        print(f"      {prog} update --check", file=sys.stderr)
    elif cmd == "rollback":
        print("  Automated rollbacks are disabled to prevent unintended workspace or installation changes.", file=sys.stderr)
    elif cmd == "repair":
        print("  To run non-destructive diagnostic health checks on your installation, run:", file=sys.stderr)
        print(f"      {prog} --doctor", file=sys.stderr)
    return 1


def _git_sync_cli(argv: list[str]) -> int:
    """Publish and sync repository changes to GitHub with verified status."""
    from .git_sync import sync_and_publish
    args = argv[1:]
    if argv and argv[0] == "git" and len(argv) > 1:
        args = argv[2:]
    message = " ".join(args).strip() if args else None
    return sync_and_publish(message=message)


def main(argv=None):
    """Console entry point. Returns the process exit code."""
    argv = list(sys.argv[1:] if argv is None else argv)

    # CAT's art/UI use Unicode (box drawing, arrows, ...). When stdout is
    # piped or redirected on Windows it defaults to the legacy code page
    # (cp1252) and print() would crash with UnicodeEncodeError mid-boot.
    # Force UTF-8 with lossy fallback; interactive consoles are unaffected.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    if argv in (["-h"], ["--help"], ["help"]):
        print(_usage())
        return 0

    if argv in (["-v"], ["--version"], ["version"]):
        print(f"CAT v{_version()}")
        return 0

    if argv in (["--debug"], ["debug"]):
        return _debug_cli(argv)

    # Route Git / GitHub synchronization commands
    if argv and argv[0] in ("push", "--push", "publish", "--publish", "sync", "--sync"):
        return _git_sync_cli(argv)

    if argv and argv[0] == "git" and len(argv) > 1 and argv[1] in ("push", "publish", "sync", "status"):
        if argv[1] == "status":
            from .git_sync import inspect_repository
            st = inspect_repository()
            print(f"Branch : {st.current_branch}")
            print(f"Remote : {st.remote_url}")
            print(f"HEAD   : {st.head_commit}")
            print(f"Changes: {'Yes' if st.has_changes else 'Clean'}")
            return 0
        return _git_sync_cli(argv)

    # Route maintenance commands before workspace parsing
    if argv and argv[0] in ("update", "--update"):
        if len(argv) > 1 and argv[1] in ("--check", "check"):
            return _update_check_cli(argv)
        return _state_changing_disabled("update", argv)

    if argv and argv[0] in ("rollback", "--rollback"):
        return _state_changing_disabled("rollback", argv)

    if argv and argv[0] in ("repair", "--repair"):
        return _state_changing_disabled("repair", argv)

    # Assert CAT CLI terminal tab & window identity
    try:
        from .terminal_identity import init_terminal_identity

        init_terminal_identity()
    except Exception:
        pass

    if argv in (["--doctor"], ["doctor"]):
        from .doctor import main as _doctor_main
        return _doctor_main()

    # --- Fomoji auth subcommands (never gated — they ARE the gate) ---
    if argv and argv[0] in ("--auth", "auth"):
        try:
            from .fomoji_auth import _auth_cli
            return _auth_cli(argv)
        except Exception as e:
            print(f"cat: auth error: {e}", file=sys.stderr)
            return 1
    if argv and argv[0] in ("--signout", "--sign-out", "--logout", "signout", "sign-out", "logout"):
        try:
            from .fomoji_auth import logout, get_identity
            ident = get_identity()
            who = ident.get("name") if ident else None
            logout()
            try:
                import urllib.request
                from .fomoji_auth import get_fomoji_url
                base = get_fomoji_url()
                req = urllib.request.Request(base + "/api/logout", data=b"{}", method="POST")
                req.add_header("Content-Type", "application/json")
                urllib.request.urlopen(req, timeout=3)
            except Exception:
                pass
            if who:
                print(f"Signed out — {who} disconnected. Run `cat --auth login` to sign in again.")
            else:
                print("Signed out — no active session.")
            return 0
        except Exception as e:
            print(f"cat: signout error: {e}", file=sys.stderr)
            return 1
    # --- CAT Vision (spec 40: cat vision / cat vision start etc) ----
    if argv and argv[0] == "vision":
        sub = argv[1] if len(argv) > 1 else "status"
        if sub in ("status", "start", "stop", "pause", "resume", "analyze", "screenshot", "clear", "help"):
            # Route through the shared VisionSessionManager logic, not a duplicate.
            try:
                from calc_terminal.vision.session import VisionSessionManager
                from calc_terminal.vision.capture import CaptureConfig
                import asyncio
                mgr = VisionSessionManager()
                print(f"CAT Vision: {sub} — launching CAT to handle vision session...")
                print("Open CAT and use the CAT Vision panel (eye icon in main menu) for full screen sharing + annotation.")
                print("Browser/PWA: open FATTY CAT at http://localhost:8765 for live capture.")
                if sub == "help":
                    print("\n  cat vision start     Start capture (browser will prompt)")
                    print("  cat vision stop      Stop sharing")
                    print("  cat vision pause     Pause capture")
                    print("  cat vision analyze   Analyze current screen")
                    print("  cat vision clear     Clear vision session")
                return 0
            except Exception as e:
                print(f"cat vision {sub} failed: {e}", file=sys.stderr)
                return 1
        print(f"cat: unknown vision subcommand: {sub} (try: cat vision help)")
        return 2

    # --- Fatty CAT Web / PWA Server & Launcher ---------------------------
    # `cat fatty` / `cat web` / `cat server` / `cat --fatty` / `cat --web`
    if argv and argv[0] in ("fatty", "--fatty", "web", "--web", "pwa", "--pwa", "server", "--server"):
        cmd = argv[0].lstrip("-")
        try:
            from .web.server import ensure_fatty_server, is_server_running, main as _server_main
        except ImportError as e:
            print("cat: the Fatty CAT web server needs the optional `web` extra.", file=sys.stderr)
            print(f"  (missing: {e})", file=sys.stderr)
            print("  Install it with:  pip install \"cct-cli[web]\"", file=sys.stderr)
            return 1
        if cmd in ("server",):
            print("Starting Fatty CAT server on http://localhost:8765 ... (Press Ctrl+C to stop)")
            try:
                _server_main()
                return 0
            except KeyboardInterrupt:
                print("\nFatty CAT server stopped.")
                return 0
            except Exception as e:
                print(f"cat server error: {e}", file=sys.stderr)
                return 1

        # `cat fatty` or `cat web`: ensure server is running, then open browser
        print("Launching Fatty CAT at http://localhost:8765 ...")
        if not is_server_running():
            print("Starting background Fatty CAT server...")
            if not ensure_fatty_server(timeout=10.0, auto_start=True):
                print("cat: failed to start Fatty CAT server on port 8765", file=sys.stderr)
                return 1
            print("✓ Fatty CAT server is running at http://localhost:8765/")
        else:
            print("✓ Fatty CAT server is already active at http://localhost:8765/")

        # Try to launch inside CAT's own browser first
        try:
            from .host.launcher import launch_cat_host, can_launch_host
            if can_launch_host():
                return launch_cat_host(
                    start_browser_url="http://localhost:8765/",
                    start_mode="browser",
                )
        except SystemExit:
            raise
        except Exception:
            pass

        # Fallback to system web browser
        import webbrowser
        webbrowser.open("http://localhost:8765/")
        print("Opened http://localhost:8765/ in your default browser.")
        return 0

    # --- CAT Browser (real Qt WebEngine / Chromium) ----------------------
    # `cat browse [url]` / `cat --browser [url]` — opens CAT's real browser
    # using QWebEngineView (Chromium via Qt WebEngine). Real HTML/CSS/JS.
    if argv and argv[0] in ("browse", "--browse", "--browser", "browser", "--host", "--host-browser", "host", "/cat", "cat-browser"):
        _browse_args = argv[1:]
        url = _browse_args[0] if _browse_args else None
        if url and url.lower() in ("fatty", "--fatty", "web", "--web"):
            url = "http://localhost:8765/"
        if url and url.startswith("-"):
            print(_usage())
            print(f"cat: error: unexpected argument for browse: {url}")
            return 2
        # Try the real browser first (Qt WebEngine / Chromium)
        try:
            from .host.launcher import launch_cat_host, can_launch_host
            if can_launch_host():
                return launch_cat_host(
                    start_browser_url=url,
                    start_mode="browser" if url else "terminal",
                )
        except SystemExit:
            raise
        except Exception:
            pass
        # Fallback: standalone Qt browser window
        try:
            from .browser_gui.qt_browser import launch_qt_browser
            return launch_qt_browser(start_url=url)
        except Exception:
            pass
        print("[CAT Browser] No browser engine found.", file=sys.stderr)
        print("Install PySide6 for real HTML/CSS/JS rendering in CAT Browser:", file=sys.stderr)
        print("  pip install PySide6", file=sys.stderr)
        return 1

    # --- Dynamic Model & Provider CLI (v2026.09) -------------------------
    if argv and argv[0] in ("models", "--models", "model", "--model"):
        return _models_cli(argv)

    if argv and argv[0] in ("providers", "--providers", "provider", "--provider"):
        return _providers_cli(argv)

    if argv and argv[0] in ("offline", "--offline", "local-only", "--local-only"):
        return _offline_cli(argv)

    # Optional single positional: the workspace/project directory.
    path = None
    rest = []
    for arg in argv:
        if arg.startswith("-") and arg not in ("-",):
            print(_usage())
            print(f"cat: error: unrecognized argument: {arg}")
            return 2
        if path is None:
            path = arg
        else:
            rest.append(arg)
    if rest:
        print(_usage())
        print(f"cat: error: too many arguments: {' '.join(rest)}")
        return 2

    if path is not None:
        # `cct .` means "stay in the current directory"; any other path
        # must exist and be a directory before we change into it, so a
        # typo fails with a clear message instead of launching CCT in
        # whatever directory the shell happened to be in.
        expanded = os.path.abspath(os.path.expanduser(path))
        if not os.path.isdir(expanded):
            print(f"cat: error: not a directory: {expanded}", file=sys.stderr)
            return 2
        try:
            os.chdir(expanded)
        except OSError as e:
            print(f"cat: error: cannot open workspace {expanded}: {e}", file=sys.stderr)
            return 2

    # First-run detection: on the very first launch only, prepare the
    # application-data directory and run model.py's one-time
    # initialization before the main application starts. If that fails
    # nothing is marked as done, the error is reported, and the next
    # `cct` retries. Every later launch skips straight to the app.
    from .first_run import ensure_first_run
    rc = ensure_first_run()
    if rc != 0:
        return rc

    return bootstrap()


def _launch_cat_terminal():
    """Launch the CAT Textual TUI (CCTApp). This is the main CAT experience:
    model.py setup wizard, /ai chat, /agent notebook, etc."""
    try:
        from .terminal_identity import init_terminal_identity
        init_terminal_identity()
    except Exception:
        pass
    from .app import App
    from .ui.app import launch_chat_app
    repl = App()
    config = {}
    try:
        from . import aicore
        config = aicore.load_config()
    except Exception:
        pass
    stats = {
        "solved": len(repl.history),
        "provider": config.get("provider") or "none",
        "model": config.get("model") or "none",
    }
    ok, msg = launch_chat_app(repl, repl.history, stats)
    if not ok:
        try:
            from . import theme
            theme.enable_windows_ansi()
            print(theme.orange(f"  {msg}"))
        except Exception:
            print(f"  {msg}")
        print("  Falling back to terminal REPL...")
        repl.run()
    return 0


def bootstrap():
    """CAT entry point - handles Fomoji auth, then launches the CAT terminal.

    Flow:
      1. Ensure Fomoji server is running (auto-start if needed)
      2. Check auth status (fast, reads local file)
      3. If already authenticated -> launch CAT terminal directly
      4. If not authenticated:
         a. Start device flow, get code + notification
         b. Open browser to Fomoji connector page (y/n permission)
         c. Poll for approval in BACKGROUND THREAD
         d. After approval -> verify session -> launch CAT terminal
    """
    from .fomoji_auth import (
        ensure_fomoji_server, status, get_identity,
        check_server_reachable, get_fomoji_url,
        _device_start, _device_poll, _save_local, _print_device_prompt,
        DEFAULT_PERMISSIONS,
    )

    # Ensure server is running first with proper dependency checks and auto-start
    from .fomoji_manager import initialize_fomoji_subsystem
    server_ok = initialize_fomoji_subsystem(interactive=True)
    if not server_ok and not check_server_reachable(timeout=3):
        # Fomoji is an optional component — CAT starts in standalone/offline mode without crashing!
        os.environ["CAT_ALLOW_NO_AUTH"] = "1"
        try:
            from . import theme
            theme.enable_windows_ansi()
            print(theme.orange("  ⚠ Fomoji identity server is unavailable."))
            print(theme.dim("    Launching CAT CLI in standalone offline mode...\n"))
        except Exception:
            print("  ⚠ Fomoji identity server is unavailable.")
            print("    Launching CAT CLI in standalone offline mode...\n")
        return _launch_cat_terminal()

    # Check if user is already authenticated
    auth_status = status()

    if auth_status == "connected":
        # Already authenticated - launch CAT terminal directly
        try:
            from . import theme
            theme.enable_windows_ansi()
            ident = get_identity()
            name = ident.get("name", "?") if ident else "?"
            fid = ident.get("fomojiId", "?") if ident else "?"
            print(theme.green(f"\n  ✓ Already authenticated as {name} ({fid})", bold=True))
            print(theme.dim("    Launching CAT CLI..."))
            print()
        except Exception:
            print("\n  Already authenticated. Launching CAT CLI...\n")
        return _launch_cat_terminal()

    if auth_status == "expired":
        print("\n  Your Fomoji session has expired. Re-authenticating...\n")

    # --- Device flow for non-authenticated users ---
    import threading
    import time as _time

    # Start device flow
    try:
        perms = DEFAULT_PERMISSIONS
        start = _device_start(perms)
        device_code = start["deviceCode"]
        user_code = start["userCode"]
        verification_url = f"{get_fomoji_url()}{start.get('verificationUrl', '/connector.html')}"
        poll_interval = int(start.get("pollIntervalSeconds", 3))
    except Exception as e:
        print(f"\n  Could not initialize Fomoji device flow: {e}")
        print("  Starting CAT in standalone offline mode...\n")
        os.environ["CAT_ALLOW_NO_AUTH"] = "1"
        return _launch_cat_terminal()

    # Show code in terminal + Windows system notification + copy to clipboard
    _print_device_prompt(user_code, verification_url)

    # Shared state for background polling
    auth_result = {"identity": None, "error": None, "done": False}
    _close_requested = threading.Event()

    def _poll_for_approval():
        deadline = _time.monotonic() + 300
        while _time.monotonic() < deadline:
            try:
                result = _device_poll(device_code)
                st = result.get("status")
                if st == "approved":
                    identity = {
                        "fomojiId": result.get("fomojiId"),
                        "name": result.get("name"),
                        "identityType": result.get("identityType", "PERSON"),
                        "permissions": result.get("permissions", perms),
                        "applicationId": result.get("applicationId", "cat"),
                    }
                    _save_local({"token": result["connectorToken"], "identity": identity})
                    auth_result["identity"] = identity
                    auth_result["done"] = True
                    _close_requested.set()
                    return
                elif st in ("denied", "expired"):
                    auth_result["error"] = f"Connection request {st}."
                    auth_result["done"] = True
                    return
            except Exception:
                pass
            _time.sleep(poll_interval)
        auth_result["error"] = "Timed out waiting for approval."
        auth_result["done"] = True

    # Ask user if they want to open the browser
    open_browser = True
    if sys.stdin.isatty() and sys.stdout.isatty():
        try:
            answer = input("\n  Open browser now? (y/n): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = "n"
        if answer != "y":
            open_browser = False
            print("\n  Skipping browser. You can open it manually later.")
            print(f"  Verification URL: {verification_url}")
            print(f"  Your code: {user_code}\n")

    if not open_browser:
        # Poll without a browser window
        poll_thread = threading.Thread(target=_poll_for_approval, daemon=True)
        poll_thread.start()
        try:
            while not auth_result["done"]:
                _time.sleep(1)
        except KeyboardInterrupt:
            print("\n  Login cancelled.\n")
            return 1
        if auth_result["identity"]:
            name = auth_result["identity"].get("name", "?")
            print(f"\n  ✓ Authenticated as {name}")
            return _launch_cat_terminal()
        elif auth_result["error"]:
            print(f"\n  {auth_result['error']}\n")
            return 1
        return 1

    # Open browser for verification
    from .host.launcher import create_browser_window
    _time.sleep(1.5)

    app, window, _ = create_browser_window(
        start_browser_url=verification_url,
        start_mode="browser",
    )

    def _close_browser():
        try:
            for w in app.topLevelWidgets():
                if hasattr(w, 'close'):
                    w.close()
                    return
        except Exception:
            pass

    # Timer on the main thread that polls the flag and closes when set
    try:
        from PySide6.QtCore import QTimer as _QTimer
        _close_timer = _QTimer()
        _close_timer.setInterval(200)
        _close_timer.timeout.connect(lambda: _close_browser() if _close_requested.is_set() else None)
        _close_timer.start()
    except Exception:
        try:
            from PyQt6.QtCore import QTimer as _QTimer
            _close_timer = _QTimer()
            _close_timer.setInterval(200)
            _close_timer.timeout.connect(lambda: _close_browser() if _close_requested.is_set() else None)
            _close_timer.start()
        except Exception:
            pass

    # Poll in background thread
    poll_thread = threading.Thread(target=_poll_for_approval, daemon=True)
    poll_thread.start()

    # Start Qt event loop - BLOCKS until browser window closed (after approval)
    app.exec()  # type: ignore

    # After authentication, verify session and launch CAT terminal
    if auth_result["identity"]:
        name = auth_result["identity"].get("name", "?")
        try:
            from . import theme
            theme.enable_windows_ansi()
            print(theme.green(f"\n  ✓ Authenticated as {name}", bold=True))
            print(theme.dim("  Verifying session..."))
        except Exception:
            print(f"\n  ✓ Authenticated as {name}")

        # Verify the session is valid
        try:
            if status() == "connected":
                try:
                    from . import theme
                    theme.enable_windows_ansi()
                    print(theme.green("  ✓ Session verified!", bold=True))
                    print(theme.green("    Launching CAT CLI...\n", bold=True))
                except Exception:
                    print("  ✓ Session verified! Launching CAT CLI...\n")
                return _launch_cat_terminal()
            else:
                print("  ⚠ Session verification unconfirmed. Starting CAT in standalone offline mode...\n")
                os.environ["CAT_ALLOW_NO_AUTH"] = "1"
                return _launch_cat_terminal()
        except Exception:
            print("  Launching CAT CLI in standalone offline mode...\n")
            os.environ["CAT_ALLOW_NO_AUTH"] = "1"
            return _launch_cat_terminal()

    if auth_result["error"]:
        print(f"\n  {auth_result['error']}")
        print("  Starting CAT in standalone offline mode...\n")
        os.environ["CAT_ALLOW_NO_AUTH"] = "1"
        return _launch_cat_terminal()

    return 0


_LOG_FILE = os.path.join(os.path.expanduser("~"), ".cct_startup.log")


def _log_startup_failure(what, detail):
    """Append one clearly-marked startup-failure record to
    ~/.cct_startup.log for debugging (requirement #8: never silent)."""
    try:
        import datetime
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{stamp}] {what}: {detail}\n")
    except Exception:
        pass


# Back-compat alias — earlier builds called this from main(); both names
# now refer to the same centralized bootstrap.
_launch = bootstrap

if __name__ == "__main__":
    sys.exit(main())