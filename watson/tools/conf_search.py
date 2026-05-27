"""Conference-website paper search.

Fetches acceptance lists directly from official conference proceedings sites,
then scores relevance against the research idea to find the closest papers.

ML:  NeurIPS (papers.nips.cc), ICML (PMLR), ICLR (OpenReview API)
NLP: ACL / EMNLP / NAACL (ACL Anthology)
CV:  CVPR / ICCV / ECCV (CVF Open Access)
"""

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ── Paper-list cache ─────────────────────────────────────────────────────────

_CACHE_TTL_DAYS = 30


def _cache_dir() -> Path:
    from ..config import WATSON_DIR
    d = WATSON_DIR / "conf_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_cache(key: str) -> list[dict] | None:
    path = _cache_dir() / f"{key}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        ts = datetime.fromisoformat(data["ts"])
        if (datetime.now(timezone.utc) - ts).days < _CACHE_TTL_DAYS:
            return data["papers"]
    except Exception:
        pass
    return None


def _save_cache(key: str, papers: list[dict]) -> None:
    try:
        path = _cache_dir() / f"{key}.json"
        path.write_text(
            json.dumps({"ts": datetime.now(timezone.utc).isoformat(), "papers": papers},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


# ── Recent years to search ────────────────────────────────────────────────────

RECENT_YEARS = [2024, 2023, 2022]

# PMLR volume numbers for ICML
PMLR_ICML_VOLS = {2024: 235, 2023: 202, 2022: 162}

# OpenReview venue IDs for ICLR
OPENREVIEW_ICLR_IDS = {
    2024: "ICLR.cc/2024/Conference",
    2023: "ICLR.cc/2023/Conference",
    2022: "ICLR.cc/2022/Conference",
}

# ACL Anthology short codes
ACL_VENUE_CODES = {
    "ACL":   "acl",
    "EMNLP": "emnlp",
    "NAACL": "naacl",
}

# NAACL was not held in 2023; use explicit year list per venue
ACL_VENUE_YEARS: dict[str, list[int]] = {
    "naacl": [2024, 2022],  # 2023 skipped — conference not held
}

# ── HTTP helpers ──────────────────────────────────────────────────────────────

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "Mozilla/5.0 (Watson research assistant)"})


def _get(url: str, params: dict | None = None, timeout: int = 20) -> requests.Response:
    for attempt in range(3):
        try:
            resp = _SESSION.get(url, params=params, timeout=timeout)
            if resp.status_code == 429:
                time.sleep(3 * (attempt + 1))
                continue
            if 400 <= resp.status_code < 500:
                resp.raise_for_status()  # don't retry client errors (404 etc.)
            resp.raise_for_status()
            return resp
        except requests.HTTPError:
            raise
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(2)
    raise RuntimeError(f"Failed to GET {url}")


# ── Keyword relevance scoring ─────────────────────────────────────────────────

_STOPWORDS = {
    "a", "an", "the", "of", "in", "on", "for", "to", "and", "or", "with",
    "via", "by", "is", "are", "from", "using", "based", "towards", "learning",
}


def _score(idea: str, text: str) -> int:
    idea_words = {w.lower() for w in re.split(r"\W+", idea) if len(w) > 2} - _STOPWORDS
    text_words = {w.lower() for w in re.split(r"\W+", text) if len(w) > 2}
    return len(idea_words & text_words)


def rank_and_trim(
    papers: list[dict], idea: str, max_results: int, return_stats: bool = False
) -> "list[dict] | tuple[list[dict], int]":
    """Sort by keyword relevance, filter score==0, return top max_results.

    Stores a normalized 0-5 `relevance_score` on each returned paper.
    With return_stats=True returns (papers, n_relevant) where n_relevant is the
    count of papers with score > 0 before capping at max_results.
    """
    for p in papers:
        p["_score"] = _score(idea, p.get("title", "") + " " + p.get("summary", ""))
    relevant = [p for p in papers if p["_score"] > 0]
    relevant.sort(key=lambda p: p["_score"], reverse=True)
    # Normalize to 0-5: top paper gets 5, rest scaled relative to it
    max_score = relevant[0]["_score"] if relevant else 1
    for p in relevant:
        p["relevance_score"] = max(1, round(p["_score"] / max_score * 5))
        p.pop("_score", None)
    result = relevant[:max_results]
    if return_stats:
        return result, len(relevant)
    return result


# ── CVF Open Access (CVPR / ICCV / ECCV) ────────────────────────────────────

def cvf_venue_years(venue: str) -> list[tuple[str, int]]:
    pairs = []
    for year in RECENT_YEARS:
        if venue == "ICCV" and year % 2 == 0:
            continue  # ICCV is odd years only
        pairs.append((venue, year))
    return pairs


def fetch_cvf_year(venue: str, year: int) -> list[dict]:
    key = f"cvf_{venue}_{year}"
    cached = _load_cache(key)
    if cached is not None:
        return cached
    url = f"https://openaccess.thecvf.com/{venue}{year}?day=all"
    try:
        resp = _get(url, timeout=30)
    except Exception:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    papers: list[dict] = []

    for dt in soup.find_all("dt", class_="ptitle"):
        a = dt.find("a")
        if not a:
            continue
        title = a.get_text(strip=True)
        href  = a.get("href", "")
        link  = f"https://openaccess.thecvf.com{href}" if href.startswith("/") else href
        # Camera-ready PDF: replace the page URL with the PDF URL
        pdf   = link.replace("/html/", "/papers/").replace(".html", ".pdf") if ".html" in link else ""

        authors_dd = dt.find_next_sibling("dd")
        authors_str = authors_dd.get_text(strip=True) if authors_dd else ""
        authors = [a.strip() for a in authors_str.split(",")]

        papers.append({
            "title":      title,
            "summary":    "",
            "link":       link,
            "pdf":        pdf,
            "published":  str(year),
            "authors":    authors,
            "venue":      f"{venue} {year}",
            "source":     "cvf",
            "is_top_conf": True,
        })
    if papers:
        _save_cache(key, papers)
    return papers


def search_cvf(idea: str, venues: list[str], max_results: int = 10) -> list[dict]:
    papers: list[dict] = []
    for venue in venues:
        for v, year in _cvf_venue_years(venue):
            papers.extend(_fetch_cvf_year(v, year))
    return _rank_and_trim(papers, idea, max_results)


# ── ACL Anthology (ACL / EMNLP / NAACL) ─────────────────────────────────────

def fetch_acl_venue_year(venue_code: str, year: int) -> list[dict]:
    key = f"acl_{venue_code}_{year}"
    cached = _load_cache(key)
    if cached is not None:
        return cached
    url = f"https://aclanthology.org/events/{venue_code}-{year}/"
    try:
        resp = _get(url, timeout=30)
    except Exception:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    papers: list[dict] = []

    for strong in soup.find_all("strong"):
        a = strong.find("a")
        if not a:
            continue
        href = a.get("href", "")
        # Anthology IDs look like /2024.acl-long.1/
        if not re.match(r"/\d{4}\.", href):
            continue
        title = a.get_text(strip=True)
        paper_id = href.strip("/").split("/")[-1]
        link  = f"https://aclanthology.org{href}"
        pdf   = f"https://aclanthology.org/{paper_id}.pdf"

        # Authors are in the next sibling text node / em tag
        parent = strong.parent
        em = parent.find("em") if parent else None
        authors_str = em.get_text(strip=True) if em else ""
        authors = [a.strip() for a in authors_str.split(";")]

        venue_label = venue_code.upper()
        papers.append({
            "title":      title,
            "summary":    "",
            "link":       link,
            "pdf":        pdf,
            "published":  str(year),
            "authors":    authors,
            "venue":      f"{venue_label} {year}",
            "source":     "acl_anthology",
            "is_top_conf": True,
        })
    if papers:
        _save_cache(key, papers)
    return papers


def search_acl_anthology(idea: str, venues: list[str], max_results: int = 10) -> list[dict]:
    papers: list[dict] = []
    for venue in venues:
        code = ACL_VENUE_CODES.get(venue.upper(), venue.lower())
        for year in RECENT_YEARS:
            papers.extend(_fetch_acl_venue_year(code, year))
    return _rank_and_trim(papers, idea, max_results)


# ── OpenReview (ICLR) ─────────────────────────────────────────────────────────

def _parse_openreview_note(note: dict, year: int) -> dict:
    """Parse a single OpenReview note (works for both API v1 and v2)."""
    content = note.get("content", {})
    title = content.get("title", {})
    title = title.get("value", title) if isinstance(title, dict) else title
    abstract = content.get("abstract", {})
    abstract = abstract.get("value", abstract) if isinstance(abstract, dict) else abstract
    forum = note.get("forum", "")
    authors_raw = content.get("authors", {})
    if isinstance(authors_raw, dict):
        authors_raw = authors_raw.get("value", [])
    return {
        "title":       title or "",
        "summary":     (abstract or "")[:500],
        "link":        f"https://openreview.net/forum?id={forum}" if forum else "",
        "pdf":         f"https://openreview.net/pdf?id={forum}" if forum else "",
        "published":   str(year),
        "authors":     authors_raw if isinstance(authors_raw, list) else [],
        "venue":       f"ICLR {year}",
        "source":      "openreview",
        "is_top_conf": True,
    }


def _fetch_iclr_v2(year: int, limit: int) -> list[dict]:
    """ICLR 2024+: OpenReview API v2 with content.venue filter."""
    url = "https://api2.openreview.net/notes"
    papers: list[dict] = []
    for venue_str in [f"ICLR {year} poster", f"ICLR {year} oral", f"ICLR {year} spotlight"]:
        try:
            data = _get(url, params={"content.venue": venue_str, "limit": limit}, timeout=30).json()
        except Exception:
            continue
        for note in data.get("notes", []):
            papers.append(_parse_openreview_note(note, year))
    return papers


def _fetch_iclr_v1(year: int) -> list[dict]:
    """ICLR 2022–2023: OpenReview API v1, paginate all submissions, filter accepted."""
    url = "https://api.openreview.net/notes"
    invitation = f"ICLR.cc/{year}/Conference/-/Blind_Submission"
    all_notes: list[dict] = []
    offset = 0
    page_size = 1000
    while True:
        try:
            data = _get(url, params={"invitation": invitation, "limit": page_size, "offset": offset}, timeout=30).json()
        except Exception:
            break
        notes = data.get("notes", [])
        all_notes.extend(notes)
        if len(notes) < page_size:
            break
        offset += page_size

    papers: list[dict] = []
    for note in all_notes:
        venue = note.get("content", {}).get("venue", "")
        # Accepted papers have venue like "ICLR 2022 Poster", "ICLR 2023 notable top 5%", etc.
        # Rejected/under-review papers say "Submitted to ICLR …" or "ICLR … Submitted"
        if not venue or "submitted" in venue.lower():
            continue
        papers.append(_parse_openreview_note(note, year))
    return papers


def fetch_openreview_iclr(year: int, offset: int = 0, limit: int = 200) -> list[dict]:
    key = f"iclr_{year}"
    cached = _load_cache(key)
    if cached is not None:
        return cached

    if year >= 2024:
        papers = _fetch_iclr_v2(year, limit)
    else:
        papers = _fetch_iclr_v1(year)

    if papers:
        _save_cache(key, papers)
    return papers


def search_iclr(idea: str, max_results: int = 10) -> list[dict]:
    papers: list[dict] = []
    for year in RECENT_YEARS:
        papers.extend(_fetch_openreview_iclr(year, limit=200))
    return _rank_and_trim(papers, idea, max_results)


# ── NeurIPS (papers.nips.cc) ──────────────────────────────────────────────────

def fetch_neurips_year(year: int) -> list[dict]:
    key = f"neurips_{year}"
    cached = _load_cache(key)
    if cached is not None:
        return cached
    url = f"https://papers.nips.cc/paper_files/paper/{year}"
    try:
        resp = _get(url, timeout=30)
    except Exception:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    papers: list[dict] = []
    for li in soup.select("ul.paper-list li, li.conference"):
        a = li.find("a")
        if not a:
            continue
        title = a.get_text(strip=True)
        href  = a.get("href", "")
        link  = f"https://papers.nips.cc{href}" if href.startswith("/") else href
        papers.append({
            "title":      title,
            "summary":    "",
            "link":       link,
            "pdf":        "",
            "published":  str(year),
            "authors":    [],
            "venue":      f"NeurIPS {year}",
            "source":     "neurips",
            "is_top_conf": True,
        })
    if papers:
        _save_cache(key, papers)
    return papers


def search_neurips(idea: str, max_results: int = 10) -> list[dict]:
    papers: list[dict] = []
    for year in RECENT_YEARS:
        papers.extend(_fetch_neurips_year(year))
    return _rank_and_trim(papers, idea, max_results)


# ── PMLR / ICML ───────────────────────────────────────────────────────────────

def fetch_pmlr_year(year: int) -> list[dict]:
    key = f"icml_{year}"
    cached = _load_cache(key)
    if cached is not None:
        return cached
    vol = PMLR_ICML_VOLS.get(year)
    if not vol:
        return []
    url = f"https://proceedings.mlr.press/v{vol}/"
    try:
        resp = _get(url, timeout=30)
    except Exception:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    papers: list[dict] = []
    for div in soup.find_all("div", class_="paper"):
        title_tag = div.find("p", class_="title") or div.find("b")
        link_tag  = div.find("a", string=re.compile(r"abs|pdf", re.I))
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)
        href  = link_tag.get("href", "") if link_tag else ""
        link  = href if href.startswith("http") else f"https://proceedings.mlr.press{href}"
        authors_tag = div.find("span", class_="authors")
        authors = [a.strip() for a in (authors_tag.get_text(strip=True) if authors_tag else "").split(",")]
        papers.append({
            "title":      title,
            "summary":    "",
            "link":       link,
            "pdf":        link.replace("/abs/", "/pdf/") if "/abs/" in link else "",
            "published":  str(year),
            "authors":    authors,
            "venue":      f"ICML {year}",
            "source":     "pmlr",
            "is_top_conf": True,
        })
    if papers:
        _save_cache(key, papers)
    return papers


def search_icml(idea: str, max_results: int = 10) -> list[dict]:
    papers: list[dict] = []
    for year in RECENT_YEARS:
        papers.extend(_fetch_pmlr_year(year))
    return _rank_and_trim(papers, idea, max_results)


# ── Public dispatcher ─────────────────────────────────────────────────────────

def search_conf_papers(idea: str, style: str, max_results: int = 10) -> list[dict]:
    """Fetch acceptance-list papers from official conference sites.

    style: "ml" | "nlp" | "cv"
    Returns up to max_results papers ranked by keyword relevance to idea.
    """
    if style == "cv":
        return search_cvf(idea, ["CVPR", "ICCV", "ECCV"], max_results=max_results)

    if style == "nlp":
        return search_acl_anthology(idea, ["ACL", "EMNLP", "NAACL"], max_results=max_results)

    # ml: NeurIPS + ICML + ICLR, merge and re-rank
    pool: list[dict] = []
    pool.extend(search_neurips(idea, max_results=max_results))
    pool.extend(search_icml(idea, max_results=max_results))
    pool.extend(search_iclr(idea, max_results=max_results))
    return _rank_and_trim(pool, idea, max_results)
