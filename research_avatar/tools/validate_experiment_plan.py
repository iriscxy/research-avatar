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
from urllib.parse import urlparse


CONTRACT_RE = re.compile(
    r'<script type="application/json" id="experiment-plan-contract">(.*?)</script>', re.S
)
APPROVAL_FIELDS = {
    "approval_status", "approved_at", "approval_channel", "approval_contract_sha256",
    "approval_contract_version",
}

EVIDENCE_SOURCES = {
    "BENCHMARK_LABEL",
    "HUMAN_ANNOTATION",
    "LLM_JUDGE",
    "MODEL_OUTPUT",
    "SYSTEM_TRACE",
    "DERIVED",
}
DATASET_STATUSES = {
    "PUBLISHED", "PUBLIC_REPOSITORY", "USER_PROVIDED_PRIVATE", "SELF_BUILT_UNPUBLISHED",
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


def nonplaceholder_url(value: object) -> bool:
    parsed = urlparse(str(value))
    host = (parsed.hostname or "").lower()
    return (
        parsed.scheme in {"http", "https"}
        and bool(parsed.path.strip("/"))
        and host not in {"example.com", "example.org", "example.net", "localhost"}
    )


def validate_implementation_integrity(contract: dict) -> list[str]:
    """Cross-check algorithm implementation claims independently of visible prose."""
    errors: list[str] = []
    implementations = contract.get("implementation_contract", [])
    repository_urls = {
        str(reference.get("url", "")).rstrip("/")
        for reference in contract.get("repository_contract", {}).get("references", [])
        if isinstance(reference, dict) and reference.get("url")
    }
    for item in implementations if isinstance(implementations, list) else []:
        if not isinstance(item, dict):
            errors.append("implementation_contract entries must be objects")
            continue
        method = item.get("method")
        verification = item.get("implementation_verification")
        required = {
            "protocol_source", "required_components", "conformance_tests",
            "method_name_in_model_prompt",
        }
        if not isinstance(verification, dict) or any(field not in verification for field in required):
            errors.append(f"implementation {method} lacks implementation_verification")
            continue
        if not str(verification.get("protocol_source", "")).strip():
            errors.append(f"implementation {method} lacks a protocol source")
        for field in ("required_components", "conformance_tests"):
            if not isinstance(verification.get(field), list) or not verification.get(field):
                errors.append(f"implementation {method} requires non-empty {field}")
        if verification.get("method_name_in_model_prompt") is not False:
            errors.append(f"implementation {method} must forbid method-name prompting")
        source_url = str(item.get("source_url", "")).rstrip("/")
        if item.get("source_kind") == "OFFICIAL_GITHUB" and source_url not in repository_urls:
            errors.append(f"implementation {method} source is absent from repository_contract")
    return errors
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


def validate_projected_identifier_registry(contract: dict) -> list[str]:
    """Require every Projected Paper identifier namespace to be complete and unique."""
    errors: list[str] = []
    raw_sections = contract.get("paper_outline", [])
    sections = [section for section in raw_sections if isinstance(section, dict)]
    paragraphs = [
        paragraph
        for section in sections if isinstance(section, dict)
        for paragraph in section.get("paragraphs", []) if isinstance(paragraph, dict)
    ]
    artifacts = [
        artifact for artifact in contract.get("paper_artifacts", [])
        if isinstance(artifact, dict)
    ]
    requirements = [
        requirement for requirement in contract.get("result_requirements", [])
        if isinstance(requirement, dict)
    ]
    registries = {
        "section IDs": [section.get("id") or section.get("section_id") for section in sections],
        "paragraph IDs": [paragraph.get("id") for paragraph in paragraphs],
        "artifact IDs": [artifact.get("id") for artifact in artifacts],
        "LaTeX labels": [artifact.get("label") for artifact in artifacts],
        "result requirement IDs": [requirement.get("id") for requirement in requirements],
        "result target IDs": target_ids(contract),
    }
    for namespace, raw_values in registries.items():
        values = [str(value).strip() if value is not None else "" for value in raw_values]
        if any(not value for value in values):
            errors.append(f"Projected Paper {namespace} must be non-empty")
        seen: set[str] = set()
        duplicates: set[str] = set()
        for value in values:
            if not value:
                continue
            if value in seen:
                duplicates.add(value)
            seen.add(value)
        if duplicates:
            errors.append(
                f"Projected Paper {namespace} are not unique: {sorted(duplicates)}"
            )
    return errors


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
    errors.extend(validate_projected_identifier_registry(contract))
    schema_version = str(contract.get("schema_version", "1.0"))
    if schema_version != "1.2":
        errors.append("schema_version must be 1.2; legacy two-reference plans require expplan migration")
    if schema_version in {"1.1", "1.2"}:
        contract_version = contract.get("contract_version")
        if not isinstance(contract_version, int) or contract_version < 1:
            errors.append("schema 1.1+ requires a positive integer contract_version")
        history = contract.get("revision_history")
        if not isinstance(history, list) or not history:
            errors.append("schema 1.1+ requires a non-empty revision_history")
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
    if contract.get("scientific_integrity_version") != 1:
        errors.append(
            "scientific_integrity_version must be 1; regenerate the plan with "
            "claim/metric, implementation, and evidence-source integrity contracts"
        )
    if contract.get("approval_status") not in {"pending", "approved"}:
        errors.append("approval_status must be pending or approved")
    if contract.get("approval_status") == "approved":
        if contract.get("approval_contract_sha256") != contract_digest(contract):
            errors.append("approved experiment contract digest is missing or does not match")
        if schema_version in {"1.1", "1.2"} and contract.get("approval_contract_version") != contract.get("contract_version"):
            errors.append("approved schema 1.1+ contract requires approval_contract_version to match contract_version")
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
        explicit_reference_override = profile.get("explicit_reference_override") is True
        if explicit_reference_override and not str(profile.get("identity_source", "")).strip():
            errors.append("explicit reference override requires profile_contract.identity_source")
        if not explicit_reference_override and str(profile.get("researcher_identity", "")).lower() not in profile_path.read_text(
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
    errors.extend(validate_implementation_integrity(contract))
    for index, dataset in enumerate(contract.get("dataset_citations", [])):
        status = dataset.get("status") if isinstance(dataset, dict) else None
        if status not in DATASET_STATUSES:
            errors.append(f"dataset_citations[{index}] has invalid or missing status")
            continue
        url = str(dataset.get("url", "")).strip()
        if status in {"PUBLISHED", "PUBLIC_REPOSITORY"} and not nonplaceholder_url(url):
            errors.append(f"dataset_citations[{index}] requires a real public URL")
        if status in {"USER_PROVIDED_PRIVATE", "SELF_BUILT_UNPUBLISHED"}:
            if url:
                errors.append(f"dataset_citations[{index}] private/unpublished data must not have a URL")
            if any(
                not str(dataset.get(field, "")).strip()
                for field in ("version", "availability", "collection_contract")
            ):
                errors.append(
                    f"dataset_citations[{index}] private/unpublished data lacks "
                    "version/availability/collection_contract"
                )
    for index, metric in enumerate(contract.get("metric_contract", [])):
        required_metric_fields = (
            "id", "name", "provenance", "definition", "range", "decision_rule", "aggregation", "url",
            "construct", "claim_mappings", "cannot_establish",
            "alternative_explanations", "companion_requirements", "unit", "evidence_source",
            "input_fields", "calculation", "implementation", "protocol_checks",
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
        for field in ("input_fields", "protocol_checks"):
            if not isinstance(metric.get(field), list) or not metric.get(field):
                errors.append(f"metric_contract[{index}].{field} must be a non-empty list")
        evidence_source = metric.get("evidence_source")
        if evidence_source not in EVIDENCE_SOURCES:
            errors.append(
                f"metric_contract[{index}].evidence_source must be one of "
                f"{sorted(EVIDENCE_SOURCES)}"
            )
        if evidence_source == "HUMAN_ANNOTATION":
            human = metric.get("human_annotation_contract")
            required_human = {
                "annotator_count", "item_count", "blinding", "rubric_path",
                "annotation_file", "agreement_calculation",
            }
            if not isinstance(human, dict) or any(
                human.get(field) in (None, "", []) for field in required_human
            ):
                errors.append(
                    f"metric_contract[{index}] HUMAN_ANNOTATION requires a complete "
                    "human_annotation_contract"
                )
        if evidence_source == "LLM_JUDGE":
            judge = metric.get("judge_contract")
            required_judge = {"model", "prompt_path", "output_schema", "calibration"}
            if not isinstance(judge, dict) or any(
                judge.get(field) in (None, "", []) for field in required_judge
            ):
                errors.append(
                    f"metric_contract[{index}] LLM_JUDGE requires a complete judge_contract"
                )
    measurement_fields = {
        "construct_definition", "primary_observable", "metric_ids", "measurement_role",
        "cannot_establish", "alternative_explanations", "required_controls",
        "support_pattern", "weaken_pattern", "falsify_pattern", "uncertainty_rule",
        "outcome_rule",
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
        outcome_rule = measurement.get("outcome_rule")
        required_outcome = {
            "rule_id", "primary_metric_id", "operator", "support_threshold",
            "uncertainty_condition", "tie_outcome", "missing_outcome",
        }
        if not isinstance(outcome_rule, dict) or any(
            outcome_rule.get(field) in (None, "", []) for field in required_outcome
        ):
            errors.append(
                f"claims[{index}].measurement_contract requires a complete deterministic outcome_rule"
            )
        elif outcome_rule.get("primary_metric_id") not in measurement.get("metric_ids", []):
            errors.append(
                f"claims[{index}].outcome_rule primary_metric_id is not in the claim metric_ids"
            )

    claim_ids = {
        str(claim.get("id")) for claim in contract.get("claims", [])
        if isinstance(claim, dict) and claim.get("id")
    }
    inverse_metric_ids: dict[str, set[str]] = {claim_id: set() for claim_id in claim_ids}
    for metric_index, metric in enumerate(contract.get("metric_contract", [])):
        metric_id = str(metric.get("id", ""))
        mapped_claim_ids = [
            str(mapping.get("claim_id", ""))
            for mapping in metric.get("claim_mappings", []) if isinstance(mapping, dict)
        ]
        if len(mapped_claim_ids) != len(set(mapped_claim_ids)):
            errors.append(f"metric_contract[{metric_index}] has duplicate claim mappings")
        for claim_id in mapped_claim_ids:
            if claim_id not in claim_ids:
                errors.append(
                    f"metric_contract[{metric_index}] maps to unknown claim_id {claim_id}"
                )
            else:
                inverse_metric_ids[claim_id].add(metric_id)
    for claim_index, claim in enumerate(contract.get("claims", [])):
        claim_id = str(claim.get("id", ""))
        declared = {
            str(metric_id)
            for metric_id in claim.get("measurement_contract", {}).get("metric_ids", [])
        }
        inverse = inverse_metric_ids.get(claim_id, set())
        if declared != inverse:
            errors.append(
                f"claims[{claim_index}] metric_ids disagree with inverse metric claim_mappings: "
                f"declared={sorted(declared)}, inverse={sorted(inverse)}"
            )
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
    reference_heading = "Reference Paper"
    opening = re.search(
        rf"<section data-report-section=['\"]target-and-references['\"]>\s*<h2>1\. Target Conference and {reference_heading}</h2>\s*<div class=['\"]hero['\"]>(.*?)</div>\s*</section>\s*<section data-report-section=['\"]projected-paper['\"]>\s*<h2>2\. Projected Paper</h2>",
        page,
        re.S,
    )
    if not opening:
        errors.append(f"Section 1 must be Target Conference and {reference_heading} and directly precede Section 2")
    else:
        opening_html = opening.group(1)
        opening_text = visible_text(opening_html)
        expected_count = 2
        if len(re.findall(r"<p\b", opening_html)) != expected_count:
            errors.append(f"Section 1 must contain exactly {expected_count} entries")
        required_entries = ("Target conference:", "Researcher-owned logic reference:")
        for required in required_entries:
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
        for role in ("researcher_owned_logic",):
            url = references.get(role, {}).get("url")
            if not url or f'href="{url}"' not in opening_html:
                errors.append(f"Section 1 lacks direct link for {role}")
    if "Confirmed references" in text:
        errors.append("confirmed references must not be duplicated after Section 1")
    for token in ("RR-", "PENDING:", "fig:", "tab:"):
        if token in text:
            errors.append(f"visible internal/result identifier leaked: {token}")

    reported_reconstruction = bool(contract.get("target_work")) and bool(
        contract.get("result_requirements")
    ) and all(
        item.get("source_action") == "REUSE_REPORTED"
        for item in contract.get("result_requirements", [])
    )

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
            if reported_reconstruction:
                if "PAPER-REPORTED VALUES" not in block_text:
                    errors.append(f"{aid}: reported reconstruction lacks a paper-reported-values notice")
            elif "RESULT PLACEHOLDER — NO NUMBERS FABRICATED" not in block_text:
                errors.append(f"{aid}: missing no-fabricated-table-values warning")
            if "Dataset" not in block_text and "Datasets" not in block_text:
                errors.append(f"{aid}: dataset is not determined in the visible main table/note")
            if "<a href=" not in block:
                errors.append(f"{aid}: dataset citation is missing from the visible table/note")
            if reported_reconstruction:
                reported_cells = re.findall(
                    r'<td class="reported" data-target-id="[^"]+">(.*?)</td>', block, re.S
                )
                if not reported_cells or any(not visible_text(cell).strip() for cell in reported_cells):
                    errors.append(f"{aid}: reported reconstruction must display every sourced value")
            else:
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
                for index, (pair, panel_schema) in enumerate(
                    zip(panel_pairs, schema_panels), 1  # noqa: B905 - mismatch reported above
                ):
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
    references = contract.get("references", {})
    structure_ref = references.get("researcher_owned_logic", {})
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

    if set(references) != {"confirmed_at", "researcher_owned_logic"}:
        errors.append("schema 1.2 references must contain exactly confirmed_at and researcher_owned_logic")
    analysis = contract.get("structure_reference_analysis")
    if not isinstance(analysis, dict):
        errors.append("schema 1.2 requires structure_reference_analysis")
    else:
        for field in ("publication_key", "local_full_text", "source_sha256", "global_argument_arc", "body_sections"):
            if not analysis.get(field):
                errors.append(f"structure_reference_analysis.{field} is required")
        if analysis.get("publication_key") != structure_key:
            errors.append("structure_reference_analysis must identify the sole author-owned reference")
        if analysis.get("local_full_text") != local_full_text:
            errors.append("structure_reference_analysis full text must match the sole reference")
        if local_full_text and (project_root / local_full_text).is_file():
            actual_hash = hashlib.sha256((project_root / local_full_text).read_bytes()).hexdigest()
            if analysis.get("source_sha256") != actual_hash:
                errors.append("structure_reference_analysis source_sha256 does not match the full text")

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
        count_pairs = (
            (
                f"本计划 {body_figures + body_tables}（{body_figures} 图，{body_tables} 表）",
                f"this plan {body_figures + body_tables} ({body_figures} figures, {body_tables} tables)",
            ),
            (
                f"参考论文 {reference_figures + reference_tables}（{reference_figures} 图，{reference_tables} 表）",
                f"reference paper {reference_figures + reference_tables} ({reference_figures} figures, {reference_tables} tables)",
            ),
        )
        for chinese, english in count_pairs:
            if chinese not in budget_text and english not in budget_text:
                errors.append(f"whole-paper float budget lacks: {chinese} / {english}")
        for forbidden in ("Experiments", "正文", "因此", "回指", "出现位置", "content floats"):
            if forbidden in budget_text:
                errors.append(f"whole-paper float budget must ignore artifact placement: {forbidden}")
        if "<a " in budget.group(1) or "reference label" in budget_text.lower():
            errors.append("whole-paper float budget must end after the two numeric entries without a reference label/link")
        if "图表数量：" not in budget_text and "Figure/table count:" not in budget_text:
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

    setup_match = re.search(
        r'<div\s+data-experiment-setup(?:\s+class="[^"]*")?>(.*?)</div>',
        page,
        re.S,
    )
    if not setup_match:
        errors.append("missing Experiment Setup")
    else:
        setup = setup_match.group(1)
        if re.search(r"<p\b", setup):
            errors.append("Experimental Setup must use the fixed compact tables, not prose paragraphs")
        setup_table = re.search(
            r'<table class="setup-table">\s*<tbody>(.*?)</tbody>\s*</table>',
            setup,
            re.S,
        )
        expected_setup_labels = [
            "Dataset", "Model", "Baselines", "Proposed method", "Noise and runs", "Metrics",
        ]
        setup_values = {}
        if not setup_table:
            errors.append("Experimental Setup lacks the fixed six-row setup-table")
        else:
            setup_rows = re.findall(r"<tr>\s*<th>(.*?)</th>\s*<td>(.*?)</td>\s*</tr>", setup_table.group(1), re.S)
            labels = [visible_text(label) for label, _ in setup_rows]
            if labels != expected_setup_labels:
                errors.append(f"setup-table rows must be exactly {expected_setup_labels}: {labels}")
            setup_values = {visible_text(label): visible_text(value) for label, value in setup_rows}
        expected_setup_counts = {
            "Dataset": len(contract.get("dataset_citations", [])),
            "Baselines": len(contract.get("baseline_contract", {}).get("selected", [])),
            "Proposed method": 1,
        }
        for label, expected_count in expected_setup_counts.items():
            if not re.match(rf"{expected_count}\s*(?:—|-|:)", setup_values.get(label, "")):
                errors.append(f"{label} must begin with the explicit count {expected_count}")
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
            if [visible_text(header) for header in headers] != ["Method", "Selection and implementation"]:
                errors.append("implementation table must contain only Method and Selection and implementation")
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
        baseline_citation_urls = {
            str(item.get("name")): str(item.get("url"))
            for item in contract.get("baseline_contract", {}).get("selected", [])
            if item.get("name") and item.get("url")
        }
        for item in implementation_contract:
            for token in (item.get("method"),):
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
            elif not visible_text(row_html).replace(str(item.get("display_name") or item.get("method")), "", 1).strip():
                errors.append(f"Setup implementation row lacks a concise implementation decision: {item.get('method')}")
            if url and f'href="{url}"' not in row_html:
                errors.append(f"Setup implementation source lacks direct official link: {item.get('method')}")
            if not url and "<a " in row_html:
                linked_urls = set(re.findall(r'<a href="([^"]+)">', row_html))
                allowed_citation = baseline_citation_urls.get(str(item.get("method")))
                if linked_urls - ({allowed_citation} if allowed_citation else set()):
                    errors.append(f"local implementation row contains an unsupported link: {item.get('method')}")
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
            token = str(metric.get("name", ""))
            url = str(metric.get("url", ""))
            provenance = str(metric.get("provenance", ""))
            unit = str(metric.get("unit", ""))
            if (
                token not in visible_text(setup)
                or provenance not in visible_text(setup)
                or not unit
                or unit not in visible_text(setup)
            ):
                errors.append(f"Setup lacks metric provenance for {token}")
            if f'href="{url}"' not in setup:
                errors.append(f"Setup lacks metric source citation {url}")

    method_sections = [
        section for section in contract.get("paper_outline", [])
        if str(section.get("id") or section.get("section_id") or "").lower() == "method"
    ]
    model_design = contract.get("grounding", {}).get("model_design")
    if method_sections:
        required_design_fields = {
            "source_authority", "inputs", "outputs", "modules", "backbone",
            "stage_1", "stage_boundary", "stage_2", "adaptive_rule",
            "symbols", "data_flow", "algorithm_steps", "objectives",
            "implementation_details", "inference", "unknowns",
            "reproducibility_status", "falsifiable_links",
        }
        if not isinstance(model_design, dict):
            errors.append("projected Method requires grounding.model_design")
            model_design = {}
        missing_design = required_design_fields - set(model_design)
        if missing_design:
            errors.append(f"grounding.model_design lacks {sorted(missing_design)}")
        for field in (
            "inputs", "outputs", "modules", "algorithm_steps", "objectives",
            "implementation_details", "unknowns", "falsifiable_links",
        ):
            value = model_design.get(field)
            if not isinstance(value, list) or not value or not all(str(item).strip() for item in value):
                errors.append(f"grounding.model_design.{field} must be a non-empty list")
        list_fields = {
            "inputs", "outputs", "modules", "algorithm_steps", "objectives",
            "implementation_details", "unknowns", "falsifiable_links",
        }
        for field in required_design_fields - list_fields:
            if not str(model_design.get(field, "")).strip():
                errors.append(f"grounding.model_design.{field} is required")
        design_blocks = re.findall(
            r'<div\b[^>]*\bdata-model-design(?:\s*=\s*["\'][^"\']*["\'])?[^>]*>(.*?)</div>',
            page,
            re.S | re.I,
        )
        if len(design_blocks) != 1:
            errors.append("projected Method must contain exactly one visible data-model-design block")
        else:
            design_text = visible_text(design_blocks[0])
            for field in ("source_authority", "stage_1", "stage_boundary", "stage_2", "inference"):
                token = str(model_design.get(field, "")).strip()
                if token and token not in design_text:
                    errors.append(f"visible model design disagrees with grounding.model_design.{field}")
            for item in model_design.get("modules", []) + model_design.get("falsifiable_links", []):
                if str(item).strip() not in design_text:
                    errors.append(f"visible model design lacks contracted content: {item}")
            for field in (
                "symbols", "data_flow", "adaptive_rule", "reproducibility_status",
            ):
                token = str(model_design.get(field, "")).strip()
                if token and token not in design_text:
                    errors.append(f"visible model design disagrees with grounding.model_design.{field}")
            for field in ("algorithm_steps", "objectives", "implementation_details", "unknowns"):
                for item in model_design.get(field, []):
                    if str(item).strip() not in design_text:
                        errors.append(f"visible model design lacks contracted {field} item: {item}")
            row_count = len(re.findall(r"<tr\b", design_blocks[0], re.I))
            if not 8 <= row_count <= 14:
                errors.append(f"visible model design must stay compact at 8-14 rows; found {row_count}")
            if len(design_text) > 7000:
                errors.append("visible model design exceeds the concise 7000-character ceiling")
            if not re.search(r"(?:λ|lambda|weight|loss|objective)", design_text, re.I):
                errors.append("visible model design lacks an objective or weighting rule")
        symbol_registry = contract.get("consistency_requirements", {}).get("symbol_registry")
        if not isinstance(symbol_registry, list) or not symbol_registry:
            errors.append("Method plan requires one structured consistency_requirements.symbol_registry")
        else:
            symbol_ids = [
                str(symbol.get("id", "")) for symbol in symbol_registry
                if isinstance(symbol, dict)
            ]
            if len(symbol_ids) != len(set(symbol_ids)) or any(not value for value in symbol_ids):
                errors.append("symbol_registry IDs must be unique and non-empty")
            for symbol_index, symbol in enumerate(symbol_registry):
                if not isinstance(symbol, dict) or any(
                    not str(symbol.get(field, "")).strip()
                    for field in ("id", "latex", "meaning")
                ):
                    errors.append(f"symbol_registry[{symbol_index}] lacks id/latex/meaning")
            if model_design.get("symbol_ids") != symbol_ids:
                errors.append("grounding.model_design.symbol_ids must preserve the symbol registry order")
            known_symbol_ids = set(symbol_ids)
            for artifact in contract.get("paper_artifacts", []):
                referenced = artifact.get("symbol_ids", []) if isinstance(artifact, dict) else []
                if any(str(symbol_id) not in known_symbol_ids for symbol_id in referenced):
                    errors.append(f"artifact {artifact.get('id')} references an unknown symbol ID")
        target_work = contract.get("target_work")
        if isinstance(target_work, dict):
            authority = str(model_design.get("source_authority", "")).strip()
            expected_authority = str(target_work.get("local_full_text", "")).strip()
            structure_authority = str(
                contract.get("references", {}).get("researcher_owned_logic", {}).get("local_full_text", "")
            ).strip()
            if authority != expected_authority:
                errors.append("one-goal-paper reconstruction model design must use target_work.local_full_text as source_authority")
            if authority and authority == structure_authority:
                errors.append("one-goal-paper reconstruction must not source model design from the structural reference")
            if "reconstruction_policy" not in model_design:
                errors.append("one-goal-paper reconstruction model design requires reconstruction_policy")
            if not model_design.get("unknowns"):
                errors.append("one-goal-paper reconstruction model design requires explicit source-undisclosed unknowns")
            if model_design.get("reproducibility_status") not in {
                "complete", "partial_due_to_source_omissions"
            }:
                errors.append("one-goal-paper reconstruction has invalid reproducibility_status")

    ledger = re.search(r'<h4>Compact artifact ledger</h4>\s*<div class="table-wrap"><table>(.*?)</table>', page, re.S)
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
        if schema_version == "1.2":
            for field in ("section_role", "relation_to_previous", "relation_to_next", "length_share"):
                if section.get(field) in (None, ""):
                    errors.append(f"{section.get('id') or section.get('section_id')}: section architecture missing {field}")
        for paragraph in section.get("paragraphs", []):
            if schema_version == "1.2":
                required_architecture = {
                    "id", "plan_sentence", "rhetorical_role", "relation_to_previous",
                    "relation_to_next", "supports", "evidence", "artifact_refs",
                }
                missing_architecture = required_architecture - set(paragraph)
                if missing_architecture:
                    errors.append(
                        f"{paragraph.get('id')}: target architecture missing {sorted(missing_architecture)}"
                    )
                for field in ("plan_sentence", "rhetorical_role", "relation_to_previous", "relation_to_next"):
                    if not str(paragraph.get(field, "")).strip():
                        errors.append(f"{paragraph.get('id')}: target architecture has empty {field}")
                forbidden_mapping = {"reference_anchor", "reference_lines", "reference_paragraph_id"} & set(paragraph)
                if forbidden_mapping:
                    errors.append(
                        f"{paragraph.get('id')}: target-to-reference mapping is forbidden: {sorted(forbidden_mapping)}"
                    )
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
