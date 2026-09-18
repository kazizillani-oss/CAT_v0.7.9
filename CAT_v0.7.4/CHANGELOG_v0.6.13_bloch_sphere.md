# CCT v0.6.13 — Bloch sphere command

Added `/bloch [theta_deg] [phi_deg]` — a real, exact single-qubit Bloch
sphere renderer, motivated directly by identifying image #6 in the
quantum-visualization image analysis (a Bloch sphere widget) as a
well-scoped, unambiguous, currently-missing piece of `scires.py`.

## What's real here

- `bloch_state_probs(theta, phi)` — exact Born-rule measurement
  probabilities for |psi> = cos(theta/2)|0> + e^{i phi}sin(theta/2)|1>
  in the Z, X, and Y bases.
- `bloch_vector(theta, phi)` — the standard (x,y,z) = (sin(theta)cos(phi),
  sin(theta)sin(phi), cos(theta)) identity.
- `render_bloch_sphere(theta_deg, phi_deg)` — sphere + state vector +
  exact probability bars, same visual language as the rest of `scires.py`.

## Bug caught by testing, not shipped

First draft had the Y-basis projection amplitudes backwards — conjugating
+i to +i instead of -i in the bra <+i|psi>. Caught immediately because I
tested against a known state (theta=90,phi=90, which by definition IS
|+i>) and it reported 100% probability of being |-i> instead. Fixed, then
re-verified against |0>, |1>, |+>, |+i>, |-i>, and 20 random angles (Bloch
vector magnitude == 1 exactly every time, as required for any pure state).

## Wired in

`/bloch` command (interactive + inline-args forms, both tested), `bloch_sphere`
AI tool in `agent.py` (tested — returns the exact same verified probabilities
in its summary text), registry entry with icon/examples/keywords, workspace
category `simulations`. Same class of "discard the successful retry" bug I'd
already fixed once in `cmd_ai`/`cmd_agent` was present in my first draft of
`cmd_bloch` too — caught by pattern-matching against my own prior fix before
it shipped, not by a fresh test failure this time.

## Verified

Direct physics unit tests (7 assertions across known states + random-angle
normalization), full command-dispatch tests (interactive/inline/malformed
input), AI tool path, and the full prior regression suite — all pass.
