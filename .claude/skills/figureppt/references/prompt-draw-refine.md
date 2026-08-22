## Stage 1 — VISUAL GRAMMAR + GENPROMPT
Before prompt generation, inspect three to five relevant peer-paper method or
overview figures. Record exact paper/figure/page locators and abstract only their
shared visual grammar: composition, semantic pictograms, information density,
operation-bearing geometry, non-color encodings, and label-to-visual ratio. Do
not copy any paper's content, labels, artwork, or distinctive layout. Save the
result as a project-local JSON or text artifact.

A fixed meta-prompt is then applied to the paper's method/mechanism text and this
visual grammar via GPT (chat) to produce a publication-ready drawing prompt. The
manuscript remains the only scientific-content source. Its source of truth is
`META_PROMPT` in the tool;
its required behavior is:

> You are an expert designer of figures for ACL-family NLP papers. Read the supplied manuscript
> and return one production-ready GPT Image prompt for a restrained academic diagram. Make its
> scientific message independently decodable by an unfamiliar reader: explicitly encode the input,
> the mechanism or decision criterion, and the output or contrast whenever those roles exist. Give
> semantically different branches different operation-bearing geometry, ordering, markers, or direct
> labels; never distinguish otherwise identical paths only by color or names. Define every acronym,
> symbol, and glyph beside it or demonstrate its meaning visually. Before returning, perform a
> caption-free cold-reader check and reject attractive compositions that show only component names,
> equal boxes, or unexplained arrows instead of the load-bearing mechanism. Use a pure
> white background, flat vector geometry, thin strokes, compact alignment, precise typography,
> two to four related regions, and a muted colorblind-safe palette. Use tokens, small glyphs,
> arrows, paths, matrices, or modules only when they encode the mechanism. Prefer an
> clean academic schematic over decorative poster art. Avoid people, scenery,
> photorealism, gradients, glow, 3D depth, glossy buttons, heavy shadows, marketing drama,
> oversized text cards, and generic flowcharts. Specify exact composition, minimal labels,
> aspect ratio, safe crop, and print readability; stay evidence-faithful and return only the prompt.

```bash
python3 research_avatar/tools/figure_ppt.py genprompt --paper <method.tex-or-txt> --visual-grammar <grammar.json> --spec spec.json [--model gpt-4o]
```
It reads the paper (feed the Method/Understanding sections, or the whole `main.tex`), calls
GPT as that expert designer, and writes the returned drawing prompt into `spec.draw_prompt`.
The first automatic Prompt must already be a concrete ACL-style visual specification, not a
content summary. Reject it before drawing if it describes either a sparse repeated-box flowchart
or a decorative poster with characters, scenery, glow, gradients, or 3D effects.
Also reject it when an unfamiliar reader could not recover the figure's one-sentence message
without the manuscript or caption. A mechanism prompt must assign an explicit visual encoding to
each load-bearing operation or decision criterion; labels and color changes alone do not count.
Reject any prompt whose object inventory is mostly rectangles containing text.
Require recognizable manuscript-grounded artifacts, pictograms, tokens, masks,
checks, rank strips, trajectories, or visible before/after transformations.
Do NOT hand-author the draw prompt — it comes from the paper through this meta-prompt so the
figure is faithful to the mechanism. (Read it back; re-run if it misreads the method.)

## Stage 2 — DRAW (image model, swappable)
```bash
python3 research_avatar/tools/figure_ppt.py draw spec.json --provider openai   # gpt-image-1, quality=high
```
Draws with `spec.draw_prompt` **VERBATIM — nothing appended** (the drawing prompt keeps its own
labels). The currently supported drawer is `openai` (`OPENAI_API_KEY`). Produces `<fig>.bg.png`, and **every draw is
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
   Temporarily ignore the caption and manuscript, then state the image's message in one sentence.
   Reject the image if that sentence omits or guesses the input, operation/criterion, or output/contrast.
2. **Rewrite `spec.draw_prompt` yourself** (Edit/Write the spec) to fix exactly what you saw —
   a tight image prompt, not a multi-section design doc.
3. Re-`draw` and look again. Repeat until it reads cleanly and faithfully.
```bash
python3 research_avatar/tools/figure_ppt.py draw spec.json --provider openai   # after YOU edit spec.draw_prompt
```
Do not delegate the rewrite to a canned instruction — you have vision, so adapt to whatever
this round's image shows. If a label must be perfectly crisp, set
`spec.no_text=true` for the reference image and recreate the label as a native
text object during the complete shape reconstruction; never add it as a local
overlay to a delivered figure.
