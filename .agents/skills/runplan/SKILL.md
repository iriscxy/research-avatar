---
name: "runplan"
description: "Turn an approved EXPERIMENT_PLAN.html into a resumable, evidence-ordered hierarchy of executable goals that fill its projected-paper figure and table targets. Give every datum a deterministic acquisition contract, present the full hierarchy, and let the researcher approve automatic sequential execution or one-goal-at-a-time review."
---

# Run Plan

Run once per project session and at the start of an activated goal:

```bash
python3 -m research_avatar.research_studio.server --ensure
```

`$runplan` converts an approved scientific plan into an execution graph. It
does not redesign the science. A schema, claim, metric, dataset, baseline,
search-space, or artifact change returns to `$expplan` for amendment and renewed
approval.

The approved `03` contract, embedded run state, validated ledger, and raw
evidence are authoritative. `04_RUN_PLAN.html` and `05_EXP_RESULT.html` are
complete rendered views: every state/result change must rerun their full
renderers to temporary files, validate the pair, and atomically replace them.
Never fill a cell, move a goal panel, add provenance, or alter a plot by editing
the previously delivered HTML.

## Ownership and authorization

- `$expplan` owns the scientific and paper-artifact contract.
- `$runplan` owns goal decomposition, execution order, acquisition contracts,
  persistent state, and the researcher-selected execution mode.
- An activated goal owns implementation, runs, evidence capture, validation,
  and report refresh for exactly that goal.

Never infer authorization from silence. Build and show the complete hierarchy
before any paid/GPU work. Then ask the researcher to choose:

1. `sequential_all_goals`: execute the approved ordered goals automatically,
   preserving every goal boundary and stopping on any failed/non-continue gate;
2. `manual_each_goal`: present and approve one goal at a time.

## Validate the source plan

Default input is `reports/03_EXPERIMENT_PLAN.html`. Read its
`experiment-plan-contract` and require `approval_status=approved`, complete
`paper_outline`, `paper_artifacts`, `result_requirements`, metric and
measurement contracts, decision space, implementation contract, budgets, and
deterministic source routes.

Treat approved artifact geometry and table-defined dataset/metric semantics as
immutable. `$runplan` resolves execution splits from official protocols,
records disjoint dev/final data, assigns every decision ID to a goal, performs
all `SEARCHED` decisions on dev, and freezes configuration before final
evidence.

Read [`references/input-and-funnel.md`](references/input-and-funnel.md) while
validating the input and building the hierarchy.

## Evidence funnel and goals

Order work by information value:

`S0 minimal infrastructure → S1 phenomenon/motivation → S2 method feasibility
→ S3 development tuning → S4 primary evidence → S5 breadth/robustness → S6
explanation/cost/failures`.

Use stable major parts `P1`, `P2`, … and executable subgoals `G1.1`, `G1.2`, ….
Each goal is the smallest independently runnable, verifiable evidence slice.
Conditional goals remain visible but locked. Group work only when it answers
one decision and remains one interpretable milestone.

Every approved artifact must have at least one owning goal; every acquisition
target must have exactly one producing goal. Count-only conceptual figures map
to the goal that establishes their specification but receive no numeric
acquisition contract.

## Durable state and evidence

Maintain:

- `reports/04_RUN_PLAN.html`: the human-readable hierarchy and sole run-plan
  state container;
- embedded `<script id="run-plan-state" type="application/json">` as the only
  machine state;
- `code/RESULTS_LEDGER.csv`: append-only canonical result ledger;
- `reports/05_EXP_RESULT.html`: cumulative paper-shaped artifacts and
  provenance generated only from validated ledger rows;
- runnable code under `code/` and raw/derived outputs under
  `results/<project>/`.

Do not create a sidecar run-state file or expose the ledger as a user-facing
tab. Preserve `03` as the approved blank blueprint.

Read [`references/state-and-acquisition.md`](references/state-and-acquisition.md)
while creating embedded state, acquisition contracts, and the ledger.

## Execution modes and goal boundary

Before confirmation, expose no Current Goal. After confirmation, place exactly
one complete Current Goal panel inside its matching goal card. A copied `/goal`
command is a recovery/manual affordance, not the main workflow.

Each executor must verify predecessors and proposed goal ID, mark only its goal
running, stay inside approved decisions/budget/splits, persist every atomic
result before the next run, derive aggregates only from saved full-precision
operands, refresh `05`, validate provenance, update `04`, and evaluate the
approved gate. Negative evidence is valid completion evidence.

Automatic mode advances only on `continue`. Stop on `refine`, `pivot`,
`stopped`, `blocked`, validation failure, exhausted budget, or a new
researcher-controlled decision. Manual mode proposes the next goal and stops.

Read [`references/execution-modes.md`](references/execution-modes.md) before the
confirmation gate and during every goal boundary.

## Reports and validation

`04` must show execution estimates, inherited implementation sources, complete
artifact coverage, and the nested part/goal hierarchy with durable status
marks. Every completed Goal must show each owned figure together with its
adjacent source-data table; qualitative figures use an evidence-input table and
must not invent numeric values. `05` must preserve each approved paper
table/figure geometry, pending and filled targets, actual data-driven plots,
and clickable/hoverable provenance.
An artifact appears once under its earliest owning goal and is updated there as
later goals fill additional targets.

Read [`references/results-and-html.md`](references/results-and-html.md) while
rendering or validating `04` and `05`.

At every resume and goal completion run the ledger/provenance tools required by
those references, then run:

```bash
python3 research_avatar/tools/validate_report_structure.py --kind runplan --html reports/04_RUN_PLAN.html
python3 research_avatar/tools/validate_report_structure.py --kind results --html reports/05_EXP_RESULT.html
```

Progress marks, the Current Goal position, and embedded artifact snapshots must
already be derived by the complete `04` renderer before these validators run;
do not use a later HTML mutation step to make them pass.

Do not mark a goal complete until all of its scoped targets, raw evidence,
ledger rows, provenance links, report cells/plots, files, and checks exist.
Missing evidence is `MISSING`; failed provenance is `INVALIDATED`; never
estimate or recover a value from chat.

For fabricated skill tests, apply the visible banner
`SKILL-TEST — fabricated data, NOT a scientific result` and a `SYNTHETIC`
watermark throughout the artifact set.
