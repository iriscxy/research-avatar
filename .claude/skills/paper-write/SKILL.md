---
name: paper-write
description: Personalized paper writing from approved findings — fix a target conference and use its official LaTeX template + length limits, model structure and figures/tables on a real accepted paper from that venue, auto style-ref to the researcher's own voice, ≤3 self-citations, anti-self-plagiarism checks, section-by-section with human review, and compile the LaTeX to a PDF (fixing build errors). Use when the user wants to write, draft, or continue a research paper / section from their experiment results. Invocable as /paper-write.
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, WebSearch
---

Write / continue the paper described in the arguments passed when invoking this skill (a venue or section, optional). Read the **English** `aris-profile/PROFILE_AUTO.md` (via `$ARIS_PROFILE`) first — it is canonical (`PROFILE_AUTO.zh.md` is a human-facing Chinese mirror only, not for logic). Inputs: `outputs/02_EXPERIMENT_PLAN.html` (claims), `outputs/05_FINDINGS.html`, `results/`, figures. Converse with the researcher in **Chinese**, but write the **paper draft in the venue's language (English by default)** — do not translate the manuscript itself.

## Step 0 — Target venue, template, and a reference paper (fix FIRST, before writing)

1. **Fix the target conference.** If not passed in the arguments, **AskUserQuestion** for the target venue (offer venues from her *Active Venues*: ACL/EMNLP/NeurIPS/ICML/ICLR/SIGIR…). The venue decides everything below, so never start writing before it is fixed.
2. **Use that venue's official template.** Fetch the venue's current LaTeX style (e.g. `acl.sty` + `\documentclass` for *ACL Rolling Review*, `neurips_2026.sty`, `iclr2026_conference.sty`) and scaffold `paper/` from it — do NOT hand-roll a generic `article`. Match the real class, margins, font, and section format.
3. **Respect the length / word limits.** Enforce the venue's page/word budget (e.g. ACL 8 pages + unlimited refs; NeurIPS 9 pages; ICLR 9–10). Track current length as sections accrete and flag when a section pushes over budget; do not silently overflow.
4. **Pick ONE representative accepted paper from that venue and STRICTLY conform to it** (prefer one close to this work's `task_type`, ideally from her lineage or the plan's closest-work list).
   - **You MUST actually fetch and read it this run** (WebFetch the arXiv/anthology HTML) — never model structure "from memory" or from a generic template. If you cannot fetch it, stop and say so; do not proceed on a guessed structure.
   - **Record a "Reference Conformance Block"** at the top of `main.tex` (as a comment) AND surface it to the researcher: the reference paper's real (a) ordered section/subsection list, (b) main-body **page count**, (c) figure list — count + what each depicts + which is Figure 1, (d) table list — count + rows/cols of each. This block is the evidence the step was done; skipping the fetch leaves it empty and visible.
   - **Match it strictly:** same section order and rough per-section length, **the same page count** (fill to it, do not stop at half the pages), the **same number and kind of figures** (if it has a threat-model diagram and an architecture figure, this paper has both), and result **tables laid out identically** (same rows=methods/attacks, cols=datasets/metrics, bold-best, ± std, caption style). Each of this paper's sections/figures/tables should map to a counterpart in the reference; note any deliberate deviation.
   - **Match per-section length, not just the total.** Record the reference's per-section page share in the Conformance Block (e.g. Intro ~1pg, Related ~0.75pg, analysis ~2pg, method ~1.5pg, experiments ~2pg, +limitations/ethics, appendices to fill the rest) and allocate each of this paper's sections to roughly the same share. A section that is much shorter than its counterpart is under-written; expand it with real content before moving on.
   - **"Page count" means the MAIN BODY (Intro through Conclusion/Ethics), excluding references and appendices.** The body must reach the reference's body length (e.g. an ACL long paper is ~8 body pages); references and appendices come *after* that and push the total higher. Do not count appendix or reference pages toward the body target, and do not let a short body hide behind a long appendix.
   - **Reach the page count with SUBSTANTIVE content, never filler.** Fill to the reference's length by adding the material a real paper of this scope carries — a formal method statement with an algorithm block and the loss/objective written out, per-layer / sensitivity / qualitative analysis subsections, a fuller related-work discussion, and appendices (implementation + hyperparameters, dataset construction, the localization/attack procedure in detail, additional result tables). Do NOT pad with restated sentences or vacuous prose. If honest substantive content still falls short of the page count, say so at the gate.
   - **Dry-run figures: fill empty data-figure slots with clearly-labeled random data so they occupy real space.** When the venue reference has a figure/plot but this work has no real results yet (dry-run), do NOT leave the slot empty or a text box — generate the plot (pgfplots/matplotlib) with **synthetic/random values that follow the expected shape**, and mark it (caption or a visible tag) as dry-run/illustrative so it is swapped for real data later. This keeps the layout and page length faithful to the reference. (Architecture / concept diagrams are the exception — they stay hand-drawn placeholder boxes per the researcher's choice, since random data cannot stand in for a schematic.)

## Personalization (from the profile)

1. **Auto style-ref** — with no explicit style instruction, align to *Writing Style* (argument arc gap-first vs landscape-first; contribution-bullet phrasing) AND mirror the structure of the researcher's own same-`task_type` high-cited papers.
2. **Self-citation** — `python3 tools/bib_manager.py selfcite --enriched "$ARIS_PROFILE/enriched.json" --draft paper/main.tex`; surface suggested own-paper cites for approval — **never auto-insert a `\cite`**. **Cap self-citations at ≤3 papers total, and only the most relevant** (genuine method/lineage/baseline overlap with this work); if the tool surfaces more, rank by relevance and propose only the top 3, dropping the rest. Do not pad the reference list with the researcher's own papers.
3. **Anti-self-plagiarism** — compare each new contribution-bullet / abstract sentence against the researcher's prior abstracts (`enriched.json`); flag near-identical sentences for rewrite, don't silently reuse.

## Discipline

- **Modular, section-by-section (W4)** — one section at a time, independently regenerable. Order honoring the habit: Method → Experiments → Intro/Related → Abstract last.
- **Every number traces to `results/`** — pull from real files; unverifiable → `[UNVERIFIED]`, never restate from memory.
- **Claims match the plan** — only claim what `/run-plan`'s gates marked supported.
- **Figures & tables follow the reference paper (Step 0.4).** Two kinds, handled differently:
  - **Data plots** (ablation curves, bars, heatmaps) — generate them with a **committed Python/matplotlib script** (e.g. `paper/fig/make_figs.py`) that reads `results/` and writes a **PDF per figure** into `paper/fig/`, then include with `\includegraphics{fig/<name>.pdf}` (do NOT hand-inline pgfplots as the deliverable). Keep the script in the repo so every figure regenerates from data. Every point traces to a result file; under dry-run the script uses clearly-labelled random data of the expected shape.
  - **Architecture / method figure (the "model figure", usually Fig 1)** — do NOT draw with matplotlib, and do NOT auto-author TikZ. Instead emit a **placeholder box + a precise spec for the researcher to draw by hand** (draw.io/Inkscape/PowerPoint → export PDF, then `\includegraphics`). The placeholder is a `\fbox`/`\framebox` of the right column width with the caption in place, and a spec (as a LaTeX comment above it AND a visible TODO note) listing: every element/box, their layout and grouping, the arrows/data-flow, the before/after or highlighted parts, and any color coding. Leave the `\includegraphics{fig/model.pdf}` line commented, ready to swap in.
  - **Result tables** — laid out like the venue reference (rows=methods/attacks, cols=datasets/metrics, bold-best, ± std over seeds), `booktabs`; every cell traces to `results/`. **Match the reference's table WIDTH:** if its main results table spans both columns (a wide `table*`), the main results table here is a `table*` too, not a cramped single-column table; make it a full, dense table (multiple models/attacks × defenses) rather than a small one. A number with no result file → `[UNVERIFIED]`, never a fabricated cell.
- **Refuse fabricated/synthetic inputs.** If `05_FINDINGS.html` / `results/` are watermarked SYNTHETIC or contain placeholder markers, say so and do NOT write them into the manuscript as real results; only proceed for an explicit dry-run and keep the `[SYNTHETIC]` marks visible in the draft.

## Scaffold & compile (paper/ must build)

1. **Scaffold on first run** — if `paper/` is absent, create it from the venue template: `main.tex` (venue `\documentclass` + section skeleton), `references.bib` (seed from her BibTeX Bank), and drop the venue `.sty`/`.cls` alongside. Never overwrite an existing `paper/` (W3); write new sections in place.
2. **Compile after each section (and at the end)** — run `latexmk -pdf -interaction=nonstopmode -halt-on-error paper/main.tex` (the toolchain is installed: `pdflatex`/`xelatex`/`latexmk`).
   - **Builds** → report "compiled, N pages" + the current-vs-limit page count (Step 0.3).
   - **Fails** → extract the real errors from `main.log` (missing package, undefined `\ref`/`\cite`, bad bib key) and fix them; do not leave a `main.tex` that does not build.
3. **Output the PDF** — `paper/main.pdf` is a deliverable alongside the source.

## Bibliography

`python3 tools/bib_manager.py check paper/references.bib` — surface duplicate / non-standard keys / missing fields. Prefer the researcher's own BibTeX Bank entries before fetching new ones.

## GATE (human is judge)

Present the draft **section by section** for the researcher's edits, each compiled so she reviews the rendered result, not raw source. Do not declare the paper "done" — submission-readiness is their call. (An adversarial review is a separate, explicit request; default here is human review only.)

## Output

`paper/main.tex` + `paper/references.bib` + the venue `.sty`/`.cls` + compiled `paper/main.pdf` (venue template, within length limit, figures/tables modeled on the reference paper).
