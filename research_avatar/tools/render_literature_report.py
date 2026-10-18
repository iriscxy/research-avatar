#!/usr/bin/env python3
"""Render a literature survey atomically from one structured evidence model."""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
import tempfile
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research_avatar.tools.validate_literature_report import validate as validate_evidence
from research_avatar.tools.validate_report_structure import validate as validate_structure


DEFAULT_STYLE = """
:root{--ink:#18201d;--muted:#5e6a64;--paper:#f6fefa;--card:#fffefa;--line:#d8d5cb;--accent:#047857;--accent2:#c65d32;--soft:#ecfdf5}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.65 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
header,main,footer{max-width:920px;margin:auto;padding:24px}header{padding-top:40px}h1{margin:0 0 4px;font:700 1.7rem/1.2 Georgia,serif;color:var(--accent)}
h2{margin:44px 0 12px;padding-bottom:6px;border-bottom:2px solid var(--accent);font:700 1.5rem/1.2 Georgia,serif}.meta,.note,footer{color:var(--muted);font-size:14px}
a{color:var(--accent)}.toc{max-width:920px;margin:auto;padding:10px 24px;border-block:1px solid var(--line)}.toc a{margin-right:20px;color:var(--muted);font-weight:700;text-decoration:none}
details{margin:8px 0;border:1px solid var(--line);border-radius:10px;background:var(--card)}details>summary{padding:10px 14px;cursor:pointer;font-weight:700;color:var(--accent)}details[open]>summary{border-bottom:1px solid var(--line)}
details details{margin:8px 14px}details details>summary{font-weight:600;color:var(--ink)}details details>summary::marker{color:var(--accent2)}.body{padding:6px 14px 12px}.count{color:var(--accent2);font-weight:700}
ul{margin:6px 0;padding-left:22px}li{margin:6px 0}li::marker{color:var(--accent2)}.paper-meta{color:var(--muted);font-size:14px}footer{border-top:1px solid var(--line);margin-top:40px}
"""


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def problem_paragraph(model: dict) -> str:
    """Return the Problem stage as one plain paragraph."""
    problem = model["problem"]
    if isinstance(problem, str):
        return problem
    if problem.get("paragraph"):
        return str(problem["paragraph"])
    parts = [problem.get("lead", ""), *problem.get("paragraphs", []), problem.get("callout", "")]
    return " ".join(str(part).strip() for part in parts if str(part).strip())


def venue_year(paper: dict) -> str:
    venue, year = str(paper["venue"]), str(paper["year"])
    return esc(venue if year in venue else f"{venue} {year}")


def paper_item(paper: dict, family_id: str, subfamily_id: str) -> str:
    preprint = (
        f' · <a href="{esc(paper["arxiv_url"])}">arXiv</a>'
        if paper.get("arxiv_url") and paper["arxiv_url"] != paper["url"] else ""
    )
    return (
        f'<li id="paper-{esc(paper["id"])}" data-paper-id="{esc(paper["id"])}" '
        f'data-family-id="{esc(family_id)}" data-subfamily-id="{esc(subfamily_id)}">'
        f'<a href="{esc(paper["url"])}">{esc(paper["title"])}</a> '
        f'<span class="paper-meta">({venue_year(paper)}{preprint})</span>'
        f' — {esc(paper["takeaway"])}</li>'
    )


def groups(item: dict, member_key: str = "subfamilies") -> list[dict]:
    """Return the nested categories of a family or regime, or one implicit group."""
    nested = item.get(member_key) or item.get("subregimes")
    if nested:
        return nested
    return [{"id": f'{item.get("id", "group")}-all', "title": item["title"], "description": "", "paper_ids": item["paper_ids"]}]


def evidence_lanes(model: dict) -> list[dict]:
    """Derive evidence maturity from verified year/status records."""
    search_year = int(str(model["search_date"])[:4])
    lanes = [
        {"id": "established", "title": "Established peer-reviewed evidence", "paper_ids": []},
        {"id": "current-reviewed", "title": "Current peer-reviewed evidence", "paper_ids": []},
        {"id": "frontier-preprints", "title": "Frontier preprints", "paper_ids": []},
    ]
    by_id = {item["id"]: item for item in lanes}
    for paper in model["papers"]:
        if paper["publication_status"] == "preprint":
            lane = "frontier-preprints"
        elif int(paper["year"]) >= search_year - 1:
            lane = "current-reviewed"
        else:
            lane = "established"
        by_id[lane]["paper_ids"].append(str(paper["id"]))
    return lanes


def research_questions(model: dict) -> list[dict]:
    """Flatten research directions (or legacy per-gap questions) and optional personalized ones."""
    if model.get("directions"):
        items = [{**item, "question": item["title"], "origin": "neutral"} for item in model["directions"]]
        items += [{**item, "question": item["title"], "origin": "personalized"}
                  for item in model.get("personalized_directions") or []]
        return items
    questions = []
    for gap in model.get("gaps") or []:
        if isinstance(gap, dict):
            for item in gap.get("research_questions") or []:
                questions.append({**item, "origin": "neutral", "gap_id": gap.get("id")})
    for item in model.get("personalized_questions") or []:
        questions.append({**item, "origin": "personalized"})
    return questions


def question_items(items: list[dict], origin: str) -> str:
    return "".join(
        f'<li data-question-id="{esc(item["id"])}" data-question-origin="{origin}">'
        f'<b>{esc(item["id"])}</b> {esc(item["question"])}'
        + (f' <span class="paper-meta">({esc(item["gap_id"])} · {esc(item["anchor"])})</span>' if origin == "personalized" else "")
        + "</li>"
        for item in items
    )


def render(model: dict, style: str = DEFAULT_STYLE) -> str:
    papers = {str(item["id"]): item for item in model["papers"]}
    families = model["families"]
    contract = {
        key: value for key, value in model.items()
        if key in {"topic", "search_date", "coverage_years", "sources", "papers", "families", "search_angles", "gap_falsification", "verification_notes"}
    }
    contract["paper_count"] = len(papers)
    contract["family_count"] = len(families)
    contract["evidence_lanes"] = evidence_lanes(model)
    contract["research_questions"] = research_questions(model)
    contract["gap_falsification"] = {
        **model["gap_falsification"],
        "per_gap": [
            {"gap_id": gap["id"], "closest_collision_id": gap["closest_work"]["paper_id"],
             "bounded_difference": gap["closest_work"]["difference"]}
            for gap in model.get("gaps") or [] if isinstance(gap, dict) and gap.get("closest_work")
        ],
    }
    family_html = []
    for family in families:
        subs = []
        for sub in groups(family):
            items = "".join(paper_item(papers[pid], family["id"], sub["id"]) for pid in sub["paper_ids"])
            desc = f'<p>{esc(sub["description"])}</p>' if sub.get("description") else ""
            subs.append(
                f'<details><summary>{esc(sub["title"])} <span class="count">({len(sub["paper_ids"])})</span></summary>'
                f'<div class="body">{desc}<ul>{items}</ul></div></details>'
            )
        family_html.append(
            f'<details data-family-id="{esc(family["id"])}"><summary>{esc(family["title"])} '
            f'<span class="count">({len(family["paper_ids"])})</span></summary><div class="body">'
            f'<p>{esc(family["inclusion_rule"])} {esc(family["comparison"])}</p>'
            f'<p data-failure-boundary="{esc(family["id"])}"><b>Likely failure boundary:</b> '
            f'{esc(family["failure_boundary"])}</p>{"".join(subs)}</div></details>'
        )
    lane_html = "".join(
        f'<li data-evidence-lane="{esc(lane["id"])}">{esc(lane["title"])}: {len(lane["paper_ids"])} papers</li>'
        for lane in contract["evidence_lanes"]
    )
    regime_html = []
    for regime in model["evaluation_regimes"]:
        subs = []
        for sub in groups(regime, "subregimes"):
            links = "".join(
                f'<li><a href="{esc(papers[pid]["url"])}">{esc(papers[pid]["title"])}</a> '
                f'<span class="paper-meta">({venue_year(papers[pid])})</span></li>'
                for pid in sub["paper_ids"]
            )
            desc = f'<p>{esc(sub["description"])}</p>' if sub.get("description") else ""
            subs.append(
                f'<details><summary>{esc(sub["title"])} <span class="count">({len(sub["paper_ids"])})</span></summary>'
                f'<div class="body">{desc}<ul>{links}</ul></div></details>'
            )
        count = len({pid for sub in groups(regime, "subregimes") for pid in sub["paper_ids"]})
        regime_html.append(
            f'<details><summary>{esc(regime["title"])} <span class="count">({count})</span></summary>'
            f'<div class="body"><p>{esc(regime["description"])}</p>{"".join(subs)}</div></details>'
        )
    gap_items = []
    question_of_gap = {}
    for item in model.get("directions") or []:
        gap_items.append(
            f'<li data-question-id="{esc(item["id"])}" data-question-origin="neutral">'
            f'<b>{esc(item["id"])}</b> {esc(item["title"])}</li>'
        )
    if model.get("personalized_directions"):
        gap_items.append("<li>Directions linked to your own work<ul>" + "".join(
            f'<li data-question-id="{esc(item["id"])}" data-question-origin="personalized">'
            f'<b>{esc(item["id"])}</b> {esc(item["title"])} '
            f'<span class="paper-meta">({esc(item["anchor"])})</span></li>'
            for item in model["personalized_directions"]) + "</ul></li>")
    for gap in [] if model.get("directions") else (model.get("gaps") or model["openings"]):
        if isinstance(gap, dict):
            question = gap["research_questions"][0]
            question_of_gap[str(gap["id"])] = question["id"]
            gap_items.append(
                f'<li data-gap-id="{esc(gap["id"])}" data-question-id="{esc(question["id"])}" data-question-origin="neutral">'
                f'<b>{esc(question["id"])}</b> {esc(question["question"])}</li>'
            )
        else:
            gap_items.append(f"<li>{esc(gap)}</li>")
    personalized = model.get("personalized_questions") or []
    if personalized:
        linked = [{**item, "gap_id": question_of_gap.get(str(item["gap_id"]), item["gap_id"])} for item in personalized]
        gap_items.append(
            f'<li>Questions linked to your own work<ul>{question_items(linked, "personalized")}</ul></li>'
        )
    gaps = "".join(gap_items)
    payload = json.dumps(contract, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(model["title"])}</title><style>{style}</style></head><body>
<header><h1>{esc(model["title"])}</h1><p class="meta">{esc(model["search_date"])} · {esc(model["coverage_years"])} · {len(papers)} verified papers · {len(model["search_angles"])} search angles</p></header>
<nav class="toc"><a href="#problem">Problem</a><a href="#approaches">Approaches</a><a href="#evaluation">Evaluation</a><a href="#gaps">Research Questions</a></nav><main>
<section id="problem" data-report-section="problem"><h2>1. Problem</h2><p>{esc(problem_paragraph(model))}</p></section>
<section id="approaches" data-report-section="approaches"><h2>2. Approaches</h2><p>{len(families)} families, each split into finer categories. Click a family to expand.</p><ul>{lane_html}</ul>{"".join(family_html)}</section>
<section id="evaluation" data-report-section="evaluation"><h2>3. Evaluation</h2><p>{esc(model["evaluation_lead"])}</p>{"".join(regime_html)}<p class="note">All links and publication metadata were reopened against the recorded official venue, DOI, or arXiv page on {esc(model["search_date"])}.</p></section>
<section id="gaps" data-report-section="gaps"><h2>4. Research Questions</h2><ul>{gaps}</ul></section>
<script type="application/json" id="literature-verification">{payload}</script></main><footer>Generated by Research Avatar from one verified record set. Verify the original sources before citing.</footer></body></html>'''


def check_model(model: dict) -> list[str]:
    """Enforce the plain Problem / grouped Approaches / grouped Evaluation / bullet Gaps shape."""
    errors: list[str] = []
    if "\n" in problem_paragraph(model).strip():
        errors.append("problem must be a single paragraph")
    for kind, items, key in (("family", model["families"], "subfamilies"), ("regime", model["evaluation_regimes"], "subregimes")):
        for item in items:
            subs = item.get(key) or []
            if not 2 <= len(subs) <= 5:
                errors.append(f"{kind} {item.get('id') or item.get('title')} needs 2 to 5 {key}")
                continue
            members = [str(pid) for sub in subs for pid in sub["paper_ids"]]
            if sorted(members) != sorted(str(pid) for pid in item["paper_ids"]):
                errors.append(f"{kind} {item.get('id') or item.get('title')} {key} must cover each of its papers exactly once")
    if model.get("directions"):
        return errors + check_directions(model)
    points = model.get("gaps") or []
    if not 3 <= len(points) <= 5:
        errors.append("gaps must list 3 to 5 research questions")
    gap_ids = set()
    for index, gap in enumerate(points):
        if not isinstance(gap, dict) or not {"id", "text", "research_questions"} <= set(gap) \
                or not set(gap) <= {"id", "text", "research_questions", "closest_work"}:
            errors.append(f"gaps[{index}] needs id, text, and research_questions (closest_work is optional)")
            continue
        closest = gap.get("closest_work")
        if closest is not None and (
                not isinstance(closest, dict) or set(closest) != {"paper_id", "difference"}
                or str(closest.get("paper_id")) not in {str(p["id"]) for p in model["papers"]}
                or not str(closest.get("difference", "")).strip()):
            errors.append(f"gap {gap['id']} closest_work needs a known paper_id and a difference")
            continue
        gap_ids.add(str(gap["id"]))
        if len(gap["research_questions"] or []) != 1:
            errors.append(f"gap {gap['id']} needs exactly one research question")
    neutral = [q for q in research_questions(model) if q["origin"] == "neutral"]
    if not 3 <= len(neutral) <= 5:
        errors.append("the survey must list 3 to 5 neutral research questions in total")
    personalized = model.get("personalized_questions") or []
    if personalized and not 2 <= len(personalized) <= 4:
        errors.append("personalized_questions must list 2 to 4 questions when present")
    for item in personalized:
        if str(item.get("gap_id")) not in gap_ids or not str(item.get("anchor", "")).strip():
            errors.append(f"personalized question {item.get('id')} needs an existing gap_id and an anchor in the researcher's work")
    ids = [str(q.get("id", "")) for q in research_questions(model)]
    if any(not i for i in ids) or len(ids) != len(set(ids)):
        errors.append("research question IDs must be unique and non-empty")
    for q in research_questions(model):
        if not str(q.get("question", "")).strip().endswith("?"):
            errors.append(f"research question {q.get('id')} must be a single question ending with '?'")
    return errors


def check_directions(model: dict) -> list[str]:
    """Research directions: 3-5 short keyword titles and nothing else."""
    errors = []
    directions = model["directions"]
    if not 3 <= len(directions) <= 5:
        errors.append("directions must list 3 to 5 research directions")
    personalized = model.get("personalized_directions") or []
    if personalized and not 2 <= len(personalized) <= 4:
        errors.append("personalized_directions must list 2 to 4 directions when present")
    for item in directions + personalized:
        allowed = {"id", "title"} | ({"anchor"} if item in personalized else set())
        if not isinstance(item, dict) or set(item) != allowed:
            errors.append(f"direction {item.get('id') if isinstance(item, dict) else item} needs exactly {sorted(allowed)}")
            continue
        title = str(item["title"]).strip()
        if not title or len(title.split()) > 6 or title.endswith(("?", ".")):
            errors.append(f"direction {item['id']} title must be a short keyword phrase of at most six words")
    ids = [str(item.get("id", "")) for item in directions + personalized if isinstance(item, dict)]
    if any(not i for i in ids) or len(ids) != len(set(ids)):
        errors.append("research direction IDs must be unique and non-empty")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    model = json.loads(args.source.read_text(encoding="utf-8"))
    problems = check_model(model)
    if problems:
        raise SystemExit("\n".join(f"ERROR: {problem}" for problem in problems))
    result = render(model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".html", dir=args.output.parent, delete=False) as handle:
        handle.write(result)
        temporary = Path(handle.name)
    errors = validate_evidence(result) + validate_structure("literature", temporary)
    if errors:
        temporary.unlink(missing_ok=True)
        raise SystemExit("\n".join(f"ERROR: {error}" for error in errors))
    os.replace(temporary, args.output)
    print(f"Rendered {len(model['papers'])} papers and {len(model['families'])} families to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
