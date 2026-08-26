#!/usr/bin/env python3
"""Validate that a literature report is rendered from one verified record set."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


CONTRACT_RE = re.compile(
    r'<script\b[^>]*id=["\']literature-verification["\'][^>]*>(.*?)</script>',
    re.I | re.S,
)
PLACEHOLDER_HOSTS = {"example.com", "example.org", "example.net", "localhost"}


def valid_url(value: object) -> bool:
    try:
        parsed = urlparse(str(value))
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    return (
        parsed.scheme in {"http", "https"}
        and bool(parsed.path.strip("/"))
        and host not in PLACEHOLDER_HOSTS
        and not host.endswith(".example.com")
    )


def validate(source: str) -> list[str]:
    match = CONTRACT_RE.search(source)
    if not match:
        return ["missing literature-verification contract"]
    try:
        contract = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        return [f"invalid literature-verification JSON: {exc}"]
    errors: list[str] = []
    papers = contract.get("papers")
    families = contract.get("families")
    if not isinstance(papers, list) or not papers:
        return ["literature-verification papers must be a non-empty list"]
    if not isinstance(families, list) or not families:
        return ["literature-verification families must be a non-empty list"]
    paper_ids: list[str] = []
    for index, paper in enumerate(papers):
        if not isinstance(paper, dict):
            errors.append(f"papers[{index}] must be an object")
            continue
        missing = [
            field for field in ("id", "title", "url", "final_url", "page_title", "verified_at")
            if not str(paper.get(field, "")).strip()
        ]
        if missing:
            errors.append(f"papers[{index}] lacks {missing}")
        paper_id = str(paper.get("id", ""))
        paper_ids.append(paper_id)
        if not valid_url(paper.get("url")) or not valid_url(paper.get("final_url")):
            errors.append(f"papers[{index}] has an invalid or placeholder URL")
        try:
            checked = dt.date.fromisoformat(str(paper.get("verified_at", "")))
            if checked > dt.date.today():
                errors.append(f"papers[{index}] verification date is in the future")
        except ValueError:
            errors.append(f"papers[{index}] verified_at must be ISO YYYY-MM-DD")
    if len(paper_ids) != len(set(paper_ids)) or any(not value for value in paper_ids):
        errors.append("paper IDs must be unique and non-empty")
    family_ids: list[str] = []
    known = set(paper_ids)
    for index, family in enumerate(families):
        if not isinstance(family, dict):
            errors.append(f"families[{index}] must be an object")
            continue
        family_id = str(family.get("id", ""))
        family_ids.append(family_id)
        members = family.get("paper_ids")
        if not str(family.get("title", "")).strip() or not isinstance(members, list) or not members:
            errors.append(f"families[{index}] requires title and paper_ids")
        elif any(str(member) not in known for member in members):
            errors.append(f"families[{index}] references an unknown paper")
    if len(family_ids) != len(set(family_ids)) or any(not value for value in family_ids):
        errors.append("family IDs must be unique and non-empty")
    if contract.get("paper_count") != len(papers):
        errors.append("paper_count does not equal the verified paper records")
    if contract.get("family_count") != len(families):
        errors.append("family_count does not equal the verified family records")
    rendered_papers = set(re.findall(r'\bdata-paper-id=["\']([^"\']+)', source, re.I))
    rendered_families = set(re.findall(r'\bdata-family-id=["\']([^"\']+)', source, re.I))
    if rendered_papers != set(paper_ids):
        errors.append("rendered paper cards do not exactly match verified paper records")
    if rendered_families != set(family_ids):
        errors.append("rendered families do not exactly match verified family records")
    for paper in papers:
        if f'href="{paper.get("url")}"' not in source:
            errors.append(f"rendered report lacks verified URL for {paper.get('id')}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    errors = validate(args.report.read_text(encoding="utf-8"))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"OK: literature evidence and rendered counts match {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
