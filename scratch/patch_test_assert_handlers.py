p = "calc_terminal/tests/test_v090_voice_and_composer_layout.py"
with open(p, "r", encoding="utf-8") as f:
    text = f.read()

old_block = '''        for cmd in decommissioned:
            # Must not be in commands_data autocomplete
            self.assertNotIn(cmd, commands_list, f"Decommissioned command {cmd} still in commands_data.COMMANDS")
            # Must not be an alias target in ALIAS_TABLE
            for alias, target in alias_map.items():
                self.assertNotEqual(target, cmd, f"Alias {alias} still maps to decommissioned command {cmd}")'''

new_block = '''        from calc_terminal.app import CalcTerminalApp
        for cmd in decommissioned:
            # Must not be in commands_data autocomplete
            self.assertNotIn(cmd, commands_list, f"Decommissioned command {cmd} still in commands_data.COMMANDS")
            # Must not be an alias target in ALIAS_TABLE
            for alias, target in alias_map.items():
                self.assertNotEqual(target, cmd, f"Alias {alias} still maps to decommissioned command {cmd}")
            # Must not have a method on CalcTerminalApp
            method_name = f"cmd_{cmd.lstrip('/')}"
            self.assertFalse(hasattr(CalcTerminalApp, method_name), f"CalcTerminalApp still has handler {method_name}")'''

if old_block in text:
    text = text.replace(old_block, new_block)
    print("Replaced in test")
else:
    old_crlf = old_block.replace("\n", "\r\n")
    if old_crlf in text:
        text = text.replace(old_crlf, new_block.replace("\n", "\r\n"))
        print("Replaced CRLF in test")

with open(p, "w", encoding="utf-8") as f:
    f.write(text)

