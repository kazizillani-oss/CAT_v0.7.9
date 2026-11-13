with open('calc_terminal/fallback_cli.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_tips = '''    "/solve  \\u2014 39 formulas, solved for any variable", "/game  \\u2014 learn chemistry by playing",
    "/atomsim Fe  \\u2014 watch an iron atom spin up", "/orbitals 3d  \\u2014 live electron cloud",
    "/agent  \\u2014 an AI that solves, plots & simulates", "\\"arrhenius equation\\"",
    "/graph  \\u2014 animated kinetics & titration curves",'''

new_tips = '''    "/solve  \\u2014 39 formulas, solved for any variable", "/voice  \\u2014 real-time microphone input",
    "/derive  \\u2014 step-by-step calculus derivations", "/bloch  \\u2014 Bloch sphere for qubit states",
    "/agent  \\u2014 an AI that solves, plots & simulates", "/workspace  \\u2014 manage project files",'''

text = text.replace(old_tips, new_tips)
with open('calc_terminal/fallback_cli.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Updated fallback_cli.py successfully')

