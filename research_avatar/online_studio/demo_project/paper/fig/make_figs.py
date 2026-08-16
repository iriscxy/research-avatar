#!/usr/bin/env python3
"""Render typo-margin figures from the frozen table-first schema."""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


PALETTE = ["#087f74", "#c06a32", "#506aa8"]


def validate_rendered_marks(artists, expected):
    marks = sum(len(item.get_offsets()) if hasattr(item, "get_offsets") else 1 for item in artists)
    if marks != expected:
        raise ValueError(f"expected {expected} rendered marks, got {marks}")


def draw_panel_confirmation(ax, values, expected):
    series = values["series"][0]
    x = np.arange(len(values["categories"]))
    estimates = np.asarray(series["values"])
    lower = np.asarray(series["ci_low"])
    upper = np.asarray(series["ci_high"])
    errors = np.vstack((estimates - lower, upper - estimates))
    bars = ax.bar(
        x, estimates, yerr=errors, capsize=2.5, color=PALETTE[0], width=0.68,
        error_kw={"elinewidth": 0.9, "ecolor": "#263a42"},
    )
    ax.axhline(0, color="#263a42", linewidth=0.8)
    ax.set_ylabel("Accuracy gain")
    ax.set_xticks(x, values["categories"], rotation=28, ha="right")
    artists = list(bars)
    validate_rendered_marks(artists, expected)


def draw_panel_budget(ax, values, expected):
    x = np.arange(len(values["categories"]))
    artists = []
    for index, series in enumerate(values["series"]):
        points = ax.scatter(x, series["values"], color=PALETTE[index], s=34, label=series["name"], zorder=3)
        ax.plot(x, series["values"], color=PALETTE[index], linewidth=1.8)
        artists.append(points)
    ax.set_ylabel("Mean noisy accuracy")
    ax.set_xlabel("Augmentation budget")
    ax.set_xticks(x, values["categories"])
    ax.legend(frameon=False)
    validate_rendered_marks(artists, expected)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", default="paper/figsrc/typo_margin/figure_schema.json")
    parser.add_argument("--figure", required=True)
    parser.add_argument("--panel", required=True)
    parser.add_argument("--metrics", required=True)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--png", required=True)
    args = parser.parse_args()
    schema = json.loads(Path(args.schema).read_text(encoding="utf-8"))
    metrics = json.loads(Path(args.metrics).read_text(encoding="utf-8"))
    panel = next(item for item in schema["figures"][args.figure] if item["panel_id"] == args.panel)
    values = metrics["traceable_results"][panel["fixture_key"]]
    plt.rcParams.update({"font.family": "serif", "font.size": 9, "savefig.bbox": "standard"})
    fig, ax = plt.subplots(figsize=(3.32, 2.45))
    if args.figure == "F2":
        draw_panel_confirmation(ax, values, panel["plotted_marks"])
    elif args.figure == "F3":
        draw_panel_budget(ax, values, panel["plotted_marks"])
    else:
        raise ValueError(f"unsupported figure {args.figure}")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#dbe5e3", linewidth=0.6, zorder=0)
    if metrics.get("synthetic") is True:
        ax.text(0.5, 0.52, "PROJECTED SHAPE — NOT RESULTS", transform=ax.transAxes,
                ha="center", va="center", color="#9b3c2e", fontsize=8,
                bbox={"facecolor": "white", "edgecolor": "#9b3c2e", "alpha": 0.9})
    fig.tight_layout()
    for destination in (Path(args.pdf), Path(args.png)):
        destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.pdf)
    fig.savefig(args.png, dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
