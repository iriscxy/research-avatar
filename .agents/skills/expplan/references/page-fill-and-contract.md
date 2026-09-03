# Page-fill, embedded contract, and approval

Read this file after the paper architecture and artifact shells are concrete.
It continues the projected-paper blueprint at part (c).

(c) **Page-fill feasibility vs the target venue.** Complete this hard
check before the approval gate. The experiment plan must contain enough
substantive evidence to fill the target body-page allowance; browser writing
cannot invent missing experiments later.

Compare three grounded quantities:

1. the official venue body-page limit;
2. the researcher-owned reference paper's body proportions and total
   content-bearing figures and tables;
3. this plan's expected body coverage and content-bearing figures and tables.

Use the current official venue rules; common historical ranges such as ACL or
EMNLP at eight pages, NeurIPS around nine, ICLR around nine to ten, and AAAI
around seven to eight are orientation only, not authority. Count only figures
and tables that carry results, analysis, or qualitative evidence. The mandatory
six-row setup table is a compact index, not a content float. Do not add another
setup/configuration table to inflate the count.

If the plan is materially thinner than the owned reference or the strongest
directly relevant grounded papers, expand the scientific coverage with
appropriate datasets, baselines, ablations, model/seed sensitivity, robustness,
qualitative analysis, or cost analysis. Do not add duplicate or empty
experiments merely to occupy space.

A researcher-authorized micro or smoke study may remain deliberately short. At
the gate, state its expected float count and page shortfall plainly instead of
letting Paper Studio discover the mismatch at compile time.

Immediately below the visible `2. Projected Paper` heading, render one compact
whole-paper float-budget line comparing this plan with the owned reference.
Show only total, figure count, and table count for each paper. Do not append a
citation, link, section-position breakdown, interpretation, or difference; the
reference link already appears in Section 1.

Store the auditable decision in `page_fill_contract` with
`target_body_pages`, `section_length_shares`, `experiment_paragraph_ids`,
`result_artifact_ids`, `evidence_blocks`, `expected_body_pages`,
`minimum_last_page_fill`, `feasibility_status`, `micro_study_override`, and
`estimation_basis`.
`section_length_shares` must cover the projected outline exactly and sum to
1.0. Each evidence block names its kind, target paragraph IDs, experiment IDs,
and artifact IDs. A full-length plan includes `main_comparison` and at least
three distinct applicable analysis kinds beyond it. For a four-page short
paper, plan at least four experiment/result paragraphs and three distinct
result-bearing artifacts unless an explicitly authorized micro-study shortfall
is recorded. The validator rejects an unsupported prose-only assertion that
the scope is sufficient.
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
`result_requirements`, plus `page_fill_contract`. Each `paper_artifacts` entry must
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
consume those identifiers but may not independently renumber them. Do not rely
on the structure-writing model to enforce uniqueness: pass its target outline
through `canonicalize_target_identifiers` before rendering or persistence. That
allocator preserves the first valid unique suggestion and deterministically
replaces only missing or colliding section/paragraph IDs; validation remains a
final assertion rather than the mechanism that discovers the problem for the
user.

**GATE (human is judge — enforce it, don't just present):** in the approval conversation, summarize claims, selected baseline coverage/actions, exact reuse sources, omitted-Required risks, repository authority/fallbacks, the reference-aligned one-sentence-per-paragraph blueprint, every inline figure/table shell and its unfilled targets, variable feasibility, ablations, first three dependency-sketch experiments, budget, and artifact placement. Do not add these as extra visible HTML sections. Baseline and repository contracts must be resolved before the final HTML is written, so the GATE asks only for approval or revision of the complete plan. Reject the plan before this gate if any claim lacks a valid measurement contract, a proxy is asked to establish a stronger construct without a companion direct measure/control, any researcher-controlled decision is outside the authorized decision-space contract, any section/subsection omits its planned paragraphs, any paragraph lacks exactly one concrete planning sentence, any promised artifact lacks a visible shell, any numeric shell cell lacks exactly one result requirement, any result requirement lacks a single authorized source action and experiment/source locator, or any required target cannot be deterministically acquired. **Then STOP and call `ask the user directly`** for the researcher to `approve` / `revise` the plan (offer those options; `revise` collects what to change) — exactly as the intermediate baseline/reuse/repository gates already do. **Do NOT auto-proceed to `$runplan`; wait for the researcher's approval token.** This holds even in a skill-test run (fabricated data does not skip the gate).

Before presenting the gate, run `python research_avatar/tools/validate_experiment_plan.py --plan reports/03_EXPERIMENT_PLAN.html`. Fix every failure. This validator enforces table-owned dataset/metric semantics, no expplan split, Python-generated projected figures, fixture isolation, target coverage, and non-visible internal result IDs.

On `approve`, set the embedded contract's `approval_status` to `approved` and
validate that every artifact in the visible HTML ledger appears once in that
contract. When this skill later
changes the approved scientific scope or artifact ledger, reset the
embedded contract to `pending` and return to this gate. Approval is an explicit human
state, not a file-hash check. Regenerating fixtures/plots or hiding internal IDs
without changing table/figure semantics is a presentation refresh and preserves approval.
