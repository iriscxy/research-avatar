#!/usr/bin/env python3
"""Render an Idea Selection report from one structured decision model."""

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

from research_avatar.tools.validate_ideagen_report import validate as validate_ideas
from research_avatar.tools.validate_report_structure import validate as validate_structure


STYLE = """
:root{--ink:#17323e;--muted:#667b83;--line:#dce8e5;--teal:#087f70;--soft:#eef8f5;--amber:#9a6511;--red:#9a3e3e}
*{box-sizing:border-box}body{margin:0;background:#fff;color:var(--ink);font:15px/1.65 Inter,system-ui,sans-serif}header,main,footer{max-width:1180px;margin:auto;padding:30px}
header{padding-top:54px}h1{margin:.2em 0;font:750 46px/1.1 Georgia,serif}h2{margin-top:52px;font:700 30px/1.2 Georgia,serif}h3{margin-bottom:7px}.kicker,.eyebrow{color:var(--teal);font-size:12px;font-weight:850;letter-spacing:.09em;text-transform:uppercase}.sub,.note,footer{color:var(--muted)}
.toc{position:sticky;top:0;z-index:3;display:flex;gap:24px;padding:13px 30px;border-block:1px solid var(--line);background:#fffffff2}.toc a,a{color:#075f73}.lead,.callout{padding:17px 20px;border-left:4px solid var(--teal);background:var(--soft);border-radius:5px}.warning{border-color:var(--amber);background:#fff8e8}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:16px}.card{border:1px solid var(--line);border-radius:12px;padding:19px;box-shadow:0 5px 18px #17323e0b}.card dl{display:grid;grid-template-columns:130px 1fr;gap:7px 12px}.card dt{font-weight:800}.card dd{margin:0}.badge{display:inline-block;padding:4px 9px;border-radius:999px;background:var(--soft);color:var(--teal);font-weight:800;font-size:12px}.blocked{background:#fff1f1;color:var(--red)}
table{width:100%;border-collapse:collapse;margin:17px 0;font-size:13px}th,td{padding:10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{background:#f4f8f7}.pick{padding:18px;border:1px solid var(--line);border-radius:10px;margin:10px 0}footer{border-top:1px solid var(--line);margin-top:50px}@media(max-width:700px){header,main,footer{padding:20px}h1{font-size:35px}.toc{overflow:auto}.card dl{grid-template-columns:1fr}}
"""


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def links(items: list[dict]) -> str:
    return ", ".join(f'<a href="{esc(item["url"])}">{esc(item["title"])}</a>' for item in items)


def card(candidate: dict, selected_id: str = "") -> str:
    selectable = candidate["selectable"]
    attrs = ""
    if selectable:
        attrs = (
            f' data-idea-id="{esc(candidate["id"])}" data-novelty-status="{esc(candidate["novelty_attribute"])}"'
            f' data-idea-tier="{esc(candidate["tier"])}" data-default-pick="false"'
            f' data-scope-necessity="{esc(candidate["scope_necessity"])}"'
            f' data-scope-action="{esc(candidate["scope_action"])}"'
        )
    if candidate["id"] == selected_id:
        attrs += ' data-selected="true"'
    steps = "".join(f"<li>{esc(step)}</li>" for step in candidate["steps"])
    status_class = "badge" if selectable else "badge blocked"
    selected_badge = '<span class="badge">Selected</span> ' if candidate["id"] == selected_id else ""
    grounding = "".join(
        f'<li><a href="01_LIT_SURVEY.html#{esc(item["anchor"])}">{esc(item["kind"])}: '
        f'{esc(item["title"])}</a> — {esc(item["failure_boundary"])}</li>'
        for item in candidate["source_grounding"]
    )
    return f'''<article class="card"{attrs}><div class="eyebrow">{esc(candidate["id"])} · {esc(candidate["contribution_type"])}</div>
<h3>{esc(candidate["title"])}</h3><span class="{status_class}">{esc(candidate["novelty_status"])}</span>
{selected_badge}
<p><b>Plain-language summary.</b> {esc(candidate["summary"])}</p>
<p><b>One mechanism.</b> {esc(candidate["mechanism"])}</p><ol>{steps}</ol>
<p><b>Survey origin and failure boundary.</b></p><ul>{grounding}</ul>
<dl><dt>Hypothesis</dt><dd>{esc(candidate["hypothesis"])}</dd><dt>Falsifier</dt><dd>{esc(candidate["falsifier"])}</dd>
<dt>Closest work</dt><dd>{links(candidate["closest_sources"])}</dd><dt>Concrete difference</dt><dd>{esc(candidate["difference"])}</dd>
<dt>Own-work overlap</dt><dd>{esc(candidate["own_work_overlap"])}</dd><dt>Scope necessity</dt><dd>{esc(candidate["scope_text"])}</dd>
<dt>Feasibility</dt><dd>{esc(candidate["feasibility"])}</dd><dt>Reviewer risk</dt><dd>{esc(candidate["reviewer_risk"])}</dd>
<dt>Devil's advocate</dt><dd>{esc(candidate["objection"])}</dd><dt>Effort</dt><dd>{esc(candidate["effort"])}</dd></dl></article>'''


def render(model: dict) -> str:
    rows = "".join(
        f'<tr><td>{esc(c["id"])}</td><td>{esc(c["tier"])}</td><td>{esc(c["summary"])}</td>'
        f'<td>{esc(c["novelty_status"])}</td><td>{esc(c["scope_necessity"])}</td>'
        f'<td>{esc(c["closest_sources"][0]["title"])}</td><td>{esc(c["difference"])}</td>'
        f'<td>{esc(c["objection"])}</td><td>{esc(c["confidence"])}</td></tr>'
        for c in model["candidates"]
    )
    selection = model.get("selection") or {}
    selected_id = str(selection.get("selected_id", ""))
    cards = "".join(card(candidate, selected_id) for candidate in model["candidates"])
    picks = "".join(
        f'<div class="pick"><b>{esc(c["id"])} — {esc(c["title"])}</b><p>{esc(c["summary"])}</p></div>'
        for c in model["candidates"] if c["selectable"]
    )
    audit = {"grounding_contract_version": 1, "candidates": [
        {**c["audit"], "source_grounding": c["source_grounding"]}
        for c in model["candidates"] if c["selectable"]
    ]}
    audit_json = json.dumps(audit, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    selection_json = json.dumps(selection, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    selection_banner = ""
    if selected_id:
        selected = next((c for c in model["candidates"] if c["id"] == selected_id), None)
        if selected:
            selection_banner = (
                f'<div class="lead" data-selected-idea="{esc(selected_id)}"><b>Selected: '
                f'{esc(selected_id)} — {esc(selected["title"])}</b><p>{esc(selection.get("reason", ""))}</p></div>'
            )
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(model["title"])}</title><style>{STYLE}</style></head><body>
<header><div class="kicker">Research Idea Selection · Benchmark Lens</div><h1>{esc(model["title"])}</h1><p class="sub">{esc(model["subtitle"])}</p></header>
<nav class="toc"><a href="#literature-landscape">Landscape</a><a href="#ranked-slate">Decision slate</a><a href="#candidate-cards">Candidate cards</a><a href="#human-selection">Selection</a></nav>
<main data-idea-branch="standard" data-disruptive-wildcard="off">
<section id="literature-landscape" data-report-section="literature-landscape"><h2>1. Literature Landscape</h2><div class="lead">{esc(model["landscape_lead"])}</div><p>{esc(model["landscape_body"])}</p><p>See the <a href="01_LIT_SURVEY.html">complete verified literature survey</a> and its search audit; the survey page derives its displayed count from the verified record set.</p></section>
<section id="ranked-slate" data-report-section="ranked-slate"><h2>2. Ranked Decision Slate</h2><div class="callout warning"><b>No high-confidence novel recommendation.</b><p>{esc(model["ranking_note"])}</p></div><table><thead><tr><th>ID</th><th>Tier</th><th>Idea</th><th>Novelty</th><th>Scope</th><th>Closest work</th><th>Difference</th><th>Strongest objection</th><th>Confidence</th></tr></thead><tbody>{rows}</tbody></table></section>
<section id="candidate-cards" data-report-section="candidate-cards"><h2>3. Candidate Cards</h2><p class="lead">Each card separates technical feasibility from novelty and reviewer risk. Dataset plans marked self-built have no fabricated publication link.</p><div class="cards">{cards}</div></section>
<section id="human-selection" data-report-section="human-selection"><h2>4. Human Selection</h2>{selection_banner}<p class="lead">Choose one Tier B candidate only if you accept a framing-sensitive contribution. The two blocked candidates remain visible because their collisions are useful negative evidence.</p>{picks}</section>
<script id="idea-novelty-audit" type="application/json">{audit_json}</script><script id="idea-selection" type="application/json">{selection_json}</script></main><footer>Generated from the verified profile, literature survey, and candidate-level collision searches. Recheck concurrent work before submission.</footer></body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    model = json.loads(args.source.read_text(encoding="utf-8"))
    result = render(model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".html", dir=args.output.parent, delete=False) as handle:
        handle.write(result)
        temporary = Path(handle.name)
    errors = validate_ideas(result) + validate_structure("ideas", temporary)
    if errors:
        temporary.unlink(missing_ok=True)
        raise SystemExit("\n".join(f"ERROR: {error}" for error in errors))
    os.replace(temporary, args.output)
    print(f"Rendered {len(model['candidates'])} candidates to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
