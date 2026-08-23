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
data-bearing figure/table IDs it supports (`F2`, `T1`, etc.). If it supports no
paper artifact directly, say `无直接图表` and state its infrastructure role.
Immediately below the execution estimate, show `图表覆盖：N/N` followed by the
complete data-bearing artifact-ID set derived from `03.result_requirements`.
Figures without any result requirement are writing-stage artifacts: do not map
them to a Goal, count them in RunPlan coverage, draw them in `04`, or copy them
to `05`. Embed only data-bearing IDs in `approved_artifact_ids` and
`artifact_coverage`. Generation and validation must fail unless those IDs
exactly equal the ordered unique artifact IDs in `03.result_requirements`, each
has at least one owning goal, and every visible `对应图表` mapping agrees with
the hidden state.

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

For each data-bearing experiment artifact, render exactly one `Completed Goal Evidence`
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
