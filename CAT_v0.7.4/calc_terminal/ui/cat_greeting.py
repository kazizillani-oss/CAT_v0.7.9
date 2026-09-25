"""
CAT UI — 3D ASCII Block Art & Routine Time-Based Greetings.

Provides rotating 3D ASCII block art greetings for the CAT section of the dashboard.
Renders authentic 3D block greetings (READY, ONLINE, AWAKE, BUILD, CODE, HELLO, etc.)
rather than a repeated CAT logo, adapting dynamically based on time of day (Morning Build,
Afternoon Focus, Evening Session, Night Ops) and cycling on user interaction.
"""

from __future__ import annotations

import datetime
from typing import Dict, List, Tuple

# ─── 50 NUMBERED ROUTINE GREETINGS ───────────────────────────────────────────
GREETINGS_NUMBERED = [
    "[01]  > CAT is ready.",
    "[02]  > Welcome back.",
    "[03]  > CAT is awake.",
    "[04]  > Ready when you are.",
    "[05]  > Let's build.",
    "[06]  > Let's code.",
    "[07]  > Let's create.",
    "[08]  > Terminal ready.",
    "[09]  > Workspace ready.",
    "[10]  > System ready.",
    "[11]  > CAT online.",
    "[12]  > CAT initialized.",
    "[13]  > CAT is purring.",
    "[14]  > Paws on keyboard.",
    "[15]  > Ready to assist.",
    "[16]  > What are we building?",
    "[17]  > What are we coding?",
    "[18]  > What's the mission?",
    "[19]  > Your workspace awaits.",
    "[20]  > Back to work.",
    "[21]  > Let's get started.",
    "[22]  > Time to build.",
    "[23]  > Time to code.",
    "[24]  > Code mode ready.",
    "[25]  > Agent mode ready.",
    "[26]  > Notebook ready.",
    "[27]  > Research mode ready.",
    "[28]  > Plan mode ready.",
    "[29]  > Debug mode ready.",
    "[30]  > Build mode ready.",
    "[31]  > All systems go.",
    "[32]  > Everything is ready.",
    "[33]  > CAT has arrived.",
    "[34]  > CAT is here.",
    "[35]  > Good to see you.",
    "[36]  > Welcome to CAT.",
    "[37]  > Back in the terminal.",
    "[38]  > Your terminal companion.",
    "[39]  > Let's make something.",
    "[40]  > Let's solve it.",
    "[41]  > Let's figure it out.",
    "[42]  > Ready for the next task.",
    "[43]  > New session started.",
    "[44]  > Fresh session ready.",
    "[45]  > Workspace unlocked.",
    "[46]  > Terminal paws ready.",
    "[47]  > Brain online. Paws ready.",
    "[48]  > Coffee optional. Code required.",
    "[49]  > No noise. Just code.",
    "[50]  > CAT ready. Your move.",
]

# ─── ACTION PHRASES ──────────────────────────────────────────────────────────
GREETINGS_ACTION = [
    "> Ready.",
    "> Online.",
    "> Awake.",
    "> Let's code.",
    "> Let's build.",
    "> Let's create.",
    "> Let's go.",
    "> Begin.",
    "> Start coding.",
    "> Workspace ready.",
    "> Terminal ready.",
    "> Agent ready.",
    "> Plan ready.",
    "> Build ready.",
    "> Debug ready.",
    "> Research ready.",
    "> Notebook ready.",
    "> CAT online.",
    "> CAT awake.",
    "> CAT initialized.",
    "> Paws ready.",
    "> Brain online.",
    "> Back to work.",
    "> New session.",
    "> Fresh start.",
    "> Mission ready.",
    "> Task ready.",
    "> System ready.",
    "> All systems go.",
    "> Your move.",
]

# ─── FELINE PHRASES ──────────────────────────────────────────────────────────
GREETINGS_FELINE = [
    "> *meow* — ready.",
    "> Paws ready.",
    "> CAT is purring.",
    "> CAT has entered.",
    "> Paws on keyboard.",
    "> Meow. Let's code.",
    "> 🐾 Ready to build.",
    "> 🐾 Ready to debug.",
    "> 🐾 Ready to explore.",
    "> 🐾 Ready to create.",
]

# ─── 3D ASCII BLOCK ART GREETINGS ────────────────────────────────────────────
# Handcrafted 3D isometric block typography for greetings (NOT a CAT logo).
# Width budgeted at 18–27 characters to ensure zero overflow in card columns.
GREETING_3D_ART: Dict[str, List[str]] = {
    "READY": [
        "  █▀▀▄ █▀▀ █▀▀█ █▀▀▄ █   █",
        "  █▄▄▀ █▀▀ █▄▄█ █  █  ▀█▀ ",
        "  ▀  ▀ ▀▀▀ ▀  ▀ ▀▀▀    █  ",
    ],
    "ONLINE": [
        " █▀▀█ █▄ █ █   ▀█▀ █▄ █ █▀▀",
        " █  █ █ ▀█ █    █  █ ▀█ █▀▀",
        " ▀▀▀▀ ▀  ▀ ▀▀▀ ▀▀▀ ▀  ▀ ▀▀▀",
    ],
    "AWAKE": [
        "  █▀▀█ █   █ █▀▀█ █▄▀ █▀▀",
        "  █▄▄█ █ █ █ █▄▄█ █ █ █▀▀",
        "  ▀  ▀ ▀▀ ▀▀ ▀  ▀ ▀ ▀ ▀▀▀",
    ],
    "BUILD": [
        "  █▀▀▄ █  █ ▀█▀ █   █▀▀▄",
        "  █▀▀▄ █  █  █  █   █  █",
        "  ▀▀▀  ▀▀▀▀ ▀▀▀ ▀▀▀ ▀▀▀ ",
    ],
    "CODE": [
        "   █▀▀ █▀▀█ █▀▀▄ █▀▀",
        "   █   █  █ █  █ █▀▀",
        "   ▀▀▀ ▀▀▀▀ ▀▀▀  ▀▀▀",
    ],
    "HELLO": [
        "  █  █ █▀▀ █   █   █▀▀█",
        "  █▀▀█ █▀▀ █   █   █  █",
        "  ▀  ▀ ▀▀▀ ▀▀▀ ▀▀▀ ▀▀▀▀",
    ],
    "GO !": [
        "    █▀▀▀   █▀▀█    █",
        "    █ ▀█   █  █    █",
        "    ▀▀▀▀   ▀▀▀▀    ▄",
    ],
    "START": [
        "  █▀▀ ▀█▀ █▀▀█ █▀▀▄ ▀█▀",
        "  ▀▀█  █  █▄▄█ █▄▄▀  █ ",
        "  ▀▀▀  ▀  ▀  ▀ ▀  ▀  ▀ ",
    ],
    "BEGIN": [
        "  █▀▀▄ █▀▀ █▀▀▀ ▀█▀ █▄ █",
        "  █▀▀▄ █▀▀ █ ▀█  █  █ ▀█",
        "  ▀▀▀  ▀▀▀ ▀▀▀▀ ▀▀▀ ▀  ▀",
    ],
    "MEOW": [
        "  █▄ ▄█ █▀▀ █▀▀█ █   █",
        "  █ ▀ █ █▀▀ █  █ █ █ █",
        "  ▀   ▀ ▀▀▀ ▀▀▀▀ ▀▀ ▀▀",
    ],
    "PAWS": [
        "   █▀▀▄ █▀▀█ █   █ █▀▀",
        "   █▄▄▀ █▄▄█ █ █ █ ▀▀█",
        "   ▀    ▀  ▀ ▀▀ ▀▀ ▀▀▀",
    ],
    "PLAN": [
        "   █▀▀▄ █   █▀▀█ █▄ █",
        "   █▄▄▀ █   █▄▄█ █ ▀█",
        "   ▀    ▀▀▀ ▀  ▀ ▀  ▀",
    ],
    "DEBUG": [
        " █▀▀▄ █▀▀ █▀▀▄ █  █ █▀▀▀ ",
        " █  █ █▀▀ █▀▀▄ █  █ █ ▀█ ",
        " ▀▀▀  ▀▀▀ ▀▀▀  ▀▀▀▀ ▀▀▀▀ ",
    ],
    "WORK": [
        "   █   █ █▀▀█ █▀▀▄ █▄▀",
        "   █ █ █ █  █ █▄▄▀ █ █",
        "   ▀▀ ▀▀ ▀▀▀▀ ▀  ▀ ▀ ▀",
    ],
}

# Backward compatibility alias
BLOCK_ART_3D_ISOMETRIC = GREETING_3D_ART["READY"]
BLOCK_ART_3D_SHADED = GREETING_3D_ART["ONLINE"]
BLOCK_ART_3D_EXTRUDED = GREETING_3D_ART["AWAKE"]


def get_routine_period(hour: int) -> Tuple[str, str]:
    """Returns (period_name, icon) for the given 24h hour."""
    if 5 <= hour < 12:
        return "Morning Build", "🌅"
    elif 12 <= hour < 17:
        return "Afternoon Focus", "☀️"
    elif 17 <= hour < 22:
        return "Evening Session", "🌆"
    else:
        return "Night Ops", "🌙"


def extract_greeting_keyword(numbered: str, action: str, feline: str) -> str:
    """Selects the matching 3D block greeting keyword based on active messages."""
    for text in (numbered, action, feline):
        t = text.lower()
        if "ready" in t or "assist" in t or "mission" in t or "task" in t:
            return "READY"
        elif "online" in t or "brain online" in t or "initialized" in t:
            return "ONLINE"
        elif "awake" in t:
            return "AWAKE"
        elif "code" in t or "coding" in t:
            return "CODE"
        elif "build" in t or "building" in t or "create" in t:
            return "BUILD"
        elif "plan" in t:
            return "PLAN"
        elif "debug" in t:
            return "DEBUG"
        elif "welcome" in t or "arrived" in t or "here" in t:
            return "HELLO"
        elif "start" in t or "session" in t or "fresh" in t:
            return "START"
        elif "begin" in t:
            return "BEGIN"
        elif "work" in t or "solve" in t:
            return "WORK"
        elif "go" in t or "move" in t:
            return "GO !"
        elif "paws" in t:
            return "PAWS"
        elif "meow" in t or "purr" in t:
            return "MEOW"
    return "READY"


def get_cat_routine_data(now: datetime.datetime | None = None, offset: int = 0) -> dict:
    """Computes routine time-based greeting metadata with 3D block greeting typography."""
    if now is None:
        now = datetime.datetime.now()

    hour = now.hour
    minute = now.minute
    time_str = now.strftime("%I:%M %p").lstrip("0")
    period_name, icon = get_routine_period(hour)

    # Deterministic rotation based on minute-of-day + offset
    minute_of_day = hour * 60 + minute
    num_idx = (minute_of_day + offset) % len(GREETINGS_NUMBERED)
    act_idx = (minute_of_day // 5 + offset) % len(GREETINGS_ACTION)
    fel_idx = (minute_of_day // 3 + offset) % len(GREETINGS_FELINE)

    numbered_msg = GREETINGS_NUMBERED[num_idx]
    action_msg = GREETINGS_ACTION[act_idx]
    feline_msg = GREETINGS_FELINE[fel_idx]

    # Determine 3D block greeting keyword based on active greeting
    keyword = extract_greeting_keyword(numbered_msg, action_msg, feline_msg)
    art_lines = GREETING_3D_ART.get(keyword, GREETING_3D_ART["READY"])

    return {
        "time_str": time_str,
        "period_name": period_name,
        "period_icon": icon,
        "numbered": numbered_msg,
        "action": action_msg,
        "feline": feline_msg,
        "keyword": keyword,
        "art_lines": art_lines,
        "index": num_idx + 1,
    }


def get_cat_routine_display(
    offset: int = 0,
    accent_hex: str = "#89b4fa",
    text_muted_hex: str = "#a6adc8",
    text_faint_hex: str = "#6c7086",
    mode_key: str | None = None,
) -> str:
    """Generates rich markup text for the CAT dashboard column."""
    data = get_cat_routine_data(offset=offset)
    # Render the 3D block greeting typography with active mode accent
    art = "\n".join(f"[{accent_hex} b]{line}[/]" for line in data["art_lines"])

    mode_prefix = ""
    if mode_key:
        try:
            from .. import ai_modes
            m = ai_modes.meta(mode_key)
            if m:
                m_icon = m.get("icon", "⚡")
                m_lbl = m.get("label", mode_key.capitalize())
                mode_prefix = f"  [{accent_hex} b]{m_icon} {m_lbl} Mode[/] \u00b7 "
        except Exception:
            pass

    badge = (
        f"{mode_prefix}[{accent_hex}]⚡[/] [b]{data['period_icon']} Routine {data['time_str']}[/]  "
        f"\u00b7  [{text_faint_hex}]{data['period_name']}[/]"
    )
    greeting = f"  [{accent_hex} b]{data['numbered']}[/]"
    sub_greeting = f"  [{text_muted_hex}]{data['feline']}[/]"

    return f"{art}\n\n{badge}\n{greeting}\n{sub_greeting}"
