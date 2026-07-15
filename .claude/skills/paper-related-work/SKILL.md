---
name: paper-related-work
description: Build a thorough, well-organized related-work section by broadly searching the literature — the works the method is built on, works on the same topic, and any work that corroborates a claim — then integrating them under clear subheadings without clutter. Every arXiv ID is verified before it is added (a wrong ID is worse than no citation). Prefers the researcher's own BibTeX Bank and caps self-citations at ≤3. A review sub-skill of /paper-write; also usable standalone. Invoke when the user says "相关工作太少", "related work", "找更多引用", "expand citations", "查相关工作", or /paper-related-work.
---

# paper-related-work

A thin related-work section is a common reviewer complaint and an easy fix. This
skill makes the search broad and the integration disciplined.

Review sub-skill of `/paper-write`. Converse in the user's language (Chinese here);
write the section in the paper's language (English by default).

## Reuse before you search
The survey is already done: read `outputs/01_LIT_SURVEY.html` and the researcher's
**BibTeX Bank** in `aris-profile/PROFILE_AUTO.md` first — most of the neighbours and
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
Use `outputs/01_LIT_SURVEY.html`, the profile Bank, WebSearch, or arXiv; a fan-out
sub-agent (Agent tool) is efficient for covering many buckets at once.

## How much (the clutter boundary)
Add as much as is genuinely relevant, stopping before the section reads as a list
dump. Target for a two-column template: the **references fill about 2–4 columns**
(check by rendering the compiled PDF's reference pages). Too few signals thin
scholarship; too many, padding. Every citation must do work in a sentence — if you
cannot say in one clause how it relates to this method, drop it.

## Self-citation discipline (personalization — non-negotiable)
**When invoked by `/paper-write`, draw from the shared `self_cite_budget` in the
personalization context** — the ≤3 cap is for the WHOLE paper, so if the main draft has
already spent 2 self-cites you may add at most 1 here; do NOT open a second independent
≤3 cap. Write the section in the context's `writing_style` voice. Standalone, apply the
≤3 cap yourself.

Prefer the researcher's own BibTeX Bank entries before fetching new ones, BUT **cap
self-citations at ≤3 papers total**, only the most relevant (genuine
method/lineage/baseline overlap). Run
`python3 tools/bib_manager.py selfcite --enriched "$ARIS_PROFILE/enriched.json" --draft paper/main.tex`
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
- Scatter a few citations into the right body sections too (the framework reference in
  the method; the mechanism references in the analysis), not only related work.
- Add BibTeX to `paper/references.bib`, then `\cite` every new key. Run
  `python3 tools/bib_manager.py check paper/references.bib` (duplicate / non-standard
  keys / missing fields) and recompile after.

## Output
Updated `paper/references.bib` (verified entries) + an expanded, subheading-organized
related-work section + scattered in-context citations, references spanning ~2–4
columns, `bib_manager check` clean, self-cites ≤3.
