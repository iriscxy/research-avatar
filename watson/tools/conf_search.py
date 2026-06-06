"""Conference-website paper search.

Fetches acceptance lists directly from official conference proceedings sites,
then scores relevance against the research idea to find the closest papers.

ML:  NeurIPS (papers.nips.cc), ICML (PMLR), ICLR (OpenReview API)
NLP: ACL / EMNLP / NAACL (ACL Anthology)
CV:  CVPR / ICCV / ECCV (CVF Open Access)
IR/Web/DM: SIGIR / KDD / WWW (DBLP)
"""

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ── Paper-list cache ─────────────────────────────────────────────────────────

_CACHE_TTL_DAYS = 365


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

# PMLR volume numbers for AISTATS
PMLR_AISTATS_VOLS = {2024: 238, 2023: 206, 2022: 151}

# PMLR volume numbers for UAI
PMLR_UAI_VOLS = {2024: 244, 2023: 216, 2022: 180}

# OpenReview venue IDs for ICLR
OPENREVIEW_ICLR_IDS = {
    2024: "ICLR.cc/2024/Conference",
    2023: "ICLR.cc/2023/Conference",
    2022: "ICLR.cc/2022/Conference",
}

# ACL Anthology short codes
ACL_VENUE_CODES = {
    "ACL":    "acl",
    "EMNLP":  "emnlp",
    "NAACL":  "naacl",
    "COLING": "coling",
    "EACL":   "eacl",
}

# Explicit year lists for venues with irregular schedules
ACL_VENUE_YEARS: dict[str, list[int]] = {
    "naacl":  [2024, 2022],        # 2023 skipped — conference not held
    "coling": [2024, 2022],        # biennial
    "eacl":   [2024],              # 2021 outside RECENT_YEARS; no 2022/2023
}

# DBLP venue keys for IR / Web / Data Mining / AI conferences
DBLP_VENUES: dict[str, str] = {
    "SIGIR":  "sigir",
    "KDD":    "kdd",
    "WWW":    "www",
    "AAAI":   "aaai",
    "IJCAI":  "ijcai",
}

# PVLDB journal volume numbers for VLDB (VLDB publishes as PVLDB journal, not conf proceedings)
PVLDB_VOLS: dict[int, int] = {2024: 17, 2023: 16, 2022: 15}

# PACMMOD journal volume numbers for SIGMOD (since 2023 SIGMOD publishes via PACMMOD journal)
# Each volume may contain papers from multiple conference years; filter by DBLP ID year suffix.
PACMMOD_VOLS: dict[int, list[int]] = {
    2024: [1, 2],   # pacmmod1 (issues 3-4) + pacmmod2 (issues 1,3) contain 2024 SIGMOD papers
    2023: [1],      # pacmmod1 (issues 1-2) contains 2023 SIGMOD papers
}

# Venue → research domain mapping
VENUE_CATEGORIES: dict[str, str] = {
    "NeurIPS": "ML",   "ICML": "ML",    "ICLR": "ML",
    "AISTATS": "ML",   "UAI": "ML",
    "ACL": "NLP",      "EMNLP": "NLP",  "NAACL": "NLP",
    "COLING": "NLP",   "EACL": "NLP",
    "CVPR": "CV",      "ICCV": "CV",    "ECCV": "CV",   "WACV": "CV",
    "SIGIR": "IR",     "KDD": "DM",     "WWW": "Web",
    "AAAI": "AI",      "IJCAI": "AI",
    "VLDB": "DB",      "SIGMOD": "DB",
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


# ── BM25 relevance scoring ────────────────────────────────────────────────────

_STOPWORDS = {
    "a", "an", "the", "of", "in", "on", "for", "to", "and", "or", "with",
    "via", "by", "is", "are", "from", "using", "based", "towards", "learning",
}

# Abbreviation → expansion tokens. Applied to BOTH query and paper text so
# "MOE" in a title matches "mixture of experts" in the query and vice versa.
_ABBREV_EXPAND: dict[str, list[str]] = {
    "moe":   ["mixture", "experts"],
    "llm":   ["large", "language", "model"],
    "llms":  ["large", "language", "model"],
    "rag":   ["retrieval", "augmented", "generation"],
    "peft":  ["parameter", "efficient", "fine", "tuning"],
    "lora":  ["low", "rank", "adaptation"],
    "rlhf":  ["reinforcement", "human", "feedback"],
    "sft":   ["supervised", "fine", "tuning"],
    "cot":   ["chain", "thought"],
    "kv":    ["key", "value"],
    "vit":   ["vision", "transformer"],
    "gnn":   ["graph", "neural", "network"],
    "nlp":   ["natural", "language", "processing"],
    "cv":    ["computer", "vision"],
}


def _tokenize(text: str) -> list[str]:
    tokens = [w.lower() for w in re.split(r"\W+", text) if len(w) > 2 and w.lower() not in _STOPWORDS]
    expanded: list[str] = []
    for t in tokens:
        expanded.append(t)
        if t in _ABBREV_EXPAND:
            expanded.extend(_ABBREV_EXPAND[t])
    return expanded


def _bm25_score_papers(papers: list[dict], query: str) -> list[dict]:
    """Score papers against query using BM25; attaches '_score' to each paper."""
    from rank_bm25 import BM25Okapi
    corpus = [_tokenize(p.get("title", "") + " " + p.get("summary", "")) for p in papers]
    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(_tokenize(query))
    for p, s in zip(papers, scores):
        p["_score"] = float(s)
    return papers


def _count_dimension_hits(paper: dict, dimensions: dict) -> int:
    """Count how many dimension groups have at least one keyword hit in paper title+abstract."""
    text = (paper.get("title", "") + " " + paper.get("summary", "")).lower()
    hits = 0
    for keywords in dimensions.values():
        if any(kw.lower() in text for kw in keywords):
            hits += 1
    return hits


def rank_and_trim(
    papers: list[dict], idea: str, max_results: int, return_stats: bool = False
) -> "list[dict] | tuple[list[dict], int]":
    """Score with BM25, filter score==0, return top max_results with normalized 1-5 relevance_score."""
    _bm25_score_papers(papers, idea)
    relevant = [p for p in papers if p["_score"] > 0]
    relevant.sort(key=lambda p: p["_score"], reverse=True)
    max_score = relevant[0]["_score"] if relevant else 1.0
    for p in relevant:
        p["relevance_score"] = max(1, round(p["_score"] / max_score * 5))
        p.pop("_score", None)
    result = relevant[:max_results]
    if return_stats:
        return result, len(relevant)
    return result


def compute_venue_fit_score(venue_counts: dict[str, int], relevant_count: int) -> tuple[int, str]:
    """Return (score 1-5, label) based on how concentrated relevant papers are in one domain.

    5 = ≥70% in one domain (clear target)
    4 = 50-70%
    3 = 35-50%
    2 = 20-35%
    1 = scattered or too few papers
    """
    if relevant_count < 5:
        return 1, "覆盖不足"
    category_counts: dict[str, int] = {}
    for venue, count in venue_counts.items():
        cat = VENUE_CATEGORIES.get(venue, "Other")
        category_counts[cat] = category_counts.get(cat, 0) + count
    if not category_counts:
        return 1, "无法判断"
    top_cat = max(category_counts, key=category_counts.get)
    top_pct = category_counts[top_cat] / relevant_count
    score = 5 if top_pct >= 0.7 else 4 if top_pct >= 0.5 else 3 if top_pct >= 0.35 else 2 if top_pct >= 0.2 else 1
    cat_label = {"ML": "ML 领域", "NLP": "NLP 领域", "CV": "CV 领域"}.get(top_cat, "跨领域")
    return score, f"{cat_label}（{top_pct:.0%}）"


def compute_saturation_risk(top_papers: list[dict]) -> tuple[float, str]:
    """Fraction of top papers with high overlap (score ≥ 4) → saturation signal."""
    if not top_papers:
        return 0.0, "数据不足"
    high = sum(1 for p in top_papers if p.get("relevance_score", 0) >= 4)
    ratio = high / len(top_papers)
    label = "竞争激烈" if ratio >= 0.6 else "竞争中等" if ratio >= 0.3 else "空间充足"
    return ratio, label


def compute_field_vitality(year_counts: dict, venue_counts: dict, competitor_count: int) -> tuple[int, str]:
    """Composite vitality score 1-5 from avg YoY growth + venue breadth + competitor volume."""
    from datetime import datetime
    current_year = str(datetime.now().year)
    score = 0

    # Only 4-digit year keys; exclude current incomplete year; exclude sparse years
    # (< 5% of peak) so API-only years don't distort the trend.
    all_years = sorted(y for y in year_counts if y.isdigit() and len(y) == 4 and y < current_year)
    if all_years:
        peak = max(year_counts.get(y, 0) for y in all_years) or 1
        min_count = max(5, peak * 0.05)
        dense_years = [y for y in all_years if year_counts.get(y, 0) >= min_count]
    else:
        dense_years = []

    if len(dense_years) >= 2:
        # Average YoY growth across all consecutive dense year pairs (more robust than first→last)
        yoy_rates = []
        for i in range(1, len(dense_years)):
            prev = year_counts.get(dense_years[i - 1], 1) or 1
            curr = year_counts.get(dense_years[i], 0)
            yoy_rates.append((curr - prev) / prev * 100)
        avg_growth = sum(yoy_rates) / len(yoy_rates)
        score += 2 if avg_growth > 30 else 1 if avg_growth >= 0 else 0
    else:
        score += 1

    score += 2 if len(venue_counts) >= 4 else 1 if len(venue_counts) >= 2 else 0
    # Use competitor_count (2+ dimension hits) — background papers would inflate the signal
    score += 2 if competitor_count >= 10 else 1 if competitor_count >= 5 else 0

    normalized = max(1, round(score / 6 * 5))
    label = "活跃" if normalized >= 4 else "平稳" if normalized >= 3 else "低迷"
    return normalized, label


def compute_metrics(pool: list[dict], idea: str, max_results: int = 10,
                    dimensions: dict | None = None) -> dict:
    """Score all papers with BM25, apply two-tier filtering if dimensions provided.

    With dimensions:
      - competitor (tier='competitor'): 2+ dimension groups hit → direct novelty threat
      - background (tier='background'): exactly 1 dimension group hit → validates problem value
    Without dimensions: all BM25>0 papers treated as competitors (fallback).
    """
    if pool:
        _bm25_score_papers(pool, idea)

    if dimensions:
        competitors, background = [], []
        for p in pool:
            hits = _count_dimension_hits(p, dimensions)
            if hits >= 2:
                p["tier"] = "competitor"
                competitors.append(p)
            elif hits == 1:
                p["tier"] = "background"
                background.append(p)
        competitors.sort(key=lambda p: p.get("_score", 0), reverse=True)
        background.sort(key=lambda p: p.get("_score", 0), reverse=True)
        relevant = competitors + background
    else:
        relevant = [p for p in pool if p.get("_score", 0) > 0]
        relevant.sort(key=lambda p: p["_score"], reverse=True)
        for p in relevant:
            p["tier"] = "competitor"
        competitors, background = relevant, []

    if not relevant:
        return {
            "top_papers": [], "all_relevant_papers": [],
            "competitor_count": 0, "background_count": 0,
            "relevant_count": 0, "pool_size": len(pool), "density": 0,
            "year_counts": {}, "venue_counts": {}, "avg_score": 0,
            "venue_fit_score": 1, "venue_fit_label": "数据不足",
            "saturation_ratio": 0.0, "saturation_label": "数据不足",
            "vitality_score": 1, "vitality_label": "低迷",
        }

    max_score = relevant[0].get("_score", 1.0) or 1.0
    for p in relevant:
        p["relevance_score"] = max(1, round(p.get("_score", 0) / max_score * 5))
        p.pop("_score", None)

    # top_papers = top competitors (these get LLM annotation)
    top = competitors[:max_results]

    # Year/venue counts from competitors only (2+ dimension hits) for a focused vitality signal.
    # Background papers (1 dimension) would inflate the trend with loosely-related work.
    count_source = competitors if competitors else relevant
    year_counts: dict[str, int] = {}
    for p in count_source:
        yr = p.get("published", "")[:4]  # normalise "2022-11-01" → "2022"
        if yr.isdigit():
            year_counts[yr] = year_counts.get(yr, 0) + 1

    venue_counts: dict[str, int] = {}
    for p in count_source:
        venue = p.get("venue", "")
        conf = venue.split()[0] if venue else "Unknown"
        venue_counts[conf] = venue_counts.get(conf, 0) + 1

    scores = [p["relevance_score"] for p in top if p.get("relevance_score")]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    venue_fit_score, venue_fit_label = compute_venue_fit_score(venue_counts, len(relevant))
    saturation_ratio, saturation_label = compute_saturation_risk(top)
    vitality_score, vitality_label = compute_field_vitality(year_counts, venue_counts, len(competitors))

    return {
        "top_papers":          top,
        "all_relevant_papers": relevant,
        "competitor_count":    len(competitors),
        "background_count":    len(background),
        "relevant_count":      len(relevant),
        "pool_size":           len(pool),
        "density":             len(relevant) / len(pool) if pool else 0,
        "year_counts":         year_counts,
        "venue_counts":        venue_counts,
        "avg_score":           avg_score,
        "venue_fit_score":     venue_fit_score,
        "venue_fit_label":     venue_fit_label,
        "saturation_ratio":    saturation_ratio,
        "saturation_label":    saturation_label,
        "vitality_score":      vitality_score,
        "vitality_label":      vitality_label,
    }


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


# ── ECVA (ECCV) ───────────────────────────────────────────────────────────────

def fetch_ecva_year(year: int) -> list[dict]:
    """Fetch ECCV papers from ecva.net (all years on one page, cached per year)."""
    key = f"eccv_{year}"
    cached = _load_cache(key)
    if cached is not None:
        return cached

    url = "https://www.ecva.net/papers.php"
    try:
        resp = _get(url, timeout=40)
    except Exception:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    from collections import defaultdict
    year_papers: dict[str, list] = defaultdict(list)

    for dt in soup.find_all("dt", class_="ptitle"):
        a = dt.find("a")
        if not a:
            continue
        href = a.get("href", "")
        m = re.match(r"papers/eccv_(\d{4})/", href)
        if not m:
            continue
        p_year = m.group(1)
        title = a.get_text(strip=True)
        link  = f"https://www.ecva.net/{href}"
        pdf   = re.sub(r"/html/(.+)_paper\.php$", r"/\1.pdf", link) if "/html/" in link else ""

        authors_dd = dt.find_next_sibling("dd")
        authors_str = authors_dd.get_text(strip=True) if authors_dd else ""
        authors = [s.strip() for s in authors_str.split(",") if s.strip()]

        year_papers[p_year].append({
            "title":       title,
            "summary":     "",
            "link":        link,
            "pdf":         pdf,
            "published":   p_year,
            "authors":     authors[:5],
            "venue":       f"ECCV {p_year}",
            "source":      "ecva",
            "is_top_conf": True,
        })

    # Cache every year found so subsequent per-year calls are instant
    for yr, papers in year_papers.items():
        if papers:
            _save_cache(f"eccv_{yr}", papers)

    return year_papers.get(str(year), [])


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


def fetch_pmlr_volume(venue_name: str, vol: int, year: int) -> list[dict]:
    """Generic PMLR volume fetcher (for AISTATS, UAI, and future venues)."""
    key = f"pmlr_v{vol}"
    cached = _load_cache(key)
    if cached is not None:
        return cached
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
            "title":       title,
            "summary":     "",
            "link":        link,
            "pdf":         link.replace("/abs/", "/pdf/") if "/abs/" in link else "",
            "published":   str(year),
            "authors":     authors,
            "venue":       f"{venue_name} {year}",
            "source":      "pmlr",
            "is_top_conf": True,
        })
    if papers:
        _save_cache(key, papers)
    return papers


def fetch_aistats_year(year: int) -> list[dict]:
    vol = PMLR_AISTATS_VOLS.get(year)
    return fetch_pmlr_volume("AISTATS", vol, year) if vol else []


def fetch_uai_year(year: int) -> list[dict]:
    vol = PMLR_UAI_VOLS.get(year)
    return fetch_pmlr_volume("UAI", vol, year) if vol else []


def search_icml(idea: str, max_results: int = 10) -> list[dict]:
    papers: list[dict] = []
    for year in RECENT_YEARS:
        papers.extend(fetch_pmlr_year(year))
    return _rank_and_trim(papers, idea, max_results)


# ── DBLP (SIGIR / KDD / WWW) ─────────────────────────────────────────────────

def fetch_dblp_venue_year(venue_name: str, dblp_key: str, year: int) -> list[dict]:
    """Fetch accepted papers from DBLP proceedings page.

    URL pattern: https://dblp.org/db/conf/{dblp_key}/{dblp_key}{year}.html
    Used for SIGIR, KDD, and WWW (The Web Conference).
    """
    key = f"dblp_{dblp_key}_{year}"
    cached = _load_cache(key)
    if cached is not None:
        return cached

    url = f"https://dblp.org/db/conf/{dblp_key}/{dblp_key}{year}.html"
    try:
        resp = _get(url, timeout=30)
    except Exception:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    papers: list[dict] = []

    for li in soup.select("li.entry.inproceedings"):
        # Title
        title_tag = li.find("span", class_="title")
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True).rstrip(".")
        if not title:
            continue

        # Authors: <a> tags inside the data div linking to dblp.org/pid/
        data_div = li.find("div", class_="data") or li
        authors = [
            a.get_text(strip=True)
            for a in data_div.find_all("a", href=re.compile(r"dblp\.org/pid/"))
        ]

        # Link: prefer DOI, fall back to first external link in <nav>
        link = ""
        nav = li.find("nav")
        if nav:
            doi_a = nav.find("a", href=re.compile(r"doi\.org/"))
            if doi_a:
                link = doi_a["href"]
            else:
                first_a = nav.find("a", href=True)
                if first_a:
                    link = first_a["href"]

        papers.append({
            "title": title,
            "summary": "",
            "link": link,
            "pdf": "",
            "published": str(year),
            "authors": authors[:5],
            "venue": f"{venue_name} {year}",
            "source": "dblp",
            "is_top_conf": True,
        })

    if papers:
        _save_cache(key, papers)
    return papers


# ── VLDB (PVLDB journal on DBLP) ─────────────────────────────────────────────

def _parse_dblp_article_entries(soup: "BeautifulSoup", entry_type: str,
                                venue_name: str, year: int,
                                id_suffix: str | None = None) -> list[dict]:
    """Parse DBLP HTML page into paper dicts.

    entry_type: "article" or "inproceedings"
    id_suffix:  if given, only include entries whose DBLP id ends with this suffix
    """
    papers: list[dict] = []
    for li in soup.select(f"li.entry.{entry_type}"):
        if id_suffix and not li.get("id", "").endswith(id_suffix):
            continue
        title_tag = li.find("span", class_="title")
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True).rstrip(".")
        if not title:
            continue
        data_div = li.find("div", class_="data") or li
        authors = [
            a.get_text(strip=True)
            for a in data_div.find_all("a", href=re.compile(r"dblp\.org/pid/"))
        ]
        link = ""
        nav = li.find("nav")
        if nav:
            doi_a = nav.find("a", href=re.compile(r"doi\.org/"))
            if doi_a:
                link = doi_a["href"]
            else:
                first_a = nav.find("a", href=True)
                if first_a:
                    link = first_a["href"]
        papers.append({
            "title": title,
            "summary": "",
            "link": link,
            "pdf": "",
            "published": str(year),
            "authors": authors[:5],
            "venue": f"{venue_name} {year}",
            "source": "dblp",
            "is_top_conf": True,
        })
    return papers


def fetch_vldb_year(year: int) -> list[dict]:
    """Fetch VLDB papers from the PVLDB journal page on DBLP."""
    vol = PVLDB_VOLS.get(year)
    if not vol:
        return []
    key = f"vldb_{year}"
    cached = _load_cache(key)
    if cached is not None:
        return cached
    url = f"https://dblp.org/db/journals/pvldb/pvldb{vol}.html"
    try:
        resp = _get(url, timeout=30)
    except Exception:
        return []
    soup = BeautifulSoup(resp.text, "lxml")
    papers = _parse_dblp_article_entries(soup, "article", "VLDB", year)
    if papers:
        _save_cache(key, papers)
    return papers


# ── SIGMOD (traditional 2022, PACMMOD journal 2023+) ─────────────────────────

def fetch_sigmod_year(year: int) -> list[dict]:
    """Fetch SIGMOD papers from DBLP.

    2022 and earlier: standard conf proceedings (sigmod{year}.html, inproceedings).
    2023+: PACMMOD journal pages, filtered by DBLP ID year suffix.
    """
    key = f"sigmod_{year}"
    cached = _load_cache(key)
    if cached is not None:
        return cached

    papers: list[dict] = []
    if year <= 2022:
        url = f"https://dblp.org/db/conf/sigmod/sigmod{year}.html"
        try:
            resp = _get(url, timeout=30)
            soup = BeautifulSoup(resp.text, "lxml")
            papers = _parse_dblp_article_entries(soup, "inproceedings", "SIGMOD", year)
        except Exception:
            pass
    else:
        yr_suffix = str(year)[-2:]
        for vol in PACMMOD_VOLS.get(year, []):
            url = f"https://dblp.org/db/journals/pacmmod/pacmmod{vol}.html"
            try:
                resp = _get(url, timeout=30)
                soup = BeautifulSoup(resp.text, "lxml")
                papers.extend(_parse_dblp_article_entries(
                    soup, "article", "SIGMOD", year, id_suffix=yr_suffix
                ))
            except Exception:
                continue

    if papers:
        _save_cache(key, papers)
    return papers


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
