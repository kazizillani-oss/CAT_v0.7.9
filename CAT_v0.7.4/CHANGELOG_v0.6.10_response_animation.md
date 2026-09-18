# CCT v0.6.10 — Advanced AI Response Animation System (Spec #25)

Implements `25. Advanced AI Response Animation System` against the
primary chat UI (`calc_terminal/ui/`). One new module owns the logic;
three existing files get the minimum wiring needed to use it — nothing
else in the animation-system spec doc lives outside these four files.

## New — `calc_terminal/ui/thinking.py`

Pure logic + formatting, no Textual dependency:

- **Response Stages** — `detect_stage(prompt, elapsed, chunk_count)`.
  Keyword matching against the prompt fires first (`/websearch` →
  *Searching Web*, `/graph`/"plot" → *Rendering Graph*, `/sim3d`/
  "simulate" → *Rendering 3D Simulation* or *Running Simulation*,
  `/solve`/"calculate" → *Running Calculation*, `` ``` ``/"write code"
  → *Executing Code*, etc. — see `_KEYWORD_STAGES`). With no keyword
  match, an elapsed-time progression fills in: *Preparing* → *Thinking*
  → *Analyzing Question* before the first token arrives, then
  *Building Response* → *Formatting Result* → *Finalizing* once tokens
  are streaming — so the indicator is never frozen on one word for the
  whole reply.
- **Live Timer** — `format_timer(elapsed)`: `0.1 s` / `5.8 s` under a
  minute, `mm:ss` beyond.
- **Three animation styles** — `DOT_FRAMES` / `BRAILLE_FRAMES` /
  `BLOCK_FRAMES` (spec's Style 1/2/3), each stage picks whichever style
  fits its feel; `spinner_frame(style, tick)` loops continuously.
- **Animated Status Colors** — `STAGES` maps every stage to the spec's
  color table (Thinking/Building = blue, Searching = cyan, Calculating
  = orange, Simulation = purple, GPU/code/HTML = magenta, Completed =
  green, Error = red).
- **Chemistry-Themed Idle Animation** — `IDLE_ICONS` (⚛ 🧪 🧬 ☁) +
  `idle_icon(tick)`.
- **Message Completion** — `completion_summary_lines(...)` builds the
  "✓ Response Complete / Provider / Model / Time / Tokens / Commands
  used" block as Rich-markup lines; `commands_used(*texts)` pulls every
  `/slash-command` mentioned in the prompt or reply.

## Changed — `calc_terminal/ui/composer.py`

`StickyComposer.set_streaming(value, prompt_hint=None)` now drives the
existing `#cct-streaming-status` bar through `thinking.py` instead of a
bare `○ streaming · model · 3s` counter: `{spinner} {Stage}… ·
{model} · {timer}`, all color-coded per stage, ticking every 100ms
(spinner + timer read as alive without doing real work between ticks —
per the spec's Performance Requirement). New `note_chunk_received()`
flips stage detection from the pre-token to the post-token progression
the moment real content starts arriving.

## Changed — `calc_terminal/ui/conversation.py`

`ConversationItem`/`ConversationView` gain an optional `meta_lines`
list, rendered as dim lines under a *finished* assistant bubble (never
while streaming) — this is where the Message Completion block lands.

## Changed — `calc_terminal/ui/app.py`

- `MessageStarted` now carries the triggering prompt (see
  `events.py`), fed straight into `composer.set_streaming(...)` for
  stage detection.
- `on_message_chunk` calls `composer.note_chunk_received()`.
- `on_message_finished` builds the completion summary
  (`_completion_summary`) from the session's AI config (provider/
  model), the turn's real duration/usage, and commands mentioned in
  the prompt/reply, then passes it to `conversation.finish(...)`.
- Idle chemistry icon added to the bottom `StatusLine`'s field list,
  ticking every 1.6s, shown only while nothing is actively streaming.

## Changed — `calc_terminal/ui/events.py`

`MessageStarted` gained an optional `prompt=""` field (backward
compatible — every existing caller that didn't pass it still works).

## Not changed

Streaming text itself already appears progressively, character by
character, exactly as `aicore.stream_ai` yields it (`Markdown`/code
fences/tables render correctly mid-stream already) — the spec's
"Streaming Text Animation" section was already satisfied by the
existing chunk pipeline and needed no changes here. The fallback CLI
(`fallback_cli.py`) already has its own independent spinner/"thinking"
line and was left alone; this pass only targets the primary chat UI.
