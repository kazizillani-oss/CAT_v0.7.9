"""
calc_terminal/identity.py
==========================
Single source of truth for CCT's application identity: what CCT is, who
made it, and what it's actually built with.

Before this module existed, "who made you" style questions were answered
in three different, drifting places: the AI's default system prompt (no
creator info at all), the AGENT/AI system prompts in agent.py (also
nothing), and a hidden easter egg in easter_eggs.py (vibes, no name).
That's why the app used to give inconsistent or flatly wrong answers.

Every one of those places now reads from here instead of hardcoding its
own copy:
  - aicore.py's default system prompts embed IDENTITY_BLOCK
  - agent.py's AGENT_SYSTEM_PROMPT / AI_SYSTEM_PROMPT embed IDENTITY_BLOCK
  - easter_eggs.py's "who made this" panel renders answer_creator()
  - the Textual UI (ui/app.py) and the fallback CLI (app.py) both run a
    deterministic fast-path intercept (is_identity_question / answer_for)
    *before* ever reaching the AI, so the answer is 100% consistent no
    matter which AI provider is active, whether it's offline, or how a
    particular model happens to phrase things.

tech_stack_sentence() never invents technology — it only ever reports the
Python/Textual/engine core that's always true plus whatever AI provider
is actually configured right now (from aicore's own config), so it can't
drift out of sync with reality either.
"""

import re

# --------------------------------------------------------------- facts --
APP_NAME = "Coding Agent Terminal"
SHORT_NAME = "CAT"
APP_TAGLINE = "a terminal-based AI-powered coding and scientific workspace"
APP_VERSION = "0.8.ab"

CLI_TITLE = "CAT CLI"
CLI_EMOJI = "🐱"
FULL_CLI_TITLE = f"{CLI_EMOJI} {CLI_TITLE}"

CREATOR_NAME = "Kazi Zillani"
CREATOR_ROLE = "a student and independent developer"
DEVELOPMENT_NOTE = "designed and developed by a single developer"

# Technology that's always part of CAT regardless of which AI backend
# (if any) is currently configured.
_CORE_TECH = [
    "Python",
    "the Textual terminal UI framework",
    "a custom chemistry calculation engine",
]

_PROVIDER_LABELS = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "gemini": "Google Gemini",
    "openrouter": "OpenRouter",
    "groq": "Groq",
    "ollama": "a local Ollama model",
}


def _provider_phrase(config):
    """Describe the currently configured AI backend truthfully, or return
    None if nothing is configured — never guess a provider that isn't
    actually active."""
    if not config:
        return None
    provider = (config.get("provider") or "").strip().lower()
    if not provider:
        return None
    model = (config.get("model") or "").strip()
    label = _PROVIDER_LABELS.get(provider, provider)
    if provider == "ollama":
        return f"{label} (model: {model})" if model else label
    return f"{label} (model: {model})" if model else label


def tech_stack_parts(config=None):
    """List of technology strings actually in play right now. `config`
    should be aicore.load_config()'s return value, if available."""
    parts = list(_CORE_TECH)
    provider_phrase = _provider_phrase(config)
    if provider_phrase:
        parts.append(provider_phrase)
    return parts


def tech_stack_sentence(config=None):
    parts = tech_stack_parts(config)
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + ", and " + parts[-1]


# ------------------------------------------------------- system prompt --
# Folded into every AI system prompt so the model itself stays accurate
# even for identity phrasings the fast-path intercept below doesn't
# happen to catch.
IDENTITY_BLOCK = f"""[CAT IDENTITY \u2014 factual, do not deviate from this]
You are running inside {APP_NAME} ({SHORT_NAME}), {APP_TAGLINE}.
{SHORT_NAME} the application was created by {CREATOR_NAME}, {CREATOR_ROLE} \u2014 {DEVELOPMENT_NOTE}.
You (the AI answering right now) are a separate thing from {SHORT_NAME} itself: {SHORT_NAME} is the app/terminal the person is typing into; the AI is whichever model provider is currently configured. Never claim {CREATOR_NAME} built or trained the underlying AI model \u2014 only the {SHORT_NAME} application around it.
If asked who made/built/created/developed {SHORT_NAME}, or who owns this project: the answer is {CREATOR_NAME}, {CREATOR_ROLE}.
If asked what AI model or provider is answering: name the actual configured provider/model, never {CREATOR_NAME}.
Never invent capabilities, companies, or technologies that aren't actually part of {SHORT_NAME}."""


# ---------------------------------------------------- deterministic Q&A --
# A fast-path for the most common phrasings, answered directly from this
# module with zero AI involved, so the answer can never depend on model
# mood, provider, or connectivity. Broader than an exact-match easter
# egg on purpose: "who built cat", "who owns this project", "who
# developed you" etc. should all land here, not just one exact string.
_CREATOR_PATTERNS = [
    r"\bwho\b[^.?!]{0,40}\b(made|built|created|developed|designed|coded|wrote|owns)\b[^.?!]{0,25}\b(you|this|it|cat|cct|the app|the application|the project|coding agent terminal)\b",
    r"\bwho(?:'s| is)\b[^.?!]{0,25}\b(creator|developer|maker|author|owner)\b",
    r"\bwho\s+(?:made|built|created|developed|owns)\s+(?:cat|cct)\b",
]
_WHAT_ARE_YOU_PATTERNS = [
    r"^\s*what\s+are\s+you\s*\??\s*$",
    r"^\s*who\s+are\s+you\s*\??\s*$",
    r"^\s*whoareyou\s*\??\s*$",
    r"^\s*whatareyou\s*\??\s*$",
    r"\bwhat\s+is\s+cat\b",
    r"\bwhat\s+is\s+cct\b",
    r"\bwhat\s+is\s+coding\s+agent\s+terminal\b",
    # handle concatenated like Hi,howcanIhelpyou?User:whoareyou?
    r"who\s*are\s*you",
    r"what\s*are\s*you",
]
_MODEL_PATTERNS = [
    r"\bwhat\s+(?:ai\s+)?model\b[^.?!]{0,25}\b(are you|is this|using|running|powered by)\b",
    r"\bwhich\s+(?:ai\s+)?model\b",
    r"\bwhat\s+llm\b",
]

_CREATOR_RE = re.compile("|".join(_CREATOR_PATTERNS), re.IGNORECASE)
_WHAT_ARE_YOU_RE = re.compile("|".join(_WHAT_ARE_YOU_PATTERNS), re.IGNORECASE)
_MODEL_RE = re.compile("|".join(_MODEL_PATTERNS), re.IGNORECASE)


def classify_identity_question(text):
    """Return 'model', 'creator', 'what', or None. Checked in this order
    so 'what AI model are you using' (a model question) doesn't get
    swallowed by the broader 'what are you' pattern."""
    t = (text or "").strip()
    if not t:
        return None
    if _MODEL_RE.search(t):
        return "model"
    if _CREATOR_RE.search(t):
        return "creator"
    if _WHAT_ARE_YOU_RE.search(t):
        return "what"
    return None


def is_identity_question(text):
    return classify_identity_question(text) is not None


def answer_creator(config=None):
    return (
        f"{SHORT_NAME} ({APP_NAME}) was created by {CREATOR_NAME}, {CREATOR_ROLE} \u2014 "
        f"{DEVELOPMENT_NOTE}.\n"
        f"Under the hood it's built with {tech_stack_sentence(config)}."
    )


def answer_what(config=None):
    return (
        f"{SHORT_NAME} is {APP_TAGLINE}. It's built with {tech_stack_sentence(config)}, "
        f"created by {CREATOR_NAME}, {CREATOR_ROLE}."
    )


def answer_model(config=None):
    provider_phrase = _provider_phrase(config)
    if not provider_phrase:
        return (
            f"No AI provider is configured for {SHORT_NAME} right now \u2014 run /model to set "
            f"one up. That's separate from {SHORT_NAME} itself, which was created by "
            f"{CREATOR_NAME}, {CREATOR_ROLE}."
        )
    return (
        f"Right now {SHORT_NAME} is talking to you through {provider_phrase}. That's the "
        f"underlying AI provider, not {SHORT_NAME} itself \u2014 the {SHORT_NAME} application "
        f"around it was created by {CREATOR_NAME}."
    )


def answer_for(text, config=None):
    """Return the canonical answer for an identity question, or None if
    `text` isn't one."""
    kind = classify_identity_question(text)
    if kind == "creator":
        return answer_creator(config)
    if kind == "model":
        return answer_model(config)
    if kind == "what":
        return answer_what(config)
    return None


# Re-export terminal identity functions for convenience
from .terminal_identity import (
    set_terminal_title,
    restore_terminal_title,
    init_terminal_identity,
    get_icon_path,
    configure_windows_terminal_profile,
    start_title_guard,
    stop_title_guard,
)
