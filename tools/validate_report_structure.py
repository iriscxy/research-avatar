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
            ("scope-taxonomy", "1. Scope and Taxonomy"),
            ("theme-map", "2. Theme Map"),
            ("landscape-comparison", "3. Landscape Comparison"),
            ("live-debates", "4. Live Debates"),
            ("trends-gaps", "5. Trends and Structural Gaps"),
            ("verified-references", "6. Verified References"),
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
            ("target-and-references", "1. Target Conference and Reference Papers"),
            ("projected-paper", "2. Projected Paper"),
            ("approval", "3. Approval"),
        ],
        "subsections": [
            ("projected-title-abstract", "2.1 Projected Title and Abstract"),
            ("figure-table-count", "2.2 Figure/Table Count"),
            ("paragraph-blueprint", "2.3 Paragraph Blueprint and Evidence Shells"),
            ("claim-falsifier-evidence", "2.4 Claim–Falsifier–Evidence"),
            ("implementation-plan", "2.5 Implementation Plan"),
            ("budget-decision-criteria", "2.6 Budget and Decision Criteria"),
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
    if actual_sections != expected["sections"]:
        errors.append(f"sections: expected {expected['sections']!r}, got {actual_sections!r}")
    actual_subsections = _normalized(parser.subsections)
    expected_subsections = expected.get("subsections", [])
    if actual_subsections != expected_subsections:
        errors.append(
            f"subsections: expected {expected_subsections!r}, got {actual_subsections!r}"
        )
    for (section_id, _title), body in zip(actual_sections, parser.section_bodies):
        if len(" ".join(body.split())) < 10:
            errors.append(f"section {section_id!r} has no substantive content")
    for (subsection_id, _title), body in zip(actual_subsections, parser.subsection_bodies):
        if len(" ".join(body.split())) < 10:
            errors.append(f"subsection {subsection_id!r} has no substantive content")
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
