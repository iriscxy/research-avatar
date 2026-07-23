---
name: paper-gap-check
description: Find where the paper lacks the evidence its argument needs, so the writer never papers over a hole with hand-waving, overclaiming, or a fabricated number. For each gap it either reserves a clearly-labelled placeholder (a hypothesis-marked figure/table that keeps structure and logic stable) or records the gap, and emits a single paper/EXPERIMENT_PLAN.md saying exactly which experiment would fill each gap. A review sub-skill of /paper-write; also usable standalone. Invoke when the user says "content gap", "what's missing", "check for gaps", "find weaknesses", or /paper-gap-check.
---

# paper-gap-check

The fabrication risk in AI paper-writing is structural: the draft commits to a
narrative, then a needed result is missing, and the model invents a number, a
mechanism, or a "clearly" to keep the paragraph whole. This skill makes the honest
move the easy one — surface the hole and route it to an experiment, rather than fill
it with prose.

Review sub-skill of `/paper-write`. Numbers come from `results/` (our single source of
truth here — the equivalent of watson's `evidence.json`). Converse in the user's
language (Chinese here). This skill is mostly mechanical, so it uses only one field of
the personalization context: **`reference_paper`'s Experiment Templates** (her
toolchain / base model / GPUs), so a planned experiment's cost estimate matches her
actual stack rather than a generic guess.

## What counts as a gap
A gap is a place where the argument *requires* support the evidence does not provide:
- A claim with no number behind it (no matching file in `results/`).
- A comparison the data does not actually make (missing baseline, missing target,
  wrong split, n too small to distinguish, an ablation that saturates).
- A mechanism asserted ("because the steer is routed away…") with no measurement
  isolating it.
- A scope claim ("generalizes to…") evaluated on one setting/model.
- A figure/table the structure expects but the data cannot fill.
- A defense/limitation the reader will demand that is not addressed.

Distinguish a **gap** (needs *evidence*) from a **weakness** (needs *honest
disclosure*). Weaknesses go in Limitations, plainly stated. Gaps go to the plan.

## Dry-run note (this project)
When `results/` is watermarked **SYNTHETIC** (a dry run), do NOT treat missing real
data as a gap to "fill now" — the whole results set is a placeholder by design. Here
gap-check's job is to verify the *paper's structure* has a real slot for every claim
and that every synthetic figure/table is visibly marked, then list what real
experiments `/run-plan` must produce. On a real run, apply the two responses below.

## Two responses per gap

1. **Reserve a slot** (when the structure needs the float to stay coherent). Insert a
   labelled placeholder that holds the position and states the *expected* result as a
   hypothesis, clearly marked as not-yet-measured:
   - a figure generated with **clearly-labelled synthetic data of the expected shape**
     (the `paper/fig/make_figs.py` matplotlib convention paper-write already uses),
     tagged `[SYNTHETIC / pending]` in the caption;
   - a table with a `% pending` comment and a caption ending "(pending)".
   The body references it in the conditional/forward voice ("we expect …; Table X,
   pending"), never as a finished result.

2. **Plan the experiment.** Every gap gets an entry in `paper/EXPERIMENT_PLAN.md`
   (paper-local — the holes THIS draft needs filled; distinct from the pipeline's
   `outputs/03_EXPERIMENT_PLAN.html`, though a confirmed gap should be echoed back to
   `/run-plan`).

## paper/EXPERIMENT_PLAN.md (the single output that closes the loop)
One file. Per gap:
```
## GAP-<id>: <one-line description>
- Claim it supports: <the sentence/section that needs it>
- Why current evidence is insufficient: <missing baseline / small n / no isolation / ...>
- Experiment: <design — datasets, models, conditions, the one comparison it makes>
- Metric & success criterion: <what number, what threshold decides the claim>
- Estimated cost: <runs × GPUs, rough wall-clock — match her Experiment Templates>
- Paper artifact it fills: <Table/Figure/sentence + the reserved label, if any>
- Risk if unfilled: <does the paper still stand? downgrade the claim to what?>
```
Order gaps by **risk to the paper** (claims that collapse without them first). End
with a **minimal set** — the smallest subset of experiments that lets every body
claim stand without a reserved/pending slot.

## Workflow
1. Read the compiled paper and every file in `results/`. Build the claim→file map.
2. Walk each section's claims; for each ask "what evidence makes this true, and do we
   have it?" Classify: supported / weakness (disclose) / gap (reserve+plan).
3. For gaps: reserve a slot if structure needs it; always add a plan entry.
4. Write `paper/EXPERIMENT_PLAN.md`; report the gap list and which claims are currently
   propped by reserved slots vs fully supported.
5. Re-run after experiments land: the plan is the checklist; a gap closes when its
   reserved slot is filled by a real figure/table from new `results/`.

## Grounding audit (fresh sub-agent — the producer never blesses its own grounding)
Before the gap list is final, **spawn a separate sub-agent** (Agent tool) to
adversarially audit grounding — it must NOT be whoever wrote the prose. Give it the
compiled paper + every file in `results/` and have it check, claim by claim:
- **every number** in the body/tables traces to a real file in `results/` (or is marked
  `[UNVERIFIED]`/`[SYNTHETIC]`) — no number restated from memory or rounded into existence;
- **every `\cite`** actually supports the sentence it is attached to (no citation used as
  decoration for a claim it does not make);
- no "clearly/obviously/it is well known" standing in for a missing measurement.
The auditor returns a review queue of suspect number↔claim and citation↔claim pairs; each
becomes a gap (downgrade / reserve / plan) — never waved through. This is how an overclaim
is caught against the project's own logs; trust the audit over the draft.

## Honesty rules
- Never convert a gap into a confident claim. Downgrade, reserve, or plan.
- A reserved slot's hypothesis is labelled as such in the source and caption; it must
  read as pending to any reviewer.
- Prefer cutting an unsupported claim over reserving a slot for it, unless the
  surrounding argument genuinely needs the placeholder to stay coherent.
