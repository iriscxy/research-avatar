---
name: "expdesign"
description: "Design the scientific experiment program for a chosen research idea by working backward from a PROJECTED abstract and paper skeleton. Define claims, falsifiers, baselines, datasets, metrics, ablations, evidence requirements, budgets, and repository grounding in reports/03_EXPERIMENT_PLAN.html for researcher approval. This decides what evidence the paper needs; it does not schedule or run experiments. Stops at the approval gate before /runplan converts the approved design into executable goals. Invoke explicitly as `/expdesign`."
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
- **Strict reader-facing section order:** render the final HTML in this top-level order: `1. Research Contract and Target Venue` → `2. Projected Paper` (title, PROJECTED abstract, paragraph-level skeleton, page-fill check) → claims → method/data/variables → experiment design → resources/risks → final gate → grounding appendix. Do not put a baseline registry between the venue contract and the projected paper. Discuss baselines, result reuse, and repository grounding only inside the experiment-design section, after the main experiment matrix and before ablations/run order.
- **Skill-test / fabricate-data run:** if this plan is part of an explicit skill-test (the downstream `results/` will be fabricated to exercise the pipeline), `03` must carry the same loud banner as the rest of the artifact set — `SKILL-TEST — fabricated data, NOT a scientific result` — at the top, so the whole `03`/`05` + paper set is consistently marked and none can pass as real (AGENTS.md discipline #1). The plan's own numbers stay `[X%]` placeholders marked PROJECTED regardless.
- **Self-contained HTML, never Markdown** — inline `<style>`, no external assets, real structure (`<h1>/<h2>`, `<table>`, `<ul>`); use **continuous tables as the primary layout** for structured content, never card/grid layouts; **every paper reference a direct `<a href>`** to arXiv/DOI, unverifiable → visible `pending`, never fabricated.
- **Math variables must render as proper notation, not raw ASCII in a `<code>` span.** A subscripted or Greek variable like `b_dir` / `s_si` / `Δ_cross` / `θ*` / `Pz` reads as a defect when shown as `<code>s_si</code>`. Render it natively with italic `<var>` + `<sub>` + Unicode Greek — `<var>b<sub>dir</sub></var>`, `<var>s<sub>si</sub></var>`, `<var>&Delta;<sub>cross</sub></var>`, `<var>&theta;*</var>`, `<var>P<sub>z</sub></var>` — with a one-line style rule (`var{font-family:Georgia,serif;font-style:italic} var sub{font-style:normal;font-size:.72em}`). No external MathJax/KaTeX (breaks self-containment); these are simple subscripted vars, so `<var>/<sub>` suffices and renders with zero JS. Keep raw `results/` JSON field keys (e.g. `sim_runs.json:Pz`) as `<code>` — those are literal identifiers, not math.
- `reports/03_EXPERIMENT_PLAN.html` is the single canonical plan that `/runplan` reads. Address the researcher directly, never in the third person.

## B — Experiment plan → `reports/03_EXPERIMENT_PLAN.html`

### Mandatory target-venue confirmation — FIRST, before references

Fix the intended submission venue **before selecting either reference paper or designing the experiment plan**. A venue inherited from an old draft, a profile preference, or an assistant default is not confirmation.

1. Build a short venue slate from the chosen idea's topic/contribution type and the researcher's Active Venues. For each serious candidate, show: exact venue/track and submission cycle, why the idea fits, the main fit risk, and the current official body-length/template rule. Venue deadlines and rules are time-sensitive, so verify them from the venue's official site and link the source; mark anything unavailable as `pending`, never infer it.
2. Recommend one candidate in plain language, but ask the researcher directly to `confirm venue: <venue/track/cycle>` or name a replacement.
3. **STOP until the researcher explicitly confirms one exact venue/track/cycle.** Do not propose the two-reference pair, build the baseline registry, search repositories, or write/revise `03_EXPERIMENT_PLAN.html` before this confirmation.
4. Treat the confirmed venue as part of the plan contract. Record it in the final HTML metadata and in the first top-level section, including the verified page/word limit and official rules link.
5. If the researcher later changes the venue, invalidate the reference confirmation and every venue-dependent page-fill/structure decision; return to this gate, then reconfirm the two-reference pair. Baseline and repository decisions need reconfirmation only when the venue change affects their scientific or feasibility assumptions.

The gate order is mandatory: **target venue → two references → baselines/reuse → repositories → write `03` → final plan approval**.

### Mandatory two-reference confirmation — BEFORE writing `03`

Every plan must use **two distinct, role-separated reference papers**:

1. **External mechanism reference** — the closest non-author paper to the chosen idea. It grounds novelty, experimental protocol, datasets, metrics, baselines, and the must-beat comparison floor.
2. **Researcher-owned writing/structure reference** — one paper authored by the researcher, verified against the Publications Index in `researcher-profile/PROFILE.md`. It grounds title/abstract rhetoric, Introduction paragraph logic, section ordering and proportions, and figure/table conventions. Rank candidates by target-venue match first, then task/method similarity. This paper is a structural and stylistic reference, not evidence that the new method works.

These roles may not collapse into one paper. If the closest mechanism paper is authored by the researcher, keep it in the researcher-owned role and select a separate external mechanism reference. **Only after the target venue is explicitly confirmed**, and before any baseline interaction, repository interaction, or `03_EXPERIMENT_PLAN.html` drafting:

- show the proposed pair in the conversation with title, authorship role, venue/year, direct link, local full-text path/status, and one plain-language sentence explaining why each was chosen;
- ask the researcher directly to `confirm references` or replace either paper;
- do not write or revise `03` until the researcher explicitly confirms both;
- after confirmation, read the external paper's experiments/setup/results and the researcher-owned paper's full structure, including abstract, every body heading, paragraph progression in the Introduction, and body figures/tables;
- if no researcher-owned full text is available, say exactly what is missing and ask the researcher to nominate a paper or explicitly approve a named fallback; never silently substitute an external paper;
- reconfirm the pair whenever the selected idea or target venue changes.

Record the confirmed pair in `2. Projected Paper`, before the paragraph-level skeleton, and in the final grounding appendix, with the two roles kept explicit. For structural conflicts, use this precedence: target-venue rules/template → researcher-owned writing/structure reference → external mechanism reference.

**FIRST, read the full text of the closest papers — do not guess the comparison set.** Pull the actual experimental setup of the 2–4 closest papers to the idea (from its *closest work* + the *Literature Landscape* in `reports/02_IDEA_REPORT.html`): fetch full text (`tools/fetch_fulltext.py` / `pdftotext` / web open/fetch), read the **experiments/setup section + result tables**, and extract the concrete **baselines, datasets, metrics, and reusable variables** they use. That is what tells you what to beat, on what data, and which quantities can be validly measured; a plan from memory is guessing. For every variable introduced by the plan, state whether it is directly reused from prior work, adapted from prior work, or newly proposed by this plan. Newly proposed variables must be marked `PROPOSED` and need a feasibility check before they can support a claim. Unfetchable paper → mark `[UNVERIFIED]`, don't invent. Record a **grounding table** (paper → baselines · datasets · metrics · reusable variables, each linked). **Place this table as an APPENDIX at the very END of the plan (after the GATE), not at the top** — the researcher wants to open on the projected abstract + claims, and read the grounding evidence last as backing (it is the base every baseline/dataset/metric/variable is drawn from, so keep it whole, just at the bottom). Sections reference it by name ("drawn from the grounding table / see Appendix").

**Primary reference — whose datasets/metrics/baselines are the must-cover floor.** Before building the plan's dataset/baseline list, determine which grounded paper is the primary reference. Resolve in this order:

- **Rule 1 — researcher's own closest paper.** If the idea builds on a paper the researcher authored (check PROFILE.md Publications Index), that paper IS the primary reference. Its datasets, metrics, and baselines are the **must-cover floor** (labeled `[P]` throughout the plan). Other papers' datasets/baselines are **recommended supplements** (labeled `[S]`), included only if they add coverage without conflicting with the primary.
- **Rule 2 — highest relevance + impact among the closest papers.** If the researcher has no directly relevant paper of her own (new direction), score each grounded paper on: **relevance** (how closely its task/method matches the idea, 1–5) + **impact** (citations weighted by venue tier, 1–5). Take the highest total as the surrogate primary. If tied, relevance beats impact — matching the task matters more than raw prestige for experimental design.

When grounded papers have **conflicting datasets/metrics** (same name but different version, split, or computation), do NOT silently merge them into one entry. Keep both in the grounding table with their source paper noted, and surface the conflict in a short **"Decision Required"** box right before the GATE — let the researcher decide which to adopt as authoritative.

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
- dataset / split / metric compatibility with the proposed plan;
- implementation or official-code availability when known;
- estimated reproduction burden;
- reported-result reuse status;
- short reason for including or excluding it from the recommended run set.

Do not force all fields into one wide main-body table: put the compact complete candidate overview (every `B*`, grouped by family) in §2.2, and the detailed audit (compatibility, code, burden, evidence, provenance) in the grounding appendix.

Use these recommendation tiers:

- **Required**: must normally be selected because it is the primary reference method, the closest direct competitor, a baseline repeatedly used across the grounded papers, or the strongest verified method in the selected idea's primary family.
- **Strongly recommended**: materially improves comparison coverage, represents another important family, or is a recent competitive method with compatible data and metrics.
- **Optional**: scientifically useful but redundant, expensive, weakly compatible, unavailable, or mainly needed for breadth.
- **Citation only**: relevant for positioning but not a fair or feasible experimental comparison.

"Current-family SOTA" must be based on the newest directly comparable evidence available in the grounded papers or verified public sources. Do not label a method `SOTA` merely because it is recent. If the evidence is insufficient, write `SOTA status unverified`.

#### 3. Analyze whether published baseline results may be reused

Construct a cross-paper result-provenance check for each baseline. Multiple papers reporting the same baseline name or the same numeric value does not automatically make the result reusable.

A published result may be marked **eligible for reported-result reuse** only when all material protocol fields are verified to match:

- dataset name, version, and filtering;
- train/validation/test split and temporal or leave-one-out policy;
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

Do not average results from different papers. Do not reuse a result after changing the dataset split, candidate pool, preprocessing, metric implementation, model backbone, prompt, evaluator, or test protocol. For a main headline comparison, prefer rerunning the strongest selected baseline when feasible even if a reported number is technically reusable.

If any required protocol field or exact table source remains unresolved, the action cannot be `REUSE_REPORTED`; use `RUN_LOCAL`, `CITATION_ONLY`, or ask the researcher to decide after seeing the uncertainty.

#### 4. Mandatory baseline-selection interaction

Baseline selection must happen **during the `/expdesign` conversation, after the complete registry and taxonomy are built, and before repository discovery or final HTML generation**. The HTML records the decision; it is not the interface used to collect it.

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

Only after this baseline contract is resolved should repository discovery begin. Search implementation repositories primarily for the **selected baselines**, the primary reference, and implementation-critical modules. An unselected baseline may still appear in Related Work or the complete candidate table, but its repository must not be treated as necessary for the approved execution plan.

#### 7. Required HTML structure for baselines

Render the collected material inside the main **Experiment Design** section, after its main experiment matrix and before ablations/run order. Never make baseline/repository material a top-level section before `Projected Paper`. Keep the six titles below in this order, prefixing them with the experiment section's local numbering (for example `5.2.1`–`5.2.6`). Do not add a legacy `Must-beat baselines` row; the system/dataset/metric summary may give a one-line summary of the **selected** coverage.

- **Baseline Taxonomy and Idea Classification** — the classification stated in step 1 (taxonomy + supporting papers, primary family, hybrid tags, why it determines necessary comparisons), plus the minimum family coverage expected for a credible experiment.
- **Complete Baseline Candidate Overview** — every `B*` candidate in compact per-family tables (never one table over eight columns), columns exactly `ID · Baseline · Secondary tags · Scientific role · Tier · Selected? · Planned action`. Show `[x]`/`[ ]` and `Planned action` (exactly `RUN_LOCAL`, `REUSE_REPORTED`, `CITATION_ONLY`, or `UNSELECTED`) only after selection is resolved. Remaining registry fields (compared-in papers, frequency, protocol compatibility, code, burden, evidence, rationale) go to a **Detailed Baseline Audit** table in the grounding appendix.
- **Human-selected Baseline Contract** — the step-6 contract: selected baselines only (grouped by family) with tier + scientific role + execution action, family-coverage summary, and per omitted Required baseline its affected claim(s)/reviewer risk/approved fallback; warn clearly when the selected set lacks the closest direct competitor or a necessary family. Do not re-list unselected Optional baselines (they stay in the complete candidate overview).
- **Baseline Result Reuse and Provenance** (mandatory even when nothing is reused) — per selected baseline: action, reuse classification, and when `REUSE_REPORTED` the exact source paper + table/figure, dataset/version, split, candidate/negative-sampling protocol, metric definition + `K`, model/backbone/version, known-matching + unresolved/conflicting fields, and final decision. If nothing is reused, state exactly: `No literature-reported baseline number is reused in the main comparison; selected baselines are rerun locally or citation-only.` When reused, annotate exactly: `Reported result reused from <paper/table>; not rerun in this project.` Never use `REUSE_REPORTED` with an unspecified source or a conditional phrase such as `when protocol is sufficiently matched`.

The HTML must contain the resolved baseline selections, actions, omitted-Required risks, and reuse decisions.

### Repository candidate registry, interactive selection, and grounding contract

For the primary reference, the human-selected baselines, and implementation-critical modules, identify useful repositories from paper/project links, official author repositories, repository links found in retrieved full text, web search results, and any public GitHub URL, private Git URL, or local path supplied by the researcher. Repository discovery is a recommendation step, not proof that code is correct, complete, compatible, or runnable.

#### 1. Build the complete repository candidate registry

Assign stable IDs `R1`, `R2`, `R3`, ... in recommendation order. Classify each candidate by its main implementation purpose:

- **Baseline implementation**;
- **Data / preprocessing / split construction**;
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

Do not force all fields into one wide main-body table. Put the compact candidate overview in §2.5 and the detailed repository audit in the final grounding appendix.

Do not claim that a repository is runnable, paper-faithful, complete, compatible, or safe to reuse unless a later `/goal` pins a revision and verifies it. Do not silently treat every recommended repository as implementation authority.

#### 2. Mandatory interactive repository selection

Repository selection must happen **during the `/expdesign` conversation, after the baseline contract is resolved and before the HTML is written**. The HTML records the decision; it is not the interface used to collect the decision.

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
     `/data/home/user/project # primary implementation base; reuse dataset split and evaluator`.

   Assign stable IDs `M1`, `M2`, ... to manual additions. A repository or path explicitly supplied as an implementation reference is selected, but a URL merely mentioned as background is not automatically selected.

#### 3. Resolve an exact repository grounding contract

For every selected `R*` or `M*` reference, propose and resolve:

- exactly one **use mode**:
  - `PRIMARY_BASE`: the project or repository that the executing `/goal` should extend as the main implementation base;
  - `VERIFY_AND_USE`: clone/materialize, pin a revision, smoke-test, then use only for the approved scope;
  - `REFERENCE_ONLY`: inspect design/configuration/code, but do not execute it or copy it wholesale;
- one or more **allowed scopes**:
  - baseline implementation;
  - data/preprocessing/split;
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
  `R4=PRIMARY_BASE; R1=REFERENCE_ONLY evaluator only; M1=data split authority`.

If two selected repositories claim authority over the same data split, evaluator, baseline implementation, or module and no precedence is clear, the conflict must be resolved before HTML generation. Never merge conflicting implementations silently.

#### 4. Required `/goal` execution verification checklist

A selected repository is still **not verified runnable** at `/expdesign` time. For every `PRIMARY_BASE` or `VERIFY_AND_USE` reference, the contract must require the executing `/goal` to:

- pin and record the exact commit/tag/revision;
- inspect license and redistribution constraints;
- inspect environment and dependency compatibility;
- run the smallest available smoke test;
- verify dataset split and evaluator behavior when those are approved scopes;
- record files/configs actually reused or modified;
- keep user code and upstream code distinguishable;
- fall back to the approved alternative if verification fails.

`REFERENCE_ONLY` repositories do not need to be executed, but the executing `/goal` must record which design, configuration, or code location was consulted.

#### 5. Required HTML structure for repositories

- **Code Repository Candidate Overview** — every `R*` candidate grouped by primary purpose, compact tables with columns `ID · Repository / path · Primary purpose · Grounds · Priority · Verification · Selected?`. Show `[x]`/`[ ]` only after the interaction is resolved; reference baseline IDs (`B4`, `B17`) or module names rather than repeating the baseline list. Discovery source, official/community status, license, revision status, dependencies, compatibility risks, and fallback go to a **Detailed Repository Audit** table in the grounding appendix.
- **Human-selected Repository Grounding Contract** — only selected `R*` and approved manual `M*` references (not the unselected ones, which stay in the candidate overview), each recording: use mode (`PRIMARY_BASE`, `VERIFY_AND_USE`, or `REFERENCE_ONLY`), allowed scope, prohibited scope, integration target, authority/precedence, required `/goal` verification, and fallback. If none is selected and no manual addition is approved, state: `Approved to proceed without repository grounding.` When references overlap, add a compact **Authority and Conflict Resolution** note (e.g. `M1 authoritative for dataset split and evaluator`; `R4 authoritative only for baseline B17`; `R1 background only, must not override M1`).

Only references listed in **Human-selected Repository Grounding Contract** may guide `/runplan` and its later `/goal` executions; unselected candidates are background only and must not be silently cloned, copied, or used to determine implementation details. The HTML must contain the resolved selections, use modes, scopes, precedence rules, and verification requirements.

Then, claim-driven (not a to-do list), **written backward from the abstract:**
**Reader-facing opening — write the venue contract first, then the projected paper, before claims/method/experiments.** Use `1. Research Contract and Target Venue` for the confirmed venue, official-rule boundary, two-reference roles, research question, and object of study. Immediately follow it with `2. Projected Paper`, containing parts (a)–(c):

(a) **Projected Title + Abstract** — immediately **above the abstract, draft a working paper title** (`<h2>`-sized, styled as a title): a concrete, non-generic title naming the idea's ONE core mechanism (a short name + a claim-bearing subtitle is fine, e.g. "ABD++: One Modality-Invariant Harmful Axis for Deployable Jailbreak Defense"), not a topic label. It should read like a real paper title and match the idea's single mechanism — if the best honest title still sounds like "technique A applied to domain B", that is a signal the idea is a mashup (flag it, don't dress it up). Then the **projected abstract** — the abstract the paper *would* have if the idea succeeds, in her *Writing Style* (gap-first, "We propose/release" bullets). Mark **PROJECTED — not results**; every number a placeholder `[X%]`, never fabricated.
   - Tight: ≤ ~180 words / 8–10 sentences (one gap · one "we present X" · 2–3 method · 1–2 result-with-placeholder · one takeaway).
   - **No em-dashes, no rare words**; use common words and keep only genuine terms of art.
   - **abstract↔claim self-check:** map each abstract claim-sentence to a §1 claim; a sentence with no backing experiment gets cut or gets an experiment.
(b) **Projected Paper Skeleton (write right after the abstract, INSIDE `03`)** — the researcher expects the experiment plan to show the whole projected paper, not just the runs. Name and link the confirmed two-reference pair first. Model the writing architecture on the **researcher-owned writing/structure reference**: its actual section order and proportions, Introduction paragraph progression, and figure/table rhythm. Use the **external mechanism reference** for method/experiment content and comparison logic, not as the sole writing template. Include: **Introduction** — one topic sentence per paragraph, gap-first (say what each paragraph does); **Related Work** — the sections it splits into + a one-line position for each (every paper a real `<a href>`); **Method** — the module-titled subsections (name each module). For each Method module, list its inputs, outputs, variables computed or consumed, where each variable will appear in raw result files, and whether each variable is `claim-grade`, `pilot-only`, `smoke-only`, or `unavailable`; **Experiments** — a table mapping each planned paper subsection (4.1, 4.2, …) to the concrete experiment and the claim/metric it backs; **Discussion/Conclusion** — one topic sentence each. Mark PROJECTED, keep `[X%]` placeholders. §1—§7 below are the concrete experiment plan that fills this skeleton's Experiments section.
(b.1) **Artifact ledger is part of the signed skeleton.** Give every projected
content figure/table a stable artifact ID (`F1`, `T1`, ...), a future LaTeX
label, supported claims, required row/column dimensions, and placement. Mark an
artifact `body_or_appendix` only when the HTML explicitly permits moving it to
the appendix under page pressure. The visible ledger and embedded contract
must agree exactly.
Do not describe a float as optional merely to make later layout easier.
(c) **Page-fill feasibility vs the target venue (do this BEFORE the GATE — a hard check, not a nicety).** The experiment plan must design *enough* experiments to fill the target conference's body-page requirement, because `/paperwrite` later must fill to that page count with substantive content and cannot invent experiments the plan did not specify. So, while both confirmed references are open, **count the researcher-owned reference's body proportions and content floats, inspect the external mechanism reference's experimental coverage, and estimate the plan's**: (a) read the target venue's body-page limit (ACL 8, EMNLP 8, NeurIPS 9, ICLR 9–10, AAAI 7–8) and the **researcher-owned reference's real CONTENT-float count** (how many result tables + figures it carries across its body — a table-heavy empirical paper often has 5–8). **Do NOT make the experiment setup a table at all — state backbones / datasets / hyperparameters / graph settings in prose.** A setup/config table carries no result, fills negligible space, and does not count as a content float; exclude any such table from BOTH the reference's count and the plan's, and do not add one to hit a float count. Count only floats that carry a result, an analysis, or a qualitative example; (b) count what THIS plan will produce as body content-floats — one per claim, per dataset/setting split of the main results table, per ablation-matrix row, plus per-layer / sensitivity / qualitative / cost analyses (again, the setup table is not one of them); (c) if the plan's float/experiment count is materially below the researcher-owned reference's, or its experimental coverage is materially thinner than the external mechanism reference's (e.g. the plan yields 3 floats but the owned reference has 7), the plan is **under-scoped to fill the venue's pages** — expand it NOW: add datasets, baselines (raise the baseline selection), ablation-matrix rows, network/model/seed sensitivity sweeps, and analysis axes, until the projected float count and coverage are credible. A micro / smoke plan (e.g. a deliberate ~10-case test) will NOT fill a full venue paper; when the researcher has explicitly asked for a micro run, say so plainly at the GATE ("this plan yields ~N body floats vs the owned reference's M; at full venue length the paper will fall ~K pages short unless the experiment set is scaled up") rather than letting `/paperwrite` discover the shortfall at compile time. Record the projected-float-count-vs-both-references comparison in `03` as a one-line **page-fill feasibility** note.
1. **Claims → evidence → variables** — each intended claim must map to (a) the experiment that supports it, (b) the variables that must be measured, (c) the raw fields that store those variables, and (d) the computation path from raw fields to final metric. No claim without planned measurable variables. No variable without a raw-field contract. Put every claim in a compact **pre-registered interpretation table row**, never a card: columns are (a) primary metric and comparison, (b) minimum practically meaningful effect or expected direction, (c) uncertainty reporting rule (seeds / CI / test as appropriate), and (d) the result pattern that would weaken or falsify the claim. This is a reading aid fixed before runs, not an automatic accept/reject rule: the researcher remains the judge at the result gate. Do not retrofit these criteria after seeing results; if a protocol change is necessary, record it visibly as a dated amendment with the reason.
2. **Systems, Datasets, Metrics, and Baseline Design** — give the method, datasets, and metrics before the experiment section. Inside **Experiment Design**, present the main experiment matrix first, then the baseline and repository material in the six-part order defined above, then ablations and run order. The repository sections record decisions already collected via `ask the user directly`, not a fresh interface. All baselines must be drawn from grounding evidence (real, not invented). Preserve `[P]` for the primary-reference floor and `[S]` for supplementary evidence, but do not equate `[P]` with automatic user selection. Do not include a duplicate pre-selection `Must-beat baselines` row listing every candidate. If grounded papers disagree on a dataset version/split, metric computation, or baseline-result protocol, flag it in the GATE's "Decision Required" box — don't silently merge or drop.
3. **Variable Feasibility & Provenance Table** — for every variable introduced in the plan, include: `Variable · Used in · Purpose · Source · Required observable · Available now? · Fallback/proxy · Raw field · Evidence grade`. A variable means any quantity used by the method, metric, verifier, router, ablation, claim, or analysis. Evidence grade must be one of `claim-grade`, `pilot-only`, `smoke-only`, or `unavailable`. Do not mention a variable in the abstract, method, claims, metrics, run order, or ablation table unless it appears here.
4. **Ablation matrix** — one row per ablated component; each row changes exactly one variable vs the full method.
5. **Run order** — instrumentation sanity → generation smoke → baseline → diagnosis/main pilot → ablation → polish. Instrumentation sanity must verify that every variable named in the Method, Claims, Metrics, or Routing sections exists in the raw output schema, has a documented computation path, is computable with the current stack, is written as `MISSING` if unavailable, and is downgraded to `smoke-only` or `pilot-only` if only a proxy is available.
6. **Configs** — launcher/framework/base-model from *Experiment Templates* (stack match). Set lr/batch/epochs/seed HERE (task-determined; profile does not supply these). OOM-safe defaults if the profile records OOMs.
7. **Budget** — rough GPU-hours per block; flag >1-day runs for sign-off.

**Embedded contract schema (required):** use top-level keys
`schema_version`, `source_plan`, `approval_status`,
`target`, `claims`, `paper_artifacts`,
`required_labels`, and `result_requirements`. Each `paper_artifacts` entry must
contain `id`, `kind`, `label`, `placement`, and `supports`; add `dimensions`
when a result is broken down by dataset/game/model/seed/condition. Each
`result_requirements` entry contains `id`, `any_of` dotted JSON key paths, and
`supports`. Use `[]` for a required non-empty list. Before approval, set
`approval_status` to `pending`.

**GATE (human is judge — enforce it, don't just present):** present the plan summary (claims, selected baseline coverage by family, exact baseline actions, exact reuse sources, omitted-Required risks and affected claims, selected repository use modes/scopes, repository authority or conflicts, variable feasibility table, ablation rows, first 3 runs, budget, verification fallbacks, and the complete artifact ledger with body/appendix placement). Baseline and repository contracts must be resolved before the final HTML files are written, so the GATE asks only for approval or revision of the complete plan. **Then STOP and call `ask the user directly`** for the researcher to `approve` / `revise` the plan (offer those options; `revise` collects what to change) — exactly as the intermediate baseline/reuse/repository gates already do. **Do NOT auto-proceed to `/runplan`; wait for the researcher's approval token.** This holds even in a skill-test run (fabricated data does not skip the gate).

On `approve`, set the embedded contract's `approval_status` to `approved` and
validate that every artifact in the visible HTML ledger appears once in that
contract. When this skill later
changes the approved scientific scope, HTML, or artifact ledger, reset the
embedded contract to `pending` and return to this gate. Approval is an explicit human
state, not a file-hash check.
