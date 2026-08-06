#!/usr/bin/env python3
"""Manage the researcher's personal BibTeX bank.

Used by the `/bib-manager` skill (Module 3 of ARIS personalization). Backed by the
BibTeX Bank that `/profileconstruct` produced (in `researcher-profile/publications.json` or
inline in `PROFILE.md`). Pure stdlib.

Subcommands
-----------
export    Write the bank to a .bib file (from publications.json).
check     Lint a .bib file: duplicate keys, key-naming convention, missing fields.
selfcite  Given a draft (.tex / .md / text), list the researcher's own papers that
          are NOT yet cited — candidate self-citations.

Examples
--------
python3 tools/bib_manager.py export --enriched researcher-profile/publications.json --out mybank.bib
python3 tools/bib_manager.py check paper/references.bib
python3 tools/bib_manager.py selfcite --enriched researcher-profile/publications.json --draft paper/main.tex
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_KEY_RE = re.compile(r"^@(\w+)\s*\{\s*([^,\s]+)\s*,", re.M)
# canonical key: surname + 4-digit year + lowercase word (+ optional dedup letter)
_CANON_KEY = re.compile(r"^[a-z]+\d{4}[a-z0-9]+[a-z]?$")


def _load_bank(enriched: Path) -> list[dict]:
    data = json.loads(enriched.read_text(encoding="utf-8"))
    return data.get("publications", [])


def _cited_keys(text: str) -> set[str]:
    keys: set[str] = set()
    for m in re.findall(r"\\(?:cite|citep|citet|citealp|parencite|textcite)\*?(?:\[[^\]]*\])*\{([^}]*)\}", text):
        keys.update(k.strip() for k in m.split(",") if k.strip())
    return keys


# --------------------------------------------------------------------------- #
def cmd_export(args) -> int:
    bank = _load_bank(Path(args.enriched))
    entries = [p["bibtex"] for p in bank if p.get("bibtex")]
    if not entries:
        print(json.dumps({"error": "no bibtex in bank — run profile_enrich.py first"}))
        return 1
    Path(args.out).write_text("\n\n".join(entries) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "out": args.out, "entries": len(entries)}))
    return 0


def cmd_check(args) -> int:
    text = Path(args.bibfile).read_text(encoding="utf-8", errors="ignore")
    keys = [m.group(2) for m in _KEY_RE.finditer(text)]
    seen: dict[str, int] = {}
    dups, badkeys, missing = [], [], []
    for k in keys:
        seen[k] = seen.get(k, 0) + 1
    dups = [k for k, n in seen.items() if n > 1]
    for k in set(keys):
        if not _CANON_KEY.match(k):
            badkeys.append(k)
    # crude per-entry required-field check
    for block in re.split(r"(?=^@)", text, flags=re.M):
        if not block.strip().startswith("@"):
            continue
        km = _KEY_RE.search(block)
        if not km:
            continue
        key = km.group(2)
        for field in ("title", "year"):
            if not re.search(rf"\b{field}\s*=", block, re.I):
                missing.append(f"{key}: missing {field}")
    report = {
        "entries": len(keys),
        "duplicate_keys": sorted(dups),
        "nonstandard_keys": sorted(badkeys),
        "missing_fields": missing,
        "verdict": "PASS" if not (dups or missing) else "WARN",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["verdict"] == "PASS" else 0  # lint, never hard-fail


def cmd_selfcite(args) -> int:
    bank = _load_bank(Path(args.enriched))
    draft = Path(args.draft).read_text(encoding="utf-8", errors="ignore")
    cited = _cited_keys(draft)
    draft_low = draft.lower()
    suggestions = []
    for p in bank:
        key = p.get("bibtex_key")
        if not key or key in cited:
            continue
        # relevance: any distinctive title token already appears in the draft
        toks = [w for w in re.sub(r"[^a-z0-9 ]", " ", p.get("title", "").lower()).split()
                if len(w) > 4]
        hits = [w for w in toks if w in draft_low]
        if len(hits) >= 2:
            suggestions.append({
                "key": key, "title": p.get("title", ""),
                "year": p.get("year", ""), "matched_terms": hits[:5],
            })
    suggestions.sort(key=lambda s: len(s["matched_terms"]), reverse=True)
    print(json.dumps({
        "cited_self_count": sum(1 for k in cited if any(p.get("bibtex_key") == k for p in bank)),
        "suggested_self_citations": suggestions[:15],
    }, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Personal BibTeX bank manager.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("export"); e.add_argument("--enriched", required=True)
    e.add_argument("--out", required=True); e.set_defaults(fn=cmd_export)

    c = sub.add_parser("check"); c.add_argument("bibfile"); c.set_defaults(fn=cmd_check)

    s = sub.add_parser("selfcite"); s.add_argument("--enriched", required=True)
    s.add_argument("--draft", required=True); s.set_defaults(fn=cmd_selfcite)

    args = ap.parse_args()
    try:
        return args.fn(args)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
