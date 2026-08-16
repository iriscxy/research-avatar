#!/usr/bin/env python3
"""Render projected or observed typo-basis figures from one schema."""

import argparse
import json
from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg")
except ModuleNotFoundError:
    matplotlib = None

from PIL import Image, ImageDraw, ImageFont


def validate_rendered_marks(values, expected):
    if len(values) != expected:
        raise ValueError(f"expected {expected} rendered marks, got {len(values)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", required=True)
    parser.add_argument("--figure", required=True)
    parser.add_argument("--panel", required=True)
    parser.add_argument("--metrics", required=True)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--png", required=True)
    args = parser.parse_args()
    schema = json.loads(Path(args.schema).read_text())
    metrics = json.loads(Path(args.metrics).read_text())
    panel = schema["figures"][args.figure][0]
    values = metrics["traceable_results"][panel["fixture_key"]]
    marks = [float(value) for series in values["series"] for value in series["values"]]
    validate_rendered_marks(marks, panel["plotted_marks"])
    image = Image.new("RGB", (1200, 700), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    left, top, right, bottom = 110, 80, 1140, 590
    draw.line((left, bottom, right, bottom), fill="#17313a", width=3)
    draw.line((left, top, left, bottom), fill="#17313a", width=3)
    for tick in (0.75, 0.80, 0.85, 0.90, 0.95, 1.00):
        y = bottom - (bottom - top) * (tick - 0.75) / 0.25
        draw.line((left - 8, y, left, y), fill="#17313a", width=2)
        draw.text((left - 55, y - 7), f"{tick:.2f}", fill="#17313a", font=font)
    draw.text((20, (top + bottom) // 2), "Accuracy", fill="#17313a", font=font)
    colors = ["#087f74", "#a76416"]
    labels = values["categories"]
    for series_index, series in enumerate(values["series"]):
        points = []
        for index, value in enumerate(series["values"]):
            x = left + (right - left) * index / max(1, len(labels) - 1)
            y = bottom - (bottom - top) * (float(value) - 0.75) / 0.25
            points.append((x, y))
            draw.ellipse((x - 7, y - 7, x + 7, y + 7), fill=colors[series_index])
        draw.line(points, fill=colors[series_index], width=5)
        draw.text((760, 25 + 24 * series_index), series["name"], fill=colors[series_index], font=font)
    for index, label in enumerate(labels):
        x = left + (right - left) * index / max(1, len(labels) - 1)
        draw.text((x - 25, bottom + 18), label, fill="#17313a", font=font)
    draw.text(((left + right) // 2 - 55, bottom + 48), "Held-out operator", fill="#17313a", font=font)
    if metrics.get("synthetic") is True:
        draw.text((left, 30), "PROJECTED — synthetic values, not empirical results", fill="#9b3c2e", font=font)
    for destination in (Path(args.png), Path(args.pdf)):
        destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.png)
    image.save(args.pdf, "PDF", resolution=150)


if __name__ == "__main__":
    main()
