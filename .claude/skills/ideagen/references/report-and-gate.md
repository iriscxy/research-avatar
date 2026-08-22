## Output conventions
- **One folder `reports/` (create it), two-digit step prefixes.** The survey `reports/01_LIT_SURVEY.html` is written by `/researchlit` (the grounding this skill reads). This skill writes the single canonical `reports/02_IDEA_REPORT.html` (a **short** landscape pointer to the survey + the ranked ideas — NOT a duplicated paper appendix); when `— ref paper:` is given, the reference-paper reading is folded in as a short "Reference Paper Notes" box at the top of `02` (A0), NOT a separate file. Downstream continues as `03_EXPERIMENT_PLAN.html` → `04_RUN_PLAN.html` → `05_EXP_RESULT.html`.
- **Every deliverable is self-contained HTML, never Markdown** — inline `<style>`, no external assets, real structure (`<h1>/<h2>`, `<table>`, `<ul>`). **Every paper reference is a direct `<a href>`** to its arXiv/DOI; unverifiable → visible `pending`, never a fabricated URL.
- The single file `reports/02_IDEA_REPORT.html` is the **primary** — it is what
  `/expplan` reads, and the renderer serializes the structured selection record
  in it. Address the researcher directly, never in the third person.

### Mandatory LLM API readability rewrite — every visible explanatory sentence

The first complete HTML draft is **not** the deliverable. Generate it at a
disposable staging path. After A5 has fixed the
scientific content, novelty verdicts, links, attributes, machine audit, and pick
state, ask the researcher to choose OpenAI or DeepSeek unless the current
invocation already specifies one. Then pass every eligible visible explanatory
text node through that LLM API by running:

```bash
python3 research_avatar/tools/rewrite_ideagen_html.py \
  reports/.build/02_IDEA_REPORT.html \
  --provider "<openai-or-deepseek-chosen-by-researcher>" \
  --model "<researcher-specified-model-if-any>"
```

Omit `--model` when the researcher did not specify one. OpenAI reads
`OPENAI_API_KEY` and optionally `OPENAI_BASE_URL` / `IDEAGEN_REWRITE_MODEL`;
DeepSeek reads `DEEPSEEK_API_KEY` and optionally `DEEPSEEK_BASE_URL` /
`DEEPSEEK_IDEAGEN_REWRITE_MODEL`. Show the exact local `export` command for the
selected provider when its key is missing. Never infer the provider from which
key happens to be present, inspect the other provider's key, or silently switch.

This is a hard generation stage, not an optional polish pass and not a request
to the current agent to paraphrase from memory. The script must receive the
selected provider's real API key, make successful API calls, rewrite the prose
inside the disposable staging file for an adjacent-area researcher, and embed
one hidden `ideagen-readable-rewrite` JSON
receipt containing the provider, model, API response IDs, eligible/rewritten
node counts, and output digests. **No API key, API error, malformed response,
partial node coverage, or missing receipt is a hard stop. Never silently keep
the pre-rewrite draft and call it readable.**

Rewrite all natural-language statements in `<p>`, `<li>`, `<dd>`, and prose
table cells, including landscape summaries, ranked-idea explanations, card
arguments, novelty comparisons, objections, falsifiers, feasibility notes, and
pick instructions. The rewrite must make the actor, action, comparison, and
observable consequence explicit; split overloaded sentences; explain a
necessary technical term at first use; remove noun piles and opaque shorthand;
and preserve uncertainty rather than making the claim sound stronger.

Do **not** rewrite fixed section headings, idea IDs, paper/method/model/dataset
names, direct-link anchor text, numeric values, novelty labels, machine JSON,
CSS/JavaScript, `<code>/<pre>` content, or HTML attributes. The API may improve
wording only: it may not add evidence, remove a falsifier, change a novelty or
scope verdict, alter a citation, or convert a conditional claim into a result.
Validate the complete rewritten staging report, then atomically replace
`reports/02_IDEA_REPORT.html`. The pre-rewrite draft remains internal; only the
validated API-rewritten HTML is shown to the researcher.

After the rewrite, run all ordinary validators **and**:

```bash
python3 research_avatar/tools/validate_ideagen_readability.py reports/02_IDEA_REPORT.html
```

If any source change affects visible prose, regenerate the staging report and
rerun the selected LLM API rewrite so the receipt covers the final delivered
wording. Selection rendering is exempt only for the fixed
`Selected: I<k> — <title>` banner and row tag; changing any idea explanation
requires a fresh API pass.

## GATE — human is judge

Never create a second report for the disruptive pass. Set `data-idea-branch="standard"` and `data-disruptive-wildcard="present|shortfall|off"` on `<main>`. Mark every standard card with `data-idea-id="I<k>"`.

- With wildcard `on`, append a **Disruptive wildcard** section after all standard idea cards. If an eligible survivor exists, show exactly one `<article data-disruptive-id="D1">`, its Disruptive score, and every field required by `references/disruptive-branch.md`.
- If no disruptive seed survives, set `data-disruptive-wildcard="shortfall"` and show the compact failed-gate audit in that same position; do not invent `D1`.
- Keep the standard ranking table unchanged. Do not insert D1 as rank 8 and do not compare its Disruptive score to standard Novelty / qualitative ranks.
- When the wildcard is on, run `python3 research_avatar/tools/validate_ideagen_wildcard.py reports/02_IDEA_REPORT.html` and fix all errors before presenting it. Ask the researcher to pick / kill / redirect by id (`I*` or `D1`). Never auto-proceed.

Present a **4–6 idea decision slate when evidence supports it**; fewer is valid after the second generation pass. Use `ID | Tier | Idea | Novelty status | Scope necessity | Closest work | Concrete difference | Strongest objection | Confidence` (plus conditional ethics risk). Each selectable card carries `data-idea-id`, `data-novelty-status`, `data-idea-tier`, `data-default-pick`, and the scope attributes from 2b. Only Tier A may be default; Tier B says `needs framing`; at most one card is default. Before the gate, give a fresh-context reviewer only the cards and retrieved sources; embed its per-ID verdict, absorbability result, closest-work overlap/difference, ISO latest-search date, fresh-context run ID, and ≥2 non-placeholder direct URLs as `idea-novelty-audit` JSON. The card and audit must agree. Non-selectable survivors have no pick ID. Run the mandatory LLM API readability rewrite, then `research_avatar/tools/validate_ideagen_report.py`, `research_avatar/tools/validate_ideagen_readability.py`, and the fixed-structure validator; only the API-rewritten final HTML may be presented. Then stop for pick/kill/redirect.

**Selection never hides or compacts ideas.** Every idea shown in the ranked
decision slate must keep its complete Candidate Card after a selection is
recorded, including the full summary, novelty evidence, mechanism, falsifier,
scope necessity, feasibility, strongest objection, and ethics assessment.
Choosing one ID may add only the selected banner/row/card marker and downstream
selection state. It must not remove another card, replace it with a one-line
`not selected`/`rejected` block, collapse its fields, or filter it from the
rendered page. Rejected and non-selectable ideas remain fully readable for
comparison; only their selection controls are disabled.


If any ethics risk is `HIGH` or `CRITICAL`, the gate must state that the candidate requires explicit human ethics review before implementation, data collection, deployment, or release, as applicable. Ask only the concrete review question needed for the flagged pathway; do not show an ethics prompt for unflagged work. For `LOW` or `MEDIUM`, show the risk and safeguards in the report and let the normal idea-selection gate handle the decision.

**Persist the pick:** after she picks, save the selected ID in structured
selection state and run the complete report renderer again. The regenerated
`reports/02_IDEA_REPORT.html` contains a top banner
`Selected: I<k> — <title>` (with date) and a `? SELECTED` tag on that row.
Never insert or replace those fragments in the delivered HTML. If she redirects
instead, regenerate from updated selection state and leave no stale selection.

**Handoff:** the chosen idea → **`/expplan`**, which reads the validated
selection state rendered in the report and writes
`reports/03_EXPERIMENT_PLAN.html`. Do not write the experiment plan here.

## Fixed HTML structure

Render `02_IDEA_REPORT.html` with an unnumbered selected-status banner when applicable, an optional unnumbered `Reference Paper Notes` box, and exactly these ordered top-level sections (`<section data-report-section>` and visible `<h2>` text must agree):

1. `1. Literature Landscape` (`literature-landscape`);
2. `2. Ranked Decision Slate` (`ranked-slate`);
3. `3. Candidate Cards` (`candidate-cards`);
4. `4. Human Selection` (`human-selection`).

Place any opt-in `Disruptive Wildcard` inside `Candidate Cards`; it is not a fifth top-level section. Each candidate card owns its plain-language summary, novelty evidence, one mechanism, falsifier, scope necessity, feasibility, strongest objection, and conditional ethics assessment. Every top-level title must own substantive topic-specific content; an empty section, title-only slot, or placeholder-only body is invalid. Keep audits as hidden JSON, not visible sections. Do not add, rename, reorder, or omit a top-level section; workflow logs, dashboards, and tool comparisons are forbidden. Before the pick gate, run `python3 research_avatar/tools/validate_report_structure.py --kind ideas --html reports/02_IDEA_REPORT.html` in addition to the idea-specific validators. Research Studio adds selection controls around this report; the Live Demo must display this exact section list with filled illustrative candidates.
