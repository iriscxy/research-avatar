#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const [specPath, outputPath, previewPath] = process.argv.slice(2);
if (!specPath || !outputPath || !previewPath) {
  throw new Error("usage: ppt_compose.mjs SPEC_JSON OUTPUT_PPTX PREVIEW_PNG");
}

const spec = JSON.parse(await fs.readFile(specPath, "utf8"));
const PX_PER_PT = 96 / 72;
const targetWidth = (spec.width === "single-column" ? 3.32 : 7.0) * 96;
const gap = spec.gap_pt * PX_PER_PT;
const panels = spec.panels;

let slideWidth;
let slideHeight;
if (spec.orientation === "horizontal") {
  const naturalWidths = panels.map((panel) => panel.width_pt / panel.height_pt);
  const commonHeight = (targetWidth - gap * (panels.length - 1)) /
    naturalWidths.reduce((sum, value) => sum + value, 0);
  panels.forEach((panel, index) => {
    panel.left = panels.slice(0, index).reduce(
      (sum, prior) => sum + prior.width_pt / prior.height_pt * commonHeight,
      gap * index,
    );
    panel.top = 0;
    panel.width = panel.width_pt / panel.height_pt * commonHeight;
    panel.height = commonHeight;
  });
  slideWidth = targetWidth;
  slideHeight = commonHeight;
} else {
  panels.forEach((panel, index) => {
    panel.left = 0;
    panel.top = panels.slice(0, index).reduce(
      (sum, prior) => sum + targetWidth * prior.height_pt / prior.width_pt,
      gap * index,
    );
    panel.width = targetWidth;
    panel.height = targetWidth * panel.height_pt / panel.width_pt;
  });
  slideWidth = targetWidth;
  slideHeight = panels.reduce((sum, panel) => sum + panel.height, 0) +
    gap * (panels.length - 1);
}

async function readBlob(filename) {
  const bytes = await fs.readFile(filename);
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}

const deck = Presentation.create({
  slideSize: { width: slideWidth, height: slideHeight },
});
const slide = deck.slides.add();
slide.background.fill = "#FFFFFF";

for (const panel of panels) {
  const image = slide.images.add({
    blob: await readBlob(panel.svg),
    fit: "contain",
    alt: `Vector PDF panel ${panel.id}`,
  });
  image.position = {
    left: panel.left,
    top: panel.top,
    width: panel.width,
    height: panel.height,
  };
}

for (const label of spec.labels) {
  const panel = panels.find((item) => item.id === label.panel_id);
  if (!panel) continue;
  const fontSize = label.font_size_pt * PX_PER_PT;
  const boxWidth = Math.max(fontSize * 1.8, 20);
  const boxHeight = Math.max(fontSize * 1.25, 14);
  const offset = 2 * PX_PER_PT;
  const left = label.position.endsWith("left")
    ? panel.left + offset
    : panel.left + panel.width - boxWidth - offset;
  const top = label.position.startsWith("top")
    ? panel.top + offset
    : panel.top + panel.height - boxHeight - offset;
  const shape = slide.shapes.add({
    geometry: "rect",
    position: { left, top, width: boxWidth, height: boxHeight },
    fill: "#FFFFFF",
    line: { width: 0, fill: "#FFFFFF" },
  });
  shape.text = label.text;
  shape.text.fontSize = fontSize;
  shape.text.typeface = "Arial";
  shape.text.bold = true;
  shape.text.color = "#000000";
  shape.text.alignment = "left";
  shape.text.verticalAlignment = "top";
  shape.text.insets = { left: 1, right: 0, top: 0, bottom: 0 };
  shape.text.autoFit = "shrinkText";
}

await fs.mkdir(path.dirname(outputPath), { recursive: true });
await fs.mkdir(path.dirname(previewPath), { recursive: true });
const preview = await deck.export({ slide, format: "png", scale: 2 });
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
const pptx = await PresentationFile.exportPptx(deck);
await pptx.save(outputPath);
