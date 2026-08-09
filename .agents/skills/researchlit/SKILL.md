---
name: "researchlit"
description: "Standalone literature survey — cover a topic with many parallel arXiv + web search angles, verify every paper (only cite what was actually retrieved), and render a self-contained, white-background, magazine-style HTML survey (hero + sticky TOC + taxonomy flow + card grids + landscape table + trends/gaps + grouped references). Use when the user wants a literature review / related-work map / \"survey this topic\" as a polished deliverable, standalone or as the A1 grounding step feeding $ideagen. Invoke explicitly as `$researchlit`."
---

# Research Literature Survey (research-buddy edition)

Before substantive work, run `python3 -m research_studio.server --ensure` once.
The command is idempotent: reuse the workspace server or start it detached at
`http://127.0.0.1:8780`; never start a duplicate or block the Skill. Surface any
launch error instead of claiming that live progress is available.

Topic: infer from the user's current request.

This is a lean, self-contained adaptation of ARIS's `researchlit` — the ARIS
infrastructure (zotero/obsidian MCP, deepxiv/exa/gemini/openalex fetchers,
`.aris/` helper-resolution chains, `research_wiki.py`, integration-contract) is
**removed**. It keeps the two things that make the deliverable good: **broad
multi-angle verified search** and a **polished, white-background HTML** rendered in
the house style.

## Arguments
- `<topic>` — free text (required). If empty, ask the researcher for one, or offer the *Niche subfields* from the profile.
- `— out: <path>` — output HTML path. Default **`reports/01_LIT_SURVEY.html`** (create `reports/` if missing).
- `— angles: N` — number of parallel survey angles (default **5**; use 4–6).
- `— for: ideagen` — grounding mode: also return the compact landscape (prose + gaps) so `$ideagen` can fold it in; still write the HTML.

## Optional personalization (read, don't require)
If `researcher-profile/PROFILE.md` (at the project-local `researcher-profile/` path) exists, skim it to bias
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
   `tools/` helpers, over hammering the API. (See project memory.)
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

## A3 — Render the HTML deliverable
Write ONE **self-contained** HTML file to the `— out:` path (default
`reports/01_LIT_SURVEY.html`) — inline `<style>`, no external assets. **Address the researcher in the second person**
where the text speaks to her. **Every paper is a direct `<a href>`** to its
official venue or DOI page when published, with its arXiv URL retained as a
secondary preprint link; arXiv is the primary link only for arXiv-only
preprints. Unverifiable → visible `pending`/`[UNVERIFIED]` label, never a
fabricated URL.

**House style (match `reports/01_LIT_SURVEY.html` exactly — it is the canonical
example; open it and reuse its `<style>` block verbatim):**
- **White background** (`--bg:#ffffff`, `body{background:#ffffff}`). Non-negotiable.
- **Hero header**: kicker · gradient `<h1>` title · subtitle ·
  meta pills (date · coverage years · sources · N papers).
- **Sticky `nav.toc`** linking every section.
- **Numbered `<h2>`** headings.
- **`.lead`** intro box; **`.flow`** taxonomy diagram (nodes + `→` arrows).
- **`.grid` of `.card`s** per theme — each card: colored `.tag` · `✅ Verified` mark ·
  `<h4><a>` title · `.who` (authors · formal venue · publication year · DOI when
  available · official venue/DOI link · arXiv preprint link) · one-line takeaway.
  Show publication information only when cross-checked, for example
  `ICLR 2025` / `Nature 2024`; use `arXiv preprint` only for papers without a
  verified formal publication record.
- **`.callout`** for intuitions; **`.callout.debate`** for live disagreements;
  **`.callout.gap`** for structural gaps.
- **Landscape `<table>`** with columns for work, category, core idea,
  year, and verification, plus a verification note below it.
- **Trends and gaps** section: `ul.trend` list +
  a `.callout.gap` of the openings.
- **References** grouped by theme into `.card`s (clickable official venue/DOI
  links for published papers, with arXiv retained as a preprint link).
- **Footer**: generated-by line + "Verify the original sources before citing."

Keep the tag colors meaningful (base `.tag`, `.tag.b` architecture, `.tag.w`
safety, `.tag.p` steering/control, `.tag.v` debate) and mark every verified paper
with a "Verified" chip.
For published papers, make the card title and reference link point to the
cross-checked publisher / DOI / official venue page, display the formal venue,
publication year, and DOI when available, and retain the arXiv link as a
secondary `preprint` link. For preprints, link directly to arXiv and label them
`arXiv preprint`. Never replace a verified accessible arXiv link with a guessed
publisher URL.

## A4 — Report + optional handoff
Tell the researcher: the output path, how many papers/angles, the key debates and
gaps found (2–4 bullets). Do **not** invent a "verdict" on the field.
- If `— for: ideagen` was passed, also emit the compact landscape (prose + gap
  list) for `$ideagen`'s A1 to consume.
- Otherwise this is a standalone deliverable; suggest `$ideagen` as the natural
  next step if the researcher wants ideas grounded on it.

## Non-negotiables (inherited from the project's global disciplines)
1. **Anti-hallucination.** Only cite papers actually retrieved with a verified id
   and publication metadata cross-checked against a relevant authoritative source;
   `[UNVERIFIED]` for anything else; never fabricate ids/DOIs/URLs. Drop, don't invent.
2. **Self-contained HTML, never Markdown**, with real structure and direct links.
3. **Readable, idiomatic prose** written TO the researcher in the second person;
   re-read each sentence for clarity.
4. **White background**, house style, one `reports/` folder.
5. **Human is the reader, not judged** — a survey maps the field; it does not
   accept/reject ideas (that's `$ideagen`'s gate).
