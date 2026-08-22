## Arguments
- `<topic>` — free text (required). If empty, ask the researcher for one, or offer the *Niche subfields* from the profile.
- `— out: <path>` — output HTML path. Default **`reports/01_LIT_SURVEY.html`** (create `reports/` if missing).
- `— angles: N` — number of parallel survey angles (default **5**; use 4–6).
- `— for: ideagen` — grounding mode: also return the compact landscape (prose + gaps) so `$ideagen` can fold it in; still write the HTML.
- `— language: <target language>` — optional and **explicit-only**. When present, translate the completed English Survey through the configured LLM API. Do not infer translation merely from the language used in conversation.
- `— provider: openai|deepseek` — translation provider, used only with an explicit target language. If translation is requested and no provider was specified, ask the researcher which one to use; never infer it from available keys.

## Optional personalization (read, don't require)
If `researcher-profile/PROFILE.html` (at the project-local `researcher-profile/` path) exists, skim it to bias
*angle selection* toward the researcher's niche and to name where her own work
sits in the landscape — but the survey itself stays **field-neutral and honest**
(this is a map of the field, not a pitch). If the profile is absent, proceed
anyway; this skill does not depend on it.

## A1 — Multi-angle verified search (the core)
Cover the topic with **many distinct query angles, run in PARALLEL** — so the
researcher doesn't miss the landscape, real coverage usually means **30–60 papers**,
not a handful. Breadth here is in service of a complete map for the researcher, not
volume for its own sake. Do NOT do one or two searches.

1. **Decompose** the topic into `— angles: N` (default 5) non-overlapping angles.
   Adapt to the topic; a typical decomposition: **① foundations/architectures ·
   ② dominant methods · ③ geometry/theory/mechanism · ④ evaluation/limitations ·
   ⑤ safety/robustness/applications**. Name the angles before searching.
2. **Fan out one search agent per angle** with Codex `spawn_agent`; launch all angle tasks before waiting so they run concurrently. Each agent:
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

> Prefer delegating the searches to agents so raw search dumps stay out of the
> main context — you keep the merged, verified paper list, not the transcripts.

## A2 — Synthesize the landscape
Over the merged set, do interpretive (not accept/reject) synthesis:
- **Group** papers into ~5–7 themes mirroring the angles.
- Find the **live debates** (papers that directly disagree) — these make the best
  callouts.
- Find the **structural gaps** (thin/empty sub-areas) — flag them explicitly; a
  gap is a valuable signal, worth more than padding.
- Identify **trends** across the 2–3 year window.
