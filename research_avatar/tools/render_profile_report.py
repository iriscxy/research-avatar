#!/usr/bin/env python3
"""Render PROFILE.html from fixed content slots.

Everything on the page is fixed here: the stylesheet, header, navigation, section
order and titles, every sub-heading, and every table head. A profile run only fills
the named slots in the source JSON; unknown or missing slots are rejected, so the
page can never gain extra paragraphs, callouts, or sections.
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

from research_avatar.tools.validate_report_structure import validate as validate_structure

STYLE = '\n    :root{--ink:#18201d;--muted:#5e6a64;--paper:#faf8f3;--card:#fffefa;--line:#d8d5cb;--accent:#0b6b59;--accent2:#c65d32;--soft:#eef6f3;--warn:#fff2df}\n    *{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.62 Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}\n    header{background:linear-gradient(125deg,#12352f,#0b6b59 60%,#569083);color:white;padding:72px max(6vw,28px) 58px}.eyebrow{font-size:.78rem;letter-spacing:.14em;text-transform:uppercase;opacity:.8}.hero{max-width:1100px;margin:auto}.hero h1{font:700 clamp(2.7rem,7vw,5.6rem)/.96 Georgia,serif;margin:.25em 0 .18em}.hero p{max-width:760px;font-size:1.15rem;margin:0}.metrics{display:flex;flex-wrap:wrap;gap:10px;margin-top:28px}.metric{border:1px solid #ffffff55;border-radius:999px;padding:7px 13px;font-size:.88rem}.status{background:#fff3;color:#fff}\n    nav{position:sticky;top:0;z-index:4;display:flex;gap:18px;overflow:auto;padding:12px max(6vw,28px);background:#f5f3ecef;backdrop-filter:blur(12px);border-bottom:1px solid var(--line)}nav a{white-space:nowrap;color:var(--muted);text-decoration:none;font-size:.82rem;font-weight:700}\n    main{max-width:1100px;margin:auto;padding:26px max(4vw,24px) 90px}section{padding:54px 0;border-bottom:1px solid var(--line)}h2{font:700 clamp(1.8rem,4vw,2.65rem)/1.1 Georgia,serif;margin:0 0 22px}h3{font-size:1.05rem;margin:30px 0 10px;color:var(--accent);letter-spacing:.02em}h4{margin:20px 0 6px}.lede{font-size:1.12rem;max-width:850px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(245px,1fr));gap:14px}.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}.card h3{margin-top:0}.tag{display:inline-block;padding:3px 9px;border-radius:999px;background:var(--soft);color:var(--accent);font-size:.76rem;font-weight:750;margin:2px}.warning{background:var(--warn);border-left:4px solid #d8872d;padding:14px 16px;border-radius:5px}.callout{background:#e8f2ef;border-left:4px solid var(--accent);padding:14px 16px;border-radius:5px}.timeline{border-left:3px solid var(--accent);padding-left:22px}.timeline article{position:relative;margin:0 0 25px}.timeline article:before{content:"";position:absolute;left:-30px;top:.38em;width:13px;height:13px;background:var(--accent2);border-radius:50%}.timeline time{font-weight:800;color:var(--accent2)}table{border-collapse:collapse;width:100%;background:var(--card);font-size:.91rem}th,td{text-align:left;vertical-align:top;padding:11px;border:1px solid var(--line)}th{background:#e8efeb}code{font-size:.84em;background:#e8ece9;padding:2px 5px;border-radius:4px}a{color:var(--accent)}ul,ol{padding-left:1.3em}.evidence-grid{columns:2;column-gap:34px}.evidence-grid li{break-inside:avoid;margin-bottom:5px}.small{font-size:.88rem;color:var(--muted)}.kicker{font-weight:800;color:var(--accent2)}footer{padding:25px;text-align:center;color:var(--muted)}@media(max-width:680px){.evidence-grid{columns:1}header{padding-top:50px}section{padding:40px 0}}\n  header.top{background:none !important;color:var(--ink) !important;max-width:1100px;margin:auto;padding:36px max(4vw,24px) 14px}header.top h1{font:700 1.7rem/1.2 Georgia,serif !important;margin:0 0 4px;color:var(--accent)}header.top .meta{margin:0;color:var(--muted);font-size:.9rem}\n    nav{padding-left:calc(max(0px,(100vw - 1100px)/2) + max(4vw,24px)) !important;padding-right:max(4vw,24px) !important;backdrop-filter:none !important;background:var(--paper) !important}h2{font-size:1.6rem !important;color:var(--ink)}\n  '
STYLE_OVERRIDES = """
header.top{max-width:1100px;margin:auto;padding:36px max(4vw,24px) 14px}header.top h1{font:700 1.7rem/1.2 Georgia,serif;margin:0 0 4px;color:var(--accent)}header.top .meta{margin:0;color:var(--muted);font-size:.9rem}
nav{padding-left:calc(max(0px,(100vw - 1100px)/2) + max(4vw,24px));padding-right:max(4vw,24px);backdrop-filter:none;background:var(--paper)}h2{font-size:1.6rem;color:var(--ink)}
"""
INLINE_TAGS = {"strong", "b", "em", "i", "code", "a", "span", "br"}

# slot -> (kind, minimum count); kind: text | list | rows | titled
SCHEMA = {
    "identity": {
        "niche_subfields": ("list", 1), "dominant_methods": ("text", 1),
        "active_venues": ("text", 1), "signature_works": ("list", 1),
    },
    "writing": {
        "abstract_profile": ("text", 1), "introduction_profile": ("text", 1),
        "section_profiles": ("section_profiles", 1),
    },
}
TOP_LEVEL = {
    "name", "refreshed", "stats", "writing_style_papers", "identity", "lineage",
    "idea_profile", "writing",
}
SECTIONS = (
    ("research-identity", "1. Research Identity", "Identity"),
    ("research-lineage", "2. Research Lineage", "Lineage"),
    ("idea-profile", "3. Idea Profile", "Idea"),
    ("writing-profile", "4. Writing Profile", "Writing"),
)


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def inline(value: object) -> str:
    soup = BeautifulSoup(str(value), "html.parser")
    for node in soup.find_all(True):
        if node.name not in INLINE_TAGS:
            node.unwrap()
        else:
            node.attrs = {k: v for k, v in node.attrs.items() if k in {"href"}}
    return "".join(str(child) for child in soup.contents)


def ul(items: list) -> str:
    return "<ul>" + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ul>"


def para(text: str) -> str:
    return f"<p>{inline(text)}</p>"


def check(model: dict) -> list[str]:
    errors = [f"unknown top-level slot: {k}" for k in model if k not in TOP_LEVEL]
    for key in ("name", "refreshed", "stats", "writing_style_papers", "identity", "lineage",
                "idea_profile", "writing"):
        if not model.get(key):
            errors.append(f"missing slot: {key}")
    papers = model.get("writing_style_papers", [])
    if not 1 <= len(papers) <= 15 or len(set(papers)) != len(papers):
        errors.append("writing_style_papers must list 1 to 15 unique full-paper keys (kept in the source, never rendered)")
    if "idea_profile" in model and not isinstance(model["idea_profile"], str):
        errors.append("idea_profile must be one text summary of the paired author_differences")
    for section, slots in SCHEMA.items():
        data = model.get(section) or {}
        errors += [f"unknown slot: {section}.{k}" for k in data if k not in slots]
        for slot, (kind, minimum) in slots.items():
            value = data.get(slot)
            if kind == "section_profiles":
                if not isinstance(value, list) or not value:
                    errors.append(f"{section}.{slot} must be a non-empty list")
                    continue
                for index, profile in enumerate(value):
                    if set(profile) != {"organization", "section_names", "profile", "papers"}:
                        errors.append(f"{section}.{slot}[{index}] needs organization, section_names, profile, and papers")
                    elif not all(profile[k] for k in profile):
                        errors.append(f"{section}.{slot}[{index}] contains an empty field")
            elif minimum == 0 and not value:
                continue
            elif not value or (kind != "text" and len(value) < minimum):
                errors.append(f"empty slot: {section}.{slot}")
            elif kind == "titled" and any(set(e) != {"title", "text"} for e in value):
                errors.append(f"{section}.{slot} entries need exactly title and text")
    for entry in model.get("lineage", []):
        if set(entry) != {"year", "title", "text"}:
            errors.append("each lineage entry needs exactly year, title, and text")
    for slot, value in (model.get("identity") or {}).items():
        if isinstance(value, list) and len(value) > 5:
            errors.append(f"identity.{slot} allows at most 5 items")
        if isinstance(value, str) and len(value.split()) > 80:
            errors.append(f"identity.{slot} must stay under 80 words")
    years = [str(entry.get("year")) for entry in model.get("lineage", [])]
    if len(years) != len(set(years)):
        errors.append("lineage needs exactly one entry per year")
    return errors


def render(model: dict) -> str:
    errors = check(model)
    if errors:
        raise SystemExit("\n".join(f"ERROR: {e}" for e in errors))
    i, wr = model["identity"], model["writing"]
    identity = (
        f"<h3>Niche subfields</h3>{ul(i['niche_subfields'])}<h3>Dominant methods</h3>{para(i['dominant_methods'])}"
        f"<h3>Active venues</h3>{para(i['active_venues'])}<h3>Signature works by Scholar impact</h3>{ul(i['signature_works'])}"
    )
    lineage = '<div class="timeline">' + "".join(
        f'<article><h3>{esc(e["year"])} · {esc(e["title"])}</h3><p>{inline(e["text"])}</p></article>' for e in model["lineage"]) + "</div>"
    idea = f'<article data-research-profile="idea">{para(model["idea_profile"])}</article>'
    section_profiles = "".join(
        '<article data-writing-profile="section" '
        f'data-organization="{esc(item["organization"])}" '
        f'data-section-names="{esc(" | ".join(item["section_names"]))}" '
        f'data-papers="{esc(" | ".join(item["papers"]))}">'
        f"<h3>{esc(item['organization'])}</h3>"
        f"<p>{inline(item['profile'])}</p></article>"
        for item in wr["section_profiles"]
    )
    writing = (
        "<h3>Abstract</h3>"
        '<article data-writing-profile="abstract" data-organization="Abstract" data-section-names="Abstract">'
        f"<p>{inline(wr['abstract_profile'])}</p></article>"
        "<h3>Introduction</h3>"
        '<article data-writing-profile="introduction" data-organization="Introduction" data-section-names="Introduction">'
        f"<p>{inline(wr['introduction_profile'])}</p></article>"
        f"{section_profiles}"
    )
    contents = dict(zip((sid for sid, _, _ in SECTIONS), (identity, lineage, idea, writing)))
    nav = "".join(f'<a href="#{sid}">{label}</a>' for sid, _, label in SECTIONS)
    body = "\n\n".join(
        f'<section id="{sid}" data-report-section="{sid}">\n  <h2>{esc(title)}</h2>\n  {contents[sid]}\n</section>'
        for sid, title, _ in SECTIONS
    )
    stats = " · ".join(esc(s) for s in model["stats"])
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(model["name"])} — Researcher Profile</title>
<style>{STYLE}{STYLE_OVERRIDES}</style>
</head>
<body>
<header class="top"><h1>{esc(model["name"])}</h1><p class="meta">Researcher profile · refreshed {esc(model["refreshed"])} · {stats}</p></header>
<nav aria-label="Profile sections">{nav}</nav>
<main>
{body}
</main>
<footer>Research Avatar · canonical profile source</footer>
</body>
</html>
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = render(json.loads(args.source.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".html", dir=args.output.parent, delete=False) as handle:
        handle.write(result)
        temporary = Path(handle.name)
    errors = validate_structure("profile", temporary)
    if errors:
        temporary.unlink(missing_ok=True)
        raise SystemExit("\n".join(f"ERROR: {e}" for e in errors))
    os.replace(temporary, args.output)
    print(f"Rendered profile to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
