# CCT Identity Layer

Fixes inconsistent/incorrect answers to "who created you", "who developed
you", "who built CCT", "who made this application", "what are you", and
"who owns this project".

## Root cause
Identity info didn't exist anywhere centrally:
- `aicore.py`'s default chat system prompt said nothing about who made CCT.
- `agent.py`'s `AGENT_SYSTEM_PROMPT` / `AI_SYSTEM_PROMPT` said nothing either.
- The only related code was a hidden easter egg (`easter_eggs.py`) that
  matched a few exact phrases and printed vague flavor text with no
  creator name.

So the AI model was left to guess, and different phrasings of the same
question could hit different code paths (or none) and get different —
sometimes fabricated — answers.

## Fix: single source of truth
New module: `calc_terminal/identity.py`
- App facts: name, short name, tagline, creator (Kazi Zillani, student
  and independent developer), development note.
- `tech_stack_sentence(config)` — describes the technology actually in
  use (Python / Textual / chemistry engine, plus whichever AI provider
  is really configured via `aicore.load_config()`) instead of a fixed,
  possibly-fabricated list.
- `IDENTITY_BLOCK` — a system-prompt fragment folded into every AI
  system prompt so the model itself stays accurate.
- `classify_identity_question()` / `answer_for()` — a deterministic,
  regex-based fast path that answers common phrasings directly, with
  zero AI involvement, so the answer is guaranteed consistent.

## Wired in at every layer
1. **AI system prompts** (`aicore.DEFAULT_SYSTEM_PROMPT`,
   `agent.AGENT_SYSTEM_PROMPT`, `agent.AI_SYSTEM_PROMPT`,
   `aicore.query_ai_with_image`'s default) all now include
   `identity.IDENTITY_BLOCK`.
2. **Deterministic fast-path intercept**, so the answer never depends on
   the LLM at all:
   - Textual UI (`ui/app.py`, the primary v0.6.1 chat) —
     `_maybe_answer_identity_question()` runs before any AI dispatch.
   - Fallback CLI (`app.py` via `easter_eggs.check()`) — the exact-match
     egg list was expanded and `check()` now also falls back to
     `identity.classify_identity_question()` for phrasings the exact
     list misses.
3. **Easter egg panel** (`/who made this` etc.) now renders the real
   creator name and actual tech stack instead of generic flavor text.

## App vs. AI model — kept separate
Per spec, CCT (the application) and the underlying AI model/provider are
treated as two different things everywhere:
- "Who created you?" → Kazi Zillani (the CCT app).
- "What AI model are you using?" → the actual configured provider/model
  (e.g. "OpenRouter (model: openai/gpt-4o-mini)"), never the creator's name.

Nothing about capabilities or technology is invented — `tech_stack_sentence()`
only ever reports what's actually configured.
