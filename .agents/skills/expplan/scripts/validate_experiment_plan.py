#!/usr/bin/env python3
"""Validate projected tables and reusable Python plots in EXPERIMENT_PLAN.html."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html as html_module
import json
import re
import sys
from pathlib import Path


CONTRACT_RE = re.compile(
    r'<script type="application/json" id="experiment-plan-contract">(.*?)</script>', re.S
)
APPROVAL_FIELDS = {
    "approval_status", "approved_at", "approval_channel", "approval_contract_sha256",
    "approval_contract_version",
}


def contract_digest(contract: dict) -> str:
    unsigned = {key: value for key, value in contract.items() if key not in APPROVAL_FIELDS}
    canonical = json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def identity_matches_authors(identity: str, authors: object) -> bool:
    """Accept a full author name or its conventional first-initial + surname form."""
    author_text = " ".join(map(str, authors)) if isinstance(authors, list) else str(authors)
    clean_identity = re.sub(r"[^a-z ]+", " ", identity.lower()).split()
    clean_authors = re.sub(r"[^a-z ]+", " ", author_text.lower())
    if identity.lower() in author_text.lower():
        return True
    if len(clean_identity) >= 2:
        initial_surname = rf"\b{re.escape(clean_identity[0][0])}\s+{re.escape(clean_identity[-1])}\b"
        return re.search(initial_surname, clean_authors) is not None
    return False
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
    schema_version = str(contract.get("schema_version", "1.0"))
    if schema_version not in {"1.0", "1.1"}:
        errors.append("schema_version must be 1.0 or 1.1")
    if schema_version == "1.1":
        contract_version = contract.get("contract_version")
        if not isinstance(contract_version, int) or contract_version < 1:
            errors.append("schema 1.1 requires a positive integer contract_version")
        history = contract.get("revision_history")
        if not isinstance(history, list) or not history:
            errors.append("schema 1.1 requires a non-empty revision_history")
        else:
            versions = [item.get("version") for item in history if isinstance(item, dict)]
            if versions != list(range(1, len(history) + 1)) or versions[-1] != contract_version:
                errors.append("revision_history versions must be contiguous and end at contract_version")
            for index, revision in enumerate(history):
                if not isinstance(revision, dict) or any(
                    not revision.get(field)
                    for field in ("version", "changed_at", "reason", "compatibility")
                ) or not isinstance(revision.get("changed_fields"), list):
                    errors.append(
                        f"revision_history[{index}] lacks reason/compatibility/changed_fields metadata"
                    )
            if contract_version and contract_version > 1 and not str(
                contract.get("parent_approval_sha256", "")
            ).strip():
                errors.append("an amended contract requires parent_approval_sha256")
    if contract.get("approval_status") not in {"pending", "approved"}:
        errors.append("approval_status must be pending or approved")
    if contract.get("approval_status") == "approved":
        if contract.get("approval_contract_sha256") != contract_digest(contract):
            errors.append("approved experiment contract digest is missing or does not match")
        if schema_version == "1.1" and contract.get("approval_contract_version") != contract.get("contract_version"):
            errors.append("approved schema 1.1 contract requires approval_contract_version to match contract_version")
    profile = contract.get("profile_contract", {})
    if profile.get("profile_path") != "researcher-profile/PROFILE.html":
        errors.append("profile_contract.profile_path must point to researcher-profile/PROFILE.html")
    if profile.get("publications_path") != "researcher-profile/publications.json":
        errors.append("profile_contract.publications_path must point to researcher-profile/publications.json")
    if profile.get("authorship_verified") is not True or not str(profile.get("researcher_identity", "")).strip():
        errors.append("profile_contract requires a researcher identity and verified authorship")
    structure_key = str(profile.get("structure_reference_key", "")).strip()
    if not structure_key:
        errors.append("profile_contract.structure_reference_key is required")
    project_root = plan.parent.parent if plan.parent.name == "reports" else plan.parent
    profile_path = project_root / "researcher-profile/PROFILE.html"
    publications_path = project_root / "researcher-profile/publications.json"
    publication_keys: set[str] = set()
    structure_publication: dict = {}
    if not profile_path.is_file() or not publications_path.is_file():
        errors.append("profile_contract source files do not exist; run profileconstruct")
    else:
        if str(profile.get("researcher_identity", "")).lower() not in profile_path.read_text(
            encoding="utf-8", errors="replace"
        ).lower():
            errors.append("profile_contract researcher identity is not present in PROFILE.html")
        try:
            publication_payload = json.loads(publications_path.read_text(encoding="utf-8"))
            publications = (publication_payload.get("publications", [])
                            if isinstance(publication_payload, dict) else publication_payload)
            for item in publications if isinstance(publications, list) else []:
                if isinstance(item, dict):
                    item_keys = {
                        str(item.get(field, "")).strip()
                        for field in ("citation_key", "bibtex_key", "key", "id")
                        if str(item.get(field, "")).strip()
                    }
                    publication_keys.update(item_keys)
                    if structure_key in item_keys:
                        structure_publication = item
        except json.JSONDecodeError:
            errors.append("researcher-profile/publications.json is invalid JSON")
        if structure_key and structure_key not in publication_keys:
            errors.append("profile_contract structure reference key is absent from publications.json")
        elif structure_key:
            authors = structure_publication.get("authors", [])
            identity = str(profile.get("researcher_identity", "")).strip()
            if not identity or not identity_matches_authors(identity, authors):
                errors.append("researcher identity is not an author of the structure reference publication")
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
        else:
            try:
                override_confirmed = dt.date.fromisoformat(str(override["confirmed_at"]))
                venue_date = dt.date.fromisoformat(str(target.get("confirmed_at", "")))
                generated_date = dt.date.fromisoformat(str(contract.get("generated_at", "")))
                if not venue_date <= override_confirmed <= generated_date:
                    errors.append("target.deadline_override confirmation must follow venue confirmation and precede plan generation")
            except ValueError:
                errors.append("target.deadline_override.confirmed_at must be an ISO date")
            if override.get("intended_use") not in {"internal feasibility", "preprint", "next cycle"}:
                errors.append("target.deadline_override.intended_use must be internal feasibility, preprint, or next cycle")
            if len(str(override.get("reason", "")).strip()) < 12:
                errors.append("target.deadline_override.reason must state a concrete purpose")
    try:
        venue_confirmed = dt.date.fromisoformat(str(target.get("confirmed_at", "")))
        references_confirmed = dt.date.fromisoformat(str(contract.get("references", {}).get("confirmed_at", "")))
        plan_generated = dt.date.fromisoformat(str(contract.get("generated_at", "")))
        if not venue_confirmed <= references_confirmed <= plan_generated:
            errors.append("venue confirmation must precede reference confirmation and plan generation")
    except ValueError:
        errors.append("target, references, and plan require ISO confirmation/generation dates")
    if contract.get("dataset_confirmation", {}).get("confirmed") is not True:
        errors.append("dataset slate was not explicitly confirmed before HTML generation")
    for index, metric in enumerate(contract.get("metric_contract", [])):
        required_metric_fields = (
            "id", "name", "provenance", "definition", "range", "decision_rule", "aggregation", "url",
            "construct", "claim_mappings", "cannot_establish",
            "alternative_explanations", "companion_requirements",
        )
        missing = [field for field in required_metric_fields if not str(metric.get(field, "")).strip()]
        if missing:
            errors.append(f"metric_contract[{index}] missing operational fields: {', '.join(missing)}")
        mappings = metric.get("claim_mappings")
        if not isinstance(mappings, list) or not mappings:
            errors.append(f"metric_contract[{index}].claim_mappings must be a non-empty list")
        else:
            for mapping_index, mapping in enumerate(mappings):
                if not str(mapping.get("claim_id", "")).strip():
                    errors.append(f"metric_contract[{index}].claim_mappings[{mapping_index}] lacks claim_id")
                if mapping.get("measurement_role") not in {"DIRECT", "PROXY"}:
                    errors.append(
                        f"metric_contract[{index}].claim_mappings[{mapping_index}].measurement_role "
                        "must be DIRECT or PROXY"
                    )
                if "cannot_establish" not in mapping or "companion_requirements" not in mapping:
                    errors.append(
                        f"metric_contract[{index}].claim_mappings[{mapping_index}] lacks limitations/companions"
                    )
        for field in ("alternative_explanations", "companion_requirements"):
            if not isinstance(metric.get(field), list):
                errors.append(f"metric_contract[{index}].{field} must be a list")
    measurement_fields = {
        "construct_definition", "primary_observable", "metric_ids", "measurement_role",
        "cannot_establish", "alternative_explanations", "required_controls",
        "support_pattern", "weaken_pattern", "falsify_pattern", "uncertainty_rule",
    }
    metrics_by_id = {
        metric.get("id"): metric for metric in contract.get("metric_contract", []) if metric.get("id")
    }
    for index, claim in enumerate(contract.get("claims", [])):
        measurement = claim.get("measurement_contract", {})
        missing = measurement_fields - set(measurement)
        if missing:
            errors.append(f"claims[{index}].measurement_contract missing {sorted(missing)}")
        if measurement.get("measurement_role") not in {"DIRECT", "PROXY_WITH_COMPANION"}:
            errors.append(
                f"claims[{index}].measurement_contract.measurement_role must be DIRECT or PROXY_WITH_COMPANION"
            )
        if not measurement.get("metric_ids"):
            errors.append(f"claims[{index}].measurement_contract.metric_ids must be non-empty")
        claim_id = claim.get("id")
        mapped_roles = []
        for metric_id in measurement.get("metric_ids", []):
            metric = metrics_by_id.get(metric_id)
            if metric is None:
                errors.append(f"claims[{index}] references unknown metric_id {metric_id}")
                continue
            mapped_roles.extend(
                mapping.get("measurement_role")
                for mapping in metric.get("claim_mappings", [])
                if mapping.get("claim_id") == claim_id
            )
        if measurement.get("measurement_role") == "DIRECT" and "DIRECT" not in mapped_roles:
            errors.append(f"claims[{index}] is marked DIRECT but has no directly mapped metric")
        if measurement.get("measurement_role") == "PROXY_WITH_COMPANION" and not measurement.get("required_controls"):
            errors.append(f"claims[{index}] uses a proxy without a required companion control/measure")
    decisions = contract.get("decision_space_contract", [])
    if not decisions:
        errors.append("contract lacks decision_space_contract")
    decision_fields = {
        "id", "experiment_ids", "decision_variable", "disposition", "allowed_values",
        "source", "selection_rule", "selection_observable", "budget", "freeze_point",
        "final_value_source", "test_access_prohibited",
    }
    for index, decision in enumerate(decisions):
        missing = decision_fields - set(decision)
        if missing:
            errors.append(f"decision_space_contract[{index}] missing {sorted(missing)}")
        if decision.get("disposition") not in {
            "SEARCHED", "FIXED_BY_SOURCE", "FIXED_BY_DESIGN", "NOT_APPLICABLE"
        }:
            errors.append(f"decision_space_contract[{index}] has invalid disposition")
        if decision.get("test_access_prohibited") is not True:
            errors.append(f"decision_space_contract[{index}].test_access_prohibited must be true")
        if not isinstance(decision.get("experiment_ids"), list):
            errors.append(f"decision_space_contract[{index}].experiment_ids must be a list")
    consistency = contract.get("consistency_requirements", {})
    if not all(isinstance(consistency.get(key), list)
               for key in ("canonical_terms", "source_values", "formal_links")):
        errors.append("consistency_requirements must contain three ID lists")
    else:
        baseline_ids = {
            str(item.get("id") or item.get("name") or "").strip()
            for item in contract.get("baseline_contract", {}).get("selected", [])
            if isinstance(item, dict) and str(item.get("id") or item.get("name") or "").strip()
        }
        metric_ids = {str(item.get("id")) for item in contract.get("metric_contract", []) if item.get("id")}
        formal_ids = {
            str(item.get("id")) for item in contract.get("claims", [])
            if item.get("id") and item.get("requires_formal_check") is True
        }
        expected = {
            "canonical_terms": baseline_ids | metric_ids,
            "source_values": {str(item.get("id")) for item in decisions if item.get("id")},
            "formal_links": formal_ids,
        }
        for key, wanted in expected.items():
            actual = {str(item) for item in consistency.get(key, [])}
            if actual != wanted:
                errors.append(f"consistency_requirements.{key} must exactly cover approved IDs: {sorted(wanted)}")
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
        if not isinstance(artifact.get("visible_dimensions"), list) or not artifact.get("visible_dimensions"):
            errors.append(f"{aid}: result artifact requires visible_dimensions preserved in the paper float")
        dimensions = artifact.get("dimensions", [])
        if not isinstance(dimensions, list) or not dimensions:
            errors.append(f"{aid}: result artifact requires scientific dimensions")
        elif set(map(str, artifact.get("visible_dimensions", []))) != set(map(str, dimensions)):
            errors.append(f"{aid}: visible_dimensions must exactly match scientific dimensions")
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
                required_tokens = shell.get("required_visible_tokens", [])
                if not required_tokens:
                    errors.append(f"{aid}: ablation shell must declare required_visible_tokens")
                for token in required_tokens:
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
                        series_count = len(panel_schema.get("series", [])) or 1
                        row_marks = expected_rows * series_count
                        if row_marks != expected_marks:
                            errors.append(f"{aid} panel {index}: frozen table defines {expected_rows} rows × {series_count} series but schema declares {expected_marks} marks")
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
    if not structure_key or structure_ref.get("publication_key") != structure_key:
        errors.append("researcher-owned structure reference must match the profile-verified publication key")
    local_full_text = str(structure_ref.get("local_full_text", "")).strip()
    if local_full_text and not (project_root / local_full_text).is_file():
        errors.append("researcher-owned structure reference local full text does not exist")
    publication_fulltext = str(structure_publication.get("fulltext_path", "")).strip()
    if structure_publication and publication_fulltext != local_full_text:
        errors.append("structure reference local full text must match its publications.json record")

    external_ref = contract.get("references", {}).get("external_mechanism", {})
    external_full_text = str(external_ref.get("local_full_text", "")).strip()
    if not external_ref.get("url") or not external_full_text:
        errors.append("external mechanism reference must have a URL and local full text")
    elif Path(external_full_text).is_absolute():
        errors.append("external mechanism reference local full text must be project-relative")
    elif not (project_root / external_full_text).is_file():
        errors.append("external mechanism reference local full text does not exist")

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
        implementation_table = re.search(
            r'<table class="implementation-table">(.*)$', setup, re.S
        )
        implementation_html = implementation_table.group(1) if implementation_table else ""
        if not implementation_table:
            errors.append("Setup lacks the two-column implementation table")
        else:
            headers = re.findall(r'<th>(.*?)</th>', re.search(r'<thead>(.*?)</thead>', implementation_html, re.S).group(1), re.S)
            if [visible_text(header) for header in headers] != ["Method", "How it is implemented"]:
                errors.append("implementation table must contain only Method and How it is implemented")
            for forbidden in (
                "Reuse / write boundary", "Shared boundary / fallback",
                "Source type:", "PAPER_GUIDED_REIMPLEMENT", "PAPER_SPEC",
            ):
                if forbidden in implementation_html:
                    errors.append(f"implementation table exposes internal contract field: {forbidden}")
        proposed_method = contract.get("grounding", {}).get("proposed_method")
        expected_methods = {
            item.get("name")
            for item in contract.get("baseline_contract", {}).get("selected", [])
            if item.get("name")
        }
        if proposed_method:
            expected_methods.add(proposed_method)
        actual_methods = {item.get("method") for item in implementation_contract if item.get("method")}
        if actual_methods != expected_methods or len(actual_methods) != len(implementation_contract):
            errors.append(
                "implementation plan must cover every selected baseline and the proposed method exactly once: "
                f"expected={sorted(expected_methods)}, actual={sorted(actual_methods)}"
            )
        setup_text = visible_text(setup)
        allowed_source_kinds = {"OFFICIAL_GITHUB", "LOCAL"}
        for item in implementation_contract:
            for token in (
                item.get("method"), item.get("implementation_summary"),
            ):
                if token and token not in setup_text:
                    errors.append(f"Setup implementation plan lacks: {token}")
            url = item.get("source_url")
            row = re.search(
                rf'<tr><th>{re.escape(str(item.get("display_name") or item.get("method")))}</th>(.*?)</tr>',
                implementation_html,
                re.S,
            )
            row_html = row.group(0) if row else ""
            if not row:
                errors.append(f"Setup implementation table lacks row: {item.get('display_name') or item.get('method')}")
            elif item.get("implementation_summary") not in visible_text(row_html):
                errors.append(f"Setup implementation row lacks direct decision: {item.get('method')}")
            if url and f'href="{url}"' not in row_html:
                errors.append(f"Setup implementation source lacks direct official link: {item.get('method')}")
            if not url and "<a " in row_html:
                errors.append(f"local implementation row must not contain a link: {item.get('method')}")
            source_kind = item.get("source_kind")
            if source_kind not in allowed_source_kinds:
                errors.append(f"implementation source_kind is invalid for {item.get('method')}: {source_kind}")
            mode = item.get("mode")
            if mode in {"REUSE_OFFICIAL_MODULE", "SOURCE_GUIDED_REIMPLEMENT"}:
                if source_kind != "OFFICIAL_GITHUB" or not str(url).startswith("https://github.com/"):
                    errors.append(f"source-guided implementation lacks official GitHub source: {item.get('method')}")
            if mode == "SELF_IMPLEMENT":
                if source_kind != "LOCAL" or url or not item.get("local_implementation"):
                    errors.append(f"self-implemented method lacks explicit local ownership: {item.get('method')}")
            if mode == "PAPER_GUIDED_REIMPLEMENT" or source_kind == "PAPER_SPEC":
                errors.append(
                    f"non-official code must be declared SELF_IMPLEMENT/LOCAL without an implementation link: {item.get('method')}"
                )
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
