with open("calc_terminal/agent.py", "r", encoding="utf-8") as f:
    content = f.read()
print("install_packages in TOOLS:", '"install_packages":' in content)
print("skill in TOOLS:", '"install_skill"' in content or '"manage_skills"' in content)

