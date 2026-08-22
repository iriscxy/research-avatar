---
name: "profileconstruct"
description: "Build or refresh the project-local researcher profile from a complete Google Scholar export plus available coding-agent habits. Produces canonical PROFILE.html, publications.json, and verified full text. Use for profile construction, refresh, publication re-import, or stale/missing profile data; `$constructprofile` is an alias."
---

# Profile Construct

Run once per project session:

```bash
python3 -m research_avatar.research_studio.server --ensure
```

Treat `$constructprofile` as an alias for `/profileconstruct`.

Scholar records, enrichment records, verified transcripts, mined habits, and
explicit researcher corrections are authoritative inputs. Build the complete
`PROFILE.html` and `publications.json` in staging, validate them together, and
atomically replace the prior valid pair. Never correct either canonical output
by editing a row, paragraph, or field in place.

## Canonical inputs and outputs

Google Scholar fixes the publication list. Semantic Scholar and other sources
may enrich those rows but never add or remove papers.

Require a fully expanded Scholar HTML page. If the parser reports truncation,
stop and ask the researcher to expand “Show more” and export again; never build
a profile from a partial record.

The only final entries under `researcher-profile/` are:

- `PROFILE.html`: synthesized, human-facing single source of truth;
- `publications.json`: canonical per-paper metadata, BibTeX, task type, and
  full-text status;
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
5. Infer identity, niche subfields, dominant methods, lineage, venues, signature
   works, and writing style.
6. Mine available experiment/workflow history once and fold it into Experiment
   Templates and Workflow Preferences.
7. Refresh `PROFILE.html` transactionally, preserving the old valid profile
   until the replacement is complete.
8. Enforce the final directory whitelist and validate the report.

Read
[`references/acquisition-and-style.md`](references/acquisition-and-style.md)
while acquiring abstracts/PDFs, classifying papers, or measuring writing style.
It contains the complete network fallback, full-text coverage, exactly-15-paper
style analysis, and ordering safeguards.

Read [`references/profile-contract.md`](references/profile-contract.md) while
mining workflow history, writing/refreshing the profile, cleaning outputs, or
validating completion.

## Completion rules

- Every Scholar row receives a PDF acquisition attempt across the full source
  ladder. `unavailable` requires a concrete failure reason and means profile
  construction remains incomplete.
- Every available PDF receives a transcript produced directly by the executing
  code agent that preserves
  semantic reading order and complete natural paragraphs across columns and
  page breaks. A failed transcript is incomplete; never silently fall back to
  a separate LLM API, `pdftotext`, or OCR.
- Writing Style is mined from all available abstracts and exactly 15 unique,
  representative verified full papers spanning subfields, contribution types,
  time periods, and signature/recent work.
- Measured tendencies are not hard prose rules; match structure/cadence without
  copying prior sentences.
- Workflow Preferences are descriptive mined data, not a research decision;
  write the evidence-backed W1–Wn list without an approval gate.
- Experiment Templates may capture stack, launchers, models, GPUs, and failure
  memory, but not task-specific hyperparameters.
- Refreshes must not clobber a valid profile during a partial crawl.

Run:

```bash
python3 research_avatar/tools/validate_report_structure.py --kind profile --html researcher-profile/PROFILE.html
```

Also mechanically verify exactly 15 unique full-paper keys in the Writing Style
evidence list and the strict final directory whitelist before reporting
success.
