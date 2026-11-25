# Venue and reference gates

Read this file only while confirming the target venue and the single reference paper.

## Venue

Ask the researcher directly which conference this project will target, then stop.

## One researcher-owned reference

After venue confirmation, inspect viable papers authored by the researcher. Rank them by argumentative similarity: contribution type, section progression, experiment organization, paragraph transitions, and figure/table rhythm. Venue compatibility is a constraint and tie-breaker; topic keyword overlap is not the primary score.

Show one proposal with title, verified authorship, venue/year, direct link, local full-text path/status, and a plain-language explanation. Ask for `confirm reference` and stop. Changing the idea or venue requires reconfirmation.

Accept a local transcript only when its `publications.json` record sets
`fulltext_extractor` to `code_agent`. Otherwise return to `/profileconstruct`;
do not derive structural paragraphs from `pdftotext`, OCR, a separate LLM API,
or an unverified legacy TXT. If no owned full text is available, stop and report
what is missing rather than substituting an external or synthetic paper.

After confirmation, the executing Code Agent analyzes the complete verified
transcript and current scientific obligations in one coherent pass. Return:

- every complete natural paragraph with a stable source ID, heading,
  rhetorical purpose, neighbor relations, and any figure or table it introduces
  or interprets;
- the target paper's section order and paragraph count;
- one concrete planning sentence, rhetorical role, and neighbor relation for
  every target paragraph;
- each target paragraph's mapping to the most relevant source paragraph or
  paragraphs, including complete source text and an adaptation note that names
  the logical move being imitated.

Paragraph counts need not match. Mapping is rhetorical rather than sequential:
never assign paragraphs by cursor position or round-robin order. A source
paragraph may guide several targets, and several source paragraphs may guide a
compressed target, but every target needs a non-empty mapping. Imitate only
argumentative moves and transition logic; do not copy the reference paper's
claims, methods, results, or wording.

Reject source records that begin or end mid-sentence, contain page/column
fragments, or combine columns in the wrong order. Persist the complete one-shot
analysis in `structure_reference_analysis` and its target mappings in
`paper_outline`; do not create a separate paper-plan file.

Broader literature still grounds the science, baselines, datasets, and metrics,
but does not become a second structural reference.

Before baseline design, retrieve the experiment setup and result tables of the 2–4 closest scientific papers. Extract actual baselines, datasets, metrics, and reusable variables. Mark unavailable papers `[UNVERIFIED]`; never fill gaps from memory. For every introduced variable, record whether it is directly reused, adapted, or proposed.
