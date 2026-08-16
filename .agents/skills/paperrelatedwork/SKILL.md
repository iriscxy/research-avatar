---
name: "paperrelatedwork"
description: "Build a thorough, well-organized related-work section by broadly searching the literature — the works the method is built on, works on the same topic, and any work that corroborates a claim — then integrating them under clear subheadings without clutter. Every arXiv ID is verified before it is added (a wrong ID is worse than no citation). Prefers the researcher's own entries (from `publications.json`) and caps self-citations at ≤3. A review sub-skill of $paperwrite; also usable standalone. Invoke when the user says \"related work\", \"related work is thin\", \"expand citations\", \"find more citations\", or $paperrelatedwork."
---

# paperrelatedwork

A thin related-work section is a common reviewer complaint and an easy fix. This
skill makes the search broad and the integration disciplined.

Review sub-skill of `$paperwrite`.

## Reuse before you search
The survey is already done: read `reports/01_LIT_SURVEY.html` and the researcher's
**the researcher's own entries in `publications.json`** first — most of the neighbours and
foundations are already there with verified ids. Only search the web for what is
genuinely missing.

## What to search for (breadth)
1. **Bases of the method** — the works this algorithm is built on (the
   representation/steering framework, the routing/MoE machinery, any
   estimator/optimisation technique). These ground the method's components.
2. **Same-topic work** — the direct neighbours (grouped by sub-family so the contrast
   with this method is visible).
3. **Corroborating / supporting work** — anything that backs a claim the paper makes:
   the mechanism it relies on, prior evidence for a phenomenon it exploits.
Use `reports/01_LIT_SURVEY.html`, the profile Bank, web search, or arXiv; a fan-out
sub-agent (Codex `spawn_agent` tool) is efficient for covering many buckets at once.

## How much (the clutter boundary)
Add as much as is genuinely relevant, stopping before the section reads as a list
dump. Target for a two-column template: the **references fill about 2–4 columns**
(check by rendering the compiled PDF's reference pages). Too few signals thin
scholarship; too many, padding. Every citation must do work in a sentence — if you
cannot say in one clause how it relates to this method, drop it.

## Self-citation discipline (personalization — non-negotiable)
**When invoked by `$paperwrite`, draw from the shared `self_cite_budget` in the
personalization context** — the ≤3 cap is for the WHOLE paper, so if the main draft has
already spent 2 self-cites you may add at most 1 here; do NOT open a second independent
≤3 cap. Write the section in the context's `writing_style` voice. Standalone, apply the
≤3 cap yourself.

Prefer the researcher's own entries (`publications.json`) before fetching new ones, BUT **cap
self-citations at ≤3 papers total**, only the most relevant (genuine
method/lineage/baseline overlap). Run
`python3 research_avatar/tools/bib_manager.py selfcite --enriched "researcher-profile/publications.json" --draft paper/main.tex`
to surface candidates; **never auto-insert a `\cite`** — rank by relevance, propose
the top ≤3 for approval, drop the rest. Do not pad the reference list with her own papers.

## Verify every ID (non-negotiable)
Confirm each arXiv id maps to the exact title, and the venue/year are right. Wrong ids
are caught here, not at submission. A wrong citation is worse than a missing one. If a
work has no arXiv id, cite the venue. (The survey's ids are already verified — trust
them; verify only newly added ones.)

## Integrate, don't dump
- Organize the section with `\paragraph` subheadings, one per sub-family.
- Each subheading ends by positioning this method against that family in one sentence
  ("…unlike these, ours biases the router before steering, so the edit is not routed away").
- Run a **whole-manuscript citation-obligation audit**, not a citation-count quota.
  At first substantive use, cite every externally sourced method/component, dataset,
  benchmark, metric/evaluator, pretrained model or checkpoint, protocol, adapted
  equation, and prior empirical/mechanistic fact. Record the supported clause and
  source in the paragraph plan/review log. Method and Experiments must carry their own
  in-context citations; an Introduction or Related Work citation does not discharge a
  later operational definition. Flag unsupported external facts as
  `[CITATION NEEDED]`, and flag citation concentration when the body relies on outside
  work but nearly all citations occur only in Introduction/Related Work. Do not add
  decorative citations or impose a minimum count per section.
  Persist each exact supported clause with its in-sentence citation and an exact excerpt/path
  from the retrieved local primary source, plus Setup evidence,
  in `paper/scholarship_contract.json`
  for `paper_checks.py scholarship`; do not maintain a second citation inventory.
  Before the gate, a fresh-context reviewer must compare every obligation and author/title
  metadata against the retrieved primary sources, record checked keys and unsupported clauses
  in `independent_source_audit`, and return red if any sourced sentence lacks coverage.
- Add BibTeX to `paper/references.bib`, then `\cite` every new key. Run
  `python3 research_avatar/tools/bib_manager.py check paper/references.bib` (duplicate / non-standard
  keys / missing fields) and recompile after.

## Mechanical nearest-neighbor coverage

For every claimed contribution, record at least two closest primary works in
`paper/scholarship_contract.json` under schema `1.1` → `nearest_neighbor_coverage`.
Each entry contains `contribution_id`, the exact `claim`, and neighbors with
`citation_key`, `source_url`, concrete `overlap`, and one independently testable
`independent_difference`. Every neighbor must also have an in-context
`citation_obligations` entry. “Broadly related” is not a distinction; if the paper
cannot state how it differs from its nearest work, narrow the contribution before writing.
The `paper_checks.py scholarship` gate rejects missing, duplicate, or uncited neighbors.

## Output
Updated `paper/references.bib` (verified entries) + an expanded, subheading-organized
related-work section + a whole-manuscript citation-obligation audit with in-context
citations, references spanning ~2–4 columns, `bib_manager check` clean, self-cites ≤3.
