#!/usr/bin/env python3
"""Render 03_EXPERIMENT_PLAN.html from a structured page model with one fixed template.

The layout, section order, ids, classes, and stylesheet are fixed here. A planning
run only fills content slots: the page model (``page``) and the experiment-plan
contract JSON that is embedded for downstream validators.
"""

from __future__ import annotations

import argparse
import base64
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
:root{--ink:#17323e;--muted:#61747c;--line:#d9e5e2;--green:#087f70;--soft:#eef8f5;--amber:#9a6511}
*{box-sizing:border-box}body{margin:0;color:var(--ink);font:15px/1.55 Inter,system-ui,sans-serif;background:#fff}header,main{max-width:1180px;margin:auto;padding:28px}header{padding-top:50px}h1{font:750 44px/1.08 Georgia,serif;margin:.2em 0}h2{font:700 29px/1.2 Georgia,serif;margin-top:46px}h3{font-size:18px;margin-top:28px}h4{font-size:16px;color:var(--green);margin-top:24px}.muted{color:var(--muted)}a{color:#086277}.hero,.callout{border-left:4px solid var(--green);background:var(--soft);padding:15px 18px}.float-budget{font-size:14px;border:1px solid var(--green);padding:10px 14px;border-radius:8px;font-weight:600}.paper-title{font:700 22px/1.25 Georgia,serif;margin:12px 0 8px}.paragraph{padding:12px 0;border-bottom:1px solid var(--line)}details{margin-top:7px;color:var(--muted)}table{width:100%;border-collapse:collapse;margin:12px 0;font-size:13px}th,td{padding:8px 9px;border:1px solid var(--line);text-align:left;vertical-align:top}th{background:#f3f8f6}.table-wrap{overflow:auto}.shell{border:1px solid var(--line);padding:15px;margin:16px 0;border-radius:9px}.shell-title{font-weight:850;font-size:16px}.pending{color:var(--amber);font-weight:750}.panel-pair{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr));gap:15px;align-items:center}.panel-pair>*{min-width:0}.projected-preview img{display:block;max-width:100%;height:auto}.badge{display:inline-block;border-radius:99px;background:#e5f5f1;color:var(--green);padding:3px 9px;font-weight:800;font-size:12px}.approval{margin:28px 0;padding:17px;border:2px solid var(--green);border-radius:9px}var{font-family:Georgia,serif;font-style:italic}var sub{font-style:normal;font-size:.72em}@media(max-width:760px){header,main{padding:20px}.panel-pair{grid-template-columns:1fr}h1{font-size:35px}}
[data-report-subsection="projected-paper-structure"] h4{margin:38px 0 10px;padding:8px 0 6px;border-top:3px solid var(--accent);border-bottom:1px solid var(--line);font:700 20px/1.25 Georgia,serif;color:var(--ink)}
[data-report-subsection="projected-paper-structure"] h5{margin:20px 0 8px;padding:2px 0 2px 10px;border-left:4px solid var(--accent2);font:700 14px/1.3 Inter,system-ui,sans-serif;letter-spacing:.02em;color:var(--accent)}
[data-report-subsection="projected-paper-structure"] .paragraph{margin:8px 0 8px 14px;padding:12px 16px;background:var(--card);border:1px solid var(--line);border-radius:8px;font-size:14.5px}
[data-report-subsection="projected-paper-structure"] .paragraph>b{display:inline-block;margin-right:6px;padding:1px 8px;border-radius:999px;background:var(--soft);color:var(--accent);font-size:12.5px}
[data-report-subsection="projected-paper-structure"] .paragraph .muted{margin:6px 0;font-size:12.5px}
[data-report-subsection="projected-paper-structure"] .paragraph details{margin-top:4px;font-size:13px}
[data-report-subsection="projected-paper-structure"] .shell,[data-report-subsection="projected-paper-structure"] [data-model-design],[data-report-subsection="projected-paper-structure"] [data-experiment-setup]{margin-left:14px}
.structure-split{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,.62fr);gap:20px;align-items:start}.structure-main{min-width:0}.pdf-pane{position:sticky;top:12px;max-height:94vh;overflow:auto;padding:10px;border:1px solid var(--line);border-radius:8px;background:var(--card)}.pdf-pane img{display:block;width:100%;height:auto;margin:8px 0;border:1px solid var(--line)}.pdf-title{font-size:12.5px;color:var(--muted)}@media(max-width:1100px){.structure-split{grid-template-columns:1fr}.pdf-pane{position:static;max-height:none}}
"""
STYLE = with_theme(BASE_STYLE, "expplan")
INLINE_TAGS = {"strong", "b", "em", "i", "code", "a", "span", "br", "var", "sub", "sup"}


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


def table_html(head: list[str] | None, rows: list[list[str]], first_is_th: bool = False) -> str:
    thead = "<thead><tr>" + "".join(f"<th>{esc(h)}</th>" for h in head) + "</tr></thead>" if head else ""
    body = "".join(
        "<tr>" + "".join(
            (f"<th>{inline(c)}</th>" if first_is_th and i == 0 else f"<td>{inline(c)}</td>") for i, c in enumerate(row)
        ) + "</tr>"
        for row in rows
    )
    return f"<table>{thead}<tbody>{body}</tbody></table>"


def pending_cells(target_ids: list[str]) -> str:
    return "".join(f'<td class="pending" data-target-id="{esc(t)}">[PENDING]</td>' for t in target_ids)


def paragraph_html(b: dict) -> str:
    badge = f' <span class="badge">Evidence: {esc(", ".join(b["artifact_refs"]))}</span>' if b["artifact_refs"] else ""
    details = "".join(
        f'<details><summary>Mapped reference move · {esc(m["id"])}</summary><p><b>Source heading:</b> {esc(m["heading"])}</p>'
        f'<p>{esc(m["text"])}</p><p><b>Adaptation:</b> {esc(m["adaptation"])}</p></details>'
        for m in b["mappings"]
    )
    return (f'<article class="paragraph"><b>{esc(b["id"])}</b>{esc(b["plan"])}{badge}'
            f'<p class="muted">{esc(b["relation"])}</p>{details}</article>')


def model_design_html(rows: list) -> str:
    return "<div data-model-design><table><tbody>" + "".join(
        f"<tr><th>{esc(k)}</th><td>{inline(v)}</td></tr>" for k, v in rows) + "</tbody></table></div>"


def idea_method_html(text: str) -> str:
    return f'<div data-idea-method><p><b>Method (from the selected idea).</b> {inline(text)}</p></div>'


def experiment_setup_html(b: dict) -> str:
    impl = "".join(f"<tr><th>{esc(k)}</th><td>{inline(v)}</td></tr>" for k, v in b["implementation_rows"])
    return ('<div data-experiment-setup><table class="setup-table"><tbody>'
            + "".join(f"<tr><th>{esc(k)}</th><td>{inline(v)}</td></tr>" for k, v in b["setup_rows"])
            + '</tbody></table><table class="implementation-table"><thead><tr><th>Method</th><th>Selection and implementation</th></tr></thead>'
            + f"<tbody>{impl}</tbody></table></div>")


def result_table_html(b: dict) -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in b["head"])
    rows = "".join(f"<tr><th>{esc(r['label'])}</th>{pending_cells(r['target_ids'])}</tr>" for r in b["rows"])
    return (f'<div class="shell result-table-shell"><div class="shell-title">{esc(b["id"])} · {esc(b["title"])}</div>'
            f'<p><b>RESULT PLACEHOLDER — NO NUMBERS FABRICATED.</b> {inline(b["note"])}</p>'
            f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>'
            f'<p class="muted">{esc(b["footnote"])}</p></div>')


def figure_html(b: dict) -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in b["head"])
    rows = "".join(f'<tr class="plot-point"><th>{esc(r["label"])}</th>{pending_cells(r["target_ids"])}</tr>' for r in b["rows"])
    pv = b["preview"]
    series = b["head"][1:]
    colors = ["#c46b43", "#6b71b8", "#087f70", "#9a6511"]
    left, right, top, bottom = 56, 400, 24, 200
    n = len(b["rows"])
    levels = pv.get("levels") or [[0.86 - 0.08 * si - 0.38 * k / max(n - 1, 1) for k in range(n)] for si in range(len(series))]
    xs = [left + (right - left) * (k + 0.5) / n for k in range(n)]
    parts = [f'<line stroke="#61747c" x1="{left}" x2="{right}" y1="{bottom}" y2="{bottom}"></line>',
             f'<line stroke="#61747c" x1="{left}" x2="{left}" y1="{top}" y2="{bottom}"></line>']
    for k, row in enumerate(b["rows"]):
        parts.append(f'<text font-size="11" text-anchor="middle" x="{xs[k]:.1f}" y="{bottom + 16}">{esc(row["label"])}</text>')
    for si, name in enumerate(series):
        pts = [(xs[k], top + (bottom - top) * (1 - levels[si][k])) for k in range(n)]
        parts.append(f'<polyline fill="none" stroke="{colors[si]}" stroke-dasharray="6 5" stroke-width="2" points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}"></polyline>')
        for k, (x, y) in enumerate(pts):
            parts.append(f'<circle class="plot-mark" cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="#fff" stroke="{colors[si]}" stroke-width="2" data-target-id="{esc(b["rows"][k]["target_ids"][si])}"></circle>')
        lx = left + 8 + si * 118
        parts.append(f'<circle cx="{lx}" cy="{bottom + 44}" r="4.5" fill="#fff" stroke="{colors[si]}" stroke-width="2"></circle><text font-size="11" x="{lx + 9}" y="{bottom + 48}">{esc(name)}</text>')
    parts.append(f'<text font-size="12" text-anchor="middle" x="{(left + right) / 2:.0f}" y="{bottom + 30}">{esc(pv["x_label"])}</text>')
    parts.append(f'<text font-size="12" text-anchor="middle" transform="translate(14 {(top + bottom) / 2:.0f}) rotate(-90)">{esc(pv["y_label"])}</text>')
    parts.append(f'<text fill="#61747c" font-size="11" text-anchor="middle" x="{(left + right) / 2:.0f}" y="14">{esc(pv["caption"])}</text>')
    svg = f'<svg aria-label="{esc(pv["aria"])}" role="img" viewBox="0 0 420 262">' + "".join(parts) + "</svg>"
    return (f'<div class="shell projected-figure"><div class="shell-title">{esc(b["id"])} · {esc(b["title"])}</div>'
            f'<p><b>PROJECTED SHAPE — NOT RESULTS.</b> The preview communicates chart geometry only and contains no experimental value.</p>'
            f'<section class="panel-pair" data-artifact-id="{esc(b["id"])}"><div class="required-data figure-source-data"><b>Source data table</b>'
            f'<p>{inline(b["source_html"])}</p><table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>'
            f'<div class="projected-preview">{svg}</div></section></div>')


PAGE_KEYS = {"kicker", "title", "subtitle", "target", "float_budget", "paper_title", "abstract", "outline", "artifacts", "ledger", "approval"}
OUTLINE_KEYS = {"title", "paragraphs", "model_design", "idea_method", "experiment_setup"}
PARAGRAPH_KEYS = {"id", "heading", "plan", "artifact_refs", "relation", "mappings"}
MAPPING_KEYS = {"id", "heading", "text", "adaptation"}
ARTIFACT_KEYS = {
    "result_table": {"type", "id", "title", "note", "head", "rows", "footnote"},
    "figure": {"type", "id", "title", "source_html", "head", "rows", "preview"},
}


def check_page(page: dict) -> list[str]:
    errors = [f"unknown slot: {k}" for k in page if k not in PAGE_KEYS]
    errors += [f"missing slot: {k}" for k in PAGE_KEYS if not page.get(k)]
    placed: dict[str, int] = {}
    for section in page.get("outline", []):
        errors += [f"outline slot not allowed: {k}" for k in section if k not in OUTLINE_KEYS]
        for para in section.get("paragraphs", []):
            errors += [f"paragraph slot not allowed: {k}" for k in para if k not in PARAGRAPH_KEYS]
            errors += [f"paragraph {para.get('id')} lacks {k}" for k in PARAGRAPH_KEYS if k not in para]
            for m in para.get("mappings", []):
                errors += [f"mapping slot not allowed: {k}" for k in m if k not in MAPPING_KEYS]
            for ref in para.get("artifact_refs", []):
                placed[ref] = placed.get(ref, 0) + 1
    artifacts = page.get("artifacts", [])
    for a in artifacts:
        allowed = ARTIFACT_KEYS.get(a.get("type"))
        if not allowed:
            errors.append(f"unknown artifact type: {a.get('type')}")
            continue
        errors += [f"artifact {a.get('id')} slot not allowed: {k}" for k in a if k not in allowed]
        errors += [f"artifact {a.get('id')} lacks {k}" for k in allowed if k not in a]
        if placed.get(a["id"]) != 1:
            errors.append(f"artifact {a['id']} must be referenced by exactly one paragraph")
    return errors


def projected_pdf_pane() -> str:
    """Side-by-side compiled projected paper (pages rasterized by render_projected_pdf.py), when present."""
    folder = Path(__file__).resolve().parents[2] / "paper" / "projected"
    pages = sorted(folder.glob("page-*.png"), key=lambda f: int(f.stem.split("-")[1]))
    if not pages:
        return ""
    imgs = "".join(
        f'<img alt="Projected paper page {i}" src="data:image/png;base64,{base64.b64encode(f.read_bytes()).decode()}">'
        for i, f in enumerate(pages, 1)
    )
    pdf = folder / "main.pdf"
    link = (f'<a download="projected_paper.pdf" href="data:application/pdf;base64,{base64.b64encode(pdf.read_bytes()).decode()}">Download PDF</a>'
            if pdf.exists() else "")
    return (f'<aside class="pdf-pane"><div class="pdf-title"><b>Compiled projected paper</b> · every figure and table placeholder · {link}</div>{imgs}</aside>')


def render(page: dict, contract: dict) -> str:
    errors = check_page(page)
    if errors:
        raise SystemExit("\n".join("ERROR: " + e for e in errors))
    shells = {a["id"]: (result_table_html(a) if a["type"] == "result_table" else figure_html(a)) for a in page["artifacts"]}
    target = "".join(f"<p>{inline(p)}</p>" for p in page["target"])
    blocks = ""
    for section in page["outline"]:
        blocks += f"<h4>{esc(section['title'])}</h4>"
        if section.get("idea_method"):
            blocks += idea_method_html(contract.get("grounding", {}).get("idea_method", ""))
        if section.get("model_design"):
            blocks += model_design_html(section["model_design"])
        if section.get("experiment_setup"):
            blocks += experiment_setup_html(section["experiment_setup"])
        for para in section["paragraphs"]:
            if para["heading"]:
                blocks += f"<h5>{esc(para['heading'])}</h5>"
            blocks += paragraph_html(para)
            blocks += "".join(shells[ref] for ref in para["artifact_refs"] if ref in shells)
    ledger = ('<h4>Compact artifact ledger</h4><div class="table-wrap">'
              + table_html(["ID", "Type", "Paper role", "Span", "Status"], page["ledger"]) + "</div>")
    blocks += ledger + f'<div class="approval">{inline(page["approval"])}</div>'
    payload = json.dumps(contract, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Experiment Plan · {esc(page["title"])}</title><style>{STYLE}</style></head><body>'
            f'<header><div class="muted">{esc(page["kicker"])}</div><h1>{esc(page["title"])}</h1><p>{esc(page["subtitle"])}</p></header><main>\n'
            f'<section data-report-section="target-and-references"><h2>1. Target Conference and Reference Paper</h2><div class="hero">{target}</div></section>\n'
            f'<section data-report-section="projected-paper"><h2>2. Projected Paper</h2><p class="float-budget">{esc(page["float_budget"])}</p>\n'
            f'<section data-report-subsection="projected-title-abstract"><h3>2.1 Projected Title and Abstract</h3><div class="paper-title">{esc(page["paper_title"])}</div>'
            f'<div class="callout"><b>PROJECTED — not results.</b> {inline(page["abstract"])}</div></section>\n'
            f'<section data-report-subsection="projected-paper-structure"><h3>2.2 Projected Paper Structure and Evidence Shells</h3><div class="structure-split"><div class="structure-main">{blocks}</div>{projected_pdf_pane()}</div></section></section>\n'
            f'<script type="application/json" id="experiment-plan-contract">{payload}</script></main></body></html>')


def page_from_html(source: str) -> tuple[dict, dict]:
    """One-time migration: read an existing plan page into (strict page slots, contract)."""
    soup = BeautifulSoup(source, "html.parser")
    contract = json.loads(soup.find("script", id="experiment-plan-contract").get_text())
    soup.find("script", id="experiment-plan-contract").extract()
    inner = lambda el: "".join(str(c) for c in el.contents).strip()
    head = soup.find("header")
    t = soup.find("section", attrs={"data-report-section": "target-and-references"})
    abstract = inner(soup.find("div", class_="callout")).split("</b>", 1)[1].strip()
    sub = soup.find("section", attrs={"data-report-subsection": "projected-paper-structure"})
    outline: list[dict] = []
    artifacts: list[dict] = []
    ledger: list = []
    approval = ""
    heading = ""
    for el in sub.find_all(True, recursive=False):
        cls = el.get("class") or []
        if el.name == "h4" and el.get_text() != "Compact artifact ledger":
            outline.append({"title": el.get_text(), "paragraphs": []})
        elif el.name == "h5":
            heading = el.get_text()
        elif el.name == "article":
            b = el.find("b", recursive=False)
            badge = el.find("span", class_="badge")
            outline[-1]["paragraphs"].append({
                "id": b.get_text(), "heading": heading, "plan": str(b.next_sibling).lstrip(" ·").strip(),
                "artifact_refs": [x.strip() for x in badge.get_text().replace("Evidence:", "").split(",")] if badge else [],
                "relation": el.find("p", class_="muted").get_text(),
                "mappings": [{
                    "id": d.find("summary").get_text().split("·")[-1].strip(),
                    "heading": d.find_all("p")[0].get_text().replace("Source heading:", "").strip(),
                    "text": d.find_all("p")[1].get_text(),
                    "adaptation": d.find_all("p")[2].get_text().replace("Adaptation:", "").strip(),
                } for d in el.find_all("details")],
            })
            heading = ""
        elif el.get("data-idea-method") is not None:
            outline[-1]["idea_method"] = True
        elif el.get("data-model-design") is not None:
            outline[-1]["model_design"] = [[tr.find("th").get_text(), inner(tr.find("td"))] for tr in el.find_all("tr")]
        elif el.get("data-experiment-setup") is not None:
            setup, impl = el.find("table", class_="setup-table"), el.find("table", class_="implementation-table")
            outline[-1]["experiment_setup"] = {
                "setup_rows": [[tr.find("th").get_text(), inner(tr.find("td"))] for tr in setup.find_all("tr")],
                "implementation_rows": [[tr.find("th").get_text(), inner(tr.find("td"))] for tr in impl.find("tbody").find_all("tr")]}
        elif "result-table-shell" in cls:
            tid, ttl = el.find("div", class_="shell-title").get_text().split(" · ", 1)
            table = el.find("table")
            artifacts.append({"type": "result_table", "id": tid, "title": ttl,
                              "note": inner(el.find_all("p", recursive=False)[0]).split("</b>", 1)[1].strip(),
                              "head": [th.get_text() for th in table.find("thead").find_all("th")],
                              "rows": [{"label": tr.find("th").get_text(), "target_ids": [td["data-target-id"] for td in tr.find_all("td")]} for tr in table.find("tbody").find_all("tr")],
                              "footnote": el.find("p", class_="muted").get_text()})
        elif "projected-figure" in cls:
            fid, ttl = el.find("div", class_="shell-title").get_text().split(" · ", 1)
            table = el.find("table"); svg = el.find("svg"); texts = svg.find_all("text")
            artifacts.append({"type": "figure", "id": fid, "title": ttl,
                              "source_html": inner(el.find("div", class_="required-data").find("p")),
                              "head": [th.get_text() for th in table.find("thead").find_all("th")],
                              "rows": [{"label": tr.find("th").get_text(), "target_ids": [td["data-target-id"] for td in tr.find_all("td")]} for tr in table.find("tbody").find_all("tr")],
                              "preview": {"aria": svg.get("aria-label"), "path": svg.find("path")["d"], "x_label": texts[0].get_text(),
                                          "y_label": texts[1].get_text(), "caption": texts[2].get_text()}})
        elif "table-wrap" in cls:
            tb = el.find("table")
            ledger = [[inner(td) for td in tr.find_all("td")] for tr in tb.find("tbody").find_all("tr")]
        elif "approval" in cls:
            approval = inner(el)
    page = {
        "kicker": head.find("div").get_text(), "title": head.find("h1").get_text(), "subtitle": head.find("p").get_text(),
        "target": [inner(p) for p in t.find("div", class_="hero").find_all("p")],
        "float_budget": soup.find("p", class_="float-budget").get_text(),
        "paper_title": soup.find("div", class_="paper-title").get_text(), "abstract": abstract,
        "outline": outline, "artifacts": artifacts, "ledger": ledger, "approval": approval,
    }
    return page, contract


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, help="reports/.build/03_EXPERIMENT_PLAN.source.json ({page, contract})")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--migrate-from", type=Path, help="write --source from an existing plan page, then render")
    args = parser.parse_args()
    if args.migrate_from:
        page, contract = page_from_html(args.migrate_from.read_text(encoding="utf-8"))
        args.source.parent.mkdir(parents=True, exist_ok=True)
        args.source.write_text(json.dumps({"page": page, "contract": contract}, ensure_ascii=False, indent=1), encoding="utf-8")
    model = json.loads(args.source.read_text(encoding="utf-8"))
    result = render(model["page"], model["contract"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".html", dir=args.output.parent, delete=False) as handle:
        handle.write(result)
        temporary = Path(handle.name)
    errors = validate_structure("expplan", temporary)
    if errors:
        temporary.unlink(missing_ok=True)
        raise SystemExit("\n".join(f"ERROR: {e}" for e in errors))
    os.replace(temporary, args.output)
    print(f"Rendered experiment plan to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
