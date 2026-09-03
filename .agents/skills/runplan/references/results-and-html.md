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
Only validated ledger rows may fill artifact targets; the browser writing workflow consumes
those validated rows and the filled `05` view rather than copying numbers from
conversation history.

For every final `claim_decision`, store the approved primary result ID and the
raw JSON locators of its confidence-interval bounds. The validator reloads the
point estimate and bounds, applies the approved threshold and direction, and
recomputes `supported`, `weakened`, `falsified`, or `inconclusive`; a manually
written outcome is never authoritative. When a producing Goal for a
`HUMAN_ANNOTATION` metric becomes `running` or `completed`, both the real
annotation file and rubric file must already exist or validation refuses the
transition.

Render a compact Claim-status board before the Goal catalogue. For every Claim
show the evidence-qualified outcome, whether its falsifier was triggered, the
primary result/evidence summary, and the next authorized action. Execution
coverage and scientific support are separate: the page may say every run is
finished while prominently requiring refinement or pivot, but it must never
present that state as unqualified scientific completion.

The `05` renderer must produce artifact cells, plots, provenance anchors,
provenance payload, and generation-process cards together from the same
validated ledger snapshot. It must render to a temporary file and publish only
after strict whole-report validation. DOM injection, regex replacement,
single-cell overwrite, and provenance post-processing of the delivered report
are invalid generation paths.

`05` must visibly render the **approved data-bearing experiment artifacts** in
paper order, not a prose summary of them. Determine this set from artifacts
named by `03.result_requirements`; never render a writing-only figure with no
acquired datum. Fill each result table's exact approved cells with validated
real values and uncertainty; render each experiment figure's approved panels as actual
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

“Beside” is required desktop geometry: place the source-data table on the left
and its corresponding plot on the right in a two-column row. Preserve this
left-table/right-plot arrangement when copying the figure into the
completed-Goal snapshot in `04`. Only a narrow responsive viewport may stack
the table above the plot; missing snapshot CSS must never silently turn the
desktop RunPlan layout into a vertical sequence.

Apply the same figure/table pairing to the completed-Goal snapshots in `04`.
Every owned data-bearing figure shown under a completed Goal must contain a table immediately
beside its visual. For a data-driven figure, copy the exact source-data table
from the same `05` artifact snapshot; the visible values, statuses, target IDs,
and provenance links must remain identical. Conceptual motivation or mechanism
figures without result requirements never enter `04` or `05`. A completed Goal
containing an experiment figure without its adjacent table is a hard validation
failure in both `04` and `05`.

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

At the end of `05_EXP_RESULT.html`, render one compact collapsible `Generation Process`
index with `id="result-provenance-index"` and a stable target
`id="provenance-<result_id>"` for every clickable value. Clicking a value must
update the page hash, open the matching card, move focus to it, and call
`scrollIntoView`; the browser Back action must remain meaningful. The card must
show:

- common fields: goal, metric/value/unit, dimensions, source type, acquisition
  kind, calculation/aggregation rule, obtained time, verified time, and
  verification status;
- `RUN_LOCAL`: raw artifact, exact JSON/JSONL locator, the command actually
  run, working directory, executable entrypoint, code files, config files,
  environment and input files, run-manifest path, stdout/stderr log paths, exit
  status, start/end timestamps, produced raw files, and code revision;
- `REUSE_REPORTED`: exact paper/dataset source and stable table/figure/row/
  column locator, plus a prominent statement that it was not rerun locally.
  Store that statement canonically as `reuse_notice="not rerun locally"` in
  the provenance payload and render it in reader-facing language.

Render numeric values with at most three decimal places unless the approved
display policy says otherwise, while retaining full precision in raw files and
the ledger. Display the unit or an explicit `unitless` marker. Derive every
Goal/artifact status badge from the latest validated acquisition rows: never
leave `PENDING` after all rows validate, and never show `FILLED` or `completed`
while a required row is missing or invalidated.

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
3. `3. Figure/Table Coverage` (`artifact-coverage`): the complete data-bearing experiment-artifact checklist;
4. `4. Parts and Goals` (`parts-and-goals`): ordered `Pn` parts with nested `Gn.m` goals, status, and destination. Before approval it shows the two-path Goal confirmation gate and no Current Goal. After approval, the exactly one Current Goal panel is nested inside the matching goal card and moves with `proposed_goal_id` / `active_goal`; its copyable `/goal` is only a manual/recovery affordance.

`05_EXP_RESULT.html` has exactly these ordered top-level sections:

1. `1. Artifact Completion` (`artifact-completion`);
2. `2. Paper Tables and Figures` (`paper-artifacts`): approved data-bearing artifacts in paper order with unchanged geometry and pending states;
3. `3. Generation Process` (`generation-process`): one collapsible provenance index containing raw path, actual command, code/config, calculation, and verification.

Every title in both files must own substantive project-specific content; an empty section, title-only slot, or placeholder-only body is invalid. Do not add, rename, reorder, or omit these sections. Before presenting either file, run `python3 research_avatar/tools/validate_report_structure.py --kind runplan --html reports/04_RUN_PLAN.html` and `python3 research_avatar/tools/validate_report_structure.py --kind results --html reports/05_EXP_RESULT.html` in addition to the ledger/result validators.

Never expose `RESULTS_LEDGER.csv` as a user-facing tab, table, preview, or download in Research Studio or the Live Demo. It remains an internal store used to generate and validate `05_EXP_RESULT.html`. Never add a third experiment-stage tab or a visible ledger-shaped table. The Live Demo must reproduce these two structures with illustrative content and working numeric hover/focus provenance plus the full click-through jump.

## Output

`reports/03_EXPERIMENT_PLAN.html` + `reports/04_RUN_PLAN.html` +
`code/RESULTS_LEDGER.csv` + runnable `code/` + `results/` +
`reports/05_EXP_RESULT.html`.
