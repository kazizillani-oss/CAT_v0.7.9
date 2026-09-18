# CAT — staged evolution deliverables

This folder holds deliverables produced for CAT's master evolution specification
(§1–§106). It is *staging*: nothing here is installed or activated in CAT yet.
Each item is independently ready for integration once CAT's Phase 0–4
migration roadmap (see `ARCHITECTURE_REVIEW_v0.7.4.md`) reaches the appropriate
milestone.

## Contents

### `agents/scientific-research-assistant/`

A new local Mavis agent designed to orchestrate research workflows through
CAT's capability bus. It is *not* a CAT mode — it is a sub-agent that any
custom mode (`BioLab`, `MLTrainer`, `QuantumResearch`, etc.) can request
help from.

**Files**

- `agent.md` — the system prompt. Required.
- `PERSONA.md` — tone and interaction style. Optional but recommended.

**How to activate**

The agent files follow the standard Mavis agent layout. To install:

1. Copy the folder to `C:\Users\ADMIN\.minimax\agents\scientific-research-assistant\`.
2. From any Mavis shell, run `mavis({ command: "agent get", args: { agent_name: "scientific-research-assistant" } })`.
3. The agent should appear in `mavis({ command: "agent list" })`.

If you prefer to register the agent via the runtime instead of manual copy,
use `mavis({ command: "agent create", args: { name: "scientific-research-assistant", description: "Scientific-research orchestration agent for CAT", display_name: "Scientific Research Assistant" } })`
and then paste the contents of `agent.md` and `PERSONA.md` into the produced
files at `C:\Users\ADMIN\.minimax\agents\scientific-research-assistant\`.

**Why it is staged, not installed**

CAT's Phase 0–4 roadmap is still in progress. Installing this agent now
would land it before the composition root (Phase 1), plugin architecture
(Phase 4), and capability registry cleanup are finished, which would force
workarounds that get undone later. Stage it here; install it after Phase 1.

### `research/quantum-sdk-integration-report.md`

A research report on how CAT should architect its capability bus to expose
real quantum SDK integrations (Qiskit 2.5+, Cirq 1.7+, PennyLane 0.45+).
The report covers:

- Current SDK landscape and Python-version constraints.
- CAT's existing quantum surface (`/bloch`, `bloch_sphere` tool, registry entries).
- The capability-as-adapter pattern that keeps quantum SDKs out of CAT modes.
- A per-SDK mapping table (capability names, I/O contracts, simulators, verification hooks).
- A four-check verification pipeline that satisfies §8 and §86 of the spec.
- Environment, GPU (CUDA + ROCm), and authentication constraints.
- A phased rollout aligned with CAT's own Phase 0–4 plan.
- The MCP-quantum ecosystem (IBM's `Qiskit/mcp-servers`, Conductor CODA, Waseda ABCI-Q).

The report's recommendation is the smallest honest quantum surface CAT can
ship: keep `/bloch` and `bloch_sphere`; add `qiskit.run_circuit`,
`cirq.run_circuit`, and `pennylane.run_qnode` adapters; gate hardware access
behind CAT's secrets manager and human-approval events.

**How to use**

The report is a working document, not a tutorial. Read it before starting
quantum-adapter implementation work; treat its verification pipeline as
non-negotiable; treat its "what NOT to do" section as a short list of
regressions to actively guard against.

## Provenance

- Research produced: 17 September 2026.
- Source SDK versions verified: Qiskit 2.5.2 (13 Aug 2026), Cirq 1.7.0 (30 Jun 2026),
  PennyLane 0.45.1 (26 Jun 2026), PennyLane Catalyst 0.15.0 (13 May 2026),
  Qiskit Aer 0.17.1, Qiskit MCP servers v0.12.0 (13 Jul 2026).
- CAT baseline audited: v0.7.4 (architecture review dated 31 Jul 2026).
- Workspace: `C:\Users\ADMIN\Downloads\CAT_v0.7.9\CAT_v0.7.4\staged\`.

## What is *not* in this folder

- No CAT core code changes.
- No new mode definitions (the spec forbids creating additional mandatory
  default modes; custom modes are user-side).
- No mock implementations, fake live activities, or placeholder execution paths.
- No quantum hardware credentials, tokens, or secrets of any kind.
