with open('calc_terminal/commands_data.py', 'r', encoding='utf-8') as f:
    text = f.read()

new_commands_snippet = '''    # CAT Platform Expansion: Critical Systems
    ("/index", "Index workspace symbols, classes, functions and dependencies with AST"),
    ("/project", "Show architectural project summary and code statistics"),
    ("/code", "Search code or detect dead functions (/code search, /code dead)"),
    ("/code search", "Search source code using regex or semantic keywords"),
    ("/code dead", "Detect potentially unused functions and dead code in workspace"),
    ("/security", "Open Security & Compliance Center (secret scan & safety audit)"),
    ("/security scan", "Scan workspace files for hardcoded API keys and secrets"),
    ("/dependency audit", "Audit requirements.txt / package.json for known vulnerabilities"),
    ("/deploy", "Open Deployment Center or deploy project (Vercel, Netlify, Docker, SSH)"),
    ("/release", "Alias for /deploy — manage builds and cloud deployments"),
    ("/ai benchmark", "Run AI inference latency, accuracy, and speed benchmark"),
    ("/ai evaluate", "Evaluate model response quality across reasoning and code prompts"),
    ("/ai cost", "Open AI Usage & Cost Manager (token breakdown and expenditures)"),
    ("/ai usage", "Show token consumption summary across models and providers"),
    ("/ai budget", "Set or inspect AI spending budget limit"),
    ("/automation", "Manage scheduled routines, cron jobs, and background automations"),
    ("/agent delegate", "Delegate subtask to specialized Kitty agent"),
    ("/agent studio", "Create and customize new AI Kitty agents with custom prompts"),

    # CAT Platform Expansion: High-Priority Systems
    ("/db", "Open Database Studio (schema explorer, tables, safe query runner)"),
    ("/db connect", "Connect to a SQLite database file or in-memory DB"),
    ("/db query", "Execute safe SQL query against connected database"),
    ("/db schema", "Inspect table schema, column types, and primary keys"),
    ("/db export", "Export database table to CSV or JSON format"),
    ("/workflow", "Open Workflow Builder (DAG pipelines and automated routines)"),
    ("/workflow run", "Execute an automated DAG workflow pipeline"),
    ("/workflow list", "List available workflow pipelines and templates"),
    ("/github", "Open GitHub Studio (repos, PRs, issues, actions, and commits)"),
    ("/github pr", "List open GitHub pull requests"),
    ("/github issues", "List repository issues and bug reports"),
    ("/github sync", "Pull latest updates from upstream remote branch"),
    ("/cloud", "Open Cloud Workspace (remote SSH hosts and Docker containers)"),
    ("/remote", "Alias for /cloud — manage remote SSH profiles"),
    ("/docker", "Inspect running Docker containers and daemon status"),
    ("/knowledge", "Open Knowledge Center (cheatsheets and searchable docs)"),
    ("/docs", "Search workspace documentation with line-numbered citations"),
    ("/apps", "Open App Connector Center (Slack, Notion, Discord, Google integrations)"),
    ("/integrations", "Alias for /apps — manage third-party SaaS connectors"),
'''

target = '    ("/exit", "Quit Chemistry Calc Terminal"),\n]'
replacement = target.replace('\n]', ',\n' + new_commands_snippet + ']')
assert target in text, 'target not found in commands_data.py'
text = text.replace(target, replacement, 1)

# Add to NATIVE_UI_COMMANDS
old_native = '"/compute", "/fabric", "/curl", "/brew", "/sudo"}'
new_native = '"/compute", "/fabric", "/curl", "/brew", "/sudo", "/index", "/project", "/code", "/security", "/deploy", "/release", "/ai cost", "/ai usage", "/ai budget", "/ai benchmark", "/automation", "/db", "/workflow", "/github", "/cloud", "/remote", "/docker", "/knowledge", "/docs", "/apps", "/integrations"}'

assert old_native in text, 'old_native not found'
text = text.replace(old_native, new_native, 1)

with open('calc_terminal/commands_data.py', 'w', encoding='utf-8') as f:
    f.write(text)

print('Successfully added platform commands to commands_data.py!')

