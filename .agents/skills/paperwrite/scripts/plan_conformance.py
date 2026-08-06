#!/usr/bin/env python3
"""Check that a paperwrite paper and result bundle preserve an approved experiment plan.

The approved plan embeds a JSON contract in its HTML. This checker deliberately
does not infer scientific equivalence: one aggregate table cannot satisfy two
separately approved per-setting artifacts. Every promised artifact therefore
has its own stable LaTeX label and every required result dimension has its own
JSON key path.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


INPUT_RE = re.compile(r"\\(?:input|include)\{([^}]+)\}")
FLOAT_RE = re.compile(
    r"\\begin\{(figure\*?|table\*?)\}(.*?)\\end\{\1\}",
    re.DOTALL,
)
LABEL_RE = re.compile(r"\\label\{([^}]+)\}")
CONTRACT_RE = re.compile(
    r"<script\b[^>]*\bid=[\"']experiment-plan-contract[\"'][^>]*>"
    r"(.*?)</script>",
    re.DOTALL | re.IGNORECASE,
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def expand_tex(path: Path, seen: set[Path] | None = None) -> str:
    """Recursively expand local \\input/\\include commands in source order."""
    seen = set() if seen is None else seen
    path = path.resolve()
    if path in seen:
        return ""
    seen.add(path)
    text = read_text(path)

    def replace(match: re.Match[str]) -> str:
        child = path.parent / match.group(1)
        if child.suffix == "":
            child = child.with_suffix(".tex")
        if not child.exists():
            return match.group(0)
        return expand_tex(child, seen)

    return INPUT_RE.sub(replace, text)


def get_path(value: Any, dotted: str) -> tuple[bool, Any]:
    """Resolve a dotted path; ``[]`` means any list element."""
    nodes = [value]
    for raw_part in dotted.split("."):
        any_item = raw_part.endswith("[]")
        part = raw_part[:-2] if any_item else raw_part
        next_nodes: list[Any] = []
        for node in nodes:
            if not isinstance(node, dict) or part not in node:
                continue
            selected = node[part]
            if any_item:
                if isinstance(selected, list):
                    next_nodes.extend(selected)
            else:
                next_nodes.append(selected)
        if not next_nodes:
            return False, None
        nodes = next_nodes
    return True, nodes


def load_json_files(results_dir: Path) -> list[tuple[Path, Any]]:
    loaded = []
    if not results_dir.exists():
        return loaded
    for path in sorted(results_dir.rglob("*.json")):
        try:
            loaded.append((path, json.loads(read_text(path))))
        except json.JSONDecodeError:
            continue
    return loaded


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", default="reports/03_EXPERIMENT_PLAN.html", type=Path)
    parser.add_argument("--paper-dir", default="paper", type=Path)
    parser.add_argument("--results-dir", default="results", type=Path)
    parser.add_argument("--main", default="main.tex")
    parser.add_argument(
        "--results-only",
        action="store_true",
        help="Check plan approval and result dimensions before a paper exists.",
    )
    args = parser.parse_args()

    violations: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if not args.plan.exists():
        result = {
            "check": "plan_conformance",
            "ok": False,
            "violations": [{"issue": "missing_plan", "path": str(args.plan)}],
            "warnings": [],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    plan_text = read_text(args.plan)
    contract_match = CONTRACT_RE.search(plan_text)
    if contract_match is None:
        result = {
            "check": "plan_conformance",
            "ok": False,
            "violations": [
                {
                    "issue": "missing_embedded_contract",
                    "path": str(args.plan),
                    "id": "experiment-plan-contract",
                }
            ],
            "warnings": [],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    try:
        contract = json.loads(contract_match.group(1))
    except json.JSONDecodeError as exc:
        result = {
            "check": "plan_conformance",
            "ok": False,
            "violations": [
                {
                    "issue": "invalid_embedded_contract",
                    "path": str(args.plan),
                    "error": str(exc),
                }
            ],
            "warnings": [],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    if contract.get("approval_status") != "approved":
        violations.append(
            {
                "issue": "plan_not_approved",
                "value": contract.get("approval_status"),
            }
        )

    actual_floats: dict[str, dict[str, Any]] = {}
    all_float_labels: set[str] = set()
    artifact_results = []
    if not args.results_only:
        main_tex = args.paper_dir / args.main
        if not main_tex.exists():
            violations.append({"issue": "missing_paper_main", "path": str(main_tex)})
            expanded = ""
        else:
            expanded = expand_tex(main_tex)

        appendix_at = expanded.find(r"\appendix")
        if appendix_at < 0:
            appendix_at = len(expanded) + 1

        for match in FLOAT_RE.finditer(expanded):
            kind = match.group(1).rstrip("*")
            block = match.group(2)
            labels = LABEL_RE.findall(block)
            for label in labels:
                all_float_labels.add(label)
                actual_floats[label] = {
                    "kind": kind,
                    "placement": (
                        "body" if match.start() < appendix_at else "appendix"
                    ),
                }

        expected_labels: set[str] = set()
        for artifact in contract.get("paper_artifacts", []):
            label = artifact["label"]
            expected_labels.add(label)
            actual = actual_floats.get(label)
            artifact_result = {
                "id": artifact.get("id"),
                "label": label,
                "expected_kind": artifact.get("kind"),
                "expected_placement": artifact.get("placement", "body"),
                "actual": actual,
                "ok": True,
            }
            if actual is None:
                artifact_result["ok"] = False
                violations.append(
                    {
                        "issue": "missing_planned_artifact",
                        "id": artifact.get("id"),
                        "label": label,
                    }
                )
            else:
                if artifact.get("kind") and actual["kind"] != artifact["kind"]:
                    artifact_result["ok"] = False
                    violations.append(
                        {
                            "issue": "planned_artifact_kind_mismatch",
                            "label": label,
                            "expected": artifact["kind"],
                            "actual": actual["kind"],
                        }
                    )
                placement = artifact.get("placement", "body")
                if placement == "body" and actual["placement"] != "body":
                    artifact_result["ok"] = False
                    violations.append(
                        {
                            "issue": "planned_body_artifact_moved",
                            "label": label,
                            "actual": actual["placement"],
                        }
                    )
            artifact_results.append(artifact_result)

        for label in sorted(all_float_labels - expected_labels):
            warnings.append({"issue": "unmapped_paper_float", "label": label})

        required_labels = contract.get("required_labels", [])
        source_labels = set(LABEL_RE.findall(expanded))
        for item in required_labels:
            label = item["label"] if isinstance(item, dict) else item
            if label not in source_labels:
                violations.append({"issue": "missing_required_label", "label": label})

    json_files = load_json_files(args.results_dir)
    result_checks = []
    for requirement in contract.get("result_requirements", []):
        paths = requirement.get("any_of", [])
        matches = []
        for json_path, payload in json_files:
            for dotted in paths:
                exists, values = get_path(payload, dotted)
                if exists:
                    matches.append({"file": str(json_path), "path": dotted})
        ok = bool(matches)
        result_checks.append(
            {
                "id": requirement.get("id"),
                "any_of": paths,
                "matches": matches,
                "ok": ok,
            }
        )
        if not ok:
            violations.append(
                {
                    "issue": "missing_result_dimension",
                    "id": requirement.get("id"),
                    "any_of": paths,
                    "supports": requirement.get("supports", []),
                }
            )

    result = {
        "check": "plan_conformance",
        "ok": not violations,
        "contract_source": f"{args.plan}#experiment-plan-contract",
        "plan": str(args.plan),
        "expected_artifacts": len(contract.get("paper_artifacts", [])),
        "mapped_artifacts_found": sum(1 for item in artifact_results if item["ok"]),
        "actual_labeled_floats": len(actual_floats),
        "results_only": args.results_only,
        "artifact_checks": artifact_results,
        "result_checks": result_checks,
        "violations": violations,
        "warnings": warnings,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
