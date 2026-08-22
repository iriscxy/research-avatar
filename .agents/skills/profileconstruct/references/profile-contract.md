## Overview

Reads the researcher's **Google Scholar homepage** and distills it into
**`researcher-profile/PROFILE.html`** at the project-local `researcher-profile/` path (NOT `~/researcher-profile`) — the self-contained **single source of truth**. Every
downstream research stage consumes only the fields it needs:

| Consumer | Reads |
|---|---|
| `$ideagen — lens: engineering` | *Dominant Methods* − *Known Dead-Ends* |
| `$ideagen — lens: theory` | *Research Lineage* + time-ordered records from `publications.json` |
| `$ideagen — lens: benchmark` | *Active Venues* + *Niche Subfields* |
| `$expplan` | *Experiment Templates* + closest-work grounding |
| `$runplan` | *Experiment Templates* (stack / OOM memory) |
| Browser paper writing | the selected reference paper's measured writing pattern + BibTeX from `publications.json` |

`PROFILE.html` is both the only synthesized profile document and the human-facing canonical profile. `publications.json` is only the canonical per-publication record; never create a Markdown profile, second profile, or writing-style companion file.

> **Data source is fixed: Google Scholar.** Semantic Scholar only enriches abstracts/DOIs of
> papers already on Scholar — it never adds or removes a paper.

# Optional, only when a compatible transcript path is supplied:
python3 research_avatar/tools/workflow_prefs.py --transcripts "<compatible-transcript-dir-or-jsonl>" --output "researcher-profile/prefs_bundle.json"
```
- **Fold `habits.json` → *Experiment Templates*** (deterministic): habitual launcher · framework/deps · base-model backbone · GPUs · failure memory (OOM hits, top error types). **Do NOT write hyperparameter values** (lr/batch/epochs/seed) — those are task-determined, decided by `$expplan`.
- **Fold `prefs_bundle.json` → *Workflow Preferences* W1–Wn** (LLM-distill, written directly — NO confirmation gate): cluster recurring candidates into 1-line preference statements, each with an evidence quote + why/how-to-apply; discard project-specific one-offs. **Write them straight from the mining** — Workflow Preferences are descriptive mined data, not a research decision, so this step does NOT stop to confirm them. If one is wrong, record the correction as an explicit profile input and rerun the complete profile renderer; never edit `PROFILE.html` directly. **The count is emergent — write as many W's as the mining yields, NOT a fixed 7.**

**Phase 7 — Write the single profile**: write one self-contained `PROFILE.html` with inline CSS and the fixed sections below: source/coverage header · Research Identity · Research Lineage · the complete Writing Style analysis specified in Phase 4 · Experiment Templates · Workflow Preferences (W1–Wn table — as many as mined) · one short **Publication Records** pointer to `publications.json`. Never copy a per-paper Publications Index or BibTeX bank into `PROFILE.html`; `publications.json` is the sole detailed publication source. Do not generate `PROFILE.md`, `PROFILE.<lang>.html`, or another profile companion.

**Phase 8 — Refresh and cleanup**: refresh `PROFILE.html` transactionally while preserving/merging Experiment Templates and Tacit Knowledge (W2/W3 — a stop mid-crawl must not destroy the existing profile). Mechanically verify that its Writing Style evidence list contains exactly 15 unique full-paper keys. Before declaring success, delete everything in `researcher-profile/` except `PROFILE.html`, `publications.json`, and `fulltext/`, mechanically verify that whitelist, and remove any obsolete Markdown or profile companion so two profile sources cannot drift. Run `python3 research_avatar/tools/validate_report_structure.py --kind profile --html researcher-profile/PROFILE.html` before completion.

## Key rules
- **Google Scholar decides the paper list.** S2 only enriches; never adds/drops.
- **Stop on truncation.** A partial record poisons every downstream skill.
- **Label honestly.** Every `task_type` traces to title/venue/abstract; never invent publications or habits.
- **All PDFs are a mandatory outcome.** Exhaust the source ladder for every Scholar row; browser-assisted discovery/download is allowed and expected when shell networking is throttled. A representative-only corpus or any unresolved row is not completion.
- **Strict final directory.** `researcher-profile/` contains only `PROFILE.html`, `publications.json`, and `fulltext/`.
- **Detailed style stays inside the single profile.** Refresh the complete `PROFILE.html` Writing Style section from abstracts plus exactly 15 unique representative full papers on every successful profile construction; never split it into another file.
- **No duplicated publication index.** Keep counts, coverage, signature works, and research-line summaries in `PROFILE.html`; keep every per-paper row, abstract, citation count, `task_type`, BibTeX entry, and full-text status only in `publications.json`.
- **Descriptive, not a claim; NO confirmation gate** — a profile (incl. Workflow Preferences) is mined data, not a research verdict, so this step writes it straight through and does NOT stop to confirm anything. The researcher reviews by editing `PROFILE.html`. This is deliberately distinct from the decision gates in `$ideagen`, `$expplan`, and `$runplan` — profile-building is data prep, not a judgment.
- **Network throttle ≠ no network.** When S2/arXiv-API return 429 in sandbox Bash, fall back to direct `arxiv.org/abs|pdf/<id>` plus the local browser or `web open/fetch`/`web search`. Mark abstract and PDF coverage honestly and note unresolved failures in `publications.json`; never fabricate.

## Fixed profile page structure

Write the canonical profile directly as one fixed HTML page. Preserve this exact visible order, exact section names, and exact `data-report-section` IDs:

1. `Source and Coverage` (`source-coverage`);
2. `Research Identity` (`research-identity`);
3. `Research Lineage` (`research-lineage`);
4. `Writing Style` (`writing-style`);
5. `Experiment Templates` (`experiment-templates`);
6. `Workflow Preferences` (`workflow-preferences`);
7. `Publication Records` (`publication-records`).

Use one `<section data-report-section="…">` and one matching visible `<h2>` for every slot. Vary only their content and task-specific nested headings. Do not add, rename, reorder, or omit a top-level section. Do not create extra profile tabs, upload controls, publication-index sections, or companion profile pages. Every top-level title must contain substantive, researcher-specific content; an empty heading, placeholder-only body, or title-only structure list fails the contract. The Live Demo must show all seven slots with filled illustrative content.
