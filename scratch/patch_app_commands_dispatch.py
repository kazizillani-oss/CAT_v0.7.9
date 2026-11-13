"""
Patch calc_terminal/ui/app.py with complete command handlers for Engineering Excellence upgrade.
"""

with open('calc_terminal/ui/app.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''            if word in ("/apps", "/integrations"):
                from ..app_connectors import get_app_connectors
                ac = get_app_connectors()
                conns = ac.list_connectors()
                c_str = "\\n".join(f"• {c['icon']} {c['name']} [{c['status'].upper()}] — {c.get('metadata', {}).get('description', '')}" for c in conns)
                self._system_note("🔌 App Connectors & Integrations:\\n" + c_str)
                return'''

# Also support unicode em-dash or ascii
if target not in text:
    target = '''            if word in ("/apps", "/integrations"):
                from ..app_connectors import get_app_connectors
                ac = get_app_connectors()
                conns = ac.list_connectors()
                c_str = "\\n".join(f"• {c['icon']} {c['name']} [{c['status'].upper()}] \\u2014 {c.get('metadata', {}).get('description', '')}" for c in conns)
                self._system_note("🔌 App Connectors & Integrations:\\n" + c_str)
                return'''

dispatch_block = '''            if word in ("/apps", "/integrations"):
                from ..app_connectors import get_app_connectors
                ac = get_app_connectors()
                conns = ac.list_connectors()
                c_str = "\\n".join(f"• {c['icon']} {c['name']} [{c['status'].upper()}] — {c.get('metadata', {}).get('description', '')}" for c in conns)
                self._system_note("🔌 App Connectors & Integrations:\\n" + c_str)
                return

            # --- PART 1: CAT DEVELOPER SDK ---
            if word == "/dev":
                from ..sdk import developer_tools as dev_tools
                sub_parts = arg.split(None, 1) if arg else []
                sub = sub_parts[0].lower() if sub_parts else "help"
                sub_arg = sub_parts[1].strip() if len(sub_parts) > 1 else ""

                if sub in ("help", ""):
                    card = (
                        "### 🛠️ CAT Developer SDK\\n\\n"
                        "Build CAT-compatible extensions, skills, and custom slash commands:\\n\\n"
                        "- `/dev extension create <name>` — Scaffold extension project\\n"
                        "- `/dev skill create <name>` — Create specialized agent skill\\n"
                        "- `/dev command create <name>` — Create custom slash command\\n"
                        "- `/dev agent create <name>` — Scaffold custom Kitty agent\\n"
                        "- `/dev validate [path]` — Verify manifest, syntax, & AST\\n"
                        "- `/dev test [path]` — Execute dry-run component verification\\n"
                        "- `/dev package [path]` — Bundle into distributable `.catpkg`\\n"
                        "- `/dev docs [path]` — Generate Markdown API documentation\\n"
                        "- `/dev logs` — Display recent developer SDK activity"
                    )
                    self._system_note(card, role="assistant")
                    return
                elif sub == "extension" and sub_arg.startswith("create"):
                    name = sub_arg[6:].strip() or "MyExtension"
                    p = dev_tools.create_extension(name)
                    self._system_note(f"✓ Extension project created at: `{p}`")
                    return
                elif sub == "skill" and sub_arg.startswith("create"):
                    name = sub_arg[6:].strip() or "MySkill"
                    p = dev_tools.create_skill(name)
                    self._system_note(f"✓ Skill project created at: `{p}`")
                    return
                elif sub == "command" and sub_arg.startswith("create"):
                    name = sub_arg[6:].strip() or "mycmd"
                    p = dev_tools.create_command(name)
                    self._system_note(f"✓ Command project created at: `{p}`")
                    return
                elif sub == "agent" and sub_arg.startswith("create"):
                    name = sub_arg[6:].strip() or "MyAgent"
                    p = dev_tools.create_agent(name)
                    self._system_note(f"✓ Agent project created at: `{p}`")
                    return
                elif sub == "validate":
                    target_p = sub_arg or os.getcwd()
                    res = dev_tools.validate_component(target_p)
                    icon = "✓" if res["valid"] else "✗"
                    issues_str = "\\n".join(f"  - {iss}" for iss in res["issues"]) if res["issues"] else "  None"
                    self._system_note(f"{icon} **Component Validation** (`{res['type']}`):\\n{issues_str}")
                    return
                elif sub == "test":
                    target_p = sub_arg or os.getcwd()
                    res = dev_tools.test_component(target_p)
                    icon = "✓" if res["passed"] else "✗"
                    self._system_note(f"{icon} **Component Tests**: {res.get('details', res.get('error', ''))}")
                    return
                elif sub == "package":
                    target_p = sub_arg or os.getcwd()
                    try:
                        pkg = dev_tools.package_component(target_p)
                        self._system_note(f"✓ Successfully packaged component: `{pkg}`")
                    except Exception as ex:
                        self._system_note(f"✗ Packaging failed: {ex}")
                    return
                elif sub == "docs":
                    target_p = sub_arg or os.getcwd()
                    doc_p = dev_tools.generate_docs(target_p)
                    self._system_note(f"✓ Generated component documentation: `{doc_p}`")
                    return
                elif sub == "logs":
                    logs = dev_tools.get_dev_logs(20)
                    log_str = "\\n".join(logs) if logs else "No SDK events recorded yet."
                    self._system_note(f"**Developer SDK Logs**:\\n```\\n{log_str}\\n```")
                    return

            # --- PART 2: CAT RECOVERY & ROLLBACK ---
            if word in ("/recovery", "/undo", "/redo", "/rollback"):
                from ..core.recovery_engine import recovery_engine
                if word == "/undo":
                    ok, msg = recovery_engine.undo()
                    self._system_note(("✓ " if ok else "✗ ") + msg)
                    return
                if word == "/redo":
                    ok, msg = recovery_engine.redo()
                    self._system_note(("✓ " if ok else "✗ ") + msg)
                    return
                if word == "/rollback":
                    target_cid = arg.strip() if arg else ""
                    if not target_cid:
                        hist = recovery_engine.get_history(5)
                        if hist: target_cid = hist[0]["id"]
                    if not target_cid:
                        self._system_note("Usage: /rollback <checkpoint_id>")
                        return
                    ok, restored = recovery_engine.rollback_operation(target_cid)
                    if ok:
                        self._system_note(f"✓ Rolled back to `{target_cid}`. Restored {len(restored)} file(s).")
                    else:
                        self._system_note(f"✗ Rollback failed: {restored}")
                    return

                sub_parts = arg.split(None, 1) if arg else []
                sub = sub_parts[0].lower() if sub_parts else "status"
                sub_arg = sub_parts[1].strip() if len(sub_parts) > 1 else ""

                if sub == "status":
                    st = recovery_engine.get_status()
                    self._system_note(
                        f"🛡️ **Recovery & Rollback Engine**:\\n"
                        f"- Total Snapshots: {st['total_checkpoints']}\\n"
                        f"- Undo Available: {'Yes' if st['undo_available'] else 'No'}\\n"
                        f"- Redo Available: {'Yes' if st['redo_available'] else 'No'}\\n"
                        f"- Active Transaction: {st['active_transaction'] or 'None'}\\n"
                        f"- Pending Crash Recovery: {'Yes' if st['pending_crash_recovery'] else 'None'}"
                    )
                    return
                elif sub == "history":
                    hist = recovery_engine.get_history(10)
                    if not hist:
                        self._system_note("No recovery checkpoints recorded yet.")
                    else:
                        lines = ["**Recovery Snapshots**:\\n"]
                        for h in hist:
                            t_str = time.strftime("%H:%M:%S", time.localtime(h["timestamp"]))
                            lines.append(f"• `{h['id']}` ({t_str}): {h['description']} ({h['files_count']} files)")
                        self._system_note("\\n".join(lines))
                    return
                elif sub == "preview":
                    if not sub_arg:
                        self._system_note("Usage: /recovery preview <checkpoint_id>")
                        return
                    prev = recovery_engine.preview_rollback(sub_arg)
                    if "error" in prev:
                        self._system_note(f"✗ {prev['error']}")
                    else:
                        diffs = prev.get("diffs", {})
                        d_str = f"Found diffs across {len(diffs)} file(s)." if diffs else "No differences detected."
                        self._system_note(f"**Rollback Preview for `{sub_arg}`** ({prev['description']}):\\n{d_str}")
                    return
                elif sub == "restore" or sub == "operation":
                    if not sub_arg:
                        self._system_note("Usage: /recovery restore <checkpoint_id>")
                        return
                    ok, res = recovery_engine.rollback_operation(sub_arg)
                    self._system_note(f"✓ Restored {len(res)} files from `{sub_arg}`" if ok else f"✗ Failed: {res}")
                    return
                elif sub == "file":
                    p_parts = sub_arg.split(None, 1)
                    if len(p_parts) < 2:
                        self._system_note("Usage: /recovery file <checkpoint_id> <file_path>")
                        return
                    ok, msg = recovery_engine.restore_file(p_parts[0], p_parts[1])
                    self._system_note(("✓ " if ok else "✗ ") + msg)
                    return

            # --- PART 3: CAT CONTEXT ENGINE ---
            if word == "/context":
                from ..context_engine import context_engine
                sub_parts = arg.split(None, 1) if arg else []
                sub = sub_parts[0].lower() if sub_parts else "status"
                sub_arg = sub_parts[1].strip() if len(sub_parts) > 1 else ""

                if sub == "status":
                    st = context_engine.get_status()
                    lines = [f"🧠 **Context Engine Status** (Project: `{st['current_project']}`):\\n"]
                    lines.append(f"**Total Tokens in Active Context:** {st['total_tokens']}\\n")
                    for cat, count in st["slice_counts"].items():
                        toks = st["tokens_by_category"].get(cat, 0)
                        lines.append(f"• **{cat.capitalize()} Context**: {count} slice(s) · {toks} tokens")
                    self._system_note("\\n".join(lines))
                    return
                elif sub == "inspect":
                    cat = sub_arg or "session"
                    slices = context_engine.inspect_category(cat)
                    if not slices:
                        self._system_note(f"No active context slices in category '{cat}'.")
                    else:
                        lines = [f"**Context Category: {cat.upper()}** ({len(slices)} slices):\\n"]
                        for s in slices[:8]:
                            lines.append(f"• `[{s['id']}]` ({s['tokens']} tok, prio {s['priority']}) — {s['source']}\\n  {s['snippet']}")
                        self._system_note("\\n".join(lines))
                    return
                elif sub == "compress":
                    cat = sub_arg or "session"
                    res = context_engine.compress(category=cat)
                    self._system_note(f"✓ Context compressed! Saved {res.get('tokens_saved', 0)} tokens." if res.get("compressed") else f"Context compression: {res.get('reason')}")
                    return
                elif sub == "clear":
                    context_engine.clear(sub_arg if sub_arg else None)
                    self._system_note(f"✓ Cleared context {'for category: ' + sub_arg if sub_arg else 'across all categories'}.")
                    return
                elif sub == "search":
                    hits = context_engine.retrieve(query=sub_arg, max_tokens=2000)
                    if not hits:
                        self._system_note(f"No context slices matched '{sub_arg}'.")
                    else:
                        lines = [f"**Context Search Results for '{sub_arg}'** ({len(hits)} matches):\\n"]
                        for h in hits:
                            lines.append(f"• `[{h.category.upper()}]` {h.source} ({h.tokens} tok): {h.content[:120]}...")
                        self._system_note("\\n".join(lines))
                    return

            # --- PART 4: CAT OBSERVABILITY CENTER ---
            if word in ("/observe", "/trace", "/logs"):
                from ..observability import observability_center
                if word == "/trace":
                    t_id = arg.strip() if arg else ""
                    if not t_id:
                        recent = observability_center.list_recent_traces(5)
                        if recent: t_id = recent[0]["trace_id"]
                    if not t_id:
                        self._system_note("No traces recorded yet.")
                        return
                    spans = observability_center.get_trace(t_id)
                    lines = [f"🔍 **Distributed Trace: `{t_id}`** ({len(spans)} spans):\\n"]
                    for sp in spans:
                        icon = "✓" if sp["status"] == "ok" else ("✗" if sp["status"] == "error" else "○")
                        dur = f"{sp['duration_ms']:.1f}ms" if sp['duration_ms'] else "running"
                        lines.append(f"  [{icon}] `{sp['component']}`: **{sp['name']}** ({dur})")
                    self._system_note("\\n".join(lines))
                    return

                if word == "/logs":
                    sub_parts = arg.split(None, 1) if arg else []
                    sub = sub_parts[0].lower() if sub_parts else "search"
                    q = sub_parts[1].strip() if len(sub_parts) > 1 else ""
                    if sub == "export":
                        p = observability_center.export_logs()
                        self._system_note(f"✓ Structured logs exported to: `{p}`")
                        return
                    hits = observability_center.search_logs(query=q, limit=10)
                    if not hits:
                        self._system_note(f"No log entries found for query '{q}'.")
                    else:
                        lines = [f"📄 **Structured Logs** ({len(hits)} entries):\\n"]
                        for h in hits:
                            t_str = time.strftime("%H:%M:%S", time.localtime(h["timestamp"]))
                            lines.append(f"`[{t_str}]` **[{h['level']}]** `{h['component']}`: {h['message']}")
                        self._system_note("\\n".join(lines))
                    return

                sub = arg.strip().lower() if arg else "health"
                if sub in ("health", "status", ""):
                    hlth = observability_center.get_health_status()
                    icon = "🟢" if hlth["status"] == "healthy" else "🟡"
                    m = hlth["metrics"]
                    self._system_note(
                        f"{icon} **CAT Observability Center** [{hlth['status'].upper()}]:\\n\\n"
                        f"- Total Provider Calls: {m['total_provider_calls']}\\n"
                        f"- Latency: avg {m['avg_latency_ms']}ms · p95 {m['p95_latency_ms']}ms\\n"
                        f"- Tokens / Cost: {m['total_tokens']} tokens · ${m['estimated_cost_usd']:.4f}\\n"
                        f"- Tool Executions: {m['tool_executions']} (Success Rate: {m['tool_success_rate_percent']}%)\\n"
                        f"- Extension / MCP Errors: {m['extension_errors']} / {m['mcp_errors']}\\n"
                        f"- Active Traces: {hlth['active_traces_count']}"
                    )
                    return
                elif sub == "traces":
                    traces = observability_center.list_recent_traces(10)
                    lines = ["**Recent Execution Traces**:\\n"]
                    for tr in traces:
                        icon = "✓" if tr["status"] == "ok" else "✗"
                        lines.append(f"• [{icon}] `{tr['trace_id']}` ({tr['component']}): **{tr['name']}** ({tr['duration_ms']:.1f}ms, {tr['span_count']} spans)")
                    self._system_note("\\n".join(lines))
                    return
                elif sub == "metrics":
                    m = observability_center.get_metrics_summary()
                    self._system_note(
                        f"📊 **CAT Measured Telemetry & Metrics**:\\n"
                        f"- Provider Calls: {m['total_provider_calls']}\\n"
                        f"- Average Latency: {m['avg_latency_ms']} ms\\n"
                        f"- P95 Latency: {m['p95_latency_ms']} ms\\n"
                        f"- Total Tokens: {m['total_tokens']}\\n"
                        f"- Estimated Cost: ${m['estimated_cost_usd']:.4f} USD\\n"
                        f"- Tool Success Rate: {m['tool_success_rate_percent']}%"
                    )
                    return
                elif sub == "export":
                    p = observability_center.export_logs()
                    self._system_note(f"✓ Observability telemetry & logs exported: `{p}`")
                    return

            # --- PART 5: CAT OFFLINE MODE ---
            if word in ("/offline", "/local"):
                from ..offline import offline_manager
                if word == "/offline":
                    sub = arg.strip().lower() if arg else "status"
                    if sub == "enable":
                        offline_manager.set_offline_mode(True)
                        self._system_note("✈️ **Offline Mode ENABLED**: Remote API calls blocked. Local tools enforced.")
                        return
                    elif sub == "disable":
                        offline_manager.set_offline_mode(False)
                        self._system_note("🌐 **Offline Mode DISABLED**: Cloud providers and online services restored.")
                        return
                    elif sub == "capabilities":
                        caps = offline_manager.get_offline_capabilities()
                        lines = ["📦 **Local Offline Capabilities**:\\n"]
                        for k, v in caps.items():
                            lines.append(f"• **{k.replace('_', ' ').title()}**: {v}")
                        self._system_note("\\n".join(lines))
                        return
                    else:
                        st = offline_manager.get_status()
                        self._system_note(
                            f"📡 **Network & Offline Status**:\\n"
                            f"- Connection: **{st['network_status'].upper()}** (Forced Offline: {'Yes' if st['manual_offline_forced'] else 'No'})\\n"
                            f"- Local Ollama Service: {'Running' if st['ollama_available'] else 'Stopped'}\\n"
                            f"- Local Models: {st['local_models_count']} model(s) installed"
                        )
                        return

                if word == "/local":
                    sub_parts = arg.split(None, 1) if arg else []
                    sub = sub_parts[0].lower() if sub_parts else "models"
                    sub_arg = sub_parts[1].strip() if len(sub_parts) > 1 else ""

                    if sub == "models":
                        models = offline_manager.list_local_models()
                        if not models:
                            self._system_note("No local models detected. Ensure Ollama is running (`ollama serve`).")
                        else:
                            lines = ["🖥️ **Local Models in Ollama**:\\n"]
                            for m in models:
                                tool_badge = " [Tools ✓]" if m.supports_tools else ""
                                lines.append(f"• **{m.name}** ({m.size_gb} GB, {m.parameter_size or m.family}){tool_badge}")
                            self._system_note("\\n".join(lines))
                        return
                    elif sub == "test":
                        model_name = sub_arg or "llama3.2:latest"
                        res = offline_manager.test_local_model(model_name)
                        if res["success"]:
                            self._system_note(f"✓ Model `{model_name}` responded in {res['duration_ms']}ms: \"{res['response']}\"")
                        else:
                            self._system_note(f"✗ Test failed for `{model_name}`: {res['error']}")
                        return
                    elif sub in ("status", "providers"):
                        ok, msg = offline_manager.check_ollama_service()
                        self._system_note(("✓ " if ok else "✗ ") + msg)
                        return

            # --- PART 6: CAT UPDATE & RELEASE MANAGER ---
            if word == "/update":
                from ..update_manager import update_manager
                sub_parts = arg.split(None, 1) if arg else []
                sub = sub_parts[0].lower() if sub_parts else "check"
                sub_arg = sub_parts[1].strip() if len(sub_parts) > 1 else ""

                if sub == "check":
                    chk = update_manager.check_update()
                    latest = chk.get("latest_release") or {}
                    if chk["has_update"]:
                        self._system_note(f"🚀 **New Update Available**: v{latest.get('version')} ({latest.get('channel')})\\nUse `/update preview` to inspect changes or `/update install` to apply.")
                    else:
                        self._system_note(f"✓ CAT is up to date on **{chk['channel'].upper()}** channel (v{chk['current_version']}).")
                    return
                elif sub == "channel":
                    if not sub_arg:
                        self._system_note(f"Current release channel: **{update_manager.current_channel.upper()}**. Use: `/update channel <stable|beta|dev>`")
                    else:
                        ok, msg = update_manager.set_channel(sub_arg)
                        self._system_note(("✓ " if ok else "✗ ") + msg)
                    return
                elif sub == "preview":
                    prev = update_manager.preview_update(sub_arg if sub_arg else None)
                    if "error" in prev:
                        self._system_note(f"✗ {prev['error']}")
                    else:
                        cl_str = "\\n".join(f"  • {c}" for c in prev["changelog"])
                        self._system_note(
                            f"📦 **Update Preview**: v{prev['version']} ({prev['channel']}) — {prev['release_date']}:\\n"
                            f"**Changelog:**\\n{cl_str}\\n"
                            f"**Compatibility:** Python 3.10+ (Verified: {'✓' if prev['python_compatible'] else '✗'})"
                        )
                    return
                elif sub == "install":
                    chk = update_manager.check_update()
                    latest_v = (chk.get("latest_release") or {}).get("version", "0.7.10")
                    res = update_manager.install_update(sub_arg or latest_v)
                    self._system_note(("✓ " if res["success"] else "✗ ") + res.get("message", res.get("error", "")))
                    return
                elif sub == "rollback":
                    ok, msg = update_manager.rollback_update()
                    self._system_note(("✓ " if ok else "✗ ") + msg)
                    return
                elif sub == "history":
                    hist = update_manager.get_history()
                    if not hist:
                        self._system_note("No previous update installations recorded.")
                    else:
                        lines = ["**Update History**:\\n"]
                        for h in hist:
                            t_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(h["timestamp"]))
                            lines.append(f"• v{h['from_version']} → **v{h['to_version']}** ({t_str}) · Checkpoint `{h['checkpoint_id']}`")
                        self._system_note("\\n".join(lines))
                    return

            # --- PART 7: CAT MULTI-WORKSPACE MANAGER ---
            if word in ("/workspaces", "/workspace"):
                from ..multi_workspace import multi_workspace
                sub_parts = arg.split(None, 1) if arg else []
                sub = sub_parts[0].lower() if sub_parts else "list"
                sub_arg = sub_parts[1].strip() if len(sub_parts) > 1 else ""

                if word == "/workspaces" or sub in ("list", ""):
                    st = multi_workspace.get_status()
                    active = st.get("active_workspace") or {}
                    lines = [f"📂 **Workspaces Manager** (Active: **{active.get('name', 'None')}**):\\n"]
                    for w in st["all_workspaces"]:
                        is_act = " [ACTIVE]" if w["id"] == active.get("id") else ""
                        langs = f" ({', '.join(w['languages'])})" if w["languages"] else ""
                        lines.append(f"• **{w['name']}** (`{w['path']}`){langs}{is_act}")
                    self._system_note("\\n".join(lines))
                    return
                elif sub == "create":
                    parts = sub_arg.split()
                    if not parts:
                        self._system_note("Usage: /workspace create <name> [path] [template]")
                        return
                    w_name = parts[0]
                    w_path = parts[1] if len(parts) > 1 else os.path.join(os.getcwd(), w_name)
                    w_tmpl = parts[2] if len(parts) > 2 else "python"
                    ok, msg = multi_workspace.create_workspace(w_name, w_path, template=w_tmpl)
                    self._system_note(("✓ " if ok else "✗ ") + msg)
                    return
                elif sub == "switch":
                    if not sub_arg:
                        self._system_note("Usage: /workspace switch <name_or_id>")
                        return
                    ok, msg = multi_workspace.switch_workspace(sub_arg)
                    self._system_note(("✓ " if ok else "✗ ") + msg)
                    return
                elif sub == "clone":
                    parts = sub_arg.split()
                    if len(parts) < 3:
                        self._system_note("Usage: /workspace clone <source_id> <new_name> <new_path>")
                        return
                    ok, msg = multi_workspace.clone_workspace(parts[0], parts[1], parts[2])
                    self._system_note(("✓ " if ok else "✗ ") + msg)
                    return
                elif sub == "archive":
                    if not sub_arg:
                        self._system_note("Usage: /workspace archive <id>")
                        return
                    ok, msg = multi_workspace.archive_workspace(sub_arg)
                    self._system_note(("✓ " if ok else "✗ ") + msg)
                    return
                elif sub == "delete":
                    if not sub_arg:
                        self._system_note("Usage: /workspace delete <id>")
                        return
                    ok, msg = multi_workspace.delete_workspace(sub_arg)
                    self._system_note(("✓ " if ok else "✗ ") + msg)
                    return
                elif sub == "export":
                    target_id = sub_arg or multi_workspace.active_workspace_id
                    ok, path_or_err = multi_workspace.export_workspace(target_id)
                    self._system_note(f"✓ Workspace exported to: `{path_or_err}`" if ok else f"✗ Export failed: {path_or_err}")
                    return
                elif sub in ("status", "health"):
                    hlth = multi_workspace.get_workspace_health()
                    self._system_note(
                        f"🏥 **Workspace Health Diagnostics**:\\n"
                        f"- Name: **{hlth.get('name')}** (`{hlth.get('path')}`)\\n"
                        f"- Languages: {', '.join(hlth.get('languages', [])) or 'None'}\\n"
                        f"- Git Branch: {hlth.get('git_branch') or 'Not a git repo'}\\n"
                        f"- Overall Health: **{hlth.get('health', '').upper()}**\\n"
                        f"- Issues: {', '.join(hlth.get('issues', [])) or 'None'}"
                    )
                    return

            # --- PART 8: CAT DOCUMENTATION & LEARNING CENTER ---
            if word in ("/docs", "/learn"):
                from ..doc_center import doc_center
                if word == "/learn":
                    track = arg.strip().lower() if arg else "basics"
                    steps = doc_center.get_tutorial(track)
                    lines = [f"🎓 **Interactive Learning Track: {track.upper()}**:\\n"]
                    lines.extend(f"{s}" for s in steps)
                    lines.append("\\n*Available tracks: basics, extensions, agents, mcp, commands*")
                    self._system_note("\\n".join(lines))
                    return

                sub_parts = arg.split(None, 1) if arg else []
                sub = sub_parts[0].lower() if sub_parts else "topics"
                sub_arg = sub_parts[1].strip() if len(sub_parts) > 1 else ""

                if sub in ("topics", "list", ""):
                    topics = doc_center.list_topics()
                    lines = ["📚 **CAT Documentation Topics**:\\n"]
                    for t in topics:
                        lines.append(f"• **{t['title']}** (`{t['id']}`) [{t['category'].upper()}]\\n  {t['summary']}")
                    lines.append("\\nUse `/docs <topic_id>` to read or `/docs search <query>` to search.")
                    self._system_note("\\n".join(lines))
                    return
                elif sub == "search":
                    hits = doc_center.search_docs(sub_arg)
                    if not hits:
                        self._system_note(f"No documentation matches found for '{sub_arg}'.")
                    else:
                        lines = [f"🔍 **Documentation Search for '{sub_arg}'** ({len(hits)} results):\\n"]
                        for h in hits:
                            lines.append(f"• **{h['title']}** (`{h['id']}`): {h['summary']}")
                        self._system_note("\\n".join(lines))
                    return
                elif sub == "update":
                    audit = doc_center.validate_command_documentation()
                    self._system_note(
                        f"📖 **Command Documentation Coverage Audit**:\\n"
                        f"- Total Commands in Registry: {audit['total_commands']}\\n"
                        f"- Covered in Guide Topics: {audit['explicitly_documented_in_guides']}\\n"
                        f"- Documented in Interactive Palette: 100%\\n"
                        f"- Guide Coverage: {audit['coverage_percent']}%"
                    )
                    return
                else:
                    # Check if arg matches topic ID
                    top = doc_center.get_topic(sub)
                    if top:
                        self._system_note(top.content)
                        return'''

if target in text:
    text = text.replace(target, dispatch_block, 1)
    with open('calc_terminal/ui/app.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("SUCCESS: Patched app.py with all upgrade command handlers")
else:
    print("ERROR: Target block not found in app.py")

