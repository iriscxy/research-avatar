#!/usr/bin/env python3
"""Validate the fixed, reader-facing section order of Research Avatar HTML reports."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path


REPORT_STRUCTURES = {
    "profile": {
        "sections": [
            ("source-coverage", "Source and Coverage"),
            ("research-identity", "Research Identity"),
            ("research-lineage", "Research Lineage"),
            ("writing-style", "Writing Style"),
            ("experiment-templates", "Experiment Templates"),
            ("workflow-preferences", "Workflow Preferences"),
            ("publication-records", "Publication Records"),
        ],
    },
    "literature": {
        "sections": [
            ("problem", "1. Problem"),
            ("approaches", "2. Approaches"),
            ("evaluation", "3. Evaluation"),
            ("gaps", "4. Gaps"),
        ],
    },
    "ideas": {
        "sections": [
            ("literature-landscape", "1. Literature Landscape"),
            ("ranked-slate", "2. Ranked Decision Slate"),
            ("candidate-cards", "3. Candidate Cards"),
            ("human-selection", "4. Human Selection"),
        ],
    },
    "expplan": {
        "sections": [
            ("target-and-references", "1. Target Conference and Reference Paper"),
            ("projected-paper", "2. Projected Paper"),
        ],
        "subsections": [
            ("projected-title-abstract", "2.1 Projected Title and Abstract"),
            ("projected-paper-structure", "2.2 Projected Paper Structure and Evidence Shells"),
        ],
    },
    "runplan": {
        "sections": [
            ("execution-estimate", "1. Execution Estimate"),
            ("implementation-sources", "2. Implementation Sources"),
            ("artifact-coverage", "3. Figure/Table Coverage"),
            ("parts-and-goals", "4. Parts and Goals"),
        ],
    },
    "results": {
        "sections": [
            ("artifact-completion", "1. Artifact Completion"),
            ("paper-artifacts", "2. Paper Tables and Figures"),
            ("generation-process", "3. 生成过程"),
        ],
    },
}

# Reader-facing reports may be translated after their fixed structure has been
# generated.  The stable contract is the section id and order; these localized
# titles are equivalent labels, not a structural change.
LOCALIZED_TITLE_ALIASES = {
    "literature": {
        "problem": {"1. 问题"},
        "approaches": {"2. 方法"},
        "evaluation": {"3. 评估"},
        "gaps": {"4. 差距"},
    },
}


class StructureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sections: list[list[str]] = []
        self.subsections: list[list[str]] = []
        self.section_bodies: list[str] = []
        self.subsection_bodies: list[str] = []
        self._section_stack: list[int] = []
        self._subsection_stack: list[int] = []
        self._section_markers: list[tuple[str, int] | None] = []
        self.figure_artifacts: list[list[str | bool]] = []
        self._artifact_markers: list[int | None] = []
        self._capture: tuple[str, int] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "section":
            marker: tuple[str, int] | None = None
            if attributes.get("data-report-section"):
                self.sections.append([attributes["data-report-section"] or "", ""])
                self.section_bodies.append("")
                self._section_stack.append(len(self.sections) - 1)
                marker = ("section", self._section_stack[-1])
            if attributes.get("data-report-subsection"):
                self.subsections.append([attributes["data-report-subsection"] or "", ""])
                self.subsection_bodies.append("")
                self._subsection_stack.append(len(self.subsections) - 1)
                marker = ("subsection", self._subsection_stack[-1])
            self._section_markers.append(marker)
            artifact_id = str(attributes.get("data-artifact-id") or "")
            if artifact_id.upper().startswith("F"):
                self.figure_artifacts.append([artifact_id, False])
                self._artifact_markers.append(len(self.figure_artifacts) - 1)
            else:
                self._artifact_markers.append(None)
        if tag == "table":
            for artifact_index in self._artifact_markers:
                if artifact_index is not None:
                    self.figure_artifacts[artifact_index][1] = True
        if tag == "h2" and self._section_stack:
            self._capture = ("section", self._section_stack[-1])
        if tag == "h3" and self._subsection_stack:
            self._capture = ("subsection", self._subsection_stack[-1])

    def handle_endtag(self, tag: str) -> None:
        if tag in {"h2", "h3"}:
            self._capture = None
        if tag == "section" and self._section_markers:
            marker = self._section_markers.pop()
            if marker and marker[0] == "subsection":
                self._subsection_stack.pop()
            elif marker and marker[0] == "section":
                self._section_stack.pop()
            self._artifact_markers.pop()

    def handle_data(self, data: str) -> None:
        if not self._capture:
            for index in self._section_stack:
                self.section_bodies[index] += data
            for index in self._subsection_stack:
                self.subsection_bodies[index] += data
            return
        kind, index = self._capture
        target = self.sections if kind == "section" else self.subsections
        target[index][1] += data


def _normalized(items: list[list[str]]) -> list[tuple[str, str]]:
    return [(item_id, " ".join(title.split())) for item_id, title in items]


def validate(kind: str, html_path: Path) -> list[str]:
    parser = StructureParser()
    parser.feed(html_path.read_text(encoding="utf-8"))
    expected = REPORT_STRUCTURES[kind]
    errors: list[str] = []
    actual_sections = _normalized(parser.sections)
    expected_sections = expected["sections"]
    aliases = LOCALIZED_TITLE_ALIASES.get(kind, {})
    sections_match = len(actual_sections) == len(expected_sections) and all(
        actual_id == expected_id
        and (actual_title == expected_title or actual_title in aliases.get(expected_id, set()))
        for (actual_id, actual_title), (expected_id, expected_title) in zip(
            actual_sections, expected_sections
        )
    )
    if not sections_match:
        errors.append(f"sections: expected {expected['sections']!r}, got {actual_sections!r}")
    actual_subsections = _normalized(parser.subsections)
    expected_subsections = expected.get("subsections", [])
    if actual_subsections != expected_subsections:
        errors.append(
            f"subsections: expected {expected_subsections!r}, got {actual_subsections!r}"
        )
    for (section_id, _title), body in zip(  # noqa: B905 - parser lists are compared above
        actual_sections, parser.section_bodies
    ):
        if len(" ".join(body.split())) < 10:
            errors.append(f"section {section_id!r} has no substantive content")
    for (subsection_id, _title), body in zip(  # noqa: B905 - parser lists are compared above
        actual_subsections, parser.subsection_bodies
    ):
        if len(" ".join(body.split())) < 10:
            errors.append(f"subsection {subsection_id!r} has no substantive content")
    if kind in {"runplan", "results"}:
        for artifact_id, has_table in parser.figure_artifacts:
            if not has_table:
                errors.append(
                    f"figure {artifact_id!r} lacks an adjacent source/evidence table"
                )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", required=True, choices=sorted(REPORT_STRUCTURES))
    parser.add_argument("--html", required=True, type=Path)
    args = parser.parse_args()
    if not args.html.is_file():
        parser.error(f"HTML file not found: {args.html}")
    errors = validate(args.kind, args.html)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"OK: {args.kind} structure matches {args.html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
