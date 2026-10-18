---
name: "researchlit"
description: "Create a verified, multi-angle literature survey and a polished self-contained HTML field map. Use for standalone literature reviews or the grounding survey consumed by `$ideagen`; only cite papers actually retrieved and verified. Invoke explicitly as `$researchlit`."
---

# Research Literature Survey

Run once per project session:

```bash
python3 -m research_avatar.research_studio.server --ensure
```

Default output: `reports/01_LIT_SURVEY.html`.

The merged verified paper records and synthesis model at
`reports/.build/01_LIT_SURVEY.source.json` are authoritative;
`01_LIT_SURVEY.html` is rendered output. Create or update that structured source,
then render it with:

```bash
python3 research_avatar/tools/render_literature_report.py \
  --source reports/.build/01_LIT_SURVEY.source.json \
  --output reports/01_LIT_SURVEY.html
```

The renderer derives paper cards, family membership, and all visible counts
from the same records and refuses invalid output before atomic replacement.
Never handwrite those elements in the delivered HTML. A correction or translation must build
the complete report at a temporary path, validate all four stages and protected
metadata, then atomically replace the canonical file. Never migrate, translate,
or repair the delivered HTML through local DOM/string edits.

Arguments may specify topic, output path, 4–6 search angles, `— for: ideagen`,
`— questions: personalized`, and an explicit target language/provider. If the
topic is missing, propose 2–3 broad directions derived from the profile's
Research Identity and Research Lineage (for example, “activation steering”) and
let the researcher pick one, or ask for a topic. The profile only chooses the
broad direction. Angles, searches, synthesis, and gaps stay field-neutral, so a
personalized and a non-personalized run share the same survey.

## Verified search

Decompose the topic into distinct angles and search them in parallel to
saturation. A useful broad survey commonly contains 30–60 papers, but coverage
quality—not count—is the criterion.

For every paper retrieve and verify title, the complete author list (never "First Author et al."; the paper stage can cite only works with full authors), arXiv ID or DOI, year, takeaway,
formal publication status, venue, and authoritative URL. Cross-check relevant
official sources such as ACL Anthology, OpenReview, DBLP, publisher/venue pages,
and DOI records. Use arXiv as a preprint fallback. Never infer missing metadata;
mark uncertainty `[UNVERIFIED]` or omit the lead.

Keep one canonical verified-paper record per work with the fetched final URL,
page title, stable identifier, and verification date. Render every link and all
paper/family counts from these records; never type a count separately in prose.
Before delivery, reopen every rendered paper URL and reject redirects to an
unrelated work, title/identifier mismatches, placeholder hosts, and dead links.
Record 4–6 structured search angles, each angle's normal and current/previous-
year queries, and the gap-falsification queries in the canonical source. Embed those canonical records once as `literature-verification` JSON. Render
paper cards and families with matching `data-paper-id` and `data-family-id`;
derive the visible counts from the arrays.

Merge by stable ID or normalized title, preserve disagreements, and synthesize
5–7 themes, live debates, recent trends, and structural gaps. Prefer verified
published evidence where comparable while retaining materially new preprints.

For every method family, record one concrete `failure_boundary`: an input,
transition, deployment condition, or evaluation regime under which the
family's shared design may cease to support its intended claim. This is an
evidence-bounded synthesis, not an invented failure result. Cite the papers
that motivate the boundary and mark uncertainty when it has not been tested.
IdeaGen consumes these boundaries together with Gaps and Live Debates.

Render an evidence-maturity summary derived from the paper records, never from
typed prose counts. Separate established peer-reviewed evidence, current
peer-reviewed evidence, and current/previous-year frontier preprints. A survey
with recent papers but no visible distinction between verified publication and
frontier preprint evidence is incomplete.

Every angle includes a separately recorded current/previous-year recency lane.
Before describing a gap, run mechanism-level counterevidence queries whose
purpose is to falsify that gap. Search-family breadth must not dilute
recent-work coverage.

Read
[`references/search-and-synthesis.md`](references/search-and-synthesis.md)
before decomposing queries, delegating searches, merging records, or writing the
landscape synthesis.

## HTML deliverable

Write one self-contained, white-background HTML survey with direct verified
links and exactly four reader-facing stages: **Problem → Approaches →
Evaluation → Research Questions**. This sequence is the handoff contract for downstream idea
generation and experiment planning: define the problem before cataloging
methods, compare evaluation protocols before inferring gaps, and keep gaps
separate from mere absence of papers. Keep the format plain and uniform: a one-paragraph Problem, collapsible
Approaches and Evaluation families with nested sub-categories, and a short bullet
list of research questions. No cards, tags, callouts, flow diagrams, or landscape table. Use
the renderer's built-in stylesheet; never restyle.

`Approaches` and `Evaluation` are synthesis taxonomies, not bibliographies.
Group papers into a small number of explicit, decision-relevant families, each
split into 2–5 finer sub-categories (`families[].subfamilies`,
`evaluation_regimes[].subregimes`) that together cover each paper exactly once.
Write `problem.paragraph` as one paragraph and `directions` (the research questions) as 3–5 entries in the
structured source; the renderer rejects anything else. Compare work within each family. A sequence of one-paper cards or table rows
without category definitions, inclusion criteria, and cross-paper comparison
does not satisfy the deliverable.

Read
[`references/html-and-translation.md`](references/html-and-translation.md)
while rendering the report, translating it, or preparing the handoff. It
contains the complete visual contract, fixed section structure, publication
metadata rules, and translation failure conditions.

## Research questions

The last section lists 3–5 research questions, the broad problems the field
leaves open, each written as a short keyword title rather than a sentence. Store
them as `directions`: `[{"id": "Q<k>", "title": "..."}]`. `title` is the only
visible field: a short keyword phrase of at most six words that names the
problem area, for example `Steering reliability` or `Multi-behavior steering`;
not a question or a sentence, and with no explanation after it.

A research question here names a broad problem area, not a project and not a
pipeline stage or technical step (for example not `Context selection`,
`Retrieval` or `Vector construction`): a step names where the answer lies and
leaves room for one obvious idea. The questions must be mutually distinct: no two
share the same central tension or could be answered by the same study. Do not name methods,
theories, systems to compare, experimental designs, datasets, metrics, or
expected results, and do not attach closest work or gap evidence: the
questions sit on top of the survey's synthesis, and `$ideagen` reads the whole
survey when it generates ideas for the chosen question.
Choose questions that are clearly distinct from one another and that the
survey evidence (families, failure boundaries, live debates, trends) supports.
These neutral questions never read the profile.

With `— questions: personalized`, also write `personalized_directions`: 2–4
`{"id": "PQ<k>", "title", "anchor"}` entries drawn from the same
evidence plus the profile's Research Identity, Research Lineage, and the
researcher's past `research_question` values from the Idea pairs in
`researcher-profile/profile_pairs.json`. `anchor` names the past paper or
lineage turn the question continues. They are labeled separately and never
replace the neutral questions.

The researcher chooses one question at the start of `$ideagen`; this skill does
not ask for the pick.

## Translation

To translate into a target language, require
`provider: openai|deepseek`, then run:

```bash
python3 research_avatar/tools/translate_report_html.py reports/01_LIT_SURVEY.html --target-language "<language>" --provider "<provider>"
```

The selected LLM API translates visible text and must produce a complete
`researchlit-llm-translation` receipt while preserving titles, authors, links,
venues, numbers, IDs, acronyms, and claim strength. The Code Agent must not
translate the Survey itself. Missing key, API error, protected-token change,
partial coverage, or missing receipt is a hard stop; never switch providers or
claim success. Translation is resumable: retain the generated checkpoint under
`reports/.build/`, rerun the same command after an interruption, and reuse only
nodes whose normalized source meaning, protected metadata, provider, model, and
glossary identity still match. Use the built-in academic glossary or pass a
project JSON glossary with `--glossary`; never repair a partial translation by
editing rendered DOM nodes. The translator writes each checkpoint batch and the
completed HTML atomically, so the validated English staging file remains intact
on failure.

## Validation and handoff

Run on the completed canonical English survey, before translation if one is run
and otherwise before returning:

```bash
python3 research_avatar/tools/validate_literature_report.py reports/01_LIT_SURVEY.html
python3 research_avatar/tools/validate_report_structure.py --kind literature --html reports/01_LIT_SURVEY.html
```

Report the output path, paper/angle counts, and 2–4 key debates or gaps, and
list the research questions by ID. With `— for: ideagen`, also return a compact
landscape/gap summary for `$ideagen`; otherwise leave the survey standalone and
optionally suggest ideation as the next step.
