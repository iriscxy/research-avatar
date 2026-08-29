---
name: "figureppt"
description: "Create a publication-ready editable model, method, mechanism, framework, or Figure-1 visual. Derive the composition from manuscript evidence, have Codex draw it directly as native PowerPoint shapes, and export the paper PDF from the same specification. Invoke explicitly as `/figureppt`."
---

# Editable Paper Figure

Use `research_avatar/tools/figure_ppt.py`. The deliverable is a scientific
schematic, not a text-heavy flowchart or decorative poster.

The figure spec, native-shape spec, and plotting source are authoritative; the
PPTX/PDF are rendered artifacts. Correct the responsible spec or generator and
rebuild the complete figure. Never repair a delivered PPTX/PDF with an overlay,
replacement label, hidden raster, or other local after-the-fact edit.

## Workflow

1. Read the current manuscript evidence and approved figure slot. Read the
   slot's explicit `figure_type`; do not infer it from the title, caption,
   description, section name, or keywords. Preserve its distinct rhetorical
   profile throughout composition and refinement.
2. Inspect three to five relevant peer-paper figures and write a project-local
   visual-grammar file that abstracts their shared composition, iconography,
   information density, and operation-bearing geometry. Record source figure/page
   locators. Never copy scientific content, labels, artwork, or layout identity.
3. Have Codex derive a concise composition specification from the manuscript
   evidence and visual grammar, then author the complete native `shapes.json`
   directly as the authoritative composition.
4. Reject a composition whose planned objects are mostly rectangles containing
   text. Require concrete manuscript-grounded artifacts, pictograms, state
   changes, paths, masks, checks, ranks, or other operation-bearing geometry.
5. Run `buildshapes`, render the editable PPTX to PDF, and inspect the actual
   output. Revise the authoritative shape spec and rebuild the whole figure when
   semantic, layout, or readability defects are visible.
6. Visually inspect final placement,
   clipping, shadows, density, and print readability.

Typical commands:

```bash
python3 research_avatar/tools/figure_ppt.py buildshapes shapes.json --out <figure>.pptx
python3 research_avatar/tools/figure_ppt.py pdf <figure>.pptx
```

Read [`references/prompt-draw-refine.md`](references/prompt-draw-refine.md)
before composition and refinement. It defines the Codex-native design brief,
revision archive, and semantic cold-reader test.

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
  connectors, and labels.
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

Native drawing uses `python-pptx`, and
PDF export uses the configured unattended exporter.
