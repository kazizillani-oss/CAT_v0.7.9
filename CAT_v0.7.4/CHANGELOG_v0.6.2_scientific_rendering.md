# CCT v0.6.2 — Scientific Rendering Engine (Spec Section 1)

Implements the first section of `CCT Scientific Computing Engine v0.6.0
official{Bad-Bricks Edition}`: mathematical text should never reach the
screen as raw Markdown/LaTeX — it should come out looking like a
textbook. Nothing existing was rewritten; this only *extends*
`calc_terminal/mathtext.py` (the module every notebook render already
funnels through via `mathify()`) and wires one new call into the
assistant-message path in `calc_terminal/ui/conversation.py`.

## What's new — `calc_terminal/mathtext.py`

A new pipeline, `render_math(text)`, sits alongside the existing
`mathify()`/`sub()`/`sup()`/`compose()` (all untouched, all still work
exactly as before). It's fenced-code-aware (never touches real code
blocks) and only fires on explicit math markers, so ordinary prose is
never altered. It handles:

- **Fractions** — `\frac{A}{B}` → a real 3-row stacked bar (reuses
  `compose()`), dropped in as its own fenced block so Markdown
  preserves the monospace alignment. Nested `\frac`/`\sqrt` inside a
  numerator or denominator recurse correctly.
- **Square roots** — `\sqrt{X}` → `√` with a Unicode combining
  overline across `X` (`√̅2̅K̅E̅/̅m̅`), recursing on the radicand.
- **Superscripts / subscripts** — explicit `x^2`, `x^{12}`, `H_2`,
  `psi_{100}` → Unicode (`x²`, `x¹²`, `H₂`, `ψ₁₀₀`). Only fires on a
  literal `^`/`_`, so plain numbers like "15" are never touched.
- **Greek letters** — `alpha…omega`, `pi`, `\delta`, etc. → `α…ω`,
  `π`, `Δ`, case- and word-boundary-aware (`pie` is left alone).
- **Scientific notation** — `6.022e23` → `6.022 × 10²³`.
- **Matrices** — `\begin{bmatrix}…\end{bmatrix}` (and `matrix` /
  `pmatrix` / `vmatrix`) → a bracket-bordered Unicode grid.
- **LaTeX noise** — `\times \cdot \pm \geq \leq \approx \infty
  \rightarrow …` → their Unicode glyph; `\left \right \quad $ $$ \[ \]`
  are dropped since they're purely cosmetic.
- **Chemistry notation** — new `chem_formula()` helper: `SO4^2-` →
  `SO₄²⁻`, `NH4+` → `NH₄⁺`, `CaCO3` → `CaCO₃`. Correctly distinguishes
  a caret-prefixed charge magnitude from a bare trailing sign (so
  `NH4+` reads N, H₄, +1 — never "charge 4").
- `mathify()` (used by `engine.py`/`report.py`/`app.py` for computed
  notebook lines) now also normalizes explicit `^`/`_` markup and
  Greek words — same backward-compatible signature, same callers,
  no call sites needed to change.

## Wiring — `calc_terminal/ui/conversation.py`

Assistant turns now run through `mathtext.render_math()` *before* the
existing chemistry highlighter and Rich's `Markdown` renderer ever see
the text — this is the actual fix for "raw Markdown/LaTeX occasionally
leaks through," since that's the one place AI-generated text reaches
the screen. The chemistry-formula highlighter (`_highlight_chemistry`)
now also calls `chem_formula()` so recognized formulas get real
Unicode sub/superscripts, not just an inline-code backtick wrap.

## Still open from Section 1

Determinants, standalone vector arrows, integral/summation/limit
glyphs, and piecewise braces aren't implemented yet — matrices,
fractions, roots, sub/superscripts, Greek, scientific notation, and
chemistry formulas were prioritized first since they're what the
solver/report pipeline actually emits today. Good next slice if you
want it.
