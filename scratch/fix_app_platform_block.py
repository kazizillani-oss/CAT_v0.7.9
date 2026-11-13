with open('calc_terminal/ui/app.py', 'r', encoding='utf-8') as f:
    text = f.read()

start_marker = "# --- CAT Platform Expansion: Critical & High-Priority Systems ---"
end_marker = "# Known classic terminal commands can suspend to terminal"

idx1 = text.find(start_marker)
idx2 = text.find(end_marker)

assert idx1 != -1, "start_marker not found"
assert idx2 != -1, "end_marker not found"

clean_block = '''# --- CAT Platform Expansion: Critical & High-Priority Systems ---
            if word == "/index":
                from ..code_intel import get_code_intel
                from .. import workspace as _ws
                import os
                root = _ws.root_dir() if hasattr(_ws, 'root_dir') else os.getcwd()
                idx = get_code_intel().index_workspace(root)
                cnt_files = idx.get('total_files', 0)
                cnt_lines = idx.get('total_lines', 0)
                cnt_syms = len(idx.get('symbols', {}))
                self._system_note(f"✓ Indexed workspace: {cnt_files} files, {cnt_lines:,} lines, {cnt_syms} symbols.")
                return

            if word == "/project":
                from ..code_intel import get_code_intel
                from .. import workspace as _ws
                import os
                root = _ws.root_dir() if hasattr(_ws, 'root_dir') else os.getcwd()
                summ = get_code_intel().get_project_summary(root)
                ext_str = ", ".join(f"{k}: {v}" for k, v in summ.get("file_types", {}).items())
                msg = "📊 Project Architecture Summary:\\n• Files: " + str(summ['total_files']) + " (" + ext_str + ")\\n• Total Lines: " + f"{summ['total_lines']:,}" + "\\n• Classes: " + str(summ['total_classes']) + " | Functions: " + str(summ['total_functions'])
                self._system_note(msg)
                return

            if word == "/code":
                from ..code_intel import get_code_intel
                from .. import workspace as _ws
                import os
                root = _ws.root_dir() if hasattr(_ws, 'root_dir') else os.getcwd()
                intel = get_code_intel()
                sub = arg.split()[0].lower() if arg else "help"
                rest = " ".join(arg.split()[1:]) if arg else ""
                if sub == "search" and rest:
                    results = intel.search_code(rest, root, max_results=10)
                    if results:
                        rows = "\\n".join(f"• {r['file']}:{r['line']} — {r['text']}" for r in results)
                        msg = f"🔍 Code Search Results for '{rest}':\\n" + rows
                    else:
                        msg = f"No code occurrences found for '{rest}'."
                    self._system_note(msg)
                elif sub == "dead":
                    dead = intel.detect_dead_code(root)
                    cands = dead.get("candidates", [])
                    if cands:
                        rows = "\\n".join(f"• {c['function']}() in {c['file']}:{c['line']}" for c in cands[:10])
                        msg = f"⚠️ Potentially Unused Code ({len(cands)} candidates):\\n" + rows
                    else:
                        msg = "✓ No obvious unused functions detected."
                    self._system_note(msg)
                else:
                    self._system_note("Usage: /code search <pattern> | /code dead")
                return

            if word == "/security":
                sub = arg.strip().lower() if arg else ""
                if sub in ("scan", "secrets"):
                    from ..security_center import get_security_center
                    from .. import workspace as _ws
                    import os
                    root = _ws.root_dir() if hasattr(_ws, 'root_dir') else os.getcwd()
                    sec = get_security_center().scan_secrets(root)
                    findings = sec.get("findings", [])
                    if findings:
                        rows = "\\n".join(f"• [{f['severity']}] {f['type']} at {f['file']}:{f['line']} ({f['masked']})" for f in findings[:8])
                        msg = f"⚠️ Detected {len(findings)} Potential Secrets:\\n" + rows
                    else:
                        msg = f"✓ Scanned {sec['scanned_files']} files: No hardcoded secrets detected."
                    self._system_note(msg)
                else:
                    from .platform_screens import SecurityCenterScreen
                    self.push_screen(SecurityCenterScreen())
                return

            if word == "/dependency" and arg.startswith("audit"):
                from ..security_center import get_security_center
                from .. import workspace as _ws
                import os
                root = _ws.root_dir() if hasattr(_ws, 'root_dir') else os.getcwd()
                audit = get_security_center().audit_dependencies(root)
                vulns = audit.get("vulnerabilities", [])
                if vulns:
                    rows = "\\n".join(f"• {v['package']} ({v['cve']})" for v in vulns)
                    msg = f"⚠️ Dependency Vulnerabilities Found ({len(vulns)}):\\n" + rows
                else:
                    msg = f"✓ Checked {audit['packages_checked']} packages: No known CVEs found in requirements."
                self._system_note(msg)
                return

            if word in ("/deploy", "/release"):
                if not arg:
                    from .platform_screens import DeploymentCenterScreen
                    self.push_screen(DeploymentCenterScreen())
                else:
                    from ..deployment_center import get_deployment_center
                    from .. import workspace as _ws
                    import os
                    root = _ws.root_dir() if hasattr(_ws, 'root_dir') else os.getcwd()
                    target = arg.split()[0].lower()
                    dry = "dry" in arg.lower()
                    rec = get_deployment_center().deploy(target, root, dry_run=dry)
                    u = rec.url or 'local'
                    self._system_note(f"🚀 Deploy [{rec.target.upper()}]: {rec.status} ({rec.duration_ms}ms)\\nURL: {u}\\n{rec.log_summary}")
                return

            if word == "/db":
                if not arg:
                    from .platform_screens import DatabaseStudioScreen
                    self.push_screen(DatabaseStudioScreen())
                else:
                    from ..db_studio import get_db_studio
                    studio = get_db_studio()
                    sub = arg.split()[0].lower()
                    rest = " ".join(arg.split()[1:])
                    if sub == "connect":
                        res = studio.connect_sqlite(rest or ":memory:")
                        self._system_note("🗄️ " + str(res.get('message', res.get('error'))))
                    elif sub == "tables":
                        tables = studio.get_tables()
                        t_str = "\\n".join(f"• {t['name']} ({t['row_count']} rows)" for t in tables) if tables else "No tables found."
                        self._system_note("🗄️ Database Tables:\\n" + t_str)
                    elif sub == "schema" and rest:
                        schema = studio.get_schema(rest)
                        s_str = "\\n".join(f"• {c['name']} ({c['type']})" for c in schema) if schema else f"Table '{rest}' not found."
                        self._system_note(f"🗄️ Schema for '{rest}':\\n" + s_str)
                    elif sub == "query" and rest:
                        res = studio.execute_query(rest)
                        if res.get("success"):
                            cnt = res.get("row_count", res.get("rows_affected", 0))
                            dur = res.get('duration_ms', 0)
                            self._system_note(f"✓ Query executed successfully: {cnt} records in {dur}ms.")
                        else:
                            self._system_note(f"❌ Query error: {res.get('error')}")
                    elif sub == "export" and rest:
                        csv_data = studio.export_table_csv(rest)
                        self._system_note(f"✓ Exported table '{rest}' ({len(csv_data)} bytes CSV).")
                    else:
                        self._system_note("Usage: /db [connect <path> | tables | schema <table> | query <sql> | export <table>]")
                return

            if word == "/ai":
                sub = arg.split()[0].lower() if arg else ""
                rest = " ".join(arg.split()[1:])
                if sub in ("cost", "usage"):
                    from .platform_screens import AICostManagerScreen
                    self.push_screen(AICostManagerScreen())
                    return
                elif sub == "budget":
                    from ..ai_cost_manager import get_ai_cost_manager
                    try:
                        val = float(rest) if rest else 10.0
                        limit = get_ai_cost_manager().set_budget(val)
                        self._system_note(f"💰 AI Budget limit set to ${limit:.2f}")
                    except Exception as e:
                        self._system_note(f"Usage: /ai budget <amount_in_usd> ({e})")
                    return
                elif sub in ("benchmark", "evaluate"):
                    from ..ai_eval import get_ai_eval
                    self._system_note("⏳ Running AI Benchmark suite...")
                    res = get_ai_eval().run_benchmark("current_model")
                    self._system_note(f"🏆 AI Benchmark Complete: Score {res.score_percent}% | Avg Latency: {res.avg_latency_ms}ms | Throughput: {res.tokens_per_sec} tok/s")
                    return

            if word == "/automation":
                from ..automation_engine import get_automation_engine
                auto = get_automation_engine()
                sub = arg.split()[0].lower() if arg else "list"
                rest = " ".join(arg.split()[1:])
                if sub == "list":
                    jobs = auto.list_jobs()
                    j_str = "\\n".join(f"• [{j['id']}] {j['name']} ({j['trigger_type']} -> {j['action_payload']}) [{j['last_status']}]" for j in jobs)
                    self._system_note("⚙️ Active Automations:\\n" + j_str)
                elif sub == "run" and rest:
                    res = auto.run_job_now(rest)
                    dur = res.get('duration_ms', 0)
                    self._system_note(f"✓ Job executed: {res.get('name')} in {dur}ms")
                else:
                    self._system_note("Usage: /automation [list | run <job_id>]")
                return

            if word == "/agent" and arg.startswith("delegate"):
                parts_del = arg.split()
                target_agent = parts_del[1] if len(parts_del) > 1 else "Aria"
                task_desc = " ".join(parts_del[2:]) if len(parts_del) > 2 else "Analyze code"
                from ..automation_engine import get_automation_engine
                res = get_automation_engine().delegate_task(task_desc, target_agent)
                self._system_note("✨ " + str(res.get('summary')))
                return

            if word == "/workflow":
                from ..workflow_builder import get_workflow_builder
                wfb = get_workflow_builder()
                sub = arg.split()[0].lower() if arg else "list"
                rest = " ".join(arg.split()[1:])
                if sub == "list":
                    wfs = wfb.list_workflows()
                    w_str = "\\n".join(f"• [{w['id']}] {w['name']} — {w['description']} ({len(w['nodes'])} steps)" for w in wfs)
                    self._system_note("🔄 Workflow Pipelines:\\n" + w_str)
                elif sub == "run" and rest:
                    res = wfb.run_workflow(rest)
                    if res.get("success"):
                        dur = res.get('total_duration_ms', 0)
                        cnt = len(res.get('steps', {}))
                        self._system_note(f"✓ Workflow '{res.get('name')}' completed in {dur}ms ({cnt} steps).")
                    else:
                        self._system_note(f"❌ Workflow failed: {res.get('error')}")
                else:
                    self._system_note("Usage: /workflow [list | run <workflow_id>]")
                return

            if word == "/github":
                from ..github_studio import get_github_studio
                from .. import workspace as _ws
                import os
                root = _ws.root_dir() if hasattr(_ws, 'root_dir') else os.getcwd()
                gh = get_github_studio()
                sub = arg.split()[0].lower() if arg else "repo"
                if sub == "pr":
                    prs = gh.list_pull_requests(root)
                    pr_str = "\\n".join(f"• #{p.get('number')} {p.get('title')} ({p.get('headRefName')})" for p in prs) if prs else "No open PRs."
                    self._system_note("🐙 GitHub Pull Requests:\\n" + pr_str)
                elif sub == "issues":
                    issues = gh.list_issues(root)
                    i_str = "\\n".join(f"• #{i.get('number')} {i.get('title')}" for i in issues)
                    self._system_note("🐙 GitHub Issues:\\n" + i_str)
                elif sub == "sync":
                    res = gh.sync_repo(root)
                    self._system_note(f"🐙 Git Sync: {res.get('message')}")
                else:
                    info = gh.get_repo_info(root)
                    slug = info.get('repo_slug') or 'Local Git'
                    r_url = info.get('remote_url') or 'None'
                    self._system_note(f"🐙 GitHub Repo: {slug}\\n• Branch: {info['branch']} | Modified Files: {info['modified_files_count']}\\n• Remote: {r_url}")
                return

            if word in ("/cloud", "/remote", "/docker"):
                if word == "/docker" or (arg and "docker" in arg):
                    from ..cloud_workspace import get_cloud_workspace
                    doc = get_cloud_workspace().list_docker_containers()
                    if doc.get("available"):
                        c_str = "\\n".join(f"• {c.get('Names')} ({c.get('Image')}) - {c.get('Status')}" for c in doc.get("containers", [])) if doc.get("containers") else "No running containers."
                        self._system_note("🐳 Docker Containers:\\n" + c_str)
                    else:
                        self._system_note(f"🐳 Docker Status: {doc.get('error')}")
                else:
                    from ..cloud_workspace import get_cloud_workspace
                    profs = get_cloud_workspace().list_profiles()
                    p_str = "\\n".join(f"• [{p['id']}] {p['name']} ({p['user']}@{p['host']}:{p['remote_path']})" for p in profs)
                    self._system_note("☁️ Cloud Workspaces:\\n" + p_str)
                return

            if word in ("/knowledge", "/docs"):
                from ..knowledge_center import get_knowledge_center
                from .. import workspace as _ws
                import os
                root = _ws.root_dir() if hasattr(_ws, 'root_dir') else os.getcwd()
                kc = get_knowledge_center()
                if not arg:
                    colls = kc.list_collections()
                    self._system_note(f"📚 Knowledge Collections: {', '.join(colls)}\\nUse `/docs <query>` to search with line-numbered citations.")
                else:
                    kc.index_workspace_docs(root, max_files=50)
                    hits = kc.search(arg, limit=5)
                    if hits:
                        h_str = "\\n".join(f"• [{h['collection'].upper()}] {h['title']} ({h['source_file']}:{h['line_number']})\\n  {h['content'][:140]}..." for h in hits)
                        self._system_note(f"📚 Knowledge Search for '{arg}':\\n" + h_str)
                    else:
                        self._system_note(f"No knowledge documentation matches found for '{arg}'.")
                return

            if word in ("/apps", "/integrations"):
                from ..app_connectors import get_app_connectors
                ac = get_app_connectors()
                conns = ac.list_connectors()
                c_str = "\\n".join(f"• {c['icon']} {c['name']} [{c['status'].upper()}] — {c.get('metadata', {}).get('description', '')}" for c in conns)
                self._system_note("🔌 App Connectors & Integrations:\\n" + c_str)
                return\n\n            '''

text = text[:idx1] + clean_block + text[idx2:]

with open('calc_terminal/ui/app.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Successfully replaced platform block with clean single-line strings!")

