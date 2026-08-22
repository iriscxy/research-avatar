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
  the approved table plus the execution split fixed by `/runplan`, model,
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
approved `/expplan` contract explicitly authorizes it; otherwise use
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
   Do not define new table rows/columns or figure panels inside `/runplan`.
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
missing requirements and cannot be handed to the browser writing stage as completed
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
