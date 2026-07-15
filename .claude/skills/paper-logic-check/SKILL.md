---
name: paper-logic-check
description: After a paper is drafted, check that its narrative logic is tight — that each section resolves the needs earlier sections raised (or states its own role), that every argumentative need is answered nearby, that reader understanding-cost is low, and that the whole reads as one closed loop with no dead ends. Combines a deterministic cross-reference map (grep-built, no external program) with a fresh agentic read of the compiled PDF. A review sub-skill of /paper-write; also usable standalone. Invoke when the user says "逻辑检查", "narrative logic", "叙事检测", "does it flow", "逻辑闭环", or /paper-logic-check.
---

# paper-logic-check

A paper can pass every mechanical check and still not "flow": a section that answers a
question nobody asked, a claim whose support sits three sections away with no signpost,
a forward promise that is never kept. This skill catches those.

Review sub-skill of `/paper-write`. Converse in the user's language (Chinese here). This
is the **deliberate exception** to personalization threading: narrative-logic checking is
author-agnostic and takes NO personalization context — a paper's loop either closes or it
does not, regardless of whose paper it is.

## Step 1 — cross-reference map (grep-built, no external program)
Build the section-to-section reference graph directly from the source (this replaces
watson's `paperkit xref`):
- Collect every `\label{...}` and every `\ref{...}` / `\autoref{...}` / `\Cref{...}` /
  `"Section~\ref"` / `"Appendix~\ref"` in `paper/main.tex` (and any `paper/sections/*.tex`)
  with `grep -nE`.
- Map each `\ref` to the section that owns the matching `\label`, giving a "who points
  to whom" edge list. Print: the edge list, sections **nobody references**, and
  **orphan** sections (neither point out nor are pointed to).
Orphans and one-way dangles are the first suspects: a section the rest of the paper
never needs, or a forward reference with no payoff.

## Step 2 — agentic narrative read (fresh reviewer)
**Spawn a fresh sub-agent** (Agent tool — keep the reader separate from whoever wrote
the prose) that reads the *compiled* `paper/main.pdf` end to end (not the source
fragments) with the Step-1 map in hand, and answers, per section and overall:

1. **Role.** Does this section resolve a problem an earlier section raised, or clearly
   establish a need later sections use? State each section's job in one sentence. A
   section whose job you cannot state is a problem.
2. **Local support.** For every argumentative need the section opens (a claim demanding
   evidence, a term demanding a definition, a choice demanding a justification), is the
   answer *nearby* — same section, next one, or foreshadowed earlier — and is the
   reader pointed to it? Flag needs whose answer is far away with no signpost, and
   answers that arrive before the need is set up.
3. **Understanding cost.** Where must the reader hold too much in their head, jump
   around, or infer an unstated link? Name the highest-cost spots and the missing
   bridge sentence that would fix each.
4. **The loop.** Does the whole close? The problem posed in the Introduction should be
   the problem the Conclusion claims to have addressed; every promised contribution
   delivered and pointed back to; no thread left dangling. List any open thread.

The agent returns: a per-section role+support verdict, the ranked weak links, and for
each a concrete one-line fix (usually a bridging sentence, a forward/back reference, or
a reorder). It reads as a hostile reviewer, not a defender.

## Step 3 — fix and re-check
Apply the fixes (bridge sentences, signpost references, the occasional reorder),
recompile, and re-run Step 1. Iterate until every section's role is clear, every need
is answered nearby, and the loop closes. Prefer a one-sentence signpost over a
structural change; restructure only when a section genuinely sits in the wrong place.

## Guardrails
- A bridging sentence states a *real* logical link; do not paper over a missing
  argument with a transition. If the support genuinely is not in the paper, that is a
  content gap — route it to `paper-gap-check`, do not write a smooth sentence over it.
- Keep the producer and the checker separate: the agent that reads for logic is not
  the one that wrote the prose.
