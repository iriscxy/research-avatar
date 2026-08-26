---
name: "researchlit"
description: "Create a verified, multi-angle literature survey and a polished self-contained HTML field map. Use for standalone literature reviews or the grounding survey consumed by `/ideagen`; only cite papers actually retrieved and verified. Invoke explicitly as `/researchlit`."
---

# Research Literature Survey

Run once per project session:

```bash
python3 -m research_avatar.research_studio.server --ensure
```

Default output: `reports/01_LIT_SURVEY.html`.

The merged verified paper records and synthesis model are authoritative;
`01_LIT_SURVEY.html` is rendered output. A correction or translation must build
the complete report at a temporary path, validate all four stages and protected
metadata, then atomically replace the canonical file. Never migrate, translate,
or repair the delivered HTML through local DOM/string edits.

Arguments may specify topic, output path, 4–6 search angles, `— for: ideagen`,
and an explicit target language/provider. If the topic is missing, ask for it
or offer profile niche subfields. Profile personalization is optional and may
bias angle selection, but the survey remains a field-neutral map.

## Verified search

Decompose the topic into distinct angles and search them in parallel to
saturation. A useful broad survey commonly contains 30–60 papers, but coverage
quality—not count—is the criterion.

For every paper retrieve and verify title, arXiv ID or DOI, year, takeaway,
formal publication status, venue, and authoritative URL. Cross-check relevant
official sources such as ACL Anthology, OpenReview, DBLP, publisher/venue pages,
and DOI records. Use arXiv as a preprint fallback. Never infer missing metadata;
mark uncertainty `[UNVERIFIED]` or omit the lead.

Keep one canonical verified-paper record per work with the fetched final URL,
page title, stable identifier, and verification date. Render every link and all
paper/family counts from these records; never type a count separately in prose.
Before delivery, reopen every rendered paper URL and reject redirects to an
unrelated work, title/identifier mismatches, placeholder hosts, and dead links.
Embed those canonical records once as `literature-verification` JSON. Render
paper cards and families with matching `data-paper-id` and `data-family-id`;
derive the visible counts from the arrays.

Merge by stable ID or normalized title, preserve disagreements, and synthesize
5–7 themes, live debates, recent trends, and structural gaps. Prefer verified
published evidence where comparable while retaining materially new preprints.

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
Evaluation → Gaps**. This sequence is the handoff contract for downstream idea
generation and experiment planning: define the problem before cataloging
methods, compare evaluation protocols before inferring gaps, and keep gaps
separate from mere absence of papers. Use a hero, sticky contents, taxonomy
flow, thematic cards, landscape table, debates, and a
verification footer. Address the researcher directly where appropriate. Reuse
the existing canonical report's house-style CSS when available.

`Approaches` and `Evaluation` are synthesis taxonomies, not bibliographies.
Group papers into a small number of explicit, decision-relevant families and
compare work within each family. A sequence of one-paper cards or table rows
without category definitions, inclusion criteria, and cross-paper comparison
does not satisfy the deliverable.

Read
[`references/html-and-translation.md`](references/html-and-translation.md)
while rendering the report, translating it, or preparing the handoff. It
contains the complete visual contract, fixed section structure, publication
metadata rules, and translation failure conditions.

## Explicit translation only

Translate only when the researcher explicitly requests a target language; the
conversation language alone is not a translation request. Require
`provider: openai|deepseek`, then run:

```bash
python3 research_avatar/tools/translate_report_html.py reports/01_LIT_SURVEY.html --target-language "<language>" --provider "<provider>"
```

The selected LLM API translates visible text and must produce a complete
`researchlit-llm-translation` receipt while preserving titles, authors, links,
venues, numbers, IDs, acronyms, and claim strength. The Code Agent must not
translate the Survey itself. Missing key, API error, protected-token change,
partial coverage, or missing receipt is a hard stop; never switch providers or
claim success. When the researcher does not explicitly request translation, do
not call any translation API.

## Validation and handoff

Run on the completed canonical English survey, before translation if requested
and otherwise before returning:

```bash
python3 research_avatar/tools/validate_literature_report.py reports/01_LIT_SURVEY.html
python3 research_avatar/tools/validate_report_structure.py --kind literature --html reports/01_LIT_SURVEY.html
```

Report the output path, paper/angle counts, and 2–4 key debates or gaps. With
`— for: ideagen`, also return a compact landscape/gap summary for `/ideagen`;
otherwise leave the survey standalone and optionally suggest ideation as the
next step.
