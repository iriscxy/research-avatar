## A0 — Reference paper (only if `— ref paper:` given)
Summarize BEFORE surveying so generation targets its gaps. Fetch (`research_avatar/tools/fetch_fulltext.py` / `pdftotext` / web open/fetch) and read the paper for **what they did · key results · limitations & open questions · improvement directions**. Numbers/claims trace to the paper's text; if you couldn't fetch it, say so and ask for the PDF. **Do NOT write a separate summary file** — this reading is internal grounding for idea generation. When `— ref paper:` was given, surface it as a **short "Reference Paper Notes" box at the very top of `02_IDEA_REPORT.html`** (those four bullets, condensed), so the reader sees the gap the ideas are built to attack; without `— ref paper:` there is no such box (grounding is the survey landscape only). This box is a conditional block, separate from and above the regular Literature Landscape section.

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
- **theory** — read the records in `publications.json` in time order together with *Research Lineage* in `PROFILE.html`; find the method-evolution fault line; propose hypotheses adjacent to, not repeating, the lineage.
- **benchmark** — from *Active Venues* + *Niche Subfields*: follow-up **survey** / **custom benchmark-dataset** filling an eval gap / **reproduce-and-beat** a recent competitor.

**“Plain-language summary” is mandatory and comes first.** Before the technical pitch, write exactly one plain-language sentence for every idea that an adjacent-area researcher can understand on the first read. It must state all three: **the concrete problem, what will be changed/built/tested, and the observable result that would matter**. Do not use an unexplained method name, acronym, metaphor, or abstract label as the idea. If the reader must first understand terms such as “interchange intervention”, “behavioral iso-effect”, or a newly coined framework name, rewrite the sentence. Put this same plain-language sentence in the ranked table, at the top of the idea card under a visible `Plain-language summary` label, and in the human pick options. The technical one-sentence pitch and method details may follow it; they must not replace it.

**One-sentence lead + method-first.** Every idea opens with **ONE clear sentence** that says what it is — concrete about mechanism and contribution, readable in a single pass. Write it **for an experienced peer**: use the correct domain terms precisely (do not avoid them), but do NOT hide behind abstract methodology-speak ("steering as a measurement tool for mechanistic faithfulness") NOR dumb it down with childish analogies (kids arguing about vaccines). If the one sentence isn't clear, the idea isn't ready. Only *after* that sentence give the **2–4 concrete method steps** (what we build/train/run), then hypothesis/expected-outcome as acceptance criteria.



For the disruptive wildcard, generate per the blind-synthesis sequence in `references/disruptive-branch.md` (D1–D3: quarantine prior solution wording · ≥4 drift operators · generate from a documented anomaly · one irreducible mechanism), not by extending the paper list or asking for "more novel" variants.

**Ethics output rule.** If the ethics triage flags at least one candidate, add a rightmost column to the ranked-idea table. Each flagged row must show the level plus a compact reason, such as `HIGH — opinion manipulation at population scale`; unflagged rows must say `No material issue identified`, not a warning prompt. In the idea-cards section, add the full **Ethics assessment** subsection inside the same card that contains that idea's pitch, method, hypothesis, and qualitative record. The assessment must not be moved to a global ethics section or a separate standalone card. If nothing is flagged, do not add an ethics column, ethics subsection, or ethics-related question anywhere in the report.

**Re-run = accumulate, never discard — without contaminating the blind pass.** When the wildcard is on, finish A2 before loading prior structured idea records. A re-invocation does NOT replace the prior slate with an all-new one. Carry every unrejected record forward (an unselected idea is not a failed idea), then **ADD fresh candidates** by rotating to a different profile asset / gap, **re-rank the union**, and render a complete new report from that union. Never scrape manually changed prose or DOM from the prior delivered HTML as the source of truth. The pool grows across runs. Mark the new ones (`? new this run`) so the researcher sees what changed. Only drop an idea the researcher *explicitly rejected* as a direction. Do NOT manufacture a gimmicky twist / far-fetched mashup / contrived problem just to add something new: if this run's honest fresh angles turn out crowded or weaker than the carried-forward ideas, say so explicitly and let the strong prior ideas keep their rank rather than padding the slate.

**Present the honest slate; never enforce a novelty quota.** If few candidates are genuinely `novel`, say so explicitly rather than padding the slate or relabeling `differentiable` / weakly verified ideas. However, ideation must still give the researcher meaningful choice: after the first A5 pass, if fewer than 3 candidates are selectable (`novel` or a concrete, defensibly different `differentiable` candidate), run one additional generation pass by rotating to unused structural gaps and profile assets, novelty-check the fresh candidates, and rerank the union. Do not generate cosmetic variants of the same mechanism. If the second pass still yields fewer than 3 selectable candidates, report the field as crowded and keep the honest smaller slate.

## A4 — Candidate-level novelty evidence check
For **each surviving candidate**, assess novelty at the candidate level rather than decomposing it into an ARIS-style dossier of atomic claims:

1. **Compare with the researcher's own work.** Identify whether the candidate restates, lightly extends, or meaningfully departs from the researcher's publications.

2. **Run 2–3 targeted searches for that candidate.** Search the core mechanism, task/setting, and claimed contribution across recent work (~2 years), with an explicit final check of the latest 6 months. Reuse relevant evidence from A1 / `01_LIT_SURVEY.html` rather than repeating the full landscape survey; A4 only performs focused collision checks.

   The last-6-month check is a counterevidence pass: use the exact core
   mechanism, its synonyms, and mechanism+task combinations with the explicit
   goal of finding work that would absorb the candidate. Store the executed
   queries, date window, closest collision, and bounded difference in the
   novelty audit. Classic-work coverage cannot substitute for this pass.

3. **Inspect the closest 3–5 papers sufficiently to judge overlap.** Do not decide from titles or snippets alone when abstracts or full text are available. Record the closest work, overlapping components, the candidate's concrete difference, overlap with the researcher's own work, and any uncertainty or missing evidence.

Assign exactly one novelty status:

- **`novel`** — the search evidence is sufficiently complete, the closest work does not cover the candidate's core mechanism or claimed contribution, and the concrete difference is substantive enough to support an independent, testable contribution.
- **`differentiable (needs framing)`** — the candidate overlaps substantially with the closest work but retains a concrete difference; however, that difference is incremental, application-specific, structurally unclear, or not yet strong enough to support a clearly independent contribution.
- **`already exists`** — prior work already covers the candidate's core mechanism and main claimed contribution; remaining differences are limited to implementation details, datasets, models, parameter choices, or presentation.
- **`[UNVERIFIED]`** — search coverage, source access, citation verification, or comparison evidence is insufficient to make a reliable judgment. **No paper found ≠ novel.**

A4 is an evidence and duplicate-check stage, not the final quality-ranking stage. A confirmed exact duplicate may be removed here. Every non-duplicate candidate, including those labeled `differentiable`, `already exists`, or `[UNVERIFIED]`, proceeds to A5 with its evidence and status attached. A5 decides whether the candidate should be reformulated, downranked, or excluded from the current recommended slate. Do not run a devil's-advocate or adversarial review in A4; that review belongs exclusively to A5.

Write the result directly into `reports/02_IDEA_REPORT.html`; **do not create `NOVELTY_DOSSIER.md` or another novelty artifact**. Include a novelty-evidence table with at least: `ID | Idea | Novelty status | Closest work | Overlap | Concrete difference | Own-work overlap | Evidence gaps | Confidence`.

For every dataset asset, record one of `PUBLISHED`, `PUBLIC_REPOSITORY`,
`USER_PROVIDED_PRIVATE`, or `SELF_BUILT_UNPUBLISHED`. The last two have no
invented publication link. A self-built unpublished dataset instead records
its planned collection, versioning, access, and release status.


For every disruptive seed surviving A2, run the **absorbability test** (D4 in `references/disruptive-branch.md`): if the closest work could absorb it as one module/loss/prompt/data-slice/benchmark-axis/scale-run without changing its central causal story, label it `incremental/absorbed` and drop it from wildcard eligibility (retain in the audit). This is where paper titles and prior ideas are reintroduced and the closest collision is recorded.

## A5 — Objective gate · qualitative review · ranking
Separate the objective filter from the qualitative ranking; do **not** use numeric scores, weighted totals, or a novelty scorecard.
1. **Objective gate (mechanical only):** drop a candidate only on an objective fact — compute clearly beyond the profile's hardware, or a provably-unavailable dataset. Never drop on "looks complex" / "might already be done"; annotate uncertainty instead.
2. **Qualitative record per idea:** novelty status · closest work · concrete difference · confidence · feasibility (compute/data/implementation vs the profile stack) · risk LOW/MED/HIGH · contribution type (empirical / method / benchmark / theory / diagnostic) · fit (which *Dominant Method*/niche) · single-mechanism test (below) · scope-necessity test (below) · strongest reviewer objection · honest rough effort · **Ethics risk** (only if Step 2 flagged the idea; keep separate from technical `risk`). Feasibility contains only whether the work can be built and evaluated with available data, compute, access, time, and expertise. Incremental overlap, novelty collisions, and likely reviewer objections belong under novelty/reviewer risk, never under feasibility.
2a. **Single-mechanism test — anti-"boring mashup" diagnosis (apply to EVERY idea).** State the idea's ONE core mechanism in a single sentence, then try to break the idea into independent contributions. If it decomposes into "improvement A + improvement B" (e.g. `technique X` *plus* `apply it to domain Y`), explicitly diagnose the decomposition and try to reforge it around one insight so the second component becomes a consequence or falsification test rather than a bolt-on module. (E.g. "defense A + also works on audio" is a mashup; "harmful intent lives on one modality-invariant axis, so the same conditional defense transfers to audio *for free* — and if it needs a separate audio module, the core claim is false" is one mechanism whose audio result tests the claim.) An unresolved A+B candidate is **capped at `differentiable`, never `novel`**, and ranked below true single-mechanism ideas, but the diagnosis alone does not automatically remove it from the researcher's decision slate when it retains a concrete difference and an actionable reforge path. This is not a licence to invent a grand unifying theory over a genuinely engineering idea.
2b. **Scope-necessity test (EVERY idea).** For each domain, modality, structure,
scale, temporal/deployment setting, or population foregrounded in the title or claim,
test removal, adjacent-scope replacement, and one scope-unique prediction. Classify it
`ESSENTIAL`, `EVALUATION_SCOPE_ONLY`, `APPLICATION_SWAP`, or `[UNVERIFIED]`.
Relabel evaluation-only scope, move application swaps to **Needs reforge**, and keep an
unverified scope selectable only with a concrete falsifier for `$expplan`; a failed
falsifier narrows/relabels the claim.
Encode each selectable card with matching `data-scope-necessity`, `data-scope-action`, and, when unverified, `data-scope-falsifier`; run `python3 research_avatar/tools/validate_ideagen_report.py reports/02_IDEA_REPORT.html` before the pick gate.
2c. If the ethics triage flagged the idea, include **Ethics risk** in the qualitative record and keep it separate from the technical `risk` field. The rightmost table cell and the card's detailed assessment must agree exactly on the level. Do not silently downgrade a risk to improve ranking.
3. **Same-model devil's-advocate ranking:** in a clearly separated second pass, review the full set using the same model. For each idea state the strongest objection, likely failure mode, whether it passes 2a or remains an A+B mashup, its 2b scope-necessity classification and falsifier, whether the novelty evidence shows a collision or a defensible difference, and whether that difference can support a contribution. Rank qualitatively by this review, feasibility, risk, and research value—not by a numeric or weighted score—and write the objections out; never skip the pass. This pass diagnoses and ranks; an objection is not by itself an exclusion rule.
4. **Build a tiered decision slate.** Exclude `already exists` and `[UNVERIFIED]` from pick options. Tier A contains `novel` recommendations; Tier B contains selectable `differentiable` candidates with a concrete difference, viable test, and reforge path. Tier B is never a default recommendation—even when Tier A is empty—and must be explicitly chosen as incremental/framing work. Move absorbable application swaps, unresolved mashups, and weak differences to **Needs reforge — not selectable**. If no Tier A survives, state **no high-confidence novel recommendation**; never promote Tier B to fill rank 1.


For the disruptive pool, rank separately per **D5** in `references/disruptive-branch.md` (two-stage novelty-incubation → reality-reentry; visible **Disruptive score** = arithmetic mean of Paradigm break · Evidence plausibility · Falsifiability · Leverage/option value; feasibility risk only as tie-breaker; vague/cross-domain/expensive never earns points). Select exactly the highest-scoring eligible survivor as `D1`; do not expose lower-scoring survivors as extra cards.
