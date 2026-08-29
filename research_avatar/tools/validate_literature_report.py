#!/usr/bin/env python3
"""Validate that a literature report is rendered from one verified record set."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import re
import sys
import unicodedata
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


def normalized_title(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).casefold()
    return " ".join(re.findall(r"[a-z0-9]+", text))


def title_matches(expected: object, observed: object) -> bool:
    expected_tokens = normalized_title(expected).split()
    observed_tokens = normalized_title(observed).split()
    if not expected_tokens or not observed_tokens:
        return False
    expected_set, observed_set = set(expected_tokens), set(observed_tokens)
    return len(expected_set & observed_set) / len(expected_set) >= 0.9


def audit_live_sources(source: str, timeout: float = 20.0) -> tuple[list[str], list[str]]:
    """Reopen every paper and verify identity against a primary or authoritative fallback."""
    match = CONTRACT_RE.search(source)
    if not match:
        return ["missing literature-verification contract"], []
    contract = json.loads(match.group(1))
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError as exc:
        return [f"live literature verification dependency is unavailable: {exc}"], []

    errors: list[str] = []
    warnings: list[str] = []
    def verify_one(paper: dict) -> tuple[list[str], list[str]]:
        session = requests.Session()
        session.headers["User-Agent"] = "Mozilla/5.0 ResearchAvatarEvidenceAudit/1.0"
        local_errors: list[str] = []
        local_warnings: list[str] = []
        paper_id, expected = str(paper.get("id", "")), str(paper.get("title", ""))
        attempts: list[str] = []
        verified_by = ""
        for candidate in dict.fromkeys(
            str(value) for value in (paper.get("url"), paper.get("arxiv_url")) if value
        ):
            try:
                response = session.get(candidate, timeout=timeout, allow_redirects=True)
                page_title = BeautifulSoup(response.text, "html.parser").title
                observed = page_title.get_text(" ", strip=True) if page_title else ""
                attempts.append(f"{candidate} -> HTTP {response.status_code} -> {response.url} -> {observed[:120]}")
                if response.status_code < 400 and title_matches(expected, observed):
                    verified_by = candidate
                    if candidate != paper.get("url"):
                        local_warnings.append(f"{paper_id}: primary page was access-controlled or obscured; identity verified through {candidate}")
                    break
            except requests.RequestException as exc:
                attempts.append(f"{candidate} -> {type(exc).__name__}: {exc}")
        if not verified_by and paper.get("doi"):
            doi_url = f'https://api.crossref.org/works/{paper["doi"]}'
            try:
                response = session.get(doi_url, timeout=timeout)
                titles = response.json().get("message", {}).get("title", []) if response.status_code < 400 else []
                observed = titles[0] if titles else ""
                attempts.append(f"{doi_url} -> HTTP {response.status_code} -> {observed[:120]}")
                if title_matches(expected, observed):
                    verified_by = doi_url
                    local_warnings.append(f"{paper_id}: landing-page identity verified through DOI metadata")
            except (requests.RequestException, ValueError, KeyError) as exc:
                attempts.append(f"{doi_url} -> {type(exc).__name__}: {exc}")
        if not verified_by:
            local_errors.append(f"{paper_id}: no live authoritative page matched the recorded title; " + " | ".join(attempts))
        return local_errors, local_warnings

    papers = [paper for paper in contract.get("papers", []) if isinstance(paper, dict)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(papers) or 1)) as executor:
        for local_errors, local_warnings in executor.map(verify_one, papers):
            errors.extend(local_errors)
            warnings.extend(local_warnings)
    return errors, warnings


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
    if not str(contract.get("topic", "")).strip():
        errors.append("literature-verification topic is required")
    try:
        search_date = dt.date.fromisoformat(str(contract.get("search_date", "")))
        if search_date > dt.date.today():
            errors.append("search_date is in the future")
    except ValueError:
        errors.append("search_date must be ISO YYYY-MM-DD")
    paper_ids: list[str] = []
    for index, paper in enumerate(papers):
        if not isinstance(paper, dict):
            errors.append(f"papers[{index}] must be an object")
            continue
        missing = [
            field for field in (
                "id", "title", "authors", "year", "publication_status", "venue",
                "url", "final_url", "page_title", "verified_at",
            )
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
    known = set(paper_ids)
    angles = contract.get("search_angles")
    if not isinstance(angles, list) or not 4 <= len(angles) <= 6:
        errors.append("search_angles must contain 4 to 6 structured angles")
    else:
        angle_ids: list[str] = []
        for index, angle in enumerate(angles):
            if not isinstance(angle, dict):
                errors.append(f"search_angles[{index}] must be an object")
                continue
            angle_id = str(angle.get("id", "")).strip()
            angle_ids.append(angle_id)
            for field in ("title", "queries", "recency_queries", "paper_ids"):
                value = angle.get(field)
                if field.endswith("queries") or field == "paper_ids":
                    if not isinstance(value, list) or not value:
                        errors.append(f"search_angles[{index}].{field} must be a non-empty list")
                elif not str(value or "").strip():
                    errors.append(f"search_angles[{index}].{field} is required")
            if isinstance(angle.get("paper_ids"), list) and any(
                str(value) not in known for value in angle["paper_ids"]
            ):
                errors.append(f"search_angles[{index}] references an unknown paper")
        if any(not value for value in angle_ids) or len(angle_ids) != len(set(angle_ids)):
            errors.append("search angle IDs must be unique and non-empty")
    falsification = contract.get("gap_falsification")
    if not isinstance(falsification, dict):
        errors.append("gap_falsification must be an object")
    else:
        queries = falsification.get("queries")
        if not isinstance(queries, list) or len(queries) < 3:
            errors.append("gap_falsification requires at least three counterevidence queries")
        collision = str(falsification.get("closest_collision_id", "")).strip()
        if collision not in known:
            errors.append("gap_falsification closest_collision_id must resolve to a paper")
        if not str(falsification.get("bounded_difference", "")).strip():
            errors.append("gap_falsification bounded_difference is required")
    family_ids: list[str] = []
    family_members: list[str] = []
    for index, family in enumerate(families):
        if not isinstance(family, dict):
            errors.append(f"families[{index}] must be an object")
            continue
        family_id = str(family.get("id", ""))
        family_ids.append(family_id)
        if not str(family.get("failure_boundary", "")).strip():
            errors.append(f"families[{index}] requires a failure_boundary")
        members = family.get("paper_ids")
        if not str(family.get("title", "")).strip() or not isinstance(members, list) or not members:
            errors.append(f"families[{index}] requires title and paper_ids")
        elif any(str(member) not in known for member in members):
            errors.append(f"families[{index}] references an unknown paper")
        else:
            family_members.extend(str(member) for member in members)
    if len(family_ids) != len(set(family_ids)) or any(not value for value in family_ids):
        errors.append("family IDs must be unique and non-empty")
    if set(family_members) != known:
        errors.append("family memberships must cover every verified paper")
    if contract.get("paper_count") != len(papers):
        errors.append("paper_count does not equal the verified paper records")
    if contract.get("family_count") != len(families):
        errors.append("family_count does not equal the verified family records")
    lanes = contract.get("evidence_lanes")
    if not isinstance(lanes, list) or {
        str(item.get("id", "")) for item in lanes if isinstance(item, dict)
    } != {"established", "current-reviewed", "frontier-preprints"}:
        errors.append("evidence_lanes must separate established, current-reviewed, and frontier-preprints")
    else:
        lane_members = [
            str(paper_id)
            for lane in lanes
            for paper_id in lane.get("paper_ids", [])
        ]
        if sorted(lane_members) != sorted(paper_ids) or len(lane_members) != len(set(lane_members)):
            errors.append("evidence_lanes must cover every paper exactly once")
        for lane in lanes:
            if f'data-evidence-lane="{lane["id"]}"' not in source:
                errors.append(f'evidence lane {lane["id"]} is not rendered')
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
    parser.add_argument("--offline", action="store_true", help="validate the saved receipt without reopening sources")
    args = parser.parse_args()
    errors = validate(args.report.read_text(encoding="utf-8"))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    if not args.offline:
        live_errors, warnings = audit_live_sources(args.report.read_text(encoding="utf-8"))
        for warning in warnings:
            print(f"WARNING: {warning}")
        if live_errors:
            for error in live_errors:
                print(f"ERROR: {error}")
            return 1
    print(f"OK: literature evidence and rendered counts match {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
