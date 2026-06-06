"""Download and parse LaTeX source from arXiv."""

import gzip
import io
import re
import tarfile

import requests

# Maps our section keys → title keywords to match against arXiv \section{...}
_SECTION_PATTERNS: dict[str, list[str]] = {
    "abstract":     [],  # handled separately via \begin{abstract}
    "introduction": ["introduction"],
    "related":      ["related work", "related", "background", "prior work", "literature"],
    "method":       ["method", "methodology", "approach", "our approach", "proposed", "model"],
    "experiments":  ["experiment", "evaluation", "results", "empirical"],
    "analysis":     ["analysis", "discussion", "ablation"],
    "conclusion":   ["conclusion", "concluding", "summary"],
}


def extract_arxiv_id(link: str) -> str:
    m = re.search(r"arxiv\.org/(?:abs|pdf|src)/([0-9]{4}\.[0-9]{4,5})", link)
    return m.group(1) if m else ""


def _download_source(arxiv_id: str) -> bytes | None:
    url = f"https://arxiv.org/src/{arxiv_id}"
    try:
        resp = requests.get(url, timeout=60,
                            headers={"User-Agent": "Watson-Research-Assistant/1.0"})
        if resp.status_code == 200:
            return resp.content
    except Exception:
        pass
    return None


def _normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _find_main_tex(tf: tarfile.TarFile) -> str | None:
    tex_members = [m for m in tf.getmembers() if m.name.endswith(".tex")]
    if not tex_members:
        return None
    # Prefer files with \documentclass
    for member in sorted(tex_members, key=lambda m: -m.size):
        f = tf.extractfile(member)
        if not f:
            continue
        try:
            content = _normalize(f.read().decode("utf-8", errors="replace"))
            if r"\documentclass" in content:
                return content
        except Exception:
            continue
    # Fallback: largest .tex file
    f = tf.extractfile(tex_members[0])
    return _normalize(f.read().decode("utf-8", errors="replace")) if f else None


def _parse_sections(tex: str) -> dict[str, str]:
    result: dict[str, str] = {}

    # Abstract via environment
    abs_m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", tex, re.DOTALL)
    if abs_m:
        result["abstract"] = abs_m.group(0).strip()

    # Split on \section / \section*
    parts = re.split(r"(\\section\*?\{[^}]+\})", tex)

    sections_raw: list[tuple[str, str]] = []
    i = 0
    while i < len(parts):
        if re.match(r"\\section\*?\{[^}]+\}", parts[i]):
            heading = parts[i]
            body = parts[i + 1] if i + 1 < len(parts) else ""
            sections_raw.append((heading, heading + body))
            i += 2
        else:
            i += 1

    for heading, content in sections_raw:
        m = re.search(r"\\section\*?\{([^}]+)\}", heading)
        if not m:
            continue
        title = m.group(1).lower().strip()
        for key, patterns in _SECTION_PATTERNS.items():
            if not patterns:
                continue
            if any(p in title for p in patterns):
                if key not in result:
                    result[key] = content.strip()
                break

    return result


def fetch_template_latex(link: str) -> dict[str, str]:
    """Download arXiv LaTeX source and return parsed sections dict.

    Keys: abstract, introduction, related, method, experiments, analysis, conclusion.
    Returns {} if arXiv ID cannot be extracted or download fails.
    """
    arxiv_id = extract_arxiv_id(link)
    if not arxiv_id:
        return {}

    raw = _download_source(arxiv_id)
    if not raw:
        return {}

    tex: str | None = None

    # Try tar archive (most common)
    try:
        with tarfile.open(fileobj=io.BytesIO(raw)) as tf:
            tex = _find_main_tex(tf)
    except Exception:
        pass

    # Try plain gzip (single-file submissions)
    if tex is None:
        try:
            tex = _normalize(gzip.decompress(raw).decode("utf-8", errors="replace"))
        except Exception:
            pass

    if not tex:
        return {}

    return _parse_sections(tex)
