---
name: "figureppt"
description: "Create a publication-ready editable model, method, mechanism, framework, or Figure-1 visual. Generate a composition prompt from manuscript evidence, use GPT Image as a visual reference, rebuild every visible element as native PowerPoint shapes, and export the paper PDF from the same specification. Invoke explicitly as `$figureppt`."
---

# Editable Paper Figure

Use `research_avatar/tools/figure_ppt.py`. The deliverable is a scientific
schematic, not a text-heavy flowchart or decorative poster.

The figure spec, native-shape spec, and plotting source are authoritative; the
PPTX/PDF are rendered artifacts. Correct the responsible spec or generator and
rebuild the complete figure. Never repair a delivered PPTX/PDF with an overlay,
replacement label, hidden raster, or other local after-the-fact edit.

## Workflow

1. Read the current manuscript evidence and approved figure slot.
2. Inspect three to five relevant peer-paper figures and write a project-local
   visual-grammar file that abstracts their shared composition, iconography,
   information density, and operation-bearing geometry. Record source figure/page
   locators. Never copy scientific content, labels, artwork, or layout identity.
3. Run `genprompt --visual-grammar <grammar.json>` so the tool derives
   `spec.draw_prompt` jointly from manuscript evidence and that abstract visual
   grammar; do not hand-author the initial prompt.
4. Reject a prompt whose planned objects are mostly rectangles containing text.
   Require concrete manuscript-grounded artifacts, pictograms, state changes,
   paths, masks, checks, ranks, or other operation-bearing geometry.
5. Show the prompt and obtain explicit approval before an image-model call.
6. Run `draw`; inspect the actual raster reference yourself.
7. Revise the prompt based on observed semantic/layout defects and redraw until
   the figure is faithful and readable. Reuse an unchanged successful prompt
   instead of spending another image call.
8. Reconstruct the approved reference as native shapes with `buildshapes`.
9. Export the same editable PPTX to PDF and visually inspect final placement,
   clipping, shadows, density, and print readability.

Typical commands:

```bash
python3 research_avatar/tools/figure_ppt.py genprompt --paper <method.tex-or-txt> --visual-grammar <grammar.json> --spec spec.json
python3 research_avatar/tools/figure_ppt.py draw spec.json --provider openai
python3 research_avatar/tools/figure_ppt.py buildshapes shapes.json --out <figure>.pptx
python3 research_avatar/tools/figure_ppt.py pdf <figure>.pptx
```

Read
[`references/prompt-draw-refine.md`](references/prompt-draw-refine.md) before
prompt generation, image calls, or refinement. It contains the complete
meta-prompt behavior, archive contract, semantic cold-reader test, and
agent-driven refinement rules.

Read [`references/editable-output.md`](references/editable-output.md) before
shape reconstruction, export, cleanup, or final validation. It contains the
shape schema, flat-design implementation details, legacy image-backed path,
readability/accessibility gates, and directory contract.

## Non-negotiables

- Use the project-approved role, section, span, canvas, aspect ratio, filename,
  and density. Never assume every project needs the same Figure 1.
- The picture must make its one scientific message recoverable without the
  caption. Encode input, load-bearing operation/criterion, and output/contrast
  with meaningful geometry—not color or labels alone.
- Peer figures contribute only generalized visual grammar. Scientific content
  comes exclusively from the current manuscript, and the final composition must
  be project-specific rather than a copy of any reference figure.
- A set of labeled rectangles is a flowchart, not an acceptable model figure.
  Enclosing panels may organize real subsystems, but their interiors must depict
  the relevant artifacts and transformations visually.
- A method/mechanism figure contains no result bars, accuracy/ASR values, or
  unsupported causal claims.
- Final editable deliverables use independent native modules, icons,
  connectors, and labels. The GPT Image raster is a composition reference, not
  a final background layer.
- Use flat solid fills, no gradients/3D/theme shadows, a color-vision-safe
  palette, non-color encodings, ≥4.5:1 text contrast, and final-size label
  floors from the detailed reference.
- Inspect the generated image and final PDF. Reject garbled text, unexplained
  symbols, identical-looking semantic branches, clipping, sparse placeholder
  reconstruction, and any hidden raster layer in the PPT package.
- Keep deliverables in `paper/fig/` and generation sources/iteration history in
  `paper/figsrc/`; remove disposable raster/build clutter only after verified
  final outputs exist.

The supported tool commands and dependencies are authoritative via:

```bash
python3 research_avatar/tools/figure_ppt.py --help
```

Image generation requires the selected provider's key; native reconstruction
uses `python-pptx`, and PDF export uses the configured unattended exporter.
