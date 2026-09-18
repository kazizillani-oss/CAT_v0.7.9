"""
CCT slash-command registry — single source of truth.

This used to be a module-level list inside app.py. It moved here in
v0.6.0 so calc_terminal/ui/palette.py's CommandPalette (the "/ opens an
integrated command palette inside the composer" piece of the v6.0
redesign brief) can list/filter the *exact* same commands the plain
print()/input() REPL supports, instead of hand-maintaining a second
copy that silently drifts out of sync every time a command is added.

app.py imports COMMANDS from here (see the top of app.py) and behaves
exactly as it did before this refactor — nothing about the REPL's
behavior changed, only where the list lives.
"""

COMMANDS = [
    ("/help", "Show help & shortcuts"),
    ("/calculator", "Quick scientific calculator"),
    ("/solve", "Universal formula calculator (39 formulas + custom)"),
    ("/formulas", "Browse the formula library"),
    ("/kinetics", "Chemical kinetics numericals"),
    ("/derive", "Real step-by-step calculus derivations (not examples)"),
    ("/electrochemistry", "Cell potential & Nernst numericals"),
    ("/atomsim", "Live Bohr atom & electron simulation"),
    ("/orbitals", "Live quantum orbital (electron cloud) simulation"),
    ("/orbitalgrid", "Export a reference chart of many hydrogen orbitals"),
    ("/bonding", "Chemical bonding density map (ELF-style) for a molecule"),
    ("/bloch", "Bloch sphere for a single qubit state (theta, phi in degrees)"),
    ("/permissions", "View or switch AI permission mode (ask/restricted/full)"),
    ("/workspace", "Workspace manager — detect, open, and manage project folders; browse generated files"),
    ("/graph", "Chemistry graphs — animated 2D + exported 2D/3D"),
    ("/game", "Element Quiz — learn chemistry by playing"),
    ("/history", "Review previously solved notebooks"),
    ("/settings", "Autosave, precision & preferences"),
    ("/shortcuts", "Full shortcut key reference"),
    ("/about", "About this terminal"),
    ("/random", "Solve a random numerical"),
    ("/upload", "Simulate solving from an image"),
    ("/voice", "Simulate voice input"),
    ("/sim3d", "[BETA] Real-time 3D Atomic Simulation"),
    ("/gpu3d", "[BETA] Real GPU-rendered 3D (atom/graph/scale) — opens in browser"),
    ("/mode", "Cycle or jump to an AI mode: Notebook, Research, Plan, Build, Debugger, or Agent"),
    ("/summarize", "Summarize the full conversation and generate a smart chat title"),
    ("/summary", "Alias for /summarize — full chat summary & title"),
    ("/notebook", "Switch to Notebook AI mode — chemistry/physics/math, daily use"),
    ("/research", "Deep research: multi-query web search + AI-synthesized summary"),
    ("/agent", "Switch to Agent AI mode — real tool use: solves/plots/simulates for you"),
    ("/build", "Switch to Build AI mode — code generation, debugging, architecture"),
    ("/plan", "Switch to Plan AI mode — roadmaps, brainstorming, prototypes"),
    ("/debug", "Switch to Debugger AI mode — focused troubleshooting of broken code"),
    ("/ai", "Alias for /notebook — CAT AI's original quick-chat persona"),
    ("/install", "Autonomous package manager — install real packages with permission"),
    ("/packages", "Installation dashboard — supported managers & remembered decisions"),
    ("/pipeline", "AI Execution Pipeline — Planner→Research→Build→Verify, fully visible"),
    ("/orchestrate", "Agent Orchestrator — Coordinator + specialist agent roster"),
    ("/devices", "Responsible device control — provider roster & approval-gated actions"),
    ("/ai-verify", "Test your AI provider connection & list models"),
    ("/memory", "What CAT remembers about you — facts, activity, topics"),
    ("/codepad", "Write/run code, or have CAT AI generate it (GitHub Light syntax)"),
    ("/edit", "Plain-text in-terminal editor — notes, todo lists, snippets"),
    ("/model", "Switch AI model for the current provider (live list, search & filters)"),
    ("/model search", "Search available models by name, family, or capability"),
    ("/model refresh", "Force-refresh the model list from the provider's API"),
    ("/free", "Show only free models for the current provider"),
    ("/latest", "Show the newest available models for the current provider"),
    ("/provider", "Switch AI provider (data-driven list from providers.json)"),
    ("/status", "Provider / model / source / last refresh status"),
    ("/refresh-models", "Force-refresh the model list from the selected provider"),
    ("/tokens", "Session token usage & estimated context remaining"),
    ("/theme", "Switch terminal theme — Tokyo Night (dark) or GitHub Light"),
    ("/websearch", "Live web search (no API key needed)"),
    ("/import", "Import a text file, image, or .zip for the AI/agent to read/see"),
    ("/pet", "Show the live mascot pet — walks, runs, or sleeps based on activity"),
    ("/react", "NEW Reaction simulator — balance equations + kinetics/equilibrium playback"),
    ("/export", "NEW Export solved notebooks to Markdown or PDF"),
    ("/tui", "NEW Real Textual dashboard — sidebar + scrolling history + status bar"),
    ("/composer", "Reopen the primary chat UI if you dropped to the fallback terminal"),
    ("/open", "Open a project folder as the IDE workspace (Explorer + Editor)"),
    ("/sidebar", "Toggle the Explorer sidebar"),
    ("/find", "Toggle find/replace in the active editor tab"),
    ("/preview", "Live Web Preview — open/close the embedded browser (Ctrl+Shift+P)"),
    ("/preview start", "Start the live preview server + embedded browser"),
    ("/preview stop", "Stop the live preview and return to the code editor"),
    ("/preview reload", "Reload the web preview page"),
    ("/preview fullscreen", "Expand/restore the right workspace pane (⿻)"),
    ("/preview status", "Show live server / browser / watcher state"),
    ("/browser", "CAT Browser — graphical browser (tabs, address bar, Fomoji)"),
    ("/browse", "Alias for /browser — open any URL or search"),
    ("/cat", "Open CAT Browser (Chromium / Qt WebEngine) — our own browser"),
    ("/browser open", "Open a URL in CAT Browser"),
    ("/browser search", "Search the web in CAT Browser (Google/DuckDuckGo)"),
    ("/signout", "Sign out of Fomoji — clear CAT session"),
    ("/logout", "Alias for /signout"),
    ("/todo", "NEW AI Todo Manager — manual + AI-detected tasks, per project"),
    ("/timeline", "NEW Session Timeline — searchable log of this run's activity"),
    ("/copycode", "Copy the most recent code block shown by the AI to your clipboard"),
    ("/vision", "CAT Vision — screen sharing + annotation + visual debugging"),
    ("/vision start", "Start a Vision capture session"),
    ("/vision stop", "Stop the current Vision session"),
    ("/vision pause", "Pause Vision capture"),
    ("/vision analyze", "Analyze current annotated region"),
    ("/vision screenshot", "Capture a single screenshot for analysis"),
    ("/vision clear", "Clear Vision session data"),
    ("/touch", "Toggle touch-friendly touchscreen laptop UI mode"),
    ("/cat doctor", "Comprehensive 19-dimension health check across runtime, providers & tools"),
    ("/cat self-test", "Automated self-test suite validating all core agent subsystems"),
    ("/cat verify", "Verify workspace edits, AST syntax, tests, and endpoints via Reality Engine"),
    ("/doctor", "Alias for /cat doctor — system diagnostic check"),
    ("/self-test", "Alias for /cat self-test — automated test suite"),
    ("/verify", "Alias for /cat verify — reality engine verification"),
    ("/mode create", "Create a custom AI mode by name"),
    ("/mode list", "List active built-in and custom AI modes"),
    ("/mode delete", "Delete a custom AI mode"),
    ("/checkpoint", "Create workspace snapshot or rollback recent changes"),
    ("/compute", "List compute fabric targets and hardware resources"),
    ("/fabric", "Alias for /compute — inspect compute fabric"),
    ("/clear", "Clear screen & return home"),
    ("/exit", "Quit Chemistry Calc Terminal"),
]

# Commands calc_terminal/ui/app.py's CCTApp runs natively, in-process,
# without leaving the Textual UI — small, quick, no blocking input()
# menus of their own. Every other command in COMMANDS above still
# works from inside the composer: CCTApp suspends the Textual screen
# (textual's real suspend/resume, not a fake), lets the existing
# fallback_cli.App.handle() run it exactly as it always has in a real
# terminal, and resumes the chat UI when that finishes — so nothing on
# this list is unsupported, this is just the set worth a native,
# no-suspend round trip.
NATIVE_UI_COMMANDS = {"/clear", "/theme", "/model", "/tokens", "/tui", "/composer",
                       "/history", "/memory", "/about", "/help", "/exit",
                       "/mode", "/notebook", "/agent", "/build", "/plan", "/ai",
                       "/research", "/debug",
                       "/open", "/sidebar", "/find", "/todo", "/timeline",
                       "/preview", "/browser", "/browse", "/cat",
                       "/vision", "/signout", "/logout", "/touch",
                       "/doctor", "/self-test", "/verify", "/checkpoint",
                       "/compute", "/fabric"}

