# Editable native output

Use `buildshapes` for the publication path:

```bash
python3 research_avatar/tools/figure_ppt.py buildshapes shapes.json --out <figure>.pptx
python3 research_avatar/tools/figure_ppt.py pdf <figure>.pptx
```

The shape specification is authoritative. Every visible module, pictogram,
connector, and label must be an independent PowerPoint object. Flat design is
required: solid fills, no gradients, 3D bevels, theme shadows, hidden raster
backgrounds, or local overlay repairs.

Shape schema; coordinates are fractions of the canvas:

```json
{"figure_id":"f1","canvas_in":[7.0,3.2],"shapes":[
  {"kind":"rounded_rect|rect|oval|hexagon|right_arrow","x":0.1,"y":0.1,"w":0.2,"h":0.1,"fill":"FFFFFF","line":"333333","line_w":1,"text":"","font_size":8,"bold":false,"font_color":"202124","align":"center"},
  {"kind":"textbox","x":0.1,"y":0.1,"w":0.2,"h":0.05,"text":"Label","font_size":8,"bold":true,"font_color":"202124","align":"center"},
  {"kind":"arrow|line","x1":0.1,"y1":0.2,"x2":0.3,"y2":0.2,"color":"333333","weight":1}
]}
```

Combine primitives into recognizable native pictograms when the mechanism
benefits from them: head and torso for a person, antenna/head/eyes for an
assistant, facing pages and spine for a narrative source, warning mark and
boundary for an untrusted source, document lines for a fact, tag shapes for
attribution, and gate/check geometry for authorization. Pictograms must encode
manuscript meaning and remain editable; avoid decorative icons.

At final paper size, body labels are at least 7 pt and panel labels at least 8
pt. Use a color-vision-safe palette, at least 4.5:1 text contrast, and a
non-color distinction for every semantic branch. Render in grayscale and reject
branches that become indistinguishable. Verify no clipping or theme shadows and
inspect the PPT package to ensure it has no `ppt/media/` raster layer.

Keep final PDF and PPTX in `paper/fig/`. Keep the current shape spec,
composition brief, visual grammar, and archived revisions in `paper/figsrc/`.
Do not leave PNG drafts or disposable build files in `paper/fig/`.

Dependencies: `python-pptx` and the configured unattended PowerPoint/PDF
exporter. No image-generation API key is required.
