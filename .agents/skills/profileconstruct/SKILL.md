---
name: "profileconstruct"
description: "Build / refresh the personalized researcher profile (PROFILE.md, the single source of truth) from Google Scholar + available coding-agent habits. Use when the user wants to (re)build or refresh their research profile, re-import publications, sync Experiment Templates / Workflow Preferences, or whenever PROFILE.md is missing or stale. Invoke explicitly as `$profileconstruct`."
---

# Profile Construct — Personalize the research buddy from Google Scholar

At the first Skill action in this Codex project session, run
`python3 -m research_studio.server --ensure-studios` before substantive work.
This idempotent project bootstrap starts or reuses Research Studio at
`http://127.0.0.1:8780` and Paper Studio at `http://127.0.0.1:8765`, then opens
both browser pages. Run it once per session, never launch duplicate servers, and
surface any startup error instead of claiming that either page is available.

> Restored 2026-07-03 by adapting the origin skill (`Auto-claude-code-research-in-sleep/skills/profile-builder`) to this project after the project skill tree was rebuilt. Kept research-buddy specifics: in-repo `researcher-profile/`, the `tools/` helpers, the six-skill pipeline, and W1–Wn workflow preferences.

## Overview

Reads the researcher's **Google Scholar homepage** and distills it into
**`researcher-profile/PROFILE.md`** at the project-local `researcher-profile/` path (NOT `~/researcher-profile`) — the **single source of truth**. Every
downstream skill is a consumer:

| Consumer | Reads |
|---|---|
| `$ideagen — lens: engineering` | *Dominant Methods* − *Known Dead-Ends* |
| `$ideagen — lens: theory` | *Research Lineage* + time-ordered records from `publications.json` |
| `$ideagen — lens: benchmark` | *Active Venues* + *Niche Subfields* |
| `$expplan` | *Experiment Templates* + closest-work grounding |
| `$runplan` | *Experiment Templates* (stack / OOM memory) |
| `$paperwrite` | the detailed *Writing Style* section in `PROFILE.md` + per-paper `task_type` + BibTeX (from `publications.json`) |

`PROFILE.md` is the only synthesized profile document and canonical profile source. Its rendered HTML is the one human-facing profile. `publications.json` is only the canonical per-publication record; never create a second profile or writing-style companion file.

> **Data source is fixed: Google Scholar.** Semantic Scholar only enriches abstracts/DOIs of
> papers already on Scholar — it never adds or removes a paper.

## Preflight: a COMPLETE Scholar page
Scholar serves ~20 papers initially; the rest load on **"Show more"**, and `Cmd+S` saves the
truncated source. Get a complete page (DevTools → Copy outerHTML into a `.html`, or `--from-tab`).
The helper **detects truncation** and emits `truncated: true` + a `warning`; **if truncated, STOP
and tell the user to expand fully and re-export** — never profile on a partial record.

### Research Studio terminal entry

Run `$profileconstruct` in the terminal with the fully expanded `.html`/`.htm` path. Research Studio only provides copy/open-terminal controls and renders the resulting `PROFILE.md` and `publications.json`; it must not upload Scholar HTML, run this Skill in a web-server background process, duplicate its logic, or maintain a second profile state. `PROFILE.md`, `publications.json`, and `fulltext/` are the only canonical outputs.

## Pipeline (cheap/deterministic first — W1; cache & never clobber — W2/W3)

All artifacts are built under the in-repo `researcher-profile/` path. The **final directory has a strict whitelist**:

- `PROFILE.md`
- `publications.json`
- `fulltext/` (both `pdf/` and extracted `txt/`)

Temporary `gs.json`, `arxiv_abs.json`, `habits.json`, `prefs_bundle.json`, and status manifests may exist only during a run and **must be deleted before completion**. Put diagnostic/status manifests in a system temporary directory when possible.

**Phase 1 — Read Scholar** → `gs.json`
```bash
python3 tools/scholar_profile.py --from-html "<exported.html>" > "researcher-profile/gs.json"
# or: python3 tools/scholar_profile.py --from-tab > "researcher-profile/gs.json"
```
Read the JSON. If `truncated` is true, surface the `warning` and stop. If `error`, surface it and stop.

**Phase 2 — Enrich (abstracts + DOIs + BibTeX)** → `publications.json`
```bash
python3 tools/profile_enrich.py --input "researcher-profile/gs.json" --output "researcher-profile/publications.json"
python3 tools/fetch_fulltext.py --enriched "researcher-profile/publications.json" --outdir "researcher-profile/fulltext" --delay 2
```
BibTeX always builds from Scholar metadata (offline) into `publications.json`. Abstracts + full-text depend on the network.

### Phase 2 network-resilience recipe (learned 2026-07-03 — READ THIS when abstracts/full-text come back empty)
The **sandbox `Bash` tool throttles outbound HTTP**: Semantic Scholar (`api.semanticscholar.org`) and even the arXiv **API** (`export.arxiv.org/api/query`) return **HTTP 429 / read-timeout**, so `profile_enrich.py` reports `"skipped_no_network"` / `enriched: 0` and `fetch_fulltext.py` silently drops papers it can't resolve. Do NOT conclude "no network" — the throttle is partial. Two paths still work; use them in order:

1. **Direct arXiv abstract-hosts DO respond from sandbox Bash** — `https://arxiv.org/abs/<id>` and `https://arxiv.org/pdf/<id>` return **200** even while the API is 429'd. Test once: `curl -sL -m25 -o /tmp/t.pdf -w '%{http_code}\n' https://arxiv.org/pdf/2505.15524`.
2. **The harness `web open/fetch`/`web search` tools use a DIFFERENT (un-throttled) network** than sandbox Bash. This is the reliable way to crawl abstracts + resolve arXiv ids when S2 is down (equivalent to "open the link in a real browser window").

**Abstract + arXiv-id crawl (when S2 is throttled):** for each paper, if the Scholar venue string already contains `arXiv:<id>` use it; else `web search "site:arxiv.org <title>"` → `web open/fetch https://arxiv.org/abs/<id>` asking for the verbatim title + abstract. **Verify the fetched title matches** (guard against grabbing a different paper); conference-only papers (KDD/ACL/ICML not on arXiv) legitimately have **no** abstract — record null, never fabricate. **Delegate the whole 19-paper crawl to one sub-agent** (it has web open/fetch/web search) that returns a compact `[{key, arxiv_id, abstract}]` JSON — keeps the many fetch outputs out of the main context. Persist to `researcher-profile/arxiv_abs.json`, then merge `abstract`/`arxiv_id`/`url_arxiv` into `publications.json` by `bibtex_key`.

**Every Scholar paper requires a PDF acquisition attempt.** Downloading only representative papers or only papers with an arXiv ID is incomplete. For each Scholar row, search in this order: explicit arXiv ID/URL → exact-title arXiv search → ACL Anthology or venue repository → publisher open-access PDF → bioRxiv/medRxiv → institutional/author repository. Duplicate Scholar rows may share one verified PDF, but every row must point to it in `publications.json`.

Once you have arXiv ids, download by id directly — this is more reliable than `fetch_fulltext.py`'s S2-based resolution:
```bash
curl -sL -m40 -o "researcher-profile/fulltext/pdf/<key>.pdf" "https://arxiv.org/pdf/<id>" \
  && pdftotext -q "researcher-profile/fulltext/pdf/<key>.pdf" "researcher-profile/fulltext/txt/<key>.txt"
```
Loop over all on-arXiv papers with a `sleep 2` between fetches. `pdftotext` (poppler) is present; `pypdf` is a fallback.

When shell search/download is throttled, **use the local browser or the harness browser network** (`web search`, `web open/fetch`) to resolve the exact-title PDF URL, then download it into `fulltext/pdf/`. The local browser is an approved fallback, not a last-resort exception. Verify the PDF title before accepting it. Do not substitute a similarly named paper.

For each row, write `pdf_path`, `fulltext_path`, and `fulltext_status` into `publications.json`. Statuses are `downloaded`, `shared_duplicate`, and `unavailable`. `unavailable` may be recorded only after all source classes above were tried, and must include a concrete `fulltext_failure_reason`; silent skips are forbidden. **Any `unavailable` row means the all-PDF requirement is not complete:** report the profile as incomplete/blocked rather than declaring success. The status report must state Scholar rows covered, unique PDFs, shared duplicates, and unresolved rows.

**Two ordering hazards:**
- `fetch_fulltext.py` **rewrites `publications.json` as it runs** (it re-writes abstracts it finds). If you run it in the background, it will **clobber** any manual abstract-merge done mid-flight. So: let it fully **exit** (poll `pgrep -f fetch_fulltext`, or `pkill` the straggler) **before** doing the authoritative `arxiv_abs.json → publications.json` merge as the LAST write.
- After a partial S2 run + a full arXiv crawl, the arXiv crawl is the **more complete** source — let it win the merge, keeping any tool-fetched abstract only as fallback.

**Phase 3 — Classify each paper `task_type ∈ {engineering, theory, benchmark}`** from title + venue + abstract:
- **engineering** — a system/method that improves a task (model, training recipe, architecture, agent system, application).
- **theory** — a hypothesis / analysis / interpretability / bound / diagnostic contribution.
- **benchmark** — a dataset / benchmark / survey / toolkit (evaluation infra).
Honesty rule: when a paper straddles two, pick the dominant contribution and note it; never invent a label the abstract doesn't support.

**Phase 4 — Infer identity + writing style**: Niche Subfields (ranked by recent volume × recency) · Dominant Methods · Research Lineage (origin → evolution → frontier) · Active Venues (last 3y) · Signature Works · **Writing Style — mine BOTH the abstracts AND the full papers, not abstracts alone.**

**Writing Style must capture two layers** (an abstract-only style profile is incomplete — it misses how the researcher writes a whole paper):
- **Abstract-level** (from the abstracts in `publications.json`): argument arc (gap-first vs landscape-first), two-/N-challenge framing, method-naming habit, mechanism-intro phrasing, closing/evaluation cadence, contribution-bullet phrasing.
- **Whole-paper-level** (from `fulltext/txt/`): read **exactly 15 unique representative full papers**, not just their abstracts. Select them to cover the researcher's major subfields, engineering/theory/benchmark contribution types, earlier/recent periods, and signature/recent work; do not simply take the first 15 downloads. Analyze **section organization** (which sections, in what order, typical lengths) · **Introduction structure** (the role each paragraph plays — hook → gap → approach → contributions list) · **Related Work organization** (thematic vs chronological; how many subsections) · **Method presentation** (subsection-per-module naming, notation conventions, how a module is introduced then formalized) · **paragraph rhetoric** (topic-sentence habits, transition words, how claims are hedged/qualified) · **table/figure conventions** (caption style, what Fig 1 usually is, table density) · **Limitations / Conclusion patterns**. Record these as concrete, reusable observations tied to example papers, so `$paperwrite` can match structure and cadence at the section level, not only the abstract. Head the section by stating it was mined from BOTH abstracts and exactly 15 full papers, listing all 15 unique publication keys. If fewer than 15 verified full texts are available, continue the acquisition ladder; never silently lower the sample count or substitute abstract-only evidence.

Write the detailed, operational style analysis directly inside the **`PROFILE.md` Writing Style section**. It must record its evidence base and include: quantitative abstract tendencies; core voice; abstract blueprint; paragraph-by-paragraph Introduction architecture; Related Work organization; Method/notation/naming conventions; experiment narrative and result-paragraph pattern; figure/table/caption conventions; paragraph/sentence mechanics; limitations/ethics/conclusion patterns; engineering/theory/benchmark variants; anti-imitation safeguards; and a drafting checklist. Tie observations to representative local full texts, distinguish measured tendencies from hard rules, and match structure/cadence without copying prior sentences. Do not generate any second profile or style-guide file.

**Phase 5 — Tacit knowledge (optional, non-blocking)**: reviewer-pushback themes / experiments they refuse to redo / recurring pitfalls seed *Known Dead-Ends*. You MAY ask the researcher for these if she is present, but this does NOT gate profile generation — if she doesn't supply them, seed *Known Dead-Ends* from the mined history + publications and move on. Never block the profile on an interview or a confirmation.

**Phase 6 — Mine available coding-agent history (ONCE, here; downstream never re-mines).** Prefer `.aris/meta/events.jsonl`. Claude transcripts may also be included when present; do not assume Codex session JSON is compatible with `workflow_prefs.py`:
```bash
python3 tools/experiment_history.py --events .aris/meta/events.jsonl --output "researcher-profile/habits.json"
# Optional, only when a compatible transcript path is supplied:
python3 tools/workflow_prefs.py --transcripts "<compatible-transcript-dir-or-jsonl>" --output "researcher-profile/prefs_bundle.json"
```
- **Fold `habits.json` → *Experiment Templates*** (deterministic): habitual launcher · framework/deps · base-model backbone · GPUs · failure memory (OOM hits, top error types). **Do NOT write hyperparameter values** (lr/batch/epochs/seed) — those are task-determined, decided by `$expplan`.
- **Fold `prefs_bundle.json` → *Workflow Preferences* W1–Wn** (LLM-distill, written directly — NO confirmation gate): cluster recurring candidates into 1-line preference statements, each with an evidence quote + why/how-to-apply; discard project-specific one-offs. **Write them straight from the mining** — Workflow Preferences are descriptive mined data, not a research decision, so this step does NOT stop to confirm them; if one is off, the researcher edits `PROFILE.md` directly. **The count is emergent — write as many W's as the mining yields, NOT a fixed 7.**

**Phase 7 — Write the single profile**: write `PROFILE.md` with sections: header (source/affiliation/stats/generated/publications + ⚠ if truncated) · Research Identity · Research Lineage · the complete Writing Style analysis specified in Phase 4 · Experiment Templates · Workflow Preferences (W1–Wn table — as many as mined) · one short **Publication Records** pointer to `publications.json`. Never copy a per-paper Publications Index or BibTeX bank into `PROFILE.md`; `publications.json` is the sole detailed publication source and Research Studio renders it for people. Do not generate `PROFILE.<lang>.md` or another profile companion.

**Phase 8 — Refresh and cleanup**: refresh `PROFILE.md` in place while preserving/merging Experiment Templates and Tacit Knowledge (W2/W3 — a stop mid-crawl must not destroy the existing profile). Mechanically verify that its Writing Style evidence list contains exactly 15 unique full-paper keys. Before declaring success, delete everything in `researcher-profile/` except `PROFILE.md`, `publications.json`, and `fulltext/`, mechanically verify that whitelist, and remove any obsolete profile companion so two profile sources cannot drift.

## Key rules
- **Google Scholar decides the paper list.** S2 only enriches; never adds/drops.
- **Stop on truncation.** A partial record poisons every downstream skill.
- **Label honestly.** Every `task_type` traces to title/venue/abstract; never invent publications or habits.
- **All PDFs are a mandatory outcome.** Exhaust the source ladder for every Scholar row; browser-assisted discovery/download is allowed and expected when shell networking is throttled. A representative-only corpus or any unresolved row is not completion.
- **Strict final directory.** `researcher-profile/` contains only `PROFILE.md`, `publications.json`, and `fulltext/`.
- **Detailed style stays inside the single profile.** Refresh the complete `PROFILE.md` Writing Style section from abstracts plus exactly 15 unique representative full papers on every successful profile construction; never split it into another file.
- **No duplicated publication index.** Keep counts, coverage, signature works, and research-line summaries in `PROFILE.md`; keep every per-paper row, abstract, citation count, `task_type`, BibTeX entry, and full-text status only in `publications.json`.
- **Descriptive, not a claim; NO confirmation gate** — a profile (incl. Workflow Preferences) is mined data, not a research verdict, so this step writes it straight through and does NOT stop to confirm anything. The researcher reviews by editing `PROFILE.md`. This is deliberately distinct from the research gates in `$ideagen`…`$paperwrite`, which DO stop for the human — profile-building is data prep, not a judgment.
- **Network throttle ≠ no network.** When S2/arXiv-API return 429 in sandbox Bash, fall back to direct `arxiv.org/abs|pdf/<id>` plus the local browser or `web open/fetch`/`web search`. Mark abstract and PDF coverage honestly and note unresolved failures in `publications.json`; never fabricate.

## Fixed profile page structure

Research Studio renders the single `PROFILE.md` as one fixed page: source/coverage header → Research Identity → Research Lineage → complete Writing Style → Experiment Templates → Workflow Preferences → short Publication Records pointer. Vary only the profile content inside these headings. Do not create extra profile tabs, upload controls, publication-index sections, or companion profile pages. The Live Demo must show these same slots with illustrative content.
