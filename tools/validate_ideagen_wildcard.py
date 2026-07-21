#!/usr/bin/env python3
"""Validate a standard Research Buddy idea report with one optional wildcard."""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


REQUIRED_LABELS = (
    "one-sentence pitch",
    "verified anomaly",
    "broken assumption",
    "drift operator",
    "core mechanism",
    "why the current route cannot absorb it",
    "predicted signature",
    "decisive falsifier",
    "minimum viable evidence",
    "closest work and collision verdict",
    "own-work check",
    "paradigm break",
    "evidence plausibility",
    "falsifiability",
    "leverage / option value",
    "disruptive score",
    "feasibility",
    "strongest reviewer objection",
)

VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


class ReportParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.idea_branch: str | None = None
        self.wildcard: str | None = None
        self.legacy_slate_shortfall = False
        self.disruptive_cards: list[dict[str, object]] = []
        self.standard_cards: list[dict[str, object]] = []
        self.sequence: list[tuple[str, str]] = []
        self.all_text: list[str] = []
        self._card: dict[str, object] | None = None
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "main":
            self.idea_branch = attr.get("data-idea-branch")
            self.wildcard = attr.get("data-disruptive-wildcard")
            self.legacy_slate_shortfall = "data-slate-shortfall" in attr
        if tag == "article" and (
            attr.get("data-idea-id") or attr.get("data-disruptive-id")
        ):
            kind = "standard" if attr.get("data-idea-id") else "disruptive"
            idea_id = attr.get("data-idea-id") or attr.get("data-disruptive-id")
            self._card = {
                "kind": kind,
                "id": idea_id,
                "text": [],
                "links": [],
            }
            self._depth = 1
        elif self._card is not None:
            if tag == "a" and attr.get("href"):
                self._card["links"].append(attr["href"])
            if tag not in VOID_TAGS:
                self._depth += 1

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attr = dict(attrs)
        if self._card is not None and tag == "a" and attr.get("href"):
            self._card["links"].append(attr["href"])

    def handle_endtag(self, tag: str) -> None:
        if self._card is None:
            return
        self._depth -= 1
        if self._depth == 0:
            kind = str(self._card["kind"])
            idea_id = str(self._card["id"])
            if kind == "standard":
                self.standard_cards.append(self._card)
            else:
                self.disruptive_cards.append(self._card)
            self.sequence.append((kind, idea_id))
            self._card = None

    def handle_data(self, data: str) -> None:
        self.all_text.append(data)
        if self._card is not None:
            self._card["text"].append(data)


def validate_text(html: str) -> list[str]:
    parser = ReportParser()
    parser.feed(html)
    errors: list[str] = []
    branch = parser.idea_branch
    if branch != "standard":
        errors.append('main must declare data-idea-branch="standard"')
    if parser.wildcard not in {"present", "shortfall", "off"}:
        errors.append(
            "main must declare data-disruptive-wildcard="
            '"present", "shortfall", or "off"'
        )
    if parser.legacy_slate_shortfall:
        errors.append(
            "data-slate-shortfall is obsolete; use "
            'data-disruptive-wildcard="shortfall"'
        )

    standard_ids = [str(card["id"]) for card in parser.standard_cards]
    if not 4 <= len(standard_ids) <= 6:
        errors.append(
            f"report has {len(standard_ids)} standard cards; expected 4–6"
        )
    if len(standard_ids) != len(set(standard_ids)):
        errors.append("standard ids are not unique")
    for idea_id in standard_ids:
        if not re.fullmatch(r"I[1-9][0-9]*", idea_id):
            errors.append(f"invalid standard id: {idea_id}")

    disruptive_ids = [str(card["id"]) for card in parser.disruptive_cards]
    if parser.wildcard == "present":
        if disruptive_ids != ["D1"]:
            errors.append(
                "present wildcard must contain exactly one disruptive card D1"
            )
    elif disruptive_ids:
        errors.append(
            f"{parser.wildcard} wildcard must contain no disruptive cards; "
            f"found {disruptive_ids}"
        )

    if disruptive_ids:
        first_d = next(
            index
            for index, (kind, _) in enumerate(parser.sequence)
            if kind == "disruptive"
        )
        if any(kind == "standard" for kind, _ in parser.sequence[first_d + 1 :]):
            errors.append("D1 must appear after every standard idea card")

    normalized_report = re.sub(
        r"\s+", " ", " ".join(parser.all_text)
    ).strip().casefold()
    if parser.wildcard == "shortfall" and "shortfall" not in normalized_report:
        errors.append("shortfall report must visibly explain the wildcard shortfall")

    for card in parser.disruptive_cards:
        idea_id = str(card["id"])
        text = " ".join(str(part) for part in card["text"])
        normalized = re.sub(r"\s+", " ", text).strip().casefold()
        for label in REQUIRED_LABELS:
            if label not in normalized:
                errors.append(f"{idea_id}: missing visible label '{label}'")
        links = [str(link) for link in card["links"]]
        if not any(link.startswith(("https://arxiv.org/", "https://doi.org/")) for link in links):
            errors.append(f"{idea_id}: no direct arXiv/DOI closest-work link")
    return errors


def self_test() -> int:
    fields = "<br>".join(f"<p>{label}: value</p>" for label in REQUIRED_LABELS)
    standard = "".join(
        f'<article data-idea-id="I{i}">standard {i}</article>'
        for i in range(1, 6)
    )
    d1 = (
        f'<article data-disruptive-id="D1">{fields}'
        '<a href="https://arxiv.org/abs/2401.00001">work</a></article>'
    )
    valid = (
        '<main data-idea-branch="standard" '
        f'data-disruptive-wildcard="present">{standard}{d1}</main>'
    )
    shortfall = (
        '<main data-idea-branch="standard" '
        f'data-disruptive-wildcard="shortfall">{standard}'
        "<section>Disruptive wildcard shortfall: no seed survived.</section></main>"
    )
    off = (
        '<main data-idea-branch="standard" '
        f'data-disruptive-wildcard="off">{standard}</main>'
    )
    invalid = (
        '<main data-idea-branch="disruptive" '
        f'data-disruptive-wildcard="present">{d1}{standard}</main>'
    )
    valid_errors = validate_text(valid)
    shortfall_errors = validate_text(shortfall)
    off_errors = validate_text(off)
    invalid_errors = validate_text(invalid)
    if valid_errors or shortfall_errors or off_errors or not invalid_errors:
        print(
            json.dumps(
                {
                    "valid_errors": valid_errors,
                    "shortfall_errors": shortfall_errors,
                    "off_errors": off_errors,
                    "invalid_errors": invalid_errors,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    print("self-test: PASS")
    return 0


def main() -> int:
    argp = argparse.ArgumentParser()
    argp.add_argument("report", nargs="?", type=Path)
    argp.add_argument("--self-test", action="store_true")
    args = argp.parse_args()
    if args.self_test:
        return self_test()
    if args.report is None:
        argp.error("report is required unless --self-test is used")
    errors = validate_text(args.report.read_text(encoding="utf-8"))
    if errors:
        print(json.dumps({"status": "FAIL", "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"status": "PASS", "report": str(args.report)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
