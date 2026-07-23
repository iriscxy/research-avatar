---
name: figure-ppt
description: Draw a paper's model / method / Figure-1 mechanism figure by (1) applying a fixed "expert scientific-figure designer" meta-prompt to the paper's method text to GENERATE a BioRender-style image prompt, (2) calling an image model (gpt-image) to draw the imagery from that prompt, (3) compositing it into an EDITABLE PowerPoint (image background + every label a hand-editable text box) and exporting a PDF. The image drawer is swappable (gpt-image now via OPENAI_API_KEY; Gemini later). Use for "model figure", "method figure", "mechanism figure", "framework figure", "Figure 1", or when /paper-write needs the Fig 1 slot filled. Invocable as /figure-ppt.
allowed-tools: Bash(*), Read, Write, Edit, AskUserQuestion
---

# figure-ppt — paper → BioRender prompt → gpt-image → editable PPT → PDF

The model figure is a **schematic that conveys the mechanism through imagery** (vectors,
geometry, arrows, icons — BioRender style), NOT a flowchart of text-filled boxes. The
mechanism is fixed in four stages (tool: `tools/figure_ppt.py`):

## Stage 1 — GENPROMPT (the draw prompt is GENERATED from the paper, not hand-written)
A fixed meta-prompt is applied to the paper's method/mechanism text via GPT (chat) to
produce a BioRender-style image prompt. The meta-prompt (verbatim, in the tool as
`META_PROMPT`) is:

> You are a professional and experienced scientific-figure designer. Carefully read the following
> paper content, deeply understand its core mechanism, key method, and deep-model experimental
> pipeline, and then generate a BioRender-style prompt for the mechanism figure.

```bash
python3 tools/figure_ppt.py genprompt --paper <method.tex-or-txt> --spec spec.json [--model gpt-4o]
```
It reads the paper (feed the Method/Understanding sections, or the whole `main.tex`), calls
GPT as that expert designer, and writes the returned BioRender prompt into `spec.draw_prompt`.
Do NOT hand-author the draw prompt — it comes from the paper through this meta-prompt so the
figure is faithful to the mechanism. (Read it back; re-run if it misreads the method.)

## Stage 2 — DRAW (image model, swappable)
```bash
python3 tools/figure_ppt.py draw spec.json --provider openai   # gpt-image-1, quality=high
```
Draws with `spec.draw_prompt` **VERBATIM — nothing appended** (a BioRender figure keeps its own
labels). Drawer is a flag: `openai` now (OPENAI_API_KEY); `gemini` (Nano Banana) once
`GEMINI_API_KEY` + `google-generativeai` are wired. Produces `<fig>.bg.png`, and **every draw is
archived** to `iterations/<figure_id>/round_NN.png` + `round_NN.prompt.txt` (the exact prompt used
that round) — no iteration is overwritten, so the whole refine history is kept. (Opt into
imagery-only + editable-label-overlay with `spec {"no_text": true}` if you want crisp editable
text instead of baked labels — image models garble baked text.)

## Stage 3 — REFINE (AGENT-DRIVEN: YOU read the figure → YOU rewrite the prompt → redraw)
**There is deliberately NO fixed refine instruction.** A first-draft figure fails in ways that
cannot be enumerated in advance, so the refinement is done by **you, the calling agent**:
1. `Read` the drawn `<fig>.bg.png` and judge what is actually wrong — e.g. garbled/misspelled
   text, an off-convention **results/metrics/bar-chart panel** (a method figure shows ONLY the
   mechanism, never results), a wrong or missing mechanism, clutter, weak composition,
   verbose-doc prose that the image model rendered literally.
2. **Rewrite `spec.draw_prompt` yourself** (Edit/Write the spec) to fix exactly what you saw —
   a tight image prompt, not a multi-section design doc.
3. Re-`draw` and look again. Repeat until it reads cleanly and faithfully.
```bash
python3 tools/figure_ppt.py draw spec.json --provider openai   # after YOU edit spec.draw_prompt
```
Do not delegate the rewrite to a canned instruction — you have vision, so adapt to whatever
this round's image shows. (Image models garble baked text; if a label must be perfectly crisp,
set spec `no_text:true` and overlay it as an editable PPT box.)

## Stage 4 — BUILD an EDITABLE PPT + PDF. Two paths:

**(A) `buildshapes` — FULLY editable (default when "everything must be editable in PPT").**
```bash
python3 tools/figure_ppt.py buildshapes shapes.json --out <fig>.pptx   # native PPT shapes
python3 tools/figure_ppt.py pdf         <fig>.pptx                      # soffice → PDF
```
Renders a **shape spec** into **native PowerPoint shapes** — every module a rounded rect, every
flow an arrow (connector with an arrowhead), every label a text box, ovals/hexagons as needed —
so **every element is selectable and editable** in PowerPoint and **text is crisp (never garbled)**.
**Flat design (enforced in code): solid fills only, NO drop shadows on any element, no gradients, no
3D bevels.** The schematic must read as clean flat blocks and lines. NOTE: `shadow.inherit=False`
alone is NOT enough — python-pptx adds an empty `<a:effectLst/>` that PowerPoint honours but
LibreOffice/`soffice` ignores, so on the pptx→pdf export it still renders the THEME shadow that each
shape's `<p:style>/<a:effectRef idx="2">` points at. The `buildshapes` `_flat()` helper therefore
also rewrites every `a:effectRef` to `idx="0"` (shapes, connectors, and text boxes), which kills the
shadow in every renderer. After exporting, READ the PDF and confirm there are no shadows. YOU author `shapes.json` (Write it) by reconstructing the mechanism from the
gpt-image reference (`iterations/…/round_NN.png`) — the raster becomes the *visual guide*, the PPT
is real shapes.
Shape schema — `x,y,w,h` (and arrow `x1,y1,x2,y2`) are FRACTIONS of the canvas:
```
{"figure_id","canvas_in":[W,H],"shapes":[
  {"kind":"rounded_rect|rect|oval|hexagon|right_arrow","x","y","w","h","fill","line","line_w","text","font_size","bold","font_color","align"},
  {"kind":"textbox","x","y","w","text","font_size","bold","font_color","align"},
  {"kind":"arrow|line","x1","y1","x2","y2","color","weight"}]}
```
Tradeoff: the look is a clean native-shape diagram, not the painterly BioRender raster — that is
the cost of full editability (a raster cannot become editable elements).

**(B) `build` — image background + editable label boxes (partial edit).** Keeps the gpt-image
painterly look; only the overlay labels are editable (the imagery is a flat raster). Use when the
baked figure looks right and you only need to fix/add a few crisp labels.
```bash
python3 tools/figure_ppt.py build spec.json --img <fig>.bg.png   # image bg + editable label boxes
python3 tools/figure_ppt.py pdf   <fig>.pptx
```
`soffice` (LibreOffice, headless) exports the PDF that drops into the paper.

`python3 tools/figure_ppt.py all spec.json --paper <method> [--refine-rounds N]` chains
genprompt → draw → (refine → draw)×N → build → pdf.

## Workflow when called by /paper-write
1. `emit-example` → a spec; set `canvas_in: [W,H]` to the Fig 1 slot's aspect ratio + `image_size`.
2. **genprompt** from the paper's Method section → `spec.draw_prompt` (BioRender prompt).
3. **draw** → `.bg.png`; **read the image yourself**.
4. **refine (agent-driven) → draw**, repeated: YOU read the image, rewrite `spec.draw_prompt` to
   fix whatever you actually see (garbles / an off-convention results panel / a wrong mechanism /
   clutter), then redraw. Loop until clean. No canned refine instruction.
5. (optional) `spec.labels[]` — for a `no_text` figure, short tags/symbols from the Method
   (truth) positioned over the imagery; apply `figure_style` (panel-label case, font, palette).
6. **build + pdf** → editable `.pptx` + `.pdf`.
7. Copy the PDF to `paper/fig/model.pdf` and `\includegraphics{fig/model.pdf}` into the Fig 1 slot.

## Rules
- **Keep `paper/fig/` clean — deliverables ONLY.** After building, `paper/fig/` should contain only the
  figures the paper includes plus their editable/source-of-truth artifacts: the final figure PDFs
  (`model.pdf`, `motiv.pdf`, data plots), the editable `*.pptx`, and each gpt-generated image saved AS A
  PDF (`stylejb_*.gpt.pdf`). Move generation sources (`make_figs.py`, `style.py`, `*_shapes.json`,
  `*_spec.json`, `*_method.txt`, the `iterations/` gpt-draft archive) to `paper/figsrc/`, and delete the
  clutter (`*.bg.png` raster working copies, duplicate PDFs). Do not leave json/txt/png/scripts loose in `fig/`.
- **For a paper model figure the flow is `draw` (gpt-image, as a DRAFT) → `buildshapes`** — gpt drafts
  the composition, then you rebuild it as native PPT shapes so EVERY element (icons, arrows, labels) is
  individually editable. The `build` path (gpt raster background + editable labels only) is NOT enough
  when every element must be editable, because its icons stay a non-editable raster. gpt is still used
  (it drafts the figure), it is just not the final deliverable.
- **A model figure must be PAGE-WIDTH** — a two-column `figure*` at `\includegraphics[width=\textwidth]`,
  never a single-column half-width include. Set the `buildshapes` `canvas_in` to a full-width banner
  aspect (e.g. `[7.0, 2.4]`). An opening / motivation figure is instead single-column (half width).
  After `pdf`, READ the rendered PDF and confirm it is the right width and nothing is clipped.
- **Draw prompt is GENERATED from the paper via the meta-prompt** — never hand-written.
- **Refine from the IMAGE, agent-driven** — after drawing, YOU look at the figure and rewrite
  `spec.draw_prompt` from what is actually rendered; no fixed refine instruction (first-draft
  failures can't be enumerated in advance). The image is throwaway between rounds.
- **BioRender-style schematic, not a text flowchart** — the picture carries the mechanism.
- **Method figure shows the METHOD, never results** — no accuracy/ASR/metric numbers or bar charts.
- **Image models garble baked text** — regenerate/refine to reduce it; if a label must be crisp,
  set `no_text` and overlay it as an editable PPT box instead.
- **Drawer swappable + throwaway** — provider is a flag; regenerate until the figure reads right.

## Tool & deps
`tools/figure_ppt.py` — `genprompt` / `draw` / `build` / `buildshapes` / `pdf` / `all` / `emit-example`
(refine is agent-driven — read the image, edit `spec.draw_prompt`, re-`draw`; no CLI command).
`buildshapes` is the fully-editable native-shapes path (Stage 4A).
Deps in this repo: `OPENAI_API_KEY` (genprompt chat + gpt-image draw), `python-pptx` (build),
`soffice` (pdf). Run `--help` for flags.
