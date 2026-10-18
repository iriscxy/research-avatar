#!/usr/bin/env python3
"""Render 04_RUN_PLAN.html from a structured model with one fixed template.

Sections, ids, classes, and stylesheet are fixed. A run-planning run fills
content slots only: how many Parts and Goals exist, their wording, and the
embedded run-plan state. Per-goal result panels (``results_html``) are produced
by ``run_plan_progress.py`` from the results ledger and are passed through.
"""

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

from research_avatar.report_theme import with_theme
from research_avatar.tools.validate_report_structure import validate as validate_structure

BASE_STYLE = """
:root{--ink:#17323e;--muted:#62777e;--line:#d9e5e2;--green:#087f70;--soft:#eef8f5;--amber:#9a6511}
*{box-sizing:border-box}body{margin:0;color:var(--ink);font:15px/1.55 Inter,system-ui,sans-serif}header,main{max-width:1180px;margin:auto;padding:28px}header{padding-top:48px}h1{font:750 43px/1.08 Georgia,serif;margin:.2em 0}h2{font:700 29px/1.2 Georgia,serif;margin-top:44px}h3{margin-top:25px}.muted{color:var(--muted)}table{width:100%;border-collapse:collapse;margin:13px 0;font-size:13px}th,td{padding:8px 9px;border:1px solid var(--line);text-align:left;vertical-align:top}th{background:#f2f7f5}.part,.goal,.artifact{border:1px solid var(--line);padding:15px;margin:12px 0;border-radius:9px}.current{border:2px solid var(--green);background:var(--soft);padding:14px;margin-top:12px}.status{font-weight:800;color:var(--amber)}code{white-space:pre-wrap;word-break:break-word}.artifact-row,.panel-pair{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr));gap:15px;align-items:start}.result-panel .panel-pair{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:15px}.artifact-row>*,.panel-pair>*{min-width:0}.pending-plot{min-height:240px;border:2px dashed var(--line);display:grid;place-items:center;text-align:center;color:var(--muted);padding:20px}.pending{color:var(--amber);font-weight:800}.copy{border:0;background:var(--green);color:#fff;border-radius:7px;padding:8px 12px;font-weight:800}.result-plot{display:block;max-width:100%;height:auto;margin:0 auto}.result-panel{overflow:hidden}.part,.goal,main>section{overflow-x:auto}.panel-pair>*{min-width:0}@media(max-width:760px){header,main{padding:20px}.artifact-row,.panel-pair,.result-panel .panel-pair{grid-template-columns:1fr}h1{font-size:34px}}
"""
STYLE = with_theme(BASE_STYLE, "runplan")
INLINE_TAGS = {"strong", "b", "em", "i", "code", "a", "span", "br"}


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def inline(value: str) -> str:
    soup = BeautifulSoup(str(value), "html.parser")
    for node in soup.find_all(True):
        if node.name not in INLINE_TAGS:
            node.unwrap()
        else:
            node.attrs = {k: v for k, v in node.attrs.items() if k in {"href", "class"}}
    return "".join(str(c) for c in soup.contents)


def table(head: list[str] | None, rows: list[list[str]], th_first: bool = False) -> str:
    thead = "<thead><tr>" + "".join(f"<th>{esc(h)}</th>" for h in head) + "</tr></thead>" if head else ""
    body = "".join(
        "<tr>" + "".join(
            f"<th>{inline(c)}</th>" if th_first and i == 0 else f"<td>{inline(c)}</td>" for i, c in enumerate(row)
        ) + "</tr>" for row in rows
    )
    return f"<table>{thead}<tbody>{body}</tbody></table>"


def render(page: dict, state: dict) -> str:
    required = ("kicker", "title", "subtitle", "estimate", "sources", "coverage", "parts", "mode", "checkpoint")
    missing = [k for k in required if not page.get(k)]
    if missing:
        raise SystemExit("ERROR: empty run-plan slots: " + ", ".join(missing))
    estimate = "<table><tbody>" + "".join(
        "<tr>" + "".join(f"<{'th' if i % 2 == 0 else 'td'}>{inline(c)}</{'th' if i % 2 == 0 else 'td'}>" for i, c in enumerate(row)) + "</tr>"
        for row in page["estimate"]) + "</tbody></table>"
    sources = table(["Method", "Selection and implementation"], page["sources"], th_first=True)
    cov = page["coverage"]
    coverage = f"<p>{inline(cov['summary'])}</p>" + table(cov["head"], cov["rows"])
    parts = ""
    for part in page["parts"]:
        goals = ""
        for goal in part["goals"]:
            goals += (f'<article class="goal" data-goal-id="{esc(goal["id"])}" data-artifact-ids="{esc(goal["artifact_ids"])}">'
                      f'<h3>{esc(goal["title"])}</h3><p>{inline(goal["question"])}</p>'
                      f'<p><b>Corresponding artifacts:</b> {inline(goal["artifacts"])}</p><p>{inline(goal["completion"])}</p>'
                      f'{goal.get("results_html", "")}</article>')
        parts += f'<article class="part"><h3>{esc(part["title"])}</h3>{goals}</article>'
    checkpoint = "".join(f"<p>{inline(p)}</p>" for p in page["checkpoint"])
    payload = json.dumps(state, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Run Plan · {esc(page["name"])}</title><style>{STYLE}</style></head><body>'
            f'<header><div class="muted">{esc(page["kicker"])}</div><h1>{esc(page["title"])}</h1><p>{esc(page["subtitle"])}</p></header><main>\n'
            f'<section data-report-section="execution-estimate"><h2>1. Execution Estimate</h2>{estimate}</section>\n'
            f'<section data-report-section="implementation-sources"><h2>2. Implementation Sources</h2>{sources}</section>\n'
            f'<section data-report-section="artifact-coverage"><h2>3. Figure/Table Coverage</h2>{coverage}</section>\n'
            f'<section data-report-section="parts-and-goals"><h2>4. Parts and Goals</h2><p>{inline(page["mode"])}</p>{parts}</section>\n'
            f'<section data-report-section="reideation-checkpoint" id="reideation-checkpoint"><h2>5. Post-baseline Idea Checkpoint</h2>{checkpoint}</section>\n'
            f'<script type="application/json" id="run-plan-state">{payload}</script></main></body></html>')


def page_from_html(source: str) -> tuple[dict, dict]:
    """One-time migration from an existing run-plan page to (page model, state)."""
    soup = BeautifulSoup(source, "html.parser")
    state = json.loads(soup.find("script", id="run-plan-state").get_text())
    inner = lambda el: "".join(str(c) for c in el.contents).strip()
    head = soup.find("header")
    sec = lambda name: soup.find("section", attrs={"data-report-section": name})
    est = [[inner(c) for c in tr.find_all(["th", "td"])] for tr in sec("execution-estimate").find_all("tr")]
    src = [[inner(c) for c in tr.find_all(["th", "td"])] for tr in sec("implementation-sources").find("tbody").find_all("tr")]
    cov_sec = sec("artifact-coverage")
    cov_table = cov_sec.find("table")
    coverage = {"summary": inner(cov_sec.find("p")),
                "head": [th.get_text() for th in cov_table.find("thead").find_all("th")],
                "rows": [[inner(td) for td in tr.find_all("td")] for tr in cov_table.find("tbody").find_all("tr")]}
    pg = sec("parts-and-goals")
    parts = []
    for part in pg.find_all("article", class_="part"):
        goals = []
        for g in part.find_all("article", class_="goal"):
            ps = g.find_all("p", recursive=False)
            res = g.find("div", class_="goal-results", recursive=False)
            goals.append({
                "id": g["data-goal-id"], "artifact_ids": g.get("data-artifact-ids", ""), "title": g.find("h3", recursive=False).get_text(),
                "question": inner(ps[0]), "artifacts": inner(ps[1]).split("</b>", 1)[1].strip(), "completion": inner(ps[2]),
                "results_html": str(res) if res else "",
            })
        parts.append({"title": part.find("h3", recursive=False).get_text(), "goals": goals})
    name = soup.find("title").get_text().split("·", 1)[1].strip()
    page = {"name": name, "kicker": head.find("div").get_text(), "title": head.find("h1").get_text(), "subtitle": head.find("p").get_text(),
            "estimate": est, "sources": src, "coverage": coverage, "mode": inner(pg.find("p", recursive=False)), "parts": parts,
            "checkpoint": [inner(p) for p in sec("reideation-checkpoint").find_all("p")]}
    return page, state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, help="reports/.build/04_RUN_PLAN.source.json ({page, state})")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--migrate-from", type=Path)
    args = parser.parse_args()
    if args.migrate_from:
        page, state = page_from_html(args.migrate_from.read_text(encoding="utf-8"))
        args.source.parent.mkdir(parents=True, exist_ok=True)
        args.source.write_text(json.dumps({"page": page, "state": state}, ensure_ascii=False, indent=1), encoding="utf-8")
    model = json.loads(args.source.read_text(encoding="utf-8"))
    result = render(model["page"], model["state"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".html", dir=args.output.parent, delete=False) as handle:
        handle.write(result)
        temporary = Path(handle.name)
    errors = validate_structure("runplan", temporary)
    if errors:
        temporary.unlink(missing_ok=True)
        raise SystemExit("\n".join(f"ERROR: {e}" for e in errors))
    os.replace(temporary, args.output)
    print(f"Rendered run plan to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
