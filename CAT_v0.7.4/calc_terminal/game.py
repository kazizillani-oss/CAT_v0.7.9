"""
Element Quiz — a small multiple-choice game bolted onto the same
premium panel/gradient rendering as the rest of Chemistry Calc
Terminal, so learning periodic-table facts feels like part of the
same app instead of a bolted-on mini-game.

Question types are generated from the same ELEMENTS table atomsim.py
already uses for the live Bohr simulation (Z, symbol, name, shells,
mass), so there's exactly one source of truth for element data.
"""

import random
import time

from . import theme
from . import sound
from .atomsim import ELEMENTS
from .engine import WIDTH
LETTERS = ["A", "B", "C", "D"]
START_LIVES = 3


def _shells_str(shells):
    return "-".join(str(s) for s in shells)


def _distractor_pool(exclude_z):
    return [z for z in ELEMENTS if z != exclude_z]


def _make_options(correct, pool_values, n=4):
    others = random.sample([v for v in pool_values if v != correct], min(n - 1, len(pool_values) - 1))
    options = others + [correct]
    random.shuffle(options)
    return options


def make_question(difficulty=1):
    """Build one multiple-choice question dict:
    {prompt, options: [...], correct_index, explain}"""
    z = random.choice(list(ELEMENTS.keys()))
    sym, name, shells, mass = ELEMENTS[z]
    qtype = random.choice([
        "symbol_from_name", "name_from_symbol", "z_from_name",
        "name_from_z", "shells_from_name", "mass_from_name",
    ])

    if qtype == "symbol_from_name":
        prompt = f"What is the chemical symbol for {theme.text(name, bold=True)}?"
        correct = sym
        pool = [ELEMENTS[k][0] for k in ELEMENTS]
        explain = f"{name} \u2192 {sym} (Z={z})"
    elif qtype == "name_from_symbol":
        prompt = f"Which element has the symbol {theme.cyan(sym, bold=True)}?"
        correct = name
        pool = [ELEMENTS[k][1] for k in ELEMENTS]
        explain = f"{sym} \u2192 {name} (Z={z})"
    elif qtype == "z_from_name":
        prompt = f"What is the atomic number of {theme.text(name, bold=True)}?"
        correct = str(z)
        pool = [str(k) for k in ELEMENTS]
        explain = f"{name} has {z} protons \u2192 Z = {z}"
    elif qtype == "name_from_z":
        prompt = f"Which element has atomic number {theme.orange(str(z), bold=True)}?"
        correct = name
        pool = [ELEMENTS[k][1] for k in ELEMENTS]
        explain = f"Z={z} \u2192 {name} ({sym})"
    elif qtype == "shells_from_name":
        prompt = f"What is the electron shell structure (K-L-M...) of {theme.text(name, bold=True)}?"
        correct = _shells_str(shells)
        pool_z = random.sample(list(ELEMENTS.keys()), min(12, len(ELEMENTS)))
        pool = [_shells_str(ELEMENTS[k][2]) for k in pool_z]
        explain = f"{name} ({sym}, Z={z}) \u2192 {_shells_str(shells)}"
    else:  # mass_from_name
        prompt = f"What is the approximate atomic mass of {theme.text(name, bold=True)}?"
        correct = str(mass)
        pool = [str(ELEMENTS[k][3]) for k in ELEMENTS]
        explain = f"{name} ({sym}) \u2248 {mass} u"

    options = _make_options(correct, pool)
    if correct not in options:
        options[-1] = correct
        random.shuffle(options)
    correct_index = options.index(correct)
    return {"prompt": prompt, "options": options, "correct_index": correct_index, "explain": explain}


def _hearts(lives):
    return theme.red("\u2665 " * lives, bold=True) + theme.faint("\u2661 " * (START_LIVES - lives))


def _streak_badge(streak):
    if streak >= 8:
        return theme.gradient(f"\U0001f525 x{streak} ON FIRE", theme.ORANGE, theme.RED, bold=True)
    if streak >= 4:
        return theme.orange(f"\U0001f525 x{streak} streak", bold=True)
    if streak >= 1:
        return theme.dim(f"streak x{streak}")
    return theme.faint("streak x0")


def _grade(score):
    if score >= 900:
        return "S", theme.gradient("S \u2014 PERIODIC LEGEND", theme.CYAN, theme.PURPLE, bold=True)
    if score >= 600:
        return "A", theme.green("A \u2014 Sharp chemist", bold=True)
    if score >= 350:
        return "B", theme.cyan("B \u2014 Solid grasp", bold=True)
    if score >= 150:
        return "C", theme.orange("C \u2014 Getting there", bold=True)
    return "D", theme.faint("D \u2014 Back to the formula library")


def run_game(app):
    theme.clear_screen()
    print()
    print(theme.panel([
        theme.gradient("\u2697  ELEMENT QUIZ  \u2697", theme.CYAN, theme.PURPLE, bold=True),
        "",
        theme.dim("Multiple choice \u2014 symbols, names, atomic numbers, shells & mass."),
        theme.dim(f"You have {START_LIVES} lives. Answer fast for a speed bonus."),
        theme.dim("Type a letter (A-D) to answer, or /quit to stop anytime."),
    ], title="game", color=theme.PURPLE, width=WIDTH, title_gradient=(theme.CYAN, theme.PURPLE)))

    score = 0
    streak = 0
    best_streak_this_run = 0
    lives = START_LIVES
    qn = 0

    while lives > 0:
        qn += 1
        q = make_question()
        print()
        header = (theme.faint(f"Q{qn}") + "   " + _hearts(lives) + "   " +
                  theme.dim(f"score {score}") + "   " + _streak_badge(streak))
        print("  " + header)
        print(theme.panel(
            [q["prompt"], ""] + [f"  {theme.cyan(LETTERS[i])}. {opt}" for i, opt in enumerate(q["options"])],
            title=f"question {qn}", color=theme.CYAN, width=WIDTH,
        ))
        start = time.time()
        try:
            raw = input(theme.dim("  answer \u25b8 ")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        elapsed = time.time() - start
        low = raw.strip().lower()
        if low in ("/quit", "/back", "/exit", "quit"):
            break

        pick = None
        if low and low[0].upper() in LETTERS:
            pick = LETTERS.index(low[0].upper())

        if pick == q["correct_index"]:
            speed_bonus = 40 if elapsed < 3 else (20 if elapsed < 6 else 0)
            base = 60
            streak += 1
            best_streak_this_run = max(best_streak_this_run, streak)
            gained = base + speed_bonus + streak * 5
            score += gained
            sound.play("success")
            tag = " \u26a1 speed bonus!" if speed_bonus == 40 else ""
            print("  " + theme.green(f"\u2713 Correct! +{gained}{tag}", bold=True))
            print("  " + theme.dim(q["explain"]))
        else:
            lives -= 1
            streak = 0
            sound.play("error")
            correct_letter = LETTERS[q["correct_index"]]
            print("  " + theme.red(f"\u2717 Not quite \u2014 correct answer was {correct_letter}.", bold=True))
            print("  " + theme.dim(q["explain"]))
            if lives == 0:
                print("  " + theme.orange("Out of lives!", bold=True))

    app.game_high_score = max(app.game_high_score, score)
    app.game_best_streak = max(app.game_best_streak, best_streak_this_run)
    _, grade_line = _grade(score)

    print()
    print(theme.panel([
        theme.gradient("ROUND OVER", theme.PURPLE, theme.CYAN, bold=True),
        "",
        theme.text(f"Final score: {score}", bold=True),
        theme.dim(f"Best streak this round: {best_streak_this_run}"),
        theme.dim(f"Session high score: {app.game_high_score}  \u00b7  Session best streak: {app.game_best_streak}"),
        "",
        grade_line,
    ], title="results", color=theme.PURPLE, width=WIDTH, title_gradient=(theme.PURPLE, theme.CYAN)))
    print()
    input(theme.faint("  Press Enter to return home\u2026"))
