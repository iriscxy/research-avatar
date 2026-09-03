---
name: "runplan"
description: "Turn an approved EXPERIMENT_PLAN.html into a resumable, evidence-ordered hierarchy of executable goals that fill its projected-paper figure and table targets. Give every datum a deterministic acquisition contract, present the full hierarchy, and let the researcher approve automatic sequential execution or one-goal-at-a-time review."
---

# Run Plan

Run once per project session and at the start of an activated goal:

```bash
python3 -m research_avatar.research_studio.server --ensure
```

`/runplan` converts an approved scientific plan into an execution graph. It
does not redesign the science. A schema, claim, metric, dataset, baseline,
search-space, or artifact change returns to `/expplan` for amendment and renewed
approval.

The approved `03` contract, embedded run state, validated ledger, and raw
evidence are authoritative. `04_RUN_PLAN.html` and `05_EXP_RESULT.html` are
complete rendered views: every state/result change must rerun their full
renderers to temporary files, validate the pair, and atomically replace them.
Never fill a cell, move a goal panel, add provenance, or alter a plot by editing
the previously delivered HTML.

## Ownership and authorization

- `/expplan` owns the scientific and paper-artifact contract.
- `/runplan` owns goal decomposition, execution order, acquisition contracts,
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
immutable. `/runplan` resolves execution splits from official protocols,
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

Every approved result requirement must have exactly one producing goal. Only
artifacts with at least one `result_requirements` entry belong to RunPlan
coverage, Goal ownership, `04`, `05`, or the result ledger. A conceptual,
motivation, mechanism, or other writing-stage figure with no acquired datum
remains in `03` for Paper Writing and must not be drawn or embedded in RunPlan.

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

Copy every approved metric's stable `metric_id`, unit, evidence source, input
schema, and calculation into each acquisition contract. The ledger validator
must reject reinterpretation. `HUMAN_ANNOTATION` requires the real annotation
file, rubric, blinded item/annotator IDs, and label fields; an LLM judge cannot
fill it. `LLM_JUDGE` instead preserves its model, prompt file, raw judgments,
and calibration record.

After every baseline implementation or reproduction goal, persist a
`reideation_checkpoint`. It records whether conformance passed, whether a
scientifically relevant mismatch remained after adapter repair, and the exact
command/raw artifact that demonstrates the mismatch. If a verified anomaly
remains, also record `observed_mismatch` and the baseline's intended
`baseline_contract`, then run:

```bash
python3 research_avatar/tools/prepare_reideation_handoff.py
```

This atomically refreshes `reports/.build/reideation_input.json`, so the next
IdeaGen pass receives the verified failure without manual copying. `04` shows a
user decision card offering `/ideagen`; it does not silently replace the
researcher's selected project. If no anomaly remains, render a compact "not
triggered" checkpoint and still refresh the handoff file so a stale anomaly
cannot be reused.

For scientific-integrity-v3 plans, execution coverage is not scientific
success. At every Goal boundary, mechanically evaluate every newly decidable
Claim, apply its preregistered outcome-to-action mapping, and stop before any
successor when the action is not `continue`. Keep the Claim decision visible in
`04`, not only in embedded state; the strict validator must reject a completed
queue that crossed a `refine`, `pivot`, `stopped`, or `blocked` boundary.

Automatic mode advances only on `continue`. Stop on `refine`, `pivot`,
`stopped`, `blocked`, validation failure, exhausted budget, or a new
researcher-controlled decision. Manual mode proposes the next goal and stops.

Read [`references/execution-modes.md`](references/execution-modes.md) before the
confirmation gate and during every goal boundary.

## Reports and validation

`04` must show execution estimates, inherited implementation sources, complete
coverage of data-bearing experiment artifacts, and the nested part/goal
hierarchy with durable status marks. Every completed Goal must show each owned
experiment figure together with its
adjacent source-data table; qualitative figures use an evidence-input table and
must not invent numeric values. `05` must preserve each approved paper
table/figure geometry, pending and filled targets, actual data-driven plots,
and clickable/hoverable provenance.

Treat “how this value was obtained” as a reproducibility record, not a short
source note. For every locally produced value, the complete generation process
must identify the exact command actually executed, working directory,
executable entrypoint and code files, config and environment files, inputs,
raw outputs and locator, stdout/stderr logs, exit status, timestamps, code
revision, calculation or aggregation, and verification. Persist these facts at
execution time; never reconstruct them later from a command template or prose.
An artifact appears once under its earliest owning goal and is updated there as
later goals fill additional targets.

Goal and artifact status are derived from the latest validated ledger row for
every owned acquisition, never manually assigned. A completed goal requires a
current `REAL`/`VERIFIED` row for every acquisition. After final-evidence goals
complete, evaluate every claim only through its approved deterministic
`outcome_rule` and persist `claim_decisions`; ties, missing evidence, or an
interval that misses the registered condition cannot become `supported`.

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
