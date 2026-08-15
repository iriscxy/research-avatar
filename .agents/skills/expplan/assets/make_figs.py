#!/usr/bin/env python3
"""Render projected or final paper figures from a frozen figure schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


COLORS = ("#173f5f", "#d75b3f", "#16877a", "#7b61a8")
MARKERS = ("o", "s", "D", "^")


def validate_rendered_marks(ax: plt.Axes, expected: int) -> None:
    rendered = sum(len(collection.get_offsets()) for collection in ax.collections) + len(ax.patches)
    if rendered != expected:
        raise ValueError(f"rendered marks {rendered} != schema plotted_marks {expected}")


def draw_panel_lines(ax: plt.Axes, panel: dict, result: dict) -> None:
    x_values = result["x"]
    if x_values != panel["x_values"]:
        raise ValueError("metrics x values do not match the frozen source table")
    for index, name in enumerate(panel["series"]):
        values = result["series"].get(name)
        if values is None or len(values) != len(x_values):
            raise ValueError(f"missing or malformed series: {name}")
        ax.plot(x_values, values, color=COLORS[index], linewidth=2.1, alpha=0.9)
        ax.scatter(x_values, values, color=COLORS[index], marker=MARKERS[index], s=34,
                   edgecolor="white", linewidth=0.7, label=name, zorder=3)
    ax.set_xlabel(panel["x_axis"])
    ax.set_ylabel(panel["y_axis"])
    ax.set_ylim(0.0, 1.02)
    ax.grid(True, color="#d9e2e6", linewidth=0.8, alpha=0.75)
    ax.legend(frameon=False, fontsize=8, loc="best")
    validate_rendered_marks(ax, panel["plotted_marks"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", required=True, type=Path)
    parser.add_argument("--figure", required=True)
    parser.add_argument("--panel", required=True)
    parser.add_argument("--metrics", required=True, type=Path)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--png", required=True, type=Path)
    args = parser.parse_args()
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    metrics = json.loads(args.metrics.read_text(encoding="utf-8"))
    panels = schema["figures"].get(args.figure)
    selected = next((item for item in panels or [] if item["panel"] == args.panel), None)
    if selected is None:
        raise ValueError(f"unknown figure/panel: {args.figure}/{args.panel}")
    result = metrics.get("traceable_results", {}).get(selected["fixture_key"])
    if result is None:
        raise ValueError(f"missing metrics key: {selected['fixture_key']}")
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    draw_panel_lines(ax, selected, result)
    titles = {
        "exit_depth": "Where safety trajectories leave the tube",
        "first_exit_concentration": "First exits for successful jailbreaks",
        "repair_offset": "Repair effectiveness by layer offset",
        "downstream_recovery": "Downstream safety-trajectory recovery",
        "repair_strength": "Safety–utility sensitivity to repair strength",
    }
    ax.set_title(titles[selected["panel"]], loc="left", fontweight="bold")
    if metrics.get("synthetic") is True:
        fig.text(0.5, 0.5, "PROJECTED SHAPE — NOT RESULTS", ha="center", va="center",
                 rotation=22, fontsize=16, color="#b23a2b", alpha=0.2, weight="bold")
    fig.tight_layout()
    args.pdf.parent.mkdir(parents=True, exist_ok=True)
    args.png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.pdf)
    fig.savefig(args.png, dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
