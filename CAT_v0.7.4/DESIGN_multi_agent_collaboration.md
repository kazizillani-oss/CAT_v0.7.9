# Multi-Agent Collaboration — Design Doc (v0.7.2 roadmap)

Status: design only, no code in this pass. Written after the EventBus,
Session Timeline, AI Todo Manager, and Project Dashboard slices landed
(see CHANGELOG_v0.7.2_context_menu_and_clear_recent.md), since this
design leans on the EventBus existing already.

## 1. What the roadmap actually asks for

> Notebook AI → Plan AI → Build AI → Agent AI → Review AI, each
> communicating through shared project context, multiple agents
> working simultaneously, pause/resume/stop, manual task assignment,
> future custom agents.

Two different features are bundled under one name here, and they have
very different costs:

- **(A) Sequential agent handoff** — one agent's output becomes the
  next agent's input (Notebook → Plan → Build → Agent → Review), no
  two running at once. This is close to what CCT already has: modes
  already exist (`ai_modes.py`), turns already carry `mode` metadata
  (`session.Turn`), and "Try Again in Build Mode" (the July context-
  menu work) already proves the mechanics of switching mode and
  regenerating against the same conversation. Sequential handoff is
  mostly a UI/orchestration layer on top of what's already there.

- **(B) True parallel multi-agent execution** — multiple agents
  running *at the same time* against the *same workspace*, each able
  to read/write files, each burning API budget concurrently. This is
  a materially different system: it needs a locking/merge story for
  concurrent file writes, a way to show N independent output streams
  at once, a cost model (parallel agents multiply API spend linearly,
  immediately), and a permission model that still makes sense when
  it's not one human approving one AI's next action but potentially
  several AIs wanting to touch the filesystem near-simultaneously.

Recommendation: **build (A) first, design (B) but don't build it until
(A) has real usage to learn from.** The roadmap's own "Future support
should allow custom agents" line suggests even the roadmap's author
expected this to grow in stages rather than launch complete.

## 2. Why this needs its own slice, not a bolt-on

Everything else in this drop (Timeline, Todo, Dashboard) is additive:
it reads events, writes to its own store, and has an off switch (don't
open the panel, nothing changes). Multi-Agent Collaboration is not
additive in the same way — it changes what "the conversation" means.
Today, `session.ChatSession.turns` is one linear list and
`CCTApp._current_ai_mode` is one active mode; introducing agents that
run independently means either:

- multiple concurrent `_stream_worker`-style workers writing into the
  same turn list (needs real interleaving/ordering rules — whose turn
  appears where when two finish in the same second?), or
- each agent gets its own sub-conversation that gets merged back
  (needs a merge UI and a "whose edit wins" story when two agents
  touched the same file).

Either choice is a real architecture decision with UX consequences,
which is exactly why this doc exists instead of code: picking wrong
here is expensive to undo once conversations/turns/permission state
depend on it.

## 3. Proposed architecture (Phase A: sequential handoff)

### 3.1 AgentManager (new: `calc_terminal/agent_manager.py`)

Owns a **pipeline**: an ordered list of `(agent_role, mode)` steps
(e.g. `[("Notebook", "notebook"), ("Plan", "plan"), ("Build", "build"),
("Agent", "agent"), ("Review", "agent")]` — "Review" reuses Agent mode
with a different system-prompt persona rather than inventing a sixth
`ai_modes` entry, matching how `_stream_worker` already picks
`AGENT_SYSTEM_PROMPT` vs `AI_SYSTEM_PROMPT` by persona, not by mode
key).

Each step is exactly one `_regenerate_turn`/`_begin_assistant_turn`
call under the hood — the July work already proved this mechanism.
AgentManager's actual new job is **sequencing**: given step N's output,
decide (a) is step N+1 triggered automatically or does it wait for the
user to confirm, and (b) what's the prompt for step N+1 (the roadmap
doesn't say "feed the previous agent's raw output as the next prompt"
literally — that's a design choice, see open questions below).

```
AgentManager.start_pipeline(pipeline, initial_prompt)
AgentManager.pause()   # stops advancing to the next step; current step finishes
AgentManager.resume()
AgentManager.stop()    # cancels the in-flight step's worker (Textual
                        # workers already support .cancel())
AgentManager.status()  # -> which step is active, which are done/pending
```

Publishes to the EventBus (new topics: `agent_step_started`,
`agent_step_finished`, `agent_pipeline_completed`) so Timeline records
pipeline activity automatically, the same way it already picks up
`AI_RESPONSE_GENERATED` — Timeline needs zero changes for this.

### 3.2 Manual task assignment

"Allow the user to... Assign tasks manually" maps naturally onto the
Todo Manager that already exists: a todo can carry an optional
`assigned_agent` field (small addition to `todos.py`'s schema), and
AgentManager can offer "run this todo through the Build agent" as an
action from the Todo panel. This reuses existing infrastructure
instead of building a second task-tracking system inside
AgentManager.

### 3.3 Status indicators

`AgentManager.status()` is enough for a status widget (a small
footer/header badge — "Build agent: running (step 3/5)") using the
exact same Static-update pattern `StatusLine`/`BrandHeader` already
use. No new widget architecture needed here.

## 4. Proposed architecture (Phase B: true parallel agents)

Sketched for completeness, **not being built now**:

- Each concurrent agent gets its own `ChatSession` fork (the Fork
  Conversation mechanism from the July context-menu work already
  does exactly this: `ChatSession.fork_upto()` produces an
  independent session sharing the same workspace/mode snapshot). A
  parallel agent run is, structurally, "fork, then let an agent drive
  the fork instead of a human."
- File writes need a real lock, not just a permission prompt: a
  workspace-level `FileLock` keyed by path, so two agents can't both
  be mid-write to the same file. `agent.py`'s existing
  write_file/create_folder/delete_file/rename_file tools are the
  choke point where this would need to live.
- UI needs a way to show N streams — likely a tabbed or split view
  per active agent, which is a real Textual layout problem (this
  package's screens are built for one focused conversation at a
  time) — not solvable by reusing `ConversationView` as-is.
- Cost: parallel agents should probably require an explicit
  confirmation of estimated concurrent token spend before starting,
  the same instinct behind the existing execute_python permission
  gate, just for money instead of code execution.

## 5. Open questions that need a decision before Phase A starts

1. **What's the prompt for step N+1?** Verbatim output of step N?
   A summarized version? User-editable before it's sent (like Rewrite
   already lets you edit a resend)? This materially changes output
   quality and is a product decision, not an engineering one.
2. **Auto-advance or confirm-each-step?** The roadmap's diagram reads
   like an automatic pipeline, but that also means one bad step
   silently poisons every step after it. A "confirm before advancing"
   default (with an explicit "auto-run the rest" opt-in) is probably
   safer, mirroring this codebase's existing bias toward confirming
   before consequential actions (the permission-gate pattern).
3. **Failure handling**: if step 3 of 5 errors out, does the pipeline
   stop, retry that step, or skip to step 4 with degraded context?
4. **Cost visibility**: a 5-step pipeline is 5x the API calls of one
   turn. Worth showing an estimated step count/cost before starting,
   not just after.

## 6. Suggested phased rollout

1. AgentManager + sequential pipeline UI (Phase A above), manual
   "run pipeline" trigger only, confirm-each-step default.
2. Manual task assignment via Todo Manager integration.
3. Auto-advance as an opt-in setting, once step-quality is understood
   from real usage.
4. Revisit Phase B (true parallelism) only after 1–3 have real usage
   data on where sequential hand-off actually falls short — building
   the harder, riskier version first without that data would be
   guessing.
