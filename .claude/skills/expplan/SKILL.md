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
- steps 3–4: [`references/baselines-datasets.md`](references/baselines-datasets.md);
- step 5: [`references/repositories.md`](references/repositories.md).

## Reference paper and paragraph alignment

Use exactly one reference paper, authored by the current researcher and
verified in `publications.json`. Rank viable full texts by argumentative
similarity: contribution type, section progression, experiment organization,
paragraph-to-paragraph reasoning, and figure/table rhythm. Topic overlap alone
is insufficient.

Accept a local full-text transcript only when its `publications.json` record
sets `fulltext_extractor` to `code_agent`. Otherwise stop for
`/profileconstruct`; never derive source paragraphs from `pdftotext`, OCR, a
separate LLM API, or an unverified legacy TXT.

After confirmation, the executing code agent analyzes the complete verified
transcript and current scientific obligations in one coherent pass. It must
return:

- every natural paragraph of the reference paper, with stable source paragraph
  ID, heading, complete paragraph text, rhetorical purpose, relation to its
  neighbors, and any figure/table introduced or interpreted;
- the target paper's section order and paragraph count;
- one concrete planning sentence, rhetorical role, and neighbor relation for
  every target paragraph;
- an explicit mapping from every target paragraph to the most relevant one or
  more reference paragraphs, including their complete text and an adaptation
  note explaining which logical move is being imitated.

Paragraph counts need not match. A source paragraph may guide several target
paragraphs, and several source paragraphs may guide one target paragraph when
the target must compress the logic. Every target paragraph must still have a
non-empty reference mapping. Never copy the reference paper's scientific
claims, method, result, or wording into the new paper; imitate only the
argumentative move and transition logic.

Before serialization, reject any source record that begins or ends mid-sentence,
contains a page/column boundary fragment, or combines text from different
columns in the wrong order. Mapping is rhetorical rather than sequential: do
not assign source paragraphs by cursor position or round-robin order. Select
each source paragraph because its argumentative function matches the target
paragraph, and state that function in the adaptation note.

Persist the complete one-shot response in `structure_reference_analysis` and
the per-target mappings in `paper_outline`. This is the canonical input for
later paragraph-by-paragraph browser writing; do not create a separate
paper-plan file.

If no owned full text is available, stop and report what is missing. Never
substitute an external author or synthetic paper.

## Scientific design

Work backward from testable claims:

- Give each claim a stable ID, precise scope, decisive falsifier, and a chain
  from observable → raw field → computation → metric.
- Distinguish direct measurements from proxies. Narrow unsupported claims or
  add a companion direct test/control.
- Ground baselines, datasets, metrics, and protocols in retrieved experimental
  sections and result tables, not memory or titles.
- Mark variables `DIRECT`, `ADAPTED`, or `PROPOSED`; proposed variables need a
  feasibility check before supporting a headline claim.
- Include claim-complete baselines, ablations, robustness/sensitivity, failure
  analysis, and cost evidence.
- Record result-changing choices as `SEARCHED`, `FIXED_BY_SOURCE`,
  `FIXED_BY_DESIGN`, or `NOT_APPLICABLE`. `/runplan` owns execution splits and
  dev/final freezing; `/expplan` does not choose train/dev/test splits.
- Give every result target exactly one source action: `RUN_LOCAL` or explicitly
  approved `REUSE_REPORTED`.
- Set `scientific_integrity_version=1`. Every metric records a unit, evidence
  source (`BENCHMARK_LABEL`, `MODEL_OUTPUT`, `SYSTEM_TRACE`,
  `HUMAN_ANNOTATION`, `LLM_JUDGE`, or `DERIVED`), raw input fields, executable
  calculation, implementation entrypoint, and protocol checks. Claim-side
  `metric_ids` and metric-side `claim_mappings` must be exact inverses; never
  bind every metric to every claim as a convenience.
- Give every claim a deterministic `outcome_rule`. A tie, missing value,
  interval crossing the registered null, or failure to meet the registered
  margin is `inconclusive` or `weakened` as specified, never automatically
  `supported` by an LLM judgment.
- A human-named construct requires a real `HUMAN_ANNOTATION` contract with
  annotator count, item count, blinding, rubric, annotation file, and agreement
  calculation. An LLM judge is `LLM_JUDGE`, never “human agreement.”
- Every baseline and proposed method has an `implementation_verification`
  record naming the protocol source, required algorithmic components, and
  conformance tests. `method_name_in_model_prompt` must be false: prompting a
  model with a baseline name is not an implementation of that baseline.
- Represent a project-created unpublished dataset as
  `SELF_BUILT_UNPUBLISHED`, with its planned collection/versioning contract and
  no external dataset URL. Never fabricate a publication or repository link.

## Projected paper

Design the projected paper inside `reports/03_EXPERIMENT_PLAN.html`. Include:

- a working title and `PROJECTED — not results` abstract;
- every intended section/subsection and every planned paragraph;
- stable paragraph IDs, one concrete planning sentence, rhetorical role,
  previous/next relations, claims/evidence, artifact bindings, and the required
  reference-paragraph mapping described above;
- explicit subsection boundaries: on the first paragraph of each Method,
  Experiments/Evaluation, and Discussion/Analysis subsection, set a concise
  `heading` and `heading_style: subsection`; continuation paragraphs leave both
  fields empty so Paper Studio renders each heading exactly once;
- paper-shaped figure/table shells at their insertion points;
- artifact ledger, implementation plan, budget, and stop/refine/pivot criteria.

The visible report is the projected paper plan, not an experiment registry. Use
only two top-level reader-facing sections: the venue/reference and the
projected paper. Inside the projected-paper structure, render sections in the
paper's actual order. Never prepend a free-floating `5.1 Setup`, `5.2 Results`,
or other manuscript subsection number before Abstract/Introduction. Put the
dataset, model, protocol, metrics, baseline-selection rationale, and the
per-method implementation table inside the planned **Experiments** section;
put fillable result tables and figure source tables at their actual experiment
paragraphs. Keep claims, variables, decisions, budgets, and approval state in
the embedded contract unless they are expressed through that paper structure.

Render **Experimental Setup** in a fixed compact format, never as long prose.
Use a six-row `setup-table` with exactly: `Dataset`, `Model`, `Baselines`,
`Proposed method`, `Noise and runs`, and `Metrics`. State the dataset and
baseline counts explicitly. Follow it with the two-column baseline/method table;
each method gets one concise row covering selection purpose, implementation,
and its paper citation when applicable. Keep detailed metric definitions,
provenance, and acquisition contracts in the hidden JSON rather than expanding
the visible setup.

Render a detailed **Model Design** block inside the projected paper's Method
section. This is manuscript-facing design guidance, not an experiment-setup
row: specify the real input/output flow, named modules, stage boundaries,
trainable versus frozen components, objective/loss construction, update or
weighting rule, and inference path. Include the equations or algorithmic rules
needed to remove ambiguity, then bind each material component to an ablation,
diagnostic, or other falsifiable artifact. A list of subsection names, a single
high-level method sentence, or a Method overview caption is insufficient.
Store the same design under `grounding.model_design` so browser writing receives
one authoritative model specification.

Store notation once as a structured `symbol_registry`; Method equations,
algorithm steps, figure prompts, captions, and Paper Studio consume those same
symbol IDs. A figure may not introduce an alternative glyph or rename a
threshold independently.

The block must be **concise but reproduction-grade**. A competent implementer
should be able to reconstruct the disclosed model without reopening scattered
plan fields. In one compact 8--14-row table or an equivalent 250--500-word
summary, define every symbol and give: an executable end-to-end data flow;
ordered training/inference algorithm steps; exact losses, normalizations,
aggregation and update rules; candidate construction or sampling; trainable,
frozen, teacher and reference boundaries; preprocessing and model-defining
hyperparameters disclosed by the sources; and the implementation choices that
remain unknown. Do not spend this space repeating motivation, results, or
module-level rationale. Never invent a missing value: an explicit `unknown`
entry is part of a reproducible specification because it identifies what a
replicator must resolve. Record a `reproducibility_status` (`complete` or
`partial_due_to_source_omissions`) and mirror the algorithm, objectives,
configuration, unknowns, and status under `grounding.model_design`.

This requirement also applies when `/expplan` reconstructs an experiment plan
from one goal paper. In that mode, derive the model design from the goal paper's
verified method text and figures, preserve uncertainty where implementation
details are missing, and never fill a gap from the separate structural
reference. The structural reference controls rhetoric only; the goal paper is
the authority for reconstructed model content. Audit the one-goal paper for
equations, algorithms, implementation details, appendices, captions, and method
figures before assigning `reproducibility_status`; source omissions must appear
in the visible block as a compact unknowns row.

The target architecture follows the reference paper's logic but may compress,
expand, merge, or reuse its moves according to the current project's evidence.
Read [`references/projected-paper.md`](references/projected-paper.md) while
building paragraph records and evidence shells.

### Figure 1 hard rule

Introduction Figure 1 is a motivation figure by default. It must make the
problem and evidence gap understandable before revealing the method: show a
concrete failure/counterexample, why the existing observable is misleading,
and the behavioral or evidentiary criterion therefore needed. It is count-only
during `/expplan`; do not invent quantitative findings or draw final artwork.
Attach it to the Introduction gap paragraph unless the researcher explicitly
approves another role.

### Page-fill hard rule

Before approval, compare the target venue's body-page limit, the reference
paper's body proportions and content-float count, and the strongest grounded
papers' experimental coverage. The plan must contain enough substantive
experiments and result-bearing figures/tables to support a full venue paper.

If materially under-scoped, expand datasets, baselines, ablations, model/seed
sensitivity, robustness, qualitative analysis, or cost analysis as
scientifically appropriate, then revisit any affected human choices. Do not
count setup/configuration tables. If the researcher explicitly requests only a
micro study, retain the smaller scope but state the expected float/page
shortfall at the approval gate.

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
