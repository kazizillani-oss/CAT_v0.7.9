with open("calc_terminal/ui/app.py", "r", encoding="utf-8") as f:
    content = f.read()

target = """            if word in ("/summarize", "/summary"):
                self._summarize_chat()
                return

            # Known classic terminal commands can suspend to terminal"""

replacement = """            if word in ("/summarize", "/summary"):
                self._summarize_chat()
                return

            # Dev & Workspace commands
            if word in ("/files", "/ls"):
                from ..dev_commands import cmd_files
                self._system_note(cmd_files(arg))
                return
            if word == "/tree":
                from ..dev_commands import cmd_tree
                self._system_note(cmd_tree(arg))
                return
            if word == "/search":
                from ..dev_commands import cmd_search
                self._system_note(cmd_search(arg))
                return
            if word == "/grep":
                from ..dev_commands import cmd_grep
                self._system_note(cmd_grep(arg))
                return
            if word == "/replace":
                from ..dev_commands import cmd_replace
                self._system_note(cmd_replace(arg))
                return
            if word == "/rename":
                from ..dev_commands import cmd_rename
                self._system_note(cmd_rename(arg))
                return
            if word in ("/new", "/touch_file"):
                from ..dev_commands import cmd_new
                self._system_note(cmd_new(arg))
                return
            if word == "/diff":
                from ..dev_commands import cmd_diff
                self._system_note(cmd_diff(arg))
                return
            if word == "/git":
                from ..dev_commands import cmd_git
                self._system_note(cmd_git(arg))
                return
            if word == "/test":
                from ..dev_commands import cmd_test
                self._system_note(cmd_test(arg))
                return
            if word == "/lint":
                from ..dev_commands import cmd_lint
                self._system_note(cmd_lint(arg))
                return
            if word == "/format":
                from ..dev_commands import cmd_format
                self._system_note(cmd_format(arg))
                return
            if word == "/typecheck":
                from ..dev_commands import cmd_typecheck
                self._system_note(cmd_typecheck(arg))
                return
            if word in ("/run", "/exec"):
                from ..dev_commands import cmd_run
                self._system_note(cmd_run(arg))
                return

            # Office & Productivity commands
            if word == "/word":
                from ..office_commands import cmd_word
                self._system_note(cmd_word(arg))
                return
            if word in ("/excel", "/sheets"):
                from ..office_commands import cmd_excel
                self._system_note(cmd_excel(arg))
                return
            if word in ("/slides", "/presentation"):
                from ..office_commands import cmd_slides
                self._system_note(cmd_slides(arg))
                return
            if word == "/pdf":
                from ..office_commands import cmd_pdf
                self._system_note(cmd_pdf(arg))
                return
            if word == "/design":
                from ..office_commands import cmd_design
                self._system_note(cmd_design(arg))
                return
            if word == "/office":
                from ..office_commands import cmd_office
                self._system_note(cmd_office(arg))
                return

            # Package, Python & Node commands
            if word in ("/pkg", "/package", "/packages_mgr"):
                from ..pkg_commands import cmd_pkg
                self._system_note(cmd_pkg(arg))
                return
            if word == "/py":
                from ..pkg_commands import cmd_py
                self._system_note(cmd_py(arg))
                return
            if word == "/node":
                from ..pkg_commands import cmd_node
                self._system_note(cmd_node(arg))
                return

            # Skill & MCP commands
            if word in ("/skill", "/skills"):
                from ..skill_commands import cmd_skill
                self._system_note(cmd_skill(arg))
                return
            if word in ("/mcp", "/mcpserver", "/mcpservers"):
                from ..mcp import cmd_mcp
                self._system_note(cmd_mcp(arg))
                return
            if word in ("/extensions", "/extension"):
                from .extensions_panel import ExtensionsPanel
                self.push_screen(ExtensionsPanel())
                return
            if word in ("/mcp_panel", "/mcps"):
                from .mcp_panel import McpServersPanel
                self.push_screen(McpServersPanel())
                return

            # Known classic terminal commands can suspend to terminal"""

content_norm = content.replace("\r\n", "\n")
t_norm = target.replace("\r\n", "\n")
r_norm = replacement.replace("\r\n", "\n")

assert t_norm in content_norm, "Target not found in calc_terminal/ui/app.py"
content_norm = content_norm.replace(t_norm, r_norm, 1)

if "\r\n" in content:
    content_norm = content_norm.replace("\n", "\r\n")

with open("calc_terminal/ui/app.py", "w", encoding="utf-8") as f:
    f.write(content_norm)

print("SUCCESS: calc_terminal/ui/app.py patched with all new commands!")

