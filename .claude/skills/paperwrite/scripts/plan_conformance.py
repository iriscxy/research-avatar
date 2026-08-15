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
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


INPUT_RE = re.compile(r"\\(?:input|include)\s*(?:\{([^}]+)\}|([^\s%]+))")
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
APPROVAL_FIELDS = {"approval_status", "approved_at", "approval_channel", "approval_contract_sha256"}


def contract_digest(contract: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in contract.items() if key not in APPROVAL_FIELDS}
    canonical = json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def visible_tex(source: str) -> str:
    source = "\n".join(
        re.split(r"(?<!\\)%", line, maxsplit=1)[0] for line in source.splitlines()
    )
    while re.search(r"\\iffalse\b.*?\\fi\b", source, re.S):
        source = re.sub(r"\\iffalse\b.*?\\fi\b", "", source, flags=re.S)
    return source


def expand_tex(path: Path, seen: set[Path] | None = None) -> str:
    """Recursively expand local \\input/\\include commands in source order."""
    seen = set() if seen is None else seen
    path = path.resolve()
    if path in seen:
        return ""
    seen.add(path)
    text = visible_tex(read_text(path))

    def replace(match: re.Match[str]) -> str:
        child = path.parent / (match.group(1) or match.group(2))
        if child.suffix == "":
            child = child.with_suffix(".tex")
        if not child.exists():
            return match.group(0)
        return expand_tex(child, seen)

    return INPUT_RE.sub(replace, text)


def get_path(value: Any, dotted: str) -> tuple[bool, Any]:
    """Resolve a dotted path; ``[]``/``*`` expand list or mapping members."""
    nodes = [value]
    for raw_part in dotted.split("."):
        expand_members = raw_part == "*"
        any_item = raw_part.endswith("[]")
        part = raw_part[:-2] if any_item else raw_part
        next_nodes: list[Any] = []
        for node in nodes:
            if expand_members:
                if isinstance(node, list):
                    next_nodes.extend(node)
                elif isinstance(node, dict):
                    next_nodes.extend(node.values())
                continue
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


def nonempty_result(value: Any) -> bool:
    """Treat JSON null and empty containers/strings as missing evidence."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value) and all(nonempty_result(item) for item in (
            value.values() if isinstance(value, dict) else value
        ))
    return True


def json_type_matches(value: Any, expected: str) -> bool:
    expected = expected.lower()
    if expected in {"array", "list"}:
        return isinstance(value, list)
    if expected in {"object", "dict"}:
        return isinstance(value, dict)
    if expected in {"number", "numeric"}:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected in {"integer", "int"}:
        return isinstance(value, int) and not isinstance(value, bool)
    if expected in {"string", "str"}:
        return isinstance(value, str)
    if expected in {"boolean", "bool"}:
        return isinstance(value, bool)
    return False


def parse_result_selector(selector: str) -> tuple[str | None, str]:
    """Split ``results/file.json:path`` while preserving legacy dotted paths."""
    file_name, separator, dotted = selector.partition(":")
    if separator and file_name.lower().endswith(".json"):
        return file_name, dotted
    return None, selector


def resolve_result_file(results_dir: Path, file_name: str) -> Path | None:
    """Resolve an explicit result file and keep it inside the results directory."""
    candidate = Path(file_name)
    if not candidate.is_absolute():
        parts = candidate.parts
        if parts and parts[0] == results_dir.name:
            candidate = results_dir.parent / candidate
        else:
            candidate = results_dir / candidate
    candidate = candidate.resolve()
    root = results_dir.resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def validate_result_values(values: Any, requirement: dict[str, Any]) -> list[str]:
    """Apply optional type/cardinality/schema checks to one resolved result path."""
    errors: list[str] = []
    if not nonempty_result(values):
        errors.append("empty_value")
        return errors
    resolved = values if isinstance(values, list) else [values]
    expected_type = str(requirement.get("expected_type", "")).strip()
    if expected_type and any(not json_type_matches(item, expected_type) for item in resolved):
        errors.append(f"wrong_type:{expected_type}")
    count = len(resolved)
    if requirement.get("exact_items") is not None and count != int(requirement["exact_items"]):
        errors.append(f"wrong_item_count:{count}")
    if requirement.get("min_items") is not None and count < int(requirement["min_items"]):
        errors.append(f"too_few_items:{count}")
    required_fields = requirement.get("required_fields", [])
    if required_fields:
        for item in resolved:
            if not isinstance(item, dict):
                errors.append("required_fields_on_non_object")
                break
            missing = [field for field in required_fields if not nonempty_result(item.get(field))]
            if missing:
                errors.append("missing_fields:" + ",".join(map(str, missing)))
                break
    expected_unit = requirement.get("unit")
    if expected_unit is not None and any(
        not isinstance(item, dict) or item.get("unit") != expected_unit for item in resolved
    ):
        errors.append(f"wrong_unit:{expected_unit}")
    return errors


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


def normalized_names(values: list[Any]) -> list[str]:
    return [re.sub(r"[^a-z0-9]+", "", str(value).lower()) for value in values]


def configured_table_columns(definition: dict[str, Any]) -> list[str]:
    grid = definition.get("data_grid", {})
    if grid.get("type") == "records":
        return [str(item.get("label") or item.get("key") or "") for item in grid.get("columns", [])]
    if grid.get("type") == "benchmark_rows":
        return [str(grid.get("row_key", ""))] + [
            str(item.get("label") or item.get("key") or "") for item in grid.get("metrics", [])
        ]
    return []


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
    elif contract.get("approval_contract_sha256") != contract_digest(contract):
        violations.append({"issue": "approved_contract_digest_mismatch"})

    actual_floats: dict[str, dict[str, Any]] = {}
    all_float_labels: set[str] = set()
    artifact_results = []
    if not args.results_only:
        waiver_files = [
            path for path in args.paper_dir.rglob("*") if path.is_file()
            and path.suffix.lower() in {".md", ".txt", ".json"}
            and re.search(
                r"(?:(?:artifact|ledger|plan|semantic).*(?:amend|waiv|override)|"
                r"(?:amend|waiv).*(?:artifact|ledger|plan|semantic))",
                path.name, re.I,
            )
        ]
        for amendment in waiver_files:
            violations.append(
                {
                    "issue": "posthoc_artifact_amendment_forbidden",
                    "path": str(amendment),
                    "remedy": "return to expplan and reapprove the canonical contract",
                }
            )
        studio_config_path = args.paper_dir / "paper_studio.json"
        studio_config: dict[str, Any] = {}
        if not studio_config_path.exists():
            violations.append(
                {"issue": "missing_paper_studio_config", "path": str(studio_config_path)}
            )
        else:
            try:
                studio_config = json.loads(read_text(studio_config_path))
            except json.JSONDecodeError as exc:
                violations.append(
                    {
                        "issue": "invalid_paper_studio_config",
                        "path": str(studio_config_path),
                        "error": str(exc),
                    }
                )
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
                    "block": block,
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
                "actual": ({key: value for key, value in actual.items() if key != "block"}
                           if actual else None),
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
                visible_dimensions = artifact.get("visible_dimensions", [])
                if set(map(str, visible_dimensions)) != set(map(str, artifact.get("dimensions", []))):
                    artifact_result["ok"] = False
                    violations.append({"issue": "artifact_visible_dimension_contract_drift",
                                       "id": artifact.get("id")})
                normalized_block = normalized_names([actual.get("block", "")])[0]
                missing_visible = [
                    dimension for dimension in visible_dimensions
                    if normalized_names([dimension])[0] not in normalized_block
                ]
                if missing_visible:
                    artifact_result["ok"] = False
                    violations.append({
                        "issue": "planned_artifact_dimensions_not_visible",
                        "id": artifact.get("id"), "missing": missing_visible,
                    })
            configured_group = (
                studio_config.get("figures", {})
                if artifact.get("kind") == "figure"
                else studio_config.get("tables", {})
            )
            configured = configured_group.get(artifact.get("id"))
            if not isinstance(configured, dict):
                artifact_result["ok"] = False
                violations.append(
                    {
                        "issue": "artifact_missing_from_paper_studio_config",
                        "id": artifact.get("id"),
                    }
                )
            else:
                shell = artifact.get("shell", {})
                expected_panels = list(shell.get("plotting", {}).get("panels", {}))
                if expected_panels:
                    actual_panels = [str(item.get("id", "")) for item in configured.get("panels", [])]
                    if actual_panels != expected_panels:
                        artifact_result["ok"] = False
                        violations.append(
                            {
                                "issue": "artifact_panel_dimension_mismatch",
                                "id": artifact.get("id"),
                                "expected": expected_panels,
                                "actual": actual_panels,
                            }
                        )
                expected_columns = shell.get("column_labels", [])
                if expected_columns:
                    actual_columns = configured_table_columns(configured)
                    if normalized_names(actual_columns) != normalized_names(expected_columns):
                        artifact_result["ok"] = False
                        violations.append(
                            {
                                "issue": "artifact_table_dimension_mismatch",
                                "id": artifact.get("id"),
                                "expected": expected_columns,
                                "actual": actual_columns,
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
    loaded_by_path = {path.resolve(): payload for path, payload in json_files}
    result_checks = []
    for requirement in contract.get("result_requirements", []):
        paths = requirement.get("any_of", [])
        matches = []
        rejected = []
        for selector in paths:
            file_name, dotted = parse_result_selector(selector)
            if file_name:
                target = resolve_result_file(args.results_dir, file_name)
                candidates = [] if target is None else [(target, loaded_by_path.get(target))]
            else:
                candidates = json_files
            for json_path, payload in candidates:
                if payload is None:
                    rejected.append({"file": str(json_path), "path": dotted, "errors": ["missing_or_invalid_file"]})
                    continue
                exists, values = get_path(payload, dotted)
                if not exists:
                    rejected.append({"file": str(json_path), "path": dotted, "errors": ["missing_path"]})
                    continue
                errors = validate_result_values(values, requirement)
                expected_hash = str(requirement.get("sha256", "")).strip().lower()
                if expected_hash and json_path.is_file():
                    actual_hash = hashlib.sha256(json_path.read_bytes()).hexdigest()
                    if actual_hash != expected_hash:
                        errors.append("sha256_mismatch")
                if errors:
                    rejected.append({"file": str(json_path), "path": dotted, "errors": errors})
                else:
                    matches.append({"file": str(json_path), "path": dotted})
        ok = bool(matches)
        result_checks.append(
            {
                "id": requirement.get("id"),
                "any_of": paths,
                "matches": matches,
                "rejected": rejected,
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
