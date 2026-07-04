---
name: profile-construct
description: Build / refresh the personalized researcher profile (PROFILE_AUTO.md, the single source of truth) from Google Scholar + Claude-session habits. Use when the user wants to (re)build or refresh their research profile, re-import publications, sync Experiment Templates / Workflow Preferences, or whenever PROFILE_AUTO.md is missing or stale. Invocable as /profile-construct.
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, WebSearch, WebFetch, AskUserQuestion, mcp__codex__codex, mcp__codex__codex-reply
---

# Profile Construct — Personalize the research buddy from Google Scholar

> Restored 2026-07-03 by adapting the origin skill (`Auto-claude-code-research-in-sleep/skills/profile-builder`) to this project after `.claude/` was deleted. Kept research-buddy specifics: in-repo `aris-profile/`, the `tools/` helpers, the five-skill pipeline, W1–W7, and the Chinese mirror.

## Overview

Reads the researcher's **Google Scholar homepage** and distills it into
**`aris-profile/PROFILE_AUTO.md`** (via `$ARIS_PROFILE`, set in `.claude/settings.json` to the
**in-repo** `aris-profile/`, NOT `~/aris-profile`) — the **single source of truth**. Every
downstream skill is a consumer:

| Consumer | Reads from PROFILE_AUTO.md |
|---|---|
| `/ideagen — lens: engineering` | *Dominant Methods* − *Known Dead-Ends* |
| `/ideagen — lens: theory` | *Research Lineage* + *Publications Index* (time-ordered) |
| `/ideagen — lens: benchmark` | *Active Venues* + *Niche Subfields* |
| `/workplan` | *Experiment Templates* + closest-work grounding |
| `/run-plan` | *Experiment Templates* (stack / OOM memory) |
| `/paper-write` | *Writing Style* + per-paper `task_type` + *BibTeX Bank* |

Converse in **Chinese**; keep code/identifiers/paper-titles native. The English `PROFILE_AUTO.md`
is canonical; regenerate the human-facing Chinese mirror `PROFILE_AUTO.zh.md` in the same pass
(natural, native Chinese, second person 你/你的 where it addresses the researcher).

> **Data source is fixed: Google Scholar.** Semantic Scholar only enriches abstracts/DOIs of
> papers already on Scholar — it never adds or removes a paper.

## Preflight: a COMPLETE Scholar page
Scholar serves ~20 papers initially; the rest load on **"Show more"**, and `Cmd+S` saves the
truncated source. Get a complete page (DevTools → Copy outerHTML into a `.html`, or `--from-tab`).
The helper **detects truncation** and emits `truncated: true` + a `warning`; **if truncated, STOP
and tell the user to expand fully and re-export** — never profile on a partial record.

## Pipeline (cheap/deterministic first — W1; cache & never clobber — W2/W3)

All artifacts live under `$ARIS_PROFILE/` (in-repo `aris-profile/`).

**Phase 1 — Read Scholar** → `gs.json`
```bash
python3 tools/scholar_profile.py --from-html "<exported.html>" > "$ARIS_PROFILE/gs.json"
# or: python3 tools/scholar_profile.py --from-tab > "$ARIS_PROFILE/gs.json"
```
Read the JSON. If `truncated` is true, surface the `warning` and stop. If `error`, surface it and stop.

**Phase 2 — Enrich (abstracts + DOIs + BibTeX Bank)** → `enriched.json`
```bash
python3 tools/profile_enrich.py --input "$ARIS_PROFILE/gs.json" --output "$ARIS_PROFILE/enriched.json"
python3 tools/fetch_fulltext.py --enriched "$ARIS_PROFILE/enriched.json" --outdir "$ARIS_PROFILE/fulltext" --delay 2
```
BibTeX Bank always builds from Scholar metadata (offline). Abstracts + full-text depend on the network.

### Phase 2 network-resilience recipe (learned 2026-07-03 — READ THIS when abstracts/full-text come back empty)
The **sandbox `Bash` tool throttles outbound HTTP**: Semantic Scholar (`api.semanticscholar.org`) and even the arXiv **API** (`export.arxiv.org/api/query`) return **HTTP 429 / read-timeout**, so `profile_enrich.py` reports `"skipped_no_network"` / `enriched: 0` and `fetch_fulltext.py` silently drops papers it can't resolve. Do NOT conclude "no network" — the throttle is partial. Two paths still work; use them in order:

1. **Direct arXiv abstract-hosts DO respond from sandbox Bash** — `https://arxiv.org/abs/<id>` and `https://arxiv.org/pdf/<id>` return **200** even while the API is 429'd. Test once: `curl -sL -m25 -o /tmp/t.pdf -w '%{http_code}\n' https://arxiv.org/pdf/2505.15524`.
2. **The harness `WebFetch`/`WebSearch` tools use a DIFFERENT (un-throttled) network** than sandbox Bash. This is the reliable way to crawl abstracts + resolve arXiv ids when S2 is down (equivalent to "open the link in a real browser window").

**Abstract + arXiv-id crawl (when S2 is throttled):** for each paper, if the Scholar venue string already contains `arXiv:<id>` use it; else `WebSearch "site:arxiv.org <title>"` → `WebFetch https://arxiv.org/abs/<id>` asking for the verbatim title + abstract. **Verify the fetched title matches** (guard against grabbing a different paper); conference-only papers (KDD/ACL/ICML not on arXiv) legitimately have **no** abstract — record null, never fabricate. **Delegate the whole 19-paper crawl to one sub-Agent** (it has WebFetch/WebSearch) that returns a compact `[{key, arxiv_id, abstract}]` JSON — keeps the many fetch outputs out of the main context. Persist to `aris-profile/arxiv_abs.json`, then merge `abstract`/`arxiv_id`/`url_arxiv` into `enriched.json` by `bibtex_key`.

**Full-text PDFs (works in sandbox Bash even when the API is throttled):** once you have arXiv ids, download by id directly — this is more reliable than `fetch_fulltext.py`'s S2-based resolution:
```bash
curl -sL -m40 -o "$ARIS_PROFILE/fulltext/pdf/<key>.pdf" "https://arxiv.org/pdf/<id>" \
  && pdftotext -q "$ARIS_PROFILE/fulltext/pdf/<key>.pdf" "$ARIS_PROFILE/fulltext/txt/<key>.txt"
```
Loop over all on-arXiv papers with a `sleep 2` between fetches. `pdftotext` (poppler) is present; `pypdf` is a fallback.

**Two ordering hazards:**
- `fetch_fulltext.py` **rewrites `enriched.json` as it runs** (it re-writes abstracts it finds). If you run it in the background, it will **clobber** any manual abstract-merge done mid-flight. So: let it fully **exit** (poll `pgrep -f fetch_fulltext`, or `pkill` the straggler) **before** doing the authoritative `arxiv_abs.json → enriched.json` merge as the LAST write.
- After a partial S2 run + a full arXiv crawl, the arXiv crawl is the **more complete** source — let it win the merge, keeping any tool-fetched abstract only as fallback.

**Phase 3 — Classify each paper `task_type ∈ {engineering, theory, benchmark}`** from title + venue + abstract:
- **engineering** — a system/method that improves a task (model, training recipe, architecture, agent system, application).
- **theory** — a hypothesis / analysis / interpretability / bound / diagnostic contribution.
- **benchmark** — a dataset / benchmark / survey / toolkit (evaluation infra).
Honesty rule: when a paper straddles two, pick the dominant contribution and note it; never invent a label the abstract doesn't support.

**Phase 4 — Infer identity + writing style**: Niche Subfields (ranked by recent volume × recency) · Dominant Methods · Research Lineage (origin → evolution → frontier) · Active Venues (last 3y) · Signature Works · Writing Style (argument arc gap-first vs landscape-first, contribution-bullet phrasing, cadence).

**Phase 5 — Tacit-knowledge interview** (AskUserQuestion): recent reviewer pushback themes, experiments they refuse to redo, recurring pitfalls → seed *Known Dead-Ends*.

**Phase 5.5 — Mine coding-agent history (ONCE, here; downstream never re-mines)** over `~/.claude/projects/*`:
```bash
python3 tools/experiment_history.py --transcripts "$HOME"/.claude/projects/* --output "$ARIS_PROFILE/habits.json"
python3 tools/workflow_prefs.py     --transcripts "$HOME"/.claude/projects/* --output "$ARIS_PROFILE/prefs_bundle.json"
```
- **Fold `habits.json` → *Experiment Templates*** (deterministic): habitual launcher · framework/deps · base-model backbone · GPUs · failure memory (OOM hits, top error types). **Do NOT write hyperparameter values** (lr/batch/epochs/seed) — those are task-determined, decided by `/workplan`.
- **Fold `prefs_bundle.json` → *Workflow Preferences* W1–W7** (LLM-distill + user-confirm): cluster recurring candidates into 1-line preference statements, each with an evidence quote + why/how-to-apply; discard project-specific one-offs; **confirm each with AskUserQuestion before writing** (never write an unconfirmed preference).

**Phase 6 — Write `PROFILE_AUTO.md`** with sections: header (source/affiliation/stats/generated/publications + ⚠ if truncated) · Research Identity · Research Lineage · Writing Style · Experiment Templates · Workflow Preferences (W1–W7 table) · Publications Index (one row/paper with `task_type` + full-text availability) · BibTeX Bank. Then regenerate `PROFILE_AUTO.zh.md`.

**Phase 7 — Refresh**: `PROFILE_AUTO.md` records its generation date; re-run to refresh, **overwriting in place** but preserving/merging Experiment Templates and Tacit Knowledge (W2/W3 — a stop mid-crawl must not destroy the existing profile).

## Key rules
- **Google Scholar decides the paper list.** S2 only enriches; never adds/drops.
- **Stop on truncation.** A partial record poisons every downstream skill.
- **Label honestly.** Every `task_type` traces to title/venue/abstract; never invent publications or habits.
- **Descriptive, not a claim** — no autonomous accept/reject; a profile is data, optional light fidelity review only.
- **Network throttle ≠ no network.** When S2/arXiv-API return 429 in sandbox Bash, fall back to direct `arxiv.org/abs|pdf/<id>` (Bash) + `WebFetch`/`WebSearch` (harness net) per the Phase 2 recipe; mark the corpus honestly (`abstracts N/19`, `full-text N/19`) and note *why* in the header ⚠. Papers not on arXiv legitimately stay abstract-less — never fabricate.
