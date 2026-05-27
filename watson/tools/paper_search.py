"""Paper search across arXiv and Semantic Scholar.

For idea validation we run two separate searches as required:
  1. Most-similar papers (by topic/contribution).
  2. Recent papers from top CS conferences (CCF A/B class).
"""

import time
import xml.etree.ElementTree as ET
import requests

from ..config import SEMANTIC_SCHOLAR_API_KEY


def _get(url: str, params: dict, timeout: int = 30, retries: int = 3) -> requests.Response:
    """GET with exponential backoff on 429."""
    for attempt in range(retries):
        resp = requests.get(url, params=params, timeout=timeout)
        if resp.status_code == 429:
            wait = 2 ** attempt * 3   # 3s, 6s, 12s
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp
    resp.raise_for_status()
    return resp

ARXIV_API = "http://export.arxiv.org/api/query"
S2_API = "https://api.semanticscholar.org/graph/v1/paper/search"

# Venues considered CCF A or B for CS (NLP/ML/AI/CV tracks)
CCF_AB_VENUES = {
    # CCF-A
    "NeurIPS", "ICML", "ICLR", "CVPR", "ICCV", "ACL", "EMNLP",
    "SIGIR", "KDD", "AAAI", "IJCAI", "WWW", "VLDB", "SIGMOD",
    "STOC", "FOCS", "CCS", "S&P", "USENIX Security",
    # CCF-B
    "NAACL", "COLING", "EACL", "ECML", "CIKM", "WSDM", "ECIR",
    "ECCV", "BMVC", "UAI", "AISTATS",
}


# ── arXiv ─────────────────────────────────────────────────────────────────────

def _search_arxiv(query: str, max_results: int = 10) -> list[dict]:
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    resp = _get(ARXIV_API, params)

    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(resp.content)
    papers: list[dict] = []

    for entry in root.findall("a:entry", ns):
        title_el = entry.find("a:title", ns)
        summary_el = entry.find("a:summary", ns)
        link_el = entry.find("a:id", ns)
        published_el = entry.find("a:published", ns)
        authors = [
            a.find("a:name", ns).text
            for a in entry.findall("a:author", ns)
            if a.find("a:name", ns) is not None
        ]
        if title_el is None:
            continue
        papers.append({
            "title": title_el.text.strip().replace("\n", " "),
            "summary": (summary_el.text or "").strip().replace("\n", " ") if summary_el is not None else "",
            "link": link_el.text.strip() if link_el is not None else "",
            "published": (published_el.text or "")[:10] if published_el is not None else "",
            "authors": authors,
            "venue": "arXiv",
            "source": "arxiv",
            "is_top_conf": False,
        })
    return papers


# ── Semantic Scholar ───────────────────────────────────────────────────────────

def _search_s2(query: str, max_results: int = 10) -> list[dict]:
    headers = {"x-api-key": SEMANTIC_SCHOLAR_API_KEY} if SEMANTIC_SCHOLAR_API_KEY else {}
    params = {
        "query": query,
        "limit": max_results,
        "fields": "title,abstract,year,authors,externalIds,venue,publicationVenue",
    }
    try:
        resp = _get(S2_API, params, timeout=30)
        data = resp.json()
    except Exception:
        return []

    papers: list[dict] = []
    for p in data.get("data", []):
        arxiv_id = (p.get("externalIds") or {}).get("ArXiv", "")
        link = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else ""
        raw_venue = (
            (p.get("publicationVenue") or {}).get("name")
            or p.get("venue")
            or ""
        )
        is_top = _is_top_conf(raw_venue)
        papers.append({
            "title": p.get("title", ""),
            "summary": p.get("abstract") or "",
            "link": link,
            "published": str(p.get("year", "")),
            "authors": [a["name"] for a in (p.get("authors") or [])],
            "venue": raw_venue,
            "source": "semantic_scholar",
            "is_top_conf": is_top,
        })
    return papers


def _is_top_conf(venue: str) -> bool:
    if not venue:
        return False
    v = venue.upper()
    return any(c.upper() in v for c in CCF_AB_VENUES)


# ── Deduplication ─────────────────────────────────────────────────────────────

def _dedup(papers: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for p in papers:
        key = p["title"].lower()[:60]
        if key not in seen:
            seen.add(key)
            result.append(p)
    return result


# ── Public API ────────────────────────────────────────────────────────────────

def search_similar(idea: str, max_results: int = 10) -> list[dict]:
    """Find the most thematically similar papers to an idea."""
    results: list[dict] = []
    try:
        results += _search_arxiv(idea, max_results)
    except Exception:
        pass
    try:
        results += _search_s2(idea, max_results)
    except Exception:
        pass
    return _dedup(results)[:max_results]


def search_top_conf(idea: str, max_results: int = 10, venue_query: str = "", style: str = "") -> list[dict]:
    """Find recent papers at top conferences.

    When style is given ("ml"/"nlp"/"cv"), fetches directly from the official
    conference acceptance lists. Falls back to arXiv/S2 on failure.
    """
    if style:
        try:
            from .conf_search import search_conf_papers
            results = search_conf_papers(idea, style, max_results=max_results)
            if results:
                return results
        except Exception:
            pass

    # Fallback: arXiv + Semantic Scholar
    conf_terms = venue_query or "NeurIPS OR ICML OR ICLR OR ACL OR EMNLP OR CVPR OR AAAI OR IJCAI"
    query = f"({idea}) AND ({conf_terms})"
    results: list[dict] = []
    try:
        results += _search_arxiv(query, max_results)
    except Exception:
        pass
    try:
        results += _search_s2(query, max_results)
    except Exception:
        pass
    papers = _dedup(results)
    papers.sort(key=lambda p: (0 if p["is_top_conf"] else 1))
    return papers[:max_results]


def search_all(idea: str, n_similar: int = 8, n_top_conf: int = 8, venue_query: str = "", style: str = "") -> tuple[list[dict], list[dict]]:
    """Return (similar_papers, top_conf_papers), deduplicated within each group."""
    similar = search_similar(idea, n_similar)
    top = search_top_conf(idea, n_top_conf, venue_query=venue_query, style=style)
    # Remove top-conf papers that are already in similar so the LLM sees distinct sets
    similar_titles = {p["title"].lower()[:60] for p in similar}
    top = [p for p in top if p["title"].lower()[:60] not in similar_titles]
    return similar, top


def format_papers(papers: list[dict], label: str = "") -> str:
    if not papers:
        return f"*{label}: 未找到相关论文*\n"
    lines: list[str] = []
    if label:
        lines.append(f"### {label}")
    for i, p in enumerate(papers, 1):
        authors_str = ", ".join(p.get("authors", [])[:3])
        if len(p.get("authors", [])) > 3:
            authors_str += " et al."
        top_flag = " ⭐" if p.get("is_top_conf") else ""
        lines.append(f"{i}. **{p['title']}**{top_flag}")
        lines.append(f"   - 作者: {authors_str}")
        lines.append(f"   - 发表: {p.get('published', 'N/A')}  |  Venue: {p.get('venue', 'arXiv')}")
        lines.append(f"   - 链接: {p.get('link', '')}")
        summary = p.get("summary", "")
        if summary:
            lines.append(f"   - 摘要: {summary[:280]}...")
        lines.append("")
    return "\n".join(lines)
