#!/usr/bin/env python3
"""Initialize local Paper Studio from an approved 03 plan and validated 05 results."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

from bs4 import BeautifulSoup

from research_avatar.online_studio.server import (
    _ResultArtifactTables,
    _artifact_definitions,
    _latex_escape,
    _outline_sections,
    _resolve_venue_template,
    _safe_slug,
    verified_survey_bibliography,
)


PIPELINE_REPORTS = (
    "01_LIT_SURVEY.html",
    "02_IDEA_REPORT.html",
    "03_EXPERIMENT_PLAN.html",
    "04_RUN_PLAN.html",
    "05_EXP_RESULT.html",
)


def require_report_html(root: Path, path: Path, label: str) -> Path:
    """Require a canonical pipeline input to be one HTML file in reports/."""
    resolved_root = root.resolve()
    resolved = path.resolve()
    reports = (resolved_root / "reports").resolve()
    if resolved.parent != reports or resolved.suffix.lower() != ".html":
        raise ValueError(f"{label} must be an HTML file directly inside reports/")
    if not resolved.is_file():
        raise ValueError(f"{label} does not exist: {resolved}")
    return resolved


def selected_idea_from_report(path: Path) -> dict[str, str]:
    """Read the selected idea from the canonical Idea Report HTML."""
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    selected = soup.select_one(
        'article[data-idea-id][data-default-pick="true"], '
        'article[data-idea-id][data-selected="true"], '
        'article[data-idea-id].selected'
    )
    if selected is None:
        raise ValueError("reports/02_IDEA_REPORT.html has no selected idea")
    idea_id = str(selected.get("data-idea-id") or "").strip()
    heading = selected.find("h3")
    title = re.sub(
        rf"^\s*{re.escape(idea_id)}\s*[.·:-]?\s*",
        "",
        heading.get_text(" ", strip=True) if heading else "",
    ).strip()
    if not idea_id or not title:
        raise ValueError("reports/02_IDEA_REPORT.html selected idea is incomplete")
    return {"id": idea_id, "title": title}


def validate_report_only_contract(root: Path, contract: dict) -> None:
    """Enforce one report-only input chain and exactly one structural reference."""
    reports = root / "reports"
    missing = [name for name in PIPELINE_REPORTS if not (reports / name).is_file()]
    if missing:
        raise ValueError(f"reports/ is missing canonical pipeline HTML: {', '.join(missing)}")

    policy = contract.get("downstream_input_policy", {})
    if policy.get("mode") != "REPORT_HTML_ONLY":
        raise ValueError("experiment plan must declare downstream_input_policy.mode=REPORT_HTML_ONLY")
    if policy.get("files") != [f"reports/{name}" for name in PIPELINE_REPORTS]:
        raise ValueError("downstream_input_policy.files must list reports/01 through reports/05 in order")
    if policy.get("external_source_text_allowed") is not False:
        raise ValueError("downstream_input_policy must forbid external source text")

    references = contract.get("references", {})
    paper_roles = [
        (key, value)
        for key, value in references.items()
        if key != "confirmed_at" and isinstance(value, dict) and value.get("title")
    ]
    if len(paper_roles) != 1 or paper_roles[0][0] != "researcher_owned_logic":
        raise ValueError("experiment plan must select exactly one researcher-owned structural reference paper")
    reference = paper_roles[0][1]
    for field in ("title", "authors", "venue", "publication_key", "url", "selection_basis", "experiment_design_alignment"):
        if not str(reference.get(field) or "").strip():
            raise ValueError(f"selected structural reference lacks {field}")
    if reference.get("mode") != "abstracted":
        raise ValueError("report-only initialization requires an abstracted structural reference")

    selected = selected_idea_from_report(reports / "02_IDEA_REPORT.html")
    planned = contract.get("selected_idea", {})
    if str(planned.get("id") or "").strip() != selected["id"]:
        raise ValueError("Experiment Plan selected idea does not match reports/02_IDEA_REPORT.html")


def contract_from(path: Path) -> dict:
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    node = soup.find("script", id="experiment-plan-contract")
    if node is None or not node.string:
        raise ValueError(f"{path} lacks experiment-plan-contract")
    contract = json.loads(node.string)
    if contract.get("approval_status") != "approved":
        raise ValueError(f"{path} is not approved")
    return contract


def result_tables(path: Path) -> dict:
    parser = _ResultArtifactTables()
    parser.feed(path.read_text(encoding="utf-8"))
    parser.close()
    return parser.rows


def artifact_binding_contract(
    contract: dict, sections: list[dict]
) -> tuple[dict[str, dict[str, list[str]]], dict[str, dict[str, list[str]]]]:
    """Separate manuscript citations from figure-generation dependencies.

    ``artifact_refs`` is a publication-layout contract: exactly the paragraph
    named by ``paper_artifacts[].introduced_after`` owns the manuscript
    reference and float. ``artifact_dependencies`` may name additional
    paragraphs whose accepted prose is needed to build the artifact, but those
    paragraphs must not be forced to cite it.
    """
    paragraph_locations = {
        paragraph["id"]: section["id"]
        for section in sections
        for paragraph in section["paragraphs"]
    }
    section_aliases = {
        str(alias): section["id"]
        for section in sections
        for alias in (section["id"], section.get("source_id"), section["title"])
        if alias
    }
    citations: dict[str, dict[str, list[str]]] = {}
    dependencies: dict[str, dict[str, list[str]]] = {}
    for section in sections:
        for paragraph in section["paragraphs"]:
            for artifact_id in paragraph.get("artifacts", []):
                citations.setdefault(artifact_id, {}).setdefault(section["id"], []).append(
                    paragraph["id"]
                )
            for artifact_id in paragraph.get("artifact_dependencies", []):
                dependencies.setdefault(artifact_id, {}).setdefault(section["id"], []).append(
                    paragraph["id"]
                )

    known = {
        str(item.get("id")): item
        for item in contract.get("paper_artifacts", [])
        if isinstance(item, dict) and item.get("id")
    }
    for artifact_id, artifact in known.items():
        owner = str(artifact.get("introduced_after") or "").strip()
        owner_section = paragraph_locations.get(owner, "")
        declared_section = section_aliases.get(
            str(artifact.get("section_id") or "").strip(), ""
        )
        if not owner_section:
            raise ValueError(
                f"Artifact {artifact_id} introduced_after is not a planned paragraph: {owner}"
            )
        if declared_section != owner_section:
            raise ValueError(
                f"Artifact {artifact_id} owner mismatch: section_id={declared_section or 'missing'}, "
                f"introduced_after={owner_section}/{owner}"
            )
        actual = citations.get(artifact_id, {})
        expected = {owner_section: [owner]}
        if actual != expected:
            raise ValueError(
                f"Artifact {artifact_id} must be cited only by {owner_section}/{owner}; "
                f"found {actual or 'no citation owner'}"
            )
        dependency_ids = dependencies.setdefault(artifact_id, {}).setdefault(
            owner_section, []
        )
        if owner not in dependency_ids:
            dependency_ids.append(owner)

    unknown_citations = sorted(set(citations) - set(known))
    unknown_dependencies = sorted(set(dependencies) - set(known))
    if unknown_citations or unknown_dependencies:
        unknown = sorted(set(unknown_citations + unknown_dependencies))
        raise ValueError("Unknown paragraph artifact binding: " + ", ".join(unknown))
    return citations, dependencies


def completed_run_inputs(root: Path) -> tuple[Path, Path]:
    """Resolve the exact approved plan and result page from a completed run."""
    run_path = root / "reports/04_RUN_PLAN.html"
    if not run_path.is_file():
        raise ValueError("reports/04_RUN_PLAN.html does not exist")
    soup = BeautifulSoup(run_path.read_text(encoding="utf-8"), "html.parser")
    node = soup.find("script", id="run-plan-state")
    if node is None or not node.string:
        raise ValueError("reports/04_RUN_PLAN.html lacks run-plan-state")
    state = json.loads(node.string)
    goals = state.get("goals", [])
    if not (
        (state.get("status") or state.get("state")) == "completed"
        and isinstance(goals, list)
        and bool(goals)
        and all(
            isinstance(goal, dict) and goal.get("status") == "completed"
            for goal in goals
        )
    ):
        raise ValueError("the experiment run is not fully completed")
    source_plan = str(
        state.get("source_plan") or "reports/03_EXPERIMENT_PLAN.html"
    )
    plan = (root / source_plan).resolve()
    try:
        plan.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("run-plan source_plan points outside the project") from exc
    plan = require_report_html(root, plan, "run-plan source plan")
    results = require_report_html(
        root, root / "reports/05_EXP_RESULT.html", "experiment results"
    )
    return plan, results


def clean_title(value: str) -> str:
    return re.sub(r"^\s*\d+\.\s*", "", value).strip()


def materialize_appendix_contracts(sections: list[dict]) -> None:
    """Turn future-tense appendix promises into headed deliverable contracts."""
    role_titles = {
        "formal details": "Formal Details",
        "reproducibility details": "Experimental Configuration",
        "full result grid": "Complete Smoke Results",
        "evaluator validation": "Evaluator and Proxy Definitions",
        "execution provenance": "Execution Provenance",
    }
    for section in sections:
        if section.get("render") == "abstract" or "append" not in str(
            section.get("title", "")
        ).lower():
            continue
        for paragraph in section.get("paragraphs", []):
            paragraph_id = str(paragraph.get("id") or "")
            match = re.search(r"(?:^|-)AP-?([A-Z])(?:-|$)", paragraph_id, re.I)
            if not match:
                match = re.search(r"AP-([A-Z])-", paragraph_id, re.I)
            letter = match.group(1).upper() if match else ""
            role = str(paragraph.get("rhetorical_role") or "").strip()
            title = role_titles.get(role.lower(), role.title() or "Supporting Details")
            if not str(paragraph.get("heading") or "").strip():
                paragraph["heading"] = f"Appendix {letter}: {title}" if letter else title
                paragraph["heading_style"] = "subsection"
            purpose = str(paragraph.get("purpose") or "").strip()
            promised = re.sub(
                r"^Appendix\s+[A-Z]\s+will\s+",
                "",
                purpose,
                flags=re.I,
            )
            if promised != purpose:
                purpose = "Materialize this appendix with the actual content: " + promised
            paragraph["purpose"] = purpose


def reference_contexts(contract: dict, sections: list[dict]) -> dict:
    """Build paragraph-scoped reference context from the canonical plan mapping.

    ExpPlan calls the field ``reference_mapping`` and stores complete prose in
    ``source_text``. A legacy producer used
    ``source_mappings``/``complete_source_text`` instead. PaperWrite accepts
    both spellings. A reference-level ``mode=abstracted`` governs external
    full-text access; it must not erase prose explicitly embedded in the
    approved REPORT_HTML_ONLY paragraph mapping.
    """
    reference = contract.get("references", {}).get("researcher_owned_logic", {})
    source_by_paragraph = {
        str(paragraph.get("id")): paragraph
        for section in contract.get("paper_outline", [])
        for paragraph in section.get("paragraphs", [])
        if isinstance(paragraph, dict)
    }
    contexts = {}
    for section in sections:
        logic_nodes = []
        for paragraph in section["paragraphs"]:
            paragraph_id = str(paragraph.get("id") or "").strip()
            role = str(paragraph.get("rhetorical_role") or "").strip()
            purpose = str(paragraph.get("purpose") or "").strip()
            label = paragraph_id
            if role:
                label += f"（{role}）"
            if purpose:
                label += f"：{purpose}"
            logic_nodes.append(label)
        section_logic_chain = " → ".join(node for node in logic_nodes if node)
        excerpts = []
        excerpt_index: dict[str, int] = {}
        for paragraph in section["paragraphs"]:
            original = source_by_paragraph.get(str(paragraph["id"]), {})
            mappings = []
            for field in ("reference_mapping", "source_mappings"):
                values = original.get(field, [])
                if isinstance(values, list):
                    mappings.extend(item for item in values if isinstance(item, dict))
            ids = []
            for mapping in mappings:
                source_id = str(mapping.get("source_paragraph_id") or "").strip()
                source_text = str(
                    mapping.get("complete_source_text")
                    or mapping.get("source_text")
                    or ""
                ).strip()
                if source_id:
                    ids.append(source_id)
                if source_id and source_text:
                    excerpt = {
                        "id": source_id,
                        "source_paragraph_id": source_id,
                        "source_heading": str(mapping.get("source_heading") or section["title"]),
                        "text": source_text,
                    }
                    if source_id not in excerpt_index:
                        excerpt_index[source_id] = len(excerpts)
                        excerpts.append(excerpt)
                    elif len(source_text) > len(excerpts[excerpt_index[source_id]]["text"]):
                        excerpts[excerpt_index[source_id]] = excerpt
            paragraph["reference_paragraph_ids"] = list(dict.fromkeys(ids))
        if not excerpts:
            contexts[section["id"]] = {
                "mode": "abstracted",
                "source_heading": "提炼后的结构约束",
                "logic_summary_zh": section_logic_chain,
                "writing_constraints": [
                    {
                        "id": paragraph["id"],
                        "purpose": paragraph["purpose"],
                        "rhetorical_role": paragraph.get("rhetorical_role", ""),
                        "relation_to_previous": paragraph.get("relation_to_previous", ""),
                        "relation_to_next": paragraph.get("relation_to_next", ""),
                    }
                    for paragraph in section["paragraphs"]
                ],
                "excerpts": [],
            }
        else:
            contexts[section["id"]] = {
                "mode": "source",
                "declared_reference_mode": (
                    str(reference.get("mode") or "")
                    if isinstance(reference, dict)
                    else ""
                ),
                "source_heading": excerpts[0]["source_heading"] if excerpts else section["title"],
                "logic_summary_zh": section_logic_chain,
                "excerpts": excerpts,
            }
    return contexts


def repair_reference_context(root: Path, plan: Path) -> dict:
    """Refresh report-derived writing evidence without resetting a manuscript."""
    plan = require_report_html(root, plan, "experiment plan")
    contract = contract_from(plan)
    paper = root / "paper"
    config_path = paper / "paper_studio.json"
    if not config_path.is_file():
        raise ValueError("paper/paper_studio.json does not exist")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    sections = config.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError("paper/paper_studio.json has no configured sections")

    contexts = reference_contexts(contract, sections)
    payload = {
        "reference_title": contract.get("references", {})
        .get("researcher_owned_logic", {})
        .get("title", ""),
        "sections": contexts,
    }

    def replace_json(path: Path, value: dict) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    # reference_contexts() updates only reference_paragraph_ids. Preserve
    # every other project setting, manuscript paragraph, and history entry.
    replace_json(config_path, config)
    replace_json(paper / "reference_context.json", payload)

    metrics_value = str(
        config.get("paths", {}).get("metrics", "paper/metrics.json")
    ).strip()
    metrics_path = Path(metrics_value)
    if not metrics_path.is_absolute():
        metrics_path = root / metrics_path
    metrics = (
        json.loads(metrics_path.read_text(encoding="utf-8"))
        if metrics_path.is_file()
        else {}
    )
    metrics["model_design"] = contract.get("grounding", {}).get("model_design", {})
    metrics["symbol_registry"] = contract.get("consistency_requirements", {}).get(
        "symbol_registry", []
    )
    results_report = root / "reports/05_EXP_RESULT.html"
    result_evidence_synced = False
    if results_report.is_file():
        refreshed_contract = dict(contract)
        refreshed_contract["_result_tables"] = result_tables(results_report)
        refreshed_figures, refreshed_tables, refreshed_metrics = _artifact_definitions(
            refreshed_contract, sections
        )
        metrics["artifacts"] = refreshed_metrics.get("artifacts", {})
        for collection_name, refreshed in (
            ("figures", refreshed_figures),
            ("tables", refreshed_tables),
        ):
            configured = config.get(collection_name, {})
            if not isinstance(configured, dict):
                continue
            for artifact_id, definition in refreshed.items():
                if artifact_id not in configured:
                    continue
                for field in (
                    "title", "description", "caption", "result_keys",
                    "dimensions", "visible_dimensions",
                ):
                    if field in definition:
                        configured[artifact_id][field] = definition[field]
                if definition.get("data_grid"):
                    configured[artifact_id]["data_grid"] = definition["data_grid"]
        replace_json(config_path, config)
        result_evidence_synced = True
    replace_json(metrics_path, metrics)

    state_path = paper / ".paper_studio/state.json"
    state_updated = False
    if state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        ids_by_paragraph = {
            str(paragraph.get("id") or ""): list(
                paragraph.get("reference_paragraph_ids", [])
            )
            for section in sections
            for paragraph in section.get("paragraphs", [])
            if isinstance(paragraph, dict)
        }
        for section_state in state.get("sections", {}).values():
            if not isinstance(section_state, dict):
                continue
            for paragraph in section_state.get("paragraphs", []):
                if not isinstance(paragraph, dict):
                    continue
                paragraph_id = str(paragraph.get("id") or "")
                if paragraph_id in ids_by_paragraph:
                    paragraph["reference_paragraph_ids"] = ids_by_paragraph[paragraph_id]
        for collection_name in ("figures", "tables"):
            configured = config.get(collection_name, {})
            runtime = state.get(collection_name, {})
            if not isinstance(configured, dict) or not isinstance(runtime, dict):
                continue
            for artifact_id, runtime_artifact in runtime.items():
                definition = configured.get(artifact_id, {})
                if not isinstance(runtime_artifact, dict) or not isinstance(definition, dict):
                    continue
                for field in (
                    "title", "description", "caption", "result_keys",
                    "dimensions", "visible_dimensions", "data_grid",
                ):
                    if field in definition:
                        runtime_artifact[field] = definition[field]
        replace_json(state_path, state)
        state_updated = True

    return {
        "reference_context": str((paper / "reference_context.json").relative_to(root)),
        "sections": len(contexts),
        "source_sections": sum(
            context.get("mode") == "source" for context in contexts.values()
        ),
        "mapped_paragraphs": sum(
            bool(paragraph.get("reference_paragraph_ids"))
            for section in sections
            for paragraph in section.get("paragraphs", [])
        ),
        "model_design_synced": bool(metrics.get("model_design")),
        "result_evidence_synced": result_evidence_synced,
        "state_updated": state_updated,
        "manuscript_reset": False,
    }


def initialize(root: Path, plan: Path, results: Path) -> dict:
    plan = require_report_html(root, plan, "experiment plan")
    results = require_report_html(root, results, "experiment results")
    contract = contract_from(plan)
    validate_report_only_contract(root, contract)
    contract["_result_tables"] = result_tables(results)
    sections = _outline_sections(contract)
    materialize_appendix_contracts(sections)
    figures, tables, metrics = _artifact_definitions(contract, sections)
    citation_bindings, dependency_bindings = artifact_binding_contract(contract, sections)
    for artifact_id, definition in {**figures, **tables}.items():
        citations = citation_bindings.get(artifact_id, {})
        if not citations:
            raise ValueError(f"Artifact {artifact_id} has no paragraph binding")
        definition["source_sections"] = list(citations)
        definition["related_paragraphs"] = citations
        if artifact_id in figures:
            dependencies = dependency_bindings.get(artifact_id, citations)
            definition["depends_on_paragraphs"] = dependencies
            if definition.get("kind") == "mechanism":
                definition["generation_requires_paragraphs"] = dependencies
    contexts = reference_contexts(contract, sections)

    paper = root / "paper"
    section_dir = paper / "sections"
    section_dir.mkdir(parents=True, exist_ok=True)
    target = contract.get("target", {})
    venue = str(target.get("venue") or "").strip()
    template = _resolve_venue_template(venue)
    if template is None:
        raise ValueError(f"No bundled LaTeX template matches venue: {venue}")

    selected = contract.get("selected_idea", {})
    selected_title = (
        str(selected.get("title") or "")
        if isinstance(selected, dict)
        else str(selected or "")
    ).strip()
    method_name = str(
        contract.get("grounding", {}).get("proposed_method") or ""
    ).strip()
    project_name = method_name or selected_title or plan.stem
    title = str(contract.get("paper_title") or "").strip() or selected_title or project_name
    section_specs = []
    main_inputs = []
    for section in sections:
        section_id = section["id"]
        render = section["render"]
        filename = f"{section_id}.tex"
        display_title = clean_title(section["title"])
        result_keys = sorted({
            key
            for definition in [*figures.values(), *tables.values()]
            if section_id in definition["source_sections"]
            for key in definition.get("result_keys", [])
        })
        spec = {
            "id": section_id,
            "title": display_title,
            "file": filename,
            "result_keys": result_keys,
            "render": render,
            "paragraphs": section["paragraphs"],
        }
        if render != "abstract":
            spec["latex_title"] = display_title
            spec["start_label"] = f"sec:{section_id.replace('_', '-')}"
            placeholder = f"\\section{{{_latex_escape(display_title)}}}\n\n% Awaiting paragraph-level drafting in Paper Studio.\n"
            main_inputs.append(f"\\input{{sections/{section_id}}}")
        else:
            placeholder = "% Awaiting paragraph-level drafting in Paper Studio.\n"
            main_inputs.append("\\begin{abstract}\n\\input{sections/abstract}\n\\end{abstract}")
        (section_dir / filename).write_text(placeholder, encoding="utf-8")
        section_specs.append(spec)

    for asset in template.get("assets", []):
        source = Path(template["_dir"]) / asset
        shutil.copyfile(source, paper / asset)
    figure_dir = paper / "fig"
    for figure_id, definition in figures.items():
        if definition.get("kind") != "source":
            continue
        source_value = str(definition.get("source_asset") or "").strip()
        source = (root / source_value).resolve()
        try:
            source.relative_to(root.resolve())
        except ValueError as exc:
            raise ValueError(
                f"Source figure {figure_id} points outside the project: {source_value}"
            ) from exc
        if not source.is_file() or source.suffix.lower() != ".pdf":
            raise ValueError(
                f"Source figure {figure_id} must reference an existing PDF: {source_value}"
            )
        figure_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(
            source,
            figure_dir / f"{definition['deliverable_stem']}.pdf",
        )
    (section_dir / "bibliography.tex").write_text(
        "% Paper Studio enables the bibliography after the first accepted citation.\n",
        encoding="utf-8",
    )
    abstract_inputs = [line for line in main_inputs if line.startswith("\\begin{abstract}")]
    body_inputs = [line for line in main_inputs if not line.startswith("\\begin{abstract}")]
    before_maketitle = abstract_inputs if template.get("abstract_before_maketitle") else []
    if before_maketitle and str(template.get("keywords") or "").strip():
        before_maketitle.append(
            f"\\keywords{{{_latex_escape(str(template['keywords']))}}}"
        )
    if before_maketitle and str(template.get("ccsdesc") or "").strip():
        before_maketitle.append(
            f"\\ccsdesc[500]{{{str(template['ccsdesc'])}}}"
        )
    # If the venue does not require a pre-title abstract, place it immediately
    # after \maketitle and before Introduction rather than after all sections.
    after_maketitle = ([] if before_maketitle else abstract_inputs) + body_inputs
    main = "\n".join([
        str(template["documentclass"]),
        *[str(line) for line in template.get("preamble", [])],
        f"\\title{{{_latex_escape(title)}}}",
        r"\author{Anonymous Author(s)}",
        r"\date{}",
        r"\begin{document}",
        *before_maketitle,
        r"\maketitle",
        *after_maketitle,
        # Keep late figure/table floats from drifting into and splitting the
        # bibliography.  The scaffold's template includes ``placeins``.
        r"\FloatBarrier",
        r"\input{sections/bibliography}",
        r"\end{document}",
        "",
    ])
    (paper / "main.tex").write_text(main, encoding="utf-8")

    grounding = contract.get("grounding", {})
    metrics.update({
        "claims": contract.get("claims", []),
        # Keep the approved Method specification in the bounded report-derived
        # evidence bundle. Paper Studio must not reduce it to paragraph titles.
        "model_design": grounding.get("model_design", {}),
        "symbol_registry": contract.get("consistency_requirements", {}).get(
            "symbol_registry", []
        ),
        "evaluation_protocol": grounding.get("evaluation_protocol", {}),
        "experimental_setup": {
            "datasets": grounding.get("datasets", []),
            "models": grounding.get("models", []),
            "baselines": grounding.get("baselines", []),
            "protocol": grounding.get("evaluation_protocol", {}),
        },
        "result_source": str(results.relative_to(root)),
        "contract_approval_sha256": contract.get("approval_contract_sha256"),
        "evidence_grade": contract.get("plan_variant", {}).get("evidence_grade", "validated"),
    })
    (paper / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    survey = root / "reports/01_LIT_SURVEY.html"
    bibliography = verified_survey_bibliography(survey.read_text(encoding="utf-8")) if survey.is_file() else ""
    (paper / "references.bib").write_text(bibliography, encoding="utf-8")
    (paper / "reference_context.json").write_text(
        json.dumps({
            "reference_title": contract.get("references", {}).get("researcher_owned_logic", {}).get("title", ""),
            "sections": contexts,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (paper / "working_abstract.txt").write_text(
        "Draft the abstract only from accepted manuscript evidence and validated result artifacts. Use exact supported numerical results where they materially summarize the findings, do not invent placeholders, and include no citation command.\n",
        encoding="utf-8",
    )
    (paper / ".outline-approved").write_text(
        f"Inherited from approved {plan.relative_to(root)}.\n", encoding="utf-8"
    )

    reference = contract.get("references", {}).get("researcher_owned_logic", {})
    config = {
        "schema_version": "1.0",
        "project": {
            "id": _safe_slug(project_name),
            "name": project_name,
            "initial_title": title,
            "venue": venue,
            "bibliography_style": str(template.get("bibliographystyle") or "").strip(),
            "target": {key: value for key in ("venue", "track", "cycle", "submission_content_pages", "deadline") if (value := target.get(key)) not in (None, "")},
            "reference_paper": {key: value for key in ("title", "authors", "venue", "publication_key", "url") if (value := reference.get(key))},
            "decision_source": str(plan.relative_to(root)),
            "eyebrow": "LOCAL PAPER STUDIO",
            "studio_title": "Paper Studio",
            "subtitle": "基于已批准段落规划与可追溯实验结果逐段写作",
        },
        "sections": section_specs,
        # Results must exist before their compression into the abstract.
        "batch_writing_order": [
            item["id"] for item in sections if item.get("render") != "abstract"
        ] + [item["id"] for item in sections if item.get("render") == "abstract"],
        "figure_order": [item["id"] for item in contract["paper_artifacts"] if item["id"] in figures],
        "figures": figures,
        "table_order": [item["id"] for item in contract["paper_artifacts"] if item["id"] in tables],
        "tables": tables,
        "paths": {"metrics": "paper/metrics.json", "main": "paper/main.tex"},
    }
    (paper / "paper_studio.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "config": str((paper / "paper_studio.json").relative_to(root)),
        "sections": len(section_specs),
        "paragraphs": sum(len(item["paragraphs"]) for item in section_specs),
        "figures": len(figures),
        "tables": len(tables),
        "result_artifacts": len(metrics.get("artifacts", {})),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--plan", type=Path, default=Path("reports/03_EXPERIMENT_PLAN.html"))
    parser.add_argument("--results", type=Path, default=Path("reports/05_EXP_RESULT.html"))
    parser.add_argument(
        "--from-run-plan",
        action="store_true",
        help="read the executed source_plan from a fully completed 04_RUN_PLAN.html",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="start/reuse Research Studio and open its Paper Studio tab",
    )
    parser.add_argument(
        "--repair-reference-context",
        action="store_true",
        help="rebuild only paragraph reference mappings; preserve manuscript and edit history",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    if args.from_run_plan:
        plan, results = completed_run_inputs(root)
    else:
        plan = args.plan if args.plan.is_absolute() else root / args.plan
        results = args.results if args.results.is_absolute() else root / args.results
    summary = (
        repair_reference_context(root, plan)
        if args.repair_reference_context
        else initialize(root, plan, results)
    )
    if args.open:
        from research_avatar.research_studio.server import ensure_project_studios

        studios = ensure_project_studios(open_browser=True)
        summary["research_studio"] = studios["research_studio"]["url"]
        summary["paper_studio"] = "/paper-studio/"
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
