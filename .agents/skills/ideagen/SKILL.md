---
name: "ideagen"
description: "Help the researcher find candidate research ideas through a personalized lens (engineering/theory/benchmark), grounded in the researcher's own record AND the literature survey produced by $researchlit; check novelty against concurrent work, flag material ethical risks for the researcher's judgment, and present a ranked slate for the researcher to pick from — plus, ONLY when the user explicitly asks for a disruptive/paradigm-breaking idea (default off), at most one evidence-tethered disruptive wildcard (D1) appended in the same report. Optionally build on a reference paper. Stops at the pick gate for the researcher to decide; the chosen idea goes to $expdesign. Use when the user wants new research ideas, a research direction, brainstorming, disruptive/paradigm-shifting ideas, or a literature survey alone (for a literature survey alone, use $researchlit). Invoke explicitly as `$ideagen`."
---

Read `researcher-profile/PROFILE.md` (at the project-local `researcher-profile/` path) first; it is the only profile document and canonical source. If it is absent, tell the user to run `$profileconstruct`.

**Arguments:** `<direction>` (free text) · `— lens: engineering|theory|benchmark` (= **mode**) · `— disruptive-wildcard: on|off` (**default `off`** — the wildcard runs ONLY when the user explicitly asks for it, e.g. `— disruptive-wildcard: on` or a plain-language request for a disruptive/paradigm-breaking idea; never infer it on) · `— ref paper: <arXiv URL | PDF | URL>` (*optional*, triggers A0).


## Disruptive wildcard (opt-in; default off)

The standard profile · literature-gap slate is the primary output. The wildcard runs
**only when the user explicitly asks** (`— disruptive-wildcard: on` or a plain-language
request for a disruptive/paradigm-breaking idea). When on, append at most ONE
evidence-tethered survivor (`D1`) after the standard cards in the **same report** — never a
standalone disruptive report, and never merge the disruptive and standard rankings (their
scores mean different things). **When on, read
[`references/disruptive-branch.md`](references/disruptive-branch.md) completely before A1
and follow it as mandatory procedure** — it holds the full method (honesty boundary, D0
Route Gravity Map, D1–D3 blind incubation, D4 absorbability, D5 scoring, required report
fields). The steps below carry only one-line pointers into it.

## Step 1 — Lock MODE + direction + wildcard first
The mode decides what *kind* of standard contribution is generated; the wildcard switch decides whether one disruptive outlier is incubated and appended. Fix mode + direction BEFORE anything else — never infer silently, never start A1 first. **The wildcard defaults to `off`**: run it ONLY when the user explicitly passed `— disruptive-wildcard: on` or asked in plain language for a disruptive / paradigm-breaking / wildcard idea. Do NOT ask an ask the user directly about the wildcard and do NOT turn it on by default. If `— lens:` was passed use it; else **ask the user directly** for the missing values: mode (engineering = iterate habitual methods, reuse code · benchmark = survey / new dataset-eval / reproduce-and-beat · theory = a hypothesis/bound on the method-evolution fault line) and `<direction>` (offer her *Niche subfields* if none given). Only once mode + direction are fixed do A0/A1/A2/A3 run (A2 runs only if the wildcard was explicitly turned on).


## Step 2 — Ethics triage (conditional; do not create unnecessary prompts)
After direction and mode are fixed, screen the direction and every candidate idea for **material ethical risk**. This is a conditional annotation pass, not a generic disclaimer.

Flag only when the proposed research directly studies, predicts, manipulates, exposes, or deploys systems affecting people, communities, or socially consequential decisions. Trigger the screen for: human participants, consent or deception; children, patients, vulnerable groups, protected classes, or unequal outcomes; personal, sensitive, private, mobility, biometric, health, or re-identification data; political persuasion, public-opinion manipulation, polarization, propaganda, social influence, or mass behavior intervention; surveillance, profiling, high-stakes decisions, safety-critical deployment, or automated decisions about people; or dual-use capabilities with foreseeable harmful misuse.

Do **not** flag a generic method, dataset-free simulation, or ordinary model evaluation merely because it uses `agent`, `social`, `safety`, or `simulation`. If no concrete pathway is present, do not ask an ethics question and omit all ethics output from the report.

For each flagged candidate, assign exactly one level: `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`, based on foreseeable harm, affected-party vulnerability, data sensitivity, scale, reversibility, and ease of misuse. Keep ethical risk separate from technical feasibility and publication risk. Do not make a legal or IRB determination without a verified source; use `[REQUIRES IRB/ETHICS REVIEW]` when institutional review may be required.

Each flagged card must include an **Ethics assessment** covering: affected parties and context; concrete harm pathways; data, consent, retention, and de-identification; misuse and dual use; safeguards; and residual risk/uncertainty. Do not invent laws, consent status, incidents, or empirical harms. Ethics is an annotation and human decision gate, never an automatic rejection.

## Output conventions
- **One folder `reports/` (create it), two-digit step prefixes.** The survey `reports/01_LIT_SURVEY.html` is written by `$researchlit` (the grounding this skill reads). This skill writes the single canonical `reports/02_IDEA_REPORT.html` (a **short** landscape pointer to the survey + the ranked ideas — NOT a duplicated paper appendix); when `— ref paper:` is given, the reference-paper reading is folded in as a short "Reference Paper Notes" box at the top of `02` (A0), NOT a separate file. Downstream continues the numbering (`03_EXPERIMENT_PLAN` … `04_EXP_RESULT`).
- **Every deliverable is self-contained HTML, never Markdown** — inline `<style>`, no external assets, real structure (`<h1>/<h2>`, `<table>`, `<ul>`). **Every paper reference is a direct `<a href>`** to its arXiv/DOI; unverifiable → visible `pending`, never a fabricated URL.
- The single file `reports/02_IDEA_REPORT.html` is the **primary** — it is what `$expdesign` reads, and the `SELECTED` stamp lives in it. Address the researcher directly, never in the third person.

## A0 — Reference paper (only if `— ref paper:` given)
Summarize BEFORE surveying so generation targets its gaps. Fetch (`tools/fetch_fulltext.py` / `pdftotext` / web open/fetch) and read the paper for **what they did · key results · limitations & open questions · improvement directions**. Numbers/claims trace to the paper's text; if you couldn't fetch it, say so and ask for the PDF. **Do NOT write a separate summary file** — this reading is internal grounding for idea generation. When `— ref paper:` was given, surface it as a **short "Reference Paper Notes" box at the very top of `02_IDEA_REPORT.html`** (those four bullets, condensed), so the reader sees the gap the ideas are built to attack; without `— ref paper:` there is no such box (grounding is the survey landscape only). This box is a conditional block, separate from and above the regular Literature Landscape section.

## A1 — Read the literature survey (from `$researchlit` — do NOT re-survey)
**ideagen no longer runs its own survey.** The grounding is the survey `$researchlit` already produced at **`reports/01_LIT_SURVEY.html`**. Do this:
1. **Read `reports/01_LIT_SURVEY.html`.** Extract its landscape prose, the live debates, the **structural gaps** it flagged, and its verified paper list (titles + arXiv ids + one-line takeaways) — this is the evidence base the ideas are grounded on.
2. **If it is missing or clearly off-topic vs the locked `<direction>`** (e.g. the survey covers a different topic than the researcher just asked for), do NOT silently proceed on nothing: **run `$researchlit "<direction>" — for: ideagen`** to produce it first (fan-out verified search, writes the white-background HTML), then read it. If the researcher explicitly asked to skip the survey, proceed on the profile alone and say the grounding is thin.
3. **Do NOT duplicate the survey's appendix in the idea report.** The full categorized paper list lives in `01_LIT_SURVEY.html`. In `02_IDEA_REPORT.html`, open with a **short Literature Landscape** (a few sentences summarizing the survey's debates + gaps) that **links to `01_LIT_SURVEY.html`** ("See the literature survey for the complete evidence list"), and per idea cite only the **closest 1–3 papers** (direct `<a href>`) needed to justify its novelty verdict. **Anti-hallucination still applies:** cite only papers that appear (verified) in the survey or that you separately retrieved for a novelty check; unverifiable → `[UNVERIFIED]`, never fabricate.
4. **Novelty top-ups are allowed.** A3/A4 may run a few *targeted* searches to pin the closest concurrent work for a specific candidate (last 3–6 months) — that is a novelty check, not a re-survey. Keep it narrow.

When the wildcard is on, first build the **Route Gravity Map** from the survey grounding — the seven field defaults, each citing survey evidence (D0 in `references/disruptive-branch.md`).

## A2 — Blind disruptive incubation (wildcard `on` only)

When the wildcard is on, run **D0–D3** from `references/disruptive-branch.md` here — immediately after the survey grounding and **before** reading any prior idea report or drafting standard candidates — and hold the surviving seeds unranked until D4 restores the literature.



## A3 — Idea generation (ONE lens, branch-aware, method-first)
Generate 6 candidates through the chosen mode, seeded by the profile AND the survey's structural gaps (from A1 / `01_LIT_SURVEY.html`):
- **engineering** — iterate habitual methods from *Dominant Methods*; prefer reuse-existing-code. No arbitrary time cap ("2-week pilot"); let the problem set the scope.
- **theory** — read *Publications Index* in time order + *Research Lineage*; find the method-evolution fault line; propose hypotheses adjacent to, not repeating, the lineage.
- **benchmark** — from *Active Venues* + *Niche Subfields*: follow-up **survey** / **custom benchmark-dataset** filling an eval gap / **reproduce-and-beat** a recent competitor.

**“Plain-language summary” is mandatory and comes first.** Before the technical pitch, write exactly one plain-language sentence for every idea that an adjacent-area researcher can understand on the first read. It must state all three: **the concrete problem, what will be changed/built/tested, and the observable result that would matter**. Do not use an unexplained method name, acronym, metaphor, or abstract label as the idea. If the reader must first understand terms such as “interchange intervention”, “behavioral iso-effect”, or a newly coined framework name, rewrite the sentence. Put this same plain-language sentence in the ranked table, at the top of the idea card under a visible `Plain-language summary` label, and in the human pick options. The technical one-sentence pitch and method details may follow it; they must not replace it.

**One-sentence lead + method-first.** Every idea opens with **ONE clear sentence** that says what it is — concrete about mechanism and contribution, readable in a single pass. Write it **for an experienced peer**: use the correct domain terms precisely (do not avoid them), but do NOT hide behind abstract methodology-speak ("steering as a measurement tool for mechanistic faithfulness") NOR dumb it down with childish analogies (kids arguing about vaccines). If the one sentence isn't clear, the idea isn't ready. Only *after* that sentence give the **2–4 concrete method steps** (what we build/train/run), then hypothesis/expected-outcome as acceptance criteria.



For the disruptive wildcard, generate per the blind-synthesis sequence in `references/disruptive-branch.md` (D1–D3: quarantine prior solution wording · ≥4 drift operators · generate from a documented anomaly · one irreducible mechanism), not by extending the paper list or asking for "more novel" variants.

**Ethics output rule.** If the ethics triage flags at least one candidate, add a rightmost column to the ranked-idea table. Each flagged row must show the level plus a compact reason, such as `HIGH — opinion manipulation at population scale`; unflagged rows must say `No material issue identified`, not a warning prompt. In the idea-cards section, add the full **Ethics assessment** subsection inside the same card that contains that idea's pitch, method, hypothesis, and qualitative record. The assessment must not be moved to a global ethics section or a separate standalone card. If nothing is flagged, do not add an ethics column, ethics subsection, or ethics-related question anywhere in the report.

**Re-run = accumulate, never discard — without contaminating the blind pass.** When the wildcard is on, finish A2 before opening the prior report. A re-invocation does NOT replace the prior slate with an all-new one. Read any prior `reports/02_IDEA_REPORT.html`, **carry ALL its ideas forward** (they remain valid candidates — an un-selected idea is not a failed idea), then **ADD fresh candidates** by rotating to a different profile asset / gap, and **re-rank the union**. The pool grows across runs. Mark the new ones (`? new this run`) so the researcher sees what changed. Only drop an idea the researcher *explicitly rejected* as a direction. Do NOT manufacture a gimmicky twist / far-fetched mashup / contrived problem just to add something new: if this run's honest fresh angles turn out crowded or weaker than the carried-forward ideas, say so explicitly and let the strong prior ideas keep their rank rather than padding the slate.

**Present the honest slate; never enforce a novelty quota.** If few candidates are genuinely `novel`, say so explicitly rather than padding the slate or relabeling `differentiable` / weakly verified ideas.

## A4 — Candidate-level novelty evidence check
For **each surviving candidate**, assess novelty at the candidate level rather than decomposing it into an ARIS-style dossier of atomic claims:

1. **Compare with the researcher's own work.** Identify whether the candidate restates, lightly extends, or meaningfully departs from the researcher's publications.

2. **Run 2–3 targeted searches for that candidate.** Search the core mechanism, task/setting, and claimed contribution across recent work (~2 years), with an explicit final check of the latest 6 months. Reuse relevant evidence from A1 / `01_LIT_SURVEY.html` rather than repeating the full landscape survey; A4 only performs focused collision checks.

3. **Inspect the closest 3–5 papers sufficiently to judge overlap.** Do not decide from titles or snippets alone when abstracts or full text are available. Record the closest work, overlapping components, the candidate's concrete difference, overlap with the researcher's own work, and any uncertainty or missing evidence.

Assign exactly one novelty status:

- **`novel`** — the search evidence is sufficiently complete, the closest work does not cover the candidate's core mechanism or claimed contribution, and the concrete difference is substantive enough to support an independent, testable contribution.
- **`differentiable (needs framing)`** — the candidate overlaps substantially with the closest work but retains a concrete difference; however, that difference is incremental, application-specific, structurally unclear, or not yet strong enough to support a clearly independent contribution.
- **`already exists`** — prior work already covers the candidate's core mechanism and main claimed contribution; remaining differences are limited to implementation details, datasets, models, parameter choices, or presentation.
- **`[UNVERIFIED]`** — search coverage, source access, citation verification, or comparison evidence is insufficient to make a reliable judgment. **No paper found ≠ novel.**

A4 is an evidence and duplicate-check stage, not the final quality-ranking stage. A confirmed exact duplicate may be removed here. Every non-duplicate candidate, including those labeled `differentiable`, `already exists`, or `[UNVERIFIED]`, proceeds to A5 with its evidence and status attached. A5 decides whether the candidate should be reformulated, downranked, or excluded from the current recommended slate. Do not run a devil's-advocate or adversarial review in A4; that review belongs exclusively to A5.

Write the result directly into `reports/02_IDEA_REPORT.html`; **do not create `NOVELTY_DOSSIER.md` or another novelty artifact**. Include a novelty-evidence table with at least: `ID | Idea | Novelty status | Closest work | Overlap | Concrete difference | Own-work overlap | Evidence gaps | Confidence`.


For every disruptive seed surviving A2, run the **absorbability test** (D4 in `references/disruptive-branch.md`): if the closest work could absorb it as one module/loss/prompt/data-slice/benchmark-axis/scale-run without changing its central causal story, label it `incremental/absorbed` and drop it from wildcard eligibility (retain in the audit). This is where paper titles and prior ideas are reintroduced and the closest collision is recorded.

## A5 — Objective gate · qualitative review · ranking
Separate the objective filter from the qualitative ranking; do **not** use numeric scores, weighted totals, or a novelty scorecard.
1. **Objective gate (mechanical only):** drop a candidate only on an objective fact — compute clearly beyond the profile's hardware, or a provably-unavailable dataset. Never drop on "looks complex" / "might already be done"; annotate uncertainty instead.
2. **Qualitative record per idea:** novelty status · closest work · concrete difference · confidence · feasibility (compute/data/implementation vs the profile stack) · risk LOW/MED/HIGH · contribution type (empirical / method / benchmark / theory / diagnostic) · fit (which *Dominant Method*/niche) · single-mechanism test (below) · strongest reviewer objection · honest rough effort · **Ethics risk** (only if Step 2 flagged the idea; keep separate from technical `risk`).
2a. **Single-mechanism test — the anti-"boring mashup" gate (apply to EVERY idea).** State the idea's ONE core mechanism in a single sentence, then try to break the idea into independent contributions. **If it decomposes into "improvement A + improvement B" (e.g. `technique X` *plus* `apply it to domain Y`), where each half is a separate increment a reviewer could accept or reject on its own, the idea has no single core — it is a boring mashup and must NOT ship in that form.** Fix it, don't pad it: reforge around one insight so the parts stop being separable — the second "contribution" should become a *consequence or a falsification test* of the first, not a bolt-on module. (E.g. "defense A + also works on audio" is a mashup; "harmful intent lives on one modality-invariant axis, so the same conditional defense transfers to audio *for free* — and if it needs a separate audio module, the core claim is false" is one mechanism whose audio result is the test of the claim, not a second feature.) A candidate that survives only as A+B gets **capped at `differentiable`, never `novel`**, and is downranked below any true single-mechanism idea; note the decomposition explicitly in its card so the human sees why. This is *not* a licence to invent a grand unifying theory over a genuinely engineering idea — the reforged core can be a concrete engineering mechanism — it just has to be ONE thing.
2b. If the ethics triage flagged the idea, include **Ethics risk** in the qualitative record and keep it separate from the technical `risk` field. The rightmost table cell and the card's detailed assessment must agree exactly on the level. Do not silently downgrade a risk to improve ranking.
3. **Same-model devil's-advocate ranking:** in a clearly separated second pass, review the full set using the same model. For each idea state the strongest objection, likely failure mode, whether it passes 2a or remains an A+B mashup, whether the novelty evidence shows a collision or a defensible difference, and whether that difference can support a contribution. Rank qualitatively by this review, feasibility, risk, and research value—not by a numeric or weighted score—and write the objections out; never skip the pass.


For the disruptive pool, rank separately per **D5** in `references/disruptive-branch.md` (two-stage novelty-incubation → reality-reentry; visible **Disruptive score** = arithmetic mean of Paradigm break · Evidence plausibility · Falsifiability · Leverage/option value; feasibility risk only as tie-breaker; vague/cross-domain/expensive never earns points). Select exactly the highest-scoring eligible survivor as `D1`; do not expose lower-scoring survivors as extra cards.

## GATE — human is judge

Never create a second report for the disruptive pass. Set `data-idea-branch="standard"` and `data-disruptive-wildcard="present|shortfall|off"` on `<main>`. Mark every standard card with `data-idea-id="I<k>"`.

- With wildcard `on`, append a **Disruptive wildcard** section after all standard idea cards. If an eligible survivor exists, show exactly one `<article data-disruptive-id="D1">`, its Disruptive score, and every field required by `references/disruptive-branch.md`.
- If no disruptive seed survives, set `data-disruptive-wildcard="shortfall"` and show the compact failed-gate audit in that same position; do not invent `D1`.
- Keep the standard ranking table unchanged. Do not insert D1 as rank 8 and do not compare its Disruptive score to standard Novelty / qualitative ranks.
- When the wildcard is on, run `python3 tools/validate_ideagen_wildcard.py reports/02_IDEA_REPORT.html` and fix all errors before presenting it. Ask the researcher to pick / kill / redirect by id (`I*` or `D1`). Never auto-proceed.

Present **4–6 ranked ideas** in `reports/02_IDEA_REPORT.html` in A5 rank order. Use a separate ranked-summary table with the columns `ID | Idea | Novelty status | Closest work | Concrete difference | Strongest objection | Confidence` (and a rightmost `Ethics risk` column only when Step 2 flagged at least one candidate); do not show numeric scores or require a minimum number of `novel` verdicts. Give each a stable id `I1, I2, …` in the first column (this is how the pick is referenced downstream). **Each idea — in the table, card, and pick options — leads with the identical mandatory `Plain-language summary` from A3.** The card then gives the technical one-sentence pitch followed by method steps · hypothesis · MVE · own-work overlap · feasibility · risk · contribution type · unresolved novelty evidence. **Stop. ask the user directly for the researcher to pick / kill / redirect** (offer ideas by id + the `Plain-language summary`). Never auto-proceed.


If any ethics risk is `HIGH` or `CRITICAL`, the gate must state that the candidate requires explicit human ethics review before implementation, data collection, deployment, or release, as applicable. Ask only the concrete review question needed for the flagged pathway; do not show an ethics prompt for unflagged work. For `LOW` or `MEDIUM`, show the risk and safeguards in the report and let the normal idea-selection gate handle the decision.

**Persist the pick:** after she picks, stamp `reports/02_IDEA_REPORT.html` — a top banner `Selected: I<k> — <title>` (with date) + a `? SELECTED` tag on that row. If she redirects instead, regenerate and leave no stale stamp.

**Handoff:** the chosen idea → **`$expdesign`**, which reads the stamp and writes `reports/03_EXPERIMENT_PLAN.html`. Do not write the experiment plan here.
