---
name: workplan
description: From a chosen idea, write the claim-driven EXPERIMENT_PLAN.html — written backward from the projected abstract and INCLUDING the projected paper skeleton (how the abstract reads, each Intro paragraph's logic, the Related Work sections, the Method modules, and which experiments the Experiments section will run) followed by the concrete experiment plan that fills that Experiments section. Stops at the plan-approval gate before /run-plan. Use when the researcher has picked an idea and wants an experiment plan. Invocable as /workplan.
allowed-tools: Bash(*), Read, Write, Grep, Glob, WebSearch, WebFetch, AskUserQuestion
---

Read the **English** `aris-profile/PROFILE_AUTO.md` (via `$ARIS_PROFILE`) first — canonical; `PROFILE_AUTO.zh.md` is a human-facing mirror, not for logic. If absent, tell the user to run `/profile-construct`. Converse in **Chinese**; keep code/identifiers/paper-titles native.

**Which idea to plan (resolve in order):** (1) explicit argument wins — a standard idea id (`I3`), disruptive wildcard id (`D1`), rank number, or free-text idea; (2) else read the `SELECTED` stamp in `outputs/02_IDEA_REPORT.html` and echo its exact `I<k> — <title>` or `D1 — <title>` so a wrong pick is caught early; (3) report present but nothing stamped / id mismatch → don't guess, AskUserQuestion to pick; (4) no report → point to `/ideagen` (or accept a full free-text idea). Read the chosen idea's full row and card (mechanism / hypothesis / decisive falsifier / MVE / closest work) as the plan seed. For `D1`, preserve its broken-assumption claim and decisive falsifier as the plan's first gate; do not normalize it back into an incremental module.

## Output conventions
- **Shared `outputs/` folder, two-digit prefixes:** this skill writes `outputs/03_EXPERIMENT_PLAN.html` (+ its `.zh.html` mirror). **The paper skeleton is a SECTION INSIDE `03`, not a separate file** — the researcher considers the projected-paper structure to be part of the workplan itself. Only emit a standalone `outputs/03b_PAPER_PLAN.html` if she explicitly asks for a fuller/visual paper outline beyond the skeleton section.
- **Self-contained HTML, never Markdown** — inline `<style>`, no external assets, real structure (`<h1>/<h2>`, `<table>`, `<ul>`); use **continuous tables as the primary layout** for structured content, never card/grid layouts; **every paper reference a direct `<a href>`** to arXiv/DOI, unverifiable → visible `pending`, never fabricated.
- **English first (canonical), then a faithful Chinese mirror — both always present.** Write the plan in English → `outputs/03_EXPERIMENT_PLAN.html`, then produce `outputs/03_EXPERIMENT_PLAN.zh.html` (same structure/tables/links, natural native Chinese, never machine translation). **Address the researcher in the SECOND person — 你 / 你的, never third person 她 / 她的** (English "her stack / her Flipping-KD" → 你的技术栈 / 你的 Flipping-KD; 她 reads as talking about a stranger). English is canonical — it is what `/run-plan` reads. Keep the two in sync: if the plan changes at the approval gate, re-translate the changed parts so the zh mirror never drifts. Converse with the researcher in Chinese as before.

## B — Experiment plan → `outputs/03_EXPERIMENT_PLAN.html`

**FIRST, read the full text of the closest papers — do not guess the comparison set.** Pull the actual experimental setup of the 2–4 closest papers to the idea (from its *closest work* + the *Literature Landscape* in `outputs/02_IDEA_REPORT.html`): fetch full text (`tools/fetch_fulltext.py` / `pdftotext` / WebFetch), read the **experiments/setup section + result tables**, and extract the concrete **baselines, datasets, metrics, and reusable variables** they use. That is what tells you what to beat, on what data, and which quantities can be validly measured; a plan from memory is guessing. For every variable introduced by the plan, state whether it is directly reused from prior work, adapted from prior work, or newly proposed by this plan. Newly proposed variables must be marked `PROPOSED` and need a feasibility check before they can support a claim. Unfetchable paper → mark `[UNVERIFIED]`, don't invent. Record a **grounding table** (paper → baselines · datasets · metrics · reusable variables, each linked). **Place this table as an APPENDIX at the very END of the plan (after the GATE), not at the top** — the researcher wants to open on the projected abstract + claims, and read the grounding evidence last as backing (it is the base every baseline/dataset/metric/variable is drawn from, so keep it whole, just at the bottom). Sections reference it by name ("drawn from the grounding table / see Appendix").

**Primary reference — whose datasets/metrics/baselines are the must-cover floor.** Before building the plan's dataset/baseline list, determine which grounded paper is the primary reference. Resolve in this order:

- **Rule 1 — researcher's own closest paper.** If the idea builds on a paper the researcher authored (check PROFILE_AUTO.md Publications Index), that paper IS the primary reference. Its datasets, metrics, and baselines are the **must-cover floor** (labeled `[P]` throughout the plan). Other papers' datasets/baselines are **recommended supplements** (labeled `[S]`), included only if they add coverage without conflicting with the primary.
- **Rule 2 — highest relevance + impact among the closest papers.** If the researcher has no directly relevant paper of her own (new direction), score each grounded paper on: **relevance** (how closely its task/method matches the idea, 1–5) + **impact** (citations weighted by venue tier, 1–5). Take the highest total as the surrogate primary. If tied, relevance beats impact — matching the task matters more than raw prestige for experimental design.

When grounded papers have **conflicting datasets/metrics** (same name but different version, split, or computation), do NOT silently merge them into one entry. Keep both in the grounding table with their source paper noted, and surface the conflict in a short **"待你裁决"** box right before the GATE — let the researcher decide which to adopt as authoritative.

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

Do not force all of these fields into one extremely wide main-body table. The final HTML must use:

- a compact, complete candidate overview in §2.2, grouped by family, containing every `B*` candidate;
- a detailed baseline audit table in the grounding appendix for compatibility, code, burden, evidence, and provenance fields.

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

Baseline selection must happen **during the `/workplan` conversation, after the complete registry and taxonomy are built, and before repository discovery or final HTML generation**. The HTML records the decision; it is not the interface used to collect it.

1. **Show the taxonomy and classify the current idea in the Chinese conversation.** Keep the explanation concise but explicit.

2. **Show every baseline candidate, grouped by family and ordered by recommendation tier.** Use a numbered list such as:

   `B1. Method — family — Required — role: closest competitor — reuse: RERUN_PREFERRED`

   Do not show only the recommended subset. The researcher must be able to see the complete grounded candidate set.

3. **Print the shortcut expansions, then ask the baseline-selection question with `AskUserQuestion`.**

   Immediately before asking, print a compact **Selection shortcuts** block in the Chinese conversation. It must explicitly expand the tier shortcuts into baseline IDs and names:

   - `Required`: list every `Required` baseline as `B<ID> Method`;
   - `Strongly recommended`: list every `Strongly recommended` baseline as `B<ID> Method`;
   - `required selects`: repeat the exact `Required` IDs and names that will be selected;
   - `recommended selects`: repeat the exact union of `Required + Strongly recommended` IDs and names that will be selected;
   - `all selects`: state that it selects every listed experimental baseline except `Citation only`, and preferably list the IDs when the list is not excessively long.

   Use this conversation format:

   ```text
   Selection shortcuts

   Required:
   - B4 GETNext
   - B9 MMPOI
   ...

   Strongly recommended:
   - B2 BPR
   - B3 SASRec
   ...

   required selects:
   B4 GETNext, B9 MMPOI, ...

   recommended selects:
   B2 BPR, B3 SASRec, B4 GETNext, B7 STHGCN, ...

   all selects:
   every B* candidate except Citation only
   ```

   Do not print only the words `required` and `recommended`; the researcher must see exactly which methods each shortcut expands to before answering.

   Then call `AskUserQuestion`. Accept:

   - `B1,B3,B7` or `1,3,7` to select specific baselines;
   - `all` to select every listed experimental baseline except `Citation only`;
   - `required` to select exactly the printed `Required` set;
   - `recommended` to select exactly the printed union of `Required` plus `Strongly recommended`;
   - `none` to select no experimental baseline, while clearly warning that the plan may become scientifically invalid.

   Multiple selections are allowed. Never silently add an unselected baseline. If a `Required` baseline is omitted, summarize the resulting scientific risk and ask for explicit confirmation before continuing. Unknown IDs, contradictory forms such as `all,none`, or ambiguous prose require clarification rather than guessing.

4. **Resolve result-reuse decisions for the selected baselines.** If no selected baseline is `REUSE_ELIGIBLE_REPORTED` or `RERUN_PREFERRED`, continue without another question. Otherwise show the eligible candidates and ask one compact `AskUserQuestion`:

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

Only after this baseline contract is resolved should repository discovery begin. Search implementation repositories primarily for the **selected baselines**, the primary reference, and implementation-critical modules. An unselected baseline may still appear in Related Work or the complete candidate table, but its repository must not be treated as necessary for `/run-plan`.

#### 7. Required HTML structure for baselines

The baseline material must appear under the main section:

`2. Systems, Datasets, Metrics, and Baseline Design`

Do not repeat a legacy `Must-beat baselines` row containing every candidate before the taxonomy. The system/dataset/metric summary may state the method, datasets, metrics, and a one-line summary of the **selected** baseline coverage, but the candidate and selection details belong in §2.1–§2.4.

Use these exact subsection numbers and titles in both HTML files:

##### 2.1 Baseline Taxonomy and Idea Classification

Include:

- the literature-derived taxonomy;
- the current idea's primary family and hybrid tags;
- the papers supporting the classification;
- why the classification determines necessary comparisons;
- the minimum family coverage expected for a credible experiment.

##### 2.2 Complete Baseline Candidate Overview

List every `B*` candidate, grouped into separate compact tables by primary family. Do not use one unreadable table with more than eight columns.

Each family table should contain only:

- `ID`;
- `Baseline`;
- `Secondary tags`;
- `Scientific role`;
- `Tier`;
- `Selected?`;
- `Planned action`.

Use `[x]` / `[ ]` only after the human selection is resolved. `Planned action` must be exactly `RUN_LOCAL`, `REUSE_REPORTED`, `CITATION_ONLY`, or `UNSELECTED`.

Put the remaining detailed registry fields, including compared-in papers, frequency, protocol compatibility, code availability, reproduction burden, evidence status, and decision rationale, in a **Detailed Baseline Audit** table in the final grounding appendix.

##### 2.3 Human-selected Baseline Contract

Show:

- selected baselines only, grouped by family;
- recommendation tier and scientific role;
- exact execution action for each selected baseline;
- family-coverage summary;
- omitted Required baselines;
- for each omitted Required baseline: affected claim(s), reviewer risk, and approved fallback;
- a clear warning when the selected set does not include the closest direct competitor or lacks a necessary family.

Do not repeat all unselected Optional baselines in this subsection; they remain visible in §2.2.

##### 2.4 Baseline Result Reuse and Provenance

This subsection is mandatory even when no result is reused.

For every selected baseline, include:

- selected action;
- reuse classification;
- exact source paper and exact table/figure when `REUSE_REPORTED`;
- dataset/version;
- split;
- candidate/negative-sampling protocol;
- metric definition and `K`;
- model/backbone/version;
- known matching fields;
- unresolved or conflicting fields;
- final decision and rationale.

If nothing is reused, state explicitly:

`No literature-reported baseline number is reused in the main comparison; selected baselines are rerun locally or citation-only.`

When a result is reused, display the exact note:

`Reported result reused from <paper/table>; not rerun in this project.`

Never use `REUSE_REPORTED` with an unspecified source or a conditional phrase such as `when protocol is sufficiently matched`.

The English and Chinese HTML files must contain identical baseline selections, actions, omitted-Required risks, and reuse decisions.

### Repository candidate registry, interactive selection, and grounding contract

For the primary reference, the human-selected baselines, and implementation-critical modules, identify useful repositories from paper/project links, official author repositories, repository links found in retrieved full text, WebSearch results, and any public GitHub URL, private Git URL, or local path supplied by the researcher. Repository discovery is a recommendation step, not proof that code is correct, complete, compatible, or runnable.

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
- visible branch/tag/commit, otherwise `to pin in /run-plan`;
- known environment/dependency notes;
- compatibility risks and fallback.

Do not force all fields into one wide main-body table. Put the compact candidate overview in §2.5 and the detailed repository audit in the final grounding appendix.

Do not claim that a repository is runnable, paper-faithful, complete, compatible, or safe to reuse unless `/run-plan` later pins a revision and verifies it. Do not silently treat every recommended repository as implementation authority.

#### 2. Mandatory interactive repository selection

Repository selection must happen **during the `/workplan` conversation, after the baseline contract is resolved and before the final English or Chinese HTML is written**. The HTML records the decision; it is not the interface used to collect the decision.

1. **Show all repository candidates in the Chinese conversation.**

   Group candidates by primary purpose and use a concise format:

   `R1. org/repo — purpose: evaluator — grounds: B4 / metric protocol — priority: Preferred — status: author-provided — verification: paper-linked`

   Include all candidates that may reasonably help implementation. If no useful repository is found, say so and continue directly to the manual-addition question.

2. **Ask the repository-selection question with `AskUserQuestion`.**

   Accept:

   - `R1,R3` or `1,3` to select specific repositories;
   - `all` to select every listed repository except those marked `Background`;
   - `none` to proceed without selecting a recommended repository.

   Multiple selections are allowed. Never select a repository merely because it was recommended. If the response contains an unknown ID, contradictory choices such as `all,none`, or ambiguous prose, ask again instead of guessing.

3. **Ask the manual-addition question with `AskUserQuestion`.**

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
  - `PRIMARY_BASE`: the project or repository that `/run-plan` should extend as the main implementation base;
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
- a `/run-plan` verification checklist;
- a fallback if verification fails.

After proposing these contracts, ask one compact `AskUserQuestion`:

- `approve repository contract`;
- or revisions such as  
  `R4=PRIMARY_BASE; R1=REFERENCE_ONLY evaluator only; M1=data split authority`.

If two selected repositories claim authority over the same data split, evaluator, baseline implementation, or module and no precedence is clear, the conflict must be resolved before HTML generation. Never merge conflicting implementations silently.

#### 4. Required `/run-plan` verification checklist

A selected repository is still **not verified runnable** at `/workplan` time. For every `PRIMARY_BASE` or `VERIFY_AND_USE` reference, the contract must require `/run-plan` to:

- pin and record the exact commit/tag/revision;
- inspect license and redistribution constraints;
- inspect environment and dependency compatibility;
- run the smallest available smoke test;
- verify dataset split and evaluator behavior when those are approved scopes;
- record files/configs actually reused or modified;
- keep user code and upstream code distinguishable;
- fall back to the approved alternative if verification fails.

`REFERENCE_ONLY` repositories do not need to be executed, but `/run-plan` must record which design, configuration, or code location was consulted.

#### 5. Required HTML structure for repositories

##### 2.5 Code Repository Candidate Overview

List every `R*` candidate, grouped by primary purpose. Use compact tables containing only:

- `ID`;
- `Repository / path`;
- `Primary purpose`;
- `Grounds`;
- `Priority`;
- `Verification`;
- `Selected?`.

Show `[x]` / `[ ]` only after the interaction is resolved. Do not repeat the full baseline list in this section; reference baseline IDs such as `B4`, `B17`, or module names.

Put discovery source, official/community status, license, revision status, dependencies, compatibility risks, and fallback in a **Detailed Repository Audit** table in the final grounding appendix.

##### 2.6 Human-selected Repository Grounding Contract

Show only selected `R*` and approved manual `M*` references. Do not repeat all unselected candidates; they remain visible in §2.5.

For each selected reference record:

- use mode: `PRIMARY_BASE`, `VERIFY_AND_USE`, or `REFERENCE_ONLY`;
- allowed scope;
- prohibited scope;
- integration target;
- authority / precedence;
- required `/run-plan` verification;
- fallback.

If no repository is selected and no manual addition is approved, state:

`Approved to proceed without repository grounding.`

When multiple references overlap, add a compact **Authority and Conflict Resolution** note. For example:

- `M1 is authoritative for dataset split and evaluator`;
- `R4 is authoritative only for baseline B17 implementation`;
- `R1 is background/reference only and must not override M1`.

Only references listed in §2.6 may guide `/run-plan`. Unselected candidates in §2.5 are background only and must not be silently cloned, copied, or used to determine implementation details.

The English and Chinese HTML files must contain identical selections, use modes, scopes, precedence rules, and verification requirements.

Then, claim-driven (not a to-do list), **written backward from the abstract:**
0. **Projected Title + Abstract (write FIRST)** — immediately **above the abstract, draft a working paper title** (`<h2>`-sized, styled as a title): a concrete, non-generic title naming the idea's ONE core mechanism (a short name + a claim-bearing subtitle is fine, e.g. "ABD++: One Modality-Invariant Harmful Axis for Deployable Jailbreak Defense"), not a topic label. It should read like a real paper title and match the idea's single mechanism — if the best honest title still sounds like "technique A applied to domain B", that is a signal the idea is a mashup (flag it, don't dress it up). Then the **projected abstract** — the abstract the paper *would* have if the idea succeeds, in her *Writing Style* (gap-first, "We propose/release" bullets). Mark **PROJECTED — not results**; every number a placeholder `[X%]`, never fabricated.
   - Tight: ≤ ~180 words / 8–10 sentences (one gap · one "we present X" · 2–3 method · 1–2 result-with-placeholder · one takeaway).
   - **No em-dashes, no rare words** (both languages); plain common words, keep only genuine terms of art.
   - **Chinese = faithful sentence-for-sentence translation of the English** (same claims/numbers/order), not a shorter separate summary; English is canonical, re-translate if it changes.
   - **abstract↔claim self-check:** map each abstract claim-sentence to a §1 claim; a sentence with no backing experiment gets cut or gets an experiment.
0.5. **Projected Paper Skeleton (write right after the abstract, INSIDE `03`)** — the researcher expects the workplan to show the whole projected paper, not just the runs. WebFetch the actual section headings of the single closest paper (from the *Literature Landscape*) and model the structure on it; cite it as the template. Include: **Introduction** — one topic sentence per paragraph, gap-first (say what each paragraph does); **Related Work** — the sections it splits into + a one-line position for each (every paper a real `<a href>`); **Method** — the module-titled subsections (name each module). For each Method module, list its inputs, outputs, variables computed or consumed, where each variable will appear in raw result files, and whether each variable is `claim-grade`, `pilot-only`, `smoke-only`, or `unavailable`; **Experiments** — a table mapping each planned paper subsection (4.1, 4.2, …) to the concrete experiment and the claim/metric it backs; **Discussion/Conclusion** — one topic sentence each. Mark PROJECTED, keep `[X%]` placeholders. §1—§7 below are the concrete experiment plan that fills this skeleton's Experiments section.
1. **Claims → evidence → variables** — each intended claim must map to (a) the experiment that supports it, (b) the variables that must be measured, (c) the raw fields that store those variables, and (d) the computation path from raw fields to final metric. No claim without planned measurable variables. No variable without a raw-field contract. Put every claim in a compact **pre-registered interpretation table row**, never a card: columns are (a) primary metric and comparison, (b) minimum practically meaningful effect or expected direction, (c) uncertainty reporting rule (seeds / CI / test as appropriate), and (d) the result pattern that would weaken or falsify the claim. This is a reading aid fixed before runs, not an automatic accept/reject rule: the researcher remains the judge at the result gate. Do not retrofit these criteria after seeing results; if a protocol change is necessary, record it visibly as a dated amendment with the reason.
2. **Systems, Datasets, Metrics, and Baseline Design** — give the method, datasets, and metrics first, then use the exact subsection hierarchy:
   - `2.1 Baseline Taxonomy and Idea Classification`;
   - `2.2 Complete Baseline Candidate Overview`;
   - `2.3 Human-selected Baseline Contract`;
   - `2.4 Baseline Result Reuse and Provenance`;
   - `2.5 Code Repository Candidate Overview`;
   - `2.6 Human-selected Repository Grounding Contract`.

   All baselines must be drawn from grounding evidence (real, not invented). Preserve `[P]` for the primary-reference floor and `[S]` for supplementary evidence, but do not equate `[P]` with automatic user selection. Do not include a duplicate pre-selection `Must-beat baselines` row listing every candidate. Every selected baseline must have exactly one action: `RUN_LOCAL`, `REUSE_REPORTED`, or `CITATION_ONLY`. If grounded papers disagree on a dataset version/split, metric computation, or baseline-result protocol, flag it in the GATE's "待你裁决" box — don't silently merge or drop.

   Repository sections record decisions already collected through `AskUserQuestion` before HTML generation. Keep the complete compact candidate overview in §2.5 and the selected-only grounding contract in §2.6. Every selected reference must have exactly one use mode (`PRIMARY_BASE`, `VERIFY_AND_USE`, or `REFERENCE_ONLY`), explicit allowed/prohibited scopes, an integration target, a precedence rule when needed, and a `/run-plan` verification/fallback plan.
3. **Variable Feasibility & Provenance Table** — for every variable introduced in the plan, include: `Variable · Used in · Purpose · Source · Required observable · Available now? · Fallback/proxy · Raw field · Evidence grade`. A variable means any quantity used by the method, metric, verifier, router, ablation, claim, or analysis. Evidence grade must be one of `claim-grade`, `pilot-only`, `smoke-only`, or `unavailable`. Do not mention a variable in the abstract, method, claims, metrics, run order, or ablation table unless it appears here.
4. **Ablation matrix** — one row per ablated component; each row changes exactly one variable vs the full method.
5. **Run order** — instrumentation sanity → generation smoke → baseline → diagnosis/main pilot → ablation → polish. Instrumentation sanity must verify that every variable named in the Method, Claims, Metrics, or Routing sections exists in the raw output schema, has a documented computation path, is computable with the current stack, is written as `MISSING` if unavailable, and is downgraded to `smoke-only` or `pilot-only` if only a proxy is available.
6. **Configs** — launcher/framework/base-model from *Experiment Templates* (stack match). Set lr/batch/epochs/seed HERE (task-determined; profile does not supply these). OOM-safe defaults if the profile records OOMs.
7. **Budget** — rough GPU-hours per block; flag >1-day runs for sign-off.

**GATE:** present the plan summary (claims, selected baseline coverage by family, exact baseline actions, exact reuse sources, omitted-Required risks and affected claims, selected repository use modes/scopes, repository authority or conflicts, variable feasibility table, ablation rows, first 3 runs, budget, and verification fallbacks). Baseline and repository contracts must be resolved before the final HTML files are written, so the GATE asks only for approval or revision of the complete plan. **Stop for approval before `/run-plan`.**

## C — Standalone paper plan → `outputs/03b_PAPER_PLAN.html` (only on explicit request)
The paper skeleton normally lives as the §0.5 section inside `03` (above). Produce a SEPARATE `03b_PAPER_PLAN.html` **only if the researcher explicitly asks for a fuller / more visual paper outline** than that section. If she does: WebFetch the closest paper's actual section headings, then write a self-contained HTML (EN canonical + faithful ZH mirror) in this order: **Abstract** (§0 projected, EN + faithful ZH) · **Introduction** (one topic sentence per paragraph) · **Related Work** · **Method** (subsections titled by module name) · **Experiments** (table: subsection → planned experiment → claim/metric) · **Discussion/Conclusion** · **References** (every one a direct hyperlink; unverifiable → `pending`). Keep it a *plan*: mark projected, keep `[X%]` placeholders, cite only real retrieved links.
