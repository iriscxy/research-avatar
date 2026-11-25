## Preflight: a COMPLETE Scholar page
Scholar serves ~20 papers initially; the rest load on **"Show more"**, and `Cmd+S` saves the
truncated source. Get a complete page (DevTools → Copy outerHTML into a `.html`, or `--from-tab`).
The helper **detects truncation** and emits `truncated: true` + a `warning`; **if truncated, STOP
and tell the user to expand fully and re-export** — never profile on a partial record.

### Research Studio terminal entry

Run `/profileconstruct` in the terminal with the fully expanded `.html`/`.htm` path. Research Studio only provides copy/open-terminal controls and serves the resulting `PROFILE.html` plus `publications.json`; it must not upload Scholar HTML, run this Skill in a web-server background process, duplicate its logic, or maintain a second profile state. `PROFILE.html`, `publications.json`, and `fulltext/` are the only canonical outputs.

## Pipeline (cheap/deterministic first — W1; cache & never clobber — W2/W3)

All artifacts are built under the in-repo `researcher-profile/` path. The **final directory has a strict whitelist**:

- `PROFILE.html`
- `publications.json`
- `profile_pairs.json`
- `fulltext/` (both `pdf/` and extracted `txt/`)

Temporary `gs.json`, `arxiv_abs.json`, and status manifests may exist only during a run and **must be deleted before completion**. Put diagnostic/status manifests in a system temporary directory when possible.

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

**Phase 4 — Infer identity + profiles**: **Research Identity and Research Lineage come from the abstracts and metadata of every Scholar row** (title, year, venue, co-authors, citation count); they need no full text, so a row without a PDF still contributes. Identity covers Niche Subfields (ranked by recent volume × recency) · Dominant Methods · Active Venues (last 3y) · Signature Works. Each Identity list has at most 5 items, and each Identity paragraph stays under 80 words; Lineage traces origin → evolution → frontier by year, with exactly one entry (one title) per year; merge all of a year's threads into that entry. The Idea and Writing Profiles use the full texts as described below.

**The Writing Profile must capture two layers** (an abstract-only writing profile is incomplete — it misses how the researcher writes a whole paper):
- **Abstract-level** (from the abstracts in `publications.json`): argument arc (gap-first vs landscape-first), two-/N-challenge framing, method-naming habit, mechanism-intro phrasing, closing/evaluation cadence, contribution-bullet phrasing.
- **Whole-paper-level** (from `fulltext/txt/`): read the **same papers used for the pairs** — the 8 most recent papers on which the researcher is first or last author (all of them if fewer than 8), or exactly the set the researcher selects — not just their abstracts. Analyze **section organization** (which sections, in what order, typical lengths) · **Introduction structure** (the role each paragraph plays — hook → gap → approach → contributions list) · **Related Work organization** (thematic vs chronological; how many subsections) · **Method presentation** (subsection-per-module naming, notation conventions, how a module is introduced then formalized) · **paragraph rhetoric** (topic-sentence habits, transition words, how claims are hedged/qualified) · **table/figure conventions** (caption style, what Fig 1 usually is, table density) · **Limitations / Conclusion patterns**. Record these as concrete, reusable observations tied to example papers, so the browser writing API can match structure and cadence at the section level, not only the abstract. Record exactly those papers in `writing_style_papers`. If any of them lacks a verified full text, continue the acquisition ladder; never substitute another paper or abstract-only evidence.

For the Idea, Abstract, and Introduction profiles, follow [paired-profile-construction.md](paired-profile-construction.md) for the 8 most recent papers on which the researcher is first or last author (all of them if fewer than 8). `demo_paper/jinghui_prompt.md` is the authoritative task/setting/input specification. First extract the author's actual version and a task-matched input; generate a real model counterpart in a fresh context without the original or author context; then compare the two and save task-specific `author_differences`. Idea reconstruction receives only `research_question`; Abstract/Introduction reconstruction receives only a factual `content_brief` and verified `references`. The reconstruction uses setting `None`; the completed differences become input for the later Profile setting. Do not supply an existing profile when constructing its baseline counterpart. Save exact inputs, original and generated versions, accepted comparisons, model/context provenance, and validation under the paper's `bibtex_key` in `profile_pairs.json`. If the paired generation is missing or not isolated, this stage is incomplete. There is no direct observed-tendencies fallback.

For the rest of the Writing Profile, inspect the exact heading hierarchy in the selected full papers and synthesize each organization's profile directly from those full texts; do not build paired comparisons for these sections. Group observations by organization (for example, Method or Experiments) and use the actual subsection headings for matching. Do not force a universal subsection taxonomy. Describe organization, paragraph progression, evidence use, naming/notation, and transitions only where the full texts support them, citing the papers. Keep observations conditional on the paper type and preserve contrary examples. Do not copy prior sentences or generate a Markdown profile, second profile, or style-guide file.

Downstream writing must retrieve only the Abstract profile for an abstract, only the Introduction profile for an introduction, or the profile matching the current organization and heading for another section. For Jinghui Profile-mode input, build the request with `research_avatar/tools/jinghui_prompt.py`, which retrieves the matching `author_differences` records most similar to the current factual input and applies the exact task/setting/rule assembly from the source. The paper-writing interface must not include the entire Writing Profile when a matching profile is available. If there is no match, provide no unrelated profile and follow the approved outline and evidence.

Render the Writing Profile with `Abstract`, `Introduction`, and each observed organization name as direct green headings. Order `section_profiles` as the author's papers order their sections: rank each organization by its typical position (median relative position of its headings across the selected full texts, with main-text sections before appendix-only ones), so the Writing Profile reads Abstract, Introduction, then the remaining organizations in the author's usual paper order. Never order them by frequency, salience, or the order they were analyzed. Do not add a generic “Section-specific writing profiles” wrapper or display process labels such as “Observed section names.” This is a general renderer rule for every researcher profile, not a researcher-specific exception.
Use the author's actual subsection headings internally to infer and route style, but do not print a raw inventory of those headings in the profile. Present the synthesized prose under its organization heading.
