#!/usr/bin/env python3
"""Render 05_EXP_RESULT.html from a structured model with one fixed template.

Sections, ids, classes, the stylesheet, and the provenance script are fixed. A
results run fills content slots only: which artifacts exist, their tables, the
per-cell values with their provenance, plots, and the acquisition audit.
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
*{box-sizing:border-box}body{margin:0;color:var(--ink);font:15px/1.55 Inter,system-ui,sans-serif}header,main{max-width:1180px;margin:auto;padding:28px}header{padding-top:48px}h1{font:750 43px/1.08 Georgia,serif;margin:.2em 0}h2{font:700 29px/1.2 Georgia,serif;margin-top:44px}h3{margin-top:25px}.muted{color:var(--muted)}table{width:100%;border-collapse:collapse;margin:13px 0;font-size:13px}th,td{padding:8px 9px;border:1px solid var(--line);text-align:left;vertical-align:top}th{background:#f2f7f5}.part,.goal,.artifact{border:1px solid var(--line);padding:15px;margin:12px 0;border-radius:9px}.current{border:2px solid var(--green);background:var(--soft);padding:14px;margin-top:12px}.status{font-weight:800;color:var(--amber)}code{white-space:pre-wrap;word-break:break-word}.artifact-row,.panel-pair{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr));gap:15px;align-items:start}.result-panel .panel-pair{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:15px}.artifact-row>*,.panel-pair>*{min-width:0}.pending-plot{min-height:240px;border:2px dashed var(--line);display:grid;place-items:center;text-align:center;color:var(--muted);padding:20px}.pending{color:var(--amber);font-weight:800}.copy{border:0;background:var(--green);color:#fff;border-radius:7px;padding:8px 12px;font-weight:800}@media(max-width:760px){header,main{padding:20px}.artifact-row,.panel-pair,.result-panel .panel-pair{grid-template-columns:1fr}h1{font-size:34px}}
"""
STYLE = with_theme(BASE_STYLE, "results") + '.result-value:hover,.result-value:focus-visible{outline:2px solid #087f70;background:#eef8f5}.result-value{white-space:nowrap}pre{white-space:pre-wrap;word-break:break-word}.result-plot{display:block;max-width:100%;height:auto;margin:0 auto}.result-panel{overflow:hidden}section.artifact,section.figure-result{overflow-x:auto}.panel-pair>*{min-width:0}'
PROVENANCE_SCRIPT = "\nconst records=JSON.parse(document.getElementById('result-provenance').textContent);\nconst index=document.getElementById('result-provenance-index');\nObject.values(records).forEach(record=>{const card=document.createElement('div');card.id='provenance-'+record.result_id;card.tabIndex=-1;const pre=document.createElement('pre');pre.textContent=JSON.stringify(record,null,2);card.appendChild(pre);index.appendChild(card);});\nfunction openProvenance(){const id=location.hash.replace('#provenance-','');const card=document.getElementById('provenance-'+id);if(card){index.open=true;card.scrollIntoView({block:'center'});card.focus();}}\nwindow.addEventListener('hashchange',openProvenance);openProvenance();\n"
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


def cell(c: dict) -> str:
    if not c.get("result_id"):
        target = f' class="pending" data-target-id="{esc(c["target_id"])}"' if c.get("target_id") else ""
        return f"<td{target}>{inline(c['text'])}</td>"
    summary = esc(c["summary"])
    rid = esc(c["result_id"])
    return (f'<td data-result-id="{rid}" data-target-id="{esc(c["target_id"])}"><a class="result-value" data-provenance-summary="{summary}" '
            f'data-provenance-trigger="{rid}" data-result-id="{rid}" href="#provenance-{rid}" title="{summary}">{esc(c["text"])}</a></td>')


def result_table(a: dict) -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in a["head"])
    rows = "".join(f"<tr><th>{esc(r['label'])}</th>" + "".join(cell(c) for c in r["cells"]) + "</tr>" for r in a["rows"])
    return f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>"


def artifact(a: dict) -> str:
    attrs = f'data-artifact-id="{esc(a["id"])}"'
    if a["kind"] == "figure":
        attrs += f' data-source-target-ids="{esc(a["source_target_ids"])}"'
        img_attrs = "".join(f' {k}="{esc(v)}"' for k, v in sorted(a["plot"].items()))
        shown = f'<img class="result-plot"{img_attrs}>' if a["plot"] else '<svg class="pending-plot" role="img" aria-label="Plot pending until every source cell is filled" viewBox="0 0 360 220"><text x="180" y="110" text-anchor="middle" fill="#61747c">Plot pending: drawn only after every source cell is filled</text></svg>'
        body = (f'<div class="result-panel"><div class="panel-pair"><div>{result_table(a)}<p>{inline(a["note"])}</p></div>'
                f'{shown}</div></div>')
        return (f'<section class="figure-result" {attrs} data-span="{esc(a["span"])}" data-status="{esc(a["status"])}" id="{esc(a["id"])}">'
                f'<h3>{esc(a["id"])} · {esc(a["title"])}</h3>{body}</section>')
    return (f'<section class="artifact" {attrs} data-span="{esc(a["span"])}" data-status="{esc(a["status"])}" id="{esc(a["id"])}">'
            f'<h3>{esc(a["id"])} · {esc(a["title"])}</h3><p>{inline(a["note"])}</p>{result_table(a)}</section>')


def render(page: dict, provenance: dict) -> str:
    required = ("kicker", "title", "subtitle", "artifacts", "audit")
    missing = [k for k in required if not page.get(k)]
    if missing:
        raise SystemExit("ERROR: empty results slots: " + ", ".join(missing))
    cards = "".join(f'<div class="completion-card"><b>{esc(a["id"])}</b> · {esc(a["status"])}</div>' for a in page["artifacts"])
    artifacts = "".join(artifact(a) for a in page["artifacts"])
    audit = "".join(f'<div class="goal-audit"><b>{esc(g["title"])}</b><p>{inline(g["status"])}</p></div>' for g in page["audit"])
    payload = json.dumps(provenance, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Experiment Results · {esc(page["name"])}</title><style>{STYLE}</style></head><body>'
            f'<header><div class="muted">{esc(page["kicker"])}</div><h1>{esc(page["title"])}</h1><p>{esc(page["subtitle"])}</p></header><main>\n'
            f'<section data-report-section="artifact-completion"><h2>1. Artifact Completion</h2>{cards}</section>\n'
            f'<section data-report-section="paper-artifacts"><h2>2. Paper Tables and Figures</h2>{artifacts}</section>\n'
            f'<section data-report-section="generation-process"><h2>3. generation process</h2><details id="result-provenance-index"><summary>Commands, files, calculations, and verification</summary>{audit}</details></section>\n'
            f'<script type="application/json" id="result-provenance">{payload}</script><script>{PROVENANCE_SCRIPT}</script></main></body></html>')


def page_from_html(source: str) -> tuple[dict, dict]:
    """One-time migration from an existing results page to (page model, provenance)."""
    soup = BeautifulSoup(source, "html.parser")
    provenance = json.loads(soup.find("script", id="result-provenance").get_text())
    inner = lambda el: "".join(str(c) for c in el.contents).strip()
    head = soup.find("header")
    artifacts = []
    for sec in soup.find("section", attrs={"data-report-section": "paper-artifacts"}).find_all("section", recursive=False):
        figure = "figure-result" in (sec.get("class") or [])
        table = sec.find("table")
        rows = []
        for tr in table.find("tbody").find_all("tr"):
            cells = []
            for td in tr.find_all("td"):
                a = td.find("a", class_="result-value")
                cells.append({"target_id": td.get("data-target-id", ""), "result_id": td.get("data-result-id", ""),
                              "text": a.get_text() if a else inner(td), "summary": a["data-provenance-summary"] if a else ""})
            rows.append({"label": tr.find("th").get_text(), "cells": cells})
        item = {"id": sec["data-artifact-id"], "kind": "figure" if figure else "table", "span": sec["data-span"], "status": sec["data-status"],
                "title": sec.find("h3").get_text().split(" · ", 1)[1], "head": [th.get_text() for th in table.find("thead").find_all("th")], "rows": rows}
        if figure:
            item["source_target_ids"] = sec["data-source-target-ids"]
            item["note"] = inner(table.find_next_sibling("p"))
            item["plot"] = {k: (v if isinstance(v, str) else " ".join(v)) for k, v in sec.find("img").attrs.items() if k != "class"}
        else:
            item["note"] = inner(sec.find("p", recursive=False))
        artifacts.append(item)
    audit = [{"title": d.find("b").get_text(), "status": inner(d.find("p"))} for d in soup.find_all("div", class_="goal-audit")]
    name = soup.find("title").get_text().split("·", 1)[1].strip()
    page = {"name": name, "kicker": head.find("div").get_text(), "title": head.find("h1").get_text(), "subtitle": head.find("p").get_text(),
            "artifacts": artifacts, "audit": audit}
    return page, provenance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, help="reports/.build/05_EXP_RESULT.source.json ({page, provenance})")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--migrate-from", type=Path)
    args = parser.parse_args()
    if args.migrate_from:
        page, provenance = page_from_html(args.migrate_from.read_text(encoding="utf-8"))
        args.source.parent.mkdir(parents=True, exist_ok=True)
        args.source.write_text(json.dumps({"page": page, "provenance": provenance}, ensure_ascii=False, indent=1), encoding="utf-8")
    model = json.loads(args.source.read_text(encoding="utf-8"))
    result = render(model["page"], model["provenance"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".html", dir=args.output.parent, delete=False) as handle:
        handle.write(result)
        temporary = Path(handle.name)
    errors = validate_structure("results", temporary)
    if errors:
        temporary.unlink(missing_ok=True)
        raise SystemExit("\n".join(f"ERROR: {e}" for e in errors))
    os.replace(temporary, args.output)
    print(f"Rendered experiment results to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
