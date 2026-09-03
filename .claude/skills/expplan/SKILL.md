---
name: "expplan"
description: "Design the scientific experiment program and reference-aligned target-paper structure for a chosen idea. Defines claims, falsifiers, baselines, datasets, metrics, ablations, budgets, paragraph mappings, and fillable result artifacts in reports/03_EXPERIMENT_PLAN.html for researcher approval. Stops before execution. Invoke explicitly as `/expplan`."
---

# Experiment Planning

Run once per project session:

```bash
python3 -m research_avatar.research_studio.server --ensure
```

Research Studio is served at `http://127.0.0.1:8780`. Surface startup errors.

`/expplan` decides what the project must test and the exact paper architecture
that later browser writing follows. It does not run experiments or draft final
manuscript prose. `/runplan` later turns the approved evidence contract into
executable goals.

`reports/03_EXPERIMENT_PLAN.html` is a rendered artifact. Any correction must
change the planning contract, source analysis, template, or generator that
caused it, then regenerate and validate the complete HTML through a temporary
file before atomic replacement. Never hand-edit, string-replace, or inject a
correction into the delivered HTML.

## Inputs

Read:

- `researcher-profile/PROFILE.html`;
- `researcher-profile/publications.json`;
- the explicit idea, otherwise the `SELECTED` idea in
  `reports/02_IDEA_REPORT.html`.

If profile records are missing, stop for `/profileconstruct`. If an idea report
exists without a selected idea, ask the researcher; never guess. A complete
free-text idea is also valid.

## Decision order

Resolve these gates in order:

1. target conference;
2. one researcher-authored reference paper;
3. baseline set and reported-result reuse actions;
4. dataset/benchmark set;
5. implementation architecture and repository authority;
6. projected-paper and experiment contract;
7. final researcher approval.

Stop for explicit confirmation at each gate. Read these detailed procedures only at their corresponding stage:

- steps 1–2: [`references/venue-and-reference.md`](references/venue-and-reference.md);
- step 3: [`references/baselines.md`](references/baselines.md);
- step 4: [`references/datasets.md`](references/datasets.md);
- step 5: [`references/repositories.md`](references/repositories.md).

## Reference paper and paragraph alignment

Use exactly one researcher-authored reference paper with a verified Code Agent
transcript. It controls argumentative moves and paragraph transitions, not the
new paper's scientific content. Map every target paragraph to one or more
complete source paragraphs by rhetorical function, and persist the full
analysis in `structure_reference_analysis` and `paper_outline`.

Read [`references/venue-and-reference.md`](references/venue-and-reference.md)
while selecting, extracting, checking, and mapping the reference paper.

## Scientific design

Work backward from falsifiable Claims and deterministic acquisition paths.
Keep measurements, gold state, dataset applicability, method conformance,
outcome decisions, and human evidence mechanically auditable. New plans use
`scientific_integrity_version=3`.

Read [`references/scientific-integrity.md`](references/scientific-integrity.md)
while defining Claims, metrics, protocols, evidence sources, and outcome gates.

## Projected paper

Design the complete target paper inside `03`: title, projected abstract, every
section/subsection and paragraph, reference-aligned rhetorical moves,
reproduction-grade Method design, compact Experimental Setup, inline result
shells, artifact ledger, and a page-fill contract. The visible report remains
paper-shaped; machine registries stay in the embedded contract.

Use one authoritative symbol registry and one model-design specification.
Conceptual figures remain count-only at this stage, with an explicit
`figure_type`; every empirical table cell or plotted value has exactly one
result requirement. Discussion paragraphs bind the exact result artifact they
interpret. Scope the evidence so the planned paper can honestly fill the venue
limit without duplicate or scientifically empty experiments.

Read [`references/projected-paper.md`](references/projected-paper.md) while
building the paragraph architecture and model design. Read
[`references/artifact-shells.md`](references/artifact-shells.md) only while
defining figures, tables, source cells, and fixtures. Read
[`references/page-fill-and-contract.md`](references/page-fill-and-contract.md)
only while checking venue coverage, serializing the contract, and presenting
the approval gate.

## Canonical output

Write one self-contained HTML file:

`reports/03_EXPERIMENT_PLAN.html`

Embed exactly one JSON object:

```html
<script type="application/json" id="experiment-plan-contract">…</script>
```

The HTML is the canonical plan; do not create a sidecar manifest. Use stable
claim, experiment, artifact, label, result-requirement, variable, metric,
decision, source-paragraph, and target-paragraph IDs. Every numeric table cell
or figure source cell maps to exactly one result requirement and source action.

Read [`references/contract-and-html.md`](references/contract-and-html.md) only
while serializing and validating the final contract.

## Approval

Reject the draft before the gate if any claim lacks a falsifier/measurement
chain, any target paragraph lacks its complete reference mapping, any artifact
lacks a paragraph binding and fillable shell, any numeric target lacks one
deterministic source, or any researcher-controlled decision is unresolved.

Run:

```bash
python3 research_avatar/tools/validate_report_structure.py --kind expplan --html reports/03_EXPERIMENT_PLAN.html
python3 research_avatar/tools/validate_experiment_plan.py --plan reports/03_EXPERIMENT_PLAN.html
```

Fix all failures, ask the researcher to `approve` or `revise`, and stop. On
approval, bind the approval to the current `contract_version`. A scientific or
artifact amendment increments the version, records the parent digest, resets
approval to `pending`, and returns here. Presentation-only regeneration may
preserve approval.

For explicit fabricated pipeline tests, show
`SKILL-TEST — fabricated data, NOT a scientific result` and keep projected
values pending.
