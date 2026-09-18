# Fix: messages permanently remember the AI mode that created them

## The bug

`ai_modes.py` tracked the active mode in one process-global (`_current`).
Every color a message's bubble used — `.cct-bubble-user` /
`.cct-bubble-assistant`'s `background`/`border` — was resolved from Textual
CSS variables (`$accent`, `$border-active`) that `theme_css.css_variables()`
recomputed from that same global on every repaint. Switching modes called
`CCTApp.refresh_css()`, which re-resolves those variables app-wide — so
every bubble already on screen, not just new ones, repainted in the new
mode's color. There was no place a message's own mode was ever recorded.

## The fix

A message's mode is now captured once, permanently, at the moment it's
created — not read from `ai_modes.current_mode()` ever again after that.

- **`ai_modes.snapshot(key)`** — new helper. Returns a small plain dict
  (`mode`, `label`, `icon`, `accent_rgb`, `accent_hex`) with no live
  reference back to `ai_modes`, so it can be stashed elsewhere and never
  drift even if `ai_modes.MODE_META` itself changes later.

- **`session.Turn`** — gained `mode`, `mode_snapshot`, plus `provider`,
  `model`, `workspace`, `simulation_id` metadata slots. `mode`/
  `mode_snapshot` are set once in `__init__` from whatever mode is active
  *right now* and never touched again for that Turn's lifetime.
  `ChatSession.add_user_turn` / `start_assistant_turn` / `add_system_turn`
  all accept `mode=` (and the assistant variant also accepts
  `provider=`/`model=`/`workspace=`/`simulation_id=`) so callers can freeze
  the right values in.

- **`ui/conversation.py` (`ConversationItem`)** — now takes a
  `mode_snapshot` and paints its border/background directly onto
  `self.styles` (an *inline* override) once, in `on_mount`, instead of
  relying on the `$accent`/`$border` stylesheet variables. Inline
  `styles.*` assignments always take priority over CSS/stylesheet rules
  in Textual and are left completely alone by `refresh_css()` — so a mode
  switch can still repaint the composer and any brand-new bubble, but it
  can no longer reach back and recolor one that's already mounted. Each
  finished bubble also renders a small icon+label badge in its frozen
  accent color (`ConversationItem._mode_badge`), so the mode a message
  was created in is visible at a glance even after ten more mode switches.

- **`ui/app.py`** — every call site that creates a `Turn` or mounts a
  bubble (`on_message_submitted`, `_maybe_answer_identity_question`,
  `_begin_assistant_turn`, `on_message_started`, `_system_note`,
  `on_permission_denied`) now passes `mode=self._current_ai_mode` (and
  provider/model/workspace where relevant) through to the Turn, and that
  Turn's `mode_snapshot` through to the conversation view. The background
  streaming worker (`_stream_worker`) also now looks up the *turn's*
  frozen `mode` instead of `self._current_ai_mode`, so an in-flight reply
  can't have its system prompt swapped out from under it if the user
  switches modes again before it finishes.

## Result

```
Notebook Mode -> blue messages
  switch to Build AI -> new messages yellow, old Notebook messages stay blue
    switch to Plan AI -> new messages green, Notebook stays blue, Build stays yellow
```

`ActiveMode` (`ai_modes.current_mode()`) now only ever affects: the
composer/input styling, and the Turn about to be created next. It never
again reaches back into already-rendered history. Render rule going
forward: **render every message from `Turn.mode_snapshot`, never from
`ai_modes.current_mode()`.**
