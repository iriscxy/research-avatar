---
name: "runplan"
description: "Turn an approved EXPERIMENT_PLAN.html into a resumable, evidence-ordered hierarchy of executable goals for filling its projected-paper figure and table targets. Give every datum a deterministic acquisition contract, show the complete hierarchy, then let the researcher either confirm all Goals for automatic sequential execution or review and confirm them one by one. Use when the researcher says runplan, asks what experiment to run next, or wants to fill an approved experiment plan incrementally."
---

# Run Plan

At the first Skill action in this Codex project session, run
`python3 -m research_avatar.research_studio.server --ensure-studios` before substantive work.
This idempotent project bootstrap starts or reuses Research Studio at
`http://127.0.0.1:8780` and Paper Studio at `http://127.0.0.1:8765`, then opens
both browser pages. Run it once per session and run the same preflight when a
proposed `/goal` begins. Never launch duplicate servers; surface any startup
error instead of claiming that either page is available.

`$runplan` is the only experiment-execution planning skill. It converts the
approved Projected Paper's empty figure/table targets into bounded goals and
deterministic acquisition contracts; it does not execute them.

The ownership boundary is strict:

- `$expplan` defines and receives approval for the scientific plan.
- `$runplan` creates/resumes the execution graph, presents every Goal for
  approval, and records one of two researcher-selected execution modes:
  `manual_each_goal` or `sequential_all_goals`.
- In `manual_each_goal`, a researcher-issued `/goal` performs the actual code,
  engineering, runs, evidence collection, and report updates for that one goal.
- In `sequential_all_goals`, the researcher must explicitly request automatic
  execution. That one authorization lets the active coding agent execute the
  ordered goals without another prompt between them, while preserving every
  ordinary goal boundary, ledger append, validator, report refresh, and gate.

Never infer either mode from silence. `$runplan` first builds and presents the
complete graph, then stops at a Goal-confirmation gate. Execution begins only
after the researcher explicitly chooses to confirm all Goals at once or review
them one by one. The automatic executor must stop immediately on a failed
check, exhausted approved budget, `pivot`, `blocked`, or newly required
scientific decision; it may not skip the failed goal and continue.

## 1. Validate the approved input

Default input: `reports/03_EXPERIMENT_PLAN.html`.

Read the JSON in its
`<script type="application/json" id="experiment-plan-contract">` block first.
Require `approval_status=approved`; a missing, invalid, or pending contract is
a hard stop back to `$expplan`. Read `researcher-profile/PROFILE.html` only for
environment, stack, and OOM context. The researcher—not the agent—judges
whether scientific evidence supports a claim.

Require a `paper_outline`, `paper_artifacts`, and `result_requirements` mapping
every promised result cell/panel to approved evidence. If the plan lacks a
decisive motivation probe, tuning budget, runnable
next-stage configuration, result schema, acquisition/source information, or
required evidence, return to `$expplan`; do not invent research design during
execution planning.
Require and preserve `metric_contract`, every claim's `measurement_contract`,
and `decision_space_contract`. Copy the decision space byte-for-byte into the
run-plan state, assign every decision ID to a goal, and place every `SEARCHED`
decision in S3. Before any S4/S5 goal can complete, record its chosen value and
source goal in `frozen_configuration`; fixed and `NOT_APPLICABLE` decisions are
recorded without tuning. For every searched experiment, record protocol-sourced,
disjoint development/final data in `execution_splits` before S3. No goal may
introduce a choice outside this contract or tune on final data.

Treat each approved projected main table and its caption/note as the authority
for dataset and metric semantics. Do not require or invent dataset/metric
registries, and never infer a metric from a target-ID suffix. `$expplan` does
not own splits: before authorizing the first affected goal, resolve and record
the execution split from the benchmark's official protocol or approved dataset
construction procedure, then enforce dev/test separation here.

Treat the approved artifact schema as immutable. `$runplan` may decide execution
order and group targets into goals, but it may not add, remove, rename, or
reinterpret a row, column, panel, metric, baseline, dataset, or claim. A required
schema change returns to `$expplan` and resets approval.

## 2. Build the evidence funnel

Order approved work by dependency and information value:

| Stage | Decision question |
|---|---|
| S0 Minimal infrastructure | Can the smallest path needed by S1 run and reproduce itself? |
| S1 Hypothesis and motivation | Does the claimed phenomenon or gap exist? |
| S2 Method feasibility | Can the mechanism affect the intended quantity for the intended reason? |
| S3 Development tuning | Which approved configuration wins on dev within the fixed budget? |
| S4 Primary evidence | Does the frozen method support the central comparison? |
| S5 Breadth and robustness | Does it survive required baselines, settings, models, datasets, and seeds? |
| S6 Explanatory supplements | Why, when, and at what cost does it work or fail? |

S0 is deliberately narrow: validate only the data/model/metric/logging path
needed for the cheapest decisive S1 probe. Do not preflight the entire project.
S1 precedes method tuning; S3 freezes the configuration before S4/S5 test
evaluation; S6 is normally last. Within each stage, put the cheapest approved
experiment that can change the next decision first.

Do not flatten every experiment into one launch queue. Conditional work stays
visible but locked until its predecessor gate passes. Parallel work may share
one goal only when the runs have completed predecessors, answer one decision
question, and remain one interpretable milestone. A goal may fill targets from
one artifact or several artifacts, and one artifact may be filled by several
goals; there is no goal-to-table cardinality rule.

Organize this funnel as a visible two-level **experiment hierarchy** derived
from the approved `03` rather than as a flat goal list:

- A **major part** groups one complete scientific evidence block, such as
  instrumentation, problem-existence validation, method feasibility, main
  comparison, robustness, ablation, cross-play, or failure/cost analysis. Give
  it a stable ID (`P1`, `P2`, ...), decision question, covered claims and
  artifacts, dependencies, entry condition, and exit gate.
- Each major part contains ordered **goals that serve as its executable
  subparts** (`G1.1`, `G1.2`, ... within `P1`; `G2.1`, ... within `P2`). A goal
  is the smallest independently runnable and verifiable data slice,
  such as one shared implementation milestone, one model slice, one baseline
  family, one robustness condition, or one figure panel group. Record its exact
  acquisition contracts, approved targets, inputs, outputs, checks, budget,
  dependencies, and mechanical completion condition.
- Map every `Gpart.index` goal to exactly one major part. Normally one bounded
  subpart becomes one goal; split it into multiple goals only when it cannot
  safely fit one execution milestone. A subpart may fill several cells or panels, and a
  major part may span several paper artifacts. Never force part, subpart, goal,
  and table boundaries to coincide.

Show the complete major-part → subpart → goal hierarchy before proposing the
first unlocked goal. This hierarchy is an execution view only; do not mirror it
as mandatory version, part, subpart, goal, or run-ID directories on disk.

Render that hierarchy as a self-contained webpage in `reports/04_RUN_PLAN.html`, not
Markdown. Give each major part one visible `Pn — <title>` heading followed by
one plain-language sentence explaining what decision the part resolves, then
place its `Gn.m — <title>` goals directly underneath. Do not repeat the same
hierarchy as a second outline or catalogue.

The visible goal text must read like natural instructions to a researcher, not
like a database schema or an acquisition-contract dump. For each goal, use two
to five short sentences stating: why it is next, what concrete work to finish,
what evidence or paper artifact it will produce, how completion is checked, and
that its code and files must be organized before the goal ends. Keep exact
target IDs, locators, command templates, formulas, and acquisition fields in
the hidden `run-plan-state` JSON embedded in `04_RUN_PLAN.html`; expose only details that help the researcher understand the
work. Do not render long field tables, nested bullet contracts, or one visible
row per result target.

Every visible goal must end with one short `对应图表` line naming the exact
approved figure/table IDs it supports (`F1`, `T1`, etc.). If it supports no
paper artifact directly, say `无直接图表` and state its infrastructure role.
Immediately below the execution estimate, show `图表覆盖：N/N` followed by the
complete approved artifact-ID set. Count-only non-experimental figures must
still be mapped to the goal that establishes their specification, visibly
marked `非实验图，仅计数，后续由 paperwrite/figureppt 绘制`; they receive no
acquisition contract. Embed `approved_artifact_ids` and `artifact_coverage` in
the run-plan state. Generation and validation must fail unless the coverage
keys exactly equal `03.paper_artifacts`, every artifact has at least one owning
goal, and every visible `对应图表` mapping agrees with the hidden state.

Copy `03.implementation_contract` byte-for-byte into the embedded run-plan
state and render the same per-method implementation list before the hierarchy.
Render only `Method` and `How it is implemented`: local methods have no link;
methods that actually use verified official code link only the official GitHub.
The complete mode, repository, reuse, local-write, shared-boundary, and fallback
details remain in embedded state for execution checks. Goals may schedule that
contract but may not reinterpret it. Validation must fail if the Expplan and
Runplan implementation lists differ in order or content, or if any method or
`implementation_summary` is absent from the visible Runplan.

Show goal progress with one status mark derived from the embedded run-plan state whenever
the webpage is generated or resumed: `✅` for `completed`, `▶` for `running`,
`→` for the one proposed goal, `○` for locked/pending, and `⚠` for blocked or
invalidated. A completed goal must visibly retain its `✅`; do not replace it
with prose such as “status: completed.”

Render the one active or proposed **Current Goal inside its matching `Gn.m` goal
card**, immediately after that goal's description and `对应图表` line. The nested
panel contains the complete `/goal` in a selectable `<pre>`, a dedicated
`复制 /goal` button that copies that exact text with visible success/failure status,
outputs, resources, and completion check. Never shorten the copied command.
Never render Current Goal as a separate top-level section. When a goal completes,
regenerate from embedded state: the completed card keeps `✅`, and the Current
Goal panel moves downward to the newly proposed/unlocked goal. There must be
exactly one nested Current Goal whenever `active_goal` or `proposed_goal_id` is
set, and its `data-current-goal-id` must equal that state ID.

For each paper-facing artifact, render exactly one `Completed Goal Evidence`
block under the earliest goal in run-plan order whose `artifact_ids` names that
artifact. If later goals fill additional cells or panels of the same table or
figure, regenerate and update that original block; never repeat the artifact
under the later goals. Copy the matching approved artifact/table snapshot from
`05_EXP_RESULT.html`; never hand-author a second numeric source. Figure
snapshots include their adjacent source-data table, and table snapshots include
the result table. Every filled number keeps
its `data-result-id` and links to
`/artifact/results#provenance-<result_id>` when embedded in the Research Studio
Run Plan (the result page itself uses the same-page `#provenance-<result_id>`
anchor). Never use `05_EXP_RESULT.html#...` from `/artifact/runplan`, because
the browser resolves that to the nonexistent `/artifact/05_EXP_RESULT.html`.
Also attach `data-local-result-href="05_EXP_RESULT.html#provenance-<result_id>"`
and activate it only under `file:` so a researcher who opens
`reports/04_RUN_PLAN.html` directly reaches the sibling results file instead of
the invalid filesystem-root `/artifact/results` path.
The copied value also retains a
compact `data-provenance-summary` plus matching native `title`: mouse hover or
keyboard focus previews its raw source, calculation, actual command, and
verification, while click opens the complete record in `05`. Regeneration must fail if a scoped
target is missing, pending, lacks a result ID, or lacks its provenance link.

Treat `04_RUN_PLAN.html` as the single user-facing experiment-execution page in
Research Studio. Do not expose `05_EXP_RESULT.html` as a second artifact button
there: `05` remains the cumulative result/provenance backend reached by clicking
a value in an embedded Goal snapshot. When different goals fill different
panels of one figure, validate and generate each completed panel independently,
but keep the evolving source tables and plots together in the figure's one block
under its earliest owning goal. Do not repeat the same figure under each
producing goal or wait for unrelated panels before updating that one block.

## 3. Write one durable webpage with embedded state

Create or resume:

- `reports/04_RUN_PLAN.html`: a self-contained responsive webpage containing the ordered `P1`, `P2`, ... major-part hierarchy
  with `G1.1`, `G1.2`, `G2.1`, ... goals nested directly beneath their parts,
  then the decision graph and the same hierarchically numbered goal
  catalogue. Each goal records its `part_id` and `subpart_id`, decision
  question, dependencies, exact
  authorized runs, fixed variables, approved refinement budget, input/output
  paths, required checks, mechanical completion condition, falsifier,
  successor branches, explicit exclusions, and the exact approved artifact
  targets it fills.

Start `04_RUN_PLAN.html`, immediately after its title, with a compact execution
estimate table that states: total goal count, recommended concurrent GPU count,
whether one-GPU execution remains possible, the summed GPU-hour envelope from
the approved experiment budgets, compute-only wall time for the recommended
GPU count and for one GPU, end-to-end calendar time including engineering and
audits, and the assumptions behind those estimates. Label estimates as
approximate; do not present queue time or unknown hardware throughput as fact.
- Embed exactly one JSON object inside `reports/04_RUN_PLAN.html` as
  `<script type="application/json" id="run-plan-state">...</script>`. This
  hidden object is the sole machine state: source-plan identity and approval,
  major-part/subpart/goal statuses, `proposed_goal_id`, active goal, completed
  results, frozen configuration, attempts, raw paths, gate decisions,
  amendments, skips, exact next authorized action, ledger audit, and the
  machine-readable `acquisition_contracts` list. Each acquisition repeats at
  least `id`, `artifact_id`, `target_id`, `source_type`, and `producing_goal`
  so the validator can reject a nonexistent or mismatched route. Do not create
  `RUN_STATE.json` or another sidecar state file.
- `code/RESULTS_LEDGER.csv`: the canonical, append-only index of every real
  numeric/text result. Keep one result per row with its metric/value, approved
  artifact/target ID when paper-facing, acquisition contract ID, source type,
  dimensions, local raw JSON/JSONL artifact and locator or exact reported
  source, actual command when run locally, code/config/environment files, code
  revision, timestamps, and verification status. Conversation history and
  prose reports are never result sources.

Use explicit states: `awaiting_goal_activation`, `running`, `completed`,
`refine`, `pivot`, `stopped`, and `blocked`. Persist outputs before reporting
them and never silently discard prior evidence.

Before execution, write a machine-readable **acquisition contract** for every
required datum in the embedded `run-plan-state.acquisition_contracts`. Each contract has a
stable `acquisition_id` and records:

- `artifact_id` and exact table `cell_id` or figure `panel_id` (`target_id`);
- `figure_source_cell=true` when the target is one numeric cell in an approved
  figure source-data table; these targets drive the final plot directly;
- metric, unit, dimensions, and exactly `atomic` or `derived`; every aggregate,
  gap, ratio, mean, or transformed value is `derived` and needs its derivation;
- exactly one `source_type`: `RUN_LOCAL` or `REUSE_REPORTED`;
- for `RUN_LOCAL`: experiment, method/baseline, the dataset and metric read from
  the approved table plus the execution split fixed by `$runplan`, model,
  condition, seed policy, executable command template, code/config/input paths,
  raw output path, JSON/JSONL locator, computation formula, aggregation and
  uncertainty rule; do not infer dataset or metric from internal target names;
- for `REUSE_REPORTED`: exact paper/dataset source, table/figure/row/column or
  other stable locator, reported protocol match, and an explicit note that the
  value was not rerun locally;
- producing goal, prerequisites, verification procedure, and final placement
  in `reports/05_EXP_RESULT.html`.
- for every datum marked `derived`, a machine-readable `derivation` object—not
  only a prose formula—with `operation` (`subtract`, `add`, `mean`, or `ratio`),
  ordered `operand_locators`, and an explicit rounding policy. Persist operands
  at full precision and use `rounding.stage=none` by default; if the approved
  protocol truly rounds before or after the operation, record the exact stage
  and decimal count. The ledger validator must reload the raw operands,
  recompute the value with decimal arithmetic, and reject any mismatch before
  the goal can be marked complete.

No planned paper datum may be assigned only a vague action such as “run the
ablation” or “take the published score.” Every value must have one deterministic
route and one inspectable source. `REUSE_REPORTED` is allowed only when the
approved `$expplan` contract explicitly authorizes it; otherwise use
`RUN_LOCAL` or return for amendment.

Keep `04_RUN_PLAN.html` human-readable and natural-language first. Do not print a
target-level contract, one row per target, raw JSON fields, source locators, or
a technical coverage-index table. The page may state one short coverage
sentence per goal, such as “fills the main comparison table for AdvBench,”
while every required target remains exactly once in the canonical embedded
acquisition list. A goal's completion is scoped to its
assigned targets, not to an entire table by convention.

Use an **incremental evidence-capture contract** during execution:

1. Treat each atomic number as a checkpoint. As soon as one seed/cell/aggregate
   is obtained, save its raw record and append one ledger row before computing
   the next number. Never hold completed values only in terminal output, chat,
   or memory.
2. Fill the already approved artifact targets progressively from ledger rows.
   Do not define new table rows/columns or figure panels inside `$runplan`.
3. Store every seed result first. Compute mean/std or other aggregates only
   from saved rows, then record each derived number separately.
4. Never derive a scientific value from values copied out of a displayed or
   rounded table. The raw persisted records are authoritative; display
   formatting happens only after derivation unless the acquisition contract
   explicitly encodes protocol-level pre-operation rounding.

Map every embedded-contract `result_requirements` item to its producing goal,
artifact/target ID, acquisition contract, source, raw file and JSON key path
when local, and dimensions. Normal completion must
satisfy every requirement. An early `pivot` or `stop` path must enumerate the
missing requirements and cannot be handed to `$paperwrite` as completed
evidence.

Present the complete `04_RUN_PLAN.html` before proposing any paid/GPU work.

Create the ledger with the exact header documented by
`scripts/validate_results_ledger.py`. A local `REAL` row is admissible only when
the validator can reopen the raw JSON/JSONL locator, reproduce the recorded
value, and resolve every listed code/config/environment file. A reported
`REAL` row is admissible only when its exact approved source and source locator
are recorded and verified. Every `REAL` row points to an acquisition contract.
Use `MISSING` for an expected result that was not obtained and `INVALIDATED`
when a formerly recorded result fails provenance or verification. Never delete
or silently edit an old row; append a superseding row and explain the relation
in `notes`.

Keep experiment implementation under `code/` and outputs under
`results/<project>/`. Do not impose version, goal, or run-ID directory levels.
Choose subdirectories only when the
experiment naturally needs them; do not impose a fixed folder taxonomy. At
each resume and goal boundary, tidy temporary files, keep code/results easy to
identify, and verify that ledger paths still resolve. Never auto-delete raw
evidence or move a ledger-referenced file without updating its references.

## 4. Confirm the Goals, choose the execution mode, and expose one current goal

After presenting the complete hierarchy, stop at one explicit confirmation
gate. Ask the researcher to choose exactly one of these two paths:

1. **Confirm all Goals and execute automatically.** Record
   `execution_mode=sequential_all_goals`, record the full ordered Goal-ID list
   and current plan digest as the approved scope, then start the first Goal.
2. **Review Goals one by one.** Record `execution_mode=manual_each_goal`; show
   the first unlocked Goal, wait for its individual approval, execute it, and
   repeat the review gate for every successor.

Do not describe the second path as the default, and do not make copying a
`/goal` command the main workflow. The command remains a recovery affordance
for manual mode. Store the choice in `run-plan-state.goal_confirmation` with
`status=confirmed`, `scope=all_goals` or `one_goal_at_a_time`, the confirmed
Goal IDs, a plan digest, and confirmation time. Before choice, keep
`execution_mode=awaiting_goal_confirmation`, keep
`goal_confirmation.status=pending`, expose no Current Goal, and do not begin
experimental work.

The webpage must show this two-path confirmation gate before execution and,
after selection, state the selected mode in plain language at the beginning of
`4. Parts and Goals`. Automatic mode is not a bulk job: each goal independently
transitions through running/completed, writes its own raw evidence and ledger
rows, runs strict validation, updates `04` and `05`, evaluates its gate, and
only then unlocks the successor. A failed or non-continue gate stops the queue.

### Manual mode

Choose only the first/next unlocked goal with the highest information value.
Store it as embedded `run-plan-state.proposed_goal_id`, then print one self-contained
command in this form:

```text
/goal Complete Gn.m: <plain-language description of the exact data slice, methods/comparisons, engineering work, checks, metrics, and stopping condition>; follow reports/04_RUN_PLAN.html and its embedded run-plan state; save each result immediately; before completing the goal, organize its code and files, remove only disposable temporary artifacts, and verify every recorded path; append and validate every result in code/RESULTS_LEDGER.csv; update the embedded state, regenerate reports/04_RUN_PLAN.html so the goal shows ✅ and, for paper-facing targets, updates the single matching 05 figure/table snapshot under that artifact's earliest owning goal with every filled number linked to provenance; update the matching shells in reports/05_EXP_RESULT.html from the ledger; stop after Gn.m, do not start the successor goal, and only propose the next unlocked /goal.
```

Replace every placeholder with actual work. The command must make sense without
any skill name. It must never invoke `$runplan` or another skill, and it must
not use a vague instruction such as “run the next experiment.”

Ask the researcher to confirm the displayed Goal before running it. Provide the
copyable `/goal` only as an optional recovery/manual-resume command, not as the
required way to proceed. Then stop.

### Sequential mode

When the researcher has explicitly selected `sequential_all_goals`, acknowledge
that authorization once and start the first proposed goal. After every goal,
perform the complete boundary protocol in §5 before advancing. Do not ask the
researcher to copy intermediate `/goal` commands. Keep the copyable command in
the Current Goal panel as a recovery/manual-resume affordance. When all goals
are complete, set `proposed_goal_id` and `active_goal` to null, set the plan
state to `completed`, run the final strict ledger/report validation, and hand
the validated evidence to `$paperwrite` only if the user's request includes
paper generation.

## 5. Contract for each goal executor

Each goal executor—whether manually activated or reached by an explicitly
authorized sequential queue—owns exactly one goal. Its command and
`04_RUN_PLAN.html` must require it to:

1. Verify the requested `Gn.m` equals `proposed_goal_id`, all predecessors are
   complete, and no unrelated goal is active.
2. Mark only that goal `running`; perform its authorized implementation,
   smoke checks, experiments, and evidence collection autonomously.
3. Stay inside the approved variables, comparisons, search space, budget, and
   data split. Never tune on test data or redesign the scientific plan.
4. Follow the assigned acquisition contract for each target. Persist raw
   outputs and append each atomic number to
   `code/RESULTS_LEDGER.csv` immediately after it is obtained, before running
   the next number. Include `artifact_id`, `target_id`, `acquisition_id`, and
   `source_type` for every paper-facing result; record the exact command actually run and all
   code/config/environment files, not a planned command reconstructed from
   memory. For approved reported reuse, record the exact source and locator and
   never imply it was rerun. Aggregates must be computed from saved atomic rows,
   then saved as their own ledger rows. After each verified row is appended,
   immediately refill the matching approved cell in `05_EXP_RESULT.html` and
   regenerate its clickable provenance target; never wait until the whole goal
   or whole table is complete to expose already verified evidence.
5. Run `python3 .agents/skills/runplan/scripts/validate_results_ledger.py
   --ledger code/RESULTS_LEDGER.csv --plan reports/04_RUN_PLAN.html --report
   reports/05_EXP_RESULT.html --goal Gn.m --strict-report` before accepting a
   gate or completing the goal. On every resume, run the validator before new
   work and reconcile failures first. Update embedded `run-plan-state.ledger_audit` with
   the check time/status and update `reports/05_EXP_RESULT.html` only from
   validated ledger rows. Missing evidence is `MISSING`, never an estimate.
   Before that validation, after the matching cells have been regenerated with
   their `data-result-id` attributes, run
   `python3 .agents/skills/runplan/scripts/render_result_provenance.py --ledger
   code/RESULTS_LEDGER.csv --plan reports/04_RUN_PLAN.html --report
   reports/05_EXP_RESULT.html`. This deterministically linkifies every newly
   filled value, attaches its hover/focus provenance summary, and refreshes the
   page-local generation-process cards.
6. At each resume and goal boundary, organize experiment code and
   result files, remove only disposable temporary/build artifacts, and verify
   all ledger paths still exist. Do not maintain a separate file inventory.
   After provenance rendering and strict ledger/report validation, regenerate
   the visible `reports/04_RUN_PLAN.html` from its embedded state so every newly
   completed item visibly changes to `✅` before reporting completion. Run
   `python3 research_avatar/tools/run_plan_progress.py reports/04_RUN_PLAN.html`; this also moves
   the one nested Current Goal panel to the next `proposed_goal_id` and embeds
   each paper-facing artifact exactly once under its earliest owning goal,
   updating that snapshot from `05_EXP_RESULT.html` as later goals fill it.
   Validate that the evidence block is a child of that earliest owner's card,
   not a detached top-level section or a duplicate under a later goal.
7. Complete the goal only when its declared files, scoped evidence, and
   mechanical checks exist. If the goal owns paper-facing acquisition targets,
   it cannot be completed until every target scoped to that goal is filled from
   validated ledger rows, every numeric value is clickable to its provenance,
   every numeric value exposes the same provenance summary on mouse hover and
   keyboard focus,
   and the corresponding figure source-data table or result table is visibly
   updated in the artifact's single evidence block beneath its earliest owning
   goal card. A later producer goal must not receive a duplicate block. A
   data-driven figure must show its actual source-data table; a table target
   must show the result table itself.
   Partially owned artifacts may keep other goals' cells pending, but the
   completed goal's own cells may not be pending. Infrastructure-only goals
   marked `无直接图表` are exempt from the snapshot requirement.
   Report negative results and uncertainty honestly; a goal means “produce
   evidence,” not “make the hypothesis succeed.”
8. Evaluate only the preregistered gate and record the result. In
   `manual_each_goal`, propose the next unlocked or bounded refinement `/goal`
   and stop; printing it is not authorization to execute it. In
   `sequential_all_goals`, advance only when the gate says `continue`, then run
   the next unlocked goal under the same already-recorded authorization. Stop
   the queue on `refine`, `pivot`, `stopped`, `blocked`, validation failure, or
   any need for a new researcher-controlled choice.

If evidence requires a new claim, metric, dataset, baseline, or search space,
record `pivot` and return to `$expplan` for amendment and approval. `refine` may
use only execution variables and budgets already authorized by the approved
plan. `stop` records why and lists missing evidence.

## 6. Result ledger

`code/RESULTS_LEDGER.csv` is the canonical result ledger;
`reports/05_EXP_RESULT.html` is its cumulative, stage-ordered human-readable
view and the filled counterpart of the approved Projected Paper shells. Preserve
`reports/03_EXPERIMENT_PLAN.html` as the approved blank blueprint; never replace
its placeholders with run results. In `05`, each approved target is visibly
`PENDING`, `FILLED`, `MISSING`, or `INVALIDATED`. Every displayed result must
carry the ledger `result_id` (use
`data-result-id` on the containing HTML row/element) and be regenerated or
checked against validated ledger rows. For each goal include status,
dependencies, configuration, commands actually run, raw paths, result summary,
falsifier status, gate decision, negative results, and next authorized action.
Do not create a separate tracker HTML and never recover a value from chat.
Only validated ledger rows may fill artifact targets; `$paperwrite` consumes
those validated rows and the filled `05` view rather than copying numbers from
conversation history.

`05` must visibly render the **same approved paper artifacts**, not a prose
summary of them. Fill each result table's exact approved cells with validated
real values and uncertainty; render each figure's approved panels as actual
plots or traceable qualitative content generated from validated ledger rows and
their raw sources. Preserve the approved `single_column` / `double_column`
span, rows, columns, panels, axes, legends, and aggregation. Unfinished targets
remain visibly `PENDING`; missing or invalid evidence is labeled `MISSING` or
`INVALIDATED`, never estimated or visually interpolated. Every rendered table
cell and figure panel must retain its target ID and supporting result IDs in
non-visible `data-*` attributes. Reader-facing text shows only paper artifact
numbers (`T1`, `F2`, ...), captions, axes, series, metrics, status, and values;
never print target IDs, result IDs, acquisition IDs, or LaTeX labels.

Preserve the paper-facing geometry. Render a result table as the approved
method/variant rows × dataset/metric columns, with provenance attached to each
cell through `data-target-id`, `data-acquisition-id`, and, once filled,
`data-result-id`. Never render one ledger result per visible table row. Render a
figure as its approved multi-panel layout with axes, legend, and aggregation
notes; pending panels remain empty labeled shells, and filled panels become the
actual traceable plots or qualitative content. Ledger-shaped provenance tables
belong in `code/RESULTS_LEDGER.csv`, not in the reader-facing artifact area of
`05`.

For every data-driven figure in `05`, render its approved source-data table
immediately beside the corresponding panel. That table is the sole numeric
source for the plot: its cells remain `[PENDING]` until validated ledger rows
fill them, and the figure remains a visibly pending shell while any required
source cell is pending, missing, invalidated, or unverified. Once all required
cells are filled, serialize those exact displayed table values and invoke the
approved reusable Python plotting code; do not maintain a second figure-only
dataset, manually enter plot values, interpolate missing cells, or reuse the
synthetic projected fixture from `03`. Regenerate the table and plot together
after every ledger update. Record the exact source target IDs on the figure
container (`data-source-target-ids`) and on the generated plot
(`data-generated-from-target-ids`); the two sets must match exactly. A filled
panel plot while that panel's source table is not fully filled is a hard
validation failure. A completed panel must have a generated plot even if other
panels in the same figure remain pending.

Make every `FILLED` paper-facing number in a result table—and every filled
number in a figure's adjacent source-data table—a page-local provenance link.
Render the value inside an anchor carrying the same hidden result ID:
`href="#provenance-<result_id>"`, `data-result-id="<result_id>"`, and
`data-provenance-trigger="<result_id>"`. Also attach a compact escaped
`data-provenance-summary` and identical native `title` containing goal, metric,
source, calculation, and verification; local results additionally include raw
artifact/locator and the actual command, while reported reuse includes its
source/locator and not-rerun notice. Hover and keyboard focus show this compact
summary without navigation; click still opens the complete generation-process
card and preserves Back navigation. Pending, missing, or invalidated cells
are plain status text and are never clickable. Keep the paper-shaped row ×
column geometry; do not add a visible provenance column or one ledger row per
result.

At the end of `05_EXP_RESULT.html`, render one compact collapsible “生成过程”
index with `id="result-provenance-index"` and a stable target
`id="provenance-<result_id>"` for every clickable value. Clicking a value must
update the page hash, open the matching card, move focus to it, and call
`scrollIntoView`; the browser Back action must remain meaningful. The card must
show:

- common fields: goal, metric/value/unit, dimensions, source type, acquisition
  kind, calculation/aggregation rule, obtained time, verified time, and
  verification status;
- `RUN_LOCAL`: raw artifact, exact JSON/JSONL locator, the command actually
  run, code files, config files, environment files, and code revision;
- `REUSE_REPORTED`: exact paper/dataset source and stable table/figure/row/
  column locator, plus a prominent statement that it was not rerun locally.
  Store that statement canonically as `reuse_notice="not rerun locally"` in
  the provenance payload and render it in reader-facing language.

Embed the exact provenance records once as escaped JSON in
`<script type="application/json" id="result-provenance">...</script>` and
render the cards from that payload with DOM `textContent`, not interpolated
`innerHTML`. Escape `<` as `\u003c` in the JSON. For derived values, copy the
structured acquisition-contract `derivation` object exactly into
`calculation`; for atomic values use `{"kind":"atomic"}`. Never reconstruct a
command from a template or conversation. The strict ledger validator must
reject a filled value when its anchor, payload, jump target, interaction script,
or any required provenance field is absent or differs from the ledger and
acquisition contract.

Synthetic skill tests must carry a prominent `SKILL-TEST — fabricated data,
NOT a scientific result` banner and `SYNTHETIC` watermark.

## Fixed HTML structures

Render exactly two user-facing experiment artifacts. In both files, each `<section data-report-section>` and visible `<h2>` must agree.

`04_RUN_PLAN.html` has exactly these ordered top-level sections:

1. `1. Execution Estimate` (`execution-estimate`): Goals, GPUs, approximate time, and assumptions;
2. `2. Implementation Sources` (`implementation-sources`): the inherited per-method implementation contract;
3. `3. Figure/Table Coverage` (`artifact-coverage`): the complete approved artifact checklist;
4. `4. Parts and Goals` (`parts-and-goals`): ordered `Pn` parts with nested `Gn.m` goals, status, and destination. Before approval it shows the two-path Goal confirmation gate and no Current Goal. After approval, the exactly one Current Goal panel is nested inside the matching goal card and moves with `proposed_goal_id` / `active_goal`; its copyable `/goal` is only a manual/recovery affordance.

`05_EXP_RESULT.html` has exactly these ordered top-level sections:

1. `1. Artifact Completion` (`artifact-completion`);
2. `2. Paper Tables and Figures` (`paper-artifacts`): approved artifacts in paper order with unchanged geometry and pending states;
3. `3. 生成过程` (`generation-process`): one collapsible provenance index containing raw path, actual command, code/config, calculation, and verification.

Every title in both files must own substantive project-specific content; an empty section, title-only slot, or placeholder-only body is invalid. Do not add, rename, reorder, or omit these sections. Before presenting either file, run `python3 research_avatar/tools/validate_report_structure.py --kind runplan --html reports/04_RUN_PLAN.html` and `python3 research_avatar/tools/validate_report_structure.py --kind results --html reports/05_EXP_RESULT.html` in addition to the ledger/result validators.

Never expose `RESULTS_LEDGER.csv` as a user-facing tab, table, preview, or download in Research Studio or the Live Demo. It remains an internal store used to generate and validate `05_EXP_RESULT.html`. Never add a third experiment-stage tab or a visible ledger-shaped table. The Live Demo must reproduce these two structures with illustrative content and working numeric hover/focus provenance plus the full click-through jump.

## Output

`reports/03_EXPERIMENT_PLAN.html` + `reports/04_RUN_PLAN.html` +
`code/RESULTS_LEDGER.csv` + runnable `code/` + `results/` +
`reports/05_EXP_RESULT.html`.
