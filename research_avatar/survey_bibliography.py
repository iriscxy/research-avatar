"""Build a compact citation bank from verified literature-survey cards."""

from __future__ import annotations

import html
import json
import re


def _plain(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def _bib_value(value: str) -> str:
    return (
        value.replace("\\", "")
        .replace("{", "")
        .replace("}", "")
        .replace("&", r"\&")
        .strip()
    )


def _normalize_author_separators(value: str) -> str:
    """Translate serialized author-list separators into BibTeX ``and``."""
    if ";" in value and " and " not in value:
        return " and ".join(part.strip() for part in value.split(";") if part.strip())
    return value


def _survey_authors(article: str, visible_metadata: str) -> str:
    """Return BibTeX authors without inventing names absent from the survey.

    New survey cards may carry a complete machine-readable ``data-authors``
    list using BibTeX's ``and`` separator.  Older reports only expose a compact
    citation label in the first ``.who`` segment (for example ``Turner et al.``
    or ``Goyal & Daumé III``).  ``and others`` is BibTeX's standard encoding of
    an explicitly abbreviated author list and still lets natbib render the
    correct surname label instead of falling back to the ``survey...`` key.
    """
    explicit_match = re.search(
        r"\bdata-authors\s*=\s*([\"'])(.*?)\1",
        article,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if explicit_match:
        explicit = _bib_value(_plain(explicit_match.group(2)))
        # HTML data attributes commonly serialize an author list with
        # semicolons.  BibTeX does not treat ``;`` as an author separator: it
        # parses the entire value as one person and natbib consequently drops
        # the leading authors from citations.  Normalize the serialized list
        # at the ingestion boundary while preserving names verbatim.
        return _normalize_author_separators(explicit)

    citation_label = visible_metadata.split("·", 1)[0].strip()
    if not citation_label or re.search(r"\b(?:19|20)\d{2}\b", citation_label):
        return ""
    abbreviated = re.fullmatch(r"(.+?)\s+et\s+al\.?", citation_label, re.IGNORECASE)
    if abbreviated:
        first_author = abbreviated.group(1).strip()
        return f"{_bib_value(first_author)} and others" if first_author else ""
    if "&" in citation_label:
        return " and ".join(
            "{" + _bib_value(part.strip()) + "}"
            for part in citation_label.split("&")
            if part.strip()
        )
    return _normalize_author_separators(_bib_value(citation_label))


def verified_survey_bibliography(source: str) -> str:
    """Convert verified survey cards into traceable, bounded BibTeX records.

    The survey has already verified each linked scholarly landing page.  We retain
    that exact URL and visible metadata; this function never guesses missing authors
    or publication fields.
    """
    contract_bibliography = _bibliography_from_verification_contract(source)
    if contract_bibliography:
        return contract_bibliography
    records: list[str] = []
    seen_urls: set[str] = set()
    seen_keys: set[str] = set()
    for article_match in re.finditer(
        r"<article\b[^>]*class=[\"'][^\"']*\bcard\b[^\"']*[\"'][^>]*>(.*?)</article>",
        source,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        article = article_match.group(0)
        verification_text = _plain(article)
        if "Verified" not in verification_text and "verified" not in verification_text.casefold():
            continue
        title_match = re.search(
            r"<h4\b[^>]*>\s*<a\b[^>]*href=[\"'](https?://[^\"']+)[\"'][^>]*>(.*?)</a>",
            article,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not title_match:
            continue
        url = html.unescape(title_match.group(1)).strip()
        title = _plain(title_match.group(2))
        if not title or url in seen_urls:
            continue
        who_match = re.search(
            r"<div\b[^>]*class=[\"'][^\"']*\bwho\b[^\"']*[\"'][^>]*>(.*?)</div>",
            article,
            flags=re.IGNORECASE | re.DOTALL,
        )
        visible_metadata = _plain(who_match.group(1)) if who_match else ""
        authors = _survey_authors(article, visible_metadata)
        if not authors:
            raise ValueError(
                f"Verified literature-survey card is missing author metadata: {title}"
            )
        year_match = re.search(r"\b(?:19|20)\d{2}\b", visible_metadata)
        year = year_match.group(0) if year_match else ""
        coordinate = re.sub(r"^https?://", "", url).rstrip("/").split("/")[-1]
        key_base = "survey" + re.sub(r"[^A-Za-z0-9]+", "", coordinate).lower()
        if year and year not in key_base:
            key_base = f"survey{year}{key_base.removeprefix('survey')}"
        key = key_base or f"survey{len(records) + 1}"
        suffix = 2
        while key in seen_keys:
            key = f"{key_base}{suffix}"
            suffix += 1
        fields = [f"  title = {{{_bib_value(title)}}}"]
        if authors:
            fields.append(f"  author = {{{authors}}}")
        fields.append(f"  url = {{{_bib_value(url)}}}")
        if year:
            fields.append(f"  year = {{{year}}}")
        # The ACL scaffold uses pdfLaTeX.  Survey UI metadata may contain
        # Chinese verification badges; copying those badges into BibTeX's
        # optional note field makes an otherwise ASCII paper fail to compile.
        # Bibliographic identity is already carried by authors/title/year/URL,
        # so retain the optional note only when it is pdfLaTeX-safe ASCII.
        if visible_metadata and visible_metadata.isascii():
            fields.append(f"  note = {{{_bib_value(visible_metadata)}}}")
        records.append(
            f"% Verified by reports/01_LIT_SURVEY.html; source: {url}\n"
            f"@misc{{{key},\n" + ",\n".join(fields) + "\n}"
        )
        seen_urls.add(url)
        seen_keys.add(key)
    return "\n\n".join(records).rstrip() + ("\n" if records else "")


def _bibliography_from_verification_contract(source: str) -> str:
    """Build BibTeX from the survey's embedded ``literature-verification`` records.

    The fixed-template survey renders papers as plain list items, so the machine
    records (title, authors, year, venue, verified URL) are the authoritative
    source. Abbreviated author lists such as ``Turner et al.`` become BibTeX's
    ``and others``; no author, year, or venue is invented.
    """
    match = re.search(r'<script\b[^>]*id=["\']literature-verification["\'][^>]*>(.*?)</script>', source, re.S)
    if not match:
        return ""
    papers = json.loads(match.group(1)).get("papers", [])
    records: list[str] = []
    seen_keys: set[str] = set()
    for paper in papers:
        title, url = _plain(str(paper.get("title", ""))), str(paper.get("final_url") or paper.get("url") or "").strip()
        authors_list = [str(a).strip() for a in paper.get("authors", []) if str(a).strip()]
        if not title or not url or not authors_list:
            continue
        names = []
        for a in authors_list:
            abbreviated = re.fullmatch(r"(.+?)\s+et\s+al\.?", a, re.IGNORECASE)
            names.append(f"{_bib_value(abbreviated.group(1))} and others" if abbreviated else _bib_value(a))
        year = str(paper.get("year", "")).strip()
        coordinate = re.sub(r"^https?://", "", url).rstrip("/").split("/")[-1]
        key_base = "survey" + re.sub(r"[^A-Za-z0-9]+", "", coordinate).lower()
        if year and year not in key_base:
            key_base = f"survey{year}{key_base.removeprefix('survey')}"
        key, suffix = key_base, 2
        while key in seen_keys:
            key = f"{key_base}{suffix}"
            suffix += 1
        fields = [f"  title = {{{_bib_value(title)}}}", f"  author = {{{' and '.join(names)}}}", f"  url = {{{_bib_value(url)}}}"]
        if year:
            fields.append(f"  year = {{{year}}}")
        arxiv_match = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", str(paper.get("arxiv_url", "")) + " " + url)
        if arxiv_match:
            fields.append(f"  eprint = {{{arxiv_match.group(1)}}}")
            fields.append("  archiveprefix = {arXiv}")
        venue = _bib_value(str(paper.get("venue", "")))
        if venue and venue.isascii():
            fields.append(f"  note = {{{venue}}}")
        records.append(f"% Verified by reports/01_LIT_SURVEY.html; source: {url}\n@misc{{{key},\n" + ",\n".join(fields) + "\n}")
        seen_keys.add(key)
    return "\n\n".join(records).rstrip() + ("\n" if records else "")
