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

from bs4 import BeautifulSoup

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research_avatar.tools.validate_literature_report import validate as validate_evidence
from research_avatar.tools.validate_report_structure import validate as validate_structure


DEFAULT_STYLE = """
:root{--bg:#fff;--ink:#17323e;--muted:#60757d;--line:#dbe7e4;--teal:#087f70;--soft:#edf8f5;--gold:#a36b12}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#fff;color:var(--ink);font:15px/1.65 Inter,system-ui,sans-serif}
header,main,footer{max-width:1180px;margin:auto;padding:30px}.hero{padding-top:58px}.kicker,.tag{color:var(--teal);font-size:12px;font-weight:850;letter-spacing:.08em;text-transform:uppercase}
h1{max-width:900px;margin:8px 0;font:750 48px/1.08 Georgia,serif;background:linear-gradient(90deg,#17323e,#087f70);color:transparent;background-clip:text}
h2{margin:52px 0 16px;font:700 31px/1.2 Georgia,serif}h3{margin:28px 0 8px}.subtitle,.who,.note,footer{color:var(--muted)}
.meta,.flow{display:flex;flex-wrap:wrap;gap:9px;margin-top:18px}.meta span,.flow span{padding:7px 11px;border:1px solid var(--line);border-radius:999px;background:#fff}.flow b{align-self:center;color:var(--teal)}
.toc{position:sticky;top:0;z-index:5;display:flex;gap:24px;padding:13px 30px;border-block:1px solid var(--line);background:#fffffff2;backdrop-filter:blur(8px)}.toc a{color:var(--ink);font-weight:750;text-decoration:none}
.lead,.callout{padding:18px 21px;border-left:4px solid var(--teal);background:var(--soft);border-radius:4px}.callout.debate{border-color:var(--gold);background:#fff8e8}.callout.gap{border-color:#7b55aa;background:#f7f2fc}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:14px}.card{padding:17px;border:1px solid var(--line);border-radius:12px;background:#fff;box-shadow:0 5px 18px #17323e0a}.card h4{margin:7px 0}.card a{color:#075f73}.verified{float:right;color:var(--teal);font-size:12px;font-weight:800}.who{font-size:12px}.card p{margin-bottom:0}
table{width:100%;border-collapse:collapse;margin:16px 0;font-size:13px}th,td{padding:10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{background:#f5f9f8}.trend li{margin:9px 0}.regime{padding:14px 0;border-bottom:1px solid var(--line)}
footer{border-top:1px solid var(--line);margin-top:50px}@media(max-width:700px){h1{font-size:36px}.toc{overflow:auto}header,main,footer{padding:22px}}
"""


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def paragraphs(items: list[str]) -> str:
    return "".join(f"<p>{esc(item)}</p>" for item in items)


def existing_style(path: Path) -> str:
    if path.is_file():
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        style = soup.find("style")
        if style and style.get_text(strip=True):
            return style.get_text()
    return DEFAULT_STYLE


def paper_card(paper: dict, family_id: str) -> str:
    authors = "; ".join(str(value) for value in paper["authors"])
    doi = f" · DOI {esc(paper['doi'])}" if paper.get("doi") else ""
    preprint = (
        f' · <a href="{esc(paper["arxiv_url"])}">preprint</a>'
        if paper.get("arxiv_url") and paper["arxiv_url"] != paper["url"] else ""
    )
    return (
        f'<article class="card" id="paper-{esc(paper["id"])}" '
        f'data-paper-id="{esc(paper["id"])}" data-family-id="{esc(family_id)}">'
        f'<span class="tag">{esc(paper["publication_status"])}</span>'
        '<span class="verified">Verified</span>'
        f'<h4><a href="{esc(paper["url"])}">{esc(paper["title"])}</a></h4>'
        f'<div class="who">{esc(authors)} · {esc(paper["venue"])} · {esc(paper["year"])}{doi}{preprint}</div>'
        f'<p>{esc(paper["takeaway"])}</p></article>'
    )


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


def render(model: dict, style: str) -> str:
    papers = {str(item["id"]): item for item in model["papers"]}
    families = model["families"]
    contract = {
        key: value for key, value in model.items()
        if key in {"topic", "search_date", "coverage_years", "sources", "papers", "families", "search_angles", "gap_falsification", "verification_notes"}
    }
    contract["paper_count"] = len(papers)
    contract["family_count"] = len(families)
    contract["evidence_lanes"] = evidence_lanes(model)
    family_html = []
    for family in families:
        cards = "".join(paper_card(papers[paper_id], family["id"]) for paper_id in family["paper_ids"])
        family_html.append(
            f'<section data-family-id="{esc(family["id"])}"><h3>{esc(family["title"])}</h3>'
            f'<p><b>Inclusion rule:</b> {esc(family["inclusion_rule"])}</p>'
            f'<p>{esc(family["comparison"])}</p>'
            f'<p class="callout" data-failure-boundary="{esc(family["id"])}"><b>Likely failure boundary:</b> '
            f'{esc(family["failure_boundary"])}</p><div class="grid">{cards}</div></section>'
        )
    lane_html = "".join(
        f'<article class="card" data-evidence-lane="{esc(lane["id"])}"><h3>{esc(lane["title"])}</h3>'
        f'<p><b>{len(lane["paper_ids"])} works.</b> '
        + ", ".join(f'<a href="#paper-{esc(pid)}">{esc(papers[pid]["title"])}</a>' for pid in lane["paper_ids"])
        + "</p></article>"
        for lane in contract["evidence_lanes"]
    )
    regimes = "".join(
        f'<article class="regime"><h3>{esc(item["title"])}</h3><p>{esc(item["description"])}</p>'
        f'<p><b>Representative evidence:</b> '
        + ", ".join(f'<a href="#paper-{esc(pid)}">{esc(papers[pid]["title"])}</a>' for pid in item["paper_ids"])
        + "</p></article>"
        for item in model["evaluation_regimes"]
    )
    rows = "".join(
        f'<tr><td><a href="{esc(p["url"])}">{esc(p["title"])}</a></td><td>{esc(p["primary_family"])}</td>'
        f'<td>{esc(p["takeaway"])}</td><td>{esc(p["year"])}</td><td>{esc(p["publication_status"])}</td></tr>'
        for p in papers.values()
    )
    debates = "".join(
        f'<div class="callout debate"><b>{esc(item["title"])}</b><p>{esc(item["text"])}</p></div>'
        for item in model["debates"]
    )
    trends = "".join(f"<li>{esc(item)}</li>" for item in model["trends"])
    openings = "".join(f"<li>{esc(item)}</li>" for item in model["openings"])
    flow = '<div class="flow">' + "<b>→</b>".join(f"<span>{esc(item)}</span>" for item in model["taxonomy"]) + "</div>"
    payload = json.dumps(contract, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(model["title"])}</title><style>{style}</style></head><body>
<header class="hero"><div class="kicker">Research Literature Survey</div><h1>{esc(model["title"])}</h1><p class="subtitle">{esc(model["subtitle"])}</p><div class="meta"><span>{esc(model["search_date"])}</span><span>{esc(model["coverage_years"])}</span><span>{len(papers)} verified papers</span><span>{len(model["search_angles"])} search angles</span></div></header>
<nav class="toc"><a href="#problem">Problem</a><a href="#approaches">Approaches</a><a href="#evaluation">Evaluation</a><a href="#gaps">Gaps</a></nav><main>
<section id="problem" data-report-section="problem"><h2>1. Problem</h2><div class="lead">{esc(model["problem"]["lead"])}</div>{paragraphs(model["problem"]["paragraphs"])}{flow}<div class="callout">{esc(model["problem"]["callout"])}</div></section>
<section id="approaches" data-report-section="approaches"><h2>2. Approaches</h2><p class="lead">The verified record set is organized into {len(families)} decision-relevant families; each family is defined by the operation it controls.</p><h3>Evidence maturity</h3><p>Established and current peer-reviewed evidence are separated from current frontier preprints so publication maturity is not mistaken for recency.</p><div class="grid">{lane_html}</div>{''.join(family_html)}</section>
<section id="evaluation" data-report-section="evaluation"><h2>3. Evaluation</h2><p class="lead">{esc(model["evaluation_lead"])}</p>{regimes}<h3>Landscape</h3><table><thead><tr><th>Work</th><th>Category</th><th>Core evidence</th><th>Year</th><th>Verification</th></tr></thead><tbody>{rows}</tbody></table><p class="note">All links and publication metadata were reopened against the recorded official venue, DOI, or arXiv page on {esc(model["search_date"])}.</p></section>
<section id="gaps" data-report-section="gaps"><h2>4. Gaps</h2><p class="lead">{esc(model["gaps_lead"])}</p>{debates}<h3>Recent trends</h3><ul class="trend">{trends}</ul><div class="callout gap"><b>Bounded research openings</b><ul>{openings}</ul></div><p><b>Closest collision:</b> <a href="#paper-{esc(model["gap_falsification"]["closest_collision_id"])}">{esc(papers[model["gap_falsification"]["closest_collision_id"]]["title"])}</a>. {esc(model["gap_falsification"]["bounded_difference"])}</p></section>
<script type="application/json" id="literature-verification">{payload}</script></main><footer>Generated by Research Avatar from one verified record set. Verify the original sources before citing.</footer></body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    model = json.loads(args.source.read_text(encoding="utf-8"))
    result = render(model, existing_style(args.output))
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
