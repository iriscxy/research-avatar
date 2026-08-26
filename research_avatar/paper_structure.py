"""One-shot reference-informed projected-paper structure design.

This module belongs to the Experiment Planning boundary.  One Agent reads the
complete researcher-owned structure-reference paper together with the current
scientific obligations, then returns (1) an auditable analysis of the reference
paper's paragraph logic and (2) the target paper's own section/paragraph
blueprint. Each target section also carries a small, exact reference-paper
context selected by rhetorical function. This is section-level guidance, never
a forced paragraph-to-paragraph alignment.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable


class PaperStructureError(RuntimeError):
    """The Agent did not return a complete projected-paper structure."""


def _numbered_source(source: str) -> str:
    return "\n".join(
        f"{index:06d}\t{line.replace(chr(12), '[PAGE BREAK]')}"
        for index, line in enumerate(source.splitlines(), 1)
    )


def _scientific_requirements(contract: dict[str, Any]) -> dict[str, Any]:
    obligations = []
    for section in contract.get("paper_outline", []):
        if not isinstance(section, dict):
            continue
        for paragraph in section.get("paragraphs", []):
            if not isinstance(paragraph, dict):
                continue
            obligations.append({
                "id": str(paragraph.get("id") or ""),
                "section": str(section.get("section_id") or section.get("id") or ""),
                "plan_sentence": str(
                    paragraph.get("plan_sentence") or paragraph.get("purpose") or ""
                ),
                "supports": paragraph.get("supports", []),
                "evidence": paragraph.get("evidence", []),
                "artifact_refs": paragraph.get("artifact_refs", []),
                "method_metadata": {
                    key: paragraph.get(key)
                    for key in (
                        "inputs", "outputs", "variable_ids", "raw_fields",
                        "evidence_grade",
                    )
                    if key in paragraph
                },
            })
    return {
        "target": contract.get("target", {}),
        # Raw two-file onboarding briefs do not have an Experiment Plan's
        # claims and content obligations yet. Without the brief, the structure
        # call sees only generic paragraph roles plus a complete reference
        # paper and inevitably turns the reference topic into the target topic.
        "target_project_brief": str(
            contract.get("target_project_brief") or ""
        ).strip(),
        "target_project_analysis": contract.get("target_project_analysis", {}),
        "writing_boundary": contract.get("writing_boundary", {}),
        "working_title": (
            contract.get("paper_title")
            or contract.get("title")
            or contract.get("source_plan")
        ),
        "claims": [
            {
                key: claim.get(key)
                for key in ("id", "statement", "claim", "text", "summary")
                if claim.get(key) not in (None, "")
            }
            for claim in contract.get("claims", [])
            if isinstance(claim, dict)
        ],
        "content_obligations": obligations,
        "paper_artifacts": [
            {
                "id": artifact.get("id"),
                "kind": artifact.get("kind"),
                "section_id": artifact.get("section_id"),
                "supports": artifact.get("supports", []),
                "caption": (
                    artifact.get("shell", {}).get("caption")
                    if isinstance(artifact.get("shell"), dict)
                    else ""
                ),
            }
            for artifact in contract.get("paper_artifacts", [])
            if isinstance(artifact, dict)
        ],
    }


def structure_prompt(
    contract: dict[str, Any],
    reference_source: str,
    *,
    reference: dict[str, Any],
    paragraph_mapping: bool = False,
    selected_reference_inventory: bool = False,
) -> str:
    """Build the single complete Experiment Planning structure-design task."""
    requirements = _scientific_requirements(contract)
    mapping_instruction = (
        "For every TARGET paragraph, select exactly one reference paragraph whose "
        "rhetorical function is the closest match and put its ID in that target "
        "paragraph's `reference_paragraph_ids` list. Reuse is allowed when the target "
        "needs more paragraphs than the reference. The section-level reference_context "
        "must contain the union of its target paragraphs' selected IDs. This mapping "
        "controls which exact reference excerpt the paragraph-writing API receives."
        if paragraph_mapping
        else (
            "This is section-level context, not a target-to-reference paragraph mapping. "
            "Do not put reference IDs or text inside target paragraph records."
        )
    )
    mapping_shape = (
        ', "reference_paragraph_ids": ["REF-I-P1"]'
        if paragraph_mapping else ""
    )
    reference_inventory_instruction = (
        "Enumerate every real body section in reading order, but include in each "
        "section's `paragraphs` list only the exact natural prose paragraphs selected "
        "as rhetorical matches for at least one TARGET paragraph. Do not emit unused "
        "reference paragraphs."
        if selected_reference_inventory
        else (
            "Enumerate the Abstract plus every real body section and every real natural "
            "prose paragraph in reading order."
        )
    )
    return f"""You are designing the projected paper structure during Experiment
Planning, before the plan is approved. Read the complete researcher-owned
structure-reference paper and the complete scientific requirements below.
Perform the entire task in this one call and return one JSON object.

The reference is structure-only authority. Learn its section order, paragraph
counts, each paragraph's rhetorical purpose, the logical transition between
adjacent paragraphs, section proportions, and figure/table rhythm. Never copy
its topic, claims, methods, numbers, datasets, citations, or wording into the
target paper. The target venue rule and the target project's scientific needs
override the reference whenever they conflict.

The `target_project_brief` inside target_scientific_requirements is the
authoritative source for the TARGET topic, research question, method, data,
experiment, and claims. Every target title and target paragraph purpose must be
about that brief. If the brief and reference discuss different topics, that is
intentional: transfer only rhetorical organization from the reference.

<structure_reference_metadata>
{json.dumps(reference, ensure_ascii=False, indent=2)}
</structure_reference_metadata>

<complete_line_numbered_structure_reference>
{_numbered_source(reference_source)}
</complete_line_numbered_structure_reference>

<target_scientific_requirements>
{json.dumps(requirements, ensure_ascii=False, indent=2)}
</target_scientific_requirements>

First return ``structure_reference_analysis``. {reference_inventory_instruction} For each
reference paragraph report a stable ID, exact inclusive line boundaries,
concise gist, rhetorical role, relation to the previous paragraph, and relation
to the next paragraph. Exclude title/authors, captions, tables, bibliography,
and appendices from the body paragraph inventory, but summarize appendix
structure separately when it materially informs the target appendix.
Every item in a reference section's ``paragraphs`` array must point to actual
natural prose. A section/subsection heading by itself, equation, figure/table
caption, list label, or empty transition is not a paragraph and must never be
assigned a reference paragraph ID.

The reference Abstract is mandatory: always emit it as the first reference
body section, using the heading ``Abstract`` and its actual abstract prose
paragraph(s). Every TARGET Abstract paragraph and its section-level
``reference_context`` must select only paragraph IDs from that reference
Abstract. Never use an Introduction, caption, contribution list, or conclusion
paragraph as the reference excerpt for the target Abstract.

Then design ``paper_outline`` for the TARGET paper. Decide its section order,
number of paragraphs per section, each paragraph's one-sentence concrete
purpose, rhetorical role, relation to the previous target paragraph, and
relation to the next target paragraph by adapting the reference's argumentative
logic to the target venue and evidence. For each target section, add one
``reference_context`` that names the corresponding reference section, explains
its structural move in concise Chinese, and selects 1--3 reference paragraph IDs
whose rhetorical function is most useful for this target section. This is
section-level inventory. {mapping_instruction}

Every input content obligation must appear in exactly one target paragraph's
``covers`` list; you may combine compatible obligations or split their content
across additional paragraphs, but may not drop or scientifically change them.
Every artifact must appear exactly once in ``artifact_refs`` at the paragraph
that introduces or interprets it. Preserve every claim/evidence/artifact
contract. Use stable target IDs, a concise concrete writing instruction in
``plan_sentence``, and section shares that sum to 1. Method paragraphs must
carry forward the applicable method metadata. A four-page short paper must be
genuinely compact rather than imitating an eight-page reference's paragraph
count mechanically.

Keep the JSON compact enough to complete reliably in one response. Return
minified JSON without Markdown or explanatory prose. Reuse a small number of
reference paragraphs when they serve the same rhetorical function; do not
invent a separate reference item for every target paragraph. Limit every
``gist``, role, and previous/next relation to at most 12 English words (or 24
Chinese characters), every ``logic_summary_zh`` to 40 Chinese characters, and
every target ``plan_sentence`` to at most 30 English words. Arrays of IDs and
method metadata are exempt from these prose limits. Concision must not remove
any required key, content obligation, claim, artifact, or paragraph mapping.

Encode subsection boundaries directly in the paragraph blueprint. For each
Method, Experiments/Evaluation, and Discussion/Analysis section with multiple
paragraphs, give the first paragraph of every logical subsection a concise
``heading`` and set ``heading_style`` to ``subsection``; use empty strings for
paragraphs that continue the current subsection. At minimum, Method needs an
overview/formalization boundary, Experiments needs setup and results/analysis
boundaries, and Discussion needs an interpretation boundary. Do not add these
headings to Abstract or Introduction merely to satisfy this rule.

If target_scientific_requirements.writing_boundary says experiment results are
unavailable, still plan and draft every section. From Experiments/Evaluation
onward, plan proposed experiment prose in future tense: specify the datasets,
baselines, metrics, main comparisons, ablations, robustness checks, and analyses
that the project idea requires. Do not state or imply any observed outcome.
When target_scientific_requirements.writing_boundary says results are unavailable,
preserve exact experimental-design constants explicitly supplied by the target
project brief, including sample counts, permutation counts, seeds, decoding settings,
and API-call budgets. Use the literal xx only for result measurements that have not
been observed. Never replace a supplied design constant with xx, expand a sampled
procedure into an exhaustive one, or copy any number from the structural reference.

Return JSON only, once, with this shape:
{{
  "structure_reference_analysis": {{
    "title": "...",
    "global_argument_arc": "...",
    "body_sections": [{{
      "heading": "1 Introduction",
      "section_role": "...",
      "relation_to_previous": "...",
      "relation_to_next": "...",
      "paragraphs": [{{
        "id": "REF-I-P1", "start_line": 10, "end_line": 20,
        "gist": "...", "rhetorical_role": "...",
        "relation_to_previous": "...", "relation_to_next": "..."
      }}]
    }}],
    "appendix_structure": "..."
  }},
  "paper_outline": [{{
    "section_id": "introduction", "title": "Introduction",
    "section_role": "...", "relation_to_previous": "...",
    "relation_to_next": "...", "length_share": 0.15,
    "reference_context": {{
      "source_heading": "1 Introduction",
      "logic_summary_zh": "参考论文先说明问题的重要性，再收窄到尚未解决的矛盾。",
      "reference_paragraph_ids": ["REF-I-P1", "REF-I-P2"]
    }},
    "paragraphs": [{{
      "id": "I-P1", "plan_sentence": "...",
      "rhetorical_role": "...", "relation_to_previous": "...",
      "relation_to_next": "...", "covers": ["I-P1"],
      "supports": ["C1"], "evidence": ["..."],
      "artifact_refs": ["F1"],
      "heading": "", "heading_style": ""{mapping_shape}
    }}]
  }}]
}}
"""


def _parse_json(response: str) -> dict[str, Any]:
    text = response.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as first_error:
        # Hosted JSON modes still occasionally emit a trailing comma in a very
        # large nested object. Repair only that unambiguous punctuation error;
        # never guess missing fields, quotes, values, or scientific content.
        repaired: list[str] = []
        in_string = False
        escaped = False
        index = 0
        while index < len(text):
            char = text[index]
            if in_string:
                repaired.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                index += 1
                continue
            if char == '"':
                in_string = True
                repaired.append(char)
                index += 1
                continue
            if char == ",":
                lookahead = index + 1
                while lookahead < len(text) and text[lookahead].isspace():
                    lookahead += 1
                if lookahead < len(text) and text[lookahead] in "}]":
                    index += 1
                    continue
            repaired.append(char)
            index += 1
        try:
            payload = json.loads("".join(repaired))
        except json.JSONDecodeError as exc:
            raise PaperStructureError(
                "结构设计 Agent 没有返回有效 JSON：" + str(first_error)
            ) from exc
    if not isinstance(payload, dict):
        raise PaperStructureError("结构设计 Agent 返回值必须是 JSON object。")
    return payload


def parse_structure_response(response: str) -> dict[str, Any]:
    """Parse a structure response with the bounded punctuation repair above."""
    return _parse_json(response)


def normalize_reference_line_ranges(
    reference_source: str, payload: dict[str, Any]
) -> None:
    """Repair mechanical line-coordinate errors in the model inventory.

    The numbered source is authoritative.  A paragraph that overlaps the
    source keeps its claimed start and has only its outer boundary clipped;
    a paragraph wholly outside the source cannot yield a real excerpt and is
    removed.  ``normalize_structure_design`` subsequently repairs any target
    context that selected a removed coordinate.
    """
    line_count = len(reference_source.splitlines())
    analysis = payload.get("structure_reference_analysis")
    sections = analysis.get("body_sections") if isinstance(analysis, dict) else None
    if not isinstance(sections, list) or line_count < 1:
        return
    for section in sections:
        if not isinstance(section, dict) or not isinstance(section.get("paragraphs"), list):
            continue
        repaired: list[dict[str, Any]] = []
        for paragraph in section["paragraphs"]:
            if not isinstance(paragraph, dict):
                continue
            start = paragraph.get("start_line")
            end = paragraph.get("end_line")
            if isinstance(start, bool) or isinstance(end, bool):
                continue
            try:
                start = int(start)
                end = int(end)
            except (TypeError, ValueError):
                continue
            if end < 1 or start > line_count or end < start:
                continue
            paragraph["start_line"] = max(1, start)
            paragraph["end_line"] = min(line_count, end)
            repaired.append(paragraph)
        section["paragraphs"] = repaired


def normalize_structure_design(
    contract: dict[str, Any], payload: dict[str, Any], *, paragraph_mapping: bool = False
) -> None:
    """Canonicalize contract-owned numeric shares and artifact bindings.

    The model owns rhetorical grouping and relative section emphasis. The
    approved/input contract owns the complete content-obligation inventory and
    which artifact belongs to each obligation. Normalizing those mechanical
    fields prevents an otherwise valid one-shot design from failing because
    rounded shares total 1.10 or because the model recopied an obligation or
    artifact ID inconsistently while regrouping obligations. Paragraph count,
    purpose, order, transitions, and rhetorical grouping remain model-owned.
    """
    outline = payload.get("paper_outline")
    if not isinstance(outline, list) or not outline:
        return

    canonicalize_target_identifiers(outline)

    analysis = payload.get("structure_reference_analysis")
    reference_sections = analysis.get("body_sections", []) if isinstance(analysis, dict) else []
    reference_ids: set[str] = set()
    reference_id_order: list[str] = []
    reference_ids_by_heading: dict[str, list[str]] = {}
    reference_heading_by_key: dict[str, str] = {}
    reference_heading_key_by_id: dict[str, str] = {}

    def heading_key(value: Any) -> str:
        return re.sub(r"^\s*(?:\d+(?:\.\d+)*[.)]?\s*)?", "", str(value)).strip().casefold()

    for reference_section in reference_sections:
        if not isinstance(reference_section, dict):
            continue
        section_ids: list[str] = []
        for paragraph in reference_section.get("paragraphs", []):
            if not isinstance(paragraph, dict):
                continue
            paragraph_id = str(paragraph.get("id") or "").strip()
            if paragraph_id and paragraph_id not in reference_ids:
                reference_ids.add(paragraph_id)
                reference_id_order.append(paragraph_id)
                section_ids.append(paragraph_id)
        if section_ids:
            key = heading_key(reference_section.get("heading"))
            reference_ids_by_heading[key] = section_ids
            reference_heading_by_key[key] = str(reference_section.get("heading") or "").strip()
            for paragraph_id in section_ids:
                reference_heading_key_by_id[paragraph_id] = key

    # Reference paragraph IDs are coordinates into the model's own one-shot
    # inventory. Repair only coordinate transcription: keep up to three valid,
    # unique selections and, when none survive, use one paragraph from the
    # source section the model itself named in the context.
    for section in outline:
        if not isinstance(section, dict):
            continue
        context = section.get("reference_context")
        if not isinstance(context, dict):
            continue
        target_key = heading_key(section.get("section_id") or section.get("title"))
        required_section_ids = (
            reference_ids_by_heading.get("abstract", [])
            if target_key == "abstract"
            else []
        )
        if target_key == "abstract" and required_section_ids:
            context["source_heading"] = reference_heading_by_key.get("abstract", "Abstract")
        context_key = heading_key(context.get("source_heading"))
        allowed_section_ids = required_section_ids or reference_ids_by_heading.get(
            context_key, []
        )
        selected = context.get("reference_paragraph_ids")
        if not allowed_section_ids and isinstance(selected, list):
            first_valid = next(
                (str(item) for item in selected if str(item) in reference_ids), ""
            )
            owner_key = reference_heading_key_by_id.get(first_valid, "")
            if owner_key:
                context["source_heading"] = reference_heading_by_key[owner_key]
                allowed_section_ids = reference_ids_by_heading[owner_key]
        repaired_ids: list[str] = []
        if isinstance(selected, list):
            for item in map(str, selected):
                if (
                    item in reference_ids
                    and (not allowed_section_ids or item in allowed_section_ids)
                    and item not in repaired_ids
                ):
                    repaired_ids.append(item)
                if len(repaired_ids) == 3:
                    break
        if not repaired_ids:
            matching = allowed_section_ids or reference_ids_by_heading.get(
                heading_key(context.get("source_heading")), []
            )
            if matching:
                repaired_ids.append(matching[0])
            elif reference_id_order:
                # The context's prose and named source section remain the
                # model's judgement; this last-resort coordinate merely keeps
                # the excerpt grounded in a paragraph the same one-shot
                # inventory actually extracted.
                repaired_ids.append(reference_id_order[0])
        context["reference_paragraph_ids"] = repaired_ids
        if paragraph_mapping:
            paragraph_ids: list[str] = []
            paragraphs = section.get("paragraphs", [])
            for paragraph in paragraphs if isinstance(paragraphs, list) else []:
                if not isinstance(paragraph, dict):
                    continue
                raw = paragraph.get("reference_paragraph_ids", [])
                valid = [
                    str(item) for item in raw
                    if str(item) in reference_ids
                    and (not allowed_section_ids or str(item) in allowed_section_ids)
                ] if isinstance(raw, list) else []
                selected_id = next(iter(dict.fromkeys(valid)), "")
                if not selected_id:
                    selected_id = next(
                        iter(
                            allowed_section_ids or reference_ids_by_heading.get(
                                heading_key(context.get("source_heading")), []
                            )
                        ),
                        repaired_ids[0] if repaired_ids else (
                            reference_id_order[0] if reference_id_order else ""
                        ),
                    )
                paragraph["reference_paragraph_ids"] = (
                    [selected_id] if selected_id else []
                )
                if selected_id and selected_id not in paragraph_ids:
                    paragraph_ids.append(selected_id)
            if paragraph_ids:
                context["reference_paragraph_ids"] = paragraph_ids

    shares: list[float | None] = []
    for section in outline:
        try:
            share = float(section.get("length_share"))
        except (AttributeError, TypeError, ValueError):
            shares.append(None)
            continue
        if not math.isfinite(share) or share <= 0:
            shares.append(None)
            continue
        shares.append(share)
    if shares:
        positive = [share for share in shares if share is not None]
        fallback = (
            sum(positive) / len(positive)
            if positive else 1.0 / len(shares)
        )
        complete = [share if share is not None else fallback for share in shares]
        total = sum(complete)
        normalized = [share / total for share in complete]
        normalized[-1] = 1.0 - sum(normalized[:-1])
        for section, share in zip(outline, normalized):
            if isinstance(section, dict):
                section["length_share"] = share

    obligation_artifacts: dict[str, list[str]] = {}
    artifact_candidates: dict[str, list[str]] = {}
    obligations_by_section: dict[str, list[str]] = {}
    obligation_order: list[str] = []
    artifact_order = [
        str(item.get("id") or "")
        for item in contract.get("paper_artifacts", [])
        if isinstance(item, dict) and str(item.get("id") or "")
    ]
    for section in contract.get("paper_outline", []):
        if not isinstance(section, dict):
            continue
        section_id = str(section.get("section_id") or section.get("id") or "")
        for paragraph in section.get("paragraphs", []):
            if not isinstance(paragraph, dict):
                continue
            obligation_id = str(paragraph.get("id") or "")
            if obligation_id:
                obligation_order.append(obligation_id)
                obligations_by_section.setdefault(section_id, []).append(obligation_id)
                obligation_artifacts[obligation_id] = [
                    str(item) for item in paragraph.get("artifact_refs", [])
                    if str(item)
                ]
                for artifact_id in obligation_artifacts[obligation_id]:
                    artifact_candidates.setdefault(artifact_id, []).append(obligation_id)
    if not obligation_artifacts:
        return
    introduced_after = {
        str(item.get("id") or ""): str(item.get("introduced_after") or "")
        for item in contract.get("paper_artifacts", [])
        if isinstance(item, dict) and str(item.get("id") or "")
    }
    # A plan may name the same figure/table in multiple adjacent paragraph
    # obligations (one paragraph interprets human agreement, the next
    # interprets efficiency, both use F4).  The manuscript still needs one
    # physical float.  Prefer its explicit ``introduced_after`` binding;
    # otherwise use the last contracted mention, which is where a result float
    # is conventionally inserted after all of its setup/interpretation prose.
    artifact_owner = {
        artifact_id: (
            introduced_after.get(artifact_id)
            if introduced_after.get(artifact_id) in candidates
            else candidates[-1]
        )
        for artifact_id, candidates in artifact_candidates.items()
        if candidates
    }

    # ``covers`` is bookkeeping over the immutable input obligations. Keep the
    # first valid model binding, discard unknown/duplicate IDs, then place only
    # missing obligations into the closest paragraph of the same target
    # section. This repairs transcription drift without changing any generated
    # rhetorical content or forcing the target to copy reference paragraph
    # counts.
    paragraphs_by_section: dict[str, list[dict[str, Any]]] = {}
    all_target_paragraphs: list[dict[str, Any]] = []
    seen_obligations: set[str] = set()
    for section in outline:
        if not isinstance(section, dict):
            continue
        section_id = str(section.get("section_id") or "")
        target_paragraphs = [
            paragraph for paragraph in section.get("paragraphs", [])
            if isinstance(paragraph, dict)
        ]
        paragraphs_by_section[section_id] = target_paragraphs
        all_target_paragraphs.extend(target_paragraphs)
        for paragraph in target_paragraphs:
            repaired: list[str] = []
            covers = paragraph.get("covers")
            if isinstance(covers, list):
                for item in map(str, covers):
                    if item in obligation_artifacts and item not in seen_obligations:
                        repaired.append(item)
                        seen_obligations.add(item)
            paragraph["covers"] = repaired
    missing = [item for item in obligation_order if item not in seen_obligations]
    if all_target_paragraphs:
        obligation_section = {
            obligation_id: section_id
            for section_id, identifiers in obligations_by_section.items()
            for obligation_id in identifiers
        }
        for obligation_id in missing:
            section_id = obligation_section.get(obligation_id, "")
            targets = paragraphs_by_section.get(section_id) or all_target_paragraphs
            source_group = obligations_by_section.get(section_id) or obligation_order
            source_index = source_group.index(obligation_id)
            target_index = min(
                len(targets) - 1,
                (source_index * len(targets)) // max(1, len(source_group)),
            )
            targets[target_index]["covers"].append(obligation_id)

    rank = {artifact_id: index for index, artifact_id in enumerate(artifact_order)}
    for section in outline:
        if not isinstance(section, dict):
            continue
        for paragraph in section.get("paragraphs", []):
            if not isinstance(paragraph, dict) or not isinstance(paragraph.get("covers"), list):
                continue
            inherited = {
                artifact_id
                for obligation_id in map(str, paragraph["covers"])
                for artifact_id in obligation_artifacts.get(obligation_id, [])
                if artifact_owner.get(artifact_id) == obligation_id
            }
            paragraph["artifact_refs"] = sorted(
                inherited, key=lambda item: (rank.get(item, len(rank)), item)
            )


def _identifier_slug(value: Any, fallback: str) -> str:
    """Return a conservative ASCII identifier without interpreting prose."""
    characters: list[str] = []
    previous_separator = False
    for character in str(value or "").strip().casefold():
        if character.isascii() and character.isalnum():
            characters.append(character)
            previous_separator = False
        elif characters and not previous_separator:
            characters.append("-")
            previous_separator = True
    slug = "".join(characters).strip("-")
    return slug or fallback


def _paragraph_prefix(section: dict[str, Any]) -> str:
    """Choose a readable section-local prefix for generated paragraph IDs."""
    identity = " ".join(
        str(section.get(field) or "") for field in ("section_id", "id", "title")
    ).casefold()
    known = (
        (("abstract",), "ABS"),
        (("introduction",), "I"),
        (("related", "work"), "RW"),
        (("method", "approach"), "M"),
        (("experiment", "evaluation"), "E"),
        (("analysis",), "A"),
        (("discussion",), "D"),
        (("limitation", "ethic"), "L"),
        (("conclusion",), "C"),
        (("appendix",), "APP"),
    )
    for needles, prefix in known:
        if any(needle in identity for needle in needles):
            return prefix
    slug = _identifier_slug(section.get("section_id") or section.get("title"), "S")
    initials = "".join(part[0] for part in slug.split("-") if part)
    return (initials or slug[:3] or "S").upper()


def _claim_unique_identifier(candidate: str, fallback: str, used: set[str]) -> str:
    """Allocate one stable ID while preserving the first valid model suggestion."""
    suggested = candidate.strip()
    base = suggested if suggested and suggested not in used else fallback
    identifier = base
    suffix = 2
    while identifier in used:
        identifier = f"{base}-{suffix}"
        suffix += 1
    used.add(identifier)
    return identifier


def canonicalize_target_identifiers(outline: list[dict[str, Any]]) -> None:
    """Make target section and paragraph IDs globally unique before validation.

    Rhetorical content remains Agent-owned. IDs are mechanical registry keys, so
    the application, rather than the language model, resolves missing or repeated
    keys. The first non-empty unique suggestion is retained; only an invalid or
    colliding suggestion is replaced.
    """
    used_sections: set[str] = set()
    used_paragraphs: set[str] = set()
    for section_index, section in enumerate(outline, 1):
        if not isinstance(section, dict):
            continue
        raw_section_id = str(section.get("section_id") or section.get("id") or "")
        section_fallback = _identifier_slug(
            section.get("title"), f"section-{section_index}"
        )
        section_id = _claim_unique_identifier(
            raw_section_id, section_fallback, used_sections
        )
        section["section_id"] = section_id
        if "id" in section:
            section["id"] = section_id

        prefix = _paragraph_prefix(section)
        paragraphs = section.get("paragraphs", [])
        if not isinstance(paragraphs, list):
            continue
        for paragraph_index, paragraph in enumerate(paragraphs, 1):
            if not isinstance(paragraph, dict):
                continue
            raw_paragraph_id = str(paragraph.get("id") or "")
            paragraph["id"] = _claim_unique_identifier(
                raw_paragraph_id,
                f"{prefix}-P{paragraph_index}",
                used_paragraphs,
            )


def validate_structure_design(
    contract: dict[str, Any], reference_source: str, payload: dict[str, Any],
    *, require_paragraph_mapping: bool = False,
) -> None:
    """Validate coverage and protocol without making rhetorical decisions in code."""
    errors: list[str] = []
    analysis = payload.get("structure_reference_analysis")
    if not isinstance(analysis, dict) or not str(analysis.get("global_argument_arc") or "").strip():
        errors.append("缺少 structure_reference_analysis.global_argument_arc。")
    source_lines = reference_source.splitlines()
    reference_paragraphs: list[dict[str, Any]] = []
    reference_abstract_ids: set[str] = set()
    reference_ids_by_heading: dict[str, set[str]] = {}

    def normalized_heading(value: Any) -> str:
        return re.sub(
            r"^\s*(?:\d+(?:\.\d+)*[.)]?\s*)?", "", str(value or "")
        ).strip().casefold()
    if isinstance(analysis, dict):
        sections = analysis.get("body_sections")
        if not isinstance(sections, list) or not sections:
            errors.append("结构参考缺少 body_sections。")
        else:
            for section in sections:
                if not isinstance(section, dict):
                    errors.append("结构参考 section 必须是 object。")
                    continue
                for field in (
                    "heading", "section_role", "relation_to_previous", "relation_to_next"
                ):
                    if not str(section.get(field) or "").strip():
                        errors.append(f"结构参考 section 缺少 {field}。")
                paragraphs = section.get("paragraphs")
                if not isinstance(paragraphs, list):
                    errors.append(f"结构参考 section {section.get('heading')} 的 paragraphs 必须是列表。")
                    continue
                reference_paragraphs.extend(
                    paragraph for paragraph in paragraphs if isinstance(paragraph, dict)
                )
                heading = normalized_heading(section.get("heading"))
                section_ids = {
                    str(paragraph.get("id") or "").strip()
                    for paragraph in paragraphs
                    if isinstance(paragraph, dict)
                    and str(paragraph.get("id") or "").strip()
                }
                if section_ids:
                    reference_ids_by_heading[heading] = section_ids
                if heading == "abstract":
                    reference_abstract_ids.update(section_ids)
    if not reference_paragraphs:
        errors.append("结构参考分析没有任何自然段。")
    if not reference_abstract_ids:
        errors.append("结构参考分析缺少真实 Abstract 段落。")
    reference_ids: set[str] = set()
    for paragraph in reference_paragraphs:
        paragraph_id = str(paragraph.get("id") or "").strip()
        if not paragraph_id or paragraph_id in reference_ids:
            errors.append(f"结构参考 paragraph ID 无效或重复：{paragraph_id or '[empty]'}。")
        reference_ids.add(paragraph_id)
        for field in ("gist", "rhetorical_role", "relation_to_previous", "relation_to_next"):
            if not str(paragraph.get(field) or "").strip():
                errors.append(f"结构参考 paragraph {paragraph_id} 缺少 {field}。")
        start, end = paragraph.get("start_line"), paragraph.get("end_line")
        if (
            not isinstance(start, int) or isinstance(start, bool)
            or not isinstance(end, int) or isinstance(end, bool)
            or start < 1 or end < start or end > len(source_lines)
        ):
            errors.append(f"结构参考 paragraph {paragraph_id} 行号无效。")
        else:
            # Paragraph boundaries come from the structure-analysis agent, not
            # from English punctuation. A real reference paragraph may end in
            # a citation, equation, list item, caption marker, CJK punctuation,
            # or no terminal punctuation after PDF extraction. Rejecting those
            # forms blamed a valid uploaded paper for a brittle coordinate
            # heuristic and prevented the writer from opening. Line validity
            # is the protocol boundary here; rhetorical suitability remains
            # the structure agent's responsibility.
            excerpt = " ".join(
                line.strip() for line in source_lines[start - 1:end] if line.strip()
            )
            if not excerpt:
                errors.append(f"结构参考 paragraph {paragraph_id} 没有定位到文字内容。")

    outline = payload.get("paper_outline")
    if not isinstance(outline, list) or not outline:
        errors.append("缺少目标 paper_outline。")
        outline = []
    required = _scientific_requirements(contract)
    obligation_ids = {
        str(item.get("id") or "") for item in required["content_obligations"]
        if str(item.get("id") or "")
    }
    artifact_ids = {
        str(item.get("id") or "") for item in required["paper_artifacts"]
        if str(item.get("id") or "")
    }
    claim_ids = {
        str(item.get("id") or "") for item in required["claims"]
        if str(item.get("id") or "")
    }
    seen_paragraphs: set[str] = set()
    covered: list[str] = []
    used_artifacts: list[str] = []
    supported: set[str] = set()
    shares = 0.0
    for section in outline:
        if not isinstance(section, dict):
            errors.append("目标 paper_outline section 必须是 object。")
            continue
        # Only fields consumed as program coordinates are required here.
        # Rhetorical roles and transitions are generated writing guidance, not
        # user input to approve or content that application code should judge.
        for field in ("section_id", "title"):
            if not str(section.get(field) or "").strip():
                errors.append(f"目标 section 缺少 {field}。")
        reference_context = section.get("reference_context")
        target_is_abstract = str(
            section.get("section_id") or section.get("title") or ""
        ).strip().casefold() == "abstract"
        if not isinstance(reference_context, dict):
            errors.append(f"目标 section {section.get('section_id')} 缺少 reference_context。")
        else:
            for field in ("source_heading", "logic_summary_zh"):
                if not str(reference_context.get(field) or "").strip():
                    errors.append(
                        f"目标 section {section.get('section_id')} 的 reference_context 缺少 {field}。"
                    )
            selected = reference_context.get("reference_paragraph_ids")
            source_heading_key = normalized_heading(
                reference_context.get("source_heading")
            )
            source_section_ids = reference_ids_by_heading.get(source_heading_key)
            if not isinstance(selected, list) or not selected:
                errors.append(
                    f"目标 section {section.get('section_id')} 必须选择参考段落。"
                )
            elif len(selected) != len(set(map(str, selected))) or not set(
                map(str, selected)
            ).issubset(reference_ids):
                errors.append(
                    f"目标 section {section.get('section_id')} 选择了无效或重复的参考段落。"
                )
            elif not source_section_ids:
                errors.append(
                    f"目标 section {section.get('section_id')} 的 source_heading "
                    "没有对应到结构参考论文中的真实 section。"
                )
            elif not set(map(str, selected)).issubset(source_section_ids):
                errors.append(
                    f"目标 section {section.get('section_id')} 选择的参考段落不属于 "
                    "source_heading 指定的 section。"
                )
            elif target_is_abstract and not set(map(str, selected)).issubset(
                reference_abstract_ids
            ):
                errors.append("目标 Abstract 只能选择结构参考论文的真实 Abstract 段落。")
        try:
            shares += float(section.get("length_share"))
        except (TypeError, ValueError):
            errors.append(f"目标 section {section.get('section_id')} 缺少 length_share。")
        paragraphs = section.get("paragraphs")
        if not isinstance(paragraphs, list) or not paragraphs:
            errors.append(f"目标 section {section.get('section_id')} 没有 paragraphs。")
            continue
        for paragraph in paragraphs:
            if not isinstance(paragraph, dict):
                errors.append("目标 paragraph 必须是 object。")
                continue
            paragraph_id = str(paragraph.get("id") or "").strip()
            if not paragraph_id or paragraph_id in seen_paragraphs:
                errors.append(f"目标 paragraph ID 无效或重复：{paragraph_id or '[empty]'}。")
            seen_paragraphs.add(paragraph_id)
            for field in ("plan_sentence",):
                if not str(paragraph.get(field) or "").strip():
                    errors.append(f"目标 paragraph {paragraph_id} 缺少 {field}。")
            covers = paragraph.get("covers")
            artifacts = paragraph.get("artifact_refs", [])
            supports = paragraph.get("supports", [])
            if require_paragraph_mapping:
                mapped = paragraph.get("reference_paragraph_ids")
                if (
                    not isinstance(mapped, list)
                    or len(mapped) != 1
                    or str(mapped[0]) not in reference_ids
                ):
                    errors.append(
                        f"目标 paragraph {paragraph_id} 必须对应一个有效参考段落。"
                    )
                elif target_is_abstract and str(mapped[0]) not in reference_abstract_ids:
                    errors.append(
                        f"目标 Abstract paragraph {paragraph_id} 必须对应参考 Abstract。"
                    )
                elif source_section_ids and str(mapped[0]) not in source_section_ids:
                    errors.append(
                        f"目标 paragraph {paragraph_id} 的参考段落不属于 section 的 "
                        "source_heading。"
                    )
            if not isinstance(covers, list):
                errors.append(f"目标 paragraph {paragraph_id}.covers 必须是列表。")
            else:
                covered.extend(map(str, covers))
            if not isinstance(artifacts, list):
                errors.append(f"目标 paragraph {paragraph_id}.artifact_refs 必须是列表。")
            else:
                used_artifacts.extend(map(str, artifacts))
            if isinstance(supports, list):
                supported.update(map(str, supports))
    if abs(shares - 1.0) > 0.001:
        errors.append(f"目标 section length_share 总和必须为 1，当前为 {shares:.4f}。")
    if set(covered) != obligation_ids or len(covered) != len(set(covered)):
        errors.append("目标段落必须恰好覆盖每个输入 content obligation 一次。")
    if set(used_artifacts) != artifact_ids or len(used_artifacts) != len(set(used_artifacts)):
        errors.append("目标段落必须恰好放置每个 paper artifact 一次。")
    if not claim_ids.issubset(supported):
        errors.append("目标 paper_outline 没有覆盖全部 claim IDs。")
    if errors:
        raise PaperStructureError("\n".join(errors))


def materialize_reference_contexts(
    reference_source: str, payload: dict[str, Any]
) -> None:
    """Replace selected paragraph IDs with exact excerpts for downstream use."""
    lines = reference_source.splitlines()
    inventory = {
        str(paragraph["id"]): paragraph
        for section in payload["structure_reference_analysis"]["body_sections"]
        for paragraph in section.get("paragraphs", [])
    }
    for section in payload["paper_outline"]:
        context = section["reference_context"]
        selected = context.pop("reference_paragraph_ids")
        excerpts = []
        for paragraph_id in selected:
            paragraph = inventory[str(paragraph_id)]
            start = int(paragraph["start_line"])
            end = int(paragraph["end_line"])
            excerpts.append({
                "reference_paragraph_id": str(paragraph_id),
                "start_line": start,
                "end_line": end,
                "text": "\n".join(lines[start - 1:end]).strip(),
            })
        context["excerpts"] = excerpts


def design_structure_with_agent(
    contract: dict[str, Any],
    reference_source: str,
    *,
    reference: dict[str, Any],
    invoke: Callable[[str], str],
) -> dict[str, Any]:
    """Run exactly one whole-paper structure-design Agent transaction."""
    payload = _parse_json(invoke(structure_prompt(
        contract, reference_source, reference=reference
    )))
    normalize_reference_line_ranges(reference_source, payload)
    normalize_structure_design(contract, payload)
    validate_structure_design(contract, reference_source, payload)
    materialize_reference_contexts(reference_source, payload)
    return payload


def codex_structure_invoker(root: Path, reference_pdf: Path) -> Callable[[str], str]:
    """Give one complete PDF-backed Experiment Planning task to one Code Agent."""
    codex = shutil.which("codex")
    if not codex:
        raise PaperStructureError("未找到本机 codex CLI，无法设计论文结构。")
    try:
        pdf_label = reference_pdf.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise PaperStructureError("结构参考论文 PDF 必须位于项目目录内。") from exc

    def invoke(prompt: str) -> str:
        environment = dict(os.environ)
        for secret in ("OPENAI_API_KEY", "DEEPSEEK_API_KEY", "LLM_API_KEY"):
            environment.pop(secret, None)
        environment["PAPER_STUDIO_AGENT_CHILD"] = "1"
        complete_prompt = (
            f"The complete PDF is available at <reference_pdf>{pdf_label}</reference_pdf>. "
            "Read it as the primary structure source; the embedded -raw text supplies exact "
            "coordinates.\n\n" + prompt
        )
        with tempfile.TemporaryDirectory(prefix="paper-structure-") as temporary:
            output = Path(temporary) / "last-message.json"
            command = [
                codex, "exec", "--ephemeral", "--skip-git-repo-check",
                "--sandbox", "read-only", "--color", "never", "--cd", str(root),
                "--output-last-message", str(output), "-",
            ]
            try:
                completed = subprocess.run(
                    command, input=complete_prompt, capture_output=True, text=True,
                    timeout=1200, env=environment, check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise PaperStructureError("论文结构设计 Agent 超时。") from exc
            if completed.returncode:
                detail = (completed.stdout + "\n" + completed.stderr).strip()
                raise PaperStructureError(
                    "论文结构设计 Agent 失败：" + (detail[-2400:] or "codex exec failed")
                )
            if not output.is_file():
                raise PaperStructureError("论文结构设计 Agent 没有返回 JSON。")
            return output.read_text(encoding="utf-8", errors="replace")

    return invoke
