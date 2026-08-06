---
name: "runplan"
description: "Turn an approved EXPERIMENT_PLAN.html into a resumable, evidence-ordered experiment execution plan. Show the complete sequence of bounded goals, propose exactly one unlocked goal, and give the researcher a direct manual /goal command. This skill plans and proposes only; it never runs experiments. The /goal function performs the actual engineering and experiment work one milestone at a time. Use when the researcher says runplan, asks what experiment to run next, or wants to execute an approved experiment plan incrementally."
---

# Run Plan

`/runplan` is the only experiment-execution planning skill. It converts the
approved scientific scope into bounded goals; it does not execute them.

The ownership boundary is strict:

- `/expdesign` defines and receives approval for the scientific plan.
- `/runplan` creates/resumes the execution graph and proposes one goal.
- A researcher-issued `/goal` performs the actual code, engineering, runs,
  evidence collection, and report updates for that one goal.

Never run an experiment, call `create_goal`, or start a successor from
`/runplan`.

## 1. Validate the approved input

Default input: `reports/03_EXPERIMENT_PLAN.html`.

Read the JSON in its
`<script type="application/json" id="experiment-plan-contract">` block first.
Require `approval_status=approved`; a missing, invalid, or pending contract is
a hard stop back to `/expdesign`. Read `researcher-profile/PROFILE.md` only for
environment, stack, and OOM context. The researcher—not the agent—judges
whether scientific evidence supports a claim.

If the plan lacks a decisive motivation probe, dev/test separation, tuning
budget, runnable next-stage configuration, result schema, or required evidence,
return to `/expdesign`; do not invent research design during execution planning.

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
question, and remain one interpretable milestone.

## 3. Write durable plan and state

Create or resume:

- `code/RUN_PLAN.md`: the decision graph and ordered `G00`, `G01`, ... goal
  catalogue. Each goal records its decision question, dependencies, exact
  authorized runs, fixed variables, approved refinement budget, input/output
  paths, required checks, mechanical completion condition, falsifier,
  successor branches, and explicit exclusions.
- `code/RUN_STATE.json`: source-plan identity and approval, goal statuses,
  `proposed_goal_id`, active goal, completed results, frozen configuration,
  attempts, raw paths, gate decisions, amendments, skips, and exact next
  authorized action.

Use explicit states: `awaiting_goal_activation`, `running`, `completed`,
`refine`, `pivot`, `stopped`, and `blocked`. Use versioned, resume-safe outputs;
never overwrite prior results.

Map every embedded-contract `result_requirements` item to its producing goal,
artifact ID, raw file, JSON key path, and dimensions. Normal completion must
satisfy every requirement. An early `pivot` or `stop` path must enumerate the
missing requirements and cannot be handed to `/paperwrite` as completed
evidence.

Present the complete `RUN_PLAN.md` before proposing any paid/GPU work.

## 4. Propose exactly one manual goal

Choose only the first/next unlocked goal with the highest information value.
Store it as `RUN_STATE.json.proposed_goal_id`, then print one self-contained
command in this form:

```text
/goal Complete Gxx: <exact data slice, methods/comparisons, engineering work, checks, metrics, and stopping condition>; follow code/RUN_PLAN.md and code/RUN_STATE.json; save versioned raw outputs; update code/RUN_STATE.json and reports/04_EXP_RESULT.html; stop after Gxx, do not start Gyy, and only propose the next unlocked /goal.
```

Replace every placeholder with actual work. The command must make sense without
any skill name. It must never invoke `/runplan` or another skill, and it must
not use a vague instruction such as “run the next experiment.”

Tell the researcher: “If this goal looks right, run the `/goal` above manually;
I will not start it for you.” Then stop.

## 5. Contract for the `/goal` executor

The manually activated `/goal`—not `/runplan`—owns execution. Its direct command
and `RUN_PLAN.md` must require it to:

1. Verify the requested `Gxx` equals `proposed_goal_id`, all predecessors are
   complete, and no unrelated goal is active.
2. Mark only that goal `running`; perform its authorized implementation,
   smoke checks, experiments, and evidence collection autonomously.
3. Stay inside the approved variables, comparisons, search space, budget, and
   data split. Never tune on test data or redesign the scientific plan.
4. Persist versioned raw outputs and update `RUN_STATE.json` and
   `reports/04_EXP_RESULT.html`. Every reported number must trace to a raw file;
   missing evidence is `MISSING`, never an estimate.
5. Complete the goal only when its declared files and mechanical checks exist.
   Report negative results and uncertainty honestly; a goal means “produce
   evidence,” not “make the hypothesis succeed.”
6. Evaluate only the preregistered gate, record the result, propose the next
   unlocked or bounded refinement `/goal`, and stop. Printing the next command
   is not authorization to execute it.

If evidence requires a new claim, metric, dataset, baseline, or search space,
record `pivot` and return to `/expdesign` for amendment and approval. `refine` may
use only execution variables and budgets already authorized by the approved
plan. `stop` records why and lists missing evidence.

## 6. Result ledger

`reports/04_EXP_RESULT.html` is the cumulative, stage-ordered evidence ledger.
For each goal include status, dependencies, run/config ID, commands actually
run, raw paths, result summary, falsifier status, gate decision, negative
results, and next authorized action. Do not create a separate tracker HTML.

Synthetic skill tests must carry a prominent `SKILL-TEST — fabricated data,
NOT a scientific result` banner and `SYNTHETIC` watermark.

## Output

`reports/03_EXPERIMENT_PLAN.html` + `code/RUN_PLAN.md` +
`code/RUN_STATE.json` + runnable `code/` + versioned `results/` +
`reports/04_EXP_RESULT.html`.
