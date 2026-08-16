#!/usr/bin/env python3
"""Generate deterministic synthetic values from the frozen figure schema."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCHEMA = Path(__file__).with_name("figure_schema.json")
OUTPUT = Path(__file__).with_name("projected_fixture.json")


def main():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    values = {
        "F2.confirmation_matrix": {
            "categories": schema["figures"]["F2"][0]["categories"],
            "series": [{"name": "Margin minus random", "values": [0.014, 0.011, 0.006, 0.015, 0.005, 0.018]}],
        },
        "F3.budget_curve": {
            "categories": schema["figures"]["F3"][0]["categories"],
            "series": [
                {"name": "Random", "values": [0.88, 0.885, 0.89]},
                {"name": "Margin-targeted", "values": [0.887, 0.898, 0.908]}
            ],
        },
    }
    for figure_id, panels in schema["figures"].items():
        panel = panels[0]
        item = values[panel["fixture_key"]]
        marks = sum(len(series["values"]) for series in item["series"])
        if marks != panel["plotted_marks"]:
            raise ValueError(f"{figure_id}: schema expects {panel['plotted_marks']} marks, got {marks}")
    OUTPUT.write_text(json.dumps({"synthetic": True, "traceable_results": values}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
