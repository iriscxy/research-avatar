#!/usr/bin/env python3
"""Render an Idea Selection report from one structured decision model."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import tempfile
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research_avatar.tools.validate_ideagen_report import validate as validate_ideas
from research_avatar.tools.validate_report_structure import validate as validate_structure


STYLE = """
:root{--ink:#18201d;--muted:#5e6a64;--paper:#fffdf5;--card:#fffefa;--line:#d8d5cb;--accent:#b45309;--accent2:#c65d32;--soft:#fffbeb;--warn:#fff4e5}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.65 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
header,main,footer{max-width:1100px;margin:auto;padding:24px max(4vw,24px)}header{padding-top:36px}h1{margin:0 0 4px;font:700 1.7rem/1.2 Georgia,serif;color:var(--accent)}.sub,.note,footer{color:var(--muted);font-size:.9rem}
h2{margin:44px 0 12px;padding-bottom:6px;border-bottom:2px solid var(--accent);font:700 1.5rem/1.2 Georgia,serif}a{color:var(--accent)}
.toc{display:flex;gap:18px;padding:12px max(4vw,24px) 12px calc(max(0px,(100vw - 1100px)/2) + max(4vw,24px));border-block:1px solid var(--line)}.toc a{color:var(--muted);font-weight:700;font-size:.85rem;text-decoration:none}
.lead,.callout{padding:12px 16px;border-left:4px solid var(--accent);background:var(--soft);border-radius:5px}.warning{border-color:var(--accent2);background:var(--warn)}
.cards{display:grid;grid-template-columns:1fr;gap:12px}.card{border:1px solid var(--line);border-radius:10px;background:var(--card);padding:0}.card-details>summary{cursor:pointer;list-style:none;position:relative;padding:14px 40px 14px 18px}.card-details>summary::-webkit-details-marker{display:none}
.card-details>summary::after{content:'\\25B8';position:absolute;right:16px;top:14px;color:var(--accent2);font-size:18px;transition:transform .15s}.card-details[open]>summary::after{transform:rotate(90deg)}
.card h3{margin:.2em 0 .4em;color:var(--accent)}.eyebrow{color:var(--accent2);font-size:.78rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase}.badge{display:inline-block;margin-right:6px;padding:2px 9px;border-radius:999px;background:var(--soft);color:var(--accent);font-weight:700;font-size:.78rem}.blocked{background:#fbe9e4;color:#9a3e3e}
.card-body{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.15fr);column-gap:30px;margin:0 18px;padding:12px 0 16px;border-top:1px solid var(--line)}.card-body>.col{grid-column:1}.card-body>dl{grid-column:2;grid-row:1/span 6;margin:0;align-self:start}
.card dl{display:grid;grid-template-columns:130px 1fr;gap:7px 14px}.card dt{font-weight:700;color:var(--muted)}.card dd{margin:0}
table{width:100%;table-layout:auto;border-collapse:collapse;margin:14px 0;font-size:.82rem;line-height:1.45;background:var(--card)}td{overflow-wrap:break-word;hyphens:manual}table.slate th:nth-child(-n+2),table.slate td:nth-child(-n+2),table.slate th:last-child,table.slate td:last-child{white-space:nowrap}table.slate th,table.slate td{padding:9px 6px}table.slate th{font-size:.76rem}table.slate th:nth-child(3){width:21%}table.slate th:nth-child(5){width:15%}table.slate th:nth-child(6),table.slate th:nth-child(7){width:22%}th,td{padding:10px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{background:var(--soft)}
.pick{padding:12px 16px;border:1px solid var(--line);border-radius:10px;margin:10px 0;background:var(--card)}footer{border-top:1px solid var(--line);margin-top:40px}
@media(max-width:900px){.card-body{display:block}.card-body>dl{margin-top:12px}}
"""




def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def links(items: list[dict]) -> str:
    return ", ".join(f'<a href="{esc(item["url"])}">{esc(item["title"])}</a>' for item in items)


def card(candidate: dict, selected_id: str = "") -> str:
    """One idea as the four fields its isolated context generated, verbatim and unfolded."""
    attrs = ""
    if candidate["selectable"]:
        attrs = (
            f' data-idea-id="{esc(candidate["id"])}" data-novelty-status="{esc(candidate["novelty_attribute"])}"'
            f' data-idea-tier="{esc(candidate["tier"])}" data-default-pick="false"'
            f' data-scope-necessity="{esc(candidate["scope_necessity"])}"'
            f' data-scope-action="{esc(candidate["scope_action"])}"'
        )
    if candidate["id"] == selected_id:
        attrs += ' data-selected="true"'
    output = candidate["generation"]["output"]
    question = candidate.get("research_question")
    question_html = (
        f'<p data-candidate-question="true"><b>Sub-question.</b> {esc(question["question"])}</p>' if question else ""
    )
    return (
        f'<article class="card" id="idea-{esc(candidate["id"])}"{attrs}><div class="eyebrow">{esc(candidate["id"])}</div>'
        f'<h3>{esc(output["title"])}</h3>{question_html}'
        f'<p><b>Research focus.</b> {esc(output["research_focus"])}</p>'
        f'<p><b>Method.</b> {esc(output["method"])}</p>'
        f'<p><b>Validation.</b> {esc(output["validation"])}</p></article>'
    )


def question_lead(model: dict) -> str:
    direction = model.get("research_direction")
    if direction:
        return (
            f'<div class="lead" data-research-direction="{esc(direction["id"])}" data-question-origin="{esc(direction["origin"])}" '
            f'data-setting="{esc(model["setting"])}"><b>Research question:</b> {esc(direction["title"])}'
            + (f' · <b>Angle:</b> {esc(model["angle"]["title"])}' if model.get("angle") else "")
            + '</div>'
        )
    question = model["research_question"]
    return (
        f'<div class="lead" data-research-question="{esc(question["id"])}" data-question-origin="{esc(question["origin"])}" '
        f'data-setting="{esc(model["setting"])}"><b>Research question {esc(question["id"])}.</b> {esc(question["question"])}</div>'
    )


def camel_wbr(text: str) -> str:
    return re.sub(r"(?<=[a-z])(?=[A-Z])", "<wbr>", text)


def render(model: dict) -> str:
    rows = "".join(
        f'<tr><td><a href="#idea-{esc(c["id"])}">{esc(c["id"])}</a></td><td>{esc(c["tier"])}</td><td><b>{camel_wbr(esc(c["title"]))}</b><br>{esc(c["summary"])}</td>'
        f'<td>{esc(c["novelty_status"])}</td>'
        f'<td>{links(c["closest_sources"][:1])}</td><td>{esc(c["difference"])}</td>'
        f'<td>{esc(c["objection"])}</td><td>{esc(c["confidence"])}</td></tr>'
        for c in model["candidates"]
    )
    has_tier_a = any(c["tier"] == "A" and c["selectable"] for c in model["candidates"])
    if has_tier_a:
        ranking_callout = f'<div class="callout"><b>Ranking note.</b><p>{esc(model["ranking_note"])}</p></div>'
    else:
        ranking_callout = f'<div class="callout warning"><b>No high-confidence novel recommendation.</b><p>{esc(model["ranking_note"])}</p></div>'
    selection = model.get("selection") or {}
    selected_id = str(selection.get("selected_id", ""))
    cards = "".join(card(candidate, selected_id) for candidate in model["candidates"])
    audit = {"grounding_contract_version": 1, "candidates": [
        {**c["audit"], "source_grounding": c["source_grounding"]}
        for c in model["candidates"] if c["selectable"]
    ]}
    audit_json = json.dumps(audit, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    selection_json = json.dumps(selection, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    generation = {
        **({"research_direction": model["research_direction"]} if model.get("research_direction")
           else {"research_question": model["research_question"]}),
        "setting": model["setting"],
        "candidates": [{"id": c["id"], **c["generation"],
                        **({"research_question": c["research_question"]} if c.get("research_question") else {})}
                       for c in model["candidates"]],
    }
    generation_json = json.dumps(generation, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    selection_banner = '<p data-selection-pending="true">No idea selected yet.</p>'
    if selected_id:
        selected = next((c for c in model["candidates"] if c["id"] == selected_id), None)
        if selected:
            selection_banner = (
                f'<div class="lead" data-selected-idea="{esc(selected_id)}"><b>Selected: '
                f'{esc(selected_id)} — {esc(selected["generation"]["output"]["title"])}</b></div>'
            )
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(model["title"])}</title><style>{STYLE}</style></head><body>
<header><h1>{esc(model["title"])}</h1><p class="sub">{esc(model["subtitle"])}</p></header>
<nav class="toc"><a href="#literature-landscape">Landscape</a><a href="#ranked-slate">Decision slate</a><a href="#candidate-cards">Ideas</a><a href="#human-selection">Selection</a></nav>
<main data-idea-branch="standard" data-disruptive-wildcard="off" data-crowded="{"true" if model.get("crowded") else "false"}">
<section id="literature-landscape" data-report-section="literature-landscape"><h2>1. Literature Landscape</h2>{question_lead(model)}<div class="lead">{esc(model["landscape_lead"])}</div><p>{esc(model["landscape_body"])}</p><p>See the <a href="01_LIT_SURVEY.html">complete verified literature survey</a> and its search audit; the survey page derives its displayed count from the verified record set.</p></section>
<section id="ranked-slate" data-report-section="ranked-slate"><h2>2. Ranked Decision Slate</h2>{ranking_callout}<table class="slate"><thead><tr><th>ID</th><th>Tier</th><th>Idea</th><th>Novelty</th><th>Closest work</th><th>Difference</th><th>Strongest objection</th><th>Confidence</th></tr></thead><tbody>{rows}</tbody></table></section>
<section id="candidate-cards" data-report-section="candidate-cards"><h2>3. Ideas</h2><div class="cards">{cards}</div></section>
<section id="human-selection" data-report-section="human-selection"><h2>4. Human Selection</h2>{selection_banner}</section>
<script id="idea-novelty-audit" type="application/json">{audit_json}</script><script id="idea-selection" type="application/json">{selection_json}</script><script id="idea-generation" type="application/json">{generation_json}</script></main><footer>Generated for one research question and angle from the verified literature survey, with candidate-level collision searches. Recheck concurrent work before submission.</footer></body></html>'''


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
