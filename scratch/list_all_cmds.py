from calc_terminal.commands_data import COMMANDS
print("Total commands currently:", len(COMMANDS))
for c, d in COMMANDS:
    print(f"  {c:<18}: {d}")

