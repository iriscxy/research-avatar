# Projected paper, artifacts, and approval

Design the paper claim-first and backward from the projected abstract.
**Reader-facing opening — write the conference and reference first, then the projected paper.** Use `1. Target Conference and Reference Paper` for exactly two entries: target conference and the sole researcher-owned reference. Keep the official-rules link inside the target-conference entry. Do not include the research question, object of study, implementation architecture, datasets, metrics, baselines, or any other setup material there. Immediately follow it with `2. Projected Paper`, containing parts (a)–(c). Do not create later top-level report sections for claims, implementation, budget, or approval; those are contract concerns whose paper-facing consequences belong in the projected structure.

(a) **Projected Title + Abstract** — immediately **above the abstract, draft a working paper title** (`<h2>`-sized, styled as a title): a concrete, non-generic title naming the idea's ONE core mechanism (a short name + a claim-bearing subtitle is fine, e.g. "ABD++: One Modality-Invariant Harmful Axis for Deployable Jailbreak Defense"), not a topic label. It should read like a real paper title and match the idea's single mechanism — if the best honest title still sounds like "technique A applied to domain B", that is a signal the idea is a mashup (flag it, don't dress it up). Then the **projected abstract** — the abstract the paper *would* have if the idea succeeds, in her *Writing Style* (gap-first, "We propose/release" bullets). Mark **PROJECTED — not results**; every number a placeholder `[X%]`, never fabricated.
   - Derive a target length band from the venue's official abstract rule when one
     exists; otherwise use the confirmed researcher-owned reference's measured
     abstract length as the center of a reasonable band. Do not impose one universal
     word count. Require the complete rhetorical sequence: motivation · precise gap ·
     method · evaluation scope · 1–2 result-with-placeholder sentences · takeaway;
     an abstract below the band or missing a role is incomplete, not merely concise.
   - **No em-dashes, no rare words**; use common words and keep only genuine terms of art.
   - **abstract↔claim self-check:** map each abstract claim-sentence to a §1 claim; a sentence with no backing experiment gets cut or gets an experiment.
(b) **Projected Paper Blueprint (write right after the abstract, INSIDE `03`)** — show the paper that will be written, not merely a list of experiments. Use the confirmed researcher-owned paper already named and linked in Section 1. Model the target architecture on its section order, paragraph progression, and figure/table rhythm, while filling that architecture only with the current idea and independently grounded scientific content. Do not copy the reference paper's subject matter, claims, results, or prose.

For **every planned section and subsection**, enumerate every paragraph in
order. Use stable paragraph IDs such as `I-P1`, `RW1-P2`, `M2-P3`, `E3-P2`,
`D-P1`, and `C-P1`. In the visible HTML, each paragraph row contains:

- the stable paragraph ID;
- **one concrete sentence saying what that paragraph will write**;
- its relation to the previous and next target paragraph;
- the mapped reference paragraph text and a concise explanation of the logical
  move being imitated; the reference text may be collapsible but must remain
  available to the browser writer;
- the artifact ID it introduces or interprets, only when applicable.

The sentence must name the actual topic and argumentative move, not a generic
label such as “introduce the method” or a bundle of bullets disguised with
semicolons. It should be specific enough that the paragraph-writing API can draft the
paragraph from it, while remaining a plan rather than fabricated final prose.
Use exactly one grammatical planning sentence per paragraph row. Keep stable
source paragraph IDs, complete source text, source heading, source rhetorical
purpose, adaptation note, target rhetorical role, claims/variables,
evidence/citations, neighbor relations, and artifact bindings in that
paragraph's `paper_outline` record. The mapping may be many-to-one or
one-to-many; every target paragraph must have at least one mapped source
paragraph.

Do this for **all** sections, not only the Introduction: Abstract;
Introduction; each Related Work subsection; each Method subsection; every
Experiments subsection including setup prose, main results, ablations,
sensitivity/robustness, cost, qualitative/failure analysis; Discussion,
Limitations/Ethics when applicable; Conclusion; and planned appendices. For
Method paragraphs, additionally list inputs, outputs, variables, raw fields,
and evidence grade (`claim-grade`, `pilot-only`, `smoke-only`, or
`unavailable`). Mark the entire blueprint PROJECTED and keep unknown prose
numbers as `[X%]`.

Within the projected **Method** section, add one visible block marked
`data-model-design`. It must be detailed enough for the later browser writer to
draft the method without reverse-engineering scattered plan fields. Cover:

- inputs, outputs, and the end-to-end information flow;
- every named module and its responsibility;
- training phases and the boundary between trainable, frozen, teacher, and
  reference components;
- the objective/loss terms and any selection, aggregation, routing, or dynamic
  weighting equations that determine behavior;
- the inference path, including components used only during training;
- a component-to-evidence list naming the ablation, diagnostic, sensitivity,
  or result artifact that can weaken or falsify each material design claim.

Make this block concise but reproduction-grade: normally one 8--14-row table
or 250--500 English-word equivalent. It must contain an executable ordered
algorithm, define every symbol, state candidate/sampling construction,
preprocessing, objective normalization and parameter-update rules, list the
source-disclosed model-defining hyperparameters, and distinguish trainable,
frozen, teacher, and reference components. Put all source-undisclosed choices
in one explicit `Unknowns for exact reproduction` row and set
`reproducibility_status` to `partial_due_to_source_omissions`; never guess them.
Omit repeated motivation, results, and extended rationale from this block.

Mirror this exact specification in `grounding.model_design`; the visible block
and hidden contract may differ in presentation but not in scientific content.
Do not count this prose/table block as a result artifact. A generic pipeline
summary, method-module inventory without interactions, or conceptual-figure
caption does not satisfy the requirement.

For a **one-goal-paper reconstruction**, populate the block only from the goal
paper's verified full text, equations, captions, and method figures. Record the
goal paper as `source_authority`, label unreported implementation choices as
unknown, and do not borrow method content from the structural reference. The
structural reference remains limited to paragraph logic and figure/table
rhythm. Inspect the goal paper's equations, algorithm, implementation details,
appendices, captions, and method figures before judging reproducibility.

The visible order must begin with Abstract/Introduction and follow the target
paper from front to back. Experiment numbering belongs only inside the planned
Experiments section. In that section, show a clearly labeled experimental
setup block covering the concrete dataset/version, model, evaluation protocol,
metrics, seeds, and comparison rules. Follow it with a two-column **Baseline
Selection and Implementation** table that explains why each baseline is
selected and exactly how it and the proposed method will be implemented. Then
place all `[PENDING]` result tables and figure source tables at the paragraphs
that will introduce or interpret them. Never place `5.1 Setup` or `5.2 Results`
before the Abstract merely to satisfy a validator.

The setup block is a compact index, not manuscript prose or a registry dump.
Render exactly six rows in `<table class="setup-table">`: `Dataset`, `Model`,
`Baselines`, `Proposed method`, `Noise and runs`, and `Metrics`. Begin Dataset,
Baselines, and Proposed method values with their explicit counts. Do not add
setup paragraphs before or after this table. In the implementation table, use
one row per selected baseline plus one row for the proposed method; keep each
decision to one concise sentence or clause sequence and attach the supporting
paper link in the relevant baseline row. Full metric formulas and machine
provenance belong only in the embedded contract; method-defining equations
belong in the Method model-design block above when needed for an unambiguous
design.

(b.1) **Render only experiment-backed, fillable paper artifacts inline.** At
the exact point in the paragraph blueprint where a future empirical figure or
result table will be introduced, render its visible shell, not only its name in
an artifact ledger. A figure that needs no experiment, such as an Introduction
motivation figure or a Method overview, is count-only at `$expplan`: keep its
stable figure ID in the paragraph blueprint, artifact ledger, embedded
contract, and whole-paper figure total, but do not draw, mock, preview, create a
source table for, or add a result/acquisition requirement for it. Its actual
design belongs to the project-specific writing data, with `$figureppt` available only when explicitly requested after evidence is available.

**Introduction Figure / Figure 1 is a motivation figure by default.** Its
count-only contract must
make the problem and evidence gap understandable before revealing the method:
show a concrete failure or counterexample, why the existing observable can be
misleading, and the behavioral/evidentiary criterion the paper therefore
needs. It must not be an extraction pipeline, architecture diagram, algorithm
walkthrough, or method-module inventory; those belong in the Method section.
Do not render a conceptual example during `$expplan`; never invent quantitative
findings. Attach Figure 1 to the
Introduction paragraph that establishes the gap, not the paragraph that first
previews the proposed method, unless the researcher explicitly overrides this
role after seeing both alternatives.

Before designing any shell, freeze its target-template span as exactly one of
`single_column` or `double_column`. For a one-column venue template, use
`single_column` and note `full text width`; do not invent a two-column span.
Design the panel count, table columns, label density, and caption burden to fit
that approved span at readable publication size. Show the span on the visible
shell and artifact ledger and store it in the embedded contract. A later span
change requires redesigning the shell, resetting approval to `pending`, and
returning to the final gate.

- **Result table placeholder:** render the intended paper geometry, including the
  caption, row labels, multi-level headers, dataset/benchmark names, metric
  names, units/directions, uncertainty format, and notes. The table itself is
  the sole paper-facing authority for datasets and metrics; do not create a
  parallel dataset/metric registry. Keep every future numeric cell visibly
  `[PENDING]`; do not fabricate table values. Keep stable result and
  cell IDs only in hidden contract fields or non-visible `data-*` attributes;
  visible cells show values, never `RR-*`, cell IDs, panel IDs, or per-result
  numbers. The shell still specifies whether the real display will be
  `mean ± std`, CI, or another uncertainty format.
  Derive row groups, multi-level column groups, metric ordering, and notes from
  the confirmed researcher-owned structure reference's actual result-table
  grammar; never emit a generic administrative field table. Ablations use a
  publication-style component matrix: full method and one-change variants as
  rows, component-presence/state columns, then outcome columns for primary
  effect, robustness, and validity/safety, all `[PENDING]`.
- **Projected result figure:** show the intended caption and, directly beside
  the preview, the real-data source table that later experiments must fill.
  That table states dataset, metric, series, axes/categories, and aggregation,
  while every future observed X/value cell remains visibly `[PENDING]`; never
  expose synthetic fixture numbers as planned evidence. Enforce this dependency
  order: **(1) design and freeze the paper-facing source table, (2) serialize
  that table's exact categories/rows/series/required fields and plotted-mark
  count in `paper/figsrc/<project>/figure_schema.json`, (3) simulate one
  synthetic fixture value for each approved table cell/mark by running a
  schema-reading generator, (4) validate the
  fixture against the schema, and only then (5) draw the preview.** Never infer,
  resize, merge, or redesign a table from a synthetic fixture. Generate the preview
  from the separate machine-readable synthetic fixture after this validation. Generate the preview by executing
  reusable Python, not by drawing an HTML/SVG wireframe. Use the canonical
  `paper/fig/make_figs.py` plus a clearly named
  `paper/figsrc/<project>/projected_fixture.json`; accept `--figure`, `--panel`,
  `--metrics`, `--pdf`, and `--png`, use the
  `Agg` backend and only the standard library, NumPy, and Matplotlib, and emit
  PDF plus PNG. Keep values in the fixture, never hard-code them in source, and
  keep that fixture isolated from the visible pending source table.
  Store the deterministic schema-to-fixture generator at
  `paper/figsrc/<project>/make_projected_fixture.py`; it must read the frozen
  schema's explicit table rows/categories and fail if their count changes.
  Never maintain a second hand-written list of table points in either the HTML
  builder or the fixture.
  Every visible `[PENDING]` numeric cell must map to exactly one scalar input
  consumed by the plot. Do not add a generic `Observed values` pending row,
  a colspan pending summary, or any other pending cell that has no plotted
  scalar counterpart. Count pending cells from parsed HTML attributes (support
  both quote styles), not one brittle literal string.
  Treat count agreement as a hard return gate after HTML generation. For every
  panel, independently verify (i) schema/fixture row and scalar counts, (ii) the
  actual Matplotlib artists rendered (`PathCollection` offsets for scatter and
  `Rectangle` artists for bars), and (iii) `[PENDING]` numeric cells in the rendered HTML
  DOM. Require `rendered marks == plotted_marks` and
  `DOM pending cells == pending_values`; do not present or return the HTML while
  any panel fails. The reusable plotting script must implement and call a
  `validate_rendered_marks` check before saving its PDF/PNG.
  Structure multi-panel code as `draw_panel_*()` functions. With
  `synthetic: true`, draw `PROJECTED SHAPE — NOT RESULTS` prominently. Missing
  input must fail rather than default, interpolate, or invent. Embed the PNG in
  `03` as a data URL and retain script/PDF/PNG for browser writing; the paper run
  reuses the code and replaces only `--metrics` with validated results.
  Render each panel as its own preview beside exactly one corresponding data
  requirement table; never place several panels beside one combined table.
  Every panel table must name required fields and show `[PENDING]` in each
  future observed X/category and value cell. Preserve a one-to-one visual
  mapping between table cells and plotted marks: if a preview has three series
  with six points each, expose eighteen separate pending value cells (plus the
  six X/category cells when those are not already fixed design labels), never
  one `[PENDING]` cell that silently stands for an array or a whole curve. Use
  the same series names and point order in the table and preview. Predefined
  Give every pending numeric source-table cell a stable non-visible
  `data-target-id` and include those cell IDs—not only a coarse panel ID—in the
  artifact's `result_requirements`. `$runplan` and `05_EXP_RESULT.html` must
  later fill these exact cells from validated ledger rows and generate the
  final plot from the displayed values; they must not create a second plot-only
  data source.
  categorical experimental conditions are column headers, not pending data
  cells, and do not count as plotted numeric marks. Constrain the layout with
  `minmax(0,...)`, `min-width:0`, and `img{width:100%;max-width:100%;height:auto}`;
  stack table and image on narrow screens so no preview can overflow the page.
- **Non-result setup/configuration:** keep it in prose unless the
  researcher-owned reference genuinely uses a content-bearing table and the
  table is necessary for reader comprehension. Do not manufacture setup tables
  merely to create fillable cells.

The Experiments blueprint must include all paper-facing result shells implied
by the approved claims: main comparison, ablations, sensitivity/robustness,
cost/efficiency, qualitative/failure analysis, and any required per-dataset,
per-model, or transfer breakdown. The later experiment program is defined as
producing the exact evidence that fills these visible blanks. A result that
does not map to a planned cell/panel is supplementary until the plan is
amended; a promised cell/panel without an experiment is a red plan error.

(b.2) **Artifact ledger is part of the signed blueprint.** Give every projected
content figure/table a stable artifact ID (`F1`, `T1`, ...), supported claims,
owning paper subsection, introduction paragraph ID,
required row/column or panel dimensions, cell/panel requirement IDs, and
placement. Keep the future LaTeX label in the embedded contract, not in the
visible ledger: the reader sees only figure/table numbering, never internal
result identifiers or LaTeX labels. Mark an artifact `body_or_appendix` only when the HTML explicitly
permits moving it to the appendix under page pressure. The inline shell,
visible ledger, paragraph references, and embedded contract must agree exactly.
Do not describe a float as optional merely to make later layout easier.
**No duplicate evidence floats.** Every result figure/table must introduce a
distinct intervention, comparison axis, dataset/model scope, or claim test. A
“full-benchmark confirmation” is valid only when the main-results artifact is
explicitly a smaller subset and the confirmation expands it to named complete
coverage. If Main Results already covers the complete approved datasets,
models, methods, and metrics, a second aggregate table over the same cells is a
duplicate and must be removed or replaced with a distinct claim-bearing test,
such as a component ablation, robustness analysis, or defense evaluation.
(c) **Page-fill feasibility vs the target venue (do this BEFORE the GATE — a hard check, not a nicety).** The experiment plan must design *enough* experiments to fill the target conference's body-page requirement, because browser writing later must fill to that page count with substantive content and cannot invent experiments the plan did not specify. So, while the confirmed reference is open, **count its body proportions and content floats, inspect the broader grounded literature's experimental coverage, and estimate the plan's**: (a) read the target venue's body-page limit (ACL 8, EMNLP 8, NeurIPS 9, ICLR 9–10, AAAI 7–8) and the **researcher-owned reference's real CONTENT-float count** (how many result tables + figures it carries across its body — a table-heavy empirical paper often has 5–8). Keep the required six-row setup table as a compact index, but never count it as a content float and never add a second setup/configuration float to inflate the count. Count only floats that carry a result, an analysis, or a qualitative example; (b) count what THIS plan will produce as body content-floats — one per claim, per dataset/setting breakdown of the main results table, per ablation-matrix row, plus per-layer / sensitivity / qualitative / cost analyses (again, the setup table is not one of them); (c) if the plan's float/experiment count is materially below the researcher-owned reference's, or its experimental coverage is materially thinner than the strongest directly relevant grounded papers' (e.g. the plan yields 3 floats but the owned reference has 7), the plan is **under-scoped to fill the venue's pages** — expand it NOW: add datasets, baselines (raise the baseline selection), ablation-matrix rows, network/model/seed sensitivity sweeps, and analysis axes, until the projected float count and coverage are credible. A micro / smoke plan (e.g. a deliberate ~10-case test) will NOT fill a full venue paper; when the researcher has explicitly asked for a micro run, say so plainly at the GATE ("this plan yields ~N body floats vs the owned reference's M; at full venue length the paper will fall ~K pages short unless the experiment set is scaled up") rather than letting browser writing discover the shortfall at compile time. Immediately below the visible `2. Projected Paper` heading, write a compact whole-paper **float budget** comparing only this plan's total content figures/tables with the researcher-owned reference's total content figures/tables. Ignore which sections the floats appear in. Do not append a citation or `reference` link to this numeric line; the reference is already linked in Section 1. Also retain the one-line page-fill feasibility note elsewhere in `03`.
**Visible float-budget brevity overrides the preceding detail:** render exactly
one prominent line immediately below the `2. Projected Paper` heading with two numeric
entries—this whole paper and the reference whole paper—each formatted as
`total (figures, tables)`. Use a visible label such as `Figure/table count`, a
larger type size and bordered background so it cannot be mistaken for a
footnote. End the line after the second numeric entry: do not append a
`reference` label, citation, or link. The reference-paper link already belongs
in Section 1. Include count-only non-experimental figures in the totals.
Add no section-position counts, explanation, comparison, difference, or
interpretation.

The following design records are still mandatory, but keep them in the hidden
contract and let their paper-facing consequences appear in the paragraph plan
and artifact shells. Do not turn them into extra visible web sections:

1. **Claims → evidence → variables** — map each claim through experiment, observable, raw field, and computation to its metrics. Its `measurement_contract` records construct, direct/proxy role, limits/alternatives/companions, uncertainty, and support/weaken/falsify patterns. No measurable chain or only an unsupported proxy means narrow the claim or add direct evidence.
2. **Systems, datasets, metrics, and baselines** — freeze the method, selected baselines, and source actions in hidden `grounding`. Determine datasets and metrics directly in each projected main result table and caption/note; do not create dataset or metric registries. The visible table must make both unambiguous without hidden JSON. Do not discuss, decide, require, render, store, or validate train/dev/test splits in `$expplan`; they are entirely outside this skill's contract. Resolve conflicts in dataset or metric meaning at the existing decision meeting.
3. **Variable feasibility and provenance** — for every variable record `used_in`, `purpose`, `source`, `required_observable`, `available_now`, `fallback_or_proxy`, `raw_field`, and evidence grade. Do not mention a variable in the blueprint or an artifact unless it exists in this hidden record.
4. **Ablation contract** — one record per ablated component; each changes exactly one variable versus the full method and maps to approved artifact targets.
5. **Execution dependency sketch** — instrumentation sanity → generation smoke → baseline → diagnosis/main pilot → ablation → polish. This is not the final run schedule: `$runplan` later converts it into goals. Instrumentation sanity must verify raw fields and computation paths for every planned variable.
6. **Experimental decision space** — cover every result-changing researcher choice, including models, prompts, preprocessing, retrieval, thresholds, decoding, judges, stopping, and training. Each validator-defined record is `SEARCHED`, `FIXED_BY_SOURCE`, `FIXED_BY_DESIGN`, or `NOT_APPLICABLE`, with bounded values, authority/selection rule, observable, budget, freeze point, final-value source, and no test access. `$runplan`, not `$expplan`, owns dev/final data and freezes searched values.
7. **Paper consistency coverage** — `consistency_requirements` lists exactly every selected baseline/metric ID, decision ID, and claim marked `requires_formal_check`; browser writing validation must bind each to manuscript evidence instead of choosing a convenient subset.
8. **Budget** — rough GPU-hours per experiment block; flag runs longer than one day for sign-off.

**Embedded contract schema (required):** new plans use `schema_version: "1.1"` and top-level keys
`schema_version`, `contract_version`, `revision_history`, `source_plan`, `approval_status`, `profile_contract`,
`target`, `references`, `dataset_confirmation`, `grounding`, `claims`, `variables`,
`baseline_contract`, `repository_contract`, `experiment_contracts`,
`metric_contract`, `decision_space_contract`, `consistency_requirements`,
`paper_outline`, `paper_artifacts`, `required_labels`, and
`result_requirements`. Each `paper_artifacts` entry must
contain `id`, `kind`, `label`, `span`, `placement`, `supports`, `section_id`,
matching `dimensions` and `visible_dimensions` for every result-bearing artifact,
`introduced_after`, and `shell`. A table `shell` records caption, row labels,
column labels, dataset-bearing headers, metric/uncertainty format, and stable
pending cell IDs; a figure `shell` records caption,
panels, axes/legend, source variables/cells, and aggregation. Data-driven result
figures additionally record their required-data table, plotting source, fixture,
and generated PDF/PNG paths and set `data_driven: true`. Conceptual method or
overview figures set `data_driven: false` and are exempt from numeric fixtures
and Python plotting.
`revision_history` starts at version 1 and records `changed_at`, a concrete `reason`,
`changed_fields`, and compatibility impact. Any approved-contract amendment increments
`contract_version`, stores the prior approval digest as `parent_approval_sha256`, resets
approval to pending, and requires a new approval whose `approval_contract_version`
equals the current version.
Add `dimensions` when a result is broken down by
dataset/game/model/seed/condition. `paper_outline` records the ordered sections
and paragraph rows described above. Every paragraph record contains `id`,
`plan_sentence`, `rhetorical_role`, `supports`, `evidence`,
`relation_to_previous`, `relation_to_next`, `artifact_refs`, and a non-empty
`reference_mapping`. Each mapping entry records `source_paragraph_id`,
`source_heading`, complete `source_text`, `source_rhetorical_role`, and
`adaptation_note`. The HTML exposes the target plan plus its mapped reference
text without implying that source wording should be copied. Method paragraphs
additionally record `inputs`, `outputs`, `variable_ids`, `raw_fields`, and
`evidence_grade` in the hidden contract.
`dataset_confirmation` contains only `confirmed` and `confirmed_at`; dataset
names are not duplicated there because Setup and result-table headers are the
authority. It must be confirmed before HTML generation.
Each `result_requirements` entry contains `id`, `artifact_id`, exactly one of
`cell_ids` or `panel_ids`, `experiment_id`, `source_action`, `any_of` dotted
JSON key paths, and `supports`. `source_action` is exactly one of `RUN_LOCAL`
or `REUSE_REPORTED`; citation-only material cannot fill a result target. For
reported reuse, also include the exact paper/dataset source and table/figure/
row/column locator. For local work, `experiment_id` must resolve to an
`experiment_contracts` entry that references the table-defined dataset/metric
semantics and fixes only experiment-specific variables/raw fields, computation,
seed/uncertainty exceptions, authorized decision-space IDs, and repository
authority. Split selection is absent here and added by `$runplan`. This is the scientific source
contract that `$runplan` later turns into an executable acquisition contract;
it is not yet a goal schedule. Use `[]` for a required non-empty list. Before approval, set
`approval_status` to `pending`.

Treat IDs as a single-source registry, not presentation text. Section IDs,
paragraph IDs, artifact IDs, artifact LaTeX labels, result requirement IDs, and
result target IDs must each be globally unique within their namespace before
the HTML is rendered. Figure and table numbers follow the ordered artifact
registry; headings, shells, the compact ledger, Run Plan, and Paper Studio may
consume those identifiers but may not independently renumber them.

**GATE (human is judge — enforce it, don't just present):** in the approval conversation, summarize claims, selected baseline coverage/actions, exact reuse sources, omitted-Required risks, repository authority/fallbacks, the reference-aligned one-sentence-per-paragraph blueprint, every inline figure/table shell and its unfilled targets, variable feasibility, ablations, first three dependency-sketch experiments, budget, and artifact placement. Do not add these as extra visible HTML sections. Baseline and repository contracts must be resolved before the final HTML is written, so the GATE asks only for approval or revision of the complete plan. Reject the plan before this gate if any claim lacks a valid measurement contract, a proxy is asked to establish a stronger construct without a companion direct measure/control, any researcher-controlled decision is outside the authorized decision-space contract, any section/subsection omits its planned paragraphs, any paragraph lacks exactly one concrete planning sentence, any promised artifact lacks a visible shell, any numeric shell cell lacks exactly one result requirement, any result requirement lacks a single authorized source action and experiment/source locator, or any required target cannot be deterministically acquired. **Then STOP and call `ask the user directly`** for the researcher to `approve` / `revise` the plan (offer those options; `revise` collects what to change) — exactly as the intermediate baseline/reuse/repository gates already do. **Do NOT auto-proceed to `$runplan`; wait for the researcher's approval token.** This holds even in a skill-test run (fabricated data does not skip the gate).

Before presenting the gate, run `python research_avatar/tools/validate_experiment_plan.py --plan reports/03_EXPERIMENT_PLAN.html`. Fix every failure. This validator enforces table-owned dataset/metric semantics, no expplan split, Python-generated projected figures, fixture isolation, target coverage, and non-visible internal result IDs.

On `approve`, set the embedded contract's `approval_status` to `approved` and
validate that every artifact in the visible HTML ledger appears once in that
contract. When this skill later
changes the approved scientific scope or artifact ledger, reset the
embedded contract to `pending` and return to this gate. Approval is an explicit human
state, not a file-hash check. Regenerating fixtures/plots or hiding internal IDs
without changing table/figure semantics is a presentation refresh and preserves approval.
