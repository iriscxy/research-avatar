## A3 — Render the HTML deliverable
Write ONE **self-contained** HTML file to the `— out:` path (default
`reports/01_LIT_SURVEY.html`) — inline `<style>`, no external assets. **Address the researcher in the second person**
where the text speaks to her. **Every paper is a direct `<a href>`** to its
official venue or DOI page when published, with its arXiv URL retained as a
secondary preprint link; arXiv is the primary link only for arXiv-only
preprints. Unverifiable → visible `pending`/`[UNVERIFIED]` label, never a
fabricated URL.

**House style (match `reports/01_LIT_SURVEY.html` exactly — it is the canonical
example; open it and reuse its `<style>` block verbatim):**
- **White background** (`--bg:#ffffff`, `body{background:#ffffff}`). Non-negotiable.
- **Hero header**: kicker · gradient `<h1>` title · subtitle ·
  meta pills (date · coverage years · sources · N papers).
- **Sticky `nav.toc`** linking the four fixed stages: Problem, Approaches,
  Evaluation, and Gaps.
- **Numbered `<h2>`** headings.
- **`.lead`** intro box; **`.flow`** taxonomy diagram (nodes + `→` arrows).
- **`.grid` of `.card`s** inside named method/evaluation families — each paper card: colored `.tag` · `✅ Verified` mark ·
  `<h4><a>` title · `.who` (authors · formal venue · publication year · DOI when
  available · official venue/DOI link · arXiv preprint link) · one-line takeaway.
  Show publication information only when cross-checked, for example
  `ICLR 2025` / `Nature 2024`; use `arXiv preprint` only for papers without a
  verified formal publication record.
- **`.callout`** for intuitions; **`.callout.debate`** for live disagreements;
  **`.callout.gap`** for structural gaps.
- **Landscape `<table>`** with columns for work, category, core idea,
  year, and verification, plus a verification note below it.
- **Trends and gaps** section: `ul.trend` list +
  a `.callout.gap` of the openings.
- **Footer**: generated-by line + "Verify the original sources before citing."

Keep the tag colors meaningful (base `.tag`, `.tag.b` architecture, `.tag.w`
safety, `.tag.p` steering/control, `.tag.v` debate) and mark every verified paper
with a "Verified" chip.
For published papers, make the card title and reference link point to the
cross-checked publisher / DOI / official venue page, display the formal venue,
publication year, and DOI when available, and retain the arXiv link as a
secondary `preprint` link. For preprints, link directly to arXiv and label them
`arXiv preprint`. Never replace a verified accessible arXiv link with a guessed
publisher URL.

### Explicit target-language translation — LLM API only

The canonical Survey is English. Translate it **only** when the researcher
explicitly requests a target language (for example, `用中文`, `translate to
Spanish`, or `— language: Japanese`). The language of the surrounding chat is
not, by itself, a translation request.

After the evidence-locked English HTML is complete, first run the fixed report
structure validator. Copy the complete validated English render to the
disposable staging path used by the translation stage, then run:

```bash
python3 research_avatar/tools/translate_report_html.py reports/.build/01_LIT_SURVEY.html \
  --target-language "<requested language>" \
  --provider "<openai-or-deepseek-chosen-by-researcher>"
```

Provider setup:

- `openai`: `OPENAI_API_KEY`; optional `OPENAI_BASE_URL` and
  `RESEARCHLIT_TRANSLATION_MODEL` (default `gpt-4o-mini`); uses Responses API.
- `deepseek`: `DEEPSEEK_API_KEY`; optional `DEEPSEEK_BASE_URL` and
  `DEEPSEEK_TRANSLATION_MODEL` (default `deepseek-v4-flash`); uses DeepSeek's
  OpenAI-compatible Chat Completions API.

Before this terminal API step, ask the researcher to choose OpenAI or DeepSeek
unless the current invocation already specifies one. Then check only that
provider's key and show its exact local `export` command when missing.

The selected provider must translate visible explanatory and interface text
inside that staging file,
preserve paper titles, links, authors, venue metadata, numbers, IDs, acronyms,
and claim strength, and embed a complete
`researchlit-llm-translation` receipt. The Code Agent remains responsible for
search, source verification, synthesis, HTML structure, and validation; it must
not translate the Survey itself.

After translation, validate the complete staging report and receipt, then
atomically replace `reports/01_LIT_SURVEY.html`. Never run the translator on the
delivered canonical file. If translation was explicitly requested but the selected provider's key or
required configuration is absent, show the exact local `export` commands and
stop. An API error, protected-token change, partial coverage, or missing receipt
is also a hard stop. Never silently switch providers, retain the English file,
translate with the Code Agent, or claim that translation succeeded. If no target
language was explicitly requested, do not call any translation API and do not
add a translation receipt.

## A4 — Report + optional handoff
Tell the researcher: the output path, how many papers/angles, the key debates and
gaps found (2–4 bullets). Do **not** invent a "verdict" on the field.
- If `— for: ideagen` was passed, also emit the compact landscape (prose + gap
  list) for `$ideagen`'s A1 to consume.
- Otherwise this is a standalone deliverable; suggest `$ideagen` as the natural
  next step if the researcher wants ideas grounded on it.

## Non-negotiables (inherited from the project's global disciplines)
1. **Anti-hallucination.** Only cite papers actually retrieved with a verified id
   and publication metadata cross-checked against a relevant authoritative source;
   `[UNVERIFIED]` for anything else; never fabricate ids/DOIs/URLs. Drop, don't invent.
2. **Self-contained HTML, never Markdown**, with real structure and direct links.
3. **Readable, idiomatic prose** written TO the researcher in the second person;
   re-read each sentence for clarity. Explicit target-language requests must use
   the LLM API translation stage above, never Code Agent translation.
4. **White background**, house style, one `reports/` folder.
5. **Human is the reader, not judged** — a survey maps the field; it does not
   accept/reject ideas (that's `$ideagen`'s gate).

## Fixed HTML structure

Render `01_LIT_SURVEY.html` with one unnumbered hero, one sticky contents bar, and exactly these ordered top-level sections (`<section data-report-section>` and visible `<h2>` text must agree):

1. `1. Problem` (`problem`): scope, stakes, taxonomy of the phenomenon, and
   the assumptions or disagreements that define the question;
2. `2. Approaches` (`approaches`): define 3–7 method families by the decision
   they make or mechanism they use; for every family state its inclusion rule,
   shared mechanism, trade-off, and representative verified papers, then
   compare papers within the family;
3. `3. Evaluation` (`evaluation`): classify work by evaluation regime—dataset
   realism, perturbation or shift source, metric/uncertainty contract, and
   compute or efficiency accounting. Group studies under shared regimes and
   explain comparability limits instead of presenting one flat paper table;
4. `4. Gaps` (`gaps`): live debates, recent trends, structural gaps, and
   research openings that follow from the preceding evidence.

Every stage must contain substantive topic-specific synthesis and direct source
links. A gap must identify missing or conflicting evidence relative to a stated
problem and evaluation regime; “few papers exist” alone is not a structural
gap. Do not render a standalone `Verified Sources`, `Verified References`, or
duplicated bibliography section: papers are already cited and linked where they
are synthesized in the body. The sticky contents links to these exact section IDs in this exact order.
Do not add, rename, reorder, or omit a top-level section; workflow logs, agent
traces, approval controls, tool comparisons, and arbitrary appendices are
forbidden. Run `python3 research_avatar/tools/validate_report_structure.py
--kind literature --html reports/01_LIT_SURVEY.html` on the completed canonical
English file: immediately before the API translation step when one was
explicitly requested, otherwise immediately before returning. The translation
script preserves HTML tags and attributes while translating visible text and
must finish with its verified receipt. The Live Demo must display this exact
section list and filled illustrative content from the same slots.
