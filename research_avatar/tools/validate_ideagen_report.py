#!/usr/bin/env python3
"""Validate general decision-slate invariants in an ideagen HTML report."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


ARTICLE_RE = re.compile(
    r'<article\b(?P<attrs>[^>]*\bdata-idea-id=["\'][^"\']+["\'][^>]*)>', re.I
)
ATTR_RE = re.compile(r'\b([\w-]+)=["\']([^"\']*)["\']')
GENERATION_RE = re.compile(
    r'<script\b[^>]*id=["\']idea-generation["\'][^>]*>(.*?)</script>', re.I | re.S
)
IDEA_FIELDS = ("research_focus", "method", "validation", "title")
AUDIT_RE = re.compile(
    r'<script\b[^>]*id=["\']idea-novelty-audit["\'][^>]*>(.*?)</script>', re.I | re.S
)

ALLOWED = {"ESSENTIAL", "EVALUATION_SCOPE_ONLY", "APPLICATION_SWAP", "[UNVERIFIED]"}
ACTION = {
    "ESSENTIAL": "retain",
    "EVALUATION_SCOPE_ONLY": "relabel",
    "APPLICATION_SWAP": "reforge",
    "[UNVERIFIED]": "test",
}
NOVELTY_TIERS = {"novel": "A", "differentiable": "B"}
PLACEHOLDER_HOSTS = {"example.com", "example.org", "example.net", "localhost"}
DATASET_STATUSES = {
    "PUBLISHED", "PUBLIC_REPOSITORY", "USER_PROVIDED_PRIVATE", "SELF_BUILT_UNPUBLISHED",
}


def valid_source_url(value: object) -> bool:
    try:
        parsed = urlparse(str(value))
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    return (
        parsed.scheme in {"http", "https"}
        and bool(host)
        and host not in PLACEHOLDER_HOSTS
        and not host.endswith(".example.com")
        and bool(parsed.path.strip("/"))
    )


def validate_generation(source: str) -> list[str]:
    """Check that the slate comes from one research question in one Jinghui setting."""
    match = GENERATION_RE.search(source)
    if not match:
        return ["missing idea-generation record"]
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        return [f"invalid idea-generation JSON: {exc}"]
    errors: list[str] = []
    direction = payload.get("research_direction")
    if direction:
        if not str(direction.get("title", "")).strip() or not str(direction.get("id", "")).strip():
            errors.append("idea-generation research_direction needs an id and a title")
        if direction.get("origin") not in {"neutral", "personalized", "researcher"}:
            errors.append("idea-generation research_direction origin must be neutral, personalized, or researcher")
        seen_questions = set()
        for item in payload.get("candidates", []):
            question = item.get("research_question") or {}
            text = str(question.get("question", "")).strip()
            if not text.endswith("?"):
                errors.append(f"{item.get('id', 'unknown')}: research_question must be one question ending with '?'")
            if text.lower() in seen_questions:
                errors.append(f"{item.get('id', 'unknown')}: research_question repeats another candidate's question")
            seen_questions.add(text.lower())
    else:
        question = payload.get("research_question") or {}
        if not str(question.get("question", "")).strip().endswith("?"):
            errors.append("idea-generation research_question must be one question ending with '?'")
        if question.get("origin") not in {"neutral", "personalized", "researcher"}:
            errors.append("idea-generation research_question origin must be neutral, personalized, or researcher")
    setting = payload.get("setting")
    if setting not in {"profile", "none"}:
        errors.append("idea-generation setting must be profile or none")
    for item in payload.get("candidates", []):
        idea_id = item.get("id", "unknown")
        if item.get("setting") != setting:
            errors.append(f"{idea_id}: generation setting differs from the slate setting")
        output = item.get("output") or {}
        if any(not str(output.get(field, "")).strip() for field in IDEA_FIELDS):
            errors.append(f"{idea_id}: generation output needs research_focus, method, validation, and title")
        if not str(item.get("run_id", "")).strip():
            errors.append(f"{idea_id}: generation record needs the isolated context run_id")
        if setting == "none" and item.get("retrieved_ids"):
            errors.append(f"{idea_id}: the None setting cannot retrieve author_differences")
        if setting == "profile" and not item.get("retrieved_ids"):
            errors.append(f"{idea_id}: the Profile setting needs retrieved author_differences")
    return errors


def validate(source: str) -> list[str]:
    errors: list[str] = []
    articles = list(ARTICLE_RE.finditer(source))
    if not articles:
        return ["no selectable idea cards found"]
    audit_match = AUDIT_RE.search(source)
    if not audit_match:
        return ["missing independent idea-novelty-audit contract"]
    try:
        audit_payload = json.loads(audit_match.group(1))
    except json.JSONDecodeError as exc:
        return [f"invalid idea-novelty-audit JSON: {exc}"]
    audits = {
        str(item.get("idea_id", "")): item
        for item in audit_payload.get("candidates", []) if isinstance(item, dict)
    }
    errors += validate_generation(source)
    default_ids: list[str] = []
    for match in articles:
        attrs = dict(ATTR_RE.findall(match.group("attrs")))
        idea_id = attrs.get("data-idea-id", "unknown")
        status = attrs.get("data-scope-necessity")
        action = attrs.get("data-scope-action")
        falsifier = attrs.get("data-scope-falsifier", "").strip()
        novelty = attrs.get("data-novelty-status", "").strip().lower()
        tier = attrs.get("data-idea-tier", "").strip().upper()
        default_pick = attrs.get("data-default-pick", "").strip().lower()
        audit = audits.get(idea_id)
        if audit is None:
            errors.append(f"{idea_id}: missing independent novelty audit")
        else:
            verdict = str(audit.get("verdict", "")).strip().lower()
            urls = audit.get("source_urls", [])
            if verdict != novelty:
                errors.append(f"{idea_id}: card novelty disagrees with independent audit")
            if audit.get("absorbable") is not False:
                errors.append(f"{idea_id}: selectable idea remains absorbable by closest work")
            if not isinstance(urls, list) or len(set(urls)) < 2 or any(
                not valid_source_url(url) for url in urls
            ):
                errors.append(f"{idea_id}: novelty audit requires at least two direct source URLs")
            for field in ("closest_work", "overlap", "independent_difference", "latest_search_date"):
                if not str(audit.get(field, "")).strip():
                    errors.append(f"{idea_id}: novelty audit missing {field}")
            try:
                checked = dt.date.fromisoformat(str(audit.get("latest_search_date", "")))
                if checked > dt.date.today():
                    errors.append(f"{idea_id}: novelty audit search date cannot be in the future")
            except ValueError:
                errors.append(f"{idea_id}: novelty audit search date must be ISO YYYY-MM-DD")
            if audit.get("review_context") != "fresh":
                errors.append(f"{idea_id}: novelty audit must record review_context=fresh")
            if not str(audit.get("reviewer_run_id", "")).strip():
                errors.append(f"{idea_id}: novelty audit missing reviewer_run_id")
            queries = audit.get("counterevidence_queries")
            if not isinstance(queries, list) or len({str(item).strip() for item in queries if str(item).strip()}) < 3:
                errors.append(f"{idea_id}: novelty audit requires at least three counterevidence_queries")
            window = audit.get("recent_search_window")
            if not isinstance(window, dict) or not all(
                str(window.get(field, "")).strip() for field in ("start", "end")
            ):
                errors.append(f"{idea_id}: novelty audit lacks recent_search_window")
            assets = audit.get("dataset_assets")
            if not isinstance(assets, list):
                errors.append(f"{idea_id}: novelty audit dataset_assets must be a list")
            else:
                for asset_index, asset in enumerate(assets):
                    if not isinstance(asset, dict) or asset.get("status") not in DATASET_STATUSES:
                        errors.append(f"{idea_id}: dataset_assets[{asset_index}] has invalid status")
                        continue
                    if not str(asset.get("name", "")).strip():
                        errors.append(f"{idea_id}: dataset_assets[{asset_index}] lacks name")
                    if asset.get("status") in {"USER_PROVIDED_PRIVATE", "SELF_BUILT_UNPUBLISHED"}:
                        if str(asset.get("url", "")).strip():
                            errors.append(f"{idea_id}: private/unpublished dataset must not have an external URL")
                        if not str(asset.get("availability", "")).strip():
                            errors.append(f"{idea_id}: private/unpublished dataset lacks availability metadata")
            grounding = audit.get("source_grounding")
            if audit_payload.get("grounding_contract_version") == 1 and (
                not isinstance(grounding, list) or not grounding
            ):
                errors.append(f"{idea_id}: novelty audit requires source_grounding")
            elif isinstance(grounding, list):
                kinds = set()
                for grounding_index, item in enumerate(grounding):
                    if not isinstance(item, dict):
                        errors.append(f"{idea_id}: source_grounding[{grounding_index}] must be an object")
                        continue
                    kinds.add(str(item.get("kind", "")))
                    for field in ("title", "anchor", "failure_boundary"):
                        if not str(item.get(field, "")).strip():
                            errors.append(f"{idea_id}: source_grounding[{grounding_index}] lacks {field}")
                if not kinds.intersection({"Gap", "Opening", "Live Debate", "Failure Boundary", "Trend", "Research Direction"}):
                    errors.append(f"{idea_id}: source_grounding must name a Survey Gap/Opening, Live Debate, Failure Boundary, Trend, or Research Direction")
        if status not in ALLOWED:
            errors.append(f"{idea_id}: invalid or missing data-scope-necessity")
            continue
        if action != ACTION[status]:
            errors.append(f"{idea_id}: {status} requires data-scope-action={ACTION[status]}")
        if status == "APPLICATION_SWAP":
            errors.append(f"{idea_id}: APPLICATION_SWAP cannot remain selectable")
        if status == "[UNVERIFIED]" and not falsifier:
            errors.append(f"{idea_id}: [UNVERIFIED] scope requires a concrete falsifier")
        expected_tier = NOVELTY_TIERS.get(novelty)
        if expected_tier is None:
            errors.append(f"{idea_id}: selectable ideas must be novel or differentiable")
        elif tier != expected_tier:
            errors.append(f"{idea_id}: novelty={novelty} requires data-idea-tier={expected_tier}")
        if default_pick not in {"true", "false"}:
            errors.append(f"{idea_id}: data-default-pick must be true or false")
        elif novelty != "novel" and default_pick == "true":
            errors.append(f"{idea_id}: only a novel Tier A idea may be the default recommendation")
        elif default_pick == "true":
            default_ids.append(idea_id)
    if len(default_ids) > 1:
        errors.append("idea slate may contain at most one default recommendation")
    novel_ids = []
    for match in articles:
        attrs = dict(ATTR_RE.findall(match.group("attrs")))
        if attrs.get("data-novelty-status", "").strip().lower() == "novel" and \
                str(audits.get(attrs.get("data-idea-id", ""), {}).get("verdict", "")).lower() == "novel":
            novel_ids.append(attrs.get("data-idea-id"))
    if len(novel_ids) < 2 and 'data-crowded="true"' not in source:
        errors.append("the slate needs at least two independently confirmed novel ideas, "
                      "or must be marked crowded after the extra generation rounds")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    errors = validate(args.report.read_text(encoding="utf-8"))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        sys.exit(1)
    print("OK: ideagen scope-necessity contract is valid")


if __name__ == "__main__":
    main()
