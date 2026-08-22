## Stage 4 — BUILD a fully editable PPT + PDF

**`buildshapes` — required editable publication path.**
```bash
python3 research_avatar/tools/figure_ppt.py buildshapes shapes.json --out <fig>.pptx   # native PPT shapes
python3 research_avatar/tools/figure_ppt.py pdf         <fig>.pptx                      # soffice → PDF
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
The GPT image is a visual reference, not a deliverable layer. The rebuilt result is a clean
native-shape diagram rather than a painterly raster because raster pixels cannot become editable
PowerPoint components.

Image-backed `build`, `pdfimage`, and `all` outputs are not publication
deliverables for this Skill. Do not use them as a shortcut for correcting a
label or composition in an existing figure. Correct the prompt or native-shape
spec and rebuild the complete native figure.

## Standalone workflow
1. `emit-example` → a spec; set `canvas_in: [W,H]` and `image_size` from the current project's approved figure slot.
2. Inspect three to five peer figures and save an abstract visual grammar with exact source locators.
3. **genprompt** from the paper's Method section plus `--visual-grammar` → `spec.draw_prompt` (drawing prompt).
4. Show the generated Prompt to the researcher and call the image model only after explicit confirmation. The Prompt must state placement, aspect ratio, visual encoding, spatial composition, density, safe crop band, and the project-specific figure role.
5. **draw** → `.bg.png`; **read the image yourself**.
   Before drawing, compare the Prompt with the latest successful archived `round_NN.prompt.txt`.
   If unchanged, reuse the current image and do not call the image API or create a new round.
6. **refine (agent-driven) → draw**, repeated: YOU read the image, rewrite `spec.draw_prompt` to
   fix whatever you actually see (garbles / an off-convention results panel / a wrong mechanism /
   clutter), then redraw. Loop until clean. No canned refine instruction.
7. For a `no_text` reference image, recreate all short tags/symbols from the
   Method as native text objects in the complete shape spec; never layer them
   onto the raster deliverable.
8. **buildshapes + pdfshapes** → fully editable `.pptx` + matching `.pdf`.
9. Save the PDF/PPTX and LaTeX placement at the paths and slot specified by the current project; do not assume a Figure-1 ID, filename, width, or section.

## Rules
- **Print-readability gate:** body labels are at least 7 pt at final paper size and panel
  labels at least 8 pt; no information may be encoded by color alone. Every data series
  also needs a marker, line style, hatch, or direct label. Use a color-vision-safe palette,
  render once in grayscale, and reject any pair of series/modules that becomes
  indistinguishable. Keep text/background contrast at least 4.5:1 and remove labels that
  force crowding instead of shrinking them. Record the final-size font floor,
  non-color encoding, grayscale result, and density decision in the figure source spec.
- **Keep `paper/fig/` clean — deliverables ONLY.** After building, `paper/fig/` should contain only the
  figures the paper includes plus their editable/source-of-truth artifacts: the final figure PDFs
  (`model.pdf`, `motiv.pdf`, data plots), the editable `*.pptx`, and each gpt-generated image saved AS A
  PDF (`stylejb_*.gpt.pdf`). Move generation sources (`make_figs.py`, `style.py`, `*_shapes.json`,
  `*_spec.json`, `*_method.txt`, the `iterations/` gpt-draft archive) to `paper/figsrc/`, and delete the
  clutter (`*.bg.png` raster working copies, duplicate PDFs). Do not leave json/txt/png/scripts loose in `fig/`.
- **For a mechanism figure the flow is `draw` → visually grounded shape reconstruction → `buildshapes` → unattended `pdfshapes`.** Keep the GPT Image PNG only as the archived reference preview. The final PPTX must contain no raster background and every visible module, icon, connector, and label must be an independent native object. Reject sparse placeholder reconstructions with minimum object/module/connector checks; verify the PPT package has no `ppt/media/` image layer.
- **Use the project-approved placement and canvas.** Width, aspect ratio, column span, filename, and section are project data. After `pdf`, READ the rendered PDF and confirm it matches that contract and nothing is clipped.
- **Draw prompt is GENERATED from the paper via the meta-prompt** — never hand-written.
- **Refine from the IMAGE, agent-driven** — after drawing, YOU look at the figure and rewrite
  `spec.draw_prompt` from what is actually rendered; no fixed refine instruction (first-draft
  failures can't be enumerated in advance). The image is throwaway between rounds.
- **Publication-ready scientific drawing, not a text flowchart** — choose the
  visual language that best carries the mechanism; do not force one named style.
- **The first generated Prompt is an ACL-style visual specification, not a summary** — require
  exact layout and encodings, but reject both repeated-box placeholders and decorative poster art
  before spending an image call.
- **Caption-free semantic gate** — an unfamiliar reader must be able to recover the intended
  one-sentence message from the picture alone. Every load-bearing input, operation/decision
  criterion, and output/contrast needs an explicit visual encoding. Unexplained symbols and
  semantically different but visually identical branches are automatic rejection conditions.
- **Method figure shows the METHOD, never results** — no accuracy/ASR/metric numbers or bar charts.
- **Image models garble baked text** — regenerate/refine to reduce it; if a label must be crisp,
  set `no_text` and overlay it as an editable PPT box instead.
- **Drawer swappable + throwaway** — provider is a flag; regenerate until the figure reads right.

## Tool & deps
`research_avatar/tools/figure_ppt.py` — use `genprompt` / `draw` / `buildshapes` /
`pdf` / `emit-example` for this Skill. Image-backed compatibility commands are
outside the publication path.
(refine is agent-driven — read the image, edit `spec.draw_prompt`, re-`draw`; no CLI command).
`buildshapes` is the fully-editable native-shapes path (Stage 4A).
Deps in this repo: `OPENAI_API_KEY` (genprompt chat + gpt-image draw), `python-pptx` (build),
`soffice` (pdf). Run `--help` for flags.
