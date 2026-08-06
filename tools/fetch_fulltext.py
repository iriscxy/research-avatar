#!/usr/bin/env python3
"""Fetch abstracts + full-text PDFs for a Scholar publication list.

Stdlib-only (urllib + xml.etree) plus the external ``pdftotext`` binary for
text extraction. Multi-source, resumable, cache-first (W2/W3): nothing is
re-downloaded or clobbered; a run can be interrupted and resumed.

Per paper, in priority order:
  abstract/DOI/arxiv-id : arXiv API  ->  Crossref  ->  Semantic Scholar (backoff)  ->  DBLP
  open PDF              : arXiv pdf  ->  S2 openAccessPdf  ->  ACL anthology (via DOI)
                          ->  ACL anthology (via DBLP `ee`)  ->  Unpaywall
DBLP is the DOI-less/arXiv-less bridge: it resolves a DOI and/or a direct ACL
Anthology URL by title, so conference papers with no arXiv id (ACL/EMNLP/NAACL/
AAAI/IJCAI/SIGIR) are no longer silently skipped when Crossref/S2 are throttled.
Closed venues (IEEE / TOIS / Nature / closed AAAI) typically yield abstract
only; full text is marked unavailable, never faked.

Layout (under --outdir, default <profile>/fulltext):
  pdf/<key>.pdf   txt/<key>.txt   index.json
Abstracts are also merged back into the --enriched JSON in place.

Examples
--------
python3 tools/fetch_fulltext.py --enriched researcher-profile/publications.json --keys guo2024large --limit 5
python3 tools/fetch_fulltext.py --enriched researcher-profile/publications.json          # full run
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

UA = "research-buddy/1.0 (mailto:zzs144118@gmail.com)"
MAILTO = "zzs144118@gmail.com"


# --------------------------------------------------------------------------- #
# title matching (mirrors profile_enrich.py)
# --------------------------------------------------------------------------- #
def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", (t or "").lower())).strip()


def _toks(t: str) -> set[str]:
    return {w for w in _norm(t).split() if w}


def title_match(a: str, b: str) -> bool:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    ta, tb = _toks(a), _toks(b)
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= 0.7


# --------------------------------------------------------------------------- #
# http
# --------------------------------------------------------------------------- #
def http(url: str, *, timeout: int = 30, retries: int = 4, backoff: float = 3.0,
         binary: bool = False, headers: dict | None = None):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
                return data if binary else data.decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429 or 500 <= e.code < 600:
                time.sleep(backoff * (i + 1))
                continue
            return None
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(backoff * (i + 1))
    return None


# --------------------------------------------------------------------------- #
# sources
# --------------------------------------------------------------------------- #
def arxiv_lookup(title: str):
    """-> (arxiv_id, abstract) or (None, None)."""
    q = urllib.parse.quote(f'ti:"{title}"')
    url = f"http://export.arxiv.org/api/query?search_query={q}&max_results=5"
    xml = http(url, retries=3)
    if not xml:
        # fallback: loose all-field query
        q2 = urllib.parse.quote(f'all:{title}')
        xml = http(f"http://export.arxiv.org/api/query?search_query={q2}&max_results=5", retries=2)
    if not xml:
        return None, None
    ns = {"a": "http://www.w3.org/2005/Atom"}
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return None, None
    for e in root.findall("a:entry", ns):
        t = (e.findtext("a:title", default="", namespaces=ns) or "").strip()
        if title_match(title, t):
            idu = (e.findtext("a:id", default="", namespaces=ns) or "")
            m = re.search(r"abs/([0-9]+\.[0-9]+)", idu)
            aid = m.group(1) if m else None
            summ = (e.findtext("a:summary", default="", namespaces=ns) or "").strip()
            return aid, (re.sub(r"\s+", " ", summ) or None)
    return None, None


def arxiv_by_id(aid: str):
    """Fetch abstract for a known arXiv id via the id_list query."""
    url = f"http://export.arxiv.org/api/query?id_list={urllib.parse.quote(aid)}&max_results=1"
    xml = http(url, retries=3)
    if not xml:
        return None
    ns = {"a": "http://www.w3.org/2005/Atom"}
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return None
    e = root.find("a:entry", ns)
    if e is None:
        return None
    summ = (e.findtext("a:summary", default="", namespaces=ns) or "").strip()
    return re.sub(r"\s+", " ", summ) or None


def _strip_jats(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", s).strip()


def crossref_lookup(title: str):
    """-> (doi, abstract) or (None, None)."""
    q = urllib.parse.quote(title)
    url = (f"https://api.crossref.org/works?query.bibliographic={q}"
           f"&rows=5&mailto={MAILTO}")
    raw = http(url, retries=3)
    if not raw:
        return None, None
    try:
        items = json.loads(raw)["message"]["items"]
    except Exception:  # noqa: BLE001
        return None, None
    for it in items:
        t = " ".join(it.get("title") or [])
        if t and title_match(title, t):
            doi = it.get("DOI")
            abs = _strip_jats(it.get("abstract", "")) or None
            return doi, abs
    return None, None


def s2_lookup(title: str):
    """-> (abstract, doi, openpdf_url) best-effort; heavy backoff on 429."""
    q = urllib.parse.quote(title)
    fields = "title,abstract,externalIds,openAccessPdf"
    url = (f"https://api.semanticscholar.org/graph/v1/paper/search"
           f"?query={q}&limit=5&fields={fields}")
    raw = http(url, retries=5, backoff=6.0)
    if not raw:
        return None, None, None
    try:
        data = json.loads(raw).get("data") or []
    except Exception:  # noqa: BLE001
        return None, None, None
    for h in data:
        if title_match(title, h.get("title", "")):
            doi = (h.get("externalIds") or {}).get("DOI")
            pdf = (h.get("openAccessPdf") or {}).get("url")
            return h.get("abstract"), doi, pdf
    return None, None, None


def unpaywall_pdf(doi: str):
    if not doi:
        return None
    url = f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi)}?email={MAILTO}"
    raw = http(url, retries=3)
    if not raw:
        return None
    try:
        loc = (json.loads(raw).get("best_oa_location") or {})
        return loc.get("url_for_pdf") or None
    except Exception:  # noqa: BLE001
        return None


def acl_pdf_from_doi(doi: str):
    # ACL Anthology DOIs: 10.18653/v1/<anthology-id> (DBLP returns them UPPERCASE;
    # Anthology ids are lowercase, so match case-insensitively and lowercase the stub).
    if doi:
        m = re.search(r"10\.18653/v1/(.+)$", doi, re.IGNORECASE)
        if m:
            return f"https://aclanthology.org/{m.group(1).lower()}.pdf"
    return None


def acl_pdf_from_url(url: str):
    """An ACL Anthology page URL -> its .pdf URL.
    e.g. https://aclanthology.org/2021.acl-long.473  ->  .../2021.acl-long.473.pdf"""
    if not url or "aclanthology.org" not in url:
        return None
    m = re.search(r"aclanthology\.org/([^/?#]+?)/?$", url)
    if not m:
        return None
    stub = m.group(1)
    if stub.endswith(".pdf"):
        return url if url.startswith("http") else f"https://{url}"
    return f"https://aclanthology.org/{stub}.pdf"


def dblp_lookup(title: str):
    """DBLP title search -> (doi, pdf_url) or (None, None).

    The DOI-less/arXiv-less bridge to ACL Anthology & co. DBLP is un-throttled and
    covers ACL/EMNLP/NAACL/AAAI/IJCAI/SIGIR; its ``ee`` field is usually the ACL
    Anthology page (or a doi.org link), so a conference paper with NO arXiv id and
    NO resolved DOI (e.g. when Crossref/S2 were rate-limited) is still reachable.
    """
    q = urllib.parse.quote(title)
    url = f"https://dblp.org/search/publ/api?q={q}&format=json&h=5"
    raw = http(url, retries=3)
    if not raw:
        return None, None
    try:
        hits = json.loads(raw)["result"]["hits"].get("hit", [])
    except Exception:  # noqa: BLE001
        return None, None
    if isinstance(hits, dict):  # DBLP returns a bare object for a single hit
        hits = [hits]
    for h in hits:
        info = h.get("info", {})
        if not title_match(title, info.get("title", "")):
            continue
        doi = info.get("doi")
        ee = info.get("ee")
        if isinstance(ee, list):
            ee = next((u for u in ee if "aclanthology.org" in u), ee[0] if ee else None)
        return doi, ee
    return None, None


# --------------------------------------------------------------------------- #
# pdf
# --------------------------------------------------------------------------- #
def download_pdf(url: str, dest: Path) -> bool:
    data = http(url, binary=True, timeout=60, retries=3)
    if not data or len(data) < 1000 or not data[:5].startswith(b"%PDF"):
        return False
    dest.write_bytes(data)
    return True


def extract_text(pdf: Path, txt: Path) -> int:
    try:
        subprocess.run(["pdftotext", "-q", str(pdf), str(txt)],
                       check=True, timeout=120)
    except Exception:  # noqa: BLE001
        return 0
    if txt.exists():
        return len(txt.read_text("utf-8", "replace"))
    return 0


# --------------------------------------------------------------------------- #
# per-paper
# --------------------------------------------------------------------------- #
def process(p: dict, outdir: Path, use_s2: bool, delay: float) -> dict:
    key = p.get("bibtex_key") or "nokey"
    title = p.get("title", "")
    rec = {"key": key, "title": title, "abstract_source": None,
           "doi": p.get("doi"), "arxiv_id": None, "pdf_source": None,
           "pdf_url": None, "txt_chars": 0, "status": "pending"}

    abstract = p.get("abstract")
    doi = p.get("doi")
    arxiv_id = None

    # 0) arXiv id straight from an arXiv DOI (10.48550/arXiv.<id>)
    m = re.search(r"10\.48550/arxiv\.([0-9]+\.[0-9]+)", (doi or "").lower())
    if m:
        arxiv_id = m.group(1)
        rec["arxiv_id"] = arxiv_id
        if not abstract:
            id_abs = arxiv_by_id(arxiv_id)
            if id_abs:
                abstract, rec["abstract_source"] = id_abs, "arxiv"
        time.sleep(delay)

    # 1) arXiv (abstract + id)
    aid, a_abs = arxiv_lookup(title) if not arxiv_id else (arxiv_id, None)
    if aid:
        arxiv_id = aid
        rec["arxiv_id"] = aid
        if not abstract and a_abs:
            abstract, rec["abstract_source"] = a_abs, "arxiv"
    time.sleep(delay)

    # 2) Crossref (doi + maybe abstract)
    if not doi or not abstract:
        c_doi, c_abs = crossref_lookup(title)
        doi = doi or c_doi
        if not abstract and c_abs:
            abstract, rec["abstract_source"] = c_abs, "crossref"
        time.sleep(delay)

    # 3) S2 fallback (abstract + open pdf)
    s2_pdf = None
    if use_s2 and (not abstract or not doi):
        s_abs, s_doi, s_pdf = s2_lookup(title)
        doi = doi or s_doi
        s2_pdf = s_pdf
        if not abstract and s_abs:
            abstract, rec["abstract_source"] = s_abs, "s2"
        time.sleep(delay)

    # 3.5) DBLP fallback (un-throttled) — the fix for no-arXiv conference papers:
    #      resolve a DOI and/or a direct ACL-Anthology PDF URL by title when the
    #      arXiv/Crossref/S2 chain gave neither. Run whenever there is no arXiv id.
    dblp_pdf = None
    if not arxiv_id:
        d_doi, d_ee = dblp_lookup(title)
        doi = doi or d_doi
        dblp_pdf = acl_pdf_from_url(d_ee) if d_ee else None
        time.sleep(delay)

    if abstract:
        p["abstract"] = abstract
        if rec["abstract_source"] is None:
            rec["abstract_source"] = "preexisting"
    if doi:
        p["doi"] = doi
        rec["doi"] = doi

    # ---- PDF acquisition ----
    pdf_dir = outdir / "pdf"
    txt_dir = outdir / "txt"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    txt_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = pdf_dir / f"{key}.pdf"
    txt_path = txt_dir / f"{key}.txt"

    # resume: already have text
    if txt_path.exists() and len(txt_path.read_text("utf-8", "replace")) > 500:
        rec["txt_chars"] = len(txt_path.read_text("utf-8", "replace"))
        rec["pdf_source"] = "cached"
        rec["status"] = "done"
        return rec

    candidates = []
    if arxiv_id:
        candidates.append(("arxiv", f"https://arxiv.org/pdf/{arxiv_id}"))
    if s2_pdf:
        candidates.append(("s2", s2_pdf))
    acl = acl_pdf_from_doi(doi)
    if acl:
        candidates.append(("acl", acl))
    if dblp_pdf:
        candidates.append(("acl-dblp", dblp_pdf))
    up = unpaywall_pdf(doi)
    if up:
        candidates.append(("unpaywall", up))

    got = pdf_path.exists() and pdf_path.stat().st_size > 1000
    if got:
        rec["pdf_source"] = "cached"
    for src, url in candidates:
        if got:
            break
        if download_pdf(url, pdf_path):
            rec["pdf_source"], rec["pdf_url"], got = src, url, True
        time.sleep(delay)

    if got:
        rec["txt_chars"] = extract_text(pdf_path, txt_path)
        rec["status"] = "done" if rec["txt_chars"] > 500 else "pdf_no_text"
    else:
        rec["status"] = "abstract_only" if abstract else "nothing"
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--enriched", required=True)
    ap.add_argument("--outdir", default=None, help="default <enriched dir>/fulltext")
    ap.add_argument("--keys", default=None, help="comma-sep bibtex_keys to limit to")
    ap.add_argument("--limit", type=int, default=0, help="first N papers (0=all)")
    ap.add_argument("--no-s2", action="store_true")
    ap.add_argument("--delay", type=float, default=1.5)
    args = ap.parse_args()

    enriched = Path(args.enriched)
    data = json.loads(enriched.read_text("utf-8"))
    pubs = data.get("publications", [])
    outdir = Path(args.outdir) if args.outdir else enriched.parent / "fulltext"
    outdir.mkdir(parents=True, exist_ok=True)
    idx_path = outdir / "index.json"
    index = {}
    if idx_path.exists():
        try:
            index = {r["key"]: r for r in json.loads(idx_path.read_text("utf-8"))}
        except Exception:  # noqa: BLE001
            index = {}

    sel = pubs
    if args.keys:
        want = set(args.keys.split(","))
        sel = [p for p in pubs if p.get("bibtex_key") in want]
    if args.limit:
        sel = sel[:args.limit]

    for i, p in enumerate(sel, 1):
        key = p.get("bibtex_key")
        rec = process(p, outdir, use_s2=not args.no_s2, delay=args.delay)
        index[key] = rec
        # persist incrementally (resumable + crash-safe)
        idx_path.write_text(json.dumps(list(index.values()), ensure_ascii=False, indent=2), "utf-8")
        enriched.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
        print(f"[{i}/{len(sel)}] {key:30.30} abs={rec['abstract_source'] or '-':10.10} "
              f"pdf={rec['pdf_source'] or '-':9.9} txt={rec['txt_chars']:>7} {rec['status']}",
              flush=True)

    done = sum(1 for r in index.values() if r["status"] == "done")
    ab = sum(1 for r in index.values() if r["status"] == "abstract_only")
    print(json.dumps({"processed": len(sel), "fulltext": done,
                      "abstract_only": ab, "total_indexed": len(index)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
