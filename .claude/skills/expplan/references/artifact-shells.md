# Experiment-backed artifact shells

Read this file while defining paper artifacts and their exact data contracts.
It continues the projected-paper blueprint at part (b.1).

(b.1) **Render only experiment-backed, fillable paper artifacts inline.** At
the exact point in the paragraph blueprint where a future empirical figure or
result table will be introduced, render its visible shell, not only its name in
an artifact ledger. A figure that needs no experiment, such as an Introduction
motivation figure or a Method overview, is count-only at `/expplan`: keep its
stable figure ID in the paragraph blueprint, artifact ledger, embedded
contract, and whole-paper figure total, but do not draw, mock, preview, create a
source table for, or add a result/acquisition requirement for it. Its actual
design belongs to the project-specific writing data, with `/figureppt` available only when explicitly requested after evidence is available.

**Introduction Figure / Figure 1 is a motivation figure by default.** Its
count-only contract must
make the problem and evidence gap understandable before revealing the method:
show a concrete failure or counterexample, why the existing observable can be
misleading, and the behavioral/evidentiary criterion the paper therefore
needs. It must not be an extraction pipeline, architecture diagram, algorithm
walkthrough, or method-module inventory; those belong in the Method section.
Do not render a conceptual example during `/expplan`; never invent quantitative
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
  the same series names and point order in the table and preview.
  Give every pending numeric source-table cell a stable non-visible
  `data-target-id` and include those cell IDs—not only a coarse panel ID—in the
  artifact's `result_requirements`. `/runplan` and `05_EXP_RESULT.html` must
  later fill these exact cells from validated ledger rows and generate the
  final plot from the displayed values; they must not create a second plot-only
  data source.
  Predefined categorical experimental conditions are column headers, not pending data
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
