## Output conventions
- **Shared `reports/` folder, two-digit prefixes:** this skill writes a single `reports/03_EXPERIMENT_PLAN.html`. **The paper skeleton is a SECTION INSIDE `03`, not a separate file** — the researcher considers the projected-paper structure to be part of the experiment plan itself. There is no separate paper-plan file.
- **Machine-readable approval contract:** embed one JSON object inside
  `reports/03_EXPERIMENT_PLAN.html` as
  `<script type="application/json" id="experiment-plan-contract">...</script>`.
  Do not write a separate manifest file. This hidden block is the exact
  downstream contract that `$runplan` and the browser writing workflow
  must check. It records stable claim IDs,
  experiment IDs, every promised paper artifact with a unique LaTeX label and
  permitted placement (`body` or `body_or_appendix`), required appendix labels,
  and the result key paths/dimensions needed to fill each artifact. Two planned
  artifacts may not share one label: an aggregate table never silently satisfies
  separately approved per-game and per-model tables.
- **One canonical numbering registry:** before rendering, collect every Projected
  Paper section ID, paragraph ID, artifact ID, artifact LaTeX label, result
  requirement ID, and result target ID from the embedded contract. Every value
  is non-empty and unique within its namespace. Generate visible figure/table
  numbering only from the ordered unique artifact records; never assign or
  repair numbers independently in HTML. The experiment-plan validator must
  reject the plan before approval when any registry contains a duplicate.
- **Minimal reader-facing section order:** render only `1. Target Conference and Reference Paper` (exactly two entries: target conference and the sole researcher-owned reference) → `2. Projected Paper` (prominent figure/table count, title, PROJECTED abstract, reference-mapped paper structure, concrete setup and baseline implementation inside the Experiments section, inline fillable empirical result shells, compact artifact ledger, and a compact approval control). Do not put the research question, implementation architecture, datasets, metrics, baselines, or any other setup material in Section 1. Do not render separate top-level sections for approval, claims, method/data/variables, experiment matrices, baseline registries, repository audits, run order, configs, budgets, risks, or grounding appendices. Those remain necessary internal design/decision inputs and machine-readable contract fields; Projected Paper must embody their paper-facing consequences.
- **Keep the research contract and decision meetings unchanged.** Preserve the venue, single-reference, baseline/reuse, repository, and final approval gates and their order. This reorganization does not bypass or merge any human decision.
- **Skill-test / fabricate-data run:** if this plan is part of an explicit skill-test (the downstream `results/` will be fabricated to exercise the pipeline), `03` must carry the same loud banner as the rest of the artifact set — `SKILL-TEST — fabricated data, NOT a scientific result` — at the top, so the whole `03`/`05` + paper set is consistently marked and none can pass as real (AGENTS.md discipline #1). The plan's own numbers stay `[X%]` placeholders marked PROJECTED regardless.
- **Self-contained HTML, never Markdown** — inline `<style>`, no external assets, real structure (`<h1>/<h2>`, `<table>`, `<ul>`); use **continuous tables as the primary layout** for structured content, never card/grid layouts. Embed projected PNG previews as `data:` URLs. Keep the table-first figure contract in `paper/figsrc/<project>/figure_schema.json`, reusable plotting code in `paper/fig/make_figs.py`, schema-conforming synthetic inputs in `paper/figsrc/<project>/projected_fixture.json`, and projected PDF/PNG outputs in `paper/fig/<project>/projected/`, so the browser writing workflow reuses the same schema/code and swaps only the metrics input. **Every paper reference a direct `<a href>`** to arXiv/DOI, unverifiable → visible `pending`, never fabricated.
- **Math variables must render as proper notation, not raw ASCII in a `<code>` span.** A subscripted or Greek variable like `b_dir` / `s_si` / `Δ_cross` / `θ*` / `Pz` reads as a defect when shown as `<code>s_si</code>`. Render it natively with italic `<var>` + `<sub>` + Unicode Greek — `<var>b<sub>dir</sub></var>`, `<var>s<sub>si</sub></var>`, `<var>&Delta;<sub>cross</sub></var>`, `<var>&theta;*</var>`, `<var>P<sub>z</sub></var>` — with a one-line style rule (`var{font-family:Georgia,serif;font-style:italic} var sub{font-style:normal;font-size:.72em}`). No external MathJax/KaTeX (breaks self-containment); these are simple subscripted vars, so `<var>/<sub>` suffices and renders with zero JS. Keep raw `results/` JSON field keys (e.g. `sim_runs.json:Pz`) as `<code>` — those are literal identifiers, not math.
- `reports/03_EXPERIMENT_PLAN.html` is the single canonical plan that `$runplan` reads. Address the researcher directly, never in the third person.

## Fixed HTML structure

Render `03_EXPERIMENT_PLAN.html` with exactly two ordered top-level sections (`<section data-report-section>` and visible `<h2>` text must agree):

1. `1. Target Conference and Reference Paper` (`target-and-references`);
2. `2. Projected Paper` (`projected-paper`).

Place the prominent one-line whole-paper figure/table count immediately below
the Section 2 heading. Then use exactly these ordered visible subsections:

1. `2.1 Projected Title and Abstract` (`projected-title-abstract`);
2. `2.2 Projected Paper Structure and Evidence Shells` (`projected-paper-structure`), including every paper section in manuscript order and each paper-shaped table/figure shell at its first planned paragraph.

Inside the projected Method section, render exactly one substantive
`<div data-model-design>` sourced from `grounding.model_design`. It must show
inputs, outputs, modules and their interactions, training stages and frozen
boundaries, method-defining objectives/equations, inference flow, and explicit
component-to-evidence links. For a one-goal-paper reconstruction it also shows
the goal-paper `source_authority`, the reconstruction policy, and any unknown
implementation choices; structural-reference prose is never a method source.
Keep it to one compact 8--14-row table (or equivalent) while also exposing the
ordered algorithm, symbol definitions, candidate/sampling construction,
normalization/update rules, disclosed model-defining configuration, one
explicit unknowns row, and `reproducibility_status`.

Inside the projected Experiments section, include one
`<div data-experiment-setup>` containing a fixed six-row
`<table class="setup-table">` and a two-column
`<table class="implementation-table">` headed `Method` and `Selection and implementation`.
The setup-table row labels are exactly `Dataset`, `Model`, `Baselines`,
`Proposed method`, `Noise and runs`, and `Metrics`, in that order. Values for
Dataset, Baselines, and Proposed method start with explicit counts. Do not put
paragraphs or long-form metric definitions in this block. The implementation
table covers the proposed method and every selected baseline exactly once, one
concise row each, including selection rationale, implementation decision, and
the supporting paper link for each literature-derived baseline. Result shells
follow inside that same paper section; do not use hard-coded manuscript numbers
such as `5.1` or `5.2` as report-level sentinels.

Keep the machine contract in hidden JSON and place the compact pending approval
control at the end of Section 2 without creating another top-level report
section. Every visible subtitle must own substantive plan-specific content; an
empty slot or placeholder-only body is invalid. Do not add visible registries,
acquisition audits, grounding appendices, workflow logs, or generic dashboards.
Before the approval gate, run `python3 research_avatar/tools/validate_report_structure.py --kind expplan --html reports/03_EXPERIMENT_PLAN.html` before the experiment-plan validator. Research Studio adds only the approval control; the Live Demo must display this exact hierarchy with filled illustrative content and pending result cells.
