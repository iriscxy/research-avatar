#!/usr/bin/env python3
"""Compile the projected paper (every placeholder visible) from the experiment-plan source.

Writes ``paper/projected/main.tex``, compiles ``main.pdf`` and rasterizes
``page-N.png`` for the plan page. Values stay ``[PENDING]``; nothing is invented.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLORS = ["orange!80!black", "blue!60!black", "teal!80!black", "olive!80!black"]
# Filler must have the length statistics of real English prose, or the projected page count is biased:
# Latin placeholder words are about 30% longer than the words of a scientific paper.
LOREM = ("the of and to in a is that for with as on we are by this from be an or at which can not it these has each more their than such all when "
         "one two three used using results show model data systems system answer answers question questions history value values chain chains time "
         "across between over under after before only both same different first second final latest superseded revision revisions distance sessions "
         "session score scores rule based reader memory retrieval accuracy rate gap drop sweep factor factors condition conditions evidence ledger "
         "fixed length controlled measure measures measured report reports reported compare compared against while because however therefore since "
         "also then thus whether where how what who why many most some any every other another also still even so if no into out up down large small "
         "high low near far long short early late old new current previous next later earlier explicit implicit simple complex natural template").split()


def filler(words: int, seed: int) -> str:
    out = [LOREM[(seed * 7 + k) % len(LOREM)] for k in range(max(words, 1))]
    out[0] = out[0].capitalize()
    return " ".join(out) + "."


# Kept at 1.0: citations, the abstract and the real figure height are modeled directly, so no fudge factor is needed.
WRITTEN_PROSE_CALIBRATION = 1.0

SPECIAL = {"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}", "\\": r"\textbackslash{}"}


def tex(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", str(text))
    out = "".join(SPECIAL.get(ch, ch) for ch in text)
    return out.replace("—", "---").replace("→", "$\\to$").replace("×", "$\\times$").replace("−", "-")


def table_tex(art: dict, span: str, caption: str) -> str:
    cols = len(art["head"])
    env = "table*" if span == "double_column" else "table"
    head = " & ".join(r"\textbf{%s}" % tex(h) for h in art["head"])
    rows = "".join(f"{tex(r['label'])} & " + " & ".join(r"\textcolor{orange!80!black}{[PENDING]}" for _ in r["target_ids"]) + r" \\" + "\n" for r in art["rows"])
    spec = "l" + "r" * (cols - 1)
    return (f"\\begin{{{env}}}[t]\n\\centering\\footnotesize\n\\resizebox{{\\linewidth}}{{!}}{{\\begin{{tabular}}{{{spec}}}\n\\toprule\n{head} \\\\\n\\midrule\n{rows}\\bottomrule\n\\end{{tabular}}}}\n"
            f"\\caption{{{tex(caption)} \\textbf{{[PROJECTED, all values pending]}}}}\n\\end{{{env}}}\n")


def figure_tex(art: dict, shell: dict, caption: str) -> str:
    series, rows = art["head"][1:], art["rows"]
    n = len(rows)
    lines = [r"\begin{figure}[t]", r"\centering", r"\begin{tikzpicture}[x=0.9cm,y=2.1cm,font=\scriptsize]", rf"\draw[->] (0,0) -- ({n + 0.3},0); \draw[->] (0,0) -- (0,1.15);"]
    for k, row in enumerate(rows):
        lines.append(rf"\node[below] at ({k + 0.7},0) {{{tex(row['label'])}}};")
    for si, name in enumerate(series):
        pts = [(k + 0.7, shell["levels"][si][k]) for k in range(n)]
        lines.append(rf"\draw[{COLORS[si]},dashed,thick] " + " -- ".join(f"({x:.2f},{y:.2f})" for x, y in pts) + ";")
        for x, y in pts:
            lines.append(rf"\filldraw[fill=white,draw={COLORS[si]},thick] ({x:.2f},{y:.2f}) circle (0.07cm);")
        lines.append(rf"\node[anchor=west,{COLORS[si]}] at ({n + 0.4},{1.0 - 0.18 * si}) {{{tex(name)}}};")
    lines += [rf"\node[below] at ({(n + 0.3) / 2:.2f},-0.28) {{{tex(shell['x_label'])}}};", rf"\node[rotate=90] at (-0.55,0.55) {{{tex(shell['y_label'])}}};",
              rf"\node[gray] at ({(n + 0.3) / 2:.2f},1.28) {{PROJECTED SHAPE --- NOT RESULTS}};", r"\end{tikzpicture}",
              f"\\caption{{{tex(caption)} \\textbf{{[PROJECTED, values pending]}}}}", r"\end{figure}"]
    return "\n".join(lines) + "\n"


def count_only_figure(art: dict) -> str:
    label = tex(art["caption"])
    return ("\\begin{figure}[t]\n\\centering\n\\fbox{\\parbox[c][0.95\\linewidth][c]{0.9\\linewidth}{\\centering\\small\\textcolor{gray}{FIGURE PLACEHOLDER (count-only)\\\\ "
            + label + "}}}\n\\caption{" + label + " \\textbf{[PROJECTED, to be designed when writing]}}\n\\end{figure}\n")


def build(source: Path, out_dir: Path, scale: float = 1.0) -> Path:
    data = json.loads(source.read_text(encoding="utf-8"))
    page, contract = data["page"], data["contract"]
    shells = {a["id"]: a for a in page["artifacts"]}
    spans = {a["id"]: a["span"] for a in contract["paper_artifacts"]}
    captions = {a["id"]: a for a in contract["paper_artifacts"]}
    body = []
    paragraph_words = {}
    contract_shares = {sec["id"]: sec["length_share"] for sec in contract["paper_outline"]}
    for sec_c, sec in zip(contract["paper_outline"], page["outline"]):
        n = max(len(sec["paragraphs"]), 1)
        for para in sec["paragraphs"]:
            paragraph_words[para["id"]] = contract_shares[sec_c["id"]] * 1000 / n * scale
    seed = 0
    for section in page["outline"]:
        title = section["title"]
        if title == "Abstract":
            continue
        body.append(f"\\section{{{tex(title)}}}\n")
        for para in section["paragraphs"]:
            seed += 1
            if para["heading"]:
                body.append(f"\\subsection{{{tex(para['heading'])}}}\n")
            cites = (3 if section["title"] == "Introduction" and para["id"] in {"I-P1", "I-P2", "I-P3"} else 8 if section["title"] == "Related Work" else 0)
            marks = " ".join(f"(Surname et al., 2025)" for _ in range(cites))
            body.append(f"\\textbf{{[{tex(para['id'])}]}} \\textcolor{{gray}}{{{filler(round(paragraph_words[para['id']]), seed)} {marks}}}\n")
            for ref in para["artifact_refs"]:
                art = shells.get(ref)
                if art:
                    body.append(figure_tex(art, art["preview"], captions[ref]["caption"]) if art["type"] == "figure" else table_tex(art, spans[ref], captions[ref]["caption"]))
                else:
                    body.append(count_only_figure(captions[ref]))
    # A Jinghui-generated abstract is already LaTeX; use it as returned instead of escaping it.
    generated = (contract.get("abstract_generation") or {}).get("output")
    abstract_tex = generated if generated else tex(page["abstract"])
    doc = ("\\documentclass[11pt]{article}\n\\usepackage[review]{acl}\n\\usepackage{times}\n\\usepackage{latexsym}\n\\usepackage[T1]{fontenc}\n\\usepackage[utf8]{inputenc}\n"
           "\\usepackage{microtype,graphicx,booktabs,xcolor,tikz,flafter,placeins}\n\\usepackage{xurl}\n"
           f"\\title{{{tex(page['paper_title'])}}}\n\\author{{Anonymous Author(s)}}\n\\date{{}}\n\\begin{{document}}\n\\maketitle\n"
           f"\\begin{{abstract}}\n\\textbf{{[PROJECTED]}} {abstract_tex}\n\\end{{abstract}}\n" + "\n".join(body) + "\n\\FloatBarrier\n\\end{document}\n")
    out_dir.mkdir(parents=True, exist_ok=True)
    section_words = {}
    for sec_c, sec in zip(contract["paper_outline"], page["outline"]):
        if sec_c["id"] != "abstract":
            section_words[sec_c["id"].replace("-", "_")] = round(contract_shares[sec_c["id"]] * 1000 / max(len(sec["paragraphs"]), 1) * scale * WRITTEN_PROSE_CALIBRATION)
    (out_dir / "budget.json").write_text(json.dumps({"scale": round(scale, 4), "paragraph_words": {k: round(v) for k, v in paragraph_words.items()}, "section_words": section_words, "abstract_words": len(re.sub(r"<[^>]+>", "", page["abstract"]).split())}, indent=1), encoding="utf-8")
    shutil.copy(ROOT / "paper" / "acl.sty", out_dir / "acl.sty")
    shutil.copy(ROOT / "paper" / "acl_natbib.bst", out_dir / "acl_natbib.bst")
    (out_dir / "main.tex").write_text(doc, encoding="utf-8")
    return out_dir / "main.tex"


def compile_pdf(tex_path: Path, out_dir: Path) -> bool:
    for _ in range(2):
        run = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name], cwd=out_dir, capture_output=True, text=True)
        if run.returncode:
            print(run.stdout[-1800:], file=sys.stderr)
            return False
    return True


def effective_pages(out_dir: Path) -> float:
    """Pages used by the body: full pages plus the filled share of the last page (two columns)."""
    from PIL import Image
    import numpy as np

    subprocess.run(["pdftoppm", "-r", "40", "-png", "main.pdf", "m"], cwd=out_dir, check=True)
    shots = sorted(out_dir.glob("m-*.png"))
    arrays = [np.asarray(Image.open(f).convert("L")) for f in shots]
    for f in shots:
        f.unlink()
    h = arrays[0].shape[0]
    top, bottom = int(h * 0.07), int(h * 0.92)

    def column_bottom(img, side):
        w = img.shape[1]
        band = img[top:bottom, : w // 2] if side == 0 else img[top:bottom, w // 2 :]
        rows = np.where((band < 200).sum(axis=1) > 0)[0]
        return (rows.max() + 1) / (bottom - top) if len(rows) else 0.0

    last = arrays[-1]
    fill = (column_bottom(last, 0) + column_bottom(last, 1)) / 2
    return len(arrays) - 1 + fill


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=ROOT / "reports/.build/03_EXPERIMENT_PLAN.source.json")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "paper/projected")
    parser.add_argument("--target-pages", type=float, default=4.0)
    parser.add_argument("--fill", type=float, default=0.95, help="Planned fill of the last body page")
    args = parser.parse_args()
    goal = args.target_pages - 1 + args.fill
    lo, hi = 0.2, 4.0
    scale = 1.0
    for _ in range(9):
        tex_path = build(args.source, args.out_dir, scale)
        if not compile_pdf(tex_path, args.out_dir):
            return 1
        used = effective_pages(args.out_dir)
        if abs(used - goal) < 0.02:
            break
        lo, hi = (scale, hi) if used < goal else (lo, scale)
        scale = (lo + hi) / 2
    for old in args.out_dir.glob("page-*.png"):
        old.unlink()
    subprocess.run(["pdftoppm", "-r", "110", "-png", "main.pdf", "page"], cwd=args.out_dir, check=True)
    pages = len(list(args.out_dir.glob("page-*.png")))
    for junk in ("main.aux", "main.log", "main.out"):
        (args.out_dir / junk).unlink(missing_ok=True)
    budget_path = args.out_dir / "budget.json"
    budget = json.loads(budget_path.read_text(encoding="utf-8"))
    budget.update({"body_pages": round(used, 3), "target_pages": args.target_pages, "planned_last_page_fill": args.fill})
    budget_path.write_text(json.dumps(budget, indent=1), encoding="utf-8")
    print(f"Compiled projected paper: {pages} pages, body length {used:.2f} pages (target {goal:.2f}), paragraph length scale {scale:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
