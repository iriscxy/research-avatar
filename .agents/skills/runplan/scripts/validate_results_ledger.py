#!/usr/bin/env python3
"""Validate the canonical experiment result ledger and its provenance."""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import re
import sys
import tempfile
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path


COLUMNS = [
    "result_id", "goal_id", "artifact_id", "target_id", "acquisition_id", "source_type",
    "status", "metric", "value", "unit", "dimensions_json", "raw_artifact", "raw_locator",
    "source_reference", "source_locator",
    "command", "code_files", "config_files", "environment_files",
    "code_revision", "obtained_at", "verified_at", "verification_status", "notes",
]
STATUSES = {"REAL", "MISSING", "INVALIDATED"}
VERIFICATIONS = {"VERIFIED", "PENDING", "FAILED", "NOT_APPLICABLE"}
SOURCE_TYPES = {"RUN_LOCAL", "REUSE_REPORTED"}
STATE_RE = re.compile(
    r'<script type="application/json" id="run-plan-state">(.*?)</script>', re.S
)
PROVENANCE_RE = re.compile(
    r'<script\b(?=[^>]*\btype="application/json")'
    r'(?=[^>]*\bid="result-provenance")[^>]*>(.*?)</script>', re.S
)


def load_plan_state(path: Path | None) -> dict[str, object]:
    if path is None or not path.exists():
        return {}
    match = STATE_RE.search(path.read_text(encoding="utf-8"))
    if not match:
        raise ValueError("04_RUN_PLAN.html lacks embedded run-plan-state JSON")
    value = json.loads(match.group(1))
    if not isinstance(value, dict):
        raise ValueError("embedded run-plan-state must be an object")
    return value


def pointer_get(value: object, pointer: str) -> object:
    if pointer == "":
        return value
    if not pointer.startswith("/"):
        raise ValueError("JSON pointer must be empty or start with '/'")
    current = value
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            current = current[int(token)]
        elif isinstance(current, dict):
            current = current[token]
        else:
            raise ValueError(f"cannot descend through {type(current).__name__}")
    return current


def load_located(path: Path, locator: str) -> object:
    if path.suffix.lower() == ".json":
        return pointer_get(json.loads(path.read_text(encoding="utf-8")), locator)
    if path.suffix.lower() == ".jsonl":
        match = re.fullmatch(r"line:(\d+)#(.*)", locator)
        if not match:
            raise ValueError("JSONL locator must be line:<1-based>#<JSON-pointer>")
        line_number = int(match.group(1))
        lines = path.read_text(encoding="utf-8").splitlines()
        if line_number < 1 or line_number > len(lines):
            raise ValueError(f"JSONL line {line_number} is out of range")
        return pointer_get(json.loads(lines[line_number - 1]), match.group(2))
    raise ValueError("REAL raw_artifact must be .json or .jsonl")


def same_value(recorded: str, raw: object) -> bool:
    if isinstance(raw, bool) or raw is None:
        expected = "true" if raw is True else "false" if raw is False else "null"
        return recorded.strip().lower() == expected
    if isinstance(raw, (int, float)):
        try:
            return math.isclose(float(recorded), float(raw), rel_tol=1e-12, abs_tol=1e-12)
        except ValueError:
            return False
    if isinstance(raw, str):
        return recorded == raw
    return recorded == json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def raw_record(path: Path, locator: str) -> object:
    """Load the JSON object that owns a ledger value for formula verification."""
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if path.suffix.lower() == ".jsonl":
        match = re.fullmatch(r"line:(\d+)#.*", locator)
        if not match:
            raise ValueError("derived JSONL locator must identify one line")
        lines = path.read_text(encoding="utf-8").splitlines()
        return json.loads(lines[int(match.group(1)) - 1])
    raise ValueError("derived values require JSON or JSONL raw artifacts")


def recompute_derivation(record: object, spec: dict[str, object]) -> Decimal:
    """Recompute a structured derived value from persisted raw operands."""
    operation = str(spec.get("operation", ""))
    locators = spec.get("operand_locators")
    if operation not in {"subtract", "add", "mean", "ratio"}:
        raise ValueError(f"unsupported derivation operation: {operation}")
    if not isinstance(locators, list) or not locators:
        raise ValueError("derivation operand_locators must be a non-empty list")
    try:
        values = [Decimal(str(pointer_get(record, str(locator)))) for locator in locators]
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"derivation operand is not numeric: {exc}") from exc
    rounding = spec.get("rounding", {})
    if not isinstance(rounding, dict):
        raise ValueError("derivation rounding must be an object")
    stage = str(rounding.get("stage", "none"))
    decimals = rounding.get("decimals")
    quantum = Decimal(1).scaleb(-int(decimals)) if decimals is not None else None
    if stage == "operands_before_operation":
        if quantum is None:
            raise ValueError("operand rounding requires decimals")
        values = [value.quantize(quantum, rounding=ROUND_HALF_UP) for value in values]
    elif stage not in {"none", "result_after_operation"}:
        raise ValueError(f"unsupported derivation rounding stage: {stage}")
    if operation == "subtract":
        if len(values) != 2:
            raise ValueError("subtract requires exactly two operands")
        result = values[0] - values[1]
    elif operation == "add":
        result = sum(values, Decimal(0))
    elif operation == "mean":
        result = sum(values, Decimal(0)) / Decimal(len(values))
    else:
        if len(values) != 2 or values[1] == 0:
            raise ValueError("ratio requires two operands and a nonzero denominator")
        result = values[0] / values[1]
    if stage == "result_after_operation":
        if quantum is None:
            raise ValueError("result rounding requires decimals")
        result = result.quantize(quantum, rounding=ROUND_HALF_UP)
    return result


def listed_paths(value: str) -> list[Path]:
    return [Path(part.strip()) for part in value.split(";") if part.strip()]


def validate_figure_sources(report: str, acquisitions: dict[str, dict[str, object]]) -> list[str]:
    """Ensure each completed panel plot comes from its adjacent displayed table."""
    errors: list[str] = []
    expected: dict[str, dict[str, set[str]]] = {}
    for contract in acquisitions.values():
        if contract.get("figure_source_cell") is True:
            dimensions = contract.get("dimensions", {})
            panel_id = str(dimensions.get("panel", "")) if isinstance(dimensions, dict) else ""
            expected.setdefault(str(contract.get("artifact_id", "")), {}).setdefault(
                panel_id or "__artifact__", set()
            ).add(str(contract.get("target_id", "")))
    for artifact_id, panels in expected.items():
        match = re.search(
            rf'<section\b(?=[^>]*class="figure-result")(?=[^>]*data-artifact-id="{re.escape(artifact_id)}")[^>]*>(.*?)</section>',
            report,
            re.S,
        )
        if not match:
            errors.append(f"report lacks figure-result section for {artifact_id}")
            continue
        block = match.group(0)
        target_ids = set().union(*panels.values())
        declared = re.search(r'data-source-target-ids="([^"]*)"', block)
        declared_ids = set(declared.group(1).split()) if declared else set()
        displayed_ids = set(re.findall(r'<td\b[^>]*data-target-id="([^"]+)"[^>]*>', block))
        if declared_ids != target_ids or displayed_ids != target_ids:
            errors.append(f"{artifact_id}: figure source IDs do not exactly match acquisition contracts")
        panel_starts = list(re.finditer(
            r'<div\b[^>]*class="[^"]*\bresult-panel\b[^"]*"[^>]*>\s*<h4>(.*?)</h4>',
            block,
            re.S,
        ))
        panel_blocks = {
            " ".join(html.unescape(re.sub(r"<[^>]+>", " ", panel.group(1))).split()): block[
                panel.start():panel_starts[index + 1].start() if index + 1 < len(panel_starts) else len(block)
            ]
            for index, panel in enumerate(panel_starts)
        }
        for panel_id, panel_target_ids in panels.items():
            panel_block = block if panel_id == "__artifact__" else panel_blocks.get(panel_id, "")
            label = artifact_id if panel_id == "__artifact__" else f"{artifact_id}/{panel_id}"
            if not panel_block:
                errors.append(f"{label}: figure panel is missing")
                continue
            panel_displayed = set(re.findall(
                r'<td\b[^>]*data-target-id="([^"]+)"[^>]*>', panel_block
            ))
            if panel_displayed != panel_target_ids:
                errors.append(f"{label}: panel source IDs do not match acquisition contracts")
            filled = True
            for target_id in panel_target_ids:
                cell = re.search(
                    rf'(?P<open><td\b[^>]*data-target-id="{re.escape(target_id)}"[^>]*>)'
                    r'(?P<body>.*?)</td>',
                    panel_block,
                    re.S,
                )
                if not cell or 'data-result-id="' not in cell.group("open") or any(
                    status in cell.group("body")
                    for status in ("[PENDING]", "MISSING", "INVALIDATED")
                ):
                    filled = False
                    break
            plot = re.search(
                r'<(?:img|figure)\b[^>]*class="[^"]*result-plot[^"]*"[^>]*>',
                panel_block,
            )
            if not filled and plot:
                errors.append(f"{label}: result plot exists while its source table is not fully filled")
            if filled:
                if not plot:
                    errors.append(f"{label}: fully filled source table lacks generated result plot")
                else:
                    generated = re.search(r'data-generated-from-target-ids="([^"]*)"', plot.group(0))
                    generated_ids = set(generated.group(1).split()) if generated else set()
                    if generated_ids != panel_target_ids:
                        errors.append(f"{label}: generated plot source IDs differ from displayed table")
    return errors


def validate_clickable_provenance(
    report: str,
    rows: list[dict[str, str]],
    acquisitions: dict[str, dict[str, object]],
) -> list[str]:
    """Require each filled paper value to jump to exact generation evidence."""
    paper_rows = [
        row for row in rows
        if row.get("status") == "REAL" and row.get("artifact_id", "").strip()
    ]
    if not paper_rows:
        return []
    errors: list[str] = []
    if 'id="result-provenance-index"' not in report:
        errors.append("report lacks the result-provenance-index jump destination")
    payload_match = PROVENANCE_RE.search(report)
    if not payload_match:
        return errors + ["report lacks embedded result-provenance JSON"]
    if "<" in payload_match.group(1):
        errors.append("result-provenance JSON contains an unescaped '<' character")
    try:
        payload = json.loads(payload_match.group(1))
    except json.JSONDecodeError as exc:
        return errors + [f"result-provenance JSON is invalid: {exc}"]
    if not isinstance(payload, dict):
        return errors + ["result-provenance JSON must be an object keyed by result_id"]

    interaction_markers = {
        "scrollIntoView": "provenance interaction does not scroll to the selected record",
        "focus(": "provenance interaction does not focus the selected record",
        ".result-value:hover": "provenance interaction lacks a mouse-hover summary",
        ".result-value:focus-visible": "provenance interaction lacks a keyboard-focus summary",
        "provenance-": "provenance interaction does not resolve result jump targets",
        "createElement": "provenance interaction does not build jump-target cards",
        "textContent": "provenance cards are not rendered with safe textContent",
    }
    for marker, message in interaction_markers.items():
        if marker not in report:
            errors.append(message)
    if "hashchange" not in report and "pushState" not in report:
        errors.append("provenance interaction does not preserve page-hash navigation")

    common_fields = (
        "result_id", "goal_id", "metric", "value", "unit", "source_type",
        "obtained_at", "verified_at", "verification_status",
    )
    local_fields = (
        "raw_artifact", "raw_locator", "command", "code_files", "config_files",
        "environment_files", "code_revision",
    )
    reported_fields = ("source_reference", "source_locator")
    for row in paper_rows:
        rid = row["result_id"].strip()
        label = f"result {rid}"
        anchor = re.search(
            rf'<a\b(?=[^>]*\bdata-result-id="{re.escape(rid)}")'
            rf'(?=[^>]*\bdata-provenance-trigger="{re.escape(rid)}")'
            rf'(?=[^>]*\bhref="#provenance-{re.escape(rid)}")'
            rf'(?=[^>]*\bdata-provenance-summary="[^"]+")'
            rf'(?=[^>]*\btitle="[^"]+")[^>]*>',
            report,
        )
        if not anchor:
            errors.append(
                f"{label}: filled value lacks a clickable provenance jump and hover/focus summary"
            )
        record = payload.get(rid)
        if not isinstance(record, dict):
            errors.append(f"{label}: provenance payload entry is missing")
            continue
        for field in common_fields:
            if str(record.get(field, "")) != row.get(field, ""):
                errors.append(f"{label}: provenance field {field} differs from ledger")
        try:
            dimensions = json.loads(row.get("dimensions_json") or "{}")
        except json.JSONDecodeError:
            dimensions = None
        if record.get("dimensions") != dimensions:
            errors.append(f"{label}: provenance dimensions differ from ledger")
        acquisition = acquisitions.get(row.get("acquisition_id", ""), {})
        kind = acquisition.get("atomic_or_aggregate")
        if record.get("acquisition_kind") != kind:
            errors.append(f"{label}: provenance acquisition kind differs from contract")
        expected_calculation: object = (
            acquisition.get("derivation") if kind == "derived" else {"kind": "atomic"}
        )
        if record.get("calculation") != expected_calculation:
            errors.append(f"{label}: provenance calculation differs from contract")
        if row.get("source_type") == "RUN_LOCAL":
            for field in local_fields:
                if str(record.get(field, "")) != row.get(field, ""):
                    errors.append(f"{label}: provenance field {field} differs from ledger")
        elif row.get("source_type") == "REUSE_REPORTED":
            for field in reported_fields:
                if str(record.get(field, "")) != row.get(field, ""):
                    errors.append(f"{label}: provenance field {field} differs from ledger")
            if record.get("reuse_notice") != "not rerun locally":
                errors.append(f"{label}: reported reuse lacks the not-rerun notice")
        if anchor:
            summary_match = re.search(
                r'\bdata-provenance-summary="([^"]+)"', anchor.group(0)
            )
            title_match = re.search(r'\btitle="([^"]+)"', anchor.group(0))
            summary = html.unescape(summary_match.group(1)) if summary_match else ""
            title = html.unescape(title_match.group(1)) if title_match else ""
            if summary != title:
                errors.append(f"{label}: hover summary and native title differ")
            required_hover_values = [
                row.get("goal_id", ""), row.get("metric", ""), row.get("value", ""),
                row.get("verification_status", ""),
            ]
            if row.get("source_type") == "RUN_LOCAL":
                required_hover_values.extend([
                    row.get("raw_artifact", ""), row.get("raw_locator", ""),
                    row.get("command", ""),
                ])
            else:
                required_hover_values.extend([
                    row.get("source_reference", ""), row.get("source_locator", ""),
                    "not rerun locally",
                ])
            for value in required_hover_values:
                if value and value not in summary:
                    errors.append(f"{label}: hover summary lacks {value!r}")
    return errors


def validate_completed_goal_evidence(
    plan: str,
    state: dict[str, object],
    acquisitions: dict[str, dict[str, object]],
) -> list[str]:
    """Require one traceable snapshot per artifact under its earliest owning goal."""
    errors: list[str] = []
    goals = [goal for goal in state.get("goals", []) if isinstance(goal, dict)]
    completed = {
        str(goal.get("id", ""))
        for goal in goals if goal.get("status") == "completed"
    }
    artifact_owner: dict[str, str] = {}
    for goal in goals:
        for artifact_id in goal.get("artifact_ids", []):
            artifact_owner.setdefault(str(artifact_id), str(goal.get("id", "")))
    scoped: dict[str, list[dict[str, object]]] = {}
    for contract in acquisitions.values():
        producing_goal = str(contract.get("producing_goal", ""))
        artifact_id = str(contract.get("artifact_id", ""))
        if producing_goal in completed and artifact_id and contract.get("target_id"):
            scoped.setdefault(artifact_id, []).append(contract)
    for artifact_id, contracts in scoped.items():
        goal_id = artifact_owner.get(artifact_id, str(contracts[0].get("producing_goal", "")))
        if goal_id not in completed:
            errors.append(
                f"artifact {artifact_id} has completed producer data before its earliest owner {goal_id} completed"
            )
            continue
        card = re.search(
            rf'<article\b(?=[^>]*\bdata-goal-id="{re.escape(goal_id)}")[^>]*>.*?</article>',
            plan,
            re.S,
        )
        if not card or 'class="goal-results"' not in card.group(0):
            errors.append(f"artifact owner {goal_id} lacks the Completed Goal Evidence block for {artifact_id}")
            continue
        block = card.group(0)
        if plan.count(f'data-artifact-id="{artifact_id}"') != 1:
            errors.append(f"artifact {artifact_id} must appear exactly once under earliest owner {goal_id}")
        if ".result-value:hover" not in block or ".result-value:focus-visible" not in block:
            errors.append(f"artifact owner {goal_id} lacks hover/focus provenance styling")
        for contract in contracts:
            target_id = str(contract.get("target_id"))
            if f'data-artifact-id="{artifact_id}"' not in block:
                errors.append(f"artifact owner {goal_id} lacks artifact snapshot {artifact_id}")
                continue
            target = re.search(
                rf'<(?P<tag>[a-zA-Z0-9]+)\b(?=[^>]*\bdata-target-id="{re.escape(target_id)}")'
                rf'(?P<open>[^>]*)>(?P<body>.*?)</(?P=tag)>',
                block,
                re.S,
            )
            if not target:
                errors.append(f"artifact owner {goal_id} lacks target {target_id} in its snapshot")
                continue
            result = re.search(r'\bdata-result-id="([^"]+)"', target.group("open"))
            if not result or (
                f'href="/artifact/results#provenance-{result.group(1)}"'
                not in target.group("body")
            ):
                errors.append(
                    f"artifact owner {goal_id} target {target_id} lacks clickable provenance"
                )
            elif (
                f'data-local-result-href="05_EXP_RESULT.html#provenance-{result.group(1)}"'
                not in target.group("body")
            ):
                errors.append(
                    f"artifact owner {goal_id} target {target_id} lacks standalone-file provenance fallback"
                )
            elif (
                'data-provenance-summary="' not in target.group("body")
                or 'title="' not in target.group("body")
            ):
                errors.append(
                    f"artifact owner {goal_id} target {target_id} lacks hover provenance"
                )
    return errors


def validate_decision_handoff(experiment_contract: dict[str, object], state: dict[str, object]) -> list[str]:
    """Preserve approved choices and freeze searched values before final evaluation."""
    errors: list[str] = []
    approved = experiment_contract.get("decision_space_contract", [])
    if state.get("decision_space_contract") != approved:
        errors.append("run-plan decision-space contract differs from the approved expplan")
    goals = state.get("goals", [])
    covered = {decision_id for goal in goals for decision_id in goal.get("decision_ids", [])}
    expected = {item.get("id") for item in approved if item.get("id")}
    if covered != expected:
        errors.append("run-plan goals do not cover every approved decision ID")
    for decision in approved:
        if decision.get("disposition") != "SEARCHED":
            continue
        owners = [goal for goal in goals if decision.get("id") in goal.get("decision_ids", [])]
        if not owners or any(goal.get("stage") != "S3" for goal in owners):
            errors.append(f"{decision.get('id')}: SEARCHED decision must be owned by S3")
    split_by_experiment = {
        item.get("experiment_id"): item for item in state.get("execution_splits", [])
        if isinstance(item, dict) and item.get("experiment_id")
    }
    searched_experiments = {
        experiment_id for decision in approved if decision.get("disposition") == "SEARCHED"
        for experiment_id in decision.get("experiment_ids", [])
    }
    for experiment_id in searched_experiments:
        split = split_by_experiment.get(experiment_id, {})
        required = ("development_source", "final_source", "protocol_source")
        if any(not str(split.get(field, "")).strip() for field in required):
            errors.append(f"{experiment_id}: searched experiment lacks a sourced dev/final split")
        if split.get("disjoint") is not True or split.get("frozen_before_final") is not True:
            errors.append(f"{experiment_id}: dev/final split must be disjoint and frozen before final evaluation")
    final_started = any(
        goal.get("stage") in {"S4", "S5"} and goal.get("status") == "completed"
        for goal in goals
    )
    if final_started:
        frozen = state.get("frozen_configuration", {})
        for decision in approved:
            if decision.get("disposition") == "SEARCHED":
                record = frozen.get(decision.get("id"), {}) if isinstance(frozen, dict) else {}
                if not record.get("value") or not record.get("source_goal"):
                    errors.append(f"{decision.get('id')}: final evaluation lacks a frozen value/source")
    return errors


def validate(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    if not args.ledger.exists():
        return [f"ledger does not exist: {args.ledger}"]
    with args.ledger.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != COLUMNS:
            return [f"header mismatch: expected {COLUMNS}, got {reader.fieldnames}"]
        rows = list(reader)

    seen: set[str] = set()
    report_text = args.report.read_text(encoding="utf-8") if args.report and args.report.exists() else ""
    try:
        state = load_plan_state(args.plan)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"cannot load embedded run-plan state: {exc}"]
    source_plan_value = str(state.get("source_plan", "")).strip()
    source_plan = Path(source_plan_value)
    has_source_contract = bool(
        source_plan_value
        or state.get("source_plan_approval")
        or state.get("approved_artifact_ids")
        or state.get("artifact_coverage")
    )
    if args.plan and source_plan_value and not source_plan.is_absolute():
        project_root = (
            args.plan.parent.parent
            if args.plan.parent.name == "reports"
            else args.plan.parent
        )
        source_plan = project_root / source_plan
    if args.plan and has_source_contract and not source_plan.is_file():
        errors.append(f"source experiment plan does not exist: {source_plan}")
    elif source_plan.is_file() and args.plan:
        source_text = source_plan.read_text(encoding="utf-8")
        contract_match = re.search(
            r'<script type="application/json" id="experiment-plan-contract">(.*?)</script>',
            source_text,
            re.S,
        )
        if not contract_match:
            errors.append("source experiment plan lacks embedded contract")
        else:
            experiment_contract = json.loads(contract_match.group(1))
            source_approval = state.get("source_plan_approval", {})
            if not isinstance(source_approval, dict):
                errors.append("run-plan source_plan_approval must be an object")
                source_approval = {}
            if source_approval.get("status") != experiment_contract.get("approval_status"):
                errors.append("run-plan source approval status differs from the approved expplan")
            if source_approval.get("digest") != experiment_contract.get("approval_contract_sha256"):
                errors.append("run-plan source approval digest differs from the approved expplan")
            expected_version = experiment_contract.get(
                "approval_contract_version", experiment_contract.get("contract_version")
            )
            if source_approval.get("contract_version") != expected_version:
                errors.append("run-plan source contract version differs from the approved expplan")
            expected_artifacts = [item.get("id") for item in experiment_contract.get("paper_artifacts", [])]
            approved_artifacts = state.get("approved_artifact_ids", [])
            coverage = state.get("artifact_coverage", {})
            if approved_artifacts != expected_artifacts:
                errors.append("run-plan approved_artifact_ids do not preserve the approved 03 artifact order")
            if set(coverage) != set(expected_artifacts):
                errors.append("run-plan artifact coverage does not exactly cover every approved figure/table")
            goal_ids = {str(item.get("id", "")) for item in state.get("goals", [])}
            for artifact_id in expected_artifacts:
                owners = coverage.get(artifact_id, {}).get("goals", []) if isinstance(coverage, dict) else []
                if not owners or any(owner not in goal_ids for owner in owners):
                    errors.append(f"{artifact_id}: artifact coverage requires at least one valid owning goal")
            visible_goal_artifacts: dict[str, set[str]] = {}
            for artifact_attr, goal_id in re.findall(
                r'<article\b[^>]*data-artifact-ids="([^"]*)"[^>]*>\s*<h3>.*?\b(G\d+\.\d+)\s+—',
                args.plan.read_text(encoding="utf-8"),
                re.S,
            ):
                visible_goal_artifacts[goal_id] = set(artifact_attr.split())
            for item in state.get("goals", []):
                goal_id = str(item.get("id", ""))
                if visible_goal_artifacts.get(goal_id) != set(item.get("artifact_ids", [])):
                    errors.append(f"{goal_id}: visible corresponding-artifact mapping disagrees with embedded state")
            coverage_label = f"图表覆盖：{len(expected_artifacts)}/{len(expected_artifacts)}"
            if coverage_label not in args.plan.read_text(encoding="utf-8"):
                errors.append("visible run plan lacks the complete figure/table coverage count")
            approved_implementation = experiment_contract.get("implementation_contract", [])
            if state.get("implementation_contract") != approved_implementation:
                errors.append("run-plan implementation contract differs from the approved expplan")
            errors.extend(validate_decision_handoff(experiment_contract, state))
            runplan_text = args.plan.read_text(encoding="utf-8")
            runplan_visible = re.sub(r'<script\b.*?</script>', '', runplan_text, flags=re.S)
            for item in approved_implementation:
                for field in ("method", "implementation_summary"):
                    token = item.get(field)
                    if token and html.unescape(str(token)) not in html.unescape(re.sub(r'<[^>]+>', ' ', runplan_visible)):
                        errors.append(f"visible run plan lacks approved implementation detail: {token}")
                url = item.get("source_url")
                if url and f'href="{url}"' not in runplan_visible:
                    errors.append(f"visible run plan lacks approved implementation source: {item.get('method')}")
    state_paths = set(state.get("result_paths", []))
    acquisition_contracts = state.get("acquisition_contracts", [])
    if not isinstance(acquisition_contracts, list):
        errors.append("embedded run-plan-state acquisition_contracts must be a list")
        acquisition_contracts = []
    acquisitions: dict[str, dict[str, object]] = {}
    acquisition_targets: set[tuple[str, str]] = set()
    for index, contract in enumerate(acquisition_contracts):
        if not isinstance(contract, dict):
            errors.append(f"embedded acquisition_contracts[{index}] must be an object")
            continue
        acquisition_id = str(contract.get("id", "")).strip()
        if not acquisition_id:
            errors.append(f"embedded acquisition_contracts[{index}] requires id")
            continue
        if acquisition_id in acquisitions:
            errors.append(f"embedded state has duplicate acquisition contract id: {acquisition_id}")
            continue
        acquisitions[acquisition_id] = contract
        artifact_id = str(contract.get("artifact_id", "")).strip()
        target_id = str(contract.get("target_id", "")).strip()
        if bool(artifact_id) != bool(target_id):
            errors.append(
                f"embedded acquisition contract {acquisition_id}: artifact_id and target_id must be paired"
            )
        if artifact_id and target_id:
            target = (artifact_id, target_id)
            if target in acquisition_targets:
                errors.append(
                    f"embedded state has duplicate acquisition target: {artifact_id}/{target_id}"
                )
            acquisition_targets.add(target)
        if str(contract.get("source_type", "")).strip() not in SOURCE_TYPES:
            errors.append(
                f"embedded acquisition contract {acquisition_id}: invalid source_type"
            )
        if not str(contract.get("producing_goal", "")).strip():
            errors.append(
                f"embedded acquisition contract {acquisition_id}: producing_goal is required"
            )
        value_kind = contract.get("atomic_or_aggregate")
        if value_kind not in {"atomic", "derived"}:
            errors.append(
                f"embedded acquisition contract {acquisition_id}: atomic_or_aggregate must be atomic or derived"
            )
        if value_kind == "derived" and not isinstance(contract.get("derivation"), dict):
            errors.append(
                f"embedded acquisition contract {acquisition_id}: derived values require a structured derivation"
            )
        if value_kind == "atomic" and isinstance(contract.get("derivation"), dict):
            errors.append(
                f"embedded acquisition contract {acquisition_id}: an acquisition with a derivation cannot be atomic"
            )

    if args.goal and not any(row["goal_id"] == args.goal for row in rows):
        errors.append(f"no ledger row exists for requested goal {args.goal}")

    for number, row in enumerate(rows, start=2):
        label = f"row {number} ({row.get('result_id') or 'missing-id'})"
        rid = row["result_id"].strip()
        if not rid:
            errors.append(f"{label}: result_id is required")
        elif rid in seen:
            errors.append(f"{label}: duplicate result_id")
        seen.add(rid)
        if row["status"] not in STATUSES:
            errors.append(f"{label}: invalid status {row['status']!r}")
        if row["verification_status"] not in VERIFICATIONS:
            errors.append(f"{label}: invalid verification_status {row['verification_status']!r}")
        for column in ("goal_id", "acquisition_id", "metric"):
            if not row[column].strip():
                errors.append(f"{label}: {column} is required")
        if row["source_type"] not in SOURCE_TYPES:
            errors.append(f"{label}: invalid source_type {row['source_type']!r}")
        if bool(row["artifact_id"].strip()) != bool(row["target_id"].strip()):
            errors.append(f"{label}: artifact_id and target_id must be both set or both empty")
        acquisition = None
        if args.plan:
            acquisition = acquisitions.get(row["acquisition_id"].strip())
            if acquisition is None:
                errors.append(f"{label}: acquisition_id does not resolve in embedded run-plan state")
            else:
                expected = {
                    "artifact_id": row["artifact_id"].strip(),
                    "target_id": row["target_id"].strip(),
                    "source_type": row["source_type"].strip(),
                    "producing_goal": row["goal_id"].strip(),
                }
                for field, actual in expected.items():
                    if str(acquisition.get(field, "")).strip() != actual:
                        errors.append(
                            f"{label}: acquisition contract {field} does not match ledger row"
                        )
        try:
            dims = json.loads(row["dimensions_json"] or "{}")
            if not isinstance(dims, dict):
                raise ValueError("must be an object")
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(f"{label}: invalid dimensions_json: {exc}")

        if row["status"] != "REAL":
            if not row["notes"].strip():
                errors.append(f"{label}: non-REAL row requires an explanation in notes")
            continue

        required = ["value", "obtained_at", "verified_at"]
        for column in required:
            if not row[column].strip():
                errors.append(f"{label}: REAL row requires {column}")
        if row["verification_status"] != "VERIFIED":
            errors.append(f"{label}: REAL row must have verification_status=VERIFIED")

        if row["source_type"] == "RUN_LOCAL":
            for column in ("raw_artifact", "command", "code_files", "code_revision"):
                if not row[column].strip():
                    errors.append(f"{label}: RUN_LOCAL REAL row requires {column}")
            raw_path = Path(row["raw_artifact"])
            if not raw_path.is_file():
                errors.append(f"{label}: raw artifact missing: {raw_path}")
            else:
                try:
                    raw_value = load_located(raw_path, row["raw_locator"])
                    if not same_value(row["value"], raw_value):
                        errors.append(f"{label}: recorded value does not match raw locator value {raw_value!r}")
                    derivation = acquisition.get("derivation") if acquisition else None
                    if isinstance(derivation, dict):
                        recomputed = recompute_derivation(
                            raw_record(raw_path, row["raw_locator"]), derivation
                        )
                        if Decimal(str(raw_value)) != recomputed:
                            errors.append(
                                f"{label}: raw derived value {raw_value!r} does not equal formula result {recomputed}"
                            )
                except (OSError, ValueError, KeyError, IndexError, json.JSONDecodeError) as exc:
                    errors.append(f"{label}: cannot resolve raw locator: {exc}")

            for column in ("code_files", "config_files", "environment_files"):
                for path in listed_paths(row[column]):
                    if not path.is_file():
                        errors.append(f"{label}: {column} path missing: {path}")
        elif row["source_type"] == "REUSE_REPORTED":
            for column in ("source_reference", "source_locator"):
                if not row[column].strip():
                    errors.append(f"{label}: REUSE_REPORTED REAL row requires {column}")
            if row["raw_artifact"].strip() or row["raw_locator"].strip() or row["command"].strip():
                errors.append(
                    f"{label}: REUSE_REPORTED row must not imply a local raw artifact or command"
                )
        if args.strict_report and rid and f'data-result-id="{rid}"' not in report_text:
            errors.append(f"{label}: result_id is absent from HTML report")

    ledger_raw_paths = {
        row["raw_artifact"] for row in rows
        if row["status"] == "REAL" and row["source_type"] == "RUN_LOCAL"
    }
    for path in state_paths:
        if path not in ledger_raw_paths and not any(prefix.startswith(path.rstrip("/") + "/") for prefix in ledger_raw_paths):
            errors.append(f"embedded result_paths entry is absent from REAL ledger rows: {path}")
    if args.goal and acquisitions:
        assigned = {
            acquisition_id for acquisition_id, contract in acquisitions.items()
            if str(contract.get("producing_goal", "")).strip() == args.goal
        }
        recorded = {
            row["acquisition_id"].strip() for row in rows if row["goal_id"] == args.goal
        }
        for acquisition_id in sorted(assigned - recorded):
            errors.append(
                f"goal {args.goal} has no ledger row for acquisition contract {acquisition_id}"
            )
    if args.strict_report and report_text:
        errors.extend(validate_figure_sources(report_text, acquisitions))
        errors.extend(validate_clickable_provenance(report_text, rows, acquisitions))
    if args.plan:
        errors.extend(
            validate_completed_goal_evidence(
                args.plan.read_text(encoding="utf-8"), state, acquisitions
            )
        )
    return errors


def self_test() -> int:
    rounded_gap = recompute_derivation(
        {"targeted_shift": 0.12345, "control_shift": 0.12344},
        {
            "operation": "subtract",
            "operand_locators": ["/targeted_shift", "/control_shift"],
            "rounding": {"stage": "operands_before_operation", "decimals": 4},
        },
    )
    if rounded_gap != Decimal("0.0001"):
        return 1
    figure_acquisitions = {
        "A1": {"artifact_id": "F2", "target_id": "F2.a.p1.x", "figure_source_cell": True},
        "A2": {"artifact_id": "F2", "target_id": "F2.a.p1.y", "figure_source_cell": True},
    }
    pending_report = ('<section class="figure-result" data-artifact-id="F2" '
                      'data-source-target-ids="F2.a.p1.x F2.a.p1.y">'
                      '<table><tr><td data-target-id="F2.a.p1.x">[PENDING]</td>'
                      '<td data-target-id="F2.a.p1.y">[PENDING]</td></tr></table></section>')
    if validate_figure_sources(pending_report, figure_acquisitions):
        return 1
    if not any("not fully filled" in error for error in validate_figure_sources(
        pending_report.replace("</section>", '<img class="result-plot"></section>'), figure_acquisitions
    )):
        return 1
    filled_report = ('<section class="figure-result" data-artifact-id="F2" '
                     'data-source-target-ids="F2.a.p1.x F2.a.p1.y">'
                     '<table><tr><td data-target-id="F2.a.p1.x" data-result-id="R1">1</td>'
                     '<td data-target-id="F2.a.p1.y" data-result-id="R2">2</td></tr></table>'
                     '<img class="result-plot" data-generated-from-target-ids="F2.a.p1.x F2.a.p1.y">'
                     '</section>')
    if validate_figure_sources(filled_report, figure_acquisitions):
        return 1
    split_panel_acquisitions = {
        "A1": {"artifact_id": "F2", "target_id": "F2.a.x", "figure_source_cell": True,
               "dimensions": {"panel": "panel-a"}},
        "A2": {"artifact_id": "F2", "target_id": "F2.b.x", "figure_source_cell": True,
               "dimensions": {"panel": "panel-b"}},
    }
    split_panel_report = (
        '<section class="figure-result" data-artifact-id="F2" '
        'data-source-target-ids="F2.a.x F2.b.x">'
        '<div class="result-panel"><h4>panel-a</h4><table><tr>'
        '<td data-target-id="F2.a.x" data-result-id="R1">1</td></tr></table>'
        '<img class="result-plot" data-generated-from-target-ids="F2.a.x"></div>'
        '<div class="result-panel"><h4>panel-b</h4><table><tr>'
        '<td data-target-id="F2.b.x">[PENDING]</td></tr></table></div></section>'
    )
    if validate_figure_sources(split_panel_report, split_panel_acquisitions):
        return 1
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        raw = root / "metrics.json"
        code = root / "run.py"
        raw.write_text('{"score": 0.75}\n', encoding="utf-8")
        code.write_text("# fixture\n", encoding="utf-8")
        ledger = root / "ledger.csv"
        row = {column: "" for column in COLUMNS}
        row.update({
            "result_id": "R-G00-001", "goal_id": "G00", "artifact_id": "T1",
            "target_id": "score.fixture", "acquisition_id": "A-T1-score-fixture",
            "source_type": "RUN_LOCAL", "status": "REAL",
            "metric": "score", "value": "0.75",
            "dimensions_json": "{}", "raw_artifact": str(raw),
            "raw_locator": "/score",
            "command": "python run.py", "code_files": str(code),
            "code_revision": "fixture", "obtained_at": "2026-01-01T00:00:00Z",
            "verified_at": "2026-01-01T00:01:00Z", "verification_status": "VERIFIED",
        })
        def write_row() -> None:
            with ledger.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=COLUMNS)
                writer.writeheader()
                writer.writerow(row)

        write_row()
        plan_path = root / "04_RUN_PLAN.html"
        state_json = json.dumps({
            "acquisition_contracts": [{
                "id": "A-T1-score-fixture", "artifact_id": "T1",
                "target_id": "score.fixture", "source_type": "RUN_LOCAL",
                "producing_goal": "G00", "atomic_or_aggregate": "atomic",
            }],
        })
        plan_path.write_text(
            f'<script type="application/json" id="run-plan-state">{state_json}</script>',
            encoding="utf-8",
        )
        args = argparse.Namespace(
            ledger=ledger, plan=plan_path, report=None, goal="G00", strict_report=False
        )
        if validate(args):
            return 1
        provenance_payload = {
            row["result_id"]: {
                "result_id": row["result_id"], "goal_id": row["goal_id"],
                "metric": row["metric"], "value": row["value"], "unit": row["unit"],
                "dimensions": {}, "source_type": row["source_type"],
                "acquisition_kind": "atomic", "calculation": {"kind": "atomic"},
                "obtained_at": row["obtained_at"], "verified_at": row["verified_at"],
                "verification_status": row["verification_status"],
                "raw_artifact": row["raw_artifact"], "raw_locator": row["raw_locator"],
                "command": row["command"], "code_files": row["code_files"],
                "config_files": row["config_files"],
                "environment_files": row["environment_files"],
                "code_revision": row["code_revision"],
            }
        }
        hover_summary = html.escape(
            "\n".join([
                f"Goal: {row['goal_id']}",
                f"Metric: {row['metric']} = {row['value']}",
                f"Raw: {row['raw_artifact']} · {row['raw_locator']}",
                f"Command: {row['command']}",
                f"Verified: {row['verification_status']}",
            ]),
            quote=True,
        )
        report_path = root / "05_EXP_RESULT.html"
        report_path.write_text(
            '<table><tr><td data-target-id="score.fixture">'
            '<a href="#provenance-R-G00-001" data-result-id="R-G00-001" '
            'data-provenance-trigger="R-G00-001" '
            f'data-provenance-summary="{hover_summary}" title="{hover_summary}">'
            '0.75</a></td></tr></table>'
            '<section id="result-provenance-index"></section>'
            '<script type="application/json" id="result-provenance">'
            + json.dumps(provenance_payload).replace("<", "\\u003c")
            + '</script><script>const card=document.createElement("details");'
            'card.id="provenance-R-G00-001";card.textContent="generation evidence";'
            'document.getElementById("result-provenance-index").appendChild(card);'
            'addEventListener("hashchange",()=>{const target='
            'document.getElementById("provenance-"+location.hash.slice(12));'
            'target.open=true;target.focus();target.scrollIntoView();});</script>'
            '<style>.result-value:hover::after{display:block}'
            '.result-value:focus-visible::after{display:block}</style>',
            encoding="utf-8",
        )
        args.report = report_path
        args.strict_report = True
        if validate(args):
            return 1
        report_path.write_text(
            report_path.read_text(encoding="utf-8").replace(
                'href="#provenance-R-G00-001"', 'href="#broken"'
            ),
            encoding="utf-8",
        )
        if not any("clickable provenance jump" in error for error in validate(args)):
            return 1
        args.report = None
        args.strict_report = False
        row["artifact_id"] = row["target_id"] = ""
        write_row()
        args.plan = None
        if validate(args):
            return 1
        row["artifact_id"] = "T1"
        write_row()
        if not any("must be both set or both empty" in error for error in validate(args)):
            return 1
        row["target_id"] = "score.fixture"
        row["value"] = "0.74"
        write_row()
        if not any("does not match" in error for error in validate(args)):
            return 1

        row.update({
            "value": "0.75", "source_type": "REUSE_REPORTED",
            "raw_artifact": "", "raw_locator": "", "command": "", "code_files": "",
            "code_revision": "", "source_reference": "Doe et al. (2025), DOI:10.example/x",
            "source_locator": "Table 2, row Method A, column Score",
        })
        write_row()
        if validate(args):
            return 1
        row["source_locator"] = ""
        write_row()
        return 0 if any("requires source_locator" in error for error in validate(args)) else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, default=Path("code/RESULTS_LEDGER.csv"))
    parser.add_argument("--plan", type=Path, default=Path("reports/04_RUN_PLAN.html"))
    parser.add_argument("--report", type=Path)
    parser.add_argument("--goal")
    parser.add_argument("--strict-report", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        result = self_test()
        print("PASS" if result == 0 else "FAIL")
        return result
    errors = validate(args)
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
