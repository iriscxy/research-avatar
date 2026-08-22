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
/goal Complete Gn.m: <plain-language description of the exact data slice, methods/comparisons, engineering work, checks, metrics, and stopping condition>; follow reports/04_RUN_PLAN.html and its embedded run-plan state; save each result immediately; before completing the goal, organize its code and files, remove only disposable temporary artifacts, and verify every recorded path; append and validate every result in code/RESULTS_LEDGER.csv; update the embedded state; regenerate the complete reports/04_RUN_PLAN.html and reports/05_EXP_RESULT.html from the approved contract, embedded state, and validated ledger into temporary files; validate the complete pair and atomically replace the prior rendered pair so the goal shows ✅, the single matching artifact snapshot remains under its earliest owning goal, and every filled number links to provenance; stop after Gn.m, do not start the successor goal, and only propose the next unlocked /goal.
```

Replace every placeholder with actual work. The command must make sense without
any skill name. It must never invoke `/runplan` or another skill, and it must
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
the validated evidence to the project writing inputs only if the user's request includes
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
   immediately rerun the complete `05` renderer from the approved contract and
   validated ledger. Publish the new report only after whole-report validation
   and atomic replacement; never edit the matching cell or provenance fragment
   in the prior HTML.
5. Run `python3 .claude/skills/runplan/scripts/validate_results_ledger.py
   --ledger code/RESULTS_LEDGER.csv --plan reports/04_RUN_PLAN.html --report
   reports/05_EXP_RESULT.html --goal Gn.m --strict-report` before accepting a
   gate or completing the goal. On every resume, run the validator before new
   work and reconcile failures first. Update embedded `run-plan-state.ledger_audit` with
   the check time/status and update `reports/05_EXP_RESULT.html` only from
   validated ledger rows. Missing evidence is `MISSING`, never an estimate.
   The full `05` renderer must emit `data-result-id` attributes, provenance
   anchors/summaries, and generation-process cards in the same render pass from
   the ledger. A separate script that linkifies or injects provenance into an
   already rendered report is forbidden.
6. At each resume and goal boundary, organize experiment code and
   result files, remove only disposable temporary/build artifacts, and verify
   all ledger paths still exist. Do not maintain a separate file inventory.
   In the same full render, derive the visible `reports/04_RUN_PLAN.html` from
   its embedded state so every newly completed item visibly changes to `✅`,
   the one nested Current Goal panel moves to the next `proposed_goal_id`, and
   each paper-facing artifact is embedded exactly once under its earliest owning
   goal with the current snapshot from the newly rendered `05_EXP_RESULT.html`.
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
record `pivot` and return to `/expplan` for amendment and approval. `refine` may
use only execution variables and budgets already authorized by the approved
plan. `stop` records why and lists missing evidence.
