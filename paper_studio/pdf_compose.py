#!/usr/bin/env python3
"""Compose tightly cropped vector-PDF panels without rasterizing them."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import fitz


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--layout", type=Path, required=True)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--png", type=Path, required=True)
    parser.add_argument("panels", nargs="+", type=Path)
    args = parser.parse_args()

    layout = json.loads(args.layout.read_text(encoding="utf-8"))
    orientation = layout["orientation"]
    target_width_in = 3.32 if layout["width"] == "single-column" else 7.0
    gap = float(layout["gap_pt"])
    labels = {item["panel_id"]: item for item in layout["labels"]}
    panel_order = layout["panel_order"]
    if len(panel_order) != len(args.panels):
        raise SystemExit("layout panel_order does not match input panel count")
    documents = [fitz.open(path) for path in args.panels]
    rects = [document[0].rect for document in documents]
    target_extent = target_width_in * 72
    if orientation == "horizontal":
        common_height = 100.0
        natural_widths = [common_height * rect.width / rect.height for rect in rects]
        scale = (target_extent - gap * (len(rects) - 1)) / sum(natural_widths)
        widths = [value * scale for value in natural_widths]
        heights = [common_height * scale] * len(rects)
        page_width, page_height = sum(widths) + gap * (len(rects) - 1), heights[0]
        offsets = [
            (sum(widths[:index]) + gap * index, 0.0)
            for index in range(len(rects))
        ]
    else:
        widths = [target_extent] * len(rects)
        heights = [target_extent * rect.height / rect.width for rect in rects]
        page_width, page_height = target_extent, sum(heights) + gap * (len(rects) - 1)
        offsets = [
            (0.0, sum(heights[:index]) + gap * index)
            for index in range(len(rects))
        ]

    composed = fitz.open()
    page = composed.new_page(width=page_width, height=page_height)
    for index, document in enumerate(documents):
        x, y = offsets[index]
        target = fitz.Rect(x, y, x + widths[index], y + heights[index])
        page.show_pdf_page(target, document, 0, keep_proportion=False)
        label_spec = labels.get(panel_order[index])
        if label_spec:
            label = label_spec["text"]
            position = label_spec["position"]
            label_width, label_height = 24, 15
            left = x + 2 if position.endswith("left") else x + widths[index] - label_width - 2
            top = y + 2 if position.startswith("top") else y + heights[index] - label_height - 2
            label_box = fitz.Rect(left, top, left + label_width, top + label_height)
            page.draw_rect(label_box, fill=(1, 1, 1), color=None, overlay=True)
            page.insert_text(
                (left + 2, top + 10), label, fontsize=9, fontname="hebo", overlay=True
            )

    args.pdf.parent.mkdir(parents=True, exist_ok=True)
    args.png.parent.mkdir(parents=True, exist_ok=True)
    composed.save(args.pdf, garbage=4, deflate=True)
    page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5), alpha=False).save(args.png)
    composed.close()
    for document in documents:
        document.close()


if __name__ == "__main__":
    main()
