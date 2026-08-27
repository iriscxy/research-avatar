# Codex-native composition and refinement

## Stage 1 — visual grammar

Inspect three to five relevant peer-paper method or overview figures. Record
exact paper, figure, and page locators and abstract only shared visual grammar:
composition, semantic pictograms, information density, operation-bearing
geometry, non-color encodings, and label-to-visual ratio. Never copy scientific
content, labels, artwork, or a distinctive layout. The manuscript remains the
only source of scientific content.

## Stage 2 — Codex composition

Codex reads the approved figure slot, manuscript evidence, and visual grammar,
then writes a concise project-local composition brief and the complete native
shape specification. No image-generation model is called and no raster draft is
used. The shape spec must explicitly encode the input, load-bearing operation or
criterion, and output or contrast. Semantically different branches must differ
through geometry, ordering, markers, or pictograms rather than color or labels
alone.

Reject the design before rendering when its object inventory is mostly labeled
rectangles, when an unexplained symbol carries meaning, or when an unfamiliar
reader could not state the figure's one scientific message without its caption.
Prefer manuscript-grounded artifacts, tokens, tags, masks, gates, trajectories,
checks, books, documents, people, devices, or other small native pictograms.

Archive each iteration as
`paper/figsrc/iterations/<figure_id>/round_NN.shapes.json` with a matching
`round_NN.brief.txt`. Never overwrite an earlier round.

## Stage 3 — render and refine

Build the editable PPTX with `buildshapes`, export it with `pdf`, and inspect the
rendered PDF at its final paper size. Temporarily ignore the caption and state
the visible message in one sentence. If that reading omits or guesses the input,
criterion, or contrast, revise the authoritative shape spec and rebuild the
complete figure. Also reject clipping, weak hierarchy, labels below the font
floor, visually identical semantic branches, excess whitespace, or decorative
objects without manuscript-grounded meaning.

Do not repair the rendered PPTX or PDF with overlays. Revise the source brief or
shape spec and regenerate. The final PPTX contains only independent native
shapes, connectors, icons, and labels and must have no `ppt/media/` raster layer.
