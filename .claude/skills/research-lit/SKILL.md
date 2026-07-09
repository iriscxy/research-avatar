---
name: research-lit
description: Standalone literature survey — cover a topic with many parallel arXiv + web search angles, verify every paper (only cite what was actually retrieved), and render a self-contained, white-background, magazine-style HTML survey (hero + sticky TOC + taxonomy flow + card grids + landscape table + trends/gaps + grouped references) in the language the user asks for. Use when the user wants a literature review / related-work map / "survey this topic" as a polished deliverable, standalone or as the A1 grounding step feeding /ideagen. Invocable as /research-lit.
argument-hint: [topic]  ·  — out: <path>  ·  — angles: N  ·  — lang: <code>
allowed-tools: Bash(*), Read, Write, Grep, Glob, WebSearch, WebFetch, Agent, AskUserQuestion
---

# Research Literature Survey (research-buddy edition)

Topic: **$ARGUMENTS**

This is a lean, self-contained adaptation of ARIS's `research-lit` — the ARIS
infrastructure (zotero/obsidian MCP, deepxiv/exa/gemini/openalex fetchers,
`.aris/` helper-resolution chains, `research_wiki.py`, integration-contract) is
**removed**. It keeps the two things that make the deliverable good: **broad
multi-angle verified search** and a **polished, white-background HTML** rendered in
the house style, **written in the language the user asks for** (global language
policy — never hard-coded). Keep code / identifiers / paper-titles native (English).

## Arguments
- `<topic>` — free text (required). If empty, ask the researcher for one, or offer the *Niche subfields* from the profile.
- `— out: <path>` — output HTML path. Default **`outputs/01_LIT_SURVEY.html`** (create `outputs/` if missing).
- `— angles: N` — number of parallel survey angles (default **5**; use 4–6).
- `— lang: <code>` — output language (e.g. `zh`, `en`). If omitted, follow the global language policy: use the language of the user's request; if genuinely ambiguous, ask. **Never pre-decide the language.**
- `— for: ideagen` — grounding mode: also return the compact landscape (prose + gaps) so `/ideagen` can fold it in; still write the HTML.

## Optional personalization (read, don't require)
If `aris-profile/PROFILE_AUTO.md` (via `$ARIS_PROFILE`) exists, skim it to bias
*angle selection* toward the researcher's niche and to name where her own work
sits in the landscape — but the survey itself stays **field-neutral and honest**
(this is a map of the field, not a pitch). If the profile is absent, proceed
anyway; this skill does not depend on it.

## A1 — Multi-angle verified search (the core)
Cover the topic with **many distinct query angles, run in PARALLEL** — a real
survey is typically **30–60 papers**, not a handful. Do NOT do one or two
searches.

1. **Decompose** the topic into `— angles: N` (default 5) non-overlapping angles.
   Adapt to the topic; a typical decomposition: **① foundations/architectures ·
   ② dominant methods · ③ geometry/theory/mechanism · ④ evaluation/limitations ·
   ⑤ safety/robustness/applications**. Name the angles before searching.
2. **Fan out one search agent per angle** (Agent tool, `subagent_type:
   general-purpose`, all in ONE message so they run concurrently). Each agent:
   - Uses WebSearch + WebFetch on `arxiv.org` across its angle, hitting sub-topics
     separately, until fresh queries stop surfacing new work (saturation).
   - Returns, per paper: exact **title · arXiv id (or DOI) · year · one-line
     takeaway** (method + key finding/limitation).
   - **Anti-hallucination (hard rule):** report ONLY papers actually retrieved and
     whose id it saw on the page; anything unsure → mark `[UNVERIFIED]`, **never
     fabricate** an id/DOI/title. Drop unverifiable leads rather than list them.
3. **Sandbox note:** sandboxed Bash throttles the S2/arXiv **API** (HTTP 429).
   Prefer direct `arxiv.org/abs/<id>` / `arxiv.org/pdf/<id>` + WebFetch, or the
   `tools/` helpers, over hammering the API. (See project memory.)
4. **Merge + de-duplicate** across angles by arXiv id (fallback: normalized
   title). Keep one canonical row per paper; note which angle(s) surfaced it.

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
`outputs/01_LIT_SURVEY.html`) — inline `<style>`, no external assets. **Generate
the prose DIRECTLY in the user's chosen language** (global language policy — never
hard-coded; write it natively, not machine-translated; keep paper titles / code /
identifiers in English). **Localize the section labels and the `lang`/font
attributes to that language.** **Address the researcher in the second person**
where the text speaks to her. **Every paper is a direct `<a href>`** to its
arXiv/DOI page; unverifiable → visible `pending`/`[UNVERIFIED]` label, never a
fabricated URL.

**House style (match `outputs/01_LIT_SURVEY.html` exactly — it is the canonical
example; open it and reuse its `<style>` block verbatim):**
- **White background** (`--bg:#ffffff`, `body{background:#ffffff}`). Non-negotiable.
- `lang` + font stack match the chosen language (the example file is `zh-CN` with
  PingFang SC / Microsoft YaHei; adapt for other languages).
- **Hero header**: `LITERATURE SURVEY` kicker · gradient `<h1>` title · English
  subtitle · meta pills (📅 date · 📚 coverage years · 🔍 sources · 🧩 N papers).
- **Sticky `nav.toc`** linking every section.
- **Numbered Chinese `<h2>`** headings, each with an English `<span class="en">`.
- **`.lead`** intro box; **`.flow`** taxonomy diagram (nodes + `→` arrows).
- **`.grid` of `.card`s** per theme — each card: colored `.tag` · `✅ 已核实` mark ·
  `<h4><a>` title · `.who` (authors · year) · one-line Chinese takeaway.
- **`.callout`** for intuitions; **`.callout.debate`** for live disagreements;
  **`.callout.gap`** for structural gaps.
- **Landscape `<table>`** (工作 · 类别 · 核心思路 · 年份 · 核实) with a `.disc`
  **核实说明** below it (how ids were verified; note 26xx = 2026 preprints).
- **趋势与空白** section: `ul.trend` list + a `.callout.gap` of the openings.
- **References** grouped by theme into `.card`s (clickable arXiv links).
- **Footer**: generated-by line + "引用前请核对原文".

Keep the tag colors meaningful (base `.tag`, `.tag.b` architecture, `.tag.w`
safety, `.tag.p` steering/control, `.tag.v` debate) and mark every verified paper
with a "verified" chip. (The `✅ 已核实` / 核实说明 / 趋势与空白 labels shown in the
example file are the zh rendering — translate all such labels to the chosen language.)

## A4 — Report + optional handoff
Tell the researcher: the output path, how many papers/angles, the key debates and
gaps found (2–4 bullets). Do **not** invent a "verdict" on the field.
- If `— for: ideagen` was passed, also emit the compact landscape (prose + gap
  list) for `/ideagen`'s A1 to consume.
- Otherwise this is a standalone deliverable; suggest `/ideagen` as the natural
  next step if the researcher wants ideas grounded on it.

## Non-negotiables (inherited from the project's global disciplines)
1. **Anti-hallucination.** Only cite papers actually retrieved with a verified id;
   `[UNVERIFIED]` for anything else; never fabricate ids/DOIs/URLs. Drop, don't invent.
2. **Self-contained HTML, never Markdown**, with real structure and direct links.
3. **Native, idiomatic prose in the user's chosen language** (global policy — never
   hard-coded) — written TO the researcher in the second person, never a word-for-word
   machine translation; re-read each sentence for readability.
4. **White background**, house style, one `outputs/` folder.
5. **Human is the reader, not judged** — a survey maps the field; it does not
   accept/reject ideas (that's `/ideagen`'s gate).
