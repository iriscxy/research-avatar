#!/usr/bin/env python3
"""Create schema-conforming synthetic previews for First-Divergence Repair."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def projected_value(panel: str, series_index: int, point_index: int, point_count: int) -> float:
    p = point_index / max(point_count - 1, 1)
    if panel == "exit_depth":
        return round((0.08 + 0.55 * p) if series_index == 0 else (0.05 + 0.82 * p), 3)
    if panel == "first_exit_concentration":
        center = 0.43 if series_index == 0 else 0.68
        return round(0.05 + (0.58 if series_index == 0 else 0.32) * math.exp(-18 * (p - center) ** 2), 3)
    if panel == "repair_offset":
        x = point_index - (point_count // 2)
        return round((0.46 + 0.48 * math.exp(-0.72 * x * x)) if series_index == 0 else (0.93 - 0.05 * math.exp(-0.45 * x * x)), 3)
    if panel == "downstream_recovery":
        if series_index == 0:
            return round(0.42 - 0.10 * p, 3)
        if series_index == 1:
            return round(0.48 + 0.44 * (1 - math.exp(-3.2 * p)), 3)
        return round(0.47 + 0.14 * (1 - math.exp(-2.0 * p)), 3)
    if panel == "repair_strength":
        if series_index == 0:
            return round(0.48 + 0.45 * (1 - math.exp(-3.0 * p)), 3)
        if series_index == 1:
            return round(0.98 - 0.12 * p**1.5, 3)
        return round(0.99 - 0.08 * p**1.3, 3)
    raise ValueError(f"unsupported panel: {panel}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-schema", required=True)
    args = parser.parse_args()
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    traceable_results = {}
    for figure, panels in schema["figures"].items():
        for panel in panels:
            xs = panel["x_values"]
            names = panel["series"]
            if len(xs) * len(names) != panel["plotted_marks"]:
                raise ValueError(f"{figure}/{panel['panel']}: frozen table/mark mismatch")
            values = {
                name: [projected_value(panel["panel"], s, i, len(xs)) for i in range(len(xs))]
                for s, name in enumerate(names)
            }
            if sum(map(len, values.values())) != panel["pending_values"]:
                raise ValueError(f"{figure}/{panel['panel']}: fixture scalar mismatch")
            traceable_results[panel["fixture_key"]] = {"x": xs, "series": values}
    payload = {
        "synthetic": True,
        "notice": "PROJECTED SHAPE — NOT RESULTS",
        "source_schema": args.source_schema,
        "traceable_results": traceable_results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
