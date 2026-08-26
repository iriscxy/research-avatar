#!/usr/bin/env python3
"""Verify that final Idea-report prose is covered by a supported LLM API receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString

from rewrite_ideagen_html import RECEIPT_ID, eligible_string, normalize, reference_graph


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("html", type=Path)
    args = parser.parse_args()
    soup = BeautifulSoup(args.html.read_text(encoding="utf-8"), "html.parser")
    errors: list[str] = []
    receipt_tag = soup.find("script", id=RECEIPT_ID)
    if receipt_tag is None:
        errors.append("missing ideagen-readable-rewrite receipt")
        receipt = {}
    else:
        try:
            receipt = json.loads(receipt_tag.string or "")
        except json.JSONDecodeError as exc:
            errors.append(f"invalid readability receipt JSON: {exc}")
            receipt = {}
    if receipt.get("status") != "complete" or receipt.get("provider") not in {"openai-api", "deepseek-api"}:
        errors.append("readability receipt must record a complete supported LLM API pass")
    if not str(receipt.get("model", "")).strip():
        errors.append("readability receipt lacks model")
    before_graph = str(receipt.get("reference_graph_before_sha256", ""))
    after_graph = str(receipt.get("reference_graph_after_sha256", ""))
    current_graph = reference_graph(soup)["sha256"]
    if not before_graph or before_graph != after_graph or after_graph != current_graph:
        errors.append("readability rewrite did not preserve the link/footnote reference graph")
    if receipt.get("footnote_count") != reference_graph(soup)["footnote_count"]:
        errors.append("readability receipt footnote count differs from final HTML")
    response_ids = receipt.get("api_response_ids")
    if not isinstance(response_ids, list) or not response_ids or any(not str(value).strip() for value in response_ids):
        errors.append("readability receipt lacks API response IDs")

    spans = soup.find_all("span", attrs={"data-gpt-rewrite-id": True})
    records = receipt.get("nodes", []) if isinstance(receipt.get("nodes"), list) else []
    record_by_id = {str(item.get("id")): item for item in records if isinstance(item, dict)}
    if receipt.get("eligible_nodes") != receipt.get("rewritten_nodes") or receipt.get("rewritten_nodes") != len(spans):
        errors.append("eligible, rewritten, and wrapped node counts differ")
    seen: set[str] = set()
    for span in spans:
        node_id = str(span.get("data-gpt-rewrite-id", ""))
        text = normalize(span.get_text(" ", strip=True))
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if not node_id or node_id in seen:
            errors.append(f"missing or duplicate rewrite node id: {node_id!r}")
        seen.add(node_id)
        record = record_by_id.get(node_id, {})
        if digest != span.get("data-gpt-output-sha256") or digest != record.get("output_sha256"):
            errors.append(f"rewrite digest mismatch for {node_id}")

    uncovered = [
        normalize(str(node)) for node in soup.find_all(string=True)
        if isinstance(node, NavigableString) and eligible_string(node)
        and node.find_parent(attrs={"data-gpt-rewrite-id": True}) is None
    ]
    if uncovered:
        errors.append(f"{len(uncovered)} eligible visible prose nodes are outside GPT rewrite spans: {uncovered[:3]!r}")
    if set(record_by_id) != seen:
        errors.append("receipt node IDs do not exactly match final HTML rewrite spans")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(json.dumps({
        "status": "PASS", "file": str(args.html), "model": receipt["model"],
        "rewritten_nodes": len(spans), "api_calls": len(response_ids),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
