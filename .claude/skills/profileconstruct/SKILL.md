---
name: "profileconstruct"
description: "Build or refresh the project-local researcher profile from a complete Google Scholar export. Produces canonical PROFILE.html, publications.json, profile_pairs.json, and verified full text. Use for profile construction, refresh, publication re-import, or stale/missing profile data; `$constructprofile` is an alias."
---

# Profile Construct

Run once per project session:

```bash
python3 -m research_avatar.research_studio.server --ensure
```

Treat `$constructprofile` as an alias for `/profileconstruct`.

Scholar records, enrichment records, verified transcripts, and
explicit researcher corrections are authoritative inputs. Build the complete
`PROFILE.html` and `publications.json` in staging, validate them together, and
atomically replace the prior valid pair. Write each acquired PDF and each
completed transcript directly into `researcher-profile/fulltext/` as soon as it
exists; do not hold full texts in a staging copy. Never correct either canonical output
by editing a row, paragraph, or field in place.

## Canonical inputs and outputs

Google Scholar fixes the publication list. Semantic Scholar and other sources
may enrich those rows but never add or remove papers.

Require a fully expanded Scholar HTML page. If the parser reports truncation,
stop and ask the researcher to expand “Show more” and export again; never build
a profile from a partial record.

The only final entries under `researcher-profile/` are:

- `PROFILE.html`: synthesized, human-facing single source of truth;
- `publications.json`: canonical per-paper publication record only —
  metadata, abstract, BibTeX, task type, and full-text status;
- `profile_pairs.json`: the paired author/model records keyed by
  `bibtex_key`, which downstream skills retrieve from;
- `fulltext/pdf/` and `fulltext/txt/`.

Temporary crawl/mining files must be removed before completion. Do not create
Markdown profiles, translated companions, separate writing-style files, or a
duplicated publication index inside `PROFILE.html`.

## Pipeline

1. Parse Scholar with `research_avatar/tools/scholar_profile.py`; stop on
   truncation/error.
2. Enrich rows and BibTeX with `profile_enrich.py`.
3. Attempt verified PDF acquisition for every Scholar row with
   `fetch_fulltext.py` plus the documented fallback ladder.
   The executing code agent must then read each original PDF directly and
   transcribe it; do not call a separate LLM API and do not use `pdftotext`,
   OCR, or coordinate-based text as an intermediate source.
4. Assign one dominant `task_type`: `engineering`, `theory`, or `benchmark`.
5. Build Research Identity and Research Lineage from the abstracts and
   metadata of every Scholar row (title, year, venue, co-authors, citations).
   They do not need full text, so rows without a PDF still count.
6. On the 8 most recent first- or last-author papers, construct isolated
   author/model pairs for the three Jinghui tasks — Idea, Abstract, and
   Introduction — and extract each pair's `author_differences`. Synthesize the
   Idea Profile and the Abstract and Introduction parts of the Writing Profile
   from those comparisons. Derive the other Writing Profile
   sections directly from the full texts.
7. Refresh `PROFILE.html` transactionally, preserving the old valid profile
   until the replacement is complete.
8. Enforce the final directory whitelist and validate the report.

The profile describes only the researcher's past work. It never contains a new
project's idea, question, or draft. Downstream skills connect a new input to the
profile at use time by retrieving the most similar paired records from
`profile_pairs.json` with `research_avatar/tools/jinghui_prompt.py`.

Read
[`references/acquisition-and-style.md`](references/acquisition-and-style.md)
while acquiring abstracts/PDFs, classifying papers, or measuring writing style.
It contains the complete network fallback, full-text coverage, pair-paper
style analysis, and ordering safeguards.

Read [`references/profile-contract.md`](references/profile-contract.md) while
writing/refreshing the profile, cleaning outputs, or
validating completion.

Read [`references/paired-profile-construction.md`](references/paired-profile-construction.md)
before constructing the Idea, Abstract, or Introduction pairs. This
is the mandatory Jinghui-compatible pairing, isolation, input, provenance, and
`author_differences` contract.

## Completion rules

- Every Scholar row receives a PDF acquisition attempt across the full source
  ladder. `unavailable` requires a concrete failure reason and means profile
  construction remains incomplete.
- Every available PDF receives a transcript produced directly by the executing
  code agent that preserves
  semantic reading order and complete natural paragraphs across columns and
  page breaks. A failed transcript is incomplete; never silently fall back to
  a separate LLM API, `pdftotext`, or OCR.
- Pairs and full-text writing analysis use the same paper set: the 8 most
  recent papers on which the researcher is first or last author (newest year
  first; same-year ties by Scholar order; fewer than 8 eligible means all of
  them). Never use a middle-author paper. When the researcher selects a
  specific set of papers, use exactly that set instead.
- `PROFILE.html` has exactly four top-level sections in this order: Research
  Identity, Research Lineage, Idea Profile, Writing Profile. There is no
  Research Environment section and no workflow/habit mining.
- Construct the Idea, Abstract, and Introduction pairs strictly through
  `references/paired-profile-construction.md`, using the exact task prompts
  from `demo_paper/jinghui_prompt.md`, for every selected paper with a verified
  transcript. There is no Experiment pair: the Idea task's `validation` field
  already covers the kind of evidence an idea needs. Generate each model counterpart in an
  isolated context, save it, compare with the author version, and record actual
  `author_differences`. Preserve differences as paper-specific observations, not
  fixed instructions. A missing pair for a selected paper means this stage is
  incomplete.
- Do not construct pairs for other sections. Build the remaining Writing
  Profile sections from the verified full texts, tied to the papers they come
  from.
- In the Writing Profile, show `Abstract`, `Introduction`, and each observed
  organization name (for example, `Related Work`) directly as green headings.
  After Abstract and Introduction, order the organizations by the author's
  usual paper structure (typical heading position in the selected full texts).
  Do not add umbrella labels such as “Section-specific writing profiles,” nor
  process labels such as “Observed section names.” Use observed subsection
  headings to route and ground the profile internally, but do not print a raw
  list of paper headings under each organization.
- Profile prose in `PROFILE.html` carries no paper citations: never append
  paper keys such as `(gao2024shaping)` or name a paper key inline. State the
  observation itself; paper provenance stays in `profile_pairs.json`, the
  section `papers` lists, and `writing_style_papers`.
- Downstream generation passes only the task's matching `author_differences`
  retrieved for the current input, assembled in Jinghui order; it never loads
  the whole profile as prompt context. For a non-abstract, non-introduction
  section, pass only the matching organization profile.
- Measured tendencies are not hard prose rules; match structure/cadence without
  copying prior sentences.
- Refreshes must not clobber a valid profile during a partial crawl.

Run:

```bash
python3 research_avatar/tools/validate_report_structure.py --kind profile --html researcher-profile/PROFILE.html
```

Also mechanically verify 1 to 15 unique full-paper keys in `writing_style_papers` of
`reports/.build/PROFILE.source.json` (not shown on the page) and the strict final directory whitelist before reporting
success.
