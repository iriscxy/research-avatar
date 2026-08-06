#!/usr/bin/env python3
"""Enrich a Google Scholar publication list with abstracts, DOIs, and BibTeX.

Used by the ``profileconstruct`` skill. Input is the JSON emitted by
``scholar_profile.py``. For each paper we:

1. Build a clean BibTeX entry *locally* from the Scholar metadata (title,
   authors, venue, year) with a normalized citation key (e.g. ``guo2024large``).
   This never needs the network, so the BibTeX Bank is always complete.
2. Best-effort enrich via Semantic Scholar (title search): attach ``abstract``
   and ``doi`` when a confident title match is found. The DOI is folded back
   into the BibTeX entry.

Rules
-----
- **Never add or drop a paper.** S2 only *enriches* existing Scholar rows. A
  miss leaves ``abstract: null`` and the locally-built BibTeX stands.
- **Graceful degradation (Policy D1).** If S2 is unreachable / rate-limited
  (HTTP 429), enrichment stops and the rest are returned unenriched — the tool
  still succeeds with a full BibTeX Bank.

Examples
--------
python3 tools/scholar_profile.py --from-html gs.html > gs.json
python3 tools/profile_enrich.py --input gs.json --output publications.json
python3 tools/profile_enrich.py --input gs.json --output publications.json --no-network
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

_STOPWORDS = {
    "a", "an", "the", "of", "for", "and", "or", "on", "in", "to", "with",
    "via", "is", "are", "from", "by", "at", "as",
}


# --------------------------------------------------------------------------- #
# helper resolution (integration-contract §2)
# --------------------------------------------------------------------------- #
def _resolve_s2_fetcher() -> str | None:
    here = Path(__file__).resolve().parent
    candidates = [
        here / "semantic_scholar_fetch.py",
        Path(".aris/tools/semantic_scholar_fetch.py"),
        Path("tools/semantic_scholar_fetch.py"),
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    return None


# --------------------------------------------------------------------------- #
# text + key helpers
# --------------------------------------------------------------------------- #
def _norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", (t or "").lower()).strip()


def _tokens(t: str) -> set[str]:
    return {w for w in _norm_title(t).split() if w}


def _title_match(a: str, b: str) -> bool:
    """Confident match: normalized equality or high token-Jaccard overlap."""
    na, nb = _norm_title(a), _norm_title(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    jac = len(ta & tb) / len(ta | tb)
    return jac >= 0.7


def _first_author_surname(authors: str) -> str:
    """'T Guo, X Chen, ...' -> 'guo'."""
    first = (authors or "").split(",")[0].strip()
    parts = first.split()
    surname = parts[-1] if parts else "anon"
    return re.sub(r"[^a-z]", "", surname.lower()) or "anon"


def _first_title_word(title: str) -> str:
    for w in _norm_title(title).split():
        if w not in _STOPWORDS and len(w) > 1:
            return w
    return "paper"


def _entry_type(venue: str) -> str:
    v = (venue or "").lower()
    if not v or "arxiv" in v or "preprint" in v:
        return "misc"
    if any(k in v for k in ("journal", "transactions", "nature", "communications",
                            "review", "letters", "bioinformatics")):
        return "article"
    return "inproceedings"


def _bibtex(paper: dict, key: str) -> str:
    etype = _entry_type(paper.get("venue", ""))
    authors_bib = " and ".join(
        a.strip() for a in (paper.get("authors", "") or "").split(",") if a.strip()
    )
    fields = [("title", paper.get("title", "").strip())]
    if authors_bib:
        fields.append(("author", authors_bib))
    venue = (paper.get("venue", "") or "").strip()
    if venue:
        fields.append(("journal" if etype == "article" else "booktitle", venue))
    if paper.get("year"):
        fields.append(("year", str(paper["year"])))
    if paper.get("doi"):
        fields.append(("doi", paper["doi"]))
    body = ",\n".join(f"  {k} = {{{v}}}" for k, v in fields if v)
    return f"@{etype}{{{key},\n{body}\n}}"


def _make_keys(papers: list[dict]) -> None:
    """Assign a unique, normalized BibTeX key to each paper (mutates)."""
    used: dict[str, int] = {}
    for p in papers:
        base = (
            _first_author_surname(p.get("authors", ""))
            + (str(p.get("year", "")) or "0000")
            + _first_title_word(p.get("title", ""))
        )
        if base in used:
            used[base] += 1
            key = base + chr(ord("a") + used[base])
        else:
            used[base] = 0
            key = base
        p["bibtex_key"] = key


# --------------------------------------------------------------------------- #
# S2 enrichment
# --------------------------------------------------------------------------- #
def _s2_search(fetcher: str, title: str) -> list[dict]:
    proc = subprocess.run(
        ["python3", fetcher, "search", title, "--max", "3"],
        capture_output=True, text=True, timeout=40,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "s2 search failed")
    data = json.loads(proc.stdout or "{}")
    return data.get("data", []) or []


def enrich(papers: list[dict], use_network: bool, delay: float) -> dict:
    fetcher = _resolve_s2_fetcher() if use_network else None
    stats = {"enriched": 0, "missed": 0, "skipped_no_network": 0}
    if not fetcher:
        for p in papers:
            p.setdefault("abstract", None)
            p.setdefault("doi", None)
            stats["skipped_no_network"] += 1
        return stats

    halted = False
    for p in papers:
        p.setdefault("abstract", None)
        p.setdefault("doi", None)
        if halted:
            continue
        try:
            hits = _s2_search(fetcher, p.get("title", ""))
        except Exception as exc:  # noqa: BLE001
            if "429" in str(exc) or "rate" in str(exc).lower():
                halted = True  # stop hammering; rest stay unenriched
            stats["missed"] += 1
            continue
        match = next((h for h in hits if _title_match(p.get("title", ""), h.get("title", ""))), None)
        if not match:
            stats["missed"] += 1
            continue
        if match.get("abstract"):
            p["abstract"] = match["abstract"]
        ext = match.get("externalIds") or {}
        if ext.get("DOI"):
            p["doi"] = ext["DOI"]
        if not p.get("venue") and match.get("venue"):
            p["venue"] = match["venue"]
        stats["enriched"] += 1
        time.sleep(delay)
    return stats


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="Enrich Scholar pubs with abstract/DOI/BibTeX.")
    ap.add_argument("--input", required=True, help="JSON from scholar_profile.py")
    ap.add_argument("--output", required=True, help="Where to write enriched JSON")
    ap.add_argument("--no-network", action="store_true",
                    help="Skip S2; build BibTeX from metadata only.")
    ap.add_argument("--delay", type=float, default=1.0,
                    help="Polite delay (s) between S2 calls (default 1.0).")
    args = ap.parse_args()

    try:
        data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"could not read --input: {exc}"}))
        return 1

    papers = data.get("publications", [])
    if not papers:
        print(json.dumps({"error": "no publications in input"}))
        return 1

    stats = enrich(papers, use_network=not args.no_network, delay=args.delay)
    _make_keys(papers)
    for p in papers:
        p["bibtex"] = _bibtex(p, p["bibtex_key"])

    data["enrichment"] = stats
    data["bibtex_bank"] = "\n\n".join(p["bibtex"] for p in papers)
    Path(args.output).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # human-facing summary on stderr; machine JSON stat line on stdout
    print(json.dumps({
        "ok": True, "output": args.output,
        "papers": len(papers), **stats,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
