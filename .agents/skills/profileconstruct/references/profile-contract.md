## Overview

Reads the researcher's **Google Scholar homepage** and distills it into
**`researcher-profile/PROFILE.html`** at the project-local `researcher-profile/` path (NOT `~/researcher-profile`) — the self-contained **single source of truth**. Every
downstream research stage consumes only the fields it needs:

| Consumer | Reads |
|---|---|
| `$researchlit` | *Research Identity* + *Research Lineage* to propose broad directions and, only in personalized question mode, to rank research questions |
| `$ideagen` | Idea `author_differences` retrieved from `profile_pairs.json` for the selected `research_question` (Profile setting); nothing in the None setting |
| `$expplan` | nothing from the profile (closest-work grounding comes from the survey) |
| `$runplan` | nothing from the profile |
| Browser paper writing | only the matching Abstract/Introduction `author_differences`, or the matching organization/subsection profile, plus BibTeX from `publications.json` |

`PROFILE.html` is both the only synthesized profile document and the human-facing canonical profile. `publications.json` is only the canonical per-publication record and `profile_pairs.json` only the paired records; never create a Markdown profile, second profile, or writing-style companion file.

`profile_pairs.json` holds, per paper (`bibtex_key`) and task, the exact reconstruction input,
original author version, actual isolated model counterpart, factual validation,
and resulting `author_differences` entry for each supported task (Idea, Abstract, Introduction). Retain these
records in `profile_pairs.json` through refresh and cleanup. Build and validate
them with [paired-profile-construction.md](paired-profile-construction.md)
before synthesizing the readable profile. Direct preference summaries without
the required paired evidence are not a completed Jinghui Profile construction.

> **Data source is fixed: Google Scholar.** Semantic Scholar only enriches abstracts/DOIs of
> papers already on Scholar — it never adds or removes a paper.

**Write the single profile**: fill the slots of `reports/.build/PROFILE.source.json` and render the single `PROFILE.html` with `research_avatar/tools/render_profile_report.py` (see Fixed template below), with these fixed top-level sections: Research Identity · Research Lineage · Idea Profile · Writing Profile. Within the Writing Profile, put separate Abstract and Introduction profiles first, then group the remaining profiles by the paper's organization and list the actual subsection headings found in the selected papers. The grouping labels are organizational routes, not a fixed author-independent taxonomy. Never copy a per-paper Publications Index or BibTeX bank into `PROFILE.html`; `publications.json` is the sole detailed publication source. The profile describes only past work and never holds a new project's question, idea, or draft. Do not generate `PROFILE.md`, `PROFILE.<lang>.html`, or another profile companion.
Render `Abstract`, `Introduction`, and every observed organization name directly as green headings. Do not insert a generic umbrella heading for the organization profiles or expose process labels such as “Observed section names.”
Use concrete paper subsection headings for matching and analysis, but do not render a raw heading inventory under each organization; show the concise synthesized profile prose instead.

**Refresh and cleanup**: refresh `PROFILE.html` transactionally (a stop mid-crawl must not destroy the existing profile). Mechanically verify that `writing_style_papers` in `reports/.build/PROFILE.source.json` contains 1 to 15 unique full-paper keys (the renderer enforces this; keys are not shown on the page). Before declaring success, delete everything in `researcher-profile/` except `PROFILE.html`, `publications.json`, `profile_pairs.json`, and `fulltext/`, mechanically verify that whitelist, and remove any obsolete Markdown or profile companion so two profile sources cannot drift. Run `python3 research_avatar/tools/validate_report_structure.py --kind profile --html researcher-profile/PROFILE.html` before completion.

## Key rules
- **Google Scholar decides the paper list.** S2 only enriches; never adds/drops.
- **Stop on truncation.** A partial record poisons every downstream skill.
- **Label honestly.** Every `task_type` traces to title/venue/abstract; never invent publications.
- **All PDFs are a mandatory outcome.** Exhaust the source ladder for every Scholar row; browser-assisted discovery/download is allowed and expected when shell networking is throttled. A representative-only corpus or any unresolved row is not completion.
- **Strict final directory.** `researcher-profile/` contains only `PROFILE.html`, `publications.json`, `profile_pairs.json`, and `fulltext/`.
- **Detailed style stays inside the single profile.** Refresh the complete `PROFILE.html` Writing Profile from abstracts plus the same full papers used for the pairs (or the researcher-selected set) on every successful profile construction; never split it into another file.
- **Idea, Abstract, and Introduction pairs are mandatory.** For the 8 most recent first- or last-author papers (all of them if fewer than 8), build actual Idea, Abstract, and Introduction counterparts using the source task prompts and fresh contexts, and retain their inputs/outputs/comparisons in `profile_pairs.json`. Do not build other-section pairs. Do not replace missing pairs with observed-tendencies prose or simulated generations. Keep the old valid profile until the required pairs and replacement are complete.
- **No duplicated publication index.** Keep counts, coverage, signature works, and research-line summaries in `PROFILE.html`; keep every per-paper row, abstract, citation count, `task_type`, BibTeX entry, and full-text status only in `publications.json`.
- **Descriptive, not a claim; NO confirmation gate** — a profile is mined data, not a research verdict, so this step writes it straight through and does NOT stop to confirm anything. The researcher reviews by editing `PROFILE.html`. This is deliberately distinct from the decision gates in `$ideagen`, `$expplan`, and `$runplan` — profile-building is data prep, not a judgment.
- **Network throttle ≠ no network.** When S2/arXiv-API return 429 in sandbox Bash, fall back to direct `arxiv.org/abs|pdf/<id>` plus the local browser or `web open/fetch`/`web search`. Mark abstract and PDF coverage honestly and note unresolved failures in `publications.json`; never fabricate.

## Fixed profile page structure

Write the canonical profile directly as one fixed HTML page. Preserve this exact visible order, exact section names, and exact `data-report-section` IDs:

1. `1. Research Identity` (`research-identity`);
2. `2. Research Lineage` (`research-lineage`);
3. `3. Idea Profile` (`idea-profile`);
4. `4. Writing Profile` (`writing-profile`).

Use one `<section data-report-section="…">` and one matching visible `<h2>` for every slot. Vary only their content and task-specific nested headings. Do not add, rename, reorder, or omit a top-level section. Do not create extra profile tabs, upload controls, publication-index sections, or companion profile pages. Every top-level title must contain substantive, researcher-specific content; an empty heading, placeholder-only body, or title-only structure list fails the contract. The Live Demo must show all four slots with filled illustrative content.

## Fixed template — fill the named slots only

`PROFILE.html` is rendered by `research_avatar/tools/render_profile_report.py` from
`reports/.build/PROFILE.source.json`. The template fixes everything on the page: the
stylesheet, header, navigation, four numbered sections, every sub-heading, and every table
head. A run writes content into named slots; the renderer rejects missing, empty, or
unknown slots, so no extra paragraph, callout, or section can appear. Never write HTML.

Header slots: `name`, `refreshed`, `stats` (short strings), and `writing_style_papers`
(1 to 15 unique full-paper keys, checked but never shown).

| Slot | Content |
|---|---|
| `identity.niche_subfields`, `signature_works` | lists of short items, from abstracts and metadata |
| `identity.dominant_methods`, `active_venues` | one short text each, from abstracts and metadata |
| `lineage` | list of `{year, title, text}`; short title with its year, one paragraph; as many entries as the researcher has thematic turns |
| `idea_profile` | one text: readable summary of the paired Idea `author_differences` |
| `writing.abstract_profile`, `writing.introduction_profile` | separate readable summaries of actual paired `author_differences`; the complete paired records remain in `profile_pairs.json` |
| `writing.section_profiles` | list of `{organization, section_names, profile, papers}`; synthesize each from the full texts under observed author-specific headings (not from pairs) |

Text slots allow only light inline markup (`<strong>`, `<em>`, `<code>`, `<a>`).
When drafting an abstract or introduction, provide only its corresponding
profile and matching `author_differences` array. For any other paper section, match its organization and current heading
against `section_profiles` and provide only the best matching profile. If no
exact or defensible match exists, state that no author-specific profile applies
and rely on the approved outline and evidence; do not substitute a profile from
an unrelated section.
Process notes, waivers, download failures, and audit trails belong in `publications.json`,
never in a slot. Render with:

```bash
python3 research_avatar/tools/render_profile_report.py \
  --source reports/.build/PROFILE.source.json --output researcher-profile/PROFILE.html
```
