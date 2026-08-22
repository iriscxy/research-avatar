### Baseline taxonomy, recommendation, result reuse, and interactive human selection

Baseline planning must be derived from the experimental sections and result tables of multiple relevant papers, not from one paper and not from memory. Use the 2–4 closest papers already required above, and expand to additional directly relevant papers only when needed to establish a stable taxonomy, identify a recent category-specific state of the art, or resolve conflicting baseline conventions.

#### 1. Derive the baseline taxonomy from the literature

Before choosing individual baselines, infer the method-family taxonomy used across the relevant papers. The following four broad families are mandatory when they exist in the task:

- **Traditional / classical baselines**: heuristic, probabilistic, matrix-factorization, graph-statistical, rule-based, or other non-deep methods.
- **Deep-learning baselines**: neural sequence, graph neural network, representation-learning, multimodal neural, or other trained non-LLM methods.
- **LLM-based baselines**: methods whose main prediction, ranking, representation, reasoning, or generation component is an LLM.
- **Tool-using / agentic baselines**: methods that retrieve external evidence, invoke research_avatar/tools/APIs/search, use planners or multi-agent workflows, or otherwise depend on tool-mediated execution.

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
   When matching the broader grounded literature's experiment breadth, compare
   and recommend the number of headline evaluation benchmarks against the
   strongest directly relevant papers' benchmark counts. Do not inflate this count with benign
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
- in that Setup prose, introduce what each selected dataset/benchmark measures
  and why it tests a named claim, and introduce what each baseline family does
  and why it supplies a distinct control or comparison role. Describe an
  individual baseline separately only when its role is unique. Do not emit an
  unexplained list of names or invent one paragraph per method mechanically;
- immediately after the Setup prose, show a two-column implementation table:
  `Method` and `How it is implemented`. Each row directly commits to one
  implementation. If verified official code will actually be used, name the
  reused modules, the local adapter work, and link the direct official GitHub.
  Otherwise say `Local implementation` and name the components implemented;
  show no implementation-source link. Never expose separate mode, source-type,
  reuse/write-boundary, shared-boundary, or fallback columns to the reader.
  Make the common execution architecture explicit inside each row: baselines
  are implemented in the same local model/data/trace/generation/evaluator
  framework as the proposed method, while official modules are integrated into
  that framework through an adapter. Label the proposed row visibly as
  `Our method — <name>` so it cannot be mistaken for another baseline.
  Paper links remain scientific citations in Setup and never appear as code
  sources. Store the identical row order plus the full engineering details as
  `implementation_contract` in the embedded contract so `/runplan` can inherit
  it without reinterpretation. Each record requires `implementation_summary`.
  Official-code records use `OFFICIAL_GITHUB` plus
  `SOURCE_GUIDED_REIMPLEMENT` or `REUSE_OFFICIAL_MODULE` and a verified direct
  GitHub URL. Every other record uses `SELF_IMPLEMENT`, `LOCAL`, and an empty
  `source_url`; `PAPER_SPEC` and `PAPER_GUIDED_REIMPLEMENT` are not valid
  implementation-source decisions. Keep `paper_url`, `repository_status`,
  `upstream_reuse`, `local_implementation`, `shared_boundary`, and `fallback`
  only in the hidden contract for grounding and execution checks;
- approved metrics/datasets/settings appear directly as columns, axes, or
  panels;
- in Setup, give every metric its provenance class (`DIRECT`, `ADAPTED`, or
  `PROPOSED`), canonical name, exact formula or evaluator rule, score range,
  decision threshold/cutoff when one exists, aggregation rule, definition
  source, and direct citation. A proposed metric cites its closest grounding
  protocol while remaining visibly marked `PROPOSED`. Store the identical
  definitions in `metric_contract`; a citation without the operational
  definition it supports is incomplete. Add per-claim `claim_mappings` with
  `DIRECT`/`PROXY`, construct, limits, alternatives, and required companions;
  one metric may play different roles across claims, but a proxy cannot alone
  establish a stronger headline construct;
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
