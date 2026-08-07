---
name: "expplan"
description: "Design the scientific experiment program for a chosen research idea by working backward from a PROJECTED paper: every section's paragraphs summarized in one concrete sentence each, plus fillable result-table and figure shells. Define claims, falsifiers, baselines, datasets, metrics, ablations, evidence requirements, budgets, and repository grounding in reports/03_EXPERIMENT_PLAN.html for researcher approval. This decides what evidence and paper cells later experiments must fill; it does not schedule or run experiments. Stops at the approval gate before /runplan converts the approved design into executable goals. Invoke explicitly as `/expplan`."
---

Read `researcher-profile/PROFILE.md` (at the project-local `researcher-profile/` path) first; it is the only profile document and canonical source. If absent, tell the user to run `/profileconstruct`.

**Which idea to plan (resolve in order):** (1) explicit argument wins — a standard idea id (`I3`), disruptive wildcard id (`D1`), rank number, or free-text idea; (2) else read the `SELECTED` stamp in `reports/02_IDEA_REPORT.html` and echo its exact `I<k> — <title>` or `D1 — <title>` so a wrong pick is caught early; (3) report present but nothing stamped / id mismatch → don't guess, ask the user directly to pick; (4) no report → point to `/ideagen` (or accept a full free-text idea). Read the chosen idea's full row and card (mechanism / hypothesis / decisive falsifier / MVE / closest work) as the plan seed. For `D1`, preserve its broken-assumption claim and decisive falsifier as the plan's first gate; do not normalize it back into an incremental module.

## Output conventions
- **Shared `reports/` folder, two-digit prefixes:** this skill writes a single `reports/03_EXPERIMENT_PLAN.html`. **The paper skeleton is a SECTION INSIDE `03`, not a separate file** — the researcher considers the projected-paper structure to be part of the experiment plan itself. There is no separate paper-plan file.
- **Machine-readable approval contract:** embed one JSON object inside
  `reports/03_EXPERIMENT_PLAN.html` as
  `<script type="application/json" id="experiment-plan-contract">...</script>`.
  Do not write a separate manifest file. This hidden block is the exact
  downstream contract that `/runplan`, `/papergapcheck`, and `/paperwrite`
  must check. It records stable claim IDs,
  experiment IDs, every promised paper artifact with a unique LaTeX label and
  permitted placement (`body` or `body_or_appendix`), required appendix labels,
  and the result key paths/dimensions needed to fill each artifact. Two planned
  artifacts may not share one label: an aggregate table never silently satisfies
  separately approved per-game and per-model tables.
- **Minimal reader-facing section order:** render only `1. Target Conference and Reference Papers` (exactly three entries: target conference, external mechanism reference, researcher-owned structure reference) → `2. Projected Paper` (title, PROJECTED abstract, one concrete planning sentence for every paragraph in every section, inline fillable empirical result shells, compact artifact ledger, page-fill check) → `3. Approval`. Do not put the research question, implementation architecture, datasets, metrics, baselines, or any other contract material in Section 1. Do not render separate visible sections for claims, method/data/variables, experiment matrices, baseline registries, repository audits, run order, configs, budgets, risks, or grounding appendices. Those remain necessary internal design/decision inputs and machine-readable contract fields; Projected Paper must embody their paper-facing consequences.
- **Keep the research contract and decision meetings unchanged.** Preserve the existing venue, two-reference, baseline/reuse, repository, and final approval gates and their order. This revision changes what `2. Projected Paper` renders and what its signed artifact/result contract contains; it does not bypass or merge any human decision.
- **Skill-test / fabricate-data run:** if this plan is part of an explicit skill-test (the downstream `results/` will be fabricated to exercise the pipeline), `03` must carry the same loud banner as the rest of the artifact set — `SKILL-TEST — fabricated data, NOT a scientific result` — at the top, so the whole `03`/`05` + paper set is consistently marked and none can pass as real (AGENTS.md discipline #1). The plan's own numbers stay `[X%]` placeholders marked PROJECTED regardless.
- **Self-contained HTML, never Markdown** — inline `<style>`, no external assets, real structure (`<h1>/<h2>`, `<table>`, `<ul>`); use **continuous tables as the primary layout** for structured content, never card/grid layouts. Embed projected PNG previews as `data:` URLs. Keep the table-first figure contract in `paper/figsrc/<project>/figure_schema.json`, reusable plotting code in `paper/fig/make_figs.py`, schema-conforming synthetic inputs in `paper/figsrc/<project>/projected_fixture.json`, and projected PDF/PNG outputs in `paper/fig/<project>/projected/`, so `$paperwrite` reuses the same schema/code and swaps only the metrics input. **Every paper reference a direct `<a href>`** to arXiv/DOI, unverifiable → visible `pending`, never fabricated.
- **Math variables must render as proper notation, not raw ASCII in a `<code>` span.** A subscripted or Greek variable like `b_dir` / `s_si` / `Δ_cross` / `θ*` / `Pz` reads as a defect when shown as `<code>s_si</code>`. Render it natively with italic `<var>` + `<sub>` + Unicode Greek — `<var>b<sub>dir</sub></var>`, `<var>s<sub>si</sub></var>`, `<var>&Delta;<sub>cross</sub></var>`, `<var>&theta;*</var>`, `<var>P<sub>z</sub></var>` — with a one-line style rule (`var{font-family:Georgia,serif;font-style:italic} var sub{font-style:normal;font-size:.72em}`). No external MathJax/KaTeX (breaks self-containment); these are simple subscripted vars, so `<var>/<sub>` suffices and renders with zero JS. Keep raw `results/` JSON field keys (e.g. `sim_runs.json:Pz`) as `<code>` — those are literal identifiers, not math.
- `reports/03_EXPERIMENT_PLAN.html` is the single canonical plan that `/runplan` reads. Address the researcher directly, never in the third person.

## B — Experiment plan → `reports/03_EXPERIMENT_PLAN.html`

### Mandatory target-venue confirmation — FIRST, before references

Fix the intended submission venue **before selecting either reference paper or designing the experiment plan**. A venue inherited from an old draft, a profile preference, or an assistant default is not confirmation.

1. Build a short venue slate from the chosen idea's topic/contribution type and the researcher's Active Venues. For each serious candidate, show: exact venue/track and submission cycle, why the idea fits, the main fit risk, the current official body-length/template rule, and a verified deadline status (`open`, `upcoming`, `passed`, or `call_pending`). Venue deadlines and rules are time-sensitive, so verify them from the venue's official site and link the source; mark anything unavailable as `call_pending`, never infer it. A passed cycle must be visibly labeled passed and cannot be presented as an ordinary active submission target.
2. Recommend one candidate in plain language, but ask the researcher directly to `confirm venue: <venue/track/cycle>` or name a replacement.
3. **STOP until the researcher explicitly confirms one exact venue/track/cycle.** Do not propose the two-reference pair, build the baseline registry, search repositories, or write/revise `03_EXPERIMENT_PLAN.html` before this confirmation.
4. Treat the confirmed venue as part of the plan contract. Record it in the final HTML metadata and in the first top-level section, including the verified page/word limit, official rules link, and `deadline_status`. If the status is `passed`, confirmation must also capture a dated `deadline_override` with the researcher's explicit reason and intended use (`internal feasibility`, `preprint`, or `next cycle`); without that override, stop and do not generate `03`.
5. If the researcher later changes the venue, invalidate the reference confirmation and every venue-dependent page-fill/structure decision; return to this gate, then reconfirm the two-reference pair. Baseline and repository decisions need reconfirmation only when the venue change affects their scientific or feasibility assumptions.

The gate order is mandatory: **target venue → two references → baselines/reuse → datasets → repositories → write `03` → final plan approval**.

### Mandatory two-reference confirmation — BEFORE writing `03`

Every plan must use **two distinct, role-separated reference papers**:

1. **External mechanism reference** — the closest non-author paper to the chosen idea. It is the **scientific-content authority**: use it to ground the paper's substantive problem, mechanism, claims, method/experiment content, datasets, metrics, baselines, analyses, and must-beat comparison floor.
2. **Researcher-owned writing/structure reference** — one paper authored by the researcher, verified against the Publications Index in `researcher-profile/PROFILE.md`. It is the **structure-only authority**: use it for section order, each paragraph's rhetorical job, section proportions, and figure/table rhythm. Never import its research problem, theory, claims, method, experiments, or findings merely because its structure is being followed. Rank candidates by target-venue compatibility first, then by how well their section architecture matches the current contribution type and required evidence flow, then by task/method similarity; among viable owned papers, choose the one whose structure best fits the new paper.

These roles may not collapse into one paper. If the closest mechanism paper is authored by the researcher, keep it in the researcher-owned role and select a separate external mechanism reference. **Only after the target venue is explicitly confirmed**, and before any baseline interaction, repository interaction, or `03_EXPERIMENT_PLAN.html` drafting:

- show the proposed pair in the conversation with title, authorship role, venue/year, direct link, local full-text path/status, and one plain-language sentence explaining why each was chosen;
- ask the researcher directly to `confirm references` or replace either paper;
- do not write or revise `03` until the researcher explicitly confirms both;
- after confirmation, read the external paper's experiments/setup/results and the researcher-owned paper's full structure, including abstract, every body heading, **the purpose and progression of every paragraph in every section**, and every body figure/table with its insertion point;
- if no researcher-owned full text is available, say exactly what is missing and ask the researcher to nominate a paper or explicitly approve a named fallback; never silently substitute an external paper;
- reconfirm the pair whenever the selected idea or target venue changes.

Record the confirmed pair once in `1. Target Conference and Reference Papers`, with the two roles kept explicit. Do not repeat a separate `Confirmed references` block later in the report. Resolve **structure** conflicts as target-venue rules/template → researcher-owned structure reference; resolve **scientific-content** conflicts as approved idea/claim contract → external mechanism reference → supplementary grounded papers. The owned paper never overrides the new paper's mechanism content, and the external paper never silently overrides the chosen structural architecture.

**FIRST, read the full text of the closest papers — do not guess the comparison set.** Pull the actual experimental setup of the 2–4 closest papers to the idea (from its *closest work* + the *Literature Landscape* in `reports/02_IDEA_REPORT.html`): fetch full text (`tools/fetch_fulltext.py` / `pdftotext` / web open/fetch), read the **experiments/setup section + result tables**, and extract the concrete **baselines, datasets, metrics, and reusable variables** they use. That is what tells you what to beat, on what data, and which quantities can be validly measured; a plan from memory is guessing. For every variable introduced by the plan, state whether it is directly reused from prior work, adapted from prior work, or newly proposed by this plan. Newly proposed variables must be marked `PROPOSED` and need a feasibility check before they can support a claim. Unfetchable paper → mark `[UNVERIFIED]`, don't invent. Maintain the full grounding record internally and in the hidden embedded contract; do not render a visible grounding table/appendix. Put direct source links only where they support a Projected Paper paragraph, artifact shell, or compact Research Contract decision.

**Primary reference — whose datasets/metrics/baselines are the must-cover floor.** Before building the plan's dataset/baseline list, determine which grounded paper is the primary reference. Resolve in this order:

- **Rule 1 — researcher's own closest paper.** If the idea builds on a paper the researcher authored (check PROFILE.md Publications Index), that paper IS the primary reference. Its datasets, metrics, and baselines are the **must-cover floor** (labeled `[P]` throughout the plan). Other papers' datasets/baselines are **recommended supplements** (labeled `[S]`), included only if they add coverage without conflicting with the primary.
- **Rule 2 — highest relevance + impact among the closest papers.** If the researcher has no directly relevant paper of her own (new direction), score each grounded paper on: **relevance** (how closely its task/method matches the idea, 1–5) + **impact** (citations weighted by venue tier, 1–5). Take the highest total as the surrogate primary. If tied, relevance beats impact — matching the task matters more than raw prestige for experimental design.

When grounded papers have **conflicting datasets/metrics** (same name but different version or computation), do NOT silently merge them. Keep both in the internal grounding record with their source paper noted, resolve the conflict in the existing decision meeting, and freeze only the approved choice into the Projected Paper shell and hidden contract. Data splits are outside `/expplan` and must not be discussed, selected, stored, or validated here.

### Baseline taxonomy, recommendation, result reuse, and interactive human selection

Baseline planning must be derived from the experimental sections and result tables of multiple relevant papers, not from one paper and not from memory. Use the 2–4 closest papers already required above, and expand to additional directly relevant papers only when needed to establish a stable taxonomy, identify a recent category-specific state of the art, or resolve conflicting baseline conventions.

#### 1. Derive the baseline taxonomy from the literature

Before choosing individual baselines, infer the method-family taxonomy used across the relevant papers. The following four broad families are mandatory when they exist in the task:

- **Traditional / classical baselines**: heuristic, probabilistic, matrix-factorization, graph-statistical, rule-based, or other non-deep methods.
- **Deep-learning baselines**: neural sequence, graph neural network, representation-learning, multimodal neural, or other trained non-LLM methods.
- **LLM-based baselines**: methods whose main prediction, ranking, representation, reasoning, or generation component is an LLM.
- **Tool-using / agentic baselines**: methods that retrieve external evidence, invoke tools/APIs/search, use planners or multi-agent workflows, or otherwise depend on tool-mediated execution.

Do not force a paper into only one family when it is genuinely hybrid. Assign one **primary family** and, when necessary, one or more **secondary tags**, such as `LLM + tool-using`, `deep-learning + multimodal`, or `LLM + graph`. Add a domain-specific family or subfamily only when at least two relevant papers use a comparable distinction and the extra category improves experimental interpretation.

State explicitly:

- the taxonomy and the papers that support it;
- the selected idea's **primary family**;
- any secondary / hybrid tags;
- why this classification determines which baselines are scientifically necessary.

#### 2. Build the complete baseline candidate registry

Collect every baseline that appears in the grounded experimental comparison sets of the relevant papers. Do not silently drop a baseline merely because it is old, expensive, unavailable, or probably optional. Deduplicate aliases and spelling variants, but preserve version distinctions when they change the method or protocol.

Assign stable IDs `B1`, `B2`, `B3`, ... across the complete registry. For each baseline record, maintain the following internal fields:

- baseline name and paper/link;
- primary family and secondary tags;
- which grounded papers compare against it;
- comparison frequency across the grounded papers;
- scientific role, such as `foundational`, `widely-used floor`, `closest prior method`, `current-family SOTA`, `cross-family control`, `tool-use control`, or `optional breadth`;
- recommendation tier;
- dataset / metric compatibility with the proposed plan;
- implementation or official-code availability when known;
- estimated reproduction burden;
- reported-result reuse status;
- short reason for including or excluding it from the recommended run set.

Keep these candidate/audit fields for the decision meeting and hidden contract; do not render a visible candidate overview or detailed audit in the final HTML.

Use these recommendation tiers:

- **Required**: must normally be selected because it is the primary reference method, the closest direct competitor, a baseline repeatedly used across the grounded papers, or the strongest verified method in the selected idea's primary family.
- **Strongly recommended**: materially improves comparison coverage, represents another important family, or is a recent competitive method with compatible data and metrics.
- **Optional**: scientifically useful but redundant, expensive, weakly compatible, unavailable, or mainly needed for breadth.
- **Citation only**: relevant for positioning but not a fair or feasible experimental comparison.

Assign these tiers only after estimating the resulting experiment matrix. A
recommendation must account for the number of datasets, target models,
baselines, conditions, seeds/repetitions, judge calls, and any attacker-model
calls. The default recommended set is the smallest claim-complete comparison
set: normally one strongest method per scientifically distinct role/family plus
the direct control and closest competitor. Demote a redundant candidate when
it adds mostly repeated runs rather than a new falsifier or coverage axis. Do
not label many candidates `Strongly recommended` and then mechanically create
an infeasible recommended shortcut. Show the approximate run/query multiplier
of the proposed shortcut before asking the user.

"Current-family SOTA" must be based on the newest directly comparable evidence available in the grounded papers or verified public sources. Do not label a method `SOTA` merely because it is recent. If the evidence is insufficient, write `SOTA status unverified`.

#### 3. Analyze whether published baseline results may be reused

Construct a cross-paper result-provenance check for each baseline. Multiple papers reporting the same baseline name or the same numeric value does not automatically make the result reusable.

A published result may be marked **eligible for reported-result reuse** only when all material protocol fields are verified to match:

- dataset name, version, and filtering;
- candidate set and negative-sampling policy;
- preprocessing and feature/modalities available to the baseline;
- metric definition, cutoff `K`, averaging, and evaluation script;
- baseline version/backbone and material hyperparameters;
- test-time protocol, prompt/judge settings when applicable.

Classify each result as:

- `REUSE_ELIGIBLE_REPORTED`: protocol is verified equivalent; the number may be cited as a literature-reported result.
- `RERUN_PREFERRED`: protocol appears equivalent, but fairness, code availability, implementation drift, or integration with the proposed pipeline makes a local rerun preferable.
- `NO_REUSE`: any material field conflicts.
- `REUSE_STATUS_UNKNOWN`: evidence is incomplete.

When identical numbers appear in multiple papers, determine whether they are independent reproductions or copied from a common original source. Record the original source when traceable. Do not treat repeated copied numbers as independent confirmation.

A reused number must never be presented as locally reproduced. In the HTML, annotate it as:

`Reported result reused from <paper/table>; not rerun in this project.`

`<paper/table>` must be an exact source, such as `P2, Table 3` or `Author et al. (2025), Table 4`. A vague phrase such as `from grounded paper tables`, `when sufficiently matched`, or `from prior work` is not acceptable.

Do not average results from different papers. Do not reuse a result after changing the candidate pool, preprocessing, metric implementation, model backbone, prompt, evaluator, or test protocol. Split equivalence is deliberately unresolved here; `/runplan` must verify it before execution, so an otherwise reusable value defaults to a local rerun when equivalence cannot later be proven. For a main headline comparison, prefer rerunning the strongest selected baseline when feasible.

If any required protocol field or exact table source remains unresolved, the action cannot be `REUSE_REPORTED`; use `RUN_LOCAL`, `CITATION_ONLY`, or ask the researcher to decide after seeing the uncertainty.

#### 4. Mandatory baseline-selection interaction

Baseline selection must happen **during the `/expplan` conversation, after the complete registry and taxonomy are built, and before repository discovery or final HTML generation**. The HTML records the decision; it is not the interface used to collect it.

1. **Show the taxonomy and classify the current idea.** Keep the explanation concise but explicit.

2. **Show every baseline candidate, grouped by family and ordered by recommendation tier.** Use a numbered list such as:

   `B1. Method — family — Required — role: closest competitor — reuse: RERUN_PREFERRED`

   Do not show only the recommended subset. The researcher must be able to see the complete grounded candidate set.

3. **Print the shortcut expansions, then ask the baseline-selection question with `ask the user directly`.**

   Immediately before asking, print a compact **Selection shortcuts** block. It must explicitly expand the tier shortcuts into baseline IDs and names:

   - `Required`: list every `Required` baseline as `B<ID> Method`;
   - `Strongly recommended`: list every `Strongly recommended` baseline as `B<ID> Method`;
   - `required selects`: repeat the exact `Required` IDs and names that will be selected;
   - `recommended selects`: repeat the exact union of `Required + Strongly recommended` IDs and names that will be selected;
   - `all selects`: state that it selects every listed experimental baseline except `Citation only`, and preferably list the IDs when the list is not excessively long.

   Use this compact format (list each tier's members, then the exact IDs each shortcut selects):

   ```text
   Selection shortcuts
   Required:            B4 GETNext, B9 MMPOI, ...
   Strongly recommended: B2 BPR, B3 SASRec, ...
   → required selects:    B4, B9, ...
   → recommended selects: B2, B3, B4, B7, ...   (Required + Strongly recommended)
   → all selects:         every B* except Citation only
   ```

   Do not print only the words `required` and `recommended`; the researcher must see exactly which methods each shortcut expands to before answering.

   Then call `ask the user directly`. Accept:

   - `B1,B3,B7` or `1,3,7` to select specific baselines;
   - `all` to select every listed experimental baseline except `Citation only`;
   - `required` to select exactly the printed `Required` set;
   - `recommended` to select exactly the printed union of `Required` plus `Strongly recommended`;
   - `none` to select no experimental baseline, while clearly warning that the plan may become scientifically invalid.

   Multiple selections are allowed. Never silently add an unselected baseline. If a `Required` baseline is omitted, summarize the resulting scientific risk and ask for explicit confirmation before continuing. Unknown IDs, contradictory forms such as `all,none`, or ambiguous prose require clarification rather than guessing.

4. **Resolve result-reuse decisions for the selected baselines.** If no selected baseline is `REUSE_ELIGIBLE_REPORTED` or `RERUN_PREFERRED`, continue without another question. Otherwise show the eligible candidates and ask one compact `ask the user directly`:

   - `reuse all eligible`;
   - `rerun all`;
   - or a mixed decision such as `reuse B2,B5; rerun B3`.

   `RERUN_PREFERRED` defaults to rerun unless the researcher explicitly approves reuse. `REUSE_ELIGIBLE_REPORTED` may be reused only after explicit approval. If the response is ambiguous, ask again.

5. **Resolve one exact execution action for every selected baseline.**

   Every selected baseline must have exactly one action:

   - `RUN_LOCAL`;
   - `REUSE_REPORTED`;
   - `CITATION_ONLY`.

   Do not write ambiguous states such as `run locally or citation-only`, `reuse when sufficiently matched`, or `pending between rerun and reuse`. If evidence is insufficient to authorize reuse, choose `RUN_LOCAL` or ask the researcher to downgrade it to `CITATION_ONLY`.

6. **Summarize the resolved baseline contract before repository discovery.** State:

   - selected baselines;
   - unselected Required baselines and accepted risks;
   - the exact `RUN_LOCAL` / `REUSE_REPORTED` / `CITATION_ONLY` action for each selected baseline;
   - the selected idea's family coverage;
   - any family or scientific-role gaps created by the selection;
   - which claims become weaker when a Required baseline is omitted.

Only after this baseline contract is resolved should dataset selection begin. An unselected baseline may still appear in Related Work or the complete candidate table, but its repository must not be treated as necessary for the approved execution plan.

### Mandatory dataset-selection interaction — before repository discovery or HTML

Treat dataset/benchmark selection as a separate human decision, not an
assistant inference hidden in Setup prose. After baselines are resolved and
before repository discovery or any `03` generation/re-generation:

1. Build a concise candidate slate from the confirmed references and selected
   baselines. Give each candidate a temporary conversation ID (`DS1`, `DS2`,
   ...), exact dataset/benchmark name and version when applicable, direct
   source and direct citation link, scientific role, compatible planned metrics, coverage gained,
   expected collection/reproduction burden, and any material access/license
   limitation. Do not discuss or choose train/dev/test splits here.
   Separate candidates visibly into (a) headline evaluation benchmarks, (b)
   mechanism/diagnostic datasets, and (c) construction corpora or baseline
   resources. Do not count all three categories as if each caused the same
   evaluation multiplier, but include their real collection, preprocessing,
   storage, and query burden in the recommendation.
   When matching the external mechanism reference's experiment breadth, compare
   and recommend the number of headline evaluation benchmarks against that
   reference's headline benchmark count. Do not inflate this count with benign
   controls, diagnostic samples, retrieval corpora, or baseline-owned resources.
   List those supporting sources separately as analysis/method inputs, not as
   additional headline datasets.
2. Mark each candidate `Required`, `Strongly recommended`, or `Optional`, and
   print the exact expansion of `required`, `recommended`, and `all` shortcuts.
   Before assigning tiers, estimate the full workload induced by
   `benchmarks × target models × baselines × conditions × repetitions/judges`.
   The `recommended` shortcut must be the smallest set that can support every
   approved headline and diagnostic claim within the rough budget; it is not a
   literature-coverage wishlist. More than two headline evaluation benchmarks
   requires an explicit non-redundancy justification and a feasible workload
   estimate. Prefer moving a redundant benchmark to `Optional` over silently
   multiplying the whole main table.
   Dataset shortcut IDs and their count refer to headline evaluation benchmarks
   only. Supporting diagnostic data and construction corpora require explicit
   provenance and burden notes, but must not be mixed into the shortcut as if
   they were full evaluation benchmarks.
3. Call `ask the user directly` and accept explicit IDs or one printed
   shortcut. Never silently add a candidate. If a Required dataset is omitted,
   show which claim/comparison becomes weaker and require explicit confirmation.
4. Summarize the exact selected dataset names and their role, then ask for a
   final `confirm datasets` when the preceding answer was not already an
   unambiguous explicit confirmation.
5. Stop until confirmation. Only after confirmation may repository discovery
   and HTML generation continue. Put selected dataset names directly in the
   Setup paragraph and result-table headers/captions. Do not create a dataset
   registry; record only a boolean/timestamp confirmation marker in the hidden
   contract because the visible tables remain the authority. In the generated
   HTML, link every selected dataset name in Setup, result-table headers/notes,
  and figure data-source tables to its original dataset/protocol paper or
   official repository; a dataset without a verified citation remains pending.

#### 7. Baseline decisions in the minimal HTML

Do not render baseline taxonomy, candidate overview, selection contract, reuse
audit, or omitted-baseline audit as separate visible sections. Preserve the
full resolved decision in the hidden contract. In the visible Projected Paper:

- selected experimental baselines appear directly as rows/series in the
  relevant result shells;
- cite every selected baseline directly in the Setup paragraph. Keep result
  table row labels, figure legends, and adjacent figure data-source tables as
  plain method names without repeated links. A generic control with no unique
  original paper links in Setup to the grounded paper whose protocol defines
  that control and is visibly labeled `control`;
- immediately after the Setup prose, show one concise implementation-source
  entry for every selected baseline and the proposed method. Each entry names
  exactly one resolved mode (`REUSE_OFFICIAL_MODULE`,
  `SOURCE_GUIDED_REIMPLEMENT`, `PAPER_GUIDED_REIMPLEMENT`, or
  `SELF_IMPLEMENT`), links the approved GitHub/paper source when one exists,
  states which module is reused versus written locally, and names the shared
  framework boundary. Do not hide this only in repository metadata and do not
  use ambiguous language such as “reuse or reimplement.” Store the identical
  ordered list as `implementation_contract` in the embedded contract so
  `/runplan` can inherit it without reinterpretation;
- approved metrics/datasets/settings appear directly as columns, axes, or
  panels;
- in Setup, give every metric its provenance class (`DIRECT`, `ADAPTED`, or
  `PROPOSED`), canonical name, exact formula or evaluator rule, score range,
  decision threshold/cutoff when one exists, aggregation rule, definition
  source, and direct citation. A proposed metric cites its closest grounding
  protocol while remaining visibly marked `PROPOSED`. Store the identical
  definitions in `metric_contract`; a citation without the operational
  definition it supports is incomplete;
- a reused reported number is marked in its exact future cell/caption as
  `Reported result reused from <paper/table>; not rerun in this project.`;
- an omitted Required baseline is mentioned only in the paragraph/limitation
  whose interpretation it weakens.

After baseline and dataset interactions plus metric decisions are resolved,
freeze those choices into the Projected Paper's result
shells. Do not invent a provisional baseline row or metric column before the
decision. Every selected baseline that is approved for a reported comparison
must appear in the appropriate shell row; every approved dataset/setting and
metric must appear in its columns (or an explicitly designed multi-level
header). Reuse annotations remain attached to the exact affected cells.

### Repository candidate registry, interactive selection, and grounding contract

For the primary reference, the human-selected baselines, and implementation-critical modules, identify useful repositories from paper/project links, official author repositories, repository links found in retrieved full text, web search results, and any public GitHub URL, private Git URL, or local path supplied by the researcher. Repository discovery is a recommendation step, not proof that code is correct, complete, compatible, or runnable.

#### 0. Mandatory source-code architecture audit — before repository selection

Repository names and README claims are not enough to decide how the project
will be implemented. Before recommending repository selections, clone or open
every serious implementation candidate and read the relevant source code. At a
minimum inspect its executable entry points, core algorithm implementation,
model/provider abstraction, data interface, evaluator/metric interface,
configuration system, result schema, tests, dependency manifests, and license.
Also search for import-time side effects, global clients/files, hard-coded
models or paths, embedded credentials, demo values that override function
arguments, stale provider APIs, and assumptions that conflict with the
approved datasets, metrics, or target models. Record exact files and a pinned
commit when available. Static source inspection at this gate establishes an
architecture recommendation, not runnability; execution remains a later
`/goal` verification duty.

Use that evidence to compare these three project architectures explicitly:

1. build one local unified experiment framework and implement or adapt every
   method behind common model, data, evaluator, trace, and result interfaces;
2. extend one selected baseline repository as the project's primary framework;
3. execute baseline repositories independently with their native pipelines and
   implement the proposed method separately, normalizing results afterward.

Recommend exactly one architecture. A hybrid must still be assigned to one of
the three by naming what owns the shared execution and result contract. For
each selected baseline or module, state whether the implementation will be:
direct package reuse, a thin adapter around pinned upstream code, a local
reimplementation from the paper/source because upstream is unsuitable, or an
unchanged standalone run. State which code owns the proposed method. Never
infer that one baseline should become `PRIMARY_BASE` merely because it has the
most complete README or the easiest command line.

Present the source-backed architecture decision to the researcher, including
the decisive code findings and the exact per-baseline reuse boundary, and ask
them to `confirm architecture` or revise it. **STOP until the researcher
explicitly confirms the architecture.** Only then proceed to repository ID
selection, manual additions, and the repository grounding contract. Store the
confirmed architecture, source-audit evidence, shared interfaces, and
per-repository reuse boundaries in the hidden experiment-plan contract; do not
render a separate audit section in the final HTML.

#### 1. Build the complete repository candidate registry

Assign stable IDs `R1`, `R2`, `R3`, ... in recommendation order. Classify each candidate by its main implementation purpose:

- **Baseline implementation**;
- **Data / preprocessing**;
- **Evaluation / metrics / evaluator**;
- **Method-module reference**;
- **Training / serving / infrastructure**.

A repository may have secondary purposes, but it must have one primary purpose so that the researcher can understand why it is being recommended.

Maintain these internal fields for every candidate:

- repository name and direct link or local/private path;
- related paper, selected baseline, protocol, dataset pipeline, evaluator, or method module;
- primary purpose and secondary purposes;
- discovery source;
- official / author-provided / community / user-provided status;
- recommendation priority: `Preferred`, `Supplementary`, or `Background`;
- intended implementation scope;
- verification status: `paper-linked`, `metadata-checked`, `user-provided`, or `not verified runnable`;
- visible license, otherwise `pending`;
- visible branch/tag/commit, otherwise `to pin during /goal execution`;
- known environment/dependency notes;
- compatibility risks and fallback.

Keep all repository candidate/audit fields for the decision meeting and hidden contract; do not render candidate or audit tables in the final HTML.

Do not claim that a repository is runnable, paper-faithful, complete, compatible, or safe to reuse unless a later `/goal` pins a revision and verifies it. Do not silently treat every recommended repository as implementation authority.

#### 2. Mandatory interactive repository selection

Repository selection must happen **during the `/expplan` conversation, after the baseline contract is resolved and before the HTML is written**. The HTML records the decision; it is not the interface used to collect the decision.

1. **Show all repository candidates.**

   Group candidates by primary purpose and use a concise format:

   `R1. org/repo — purpose: evaluator — grounds: B4 / metric protocol — priority: Preferred — status: author-provided — verification: paper-linked`

   Include all candidates that may reasonably help implementation. If no useful repository is found, say so and continue directly to the manual-addition question.

2. **Ask the repository-selection question with `ask the user directly`.**

   Accept:

   - `R1,R3` or `1,3` to select specific repositories;
   - `all` to select every listed repository except those marked `Background`;
   - `none` to proceed without selecting a recommended repository.

   Multiple selections are allowed; never select a repository merely because it was recommended. Handle unknown IDs, contradictory forms such as `all,none`, or ambiguous prose by clarifying rather than guessing (same interaction guardrails as baseline selection).

3. **Ask the manual-addition question with `ask the user directly`.**

   Accept:

   - `none` / `no`;
   - one public GitHub URL per line;
   - one private Git URL per line;
   - one local project path per line;
   - an optional intended scope after `#`, for example:
     `/data/home/user/project # primary implementation base; reuse data pipeline and evaluator`.

   Assign stable IDs `M1`, `M2`, ... to manual additions. A repository or path explicitly supplied as an implementation reference is selected, but a URL merely mentioned as background is not automatically selected.

#### 3. Resolve an exact repository grounding contract

For every selected `R*` or `M*` reference, propose and resolve:

- exactly one **use mode**:
  - `PRIMARY_BASE`: the project or repository that the executing `/goal` should extend as the main implementation base;
  - `VERIFY_AND_USE`: clone/materialize, pin a revision, smoke-test, then use only for the approved scope;
  - `REFERENCE_ONLY`: inspect design/configuration/code, but do not execute it or copy it wholesale;
- one or more **allowed scopes**:
  - baseline implementation;
  - data/preprocessing;
  - evaluator/metric protocol;
  - method module;
  - training/serving infrastructure;
- an explicit **prohibited scope**, especially when only one component is authoritative;
- an **integration target** in the planned project;
- an **authority / precedence rule** when multiple selected references cover the same scope;
- an execution verification checklist for the relevant `/goal`;
- a fallback if verification fails.

After proposing these contracts, ask one compact `ask the user directly`:

- `approve repository contract`;
- or revisions such as
  `R4=PRIMARY_BASE; R1=REFERENCE_ONLY evaluator only; M1=data-pipeline authority`.

If two selected repositories claim authority over the same data pipeline, evaluator, baseline implementation, or module and no precedence is clear, the conflict must be resolved before HTML generation. Never merge conflicting implementations silently.

#### 4. Required `/goal` execution verification checklist

A selected repository is still **not verified runnable** at `/expplan` time. For every `PRIMARY_BASE` or `VERIFY_AND_USE` reference, the contract must require the executing `/goal` to:

- pin and record the exact commit/tag/revision;
- inspect license and redistribution constraints;
- inspect environment and dependency compatibility;
- run the smallest available smoke test;
- verify data-pipeline and evaluator behavior when those are approved scopes; do not add split selection or verification to `/expplan`;
- record files/configs actually reused or modified;
- keep user code and upstream code distinguishable;
- fall back to the approved alternative if verification fails.

`REFERENCE_ONLY` repositories do not need to be executed, but the executing `/goal` must record which design, configuration, or code location was consulted.

#### 5. Repository decisions in the minimal HTML

Do not render repository candidate, audit, or grounding-contract tables. Keep
the resolved selected references, use modes, scopes, precedence, verification,
and fallbacks in the hidden contract for `/runplan`. Only references selected
in that hidden contract may guide later execution; unselected candidates remain
background. Mention a repository visibly only when a Projected Paper paragraph
or artifact caption genuinely needs to identify an implementation/evaluator
source.

Then, claim-driven (not a to-do list), **written backward from the abstract:**
**Reader-facing opening — write the conference and references first, then the projected paper, before claims/method/experiments.** Use `1. Target Conference and Reference Papers` for exactly three entries: target conference, external mechanism reference, and researcher-owned structure reference. Keep the official-rules link inside the target-conference entry. Do not include the research question, object of study, implementation architecture, datasets, metrics, baselines, or any other setup material there. Immediately follow it with `2. Projected Paper`, containing parts (a)–(c):

(a) **Projected Title + Abstract** — immediately **above the abstract, draft a working paper title** (`<h2>`-sized, styled as a title): a concrete, non-generic title naming the idea's ONE core mechanism (a short name + a claim-bearing subtitle is fine, e.g. "ABD++: One Modality-Invariant Harmful Axis for Deployable Jailbreak Defense"), not a topic label. It should read like a real paper title and match the idea's single mechanism — if the best honest title still sounds like "technique A applied to domain B", that is a signal the idea is a mashup (flag it, don't dress it up). Then the **projected abstract** — the abstract the paper *would* have if the idea succeeds, in her *Writing Style* (gap-first, "We propose/release" bullets). Mark **PROJECTED — not results**; every number a placeholder `[X%]`, never fabricated.
   - Tight: ≤ ~180 words / 8–10 sentences (one gap · one "we present X" · 2–3 method · 1–2 result-with-placeholder · one takeaway).
   - **No em-dashes, no rare words**; use common words and keep only genuine terms of art.
   - **abstract↔claim self-check:** map each abstract claim-sentence to a §1 claim; a sentence with no backing experiment gets cut or gets an experiment.
(b) **Projected Paper Blueprint (write right after the abstract, INSIDE `03`)** — show the paper that will be written, not merely a list of experiments. Use the confirmed pair already named and linked in Section 1; do not repeat it in a second references block. Model only the writing architecture on the **researcher-owned writing/structure reference**: its actual section order and proportions, every paragraph's rhetorical job, and its figure/table rhythm. Fill that architecture with scientific content from the approved idea and the **external mechanism reference**: the actual problem evidence, mechanism, claims, method, experiments, comparison logic, datasets, metrics, and analyses. Do not copy the owned paper's subject matter into the new paper. For example, if the best-fit owned structure uses §3 to establish that the problem exists and §4 to propose the method, keep those roles: §3 must validate the current mechanism problem using current external grounding and planned evidence, while §4 must present the new method.

For **every planned section and subsection**, enumerate every paragraph in
order. Use stable paragraph IDs such as `I-P1`, `RW1-P2`, `M2-P3`, `E3-P2`,
`D-P1`, and `C-P1`. In the visible HTML, each paragraph row contains only:

- the stable paragraph ID;
- **one concrete sentence saying what that paragraph will write**;
- the artifact ID it introduces or interprets, only when applicable.

The sentence must name the actual topic and argumentative move, not a generic
label such as “introduce the method” or a bundle of bullets disguised with
semicolons. It should be specific enough that `/paperwrite` can draft the
paragraph from it, while remaining a plan rather than fabricated final prose.
Use exactly one grammatical sentence per paragraph row. Keep the matching
researcher-owned-reference anchor, rhetorical role, claims/variables,
evidence/citations, transition, and approximate length/share in that
paragraph's hidden `paper_outline` record; do not render those fields as extra
visible columns.

Do this for **all** sections, not only the Introduction: Abstract;
Introduction; each Related Work subsection; each Method subsection; every
Experiments subsection including setup prose, main results, ablations,
sensitivity/robustness, cost, qualitative/failure analysis; Discussion,
Limitations/Ethics when applicable; Conclusion; and planned appendices. For
Method paragraphs, additionally list inputs, outputs, variables, raw fields,
and evidence grade (`claim-grade`, `pilot-only`, `smoke-only`, or
`unavailable`). Mark the entire blueprint PROJECTED and keep unknown prose
numbers as `[X%]`.

(b.1) **Render only experiment-backed, fillable paper artifacts inline.** At
the exact point in the paragraph blueprint where a future empirical figure or
result table will be introduced, render its visible shell, not only its name in
an artifact ledger. A figure that needs no experiment, such as an Introduction
motivation figure or a Method overview, is count-only at `/expplan`: keep its
stable figure ID in the paragraph blueprint, artifact ledger, embedded
contract, and whole-paper figure total, but do not draw, mock, preview, create a
source table for, or add a result/acquisition requirement for it. Its actual
design belongs to `/paperwrite` / `/figureppt` after evidence is available.

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
  actual Matplotlib artists rendered (`PathCollection` offsets for scatter,
  patches for bars), and (iii) `[PENDING]` numeric cells in the rendered HTML
  DOM. Require `rendered marks == plotted_marks` and
  `DOM pending cells == pending_values`; do not present or return the HTML while
  any panel fails. The reusable plotting script must implement and call a
  `validate_rendered_marks` check before saving its PDF/PNG.
  Structure multi-panel code as `draw_panel_*()` functions. With
  `synthetic: true`, draw `PROJECTED SHAPE — NOT RESULTS` prominently. Missing
  input must fail rather than default, interpolate, or invent. Embed the PNG in
  `03` as a data URL and retain script/PDF/PNG for `$paperwrite`; the paper run
  reuses the code and replaces only `--metrics` with validated results.
  Render each panel as its own preview beside exactly one corresponding data
  requirement table; never place several panels beside one combined table.
  Every panel table must name required fields and show `[PENDING]` in each
  future observed X/category and value cell. Preserve a one-to-one visual
  mapping between table cells and plotted marks: if a preview has three series
  with six points each, expose eighteen separate pending value cells (plus the
  six X/category cells when those are not already fixed design labels), never
  one `[PENDING]` cell that silently stands for an array or a whole curve. Use
  the same series names and point order in the table and preview. Predefined
  Give every pending numeric source-table cell a stable non-visible
  `data-target-id` and include those cell IDs—not only a coarse panel ID—in the
  artifact's `result_requirements`. `/runplan` and `04_EXP_RESULT.html` must
  later fill these exact cells from validated ledger rows and generate the
  final plot from the displayed values; they must not create a second plot-only
  data source.
  categorical experimental conditions are column headers, not pending data
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
(c) **Page-fill feasibility vs the target venue (do this BEFORE the GATE — a hard check, not a nicety).** The experiment plan must design *enough* experiments to fill the target conference's body-page requirement, because `/paperwrite` later must fill to that page count with substantive content and cannot invent experiments the plan did not specify. So, while both confirmed references are open, **count the researcher-owned reference's body proportions and content floats, inspect the external mechanism reference's experimental coverage, and estimate the plan's**: (a) read the target venue's body-page limit (ACL 8, EMNLP 8, NeurIPS 9, ICLR 9–10, AAAI 7–8) and the **researcher-owned reference's real CONTENT-float count** (how many result tables + figures it carries across its body — a table-heavy empirical paper often has 5–8). **Do NOT make the experiment setup a table at all — state backbones / datasets / hyperparameters / graph settings in prose.** A setup/config table carries no result, fills negligible space, and does not count as a content float; exclude any such table from BOTH the reference's count and the plan's, and do not add one to hit a float count. Count only floats that carry a result, an analysis, or a qualitative example; (b) count what THIS plan will produce as body content-floats — one per claim, per dataset/setting breakdown of the main results table, per ablation-matrix row, plus per-layer / sensitivity / qualitative / cost analyses (again, the setup table is not one of them); (c) if the plan's float/experiment count is materially below the researcher-owned reference's, or its experimental coverage is materially thinner than the external mechanism reference's (e.g. the plan yields 3 floats but the owned reference has 7), the plan is **under-scoped to fill the venue's pages** — expand it NOW: add datasets, baselines (raise the baseline selection), ablation-matrix rows, network/model/seed sensitivity sweeps, and analysis axes, until the projected float count and coverage are credible. A micro / smoke plan (e.g. a deliberate ~10-case test) will NOT fill a full venue paper; when the researcher has explicitly asked for a micro run, say so plainly at the GATE ("this plan yields ~N body floats vs the owned reference's M; at full venue length the paper will fall ~K pages short unless the experiment set is scaled up") rather than letting `/paperwrite` discover the shortfall at compile time. Immediately below the visible `2. Projected Paper` heading, write a compact whole-paper **float budget** comparing only this plan's total content figures/tables with the researcher-owned reference's total content figures/tables. Ignore which sections the floats appear in. Do not append a citation or `reference` link to this numeric line; the reference is already linked in Section 1. Also retain the one-line page-fill feasibility note elsewhere in `03`.
**Visible float-budget brevity overrides the preceding detail:** render exactly
one prominent line immediately below the `2. Projected Paper` heading with two numeric
entries—this whole paper and the reference whole paper—each formatted as
`total (figures, tables)`. Use a visible label such as `Figure/table count`, a
larger type size and bordered background so it cannot be mistaken for a
footnote. End the line after the second numeric entry: do not append a
`reference` label, citation, or link. The two reference-paper links already
belong in Section 1. Include count-only non-experimental figures in the totals.
Add no section-position counts, explanation, comparison, difference, or
interpretation.

The following design records are still mandatory, but keep them in the hidden
contract and let their paper-facing consequences appear in the paragraph plan
and artifact shells. Do not turn them into extra visible web sections:

1. **Claims → evidence → variables** — each intended claim must map to (a) the experiment that supports it, (b) the variables that must be measured, (c) the raw fields that store those variables, and (d) the computation path from raw fields to final metric. No claim without planned measurable variables. No variable without a raw-field contract. Keep a compact pre-registered interpretation record per claim: primary metric/comparison, minimum practically meaningful effect or expected direction, uncertainty rule, and falsifying pattern. This is fixed before runs and is not an automatic accept/reject rule.
2. **Systems, datasets, metrics, and baselines** — freeze the method, selected baselines, and source actions in hidden `grounding`. Determine datasets and metrics directly in each projected main result table and caption/note; do not create dataset or metric registries. The visible table must make both unambiguous without hidden JSON. Do not discuss, decide, require, render, store, or validate train/dev/test splits in `$expplan`; they are entirely outside this skill's contract. Resolve conflicts in dataset or metric meaning at the existing decision meeting.
3. **Variable feasibility and provenance** — for every variable record `used_in`, `purpose`, `source`, `required_observable`, `available_now`, `fallback_or_proxy`, `raw_field`, and evidence grade. Do not mention a variable in the blueprint or an artifact unless it exists in this hidden record.
4. **Ablation contract** — one record per ablated component; each changes exactly one variable versus the full method and maps to approved artifact targets.
5. **Execution dependency sketch** — instrumentation sanity → generation smoke → baseline → diagnosis/main pilot → ablation → polish. This is not the final run schedule: `/runplan` later converts it into goals. Instrumentation sanity must verify raw fields and computation paths for every planned variable.
6. **Configs** — launcher/framework/base-model from Experiment Templates; task-specific lr/batch/epochs/seeds and OOM-safe defaults.
7. **Budget** — rough GPU-hours per experiment block; flag runs longer than one day for sign-off.

**Embedded contract schema (required):** use top-level keys
`schema_version`, `source_plan`, `approval_status`,
`target`, `references`, `dataset_confirmation`, `grounding`, `claims`, `variables`,
`baseline_contract`, `repository_contract`, `experiment_contracts`,
`paper_outline`, `paper_artifacts`, `required_labels`, and
`result_requirements`. Each `paper_artifacts` entry must
contain `id`, `kind`, `label`, `span`, `placement`, `supports`, `section_id`,
`introduced_after`, and `shell`. A table `shell` records caption, row labels,
column labels, dataset-bearing headers, metric/uncertainty format, and stable
pending cell IDs; a figure `shell` records caption,
panels, axes/legend, source variables/cells, and aggregation. Data-driven result
figures additionally record their required-data table, plotting source, fixture,
and generated PDF/PNG paths and set `data_driven: true`. Conceptual method or
overview figures set `data_driven: false` and are exempt from numeric fixtures
and Python plotting.
Add `dimensions` when a result is broken down by
dataset/game/model/seed/condition. `paper_outline` records the ordered sections
and paragraph rows described above. Every paragraph record contains `id`,
`plan_sentence`, `reference_anchor`, `rhetorical_role`, `supports`, `evidence`,
`transition`, `length_share`, and `artifact_refs`; the HTML exposes only `id`,
the single `plan_sentence`, and non-empty `artifact_refs`. Method paragraphs
additionally record `inputs`, `outputs`, `variable_ids`, `raw_fields`, and
`evidence_grade` in the hidden contract.
`dataset_confirmation` contains only `confirmed` and `confirmed_at`; dataset
names are not duplicated there because Setup and result-table headers are the
authority. It must be confirmed before HTML generation.
Each `result_requirements` entry contains `id`, `artifact_id`, exactly one of
`cell_ids` or `panel_ids`, `experiment_id`, `source_action`, `any_of` dotted
JSON key paths, and `supports`. `source_action` is exactly one of `RUN_LOCAL`
or `REUSE_REPORTED`; citation-only material cannot fill a result target. For
reported reuse, also include the exact paper/dataset source and table/figure/
row/column locator. For local work, `experiment_id` must resolve to an
`experiment_contracts` entry that references the table-defined dataset/metric
semantics and fixes only experiment-specific variables/raw fields, computation,
seed/uncertainty exceptions, authorized configuration space, and repository
authority. Split selection is absent here and added by `$runplan`. This is the scientific source
contract that `/runplan` later turns into an executable acquisition contract;
it is not yet a goal schedule. Use `[]` for a required non-empty list. Before approval, set
`approval_status` to `pending`.

**GATE (human is judge — enforce it, don't just present):** in the approval conversation, summarize claims, selected baseline coverage/actions, exact reuse sources, omitted-Required risks, repository authority/fallbacks, the reference-aligned one-sentence-per-paragraph blueprint, every inline figure/table shell and its unfilled targets, variable feasibility, ablations, first three dependency-sketch experiments, budget, and artifact placement. Do not add these as extra visible HTML sections. Baseline and repository contracts must be resolved before the final HTML is written, so the GATE asks only for approval or revision of the complete plan. Reject the plan before this gate if any section/subsection omits its planned paragraphs, any paragraph lacks exactly one concrete planning sentence, any promised artifact lacks a visible shell, any numeric shell cell lacks exactly one result requirement, any result requirement lacks a single authorized source action and experiment/source locator, or any required target cannot be deterministically acquired. **Then STOP and call `ask the user directly`** for the researcher to `approve` / `revise` the plan (offer those options; `revise` collects what to change) — exactly as the intermediate baseline/reuse/repository gates already do. **Do NOT auto-proceed to `/runplan`; wait for the researcher's approval token.** This holds even in a skill-test run (fabricated data does not skip the gate).

Before presenting the gate, run `python .agents/skills/expplan/scripts/validate_experiment_plan.py --plan reports/03_EXPERIMENT_PLAN.html`. Fix every failure. This validator enforces table-owned dataset/metric semantics, no expplan split, Python-generated projected figures, fixture isolation, target coverage, and non-visible internal result IDs.

On `approve`, set the embedded contract's `approval_status` to `approved` and
validate that every artifact in the visible HTML ledger appears once in that
contract. When this skill later
changes the approved scientific scope or artifact ledger, reset the
embedded contract to `pending` and return to this gate. Approval is an explicit human
state, not a file-hash check. Regenerating fixtures/plots or hiding internal IDs
without changing table/figure semantics is a presentation refresh and preserves approval.
