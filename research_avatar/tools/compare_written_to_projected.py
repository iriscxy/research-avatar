#!/usr/bin/env python3
"""Compare the written paper with the projected paper that the approved plan promised.

Both are measured the same way: body pages, and how far the body reaches down its last page.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("RESEARCH_AVATAR_ROOT", str(ROOT))
sys.path.insert(0, str(ROOT))

from research_avatar.paper_studio import server as studio  # noqa: E402


def words(text: str) -> int:
    return studio.manuscript_paragraph_word_count(text)


def main() -> int:
    budget = json.loads((ROOT / "paper/projected/budget.json").read_text(encoding="utf-8"))
    status = studio.page_budget_status()
    problems = []
    pages, fill = status["content_pages"], status["last_page_fill"]
    planned_pages = budget["target_pages"]
    planned_effective = budget["body_pages"]
    written_effective = (pages - 1 + fill) if pages and fill is not None else None
    print(f"projected: {planned_effective:.2f} body pages (target {planned_pages:g} pages, last page planned {budget['planned_last_page_fill']:.0%})")
    print(f"written:   {written_effective:.2f} body pages ({pages} pages, last page {fill:.0%})" if written_effective is not None else "written: not compiled")
    # Half a column (0.25 page in a two-column template) is the accepted difference; the body must still fit the page limit.
    if written_effective is None or pages > planned_pages or abs(written_effective - planned_effective) > 0.25:
        problems.append("written length differs from the projected paper by more than half a column (0.25 page) or exceeds the page limit")
    for section, planned in budget["section_words"].items():
        path = ROOT / "paper/sections" / f"{section}.tex"
        if not path.exists():
            problems.append(f"{section}: missing"); continue
        text = re.sub(r"\\begin\{(figure|table)\*?\}.*?\\end\{\1\*?\}", " ", path.read_text(encoding="utf-8"), flags=re.S)
        count = words(text)
        per_paragraph = count / max(len([p for p in re.split(r"\n\s*\n", text) if words(p) > 20]), 1)
        flag = "" if 0.8 <= per_paragraph / planned <= 1.25 else "  <-- off plan"
        if flag:
            problems.append(f"{section}: {per_paragraph:.0f} words per paragraph vs {planned} planned")
        print(f"  {section:13s} {per_paragraph:5.0f} words/paragraph vs {planned} planned{flag}")
    print("MATCHES the projected paper" if not problems else "DIFFERS: " + "; ".join(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
