#!/usr/bin/env python3
"""Validate projected tables and reusable Python plots in EXPERIMENT_PLAN.html."""

from __future__ import annotations

import argparse
import html as html_module
import json
import re
import sys
from pathlib import Path


CONTRACT_RE = re.compile(
    r'<script type="application/json" id="experiment-plan-contract">(.*?)</script>', re.S
)
PENDING_TD_RE = re.compile(
    r'<td\b[^>]*class\s*=\s*["\'][^"\']*\bpending\b[^"\']*["\'][^>]*>\s*\[PENDING\]\s*</td>',
    re.I,
)


def visible_html(source: str) -> str:
    return CONTRACT_RE.sub("", source)


def visible_text(source: str) -> str:
    source = visible_html(source)
    source = re.sub(r"<style\b.*?</style>|<script\b.*?</script>", " ", source, flags=re.S | re.I)
    source = re.sub(r"<[^>]+>", " ", source)
    return re.sub(r"\s+", " ", html_module.unescape(source))


def target_ids(contract: dict) -> list[str]:
    targets: list[str] = []
    for requirement in contract.get("result_requirements", []):
        targets.extend(requirement.get("cell_ids", []))
        targets.extend(requirement.get("panel_ids", []))
    return targets


def scalar_strings(value: object) -> list[str]:
    if isinstance(value, dict):
        return [item for child in value.values() for item in scalar_strings(child)]
    if isinstance(value, list):
        return [item for child in value for item in scalar_strings(child)]
    return [str(value)]


def visible_shell(source: str, artifact_id: str) -> str | None:
    """Extract one top-level shell without traversing embedded base64 previews."""
    title = f'<div class="shell-title">{artifact_id} ·'
    title_pos = source.find(title)
    if title_pos < 0:
        return None
    start = source.rfind('<div class="shell', 0, title_pos)
    if start < 0:
        return None
    boundary = re.search(r'(?:<div class="shell|<h[234]>|<script)', source[title_pos + len(title):])
    end = title_pos + len(title) + boundary.start() if boundary else len(source)
    return source[start:end]


def validate(plan: Path) -> list[str]:
    errors: list[str] = []
    source = plan.read_text(encoding="utf-8")
    match = CONTRACT_RE.search(source)
    if not match:
        return ["missing experiment-plan-contract"]
    try:
        contract = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        return [f"invalid experiment-plan-contract JSON: {exc}"]
    if contract.get("approval_status") not in {"pending", "approved"}:
        errors.append("approval_status must be pending or approved")
    target = contract.get("target", {})
    deadline_status = target.get("deadline_status")
    if deadline_status not in {"open", "upcoming", "passed", "call_pending"}:
        errors.append("target.deadline_status must be open, upcoming, passed, or call_pending")
    if deadline_status == "passed":
        override = target.get("deadline_override")
        if not isinstance(override, dict) or override.get("confirmed") is not True:
            errors.append("a passed venue cycle requires an explicitly confirmed target.deadline_override")
        elif not all(str(override.get(key, "")).strip() for key in ("confirmed_at", "reason", "intended_use")):
            errors.append("target.deadline_override requires confirmed_at, reason, and intended_use")
    if contract.get("dataset_confirmation", {}).get("confirmed") is not True:
        errors.append("dataset slate was not explicitly confirmed before HTML generation")
    for index, metric in enumerate(contract.get("metric_contract", [])):
        required_metric_fields = (
            "name", "provenance", "definition", "range", "decision_rule", "aggregation", "url"
        )
        missing = [field for field in required_metric_fields if not str(metric.get(field, "")).strip()]
        if missing:
            errors.append(f"metric_contract[{index}] missing operational fields: {', '.join(missing)}")
    if set(contract.get("dataset_confirmation", {})) != {"confirmed", "confirmed_at"}:
        errors.append("dataset_confirmation must contain only confirmed and confirmed_at")
    grounding = contract.get("grounding", {})
    for forbidden in ("datasets", "metrics", "split"):
        if forbidden in grounding:
            errors.append(f"grounding.{forbidden} is forbidden; tables own dataset/metric and expplan does not own split")

    artifacts = contract.get("paper_artifacts", [])
    result_artifacts = {
        item.get("artifact_id") for item in contract.get("result_requirements", [])
    }
    page = visible_html(source)
    text = visible_text(source)
    opening = re.search(
        r"<h2>1\. Target Conference and Reference Papers</h2>\s*<div class=['\"]hero['\"]>(.*?)</div>\s*<h2>2\. Projected Paper</h2>",
        page,
        re.S,
    )
    if not opening:
        errors.append("Section 1 must be Target Conference and Reference Papers and directly precede Section 2")
    else:
        opening_html = opening.group(1)
        opening_text = visible_text(opening_html)
        if len(re.findall(r"<p\b", opening_html)) != 3:
            errors.append("Section 1 must contain exactly three entries")
        for required in (
            "Target conference:",
            "External mechanism reference:",
            "Researcher-owned structure reference:",
        ):
            if required not in opening_text:
                errors.append(f"Section 1 lacks required entry: {required}")
        for forbidden in (
            "Research question:",
            "Confirmed architecture:",
            "Dataset:",
            "Metrics:",
            "Baselines:",
        ):
            if forbidden in opening_text:
                errors.append(f"Section 1 contains forbidden extra entry: {forbidden}")
        references = contract.get("references", {})
        for role in ("external_mechanism", "researcher_owned_structure"):
            url = references.get(role, {}).get("url")
            if not url or f'href="{url}"' not in opening_html:
                errors.append(f"Section 1 lacks direct link for {role}")
    if "Confirmed references" in text:
        errors.append("confirmed references must not be duplicated after Section 1")
    for token in ("RR-", "PENDING:", "fig:", "tab:"):
        if token in text:
            errors.append(f"visible internal/result identifier leaked: {token}")

    for artifact in artifacts:
        aid = artifact.get("id", "")
        kind = artifact.get("kind")
        if aid not in result_artifacts:
            continue
        if kind == "table":
            block = visible_shell(page, aid)
            if not block or 'class="shell result-table-shell"' not in block:
                errors.append(f"{aid}: missing paper-style result placeholder table")
                continue
            block_text = visible_text(block)
            if "RESULT PLACEHOLDER — NO NUMBERS FABRICATED" not in block_text:
                errors.append(f"{aid}: missing no-fabricated-table-values warning")
            if "Dataset" not in block_text and "Datasets" not in block_text:
                errors.append(f"{aid}: dataset is not determined in the visible main table/note")
            if "<a href=" not in block:
                errors.append(f"{aid}: dataset citation is missing from the visible table/note")
            cells = re.findall(r'<td class="pending" data-target-id="[^"]+">(.*?)</td>', block, re.S)
            if not cells or any(visible_text(cell).strip() != "[PENDING]" for cell in cells):
                errors.append(f"{aid}: result cells must remain [PENDING], without fabricated numbers")
            shell = artifact.get("shell", {})
            if not shell.get("column_labels") or not shell.get("metric_uncertainty"):
                errors.append(f"{aid}: hidden table shell lacks metric-bearing columns/uncertainty")
            if "ablation" in str(artifact.get("label", "")).lower():
                for token in (
                    "Style Jailbreak (full)", "Literary style", "Style-graph search",
                    "Two-turn continuation", "AdvBench", "TrustLLM Safety",
                ):
                    if token not in block_text:
                        errors.append(f"{aid}: ablation matrix lacks {token}")
                if "Full-benchmark confirmation" in block_text:
                    errors.append(f"{aid}: ablation artifact still contains duplicate full-benchmark confirmation")
        elif kind == "figure":
            if artifact.get("shell", {}).get("data_driven") is False:
                continue
            block = visible_shell(page, aid)
            if not block or 'class="shell projected-figure"' not in block:
                errors.append(f"{aid}: missing Python-generated projected figure")
                continue
            if 'class="required-data figure-source-data"' not in block:
                errors.append(f"{aid}: missing adjacent real-data source table")
            if "Dataset / benchmark" not in block or "Metric / axes" not in block:
                errors.append(f"{aid}: figure source table lacks dataset or metric")
            if "Required fields" not in block:
                errors.append(f"{aid}: figure source table does not specify the required data schema")
            if "<a href=" not in block:
                errors.append(f"{aid}: dataset citation is missing from figure source table")
            expected_panels = len(artifact.get("shell", {}).get("required_data", []))
            panel_pairs = re.findall(r'<section\b[^>]*class="panel-pair"[^>]*>(.*?)</section>', block, re.S)
            if len(panel_pairs) != expected_panels:
                errors.append(f"{aid}: expected {expected_panels} one-table/one-preview panel pairs, found {len(panel_pairs)}")
            for index, pair in enumerate(panel_pairs, 1):
                if pair.count('class="required-data figure-source-data"') != 1 or pair.count("data:image/png;base64,") != 1:
                    errors.append(f"{aid} panel {index}: must contain exactly one source table and one preview")
                pending = PENDING_TD_RE.findall(pair)
                if not pending:
                    errors.append(f"{aid} panel {index}: observed values must be visibly [PENDING]")
                if any(re.search(r"\bcolspan\s*=", cell, re.I) for cell in pending):
                    errors.append(f"{aid} panel {index}: colspan/summary pending cell has no one-to-one plotted scalar")
            plotting = artifact.get("shell", {}).get("plotting", {})
            for field in ("source", "schema", "fixture_generator", "fixture", "pdf", "png"):
                value = plotting.get(field)
                path = plan.parents[1] / value if value else None
                if not value or not path.exists() or path.stat().st_size == 0:
                    errors.append(f"{aid}: missing plotting {field}: {value}")
            for slug, outputs in plotting.get("panels", {}).items():
                for field in ("pdf", "png"):
                    value = outputs.get(field)
                    path = plan.parents[1] / value if value else None
                    if not value or not path.exists() or path.stat().st_size == 0:
                        errors.append(f"{aid}/{slug}: missing panel {field}: {value}")
            source_path = plan.parents[1] / plotting.get("source", "")
            if source_path.exists():
                plot_source = source_path.read_text(encoding="utf-8")
                common_path = source_path.with_name("_common.py")
                if common_path.exists():
                    plot_source += common_path.read_text(encoding="utf-8")
                for interface in ("--schema", "--figure", "--panel", "--metrics", "--pdf", "--png", "matplotlib.use(\"Agg\")", "validate_rendered_marks"):
                    if interface not in plot_source:
                        errors.append(f"{aid}: plotting source lacks {interface}")
            fixture_path = plan.parents[1] / plotting.get("fixture", "")
            schema_path = plan.parents[1] / plotting.get("schema", "")
            if fixture_path.exists() and schema_path.exists():
                fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                if fixture.get("synthetic") is not True:
                    errors.append(f"{aid}: projected fixture must set synthetic=true")
                if fixture.get("source_schema") != plotting.get("schema"):
                    errors.append(f"{aid}: synthetic fixture must declare the table schema as its source")
                if "projected_tables" in fixture:
                    errors.append("projected fixture must not fabricate main result-table values")
                keys = [item.get("fixture_key") for item in artifact.get("shell", {}).get("required_data", [])]
                for key in keys:
                    if fixture.get("traceable_results", {}).get(key) is None:
                        errors.append(f"{aid}: missing fixture key {key}")
                schema_panels = schema.get("figures", {}).get(aid, [])
                if len(schema_panels) != len(panel_pairs):
                    errors.append(f"{aid}: table schema panel count does not match HTML")
                for index, (pair, panel_schema) in enumerate(zip(panel_pairs, schema_panels), 1):
                    expected_marks = panel_schema.get("plotted_marks")
                    expected_pending = panel_schema.get("pending_values", expected_marks)
                    actual_pending = len(PENDING_TD_RE.findall(pair))
                    if actual_pending != expected_pending:
                        errors.append(
                            f"{aid} panel {index}: table has {actual_pending} pending values; schema requires {expected_pending} "
                            f"for {expected_marks} plotted marks"
                        )
                    kind = panel_schema.get("table_kind")
                    if kind in {"fixed_x_points", "scatter_points", "case_record"}:
                        expected_rows = len(panel_schema.get("x_values", [])) if kind == "fixed_x_points" else len(panel_schema.get("rows", []))
                        if expected_rows != expected_marks:
                            errors.append(f"{aid} panel {index}: frozen table defines {expected_rows} rows but schema declares {expected_marks} marks")
                        actual_rows = len(re.findall(r'class="plot-point"', pair))
                        if actual_rows != expected_rows:
                            errors.append(f"{aid} panel {index}: expected {expected_rows} point rows, found {actual_rows}")
                    for label in panel_schema.get("categories", []):
                        if f"<th>{html_module.escape(str(label))}</th>" not in pair:
                            errors.append(f"{aid} panel {index}: fixed category header is missing: {label}")

    for css_token in (".panel-pair>*{min-width:0}", ".projected-preview img{", "max-width:100%", "height:auto"):
        if css_token not in page:
            errors.append(f"responsive figure layout missing CSS token: {css_token}")

    f1 = next((item for item in artifacts if item.get("id") == "F1"), None)
    if not f1:
        errors.append("F1: missing count-only introduction motivation figure contract")
    elif not str(f1.get("introduced_after", "")).startswith("I-P") or f1.get("shell", {}).get("rhetorical_role") != "motivation":
        errors.append("F1 must attach to an Introduction paragraph and declare motivation role")

    for artifact in artifacts:
        if artifact.get("kind") != "figure" or artifact.get("shell", {}).get("data_driven") is not False:
            continue
        aid = artifact.get("id", "")
        if visible_shell(page, aid):
            errors.append(f"{aid}: non-experimental figure must be count-only, not rendered during expplan")
        if aid in result_artifacts:
            errors.append(f"{aid}: non-experimental figure must not have a result/acquisition requirement")

    target = contract.get("target", {})
    if not target.get("venue") or not isinstance(target.get("submission_content_pages"), int):
        errors.append("target venue and integer submission_content_pages are required")
    structure_ref = contract.get("references", {}).get("researcher_owned_structure", {})
    if not structure_ref.get("url") or not structure_ref.get("local_full_text"):
        errors.append("researcher-owned structure reference must have a URL and local full text")

    body_figures = sum(item.get("kind") == "figure" for item in artifacts)
    body_tables = sum(item.get("kind") == "table" for item in artifacts)
    float_budget = contract.get("float_budget", {})
    expected_counts = (float_budget.get("body_figures"), float_budget.get("body_tables"))
    actual_counts = (body_figures, body_tables)
    if expected_counts != actual_counts:
        errors.append(f"artifact contract and float budget disagree: expected={expected_counts}, actual={actual_counts}")
    budget = re.search(
        r'<h2>2\. Projected Paper</h2>\s*<p class="float-budget">(.*?)</p>',
        page,
        re.S,
    )
    if not budget:
        errors.append("the plan/reference whole-paper float budget must sit directly below the Projected Paper heading")
    else:
        budget_text = visible_text(budget.group(1))
        reference_figures = float_budget.get("reference_body_figures")
        reference_tables = float_budget.get("reference_body_tables")
        for token in (
            f"本计划 {body_figures + body_tables}（{body_figures} 图，{body_tables} 表）",
            f"参考论文 {reference_figures + reference_tables}（{reference_figures} 图，{reference_tables} 表）",
        ):
            if token not in budget_text:
                errors.append(f"whole-paper float budget lacks: {token}")
        for forbidden in ("Experiments", "正文", "因此", "回指", "出现位置", "content floats"):
            if forbidden in budget_text:
                errors.append(f"whole-paper float budget must ignore artifact placement: {forbidden}")
        if "<a " in budget.group(1) or "reference" in budget_text.lower():
            errors.append("whole-paper float budget must end after the two numeric entries without a reference label/link")
        if "图表数量：" not in budget_text:
            errors.append("whole-paper float budget needs an explicit visible figure/table count label")
        for css_token in (".float-budget{", "font-size:18px", "border:2px solid"):
            if css_token not in page:
                errors.append(f"whole-paper float budget is not visually prominent: {css_token}")

    dataset_sources = contract.get("dataset_citations", [])
    if not dataset_sources:
        errors.append("contract lacks dataset_citations")
    for item in dataset_sources:
        name, url = item.get("name"), item.get("url")
        if not re.search(rf'<a href="{re.escape(url)}">{re.escape(name)}</a>', page):
            errors.append(f"confirmed dataset lacks its direct citation: {name}")

    setup_match = re.search(r'<h4>5\.1 Setup</h4>(.*?)</table>', page, re.S)
    if not setup_match:
        errors.append("missing Experiment Setup")
    else:
        setup = setup_match.group(1)
        for baseline in contract.get("baseline_contract", {}).get("selected", []):
            url = baseline.get("url")
            if url and f'href="{url}"' not in setup:
                errors.append(f"Setup lacks baseline citation for {baseline.get('id')}")
        implementation_contract = contract.get("implementation_contract", [])
        if not implementation_contract:
            errors.append("contract lacks the per-method implementation plan")
        if {item.get("method") for item in implementation_contract} != {
            "Direct Request", "DeepInception", "PAIR", "CL-GSO", "AdvPoetry",
            "Vernacular Attack", "Style Jailbreak",
        }:
            errors.append("implementation plan must cover every baseline and the proposed method exactly once")
        setup_text = visible_text(setup)
        for item in implementation_contract:
            for token in (item.get("method"), item.get("mode"), item.get("plan")):
                if token and token not in setup_text:
                    errors.append(f"Setup implementation plan lacks: {token}")
            url = item.get("source_url")
            if url and f'href="{url}"' not in setup:
                errors.append(f"Setup implementation source lacks direct link: {item.get('method')}")
        metric_contract = contract.get("metric_contract", [])
        if not metric_contract:
            errors.append("contract lacks metric_contract")
        for metric in metric_contract:
            token = metric.get("name")
            url = metric.get("url")
            provenance = metric.get("provenance")
            if token not in visible_text(setup) or provenance not in visible_text(setup):
                errors.append(f"Setup lacks metric provenance for {token}")
            if f'href="{url}"' not in setup:
                errors.append(f"Setup lacks metric source citation {url}")

    result_region = re.search(r'<h4>5\.2[^<]*</h4>(.*?)<h3>6\.', page, re.S)
    if result_region:
        baseline_urls = {
            item.get("url") for item in contract.get("baseline_contract", {}).get("selected", []) if item.get("url")
        }
        for url in baseline_urls:
            # Dataset citations can legitimately share the Persona Vectors URL;
            # only reject links whose visible text is a baseline label.
            linked_labels = re.findall(rf'<a href="{re.escape(url)}">([^<]+)</a>', result_region.group(1))
            baseline_names = {item.get("name") for item in contract.get("baseline_contract", {}).get("selected", [])}
            if any(label in baseline_names or re.match(r"B\d+ ", label) for label in linked_labels):
                errors.append("baseline citations must appear in Setup, not result tables or figure data tables")

    ledger = re.search(r'<h3>Compact artifact ledger</h3>\s*<div class="table-wrap"><table>(.*?)</table>', page, re.S)
    if not ledger:
        errors.append("missing compact artifact ledger")
    else:
        rows = re.findall(r"<tr>(.*?)</tr>", ledger.group(1), re.S)
        widths = [len(re.findall(r"<(?:th|td)\b", row)) for row in rows]
        if not widths or any(width != 5 for width in widths):
            errors.append(f"artifact ledger must have exactly five visible columns per row: {widths}")
        if len(rows) - 1 != len(artifacts):
            errors.append("visible artifact ledger does not cover every contracted artifact exactly once")

    method_fields = {"inputs", "outputs", "variable_ids", "raw_fields", "evidence_grade"}
    for section in contract.get("paper_outline", []):
        for paragraph in section.get("paragraphs", []):
            if paragraph.get("id", "").startswith("M"):
                missing = method_fields - set(paragraph)
                if missing:
                    errors.append(f"{paragraph.get('id')}: method metadata missing {sorted(missing)}")

    baseline_fields = {
        "family", "tags", "grounded_support", "frequency", "scientific_role",
        "protocol_compatibility", "code_availability", "reproduction_burden", "inclusion_rationale",
    }
    for collection in ("selected", "unselected"):
        for baseline in contract.get("baseline_contract", {}).get(collection, []):
            missing = baseline_fields - set(baseline)
            if missing:
                errors.append(f"{baseline.get('id')}: baseline audit metadata missing {sorted(missing)}")

    repository_fields = {
        "discovery_source", "provenance_status", "priority", "verification_status",
        "license_revision", "dependencies", "compatibility_risk",
    }
    for repository in contract.get("repository_contract", {}).get("references", []):
        missing = repository_fields - set(repository)
        if missing:
            errors.append(f"{repository.get('id')}: repository audit metadata missing {sorted(missing)}")

    targets = target_ids(contract)
    if not targets:
        errors.append("no result targets")
    if len(targets) != len(set(targets)):
        errors.append("result target IDs are not unique")
    visible_table_targets = re.findall(r'data-target-id="([^"]+)"', page)
    approved_cells = {
        target
        for item in contract.get("result_requirements", [])
        for target in item.get("cell_ids", [])
    }
    if set(visible_table_targets) != approved_cells:
        errors.append("visible projected table cells do not exactly cover approved cell targets")
    return errors


def self_test() -> int:
    assert "RR-X" not in visible_text('<div data-id="RR-X">T1</div>')
    assert "RR-X" in visible_text("<div>RR-X</div>")
    assert target_ids({"result_requirements": [{"cell_ids": ["a"]}, {"panel_ids": ["b"]}]}) == ["a", "b"]
    pending_html = '<td class="pending">[PENDING]</td><td class=\'pending\'>[PENDING]</td>'
    assert len(PENDING_TD_RE.findall(pending_html)) == 2
    summary = '<td class=\'pending\' colspan=\'20\'>[PENDING]</td>'
    assert re.search(r"\bcolspan\s*=", PENDING_TD_RE.findall(summary)[0], re.I)
    print("self-test passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=Path("reports/03_EXPERIMENT_PLAN.html"))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    errors = validate(args.plan)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"validated {args.plan}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
