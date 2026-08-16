#!/usr/bin/env python3
"""Validate the committed synthetic fixture used only for layout preview."""

import json
from pathlib import Path


def main():
    path = Path(__file__).with_name("projected_fixture.json")
    payload = json.loads(path.read_text())
    if payload.get("synthetic") is not True:
        raise SystemExit("projected fixture must be synthetic")
    if "projected_tables" in payload:
        raise SystemExit("projected fixture cannot contain paper result tables")
    print(path)


if __name__ == "__main__":
    main()
