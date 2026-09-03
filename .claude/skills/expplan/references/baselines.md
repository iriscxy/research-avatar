# Baseline selection and result reuse

Read this file only during the baseline and reported-result reuse gate.

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
