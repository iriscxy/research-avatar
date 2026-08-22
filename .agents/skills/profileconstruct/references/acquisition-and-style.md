## Preflight: a COMPLETE Scholar page
Scholar serves ~20 papers initially; the rest load on **"Show more"**, and `Cmd+S` saves the
truncated source. Get a complete page (DevTools → Copy outerHTML into a `.html`, or `--from-tab`).
The helper **detects truncation** and emits `truncated: true` + a `warning`; **if truncated, STOP
and tell the user to expand fully and re-export** — never profile on a partial record.

### Research Studio terminal entry

Run `$profileconstruct` in the terminal with the fully expanded `.html`/`.htm` path. Research Studio only provides copy/open-terminal controls and serves the resulting `PROFILE.html` plus `publications.json`; it must not upload Scholar HTML, run this Skill in a web-server background process, duplicate its logic, or maintain a second profile state. `PROFILE.html`, `publications.json`, and `fulltext/` are the only canonical outputs.

## Pipeline (cheap/deterministic first — W1; cache & never clobber — W2/W3)

All artifacts are built under the in-repo `researcher-profile/` path. The **final directory has a strict whitelist**:

- `PROFILE.html`
- `publications.json`
- `fulltext/` (both `pdf/` and extracted `txt/`)

Temporary `gs.json`, `arxiv_abs.json`, `habits.json`, `prefs_bundle.json`, and status manifests may exist only during a run and **must be deleted before completion**. Put diagnostic/status manifests in a system temporary directory when possible.

**Phase 1 — Read Scholar** → `gs.json`
```bash
python3 research_avatar/tools/scholar_profile.py --from-html "<exported.html>" > "researcher-profile/gs.json"
# or: python3 research_avatar/tools/scholar_profile.py --from-tab > "researcher-profile/gs.json"
```
Read the JSON. If `truncated` is true, surface the `warning` and stop. If `error`, surface it and stop.

**Phase 2 — Enrich (abstracts + DOIs + BibTeX)** → `publications.json`
```bash
python3 research_avatar/tools/profile_enrich.py --input "researcher-profile/gs.json" --output "researcher-profile/publications.json"
python3 research_avatar/tools/fetch_fulltext.py --enriched "researcher-profile/publications.json" --outdir "researcher-profile/fulltext" --delay 2
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
curl -sL -m40 -o "researcher-profile/fulltext/pdf/<key>.pdf" "https://arxiv.org/pdf/<id>"
```
Loop over all on-arXiv papers with a `sleep 2` between downloads. `fetch_fulltext.py` stops at `pdf_ready_for_agent`; it must not manufacture TXT through a local parser.

**Full text must be extracted by the executing code agent itself.** Open the original PDF with the agent's document/vision capability and transcribe it page by page in semantic reading order. Rendering pages for the agent to inspect is allowed; feeding those pages to OCR, `pdftotext`, `pypdf`, a separate LLM API, or another automatic text extractor is not. The transcript must preserve wording, headings, captions, appendices, and references; reconstruct discretionary line-wrap hyphens; finish the left column before the right; and keep sentences and natural paragraphs intact across column and page boundaries. Write the completed transcript transactionally to `fulltext/txt/<key>.txt`, then set that publication's `fulltext_extractor` to `code_agent` in `publications.json`. Before accepting a transcript, inspect representative boundaries from the Introduction, Related Work, every page transition, and the Conclusion/Limitations. Reject and redo any transcript containing paragraph openings or endings that are visibly mid-sentence.

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
- **Whole-paper-level** (from `fulltext/txt/`): read **exactly 15 unique representative full papers**, not just their abstracts. Select them to cover the researcher's major subfields, engineering/theory/benchmark contribution types, earlier/recent periods, and signature/recent work; do not simply take the first 15 downloads. Analyze **section organization** (which sections, in what order, typical lengths) · **Introduction structure** (the role each paragraph plays — hook → gap → approach → contributions list) · **Related Work organization** (thematic vs chronological; how many subsections) · **Method presentation** (subsection-per-module naming, notation conventions, how a module is introduced then formalized) · **paragraph rhetoric** (topic-sentence habits, transition words, how claims are hedged/qualified) · **table/figure conventions** (caption style, what Fig 1 usually is, table density) · **Limitations / Conclusion patterns**. Record these as concrete, reusable observations tied to example papers, so the browser writing API can match structure and cadence at the section level, not only the abstract. Head the section by stating it was mined from BOTH abstracts and exactly 15 full papers, listing all 15 unique publication keys. If fewer than 15 verified full texts are available, continue the acquisition ladder; never silently lower the sample count or substitute abstract-only evidence.

Write the detailed, operational style analysis directly inside the **`PROFILE.html` Writing Style section**. It must record its evidence base and include: quantitative abstract tendencies; core voice; abstract blueprint; paragraph-by-paragraph Introduction architecture; Related Work organization; Method/notation/naming conventions; experiment narrative and result-paragraph pattern; figure/table/caption conventions; paragraph/sentence mechanics; limitations/ethics/conclusion patterns; engineering/theory/benchmark variants; anti-imitation safeguards; and a drafting checklist. Tie observations to representative local full texts, distinguish measured tendencies from hard rules, and match structure/cadence without copying prior sentences. Do not generate any Markdown profile, second profile, or style-guide file.

**Phase 5 — Tacit knowledge (optional, non-blocking)**: reviewer-pushback themes / experiments they refuse to redo / recurring pitfalls seed *Known Dead-Ends*. You MAY ask the researcher for these if she is present, but this does NOT gate profile generation — if she doesn't supply them, seed *Known Dead-Ends* from the mined history + publications and move on. Never block the profile on an interview or a confirmation.

**Phase 6 — Mine available coding-agent history (ONCE, here; downstream never re-mines).** Prefer `.aris/meta/events.jsonl`. Claude transcripts may also be included when present; do not assume Codex session JSON is compatible with `workflow_prefs.py`:
```bash
python3 research_avatar/tools/experiment_history.py --events .aris/meta/events.jsonl --output "researcher-profile/habits.json"
