# Disruptive wildcard

Use this procedure only when `— disruptive-wildcard: on`. It produces at most one
card inside the ordinary idea report, never a standalone disruptive report.

## Contents

- Honesty boundary
- D0: Route Gravity Map
- D1: solution quarantine
- D2: drift operators
- D3: pre-literature filters
- D4: literature restoration and absorbability
- D5: reality reentry and ranking
- Required report fields

## Honesty boundary

Treat “attention drift” as **contextual-salience drift**, not a claim that prompting directly controls Transformer attention weights. Actual attention/activation intervention requires an open model and a separate experiment.

A disruptive idea is not merely distant. It must:

1. break a documented field assumption;
2. retain an evidence-backed reason it might be true;
3. propose one irreducible causal mechanism;
4. admit a cheap decisive falsifier before a large build;
5. resist absorption into the closest current route.

Reject random cross-domain analogies, renamed existing methods, impossible-resource proposals, and vague “new paradigm” language.

## D0 — Build the Route Gravity Map

Extract seven field defaults from the verified survey:

1. object of optimization;
2. representation;
3. supervision or observability;
4. causal story;
5. unit of analysis;
6. evaluation contract;
7. scale, time, or resource assumption.

For each default, record direct evidence, the anomaly it fails to explain, and confidence. Do not copy solution phrases into the blind synthesis context.

## D1 — Quarantine existing solutions

Create a compact synthesis context containing only:

- the research question;
- the Route Gravity Map defaults;
- verified anomalies, contradictions, or negative results;
- profile strengths and hard constraints;
- banned solution families and rejected prior directions.

Exclude paper titles, method names, prior idea wording, and “closest-work differentiation” prose until D4. This reduces lexical continuation of the dominant route while keeping evidence.

Complete D1–D3 before reading any previous idea report or drafting the standard slate.
After the blind seeds are frozen, the standard workflow may read prior ideas and
accumulate/rerank them normally.

## D2 — Apply drift operators

Use at least four distinct operators; generate at least one seed per operator.

- **Assumption inversion** — make a field default false and ask what mechanism becomes necessary.
- **Objective reversal** — optimize the failure the field treats as a constraint, or constrain the metric it normally maximizes.
- **Unit jump** — move the causal unit across token, step, trajectory, population, environment, or time without merely aggregating.
- **Representation discontinuity** — replace the field’s representational primitive rather than adding another encoder, loss, or head.
- **Causal primitive swap** — replace correlation/prediction with intervention, conservation, competition, market, game, or control only when the new primitive explains a verified anomaly.
- **Boundary shift** — move the phenomenon across training/inference, model/environment, individual/collective, or short/long horizon.
- **Missing-observation world** — remove a supervision signal, modality, label, or state that every current method assumes and derive a testable mechanism that can still operate.

Remote analogy is allowed only after mapping structural roles one-to-one. Surface analogies and domain-name swaps fail.

For each seed write: `anomaly → broken assumption → drift operator → core mechanism → predicted signature → decisive falsifier`.

## D3 — Pre-literature filters

Before restoring paper names, reject a seed if any answer is bad:

- **Evidence tether:** Which verified anomaly makes the mechanism plausible?
- **Irreducibility:** Does the contribution remain one mechanism rather than A+B?
- **Program break:** Would success require changing the dominant causal story, not just adding a component?
- **Falsifiability:** Can one small test make the central mechanism clearly less likely?
- **Specificity:** Does the idea name observable variables and an intervention or prediction?
- **Non-fantasy:** Is the first decisive test possible with available or plausibly available data/compute?

Do not rescue a failing seed with more modules.

## D4 — Restore literature and test absorbability

Reintroduce paper titles, prior idea wording, the newly drafted standard slate, and the
last 3–6 months of work. Search narrowly for each surviving mechanism.

Ask: could the closest work absorb this as an extra module, loss, prompt, data slice, benchmark axis, or scale run while preserving its central causal story?

- **Yes** → `incremental/absorbed`; remove from disruptive slate and retain in the audit.
- **Unclear** → `directional`; keep only with explicit uncertainty.
- **No, and collision search is verified** → eligible for `disruptive`.

Also check against the researcher’s own work. Personal fit cannot substitute for program break.

## D5 — Reality reentry and ranking

Score each eligible survivor independently:

- **Paradigm break (0–10):** distance in causal story, not vocabulary.
- **Evidence plausibility (0–10):** strength of anomaly and mechanism link.
- **Falsifiability (0–10):** decisiveness and cost of the first test.
- **Leverage / option value (0–10):** how much follows if the mechanism is true.
- **Feasibility risk:** `LOW|MED|HIGH|uncertain`, decomposed into compute, data, and code reuse when feasibility support is active.

Compute a visible **Disruptive score** as the arithmetic mean of the four 0–10 axes.
Rank only after writing the strongest skeptical objection. High feasibility can break
a score tie; high cost does not make an idea disruptive, and ordinary implementation
difficulty alone does not kill a high-option-value idea when its first falsifier is
cheap. Select only the highest-scoring eligible survivor and rename it `D1`.

Retain rejected/absorbed seeds in a compact audit table. Do not emit the remaining
eligible seeds as additional cards, and never compare the Disruptive score to a
standard idea's Novelty score.

## Required report fields

Keep the ordinary report and set
`<main data-idea-branch="standard" data-disruptive-wildcard="present">`. Place the
wildcard section after every standard idea card and before the final joint
devil's-advocate/pick gate. The single wildcard card must be
`<article data-disruptive-id="D1">` containing these visible labels:

- One-sentence pitch
- Verified anomaly
- Broken assumption
- Drift operator
- Core mechanism
- Why the current route cannot absorb it
- Predicted signature
- Decisive falsifier
- Minimum viable evidence
- Closest work and collision verdict
- Own-work check
- Paradigm break
- Evidence plausibility
- Falsifiability
- Leverage / option value
- Disruptive score
- Feasibility
- Strongest reviewer objection

If nobody survives, use
`data-disruptive-wildcard="shortfall"`, emit no disruptive card, and show the compact
failed-gate audit in the wildcard section. If the feature is explicitly disabled, use
`data-disruptive-wildcard="off"` and emit neither the card nor the audit.

Stop at the human pick gate.
