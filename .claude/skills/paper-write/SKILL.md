---
name: paper-write
description: Personalized paper writing from approved findings — fix a target conference and use its official LaTeX template + length limits, model section structure / lengths / tables on the researcher's OWN most-relevant paper (venue template only for format+limits), draw the Fig-1 model figure as an editable-PPT schematic via the figure-ppt skill, auto style-ref to the researcher's own voice, ≤3 self-citations, anti-self-plagiarism checks, section-by-section with human review, and compile the LaTeX to a PDF (fixing build errors). Orchestrates four review sub-skills — paper-theorization, paper-related-work, paper-gap-check, paper-logic-check — automatically inside its loop (each also invocable standalone). Use when the user wants to write, draft, or continue a research paper / section from their experiment results. Invocable as /paper-write.
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, WebSearch
---

Write / continue the paper described in the arguments passed when invoking this skill (a venue or section, optional). Read the **English** `aris-profile/PROFILE_AUTO.md` (via `$ARIS_PROFILE`) first — it is canonical (`PROFILE_AUTO.zh.md` is a human-facing Chinese mirror only, not for logic). Inputs: `outputs/03_EXPERIMENT_PLAN.html` (claims), `outputs/05_FINDINGS.html`, `results/`, figures. Converse with the researcher in **Chinese**, but write the **paper draft in the venue's language (English by default)** — do not translate the manuscript itself.

## Workflow — the steps in order (Step 0–8)

The researcher invokes `/paper-write` **once**; it runs Step 0–8 in this order and **calls the review
sub-skills itself** (theorization / related-work / gap-check / logic-check) and `figure-ppt` — she does
not call them by hand. Each step's detail lives in the section named in the arrow.

- **Step 0 — Venue, template, reference.** Fix the venue → fetch its official LaTeX template → pick the researcher's OWN paper at that venue as the structural reference → seed `budget.json` from its measured section shares. (→ *§Step 0*)
- **Step 1 — Theorization.** `/paper-theorization` decides the ONE formal spine and **mechanically verifies** it before any prose is written. (→ *§Review sub-skills · 1*)
- **Step 2 — Method + Experiments.** Write these first (habit); tables come from `results/`; figures = data plots via `paper/fig/make_figs.py` **plus the model figure via `figure-ppt`** (gpt draft → `buildshapes`, every element editable, page-wide `figure*`). (→ *§Discipline · Figures*)
- **Step 3 — Related Work.** `/paper-related-work` — broad search, **verify every arXiv id**, ≤3 self-cites. (→ *§Review sub-skills · 2*)
- **Step 4 — Intro + Abstract.** Gap-first Intro; Abstract written **last**. (→ *§Personalization*)
- **Step 5 — Compile.** `latexmk`; extract and fix real build errors. (→ *§Scaffold & compile*)
- **Step 6 — Deterministic gates.** `python3 tools/paper_checks.py all` — budget / style / length / formal / format / floats. (→ *§Deterministic gates*)
- **Step 7 — Gap-check + Logic-check.** `/paper-gap-check` (every claim → a `results/` file, never fabricate) then `/paper-logic-check` (a fresh sub-agent reads the compiled PDF as a hostile reviewer). (→ *§Review sub-skills · 3–4*)
- **Step 8 — Fix → recompile → re-check**, presenting each section at the **GATE** for the researcher (human is the judge; never self-declare "done"). (→ *§GATE*)

The sections below are the per-step reference material, not a second workflow.

## Step 0 — Target venue, template, and a reference paper (fix FIRST, before writing)

1. **Fix the target conference.** If not passed in the arguments, **AskUserQuestion** for the target venue (offer venues from her *Active Venues*: ACL/EMNLP/NeurIPS/ICML/ICLR/SIGIR…). The venue decides everything below, so never start writing before it is fixed.
2. **Use that venue's official template.** Fetch the venue's current LaTeX style (e.g. `acl.sty` + `\documentclass` for *ACL Rolling Review*, `neurips_2026.sty`, `iclr2026_conference.sty`) and scaffold `paper/` from it — do NOT hand-roll a generic `article`. Match the real class, margins, font, and section format.
3. **Respect the length / word limits.** Enforce the venue's page/word budget (e.g. ACL 8 pages + unlimited refs; NeurIPS 9 pages; ICLR 9–10). Track current length as sections accrete and flag when a section pushes over budget; do not silently overflow.
4. **Pick the researcher's OWN paper AT THE TARGET VENUE as the structural reference and STRICTLY conform to it** — venue match is the SELECTION criterion, not topic. From the *Publications Index* / `fulltext/` (the Index carries each paper's venue), take her own paper published at the target venue, or its nearest sibling if she has none at the exact venue (e.g. EMNLP↔ACL↔NAACL, NeurIPS↔ICML↔ICLR). Section structure, per-section length, and figure/table conventions are venue-shaped, so this is what makes the draft read like a paper of *that venue* in *her* hand. **If she has several papers at the venue, break the tie by topic/`task_type`/lineage closeness** (topic only ranks WITHIN the venue-matched set — it never pulls in a paper from a different venue). Do NOT borrow section structure from a non-venue paper. **State the chosen reference + why (which venue, which paper).** (Fall back to a representative accepted paper from the target venue ONLY if she has no own paper at the venue or any sibling.) The venue template (0.2) and length limit (0.3) still govern format.
   - **You MUST actually read its full text this run.** Her own papers are local in `$ARIS_PROFILE/fulltext/txt/<key>.txt` (no fetch needed); a venue-fallback paper you WebFetch (arXiv/anthology HTML). Never model structure "from memory" or from a generic template. If you cannot read the chosen reference, stop and say so; do not proceed on a guessed structure.
   - **Record a "Reference Conformance Block"** at the top of `main.tex` (as a comment) AND surface it to the researcher: the reference paper's real (a) ordered section/subsection list, (b) main-body **page count**, (c) figure list — count + what each depicts + which is Figure 1 + **each figure's POSITION/ORDER** (e.g. teaser at top of page 1, architecture/model figure beside the Method, results plots in Experiments), so the draft matches the reference's figure ORDER and placement and not only its count/kind — the model figure is defined in the Method section that introduces it, never dumped among the results floats, (d) table list — count + rows/cols of each, (e) **`figure_style`** — her figure conventions, so figures read like *hers*: **panel-label case** (e.g. lowercase `(a)/(b)` vs `(A)/(B)`), **caption format** (plain `Figure N: sentence.` vs a bold lead-in), **caption POSITION** — above vs below the float, measured **separately for figures and tables** but usually the same for both (this profile's reference puts BOTH below; feed it to the format gate as `--caption-pos below`), whether **acronyms are defined inline** in captions, **font family** (serif to match body), and the **colour palette** if a PDF is available to mine (if only extracted text is available, say so and use a restrained academic default rather than inventing one). This block is the evidence the step was done; skipping the fetch leaves it empty and visible.
   - **Match it strictly:** same section order and rough per-section length, **the same page count** (fill to it, do not stop at half the pages), the **same number and kind of figures** (if it has a threat-model diagram and an architecture figure, this paper has both), and result **tables laid out identically** (same rows=methods/attacks, cols=datasets/metrics, bold-best, ± std, caption style). Each of this paper's sections/figures/tables should map to a counterpart in the reference; note any deliberate deviation.
   - **Match per-section length, and MEASURE it from the reference — never guess a "class" band.** Run `python3 tools/paper_checks.py refshares --ref "$ARIS_PROFILE/fulltext/txt/<key>.txt"` to get the reference's real per-section word shares, record them in the Conformance Block, and **seed `budget.json` from THOSE measured numbers**. Do NOT set the Experiments target from a vibe like "empirical papers put ~34% in Experiments" — that guess is exactly how Experiments balloons to 3 pages when the reference's Experiments section is ~23% (≈2 pages). Allocate each section to the reference's measured share; a section much shorter than its counterpart is under-written (expand it), one much longer is over-written (move content out).
   - **Mirror how the reference SPLITS empirical content — do not dump everything into Experiments.** A table-heavy empirical reference typically carries a large **analysis section** (its "Understanding …" §) that holds the mechanism findings, per-layer/qualitative analysis, and diagnostic tables, plus a separate, leaner **Experiments** §. Put analysis-type material (mechanism validation, per-layer, sensitivity, cost analysis) in the analysis section, and keep Experiments for the head-to-head + ablations, so the analysis/Experiments proportion matches the reference rather than a single oversized Experiments block.
   - **"Page count" means the MAIN BODY (Intro through Conclusion/Ethics), excluding references and appendices.** The body must reach the reference's body length (e.g. an ACL long paper is ~8 body pages); references and appendices come *after* that and push the total higher. Do not count appendix or reference pages toward the body target, and do not let a short body hide behind a long appendix.
   - **Reach the page count with SUBSTANTIVE content, never filler.** Fill to the reference's length by adding the material a real paper of this scope carries — a formal method statement with an algorithm block and the loss/objective written out, per-layer / sensitivity / qualitative analysis subsections, a fuller related-work discussion, and appendices (implementation + hyperparameters, dataset construction, the localization/attack procedure in detail, additional result tables). Do NOT pad with restated sentences or vacuous prose. **This is a HARD delivery requirement, not a soft target: the final PDF MUST fill to the target body page count.** After every compile, read the `endconclusion` label page; while it is below the target the paper is UNDER-WRITTEN, so expand the body (one named subsection + its own float per `03` claim/experiment/ablation, plus per-layer / sensitivity / qualitative / cost analysis, a fuller Related Work, and body-eligible appendix material) and recompile, IN A LOOP, until the Conclusion ends at the bottom of the target page. Never present the paper as done while it is under-filled. Levers that add real page height without padding: give each `03` experiment its own subsection+float, split one big table into per-setting tables, add per-layer/sensitivity/qualitative tables, and include data figures at full `\columnwidth` (a bigger figure is legitimate height, see the Figures bullet). The only exception is a genuine shortfall AFTER every `03` experiment/claim/ablation has already been written as its own subsection + float, which you state explicitly at the gate.
   - **Dry-run figures: fill empty data-figure slots with clearly-labeled random data so they occupy real space.** When the venue reference has a figure/plot but this work has no real results yet (dry-run), do NOT leave the slot empty or a text box — generate the plot (pgfplots/matplotlib) with **synthetic/random values that follow the expected shape**, and mark it (caption or a visible tag) as dry-run/illustrative so it is swapped for real data later. This keeps the layout and page length faithful to the reference. (Architecture / concept diagrams are the exception — they are a schematic drawn by the `figure-ppt` skill, not random-data plots.)

## Personalization context (paper-write OWNS it; threaded to every sub-skill)

Personalization is decided ONCE, here, and **passed down** — the sub-skills must not each
re-derive it independently, or they drift out of sync with the main draft (e.g. two skills
each inserting "≤3" self-cites for six total, or `paper-theorization` grounding in a
different paper than the structural reference). When this skill invokes a sub-skill it
passes, and the sub-skill MUST honour over its own profile read, a **personalization
context**:

- **`reference_paper`** — the ONE own-paper structural reference chosen in Step 0.4 (its
  section structure, per-section length, table conventions, AND `figure_style` below).
  `paper-theorization` grounds its formal spine in *this* paper, not a separately-picked one.
- **`self_cite_budget`** — a single shared running count, cap ≤3 for the WHOLE paper. Every
  skill that adds a `\cite` to her own work draws from and decrements this one budget;
  `paper-related-work` does not open a second independent ≤3 cap.
- **`writing_style`** — her *Writing Style* (argument arc, contribution-bullet phrasing,
  register). Any sub-skill that writes prose (`paper-related-work`, the prose in
  `paper-theorization`) matches this voice, not a generic one.
- **`figure_style`** — her figure conventions mined in Step 0.4 (palette, panel-label case,
  caption format, font). Applied to the data plots via `paper/fig/make_figs.py` (a committed
  `fig/style.py`) and to the `figure-ppt` model figure (label case/font + palette). See the Figures bullets.
- **`anti_self_plagiarism`** — the final near-duplicate pass (§Personalization.3) runs over
  ALL body prose INCLUDING sub-skill output, not only the main-line sections.

`paper-logic-check` is the deliberate exception: narrative-logic checking is author-agnostic
and takes no personalization context. `paper-gap-check` uses only `reference_paper`'s
Experiment Templates for cost estimates.

## Personalization (from the profile)

1. **Auto style-ref** — with no explicit style instruction, align to *Writing Style* (argument arc gap-first vs landscape-first; contribution-bullet phrasing) AND mirror the structure of the researcher's own same-`task_type` high-cited papers.
2. **Self-citation** — `python3 tools/bib_manager.py selfcite --enriched "$ARIS_PROFILE/enriched.json" --draft paper/main.tex`; surface suggested own-paper cites for approval — **never auto-insert a `\cite`**. **Cap self-citations at ≤3 papers total, and only the most relevant** (genuine method/lineage/baseline overlap with this work); if the tool surfaces more, rank by relevance and propose only the top 3, dropping the rest. Do not pad the reference list with the researcher's own papers.
3. **Anti-self-plagiarism** — compare each new contribution-bullet / abstract sentence against the researcher's prior abstracts (`enriched.json`); flag near-identical sentences for rewrite, don't silently reuse.

## Discipline

- **Modular, section-by-section (W4)** — one section at a time, independently regenerable. Order honoring the habit: Method → Experiments → Intro/Related → Abstract last.
- **Every number traces to `results/`** — pull from real files; unverifiable → `[UNVERIFIED]`, never restate from memory.
- **Claims match the plan** — only claim what `/run-plan`'s gates marked supported.
- **Figures & tables follow the reference paper (Step 0.4).** Two kinds, handled differently:
  - **Data plots** (ablation curves, bars, heatmaps) — generate them with a **committed Python/matplotlib script** (e.g. `paper/fig/make_figs.py`) that reads `results/` and writes a **PDF per figure** into `paper/fig/`, then include with `\includegraphics{fig/<name>.pdf}` (do NOT hand-inline pgfplots as the deliverable). Keep the script in the repo so every figure regenerates from data. Every point traces to a result file; under dry-run the script uses clearly-labelled random data of the expected shape. **Call `fig.tight_layout()` (or `plt.tight_layout()`) before saving each data figure** so ticks, axis labels, and panel titles are never clipped. **Apply `figure_style` (the personalization context):** the script imports a committed `paper/fig/style.py` that sets her palette / serif font / panel-label convention, and captions follow her format (Step 0.4e), so the plots read like *her* figures rather than matplotlib defaults. **Figure text must be the venue BODY font size, never tiny.** Generate each figure at the exact physical width it is `\includegraphics`'d at, so it is placed 1:1 with no scaling: set matplotlib `figsize` width in inches EQUAL to the include width (`\columnwidth`≈3.32in per AAAI column) AND set `savefig.bbox='standard'` (NOT `'tight'` — a tight crop makes the output narrower than `figsize`, so `\includegraphics[width=\columnwidth]` then scales it UP and the text renders LARGER than the body). Include data figures at full `\columnwidth` (not `0.72\columnwidth`). Set the base font to **~9pt — slightly SMALLER than the body** (AAAI body is 10pt; figure text should read a touch smaller, like a caption, never tiny). A figure drawn at 5in but shown at 2.4in renders its 8pt labels at ~4pt, which is too small; a 1:1 figure at 9pt renders at 9pt. After compiling, eyeball a figure against the body text: figure text should be just slightly smaller.
  - **Architecture / method figure (the "model figure", usually Fig 2 after a motivation Fig 1)** — do NOT draw with matplotlib, and do NOT auto-author TikZ. **Invoke the `figure-ppt` skill.** Its mechanism: (1) a fixed "expert scientific-figure designer" meta-prompt is applied to the paper's Method text to GENERATE a **BioRender-style** image prompt; (2) an image model (gpt-image) draws the **imagery ONLY** (no text). (3) **use the gpt image as a design DRAFT and rebuild it as a FULLY-EDITABLE figure with `buildshapes`** — author `paper/fig/model_shapes.json` from the gpt draft as the visual guide, so EVERY element (icons as rounded-rects / ovals / hexagons, flows as arrows / connectors, text as boxes) is a native PPT shape that is individually editable. gpt is still used (it drafts the composition, so it is not abandoned), but the deliverable must have every element editable, so the `build` path (gpt raster background + editable labels only) is NOT enough — its icons stay a non-editable raster. **The model/architecture figure must be as WIDE as the text block — a `figure*` spanning BOTH columns** with `\includegraphics[width=\textwidth]{fig/model.pdf}`, never a single-column half-width include (as wide as the page, not just half). Set the `buildshapes` `canvas_in` to a full-width banner aspect (e.g. `[7.0, 2.4]`). **After building, READ the rendered PDF and confirm it is page-wide and nothing is clipped.** Pass `figure_style` (panel-label case, font, palette) from the personalization context. It is a BioRender-style schematic, NOT a flowchart of prose-filled boxes. **Flat design: no drop shadows, no gradients, no 3D bevels.** Until figure-ppt returns, leave the `\includegraphics{fig/model.pdf}` line commented with a one-line TODO. **Place the model figure's float in the source INSIDE the section that introduces it — the Method — immediately after the paragraph that first `\ref`s it, NOT beside the results floats.** LaTeX positions a float near where it is DEFINED, not where it is referenced, so a model figure `\ref`'d in the Method but its `\begin{figure*}` dropped among the Experiments tables renders a section too late. The `floats` gate (below) enforces this mechanically.
  - **Opening / motivation figure (Fig 1)** — **the first figure is a MOTIVATION / concept figure**, not a results preview: it shows the problem and the core idea (e.g. a direct harmful request refused vs. the same goal succeeding once wrapped in a literary style), placed at the top of page 1 and `\ref`'d from the Introduction. **Do NOT preview experimental results in the Introduction**; results live in Experiments as tables/plots. This holds even if the reference paper's own Fig 1 happens to be a results teaser. Build the motivation figure the same way as the model figure (gpt-image drafted, then rebuilt as fully-editable shapes via `buildshapes`, every element editable), but **single-column (half width)** since it sits in the intro column, not a full-width `figure*`.
  - **Result tables** — laid out like the venue reference (rows=methods/attacks, cols=datasets/metrics, bold-best, ± std over seeds), `booktabs`; every cell traces to `results/`. **Match the reference's table WIDTH:** if its main results table spans both columns (a wide `table*`), the main results table here is a `table*` too, not a cramped single-column table; make it a full, dense table (multiple models/attacks × defenses) rather than a small one. A number with no result file → `[UNVERIFIED]`, never a fabricated cell.
- **Refuse fabricated/synthetic inputs.** If `05_FINDINGS.html` / `results/` are watermarked SYNTHETIC or contain placeholder markers, say so and do NOT write them into the manuscript as real results; only proceed for an explicit dry-run and keep the `[SYNTHETIC]` marks visible in the draft.

## Review sub-skills (this skill orchestrates them — do NOT skip)

`paper-write` is the orchestrator. Four review sub-skills run **automatically inside
this skill's loop** (each is also invocable standalone as `/paper-<name>`). Do not make
the researcher call them by hand; call each at its point in the workflow, keep the
producer and the checker separate (spawn a fresh sub-agent for the checks that demand
it), and honour every honesty rail they enforce. **Pass each the personalization context
(above); the sub-skill honours it over its own profile read** — so the formal spine,
citations, prose voice, and figures stay consistent with the main draft.

1. **`paper-theorization`** — before writing the Method/Analysis prose, decide the
   paper's formal spine: ONE unified object + 2–4 load-bearing results, each gated on
   necessity/usefulness/unity and **mechanically checked** (Lean if present, else
   `python3 paper/theory/verify.py` via sympy/numeric) before it is written. Ground it
   in her closest theory-`task_type` paper; write none if the work cannot support real
   theory — never decorate. For an `engineering`/`benchmark` paper a light spine
   (one definition + one proposition) is usually the right amount.
2. **`paper-related-work`** — when writing Related Work: reuse `outputs/01_LIT_SURVEY.html`
   + her BibTeX Bank first, search only for gaps, **verify every newly-added arXiv id**,
   integrate under `\paragraph` subheadings (never a list dump), references filling
   ~2–4 columns. Enforces the ≤3 self-citation cap (§Personalization.2).
3. **`paper-gap-check`** — in the refinement loop: walk every claim, map it to a file in
   `results/`, and for each hole either reserve a clearly-labelled pending slot or write
   it into `paper/EXPERIMENT_PLAN.md`. **Never fabricate a number to fill a gap.** Under
   the current SYNTHETIC dry-run its job is to confirm every claim has a real structural
   slot and every synthetic float is visibly marked, then list the real experiments
   `/run-plan` must produce.
4. **`paper-logic-check`** — after a full draft compiles: build the section
   cross-reference map with `grep` (no external program), then **spawn a fresh
   sub-agent** to read the compiled PDF as a hostile reviewer and check each section's
   role, local support, understanding-cost, and that the Intro→Conclusion loop closes.
   Fix with bridge/signpost sentences; a genuine missing argument is routed back to
   `paper-gap-check`, not smoothed over.

**Order in the loop:** this is Step 1 → Step 7 of the *Workflow — the steps in order (Step 0–8)*
overview at the top of this skill: theorization (Step 1) → write Method/Experiments (Step 2) →
related-work (Step 3) → Intro/Abstract (Step 4) → compile (Step 5) → **deterministic gates** (Step 6,
below) → gap-check + logic-check (Step 7) → fix → recompile → re-check (Step 8). This is the agentic
half of the length-and-quality loop that sits alongside the mechanical compile/length-diff loop below.

## Deterministic gates (`tools/paper_checks.py` — the paperkit-equivalent, don't skip)

The agentic checks above are paired with **mechanical gates** so the draft cannot merely
*claim* venue-readiness. Run `python3 tools/paper_checks.py all --paper-dir paper
--venue-pages <N> --body-target <ref-body-pages> --caption-pos <below|above>` after each
compile (set `--caption-pos` to the reference's measured convention, Step 0.4e — this profile:
`below`); it emits JSON with an `ok` per check and exits non-zero until every gate is green:

- **budget** — per-section word-share vs `paper/budget.json` (±3%). Seed `budget.json` from the
  reference's **measured** per-section shares (`paper_checks.py refshares --ref <txt>`, Step 0.4)
  BEFORE drafting — never from a guessed "class" band. **Do NOT assume Experiments is the largest
  block:** in an analysis-driven paper (like this profile's reference) the mechanism/analysis
  section is the largest and Experiments is ~0.23; mirror the reference's split. **The Conclusion
  share is small** — the reference's conclusion is a short single paragraph (~2% of body), so cap
  it there; a fat Conclusion is a red flag, not length. It is the fixed target, re-checked after
  every content edit so expanding one section cannot silently steal proportion from another.
- **style** — LLM-tell budgets per 1k body words (em-dash/paren/`\textbf`/`\emph`), **zero
  contractions**, a body **equation floor** (≥4), and **no bullet/numbered lists in the body**
  (`\begin{itemize}`/`\begin{enumerate}` are flagged — write contributions and lists as prose,
  a paragraph with the points woven into sentences, the way a dense venue paper reads). Bold/
  italic are barred as body emphasis (headings exempt); a long section with no `\paragraph`
  subheading is flagged.
- **length** — judged by **WHERE THE CONCLUSION ENDS, not a page count**. The venue-counted
  content (Intro..Conclusion) must end **exactly at the bottom of the target page** (the ACL
  8th page): not a page earlier (under-written), not a page later (over the limit), and not
  mid-page (page 8 half-empty with Limitations/Ethics sharing it). Put `\label{paper:endconclusion}`
  at the very END of the Conclusion and `\label{paper:limstart}` right after `\section*{Limitations}`;
  the gate reads both from the `.aux`. It requires `endconclusion == target` AND `limstart == target+1`
  (Limitations pushed to the next page — where Limitations *starts* is the real signal that the
  Conclusion filled the target page; where Ethics *ends* does not prove it). **For a venue with NO
  Limitations section (e.g. AAAI), the gate detects the absence and requires `endconclusion == target`
  AND the References to START on page target+1** (found via `pdftotext`): if References share the target
  page, the Conclusion ended mid-page and the body is under-filled — add BODY content until References
  are pushed to the next page. A properly filled AAAI paper (Conclusion at the page bottom, References on
  the next page) turns the gate GREEN. `conclusion_not_at_page_bottom`
  means the counted content is slightly short. **CRITICAL — fill from the BODY, never by padding the
  Conclusion.** The Conclusion must mirror the reference's short length (see the budget cap); when it
  ends above the page bottom, add analysis/experiments content or MOVE a discussion paragraph into the
  analysis section — do NOT bloat the Conclusion with a practitioner checklist or recap to reach the
  page. A Conclusion visibly longer than the reference's is over-written, even if length is green.
  **Confirm visually** that the Conclusion's last line sits at the page bottom (total pages / a long
  appendix can never substitute for this).
- **formal** — `paper/theory/verify.py` (or a `.lean`) exists, body carries the equations,
  a derivations appendix is present (pairs with `paper-theorization`).
- **format** — no overfull hboxes (from the log), `\widowpenalty=\clubpenalty=10000` set,
  a dense/wide results table is a full-width `table*`, and **caption position matches the
  reference for figures AND tables** (`--caption-pos below|above`, measured in Step 0.4e). This
  profile's reference puts both figure and table captions BELOW — so `\caption` goes AFTER
  `\end{tabular}` (tables) and AFTER `\includegraphics` (figures); the gate flags any env whose
  caption is on the wrong side.
- **floats** — every figure/table is DEFINED in the source at/near the section that first `\ref`s it,
  and figures appear in first-reference order. Flags `float_defined_after_its_reference_section` (the
  model/architecture figure `\ref`'d in the Method but its `\begin{figure}` dropped among the results
  floats, so it renders a section too late) and `figures_out_of_first_reference_order`. This keeps
  text↔figure correspondence and the reference's figure ORDER, not just its count/kind.

**Never lower a threshold or edit `budget.json` to make a gate pass** — fix the paper. A
gate that is green only because the bar was moved is worse than an honest red. If a
requirement is genuinely unsatisfiable with honest content, say so at the GATE with the
specific shortfall (e.g. "body 6/8 pages after filling every substantive slot"). Thresholds
live at the top of `paper_checks.py`; tune them once for the venue, not per-draft to dodge a
failure.

## Scaffold & compile (paper/ must build)

1. **Scaffold on first run** — if `paper/` is absent, create it from the venue template: `main.tex` (venue `\documentclass` + section skeleton), `references.bib` (seed from her BibTeX Bank), and drop the venue `.sty`/`.cls` alongside. Never overwrite an existing `paper/` (W3); write new sections in place.
2. **Compile after each section (and at the end)** — run `latexmk -pdf -interaction=nonstopmode -halt-on-error paper/main.tex` (the toolchain is installed: `pdflatex`/`xelatex`/`latexmk`).
   - **Builds** → report "compiled, N pages" + the current-vs-limit page count (Step 0.3).
   - **Fails** → extract the real errors from `main.log` (missing package, undefined `\ref`/`\cite`, bad bib key) and fix them; do not leave a `main.tex` that does not build.
3. **Diff the compiled PDF against the reference paper — this is a required check, not optional.** Put `\label{paper:endconclusion}` at the END of the Conclusion and `\label{paper:limstart}` right after `\section*{Limitations}`; the length gate reads both from the `.aux`. **The primary length test is that the Conclusion ends exactly at the bottom of the target page** (`endconclusion == target` and `limstart == target+1`) — total pages, refs, and a long appendix can never substitute for this, and neither does a padded Conclusion: the page is filled by BODY content while the Conclusion stays as short as the reference's. Compare the rendered `main.pdf` to the reference's Conformance Block (Step 0.4) on: (a) **where the Conclusion ends** — the single most important axis, measured via the endconclusion label; (b) section order + per-section page share, **including that the Conclusion is no longer than the reference's**; (c) figure count/kind **and figure ORDER/POSITION — the model figure appears beside the Method it introduces (Fig 2 near §3), not after the results teaser; run `paper_checks.py floats`**; (d) table count/layout/width **and caption position (above/below, same for figures and tables)**. Report the diff explicitly (e.g. "BODY 6.5 / 8.0 pages, Experiments 3 thin paragraphs vs the reference's 5 subsections + 4 tables").
   - **If the body is short, the paper is UNDER-WRITTEN — and the usual cause is COMPRESSION, not missing experiments.** The `/workplan` deliverable (`outputs/03_EXPERIMENT_PLAN.html`) already designed the full claim set, systems, and **ablation matrix** — that is a whole paper's worth of experiments. A short body means you wrote each of them as one thin paragraph instead of the way the reference paper writes them: **one named subsection per claim/experiment/ablation, each with its own table or figure and a real analysis paragraph** (per-layer, sensitivity, qualitative examples, cost). Match the reference's **table/figure COUNT** (a table-heavy reference ⇒ this paper is table-heavy: split the one big results table into per-setting tables, add a per-layer table, a sensitivity table, a qualitative table). Pull every row of 03's claims table and ablation matrix into the body as its own float + prose. Recompile and re-diff.
   - **Do NOT reach for filler, and do NOT add experiments 03 did not design.** The length comes from writing up, densely, what 03 already specified. If after expanding every 03 experiment into its own subsection+float the body still falls short, that is a signal the *workplan* under-scoped the experiments — go back and note it — but first exhaust 03's existing content; the near-universal fix is density, not more experiments.
   - **Arrange the section layout UP FRONT so the length is reachable** — before drafting, allocate body sections + subsections + one float per 03 experiment against the reference's per-section shares (Step 0.4) so there is a real slot for every page; a paper that has no plan to fill the pages will not fill them. Body prose is continuous — **no bullet lists** (write contributions/enumerations as sentences).
4. **Float placement — no all-float page, order tracks the text.** Place each figure/table in the source **right after the paragraph that first references it**, never in a block at the end of a section. A block of floats dumped together cascades onto a **float-only page** (a page that is nothing but tables/figures) and breaks the reference order. Rules: (a) source order = first-reference order, so float numbers increase in the order the text discusses them; (b) single-column tables use `[tb]` (top OR bottom) so LaTeX can distribute them, wide `table*`/`figure*` use `[t]`; (c) after compiling, read float→page from the `.aux` (`\newlabel{tab:..}{{}{PAGE}}`) and the rendered PDF — if any page is all floats, or two+ floats stack with no text between them, move a float to its reference point or convert it to `[tb]`; (d) keep at most ~one wide float per page; (e) **every float must be DEFINED in the source at/near the section that first `\ref`s it, and figures must appear in first-reference order** — a float defined in a LATER section than its first reference (the classic case: the model/architecture figure `\ref`'d in the Method but its `\begin{figure}` left among the results floats) renders a section too late and breaks text↔figure correspondence. `python3 tools/paper_checks.py floats` flags `float_defined_after_its_reference_section` and `figures_out_of_first_reference_order` mechanically; it is part of `paper_checks.py all`. A page should read as prose interleaved with the float that supports it, the way the reference paper does.
5. **Output the PDF** — `paper/main.pdf` is a deliverable alongside the source, at the reference's body length (within the venue limit).

## Bibliography

`python3 tools/bib_manager.py check paper/references.bib` — surface duplicate / non-standard keys / missing fields. Prefer the researcher's own BibTeX Bank entries before fetching new ones.

## GATE (human is judge)

Present the draft **section by section** for the researcher's edits, each compiled so she reviews the rendered result, not raw source. **At each gate show the length-vs-reference diff (Scaffold & compile Step 3) AND the `paper_checks.py all` gate board** — body pages vs the reference's body pages, which sections are still short, and which deterministic gates (budget/style/length/formal/format) are red — so she sees how full and how conformant the paper is, not just that it builds. Do not declare the paper "done" — submission-readiness is their call. (An adversarial review is a separate, explicit request; default here is human review only.)

## Output

`paper/main.tex` + `paper/references.bib` + the venue `.sty`/`.cls` + compiled `paper/main.pdf` (venue template, within length limit, figures/tables modeled on the reference paper).
