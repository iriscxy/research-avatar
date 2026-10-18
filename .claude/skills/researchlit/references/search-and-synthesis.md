## Arguments
- `<topic>` — free text (required). If empty, ask the researcher for one, or propose 2–3 broad directions from the profile's *Research Identity* and *Research Lineage*.
- `— questions: personalized` — also write 2–4 personalized questions (`personalized_directions`) from the same evidence plus the profile (see the SKILL's Research questions section). Neutral questions are always written.
- `— out: <path>` — output HTML path. Default **`reports/01_LIT_SURVEY.html`** (create `reports/` if missing).
- `— angles: N` — number of parallel survey angles (default **5**; use 4–6).
- `— for: ideagen` — grounding mode: also return the compact landscape (prose + gaps) so `/ideagen` can fold it in; still write the HTML.
- `— language: <target language>` — optional. When present, translate the completed English Survey through the configured LLM API.
- `— provider: openai|deepseek` — translation provider, used with a target language. If translation is requested and no provider was specified, ask the researcher which one to use; never infer it from available keys.

## Profile use (read, don't require)
If `researcher-profile/PROFILE.html` exists, read only *Research Identity* and
*Research Lineage* to propose broad directions when no topic was given, to name
where the researcher's own work sits in the landscape, and, with
`— questions: personalized`, to write the personalized questions. Angle
selection, searches, synthesis, gaps, and neutral questions do not use the
profile, so the survey stays a field-neutral map shared by personalized and
non-personalized runs. If the profile is absent, proceed anyway.

## A1 — Multi-angle verified search (the core)
Cover the topic with **many distinct query angles, run in PARALLEL** — so the
researcher doesn't miss the landscape, real coverage usually means **30–60 papers**,
not a handful. Breadth here is in service of a complete map for the researcher, not
volume for its own sake. Do NOT do one or two searches.

1. **Decompose** the topic into `— angles: N` (default 5) non-overlapping angles.
   Adapt to the topic; a typical decomposition: **① foundations/architectures ·
   ② dominant methods · ③ geometry/theory/mechanism · ④ evaluation/limitations ·
   ⑤ safety/robustness/applications**. Name the angles before searching.
2. **Fan out one search agent per angle** with the Agent tool; launch all angle tasks before waiting so they run concurrently. Each agent:
   - Uses web search + web open/fetch on `arxiv.org` across its angle, hitting sub-topics
     separately, until fresh queries stop surfacing new work (saturation).
   - Returns, per paper: exact **title · arXiv id (or DOI) · year · one-line
     takeaway** (method + key finding/limitation). For each paper, also
     cross-check publication status against the relevant **ACL Anthology,
     OpenReview, DBLP, conference/journal official website, and DOI record**
     when applicable, and return the verified **venue · publication year · DOI
     · official venue/DOI URL · arXiv URL as a preprint fallback**. Record
     `arXiv preprint` only when no formal publication record is found; never
     infer a venue, year, DOI, or URL.
   - **Anti-hallucination (hard rule):** report ONLY papers actually retrieved and
     whose id it saw on the page; anything unsure → mark `[UNVERIFIED]`, **never
     fabricate** an id/DOI/title. Drop unverifiable leads rather than list them.
   - Run a separate recency lane covering the current year and previous year,
     including arXiv-only work. Family quotas never replace this lane. Record
     the exact recency queries and search date, and explicitly report when it
     returns no verified paper.
3. **Sandbox note:** sandboxed Bash throttles the S2/arXiv **API** (HTTP 429).
   Prefer direct `arxiv.org/abs/<id>` / `arxiv.org/pdf/<id>` + web open/fetch, or the
   `research_avatar/tools/` helpers, over hammering the API. (See project memory.)
4. **Merge + de-duplicate** across angles by arXiv id (fallback: normalized
   title). Keep one canonical row per paper; note which angle(s) surfaced it.
   Preserve the cross-checked publication metadata and distinguish a formally
   published paper from an arXiv-only preprint. If sources disagree, retain
   the disagreement for the verification note and do not resolve it by guesswork.
   When several papers cover the same point, prefer peer-reviewed / published work
   and higher-cited work as the representative citation. Keep recent preprints when
   they are materially newer or uniquely relevant; publication status and citation
   count are prioritization signals, not a reason to erase relevant new work.
5. Before declaring a gap, run a **gap-falsification search** using the proposed
   missing mechanism as an exact phrase, its main synonyms, and combinations
   with the task and intervention. Search specifically for work that would make
   the gap false. Retain the queries in the canonical source;
   “no paper in the selected families” is not novelty evidence.

> Prefer delegating the searches to agents so raw search dumps stay out of the
> main context — you keep the merged, verified paper list, not the transcripts.

## A2 — Synthesize the landscape
Over the merged set, do interpretive (not accept/reject) synthesis:
- **Group** papers into ~5–7 themes mirroring the angles.
- Find the **live debates** (papers that directly disagree) — these make the best
  callouts.
- Find the **structural gaps** (thin/empty sub-areas) — flag them explicitly; a
  gap is a valuable signal, worth more than padding. Summarize the open
  problem areas as 3–5 research questions (keyword titles only) as
  the SKILL specifies; the gaps stay in the synthesis as their evidence.
- Identify **trends** across the 2–3 year window.
