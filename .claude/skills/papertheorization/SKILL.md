---
name: "papertheorization"
description: "Distill this work into ONE unified mathematical framing — a single central object with 2–4 load-bearing results stated in the body and derivations/proofs in an appendix. Gates every formal statement on necessity (non-redundant), usefulness (load-bearing), and unity (one centre), and MECHANICALLY checks each derivation (Lean if available, else sympy/numeric) before it is written. A review sub-skill of /paperwrite; also usable standalone. Invoke when the user says \"formalize this\", \"add theory\", \"build a unified theory\", \"unify the theory\", or /papertheorization."
---

# papertheorization

Turn this work into theory a top-venue reviewer respects: a unified formalization
whose results earn their place. The failure mode this skill exists to prevent is
**decorative math** — scattered definitions and a trivial lemma bolted on to look
rigorous. Better no theory than loose theory.

This is a review sub-skill of `/paperwrite`. It reads the same inputs
(`researcher-profile/PROFILE.md` at the project-local `researcher-profile/` path, `reports/03_EXPERIMENT_PLAN.html`,
`results/`) and writes into `paper/`.

## Ground it in the researcher's own theory lineage first

Before inventing a frame, read her closest theory-`task_type` paper in
`researcher-profile/fulltext/txt/` (e.g. the CRH / representation-geometry line). Reuse
**her** central object and notation where they fit — a paper that extends her own
formal frame reads as lineage, not a bolt-on. Never contradict a result she has
already published; scope to it.

**When invoked by `/paperwrite`, use the passed personalization context, not an
independent pick:** ground the spine in the SAME `reference_paper` paperwrite chose as
the structural reference (do not select a different one), write the result statements and
their load-bearing sentences in the `writing_style` voice, and hand the new statements to
paperwrite's shared `anti_self_plagiarism` pass so a theorem's prose is not a near-copy of
one of her prior papers. Standalone (`/papertheorization`), fall back to reading the
profile yourself.

## Three gates (a result is written only if it passes all three)

1. **Necessity (non-redundant).** Would removing this formal statement lose anything
   the prose did not already say plainly? If the equation just restates a sentence,
   cut it. Formalize only what is clearer, sharper, or newly true in symbols.
2. **Usefulness (load-bearing).** Name the argument each result supports. A result
   must do one of: justify a design choice, **predict a measured number in
   `results/`**, explain an otherwise-awkward empirical fact, or bound a cost. If it
   supports nothing, cut it.
3. **Unity (one centre).** Introduce a single mathematical object — a field, a metric
   space, an operator, a dispersion functional — and make every lemma a statement
   about *that* object. No patchwork. The reader carries one picture through the whole
   theory section, each step a short hop from the last.

If this work cannot support a unified, useful, non-redundant theory, say so and write
none — recommend strengthening the empirics instead. Honest absence beats forced
formalism. (For an `engineering`/`benchmark` `task_type` paper, a light formal spine
— one definition + one proposition — is often the right amount; do not force a
theorem where a crisp definition suffices.)

## The rigor gate (mechanical check before writing)

A statement reaches the paper only after its derivation has been checked by a tool,
not by vibes:

- **Lean** (preferred, if `lean`/`lake` is on PATH): state the proposition and prove
  it; write the paper statement only once `lake build` is clean. Keep the `.lean`
  under `paper/theory/` and cite it in the appendix.
- **sympy / numeric** (fallback, always available): `python3 paper/theory/verify.py`
  — verify every algebraic identity, limit, derivative, variance, inequality
  symbolically; for analytic claims that resist symbols, verify on a dense numeric
  grid and report the check. Keep the script committed.
- **Assumptions are explicit.** State each assumption, label it, and say whether it is
  proven, standard, or empirical. Never upgrade an assumption to a fact.

Write the result, its assumptions, and a one-line "verified by `theory/verify.py`"
note. If a check fails, the statement is wrong — fix the statement, not the check.

## Workflow

1. **Find the centre.** What single object captures the method? Write its definition
   first; everything hangs off it.
2. **List candidate results**, then run each through the three gates. Keep 2–4.
3. **Verify** each survivor with Lean/sympy (`paper/theory/verify.py`).
4. **Place them.** Body: the central definition, the result *statements*, and the one
   sentence each buys. Appendix (`paper/sections/app_derivations.tex` or the
   appendix block in `main.tex`): assumptions, full derivations/proofs, the
   verification note. Keep body math minimal but real — a few numbered equations that
   are referred to later.
5. **Tie to data.** The strongest theory predicts a number you already measured
   (`results/`). Point the body result at the table/figure it explains.

## Output
- `paper/theory/verify.py` (or `paper/theory/*.lean`) — the mechanical checks, runnable.
- Body edits: central definition + result statements + their load-bearing sentence.
- The derivations appendix: assumptions, derivations, verification note.
- `paper/theory/NOTES.md` — which candidate results were cut and why (gate failures) —
  evidence the formalization is disciplined.

## Anti-patterns (reject these)
- A "Theorem" that is a running max being monotone, or a definition used nowhere.
- Three unrelated bounds with different notation — patchwork, not unity.
- A proof sketch with "it can be shown" — either show it (checked) or drop it.
- Theory that contradicts the experiments (or her prior papers) — fix or scope the claim.
