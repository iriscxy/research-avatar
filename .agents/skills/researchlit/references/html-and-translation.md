## A3 — Render the HTML deliverable
Build the complete evidence and synthesis model in
`reports/.build/01_LIT_SURVEY.source.json`, then use
`research_avatar/tools/render_literature_report.py` to write ONE
**self-contained** HTML file to the `— out:` path (default
`reports/01_LIT_SURVEY.html`) — inline `<style>`, no external assets. Do not
hand-edit rendered paper cards, family blocks, or counts. **Address the researcher in the second person**
where the text speaks to her. **Every paper is a direct `<a href>`** to its
official venue or DOI page when published, with its arXiv URL retained as a
secondary preprint link; arXiv is the primary link only for arXiv-only
preprints. Unverifiable → visible `pending`/`[UNVERIFIED]` label, never a
fabricated URL.

**House style — plain and uniform (the renderer's built-in stylesheet is
authoritative; never restyle).** No gradients, pills, cards, tags, callouts,
flow diagrams, or decorative marks.
- **Warm paper background** (`#f5f3ec`) with white `details` blocks, one sans-serif font, and the same teal/orange palette as `PROFILE.html`: teal for `h1`, `h2` rules, links, and family titles, orange for counts and list markers. Color accents only; still no gradients, pills, or cards.
- **Header**: plain `<h1>` title and one meta line (date · coverage years ·
  N papers · N search angles). No hero, kicker, subtitle, or badges.
- **Sticky-free `nav.toc`** with four plain links: Problem, Approaches,
  Evaluation, Research Questions.
- **Numbered `<h2>`** headings, one per stage, in the same plain style.
- **Problem** is a single paragraph, nothing else.
- **Approaches** and **Evaluation** use the same dropdown pattern: each
  top-level family/regime is a `<details>` that opens to a one-sentence
  definition and finer sub-categories, and each sub-category is a nested
  `<details>` listing its papers. Approaches papers are plain list items:
  linked title, `(venue year)`, and a one-line takeaway. Evaluation lists only
  linked titles. No paper cards, landscape table, or per-paper tags.
- **Research Questions** is a short plain bullet list of 3–5 research questions (`Q1`…`Q5`), each a short keyword title only, with no explanation, closest work, evidence, callouts or sub-headings.
- **Footer**: generated-by line + "Verify the original sources before citing."

Every paper is a direct link: the cross-checked venue/DOI page when published
(with its arXiv URL kept as a secondary `arXiv` link), and arXiv itself only for
arXiv-only preprints. Never replace a verified accessible arXiv link with a
guessed publisher URL. Show a venue only when cross-checked; use `arXiv
preprint` only for papers without a verified formal publication record.

The structured source must contain 4–6 search angles with ordinary and recency
query lanes, plus the explicit counterevidence queries used for gap
falsification. These fields are
part of the embedded evidence contract and are validated before delivery.

### Target-language translation — LLM API only

The canonical Survey is English. A target language is given, for example, as `translate to Chinese`, `translate to
Spanish`, or `— language: Japanese`.

After the evidence-locked English HTML is complete, first run the fixed report
structure validator. Copy the complete validated English render to the
disposable staging path used by the translation stage, then run:

```bash
python3 research_avatar/tools/translate_report_html.py reports/.build/01_LIT_SURVEY.html \
  --target-language "<requested language>" \
  --provider "<openai-or-deepseek-chosen-by-researcher>" \
  --checkpoint reports/.build/01_LIT_SURVEY.translation.json
```

The translator persists each completed batch. If the API or terminal process is
interrupted, rerun the identical command: translations are reused by normalized
semantic node identity, not by raw DOM position or byte hash, so whitespace and
unrelated markup changes do not discard valid work. Provider, model, target
language, protected metadata, or glossary changes invalidate only the affected
reuse contract. The built-in academic glossary is fixed for Chinese; add a
project-specific JSON string-to-string glossary with `--glossary <path>` when
the field needs additional canonical terminology.

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

The translator updates checkpoints and the completed staging HTML atomically.
After translation, validate the complete staging report and receipt, then
atomically replace `reports/01_LIT_SURVEY.html`. Never run the translator on the
delivered canonical file. If the selected provider's key or
required configuration is absent, show the exact local `export` commands and
stop. An API error, protected-token change, partial coverage, or missing receipt
is also a hard stop: keep the checkpoint for retry and leave the validated
English staging file intact. Never silently switch providers, retain the English file,
translate with the Code Agent, or claim that translation succeeded.

## A4 — Report + optional handoff
Tell the researcher: the output path, how many papers/angles, the key debates and
gaps found (2–4 bullets). Do **not** invent a "verdict" on the field.
- If `— for: ideagen` was passed, also emit the compact landscape (prose + gap
  list + research questions by ID) for `$ideagen`'s A1 to consume.
- Otherwise this is a standalone deliverable; suggest `$ideagen` as the natural
  next step if the researcher wants ideas grounded on it.

## Non-negotiables (inherited from the project's global disciplines)
1. **Anti-hallucination.** Only cite papers actually retrieved with a verified id
   and publication metadata cross-checked against a relevant authoritative source;
   `[UNVERIFIED]` for anything else; never fabricate ids/DOIs/URLs. Drop, don't invent.
2. **Self-contained HTML, never Markdown**, with real structure and direct links.
3. **Readable, idiomatic prose** written TO the researcher in the second person;
   re-read each sentence for clarity. Target-language translations must use
   the LLM API translation stage above, never Code Agent translation.
4. **White background**, house style, one `reports/` folder.
5. **Human is the reader, not judged** — a survey maps the field; it does not
   accept/reject ideas (that's `$ideagen`'s gate).

## Fixed HTML structure

Render `01_LIT_SURVEY.html` with one unnumbered hero, one sticky contents bar, and exactly these ordered top-level sections (`<section data-report-section>` and visible `<h2>` text must agree):

1. `1. Problem` (`problem`): **one plain paragraph** covering scope, stakes,
   and the assumptions or disagreements that define the question. No lists,
   callouts, diagrams, or sub-headings;
2. `2. Approaches` (`approaches`): define 3–7 method families by the decision
   they make or mechanism they use. Each family is a collapsible dropdown with a
   one-sentence inclusion rule, a failure boundary, and **2–4 finer
   sub-categories** (`subfamilies`, each a nested dropdown with its papers).
   Every paper belongs to exactly one sub-category;
3. `3. Evaluation` (`evaluation`): classify work by evaluation regime, such as
   dataset realism, perturbation or shift source, metric/uncertainty contract,
   and compute accounting. Use the same dropdown structure as Approaches, with
   2–4 sub-categories per regime (`subregimes`), and state comparability limits
   in the one-sentence definition. No flat paper table;
4. `4. Research Questions` (`gaps`): **a short bullet list** of 3–5 research
   questions, each a keyword title only. Personalized questions,
   when requested, follow as one labeled bullet.

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
English file: immediately before the API translation step when one is
run, otherwise immediately before returning. The translation
script preserves HTML tags and attributes while translating visible text and
must finish with its verified receipt. The Live Demo must display this exact
section list and filled illustrative content from the same slots.
