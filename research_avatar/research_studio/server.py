"""Serve the project-backed Research Studio.

Run from the repository root:

    python3 -m research_avatar.research_studio.server

The server is intentionally local-only by default. It reads canonical workflow
artifacts and never invents a second completion state.
"""

from __future__ import annotations

import argparse
import hashlib
import csv
import datetime as dt
import html
import json
import os
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("RESEARCH_AVATAR_ROOT", Path.cwd())).resolve()
STATIC = Path(__file__).resolve().parent / "static"
DEMO = PACKAGE_ROOT / "web" / "demo"
PAPER_STUDIO_URL = "http://127.0.0.1:8765"
PAPER_STUDIO_ROUTE = "/paper-studio"
PAPER_STUDIO_PROXY_TOKEN = hashlib.sha256(
    f"research-studio-paper-proxy:{ROOT}".encode("utf-8")
).hexdigest()
PAPER_STUDIO_STARTUP_TIMEOUT_SECONDS = 15.0
PAPER_STUDIO_LOCK = threading.Lock()
PAPER_STUDIO_PROCESS: subprocess.Popen[bytes] | None = None
LOCAL_URL_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def paper_workspace_root() -> Path:
    """Return the project whose Paper Studio is embedded in this control plane.

    Research artifacts and the displayed manuscript usually share ``ROOT``.  A
    reconstruction or comparison run, however, may intentionally keep its paper
    in an isolated project.  Supporting that as an explicit override prevents a
    test workspace from taking over the whole Research Studio and making the
    profile, survey, and idea tabs appear empty.
    """
    configured = os.environ.get("RESEARCH_AVATAR_PAPER_ROOT", "").strip()
    if not configured:
        return ROOT
    candidate = Path(configured).expanduser()
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    return candidate.resolve()


def artifact_workspace_root(
    key: str, root: Path = ROOT, overlay_root: Path | None = None
) -> Path:
    """Choose the overlay artifact when present, otherwise the main project.

    This gives reconstruction projects a complete merged pipeline: stages they
    actually produced are shown from the reconstruction, while genuinely
    absent stages (usually researcher profile and idea selection) retain the
    canonical project's content.
    """
    if key not in ARTIFACTS:
        raise KeyError(key)
    overlay = (overlay_root or paper_workspace_root()).resolve()
    relative = ARTIFACTS[key][0]
    if overlay != root.resolve() and (overlay / relative).is_file():
        return overlay
    return root.resolve()


class StudioHTTPServer(ThreadingHTTPServer):
    """Threaded local server with enough backlog for browser asset bursts."""

    request_queue_size = 64

ARTIFACTS = {
    "profile": ("researcher-profile/PROFILE.html", "text/html; charset=utf-8"),
    "publications": ("researcher-profile/publications.json", "application/json; charset=utf-8"),
    "literature": ("reports/01_LIT_SURVEY.html", "text/html; charset=utf-8"),
    "ideas": ("reports/02_IDEA_REPORT.html", "text/html; charset=utf-8"),
    "expplan": ("reports/03_EXPERIMENT_PLAN.html", "text/html; charset=utf-8"),
    "runplan": ("reports/04_RUN_PLAN.html", "text/html; charset=utf-8"),
    "results": ("reports/05_EXP_RESULT.html", "text/html; charset=utf-8"),
    "paper_pdf": ("paper/main.pdf", "application/pdf"),
    "paper_tex": ("paper/main.tex", "text/plain; charset=utf-8"),
}


SCRIPT_PATTERN = re.compile(
    r"<script\b[^>]*\bid=[\"']{identifier}[\"'][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)
TITLE_PATTERN = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
TAG_PATTERN = re.compile(r"<[^>]+>")


def research_studio_status(host: str = "127.0.0.1", port: int = 8780) -> dict[str, Any]:
    """Return whether this workspace's Research Studio already owns the URL."""
    url = f"http://{host}:{port}"
    try:
        with LOCAL_URL_OPENER.open(f"{url}/api/state", timeout=0.8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError):
        return {"running": False, "same_workspace": False, "url": url}
    project = payload.get("project", {}) if isinstance(payload, dict) else {}
    same_workspace = Path(str(project.get("root", ""))).resolve() == ROOT.resolve()
    return {"running": True, "same_workspace": same_workspace, "url": url}


def ensure_research_studio(
    host: str = "127.0.0.1",
    port: int = 8780,
    *,
    wait_seconds: float = 5.0,
) -> dict[str, Any]:
    """Idempotently launch Research Studio as a detached local process."""
    initial = research_studio_status(host, port)
    if initial["running"]:
        if not initial["same_workspace"]:
            raise RuntimeError(
                f"{initial['url']} is already serving a different workspace"
            )
        return {**initial, "started": False}

    workspace_hash = hashlib.sha256(str(ROOT).encode("utf-8")).hexdigest()[:12]
    log_path = Path(tempfile.gettempdir()) / f"research-studio-{workspace_hash}.log"
    command = [
        sys.executable,
        "-m",
        "research_avatar.research_studio.server",
        "--host",
        host,
        "--port",
        str(port),
        "--no-browser",
    ]
    with log_path.open("ab") as log_handle:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )

    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        status = research_studio_status(host, port)
        if status["running"] and status["same_workspace"]:
            return {**status, "started": True, "pid": process.pid, "log": str(log_path)}
        if process.poll() is not None:
            break
        time.sleep(0.1)
    detail = ""
    try:
        detail = log_path.read_text(encoding="utf-8", errors="replace")[-1200:].strip()
    except OSError:
        pass
    suffix = f": {detail}" if detail else ""
    raise RuntimeError(f"Research Studio did not start at {initial['url']}{suffix}")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def extract_script_json(path: Path, identifier: str) -> dict[str, Any]:
    if not path.exists():
        return {}
    pattern = re.compile(
        SCRIPT_PATTERN.pattern.format(identifier=re.escape(identifier)),
        SCRIPT_PATTERN.flags,
    )
    match = pattern.search(read_text(path))
    if not match:
        return {}
    try:
        value = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def html_title(path: Path) -> str:
    if not path.exists():
        return ""
    match = TITLE_PATTERN.search(read_text(path))
    if not match:
        return path.name
    return html.unescape(TAG_PATTERN.sub("", match.group(1))).strip()


def plain_html(value: str) -> str:
    return " ".join(html.unescape(TAG_PATTERN.sub(" ", value)).split())


def idea_report_state(path: Path) -> dict[str, Any]:
    """Read candidate ideas and the human selection from the canonical report."""
    if not path.exists():
        return {"candidates": [], "selected_id": "", "reason": "", "confirmed_at": ""}
    source = read_text(path)
    candidates = []
    for match in re.finditer(
        r"<article\b[^>]*\bdata-idea-id=[\"']([^\"']+)[\"'][^>]*>(.*?)</article>",
        source,
        re.IGNORECASE | re.DOTALL,
    ):
        idea_id, body = match.groups()
        heading_match = re.search(r"<h3\b[^>]*>(.*?)</h3>", body, re.IGNORECASE | re.DOTALL)
        pitch_match = re.search(
            r"<p\b[^>]*\bclass=[\"'][^\"']*\bpitch\b[^\"']*[\"'][^>]*>(.*?)</p>",
            body,
            re.IGNORECASE | re.DOTALL,
        )
        heading = plain_html(heading_match.group(1)) if heading_match else idea_id
        title = re.sub(rf"^{re.escape(idea_id)}\s*[·:：-]\s*", "", heading).strip()
        candidates.append({
            "id": idea_id,
            "title": title or heading,
            "pitch": plain_html(pitch_match.group(1)) if pitch_match else "",
        })
    selection = extract_script_json(path, "idea-selection")
    if not selection:
        selected_match = re.search(r"\bdata-selected-idea=[\"']([^\"']+)[\"']", source)
        if not selected_match:
            selected_match = re.search(
                r"<article\b[^>]*\bdata-idea-id=[\"']([^\"']+)[\"']"
                r"[^>]*\bdata-selected=[\"']true[\"']",
                source,
                flags=re.IGNORECASE,
            )
        selection = {"selected_id": selected_match.group(1) if selected_match else ""}
    selected_id = str(selection.get("selected_id", ""))
    selected = next((item for item in candidates if item["id"] == selected_id), None)
    return {
        "candidates": candidates,
        "selected_id": selected_id if selected else "",
        "selected_title": selected["title"] if selected else "",
        "reason": str(selection.get("reason", "")),
        "confirmed_at": str(selection.get("confirmed_at", "")),
    }


def record_idea_selection(path: Path, idea_id: str, reason: str = "") -> dict[str, Any]:
    """Record the human pick inside 02_IDEA_REPORT.html, without a second state file."""
    state = idea_report_state(path)
    selected = next((item for item in state["candidates"] if item["id"] == idea_id), None)
    if not selected:
        raise ValueError("Unknown idea ID")
    selection = {
        "selected_id": idea_id,
        "selected_title": selected["title"],
        "reason": reason.strip()[:1000],
        "confirmed_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    source = read_text(path)
    original_nonselected_cards = {
        match.group(1): match.group(2)
        for match in re.finditer(
            r'<article\b[^>]*\bdata-idea-id=["\']([^"\']+)["\'][^>]*>(.*?)</article>',
            source,
            re.IGNORECASE | re.DOTALL,
        )
        if match.group(1) != idea_id
    }
    payload = json.dumps(selection, ensure_ascii=False).replace("</", "<\\/")
    script = f'<script type="application/json" id="idea-selection">{payload}</script>'
    pattern = re.compile(
        SCRIPT_PATTERN.pattern.format(identifier="idea-selection"),
        SCRIPT_PATTERN.flags,
    )
    if pattern.search(source):
        source = pattern.sub(script, source, count=1)
    else:
        source = source.replace("</body>", f"  {script}\n</body>", 1)
    source = re.sub(
        r"(\bdata-selected-idea=[\"'])[^\"']*([\"'])",
        rf"\g<1>{idea_id}\g<2>",
        source,
    )
    banner = (
        f'<div class="selected-banner" data-selected-idea="{idea_id}">'
        f'<b>Selected: {idea_id} — {html.escape(selected["title"])}</b>'
        f'<span>{selection["confirmed_at"][:10]}</span></div>'
    )
    banner_pattern = re.compile(
        r'<div\b(?=[^>]*\b(?:data-selected-idea=|class=["\'][^"\']*\bselected-banner\b))[^>]*>\s*<b>Selected:.*?</div>',
        re.IGNORECASE | re.DOTALL,
    )
    if banner_pattern.search(source):
        source = banner_pattern.sub(banner, source, count=1)
    else:
        source = source.replace("<body>", f"<body>\n  {banner}", 1)
    source = re.sub(
        r'<span\b[^>]*\bclass=["\'][^"\']*\bselected-tag\b[^"\']*["\'][^>]*>.*?</span>',
        "",
        source,
        flags=re.IGNORECASE | re.DOTALL,
    )
    source = re.sub(
        rf'(<article\b[^>]*\bdata-idea-id=["\']{re.escape(idea_id)}["\'][^>]*>.*?<h3\b[^>]*>.*?</h3>)',
        r'\1<span class="selected-tag">✓ SELECTED</span>',
        source,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )
    source = re.sub(
        r"(<section\b[^>]*\bclass=[\"'][^\"']*\bgate\b[^\"']*[\"'][^>]*>.*?<h2\b[^>]*>).*?(</h2>)",
        rf"\g<1>已选择 {idea_id}\g<2>",
        source,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )
    updated_nonselected_cards = {
        match.group(1): match.group(2)
        for match in re.finditer(
            r'<article\b[^>]*\bdata-idea-id=["\']([^"\']+)["\'][^>]*>(.*?)</article>',
            source,
            re.IGNORECASE | re.DOTALL,
        )
        if match.group(1) != idea_id
    }
    if updated_nonselected_cards != original_nonselected_cards:
        raise ValueError("Idea selection must preserve every non-selected idea card in full")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(source, encoding="utf-8")
    temporary.replace(path)
    return selection


def render_ledger_html(path: Path) -> str:
    """Render RESULTS_LEDGER.csv as a readable, scrollable evidence table."""
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        rows = list(reader)
    header_cells = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body_rows = []
    for row in rows:
        cells = []
        for field in fields:
            value = row.get(field, "") or ""
            normalized = value.lower()
            cell_class = " status-ok" if normalized in {"verified", "pass", "complete"} else (
                " status-bad" if normalized in {"failed", "invalid"} else ""
            )
            displayed = html.escape(value) if value else '<span class="empty">—</span>'
            cells.append(f'<td class="{cell_class.strip()}">{displayed}</td>')
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    empty_note = "" if rows else (
        '<div class="empty-ledger"><strong>目前没有实验结果</strong>'
        '<span>表头已经建立；每个 Goal 完成并核验后，结果才会写入这里。</span></div>'
    )
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Results Ledger</title><style>
:root{{--ink:#17303d;--muted:#6c7e85;--line:#d8e3e1;--teal:#087d70;--wash:#edf3f1}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--wash);color:var(--ink);font:12px/1.5 Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}}
header{{position:sticky;left:0;display:flex;align-items:end;justify-content:space-between;gap:20px;padding:22px 24px 15px;background:#fff;border-bottom:1px solid var(--line)}}
header span,header strong{{display:block}}header span{{color:var(--teal);font-size:9px;font-weight:900;letter-spacing:.12em}}header strong{{margin-top:3px;font:700 23px Georgia,serif}}header b{{font-size:11px;color:var(--muted)}}
.table-shell{{margin:18px 20px 35px;overflow:auto;border:1px solid var(--line);border-radius:9px;background:#fff;box-shadow:0 8px 24px #17303d0b}}
table{{border-collapse:separate;border-spacing:0;min-width:100%;width:max-content}}th,td{{max-width:300px;padding:9px 11px;border-right:1px solid var(--line);border-bottom:1px solid var(--line);text-align:left;vertical-align:top;white-space:nowrap}}th{{position:sticky;top:0;background:#15394a;color:#fff;font-size:9px;letter-spacing:.03em}}td{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:10px}}tbody tr:hover td{{background:#f1f8f6}}.status-ok{{color:#087d70;font-weight:800}}.status-bad{{color:#b33b32;font-weight:800}}.empty{{color:#a9b5b6}}
.empty-ledger{{position:sticky;left:0;display:grid;place-items:center;min-width:460px;padding:70px 25px;color:var(--muted);text-align:center}}.empty-ledger strong{{font:700 18px Georgia,serif;color:var(--ink)}}.empty-ledger span{{margin-top:5px}}
</style></head><body><header><div><span>CANONICAL EVIDENCE SOURCE</span><strong>RESULTS_LEDGER.csv</strong></div><b>{len(rows)} result rows · {len(fields)} fields</b></header><div class="table-shell"><table><thead><tr>{header_cells}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>{empty_note}</div></body></html>"""


def render_publications_html(path: Path) -> str:
    """Render the canonical publication JSON as a browsable academic record."""
    data = load_json(path)
    publications = data.get("publications", [])
    if not isinstance(publications, list):
        publications = []
    years = sorted({str(item.get("year", "")) for item in publications if item.get("year")}, reverse=True)
    total_citations = sum(int(item.get("cited_by", 0) or 0) for item in publications)
    fulltext_count = sum(item.get("fulltext_status") == "downloaded" for item in publications)
    cards = []
    for item in publications:
        title = str(item.get("title", "Untitled publication"))
        authors = str(item.get("authors", ""))
        venue = str(item.get("venue", ""))
        year = str(item.get("year", "—"))
        citations = int(item.get("cited_by", 0) or 0)
        task_type = str(item.get("task_type", "") or "other")
        url = str(item.get("url_arxiv") or item.get("url") or "")
        safe_url = html.escape(url, quote=True) if url.startswith(("http://", "https://")) else ""
        abstract = str(item.get("abstract", "") or "").strip()
        searchable = " ".join((title, authors, venue, year, task_type)).lower()
        title_markup = (
            f'<a href="{safe_url}" target="_blank" rel="noreferrer">{html.escape(title)}</a>'
            if safe_url else html.escape(title)
        )
        abstract_markup = (
            f"<details><summary>Abstract</summary><p>{html.escape(abstract)}</p></details>" if abstract else ""
        )
        cards.append(
            f'<article class="paper" data-year="{html.escape(year, quote=True)}" '
            f'data-search="{html.escape(searchable, quote=True)}"><div class="year">{html.escape(year)}</div>'
            f'<div><h2>{title_markup}</h2><p class="authors">{html.escape(authors)}</p>'
            f'<p class="venue">{html.escape(venue) or "Venue pending"}</p>{abstract_markup}</div>'
            f'<div class="paper-meta"><span>{html.escape(task_type)}</span><strong>{citations:,}</strong><small>citations</small></div></article>'
        )
    year_options = "".join(f'<option value="{html.escape(year, quote=True)}">{html.escape(year)}</option>' for year in years)
    profile = data.get("profile", {}) if isinstance(data.get("profile"), dict) else {}
    researcher = str(profile.get("name") or profile.get("scholar_name") or "Researcher")
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Publication Record</title><style>
:root{{--ink:#17303d;--muted:#6b7c83;--line:#d9e4e1;--teal:#087d70;--navy:#12394b;--wash:#edf4f2}}*{{box-sizing:border-box}}
body{{margin:0;background:var(--wash);color:var(--ink);font:13px/1.55 Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}}header{{padding:30px 34px 24px;background:linear-gradient(135deg,#113547,#196474);color:#fff}}header>span{{color:#73d5c5;font-size:9px;font-weight:900;letter-spacing:.14em}}header h1{{margin:5px 0 3px;font:700 28px Georgia,serif}}header p{{margin:0;color:#bed0d6}}
.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:20px}}.stat{{padding:9px 11px;border:1px solid #ffffff22;border-radius:8px;background:#ffffff0d}}.stat strong,.stat span{{display:block}}.stat strong{{font:700 18px Georgia,serif}}.stat span{{color:#a9c5cd;font-size:8px}}
.controls{{position:sticky;top:0;z-index:3;display:grid;grid-template-columns:1fr 130px;gap:8px;padding:12px 24px;border-bottom:1px solid var(--line);background:#ffffffed;backdrop-filter:blur(8px)}}input,select{{width:100%;padding:10px 12px;border:1px solid #c9d9d5;border-radius:8px;background:#fff;color:var(--ink);font:inherit}}input:focus,select:focus{{outline:2px solid #77bcb1;outline-offset:1px}}
main{{padding:15px 24px 50px}}.result-count{{margin:0 0 9px;color:var(--muted);font-size:10px}}.paper{{display:grid;grid-template-columns:45px 1fr 70px;gap:13px;padding:16px 14px;border:1px solid var(--line);border-radius:10px;background:#fff;margin-bottom:8px;box-shadow:0 3px 12px #16394708}}.paper[hidden]{{display:none}}.year{{color:var(--teal);font-weight:900}}h2{{margin:0;font:700 16px/1.35 Georgia,serif}}h2 a{{color:var(--navy);text-decoration:none}}h2 a:hover{{color:var(--teal);text-decoration:underline}}.authors,.venue{{margin:5px 0 0}}.authors{{color:#4f636b}}.venue{{color:var(--muted);font-size:11px}}.paper-meta{{text-align:right}}.paper-meta span,.paper-meta strong,.paper-meta small{{display:block}}.paper-meta span{{color:var(--teal);font-size:8px;text-transform:uppercase}}.paper-meta strong{{margin-top:7px;font:700 17px Georgia,serif}}.paper-meta small{{color:var(--muted);font-size:8px}}details{{margin-top:8px;color:var(--muted);font-size:10px}}details summary{{cursor:pointer;color:var(--teal);font-weight:800}}details p{{margin:5px 0 0}}.none{{display:none;padding:60px 20px;text-align:center;color:var(--muted)}}
@media(max-width:600px){{header{{padding:25px 18px}}.controls{{grid-template-columns:1fr;padding:10px 14px}}.controls select{{display:none}}main{{padding:12px 14px}}.paper{{grid-template-columns:37px 1fr}}.paper-meta{{display:none}}}}
</style></head><body><header><span>CANONICAL PUBLICATION RECORD</span><h1>{html.escape(researcher)}</h1><p>从 publications.json 实时渲染；筛选不会修改原始数据。</p><div class="stats"><div class="stat"><strong>{len(publications)}</strong><span>PUBLICATIONS</span></div><div class="stat"><strong>{total_citations:,}</strong><span>TOTAL CITATIONS</span></div><div class="stat"><strong>{fulltext_count}</strong><span>FULL TEXT READY</span></div></div></header><div class="controls"><input id="search" type="search" placeholder="搜索标题、作者、venue 或研究方向…"><select id="year"><option value="">全部年份</option>{year_options}</select></div><main><p class="result-count"><span id="visible-count">{len(publications)}</span> / {len(publications)} papers</p>{''.join(cards)}<div id="none" class="none">没有匹配的论文</div></main><script>
const search=document.querySelector('#search'),year=document.querySelector('#year'),papers=[...document.querySelectorAll('.paper')],count=document.querySelector('#visible-count'),none=document.querySelector('#none');function filter(){{const q=search.value.trim().toLowerCase(),y=year.value;let visible=0;papers.forEach(p=>{{const show=(!q||p.dataset.search.includes(q))&&(!y||p.dataset.year===y);p.hidden=!show;if(show)visible++}});count.textContent=visible;none.style.display=visible?'none':'block'}}search.addEventListener('input',filter);year.addEventListener('change',filter);
</script></body></html>"""


def record_expplan_approval(path: Path) -> dict[str, Any]:
    """Approve the experiment contract in-place inside its canonical HTML report."""
    contract = extract_script_json(path, "experiment-plan-contract")
    if not contract:
        raise ValueError("Experiment plan contract is missing")
    approved_at = dt.datetime.now().astimezone().date().isoformat()
    contract["approval_status"] = "approved"
    contract["approved_at"] = approved_at
    contract["approval_channel"] = "Research Studio"
    contract["approval_contract_version"] = contract.get("contract_version", 1)
    unsigned = {
        key: value for key, value in contract.items()
        if key not in {
            "approval_status", "approved_at", "approval_channel",
            "approval_contract_sha256", "approval_contract_version",
        }
    }
    canonical = json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    contract["approval_contract_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    source = read_text(path)
    payload = json.dumps(contract, ensure_ascii=False, indent=2).replace("</", "<\\/")
    script = f'<script type="application/json" id="experiment-plan-contract">{payload}</script>'
    pattern = re.compile(
        SCRIPT_PATTERN.pattern.format(identifier="experiment-plan-contract"),
        SCRIPT_PATTERN.flags,
    )
    source = pattern.sub(lambda _match: script, source, count=1)
    approval_copy = (
        f"<p><b>Approved by the researcher on {approved_at} through Research Studio.</b> "
        "This signed experiment design may now be converted into executable goals.</p>"
    )
    source = re.sub(
        r"(<h2>\s*3\.\s*Approval\s*</h2>)\s*<p>.*?</p>",
        lambda match: match.group(1) + approval_copy,
        source,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )
    source = re.sub(
        r'<div class="approval-box">.*?</div>',
        '<div class="approval-box">' + approval_copy + '</div>',
        source,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(source, encoding="utf-8")
    temporary.replace(path)
    return {"approval_status": "approved", "approved_at": approved_at}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(read_text(path))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def ledger_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"rows": 0, "verified": 0, "invalid": 0}
    rows = []
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    verified = sum(row.get("verification_status", "").lower() in {"verified", "pass"} for row in rows)
    invalid = sum(row.get("verification_status", "").lower() in {"failed", "invalid"} for row in rows)
    return {"rows": len(rows), "verified": verified, "invalid": invalid}


def file_record(root: Path, key: str) -> dict[str, Any]:
    relative, _mime = ARTIFACTS[key]
    path = root / relative
    return {
        "key": key,
        "path": relative,
        "exists": path.exists(),
        "size": path.stat().st_size if path.exists() else 0,
        "modified_ns": path.stat().st_mtime_ns if path.exists() else 0,
        "url": f"/artifact/{key}" if path.exists() else "",
        "title": html_title(path) if path.suffix == ".html" else path.name,
    }


def rewrite_artifact_html_links(source: str) -> str:
    """Route sibling workflow-report links through Research Studio.

    Reports are authored for direct filesystem viewing, where links such as
    ``01_LIT_SURVEY.html`` are correct.  When the same report is mounted at
    ``/artifact/ideas``, that relative URL would incorrectly resolve to
    ``/artifact/01_LIT_SURVEY.html``.  Rewrite only known local artifacts and
    preserve fragments. External links open in a new top-level tab because the
    report itself is rendered in a sandboxed iframe; navigating that iframe to
    sites with ``frame-ancestors 'none'`` would otherwise look like a broken
    link.
    """
    rendered = source
    for key, (relative, mime) in ARTIFACTS.items():
        if not mime.startswith("text/html"):
            continue
        filename = re.escape(Path(relative).name)
        pattern = re.compile(
            rf'(?P<prefix>\bhref\s*=\s*(?P<quote>["\']))'
            rf'(?:\./)?(?:reports/)?{filename}(?P<fragment>#[^"\']*)?'
            rf'(?P=quote)',
            re.IGNORECASE,
        )
        rendered = pattern.sub(
            lambda match: (
                f'{match.group("prefix")}/artifact/{key}'
                f'{match.group("fragment") or ""}{match.group("quote")}'
            ),
            rendered,
        )
    anchor_pattern = re.compile(r"<a\b[^>]*>", re.IGNORECASE)

    def external_link_target(match: re.Match[str]) -> str:
        tag = match.group(0)
        href_match = re.search(r'\bhref\s*=\s*(["\'])(https?://[^"\']+)\1', tag, re.IGNORECASE)
        if not href_match or re.search(r"\btarget\s*=", tag, re.IGNORECASE):
            return tag
        additions = ' target="_blank"'
        if not re.search(r"\brel\s*=", tag, re.IGNORECASE):
            additions += ' rel="noopener noreferrer"'
        return f"{tag[:-1]}{additions}>"

    rendered = anchor_pattern.sub(external_link_target, rendered)
    return rendered


def status_for(exists: bool, *, approved: bool | None = None) -> str:
    if not exists:
        return "not_started"
    if approved is False:
        return "waiting_confirmation"
    return "complete"


def profile_stage(root: Path) -> dict[str, Any]:
    profile = root / ARTIFACTS["profile"][0]
    publications = load_json(root / ARTIFACTS["publications"][0])
    publication_rows = publications.get("publications", publications if isinstance(publications, list) else [])
    count = len(publication_rows) if isinstance(publication_rows, list) else 0
    name = ""
    if profile.exists():
        title = html_title(profile)
        name = re.sub(r"^Researcher Profile\s*[—–-]?\s*", "", title).strip()
    artifact = file_record(root, "profile")
    artifact["title"] = "研究画像"
    return {
        "id": "profile",
        "title": "研究画像",
        "status": status_for(profile.exists()),
        "command": "上传完整的 Google Scholar HTML",
        "metrics": [
            {"label": "Researcher", "value": name or "Pending"},
            {"label": "Publications", "value": str(count) if count else "—"},
        ],
        "artifacts": [artifact],
        "message": "画像是后续选题、实验习惯和写作风格的唯一通用来源。",
    }


def literature_stage(root: Path) -> dict[str, Any]:
    literature = file_record(root, "literature")
    return {
        "id": "literature",
        "title": "文献 Survey",
        "status": status_for(literature["exists"]),
        "command": "等待文献 Survey 生成",
        "metrics": [
            {"label": "Survey", "value": "Ready" if literature["exists"] else "Pending"},
        ],
        "artifacts": [literature],
        "message": "先独立建立可核验的文献地图，再进入 Idea 生成与选择。",
    }


def ideas_stage(root: Path) -> dict[str, Any]:
    ideas = file_record(root, "ideas")
    idea_selection = idea_report_state(root / ARTIFACTS["ideas"][0])
    return {
        "id": "ideas",
        "title": "Idea 选择",
        "status": status_for(ideas["exists"], approved=bool(idea_selection["selected_id"]) if ideas["exists"] else None),
        "command": "等待 Idea 报告生成并选择",
        "metrics": [
            {"label": "Idea report", "value": "Ready" if ideas["exists"] else "Pending"},
            {"label": "Human pick", "value": idea_selection["selected_id"] or "Pending"},
        ],
        "artifacts": [ideas],
        "message": "推荐 idea 必须通过最近工作核对与新颖性资格门槛。",
        "idea_selection": idea_selection,
    }


def expplan_stage(root: Path) -> dict[str, Any]:
    artifact = file_record(root, "expplan")
    contract = extract_script_json(root / ARTIFACTS["expplan"][0], "experiment-plan-contract")
    approved = contract.get("approval_status") == "approved" if contract else False
    target = contract.get("target", {}) if isinstance(contract.get("target"), dict) else {}
    baselines = contract.get("baseline_contract", {}).get("selected", [])
    return {
        "id": "expplan",
        "title": "实验设计",
        "status": status_for(artifact["exists"], approved=approved),
        "command": "等待实验设计生成并确认",
        "metrics": [
            {"label": "Approval", "value": contract.get("approval_status", "Pending")},
            {"label": "Venue", "value": target.get("venue", "—")},
            {"label": "Paper artifacts", "value": str(len(contract.get("paper_artifacts", [])))},
            {"label": "Selected baselines", "value": str(len(baselines))},
        ],
        "artifacts": [artifact],
        "message": contract.get("selected_idea", "等待从 Projected Paper 反推证据空位。"),
        "approval": {
            "status": contract.get("approval_status", "pending"),
            "approved_at": contract.get("approved_at", ""),
            "can_approve": artifact["exists"] and bool(contract),
        },
    }


def runplan_stage(root: Path) -> dict[str, Any]:
    artifact = file_record(root, "runplan")
    results_artifact = file_record(root, "results")
    plan = extract_script_json(root / ARTIFACTS["runplan"][0], "run-plan-state")
    goals = plan.get("goals", []) if isinstance(plan.get("goals"), list) else []
    completed = [goal for goal in goals if goal.get("status") == "completed"]
    proposed_id = plan.get("proposed_goal_id")
    proposed = next((goal for goal in goals if goal.get("id") == proposed_id), {})
    visible_artifacts = [item for item in (results_artifact, artifact) if item["exists"]]
    if not visible_artifacts:
        visible_artifacts = [artifact]
    return {
        "id": "runplan",
        "title": "实验执行",
        "status": "in_progress" if artifact["exists"] and len(completed) < len(goals) else status_for(artifact["exists"]),
        "command": (
            f"执行 {proposed_id}: {proposed.get('title', '')}"
            if proposed_id else "等待实验执行计划"
        ),
        "metrics": [
            {"label": "Goals", "value": f"{len(completed)} / {len(goals)}"},
            {"label": "Current", "value": proposed_id or plan.get("active_goal_id") or "—"},
            {"label": "Acquisitions", "value": str(len(plan.get("acquisition_contracts", [])))},
            {
                "label": "State",
                "value": str(plan.get("state") or plan.get("status") or "Pending"),
            },
        ],
        # Once results exist, make the evidence-bearing result report the
        # default execution view. Keep the run plan beside it so the acquisition
        # hierarchy and the values it produced remain independently inspectable.
        "artifacts": visible_artifacts,
        "default_artifact_key": (
            "results" if results_artifact["exists"] else "runplan"
        ),
        "results_backend": results_artifact,
        "message": proposed.get("instructions", plan.get("exact_next_authorized_action", "等待实验计划批准。")),
        "goals": [
            {
                "id": goal.get("id"),
                "part_id": goal.get("part_id"),
                "title": goal.get("title"),
                "status": goal.get("status"),
                "artifact_ids": goal.get("artifact_ids", []),
            }
            for goal in goals
        ],
        "proposed_goal": proposed,
    }


def ensure_paper_project_from_completed_run(root: Path) -> dict[str, Any]:
    """Initialize Paper Studio from the exact plan and results of a completed run."""
    config_path = root / "paper/paper_studio.json"
    if config_path.is_file():
        return {"created": False, "reason": "already_configured"}

    run_path = root / ARTIFACTS["runplan"][0]
    results_path = root / ARTIFACTS["results"][0]
    run_state = extract_script_json(run_path, "run-plan-state")
    goals = run_state.get("goals", [])
    completed = (
        (run_state.get("status") or run_state.get("state")) == "completed"
        and isinstance(goals, list)
        and bool(goals)
        and all(
            isinstance(goal, dict) and goal.get("status") == "completed"
            for goal in goals
        )
    )
    if not completed or not results_path.is_file():
        return {"created": False, "reason": "run_or_results_incomplete"}

    # The run report is authoritative because it may point at a reduced/local
    # variant rather than reports/03_EXPERIMENT_PLAN.html.
    source_plan = str(run_state.get("source_plan") or ARTIFACTS["expplan"][0])
    plan_path = (root / source_plan).resolve()
    try:
        plan_path.relative_to(root.resolve())
    except ValueError as exc:
        raise RuntimeError("Run Plan source_plan points outside the project") from exc
    if not plan_path.is_file():
        raise RuntimeError(f"Run Plan source plan does not exist: {source_plan}")

    from research_avatar.tools.init_paper_studio_from_pipeline import initialize

    summary = initialize(root, plan_path, results_path)
    return {"created": True, "reason": "completed_run", **summary}


def paper_stage(root: Path) -> dict[str, Any]:
    config = load_json(root / "paper/paper_studio.json")
    run_state = extract_script_json(
        root / ARTIFACTS["runplan"][0], "run-plan-state"
    )
    run_goals = run_state.get("goals", [])
    experiment_ready = (
        (run_state.get("status") or run_state.get("state")) == "completed"
        and isinstance(run_goals, list)
        and bool(run_goals)
        and all(
            isinstance(goal, dict) and goal.get("status") == "completed"
            for goal in run_goals
        )
        and (root / ARTIFACTS["results"][0]).is_file()
    )
    runtime = load_json(root / "paper/.paper_studio/state.json")
    sections = runtime.get("sections", {}) if isinstance(runtime.get("sections"), dict) else {}
    accepted = 0
    total = 0
    for section in sections.values():
        paragraphs = section.get("paragraphs", []) if isinstance(section, dict) else []
        total += len(paragraphs)
        accepted += sum(bool(item.get("accepted_text")) for item in paragraphs if isinstance(item, dict))
    project = config.get("project", {}) if isinstance(config.get("project"), dict) else {}
    figures = runtime.get("figures", {}) if isinstance(runtime.get("figures"), dict) else {}
    tables = runtime.get("tables", {}) if isinstance(runtime.get("tables"), dict) else {}
    compile_state = runtime.get("compile", {}) if isinstance(runtime.get("compile"), dict) else {}
    configured_figures = config.get("figures", {}) if isinstance(config.get("figures"), dict) else {}
    configured_tables = config.get("tables", {}) if isinstance(config.get("tables"), dict) else {}
    all_content_complete = bool(total) and accepted == total
    all_figures_complete = all(
        figures.get(figure_id, {}).get("status") == "approved"
        for figure_id in configured_figures
    )
    all_tables_complete = all(
        tables.get(table_id, {}).get("status") == "approved"
        for table_id in configured_tables
    )
    # Paper Studio reports a successful live compile as ``ok``; older saved
    # projects used ``completed``.  Treat both as terminal success so a fully
    # approved imported paper does not remain permanently "in progress".
    project_complete = (
        bool(config)
        and all_content_complete
        and all_figures_complete
        and all_tables_complete
        and compile_state.get("status") in {"ok", "completed"}
    )
    config_path = root / "paper/paper_studio.json"
    studio_artifact = {
        "key": "paper_studio",
        "path": "paper/paper_studio.json",
        "exists": bool(config),
        "size": config_path.stat().st_size if config_path.exists() else 0,
        "modified_ns": config_path.stat().st_mtime_ns if config_path.exists() else 0,
        "url": f"{PAPER_STUDIO_ROUTE}/" if config else "",
        "title": "Paper Studio · 可交互论文写作",
        "interactive": True,
    }
    return {
        "id": "paper",
        "title": "论文写作",
        "status": "complete" if project_complete else ("in_progress" if config else "not_started"),
        "command": (
            "Paper Studio 已就绪"
            if config else (
                "python3 -m research_avatar.tools.init_paper_studio_from_pipeline "
                "--from-run-plan --open"
                if experiment_ready else "等待实验执行完成并生成 05_EXP_RESULT.html"
            )
        ),
        "metrics": [
            {"label": "Project", "value": project.get("name", "—")},
            {"label": "Paragraphs", "value": f"{accepted} / {total}" if total else "—"},
            {"label": "Figures", "value": str(len(config.get("figures", {})))},
            {"label": "Tables", "value": str(len(config.get("tables", {})))},
        ],
        # Paper Writing is an application stage.  The compiled PDF remains
        # available inside Paper Studio's live-output pane; using it as the
        # stage artifact silently replaces the editing workflow with a viewer.
        "artifacts": [studio_artifact],
        "message": "Paper Studio 逐段确认后写入 LaTeX，并保持图表与结果绑定。",
        "paper_studio": {
            "configured": bool(config),
            "url": f"{PAPER_STUDIO_ROUTE}/" if config else "",
            "experiment_ready": experiment_ready,
        },
    }


def build_state(
    root: Path = ROOT, paper_root: Path | None = None
) -> dict[str, Any]:
    paper_root = (paper_root or root).resolve()
    profile_root = artifact_workspace_root("profile", root, paper_root)
    literature_root = artifact_workspace_root("literature", root, paper_root)
    ideas_root = artifact_workspace_root("ideas", root, paper_root)
    expplan_root = artifact_workspace_root("expplan", root, paper_root)
    runplan_root = artifact_workspace_root("runplan", root, paper_root)
    stages = [
        profile_stage(profile_root),
        literature_stage(literature_root),
        ideas_stage(ideas_root),
        expplan_stage(expplan_root),
        runplan_stage(runplan_root),
        paper_stage(paper_root),
    ]
    paper_config = load_json(paper_root / "paper/paper_studio.json")
    paper_project = paper_config.get("project", {}) if isinstance(paper_config.get("project"), dict) else {}
    exp_contract = extract_script_json(root / ARTIFACTS["expplan"][0], "experiment-plan-contract")
    return {
        "schema_version": "1.0",
        "project": {
            "name": paper_project.get("name") or exp_contract.get("selected_idea") or root.name,
            "root": str(root),
            "paper_root": str(paper_root),
            "mode": "project",
        },
        "stages": stages,
        "updated_at": int(time.time()),
        "privacy": {"stores_ip": False, "note": "Research Studio does not persist visitor IP addresses."},
    }


def paper_studio_status() -> dict[str, Any]:
    paper_root = paper_workspace_root()
    config = load_json(paper_root / "paper/paper_studio.json")
    configured_project = config.get("project", {}) if isinstance(config, dict) else {}
    expected_project_id = (
        str(configured_project.get("id", "")).strip() or "__paper_studio_empty__"
    )
    for endpoint in ("/api/health", "/api/state"):
        try:
            with LOCAL_URL_OPENER.open(f"{PAPER_STUDIO_URL}{endpoint}", timeout=1.2) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if endpoint == "/api/health" and error.code == HTTPStatus.NOT_FOUND:
                continue
            return {
                "running": False,
                "same_workspace": False,
                "same_project": False,
                "url": PAPER_STUDIO_URL,
            }
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
            return {
                "running": False,
                "same_workspace": False,
                "same_project": False,
                "url": PAPER_STUDIO_URL,
            }
        project = payload.get("project", {}) if isinstance(payload, dict) else {}
        root = str(project.get("root", "")).strip()
        same_workspace = bool(root) and Path(root).resolve() == paper_root
        served_project_id = str(
            project.get("id") or payload.get("project_id") or ""
        ).strip()
        empty_project = bool(payload.get("empty_project", False))
        same_project = (
            bool(expected_project_id)
            and served_project_id == expected_project_id
            and not (empty_project and expected_project_id != "__paper_studio_empty__")
        )
        return {
            "running": True,
            "same_workspace": same_workspace,
            "same_project": same_project,
            "project_id": served_project_id,
            "expected_project_id": expected_project_id,
            "empty_project": empty_project,
            "pid": payload.get("pid"),
            "embedded_only": bool(payload.get("embedded_only", False)),
            "url": PAPER_STUDIO_URL,
        }
    return {
        "running": False,
        "same_workspace": False,
        "same_project": False,
        "url": PAPER_STUDIO_URL,
    }


def paper_studio_alive() -> bool:
    return bool(paper_studio_status()["running"])


def paper_project_configured(root: Path | None = None) -> bool:
    return ((root or paper_workspace_root()) / "paper/paper_studio.json").is_file()


def start_paper_studio() -> dict[str, Any]:
    global PAPER_STUDIO_PROCESS
    paper_root = paper_workspace_root()
    with PAPER_STUDIO_LOCK:
        if not paper_project_configured():
            return {"ok": False, "error": "当前项目没有 Paper Studio 配置。"}
        initial = paper_studio_status()
        if initial["running"] and not initial["same_workspace"]:
            return {
                "ok": False,
                "error": f"{PAPER_STUDIO_URL} is already serving a different workspace.",
            }
        if initial["running"] and (
            not initial.get("same_project", False)
            or not initial.get("embedded_only", False)
        ):
            stale_pid = initial.get("pid")
            if not isinstance(stale_pid, int) or stale_pid <= 1 or stale_pid == os.getpid():
                return {
                    "ok": False,
                    "error": (
                        f"{PAPER_STUDIO_URL} is serving a stale or directly exposed Paper Studio "
                        f"{initial.get('project_id') or '(unknown)'} and did not expose a safe PID."
                    ),
                }
            os.kill(stale_pid, signal.SIGTERM)
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline and paper_studio_status()["running"]:
                time.sleep(0.05)
            if paper_studio_status()["running"]:
                return {
                    "ok": False,
                    "error": f"Stale Paper Studio process {stale_pid} did not stop.",
                }
            PAPER_STUDIO_PROCESS = None
            initial = paper_studio_status()
        if initial["running"]:
            return {"ok": True, "url": PAPER_STUDIO_URL, "already_running": True}
        workspace_hash = hashlib.sha256(str(paper_root).encode("utf-8")).hexdigest()[:12]
        log_path = Path(tempfile.gettempdir()) / f"paper-studio-{workspace_hash}.log"
        if PAPER_STUDIO_PROCESS is None or PAPER_STUDIO_PROCESS.poll() is not None:
            log_handle = log_path.open("ab")
            child_environment = os.environ.copy()
            # The embedded editor runs with the selected paper project as its
            # working directory. Preserve the package checkout on sys.path so
            # `python -m research_avatar...` keeps working for overlay projects
            # that live below the repository root.
            package_parent = str(PACKAGE_ROOT.parent)
            existing_pythonpath = child_environment.get("PYTHONPATH", "")
            child_environment["PYTHONPATH"] = os.pathsep.join(
                value for value in (package_parent, existing_pythonpath) if value
            )
            child_environment.update(
                {
                    "PAPER_STUDIO_EMBEDDED_ONLY": "1",
                    "PAPER_STUDIO_PROXY_TOKEN": PAPER_STUDIO_PROXY_TOKEN,
                }
            )
            PAPER_STUDIO_PROCESS = subprocess.Popen(
                [sys.executable, "-m", "research_avatar.paper_studio.server", "--no-browser"],
                cwd=paper_root,
                env=child_environment,
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )
            log_handle.close()
        deadline = time.monotonic() + PAPER_STUDIO_STARTUP_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            status = paper_studio_status()
            if status["running"] and status["same_workspace"]:
                return {"ok": True, "url": PAPER_STUDIO_URL, "already_running": False}
            if status["running"]:
                return {
                    "ok": False,
                    "error": f"{PAPER_STUDIO_URL} was claimed by a different workspace.",
                }
            if PAPER_STUDIO_PROCESS is not None and PAPER_STUDIO_PROCESS.poll() is not None:
                return {
                    "ok": False,
                    "error": f"Paper Studio exited during startup. See {log_path}.",
                }
            time.sleep(0.15)
    return {
        "ok": False,
        "error": (
            "Paper Studio did not become ready within "
            f"{PAPER_STUDIO_STARTUP_TIMEOUT_SECONDS:g} seconds. See {log_path}."
        ),
    }


def ensure_project_studios(
    host: str = "127.0.0.1",
    port: int = 8780,
    *,
    open_browser: bool = True,
) -> dict[str, Any]:
    """Idempotently make both project Studio applications available."""
    research = ensure_research_studio(host, port)
    paper = start_paper_studio()
    if not paper.get("ok"):
        raise RuntimeError(str(paper.get("error") or "Paper Studio failed to start"))
    urls = [str(research["url"])]
    if open_browser:
        webbrowser.open(urls[0])
    return {"research_studio": research, "paper_studio": paper, "urls": urls}


def open_project_terminal() -> dict[str, Any]:
    """Open a terminal at the project root without executing an experiment command."""
    try:
        if sys.platform == "darwin":
            subprocess.Popen(
                ["open", "-a", "Terminal", str(ROOT)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif sys.platform.startswith("linux"):
            terminal = next((name for name in ("x-terminal-emulator", "gnome-terminal", "konsole") if shutil.which(name)), None)
            if not terminal:
                return {"ok": False, "error": "No supported terminal application was found."}
            command = [terminal, "--working-directory", str(ROOT)]
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sys.platform == "win32":
            subprocess.Popen(["cmd", "/c", "start", "", "cmd", "/K", f'cd /d "{ROOT}"'])
        else:
            return {"ok": False, "error": f"Unsupported platform: {sys.platform}"}
    except OSError as error:
        return {"ok": False, "error": str(error)}
    return {"ok": True, "cwd": str(ROOT)}


class Handler(BaseHTTPRequestHandler):
    server_version = "ResearchStudio/1.0"

    def write_body(self, body: bytes) -> None:
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True

    def send_bytes(self, body: bytes, mime: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.write_body(body)

    def send_json(self, value: Any, status: int = 200) -> None:
        self.send_bytes(json.dumps(value, ensure_ascii=False).encode(), "application/json; charset=utf-8", status)

    def read_json(self, *, limit: int = 16_384) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Invalid request body size.") from exc
        if length <= 0 or length > limit:
            raise ValueError("Invalid request body size.")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Request body must be valid JSON.") from exc
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object.")
        return payload

    def proxy_paper_studio(self, method: str) -> None:
        """Serve the internal Paper Studio engine under the Research Studio origin."""
        started = start_paper_studio()
        if not started.get("ok"):
            self.send_json(
                {"ok": False, "error": started.get("error", "论文编辑器启动失败。")},
                HTTPStatus.BAD_GATEWAY,
            )
            return
        upstream_path = self.path[len(PAPER_STUDIO_ROUTE) :] or "/"
        if not upstream_path.startswith("/"):
            upstream_path = "/" + upstream_path
        body = None
        if method == "POST":
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self.send_json({"ok": False, "error": "Invalid request size."}, 400)
                return
            if length < 0 or length > 32 * 1024 * 1024:
                self.send_json({"ok": False, "error": "Request too large."}, 413)
                return
            body = self.rfile.read(length)
        headers = {"X-Research-Studio-Proxy": PAPER_STUDIO_PROXY_TOKEN}
        for name in ("Content-Type", "Range", "If-None-Match", "If-Modified-Since"):
            value = self.headers.get(name)
            if value:
                headers[name] = value
        request = urllib.request.Request(
            PAPER_STUDIO_URL + upstream_path,
            data=body,
            headers=headers,
            method=method,
        )
        try:
            response = LOCAL_URL_OPENER.open(request, timeout=300)
        except urllib.error.HTTPError as error:
            response = error
        except (urllib.error.URLError, OSError) as error:
            self.send_json({"ok": False, "error": f"论文编辑器连接失败：{error}"}, 502)
            return
        with response:
            payload = response.read()
            self.send_response(response.status)
            for name in (
                "Content-Type",
                "Content-Disposition",
                "Accept-Ranges",
                "Content-Range",
                "ETag",
                "Last-Modified",
            ):
                value = response.headers.get(name)
                if value:
                    self.send_header(name, value)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.write_body(payload)

    def do_GET(self) -> None:  # noqa: N802
        request_path = unquote(urlparse(self.path).path)
        if request_path == PAPER_STUDIO_ROUTE:
            self.send_response(HTTPStatus.PERMANENT_REDIRECT)
            self.send_header("Location", PAPER_STUDIO_ROUTE + "/")
            self.end_headers()
            return
        if request_path.startswith(PAPER_STUDIO_ROUTE + "/"):
            self.proxy_paper_studio("GET")
            return
        if request_path == "/api/state":
            self.send_json(build_state(ROOT, paper_workspace_root()))
            return
        if request_path == "/api/paper-studio/status":
            self.send_json(paper_studio_status())
            return
        if request_path.startswith("/artifact/"):
            key = request_path.removeprefix("/artifact/")
            if key not in ARTIFACTS:
                self.send_json({"error": "unknown artifact"}, HTTPStatus.NOT_FOUND)
                return
            relative, mime = ARTIFACTS[key]
            target = artifact_workspace_root(key) / relative
            if not target.exists() or not target.is_file():
                self.send_json({"error": "artifact not found"}, HTTPStatus.NOT_FOUND)
                return
            if key == "publications":
                rendered = render_publications_html(target).encode()
                self.send_bytes(rendered, "text/html; charset=utf-8")
            elif mime.startswith("text/html"):
                rendered = rewrite_artifact_html_links(
                    target.read_text(encoding="utf-8", errors="replace")
                ).encode("utf-8")
                self.send_bytes(rendered, mime)
            else:
                self.send_bytes(target.read_bytes(), mime)
            return
        if request_path.startswith("/demo/"):
            relative = request_path.removeprefix("/demo/") or "index.html"
            target = (DEMO / relative).resolve()
            try:
                target.relative_to(DEMO.resolve())
            except ValueError:
                self.send_json({"error": "invalid path"}, HTTPStatus.BAD_REQUEST)
                return
            self.send_static(target)
            return
        relative = "index.html" if request_path == "/" else request_path.lstrip("/")
        self.send_static((STATIC / relative).resolve())

    def send_static(self, target: Path) -> None:
        try:
            target.relative_to(STATIC.resolve())
        except ValueError:
            try:
                target.relative_to(DEMO.resolve())
            except ValueError:
                self.send_json({"error": "invalid static path"}, HTTPStatus.BAD_REQUEST)
                return
        if not target.exists() or not target.is_file():
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        mime = {
            ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8", ".json": "application/json; charset=utf-8",
            ".svg": "image/svg+xml",
        }.get(target.suffix, "application/octet-stream")
        self.send_bytes(target.read_bytes(), mime)

    def do_POST(self) -> None:  # noqa: N802
        request_path = urlparse(self.path).path
        if request_path.startswith(PAPER_STUDIO_ROUTE + "/"):
            self.proxy_paper_studio("POST")
            return
        if request_path == "/api/idea-selection":
            try:
                payload = self.read_json()
                idea_id = str(payload.get("idea_id", "")).strip()
                reason = str(payload.get("reason", "")).strip()
                idea_root = artifact_workspace_root("ideas")
                selection = record_idea_selection(idea_root / ARTIFACTS["ideas"][0], idea_id, reason)
            except (ValueError, json.JSONDecodeError) as error:
                self.send_json({"ok": False, "error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            self.send_json({"ok": True, "selection": selection})
            return
        if request_path == "/api/expplan/approve":
            try:
                expplan_root = artifact_workspace_root("expplan")
                approval = record_expplan_approval(expplan_root / ARTIFACTS["expplan"][0])
            except ValueError as error:
                self.send_json({"ok": False, "error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            self.send_json({"ok": True, "approval": approval})
            return
        if request_path == "/api/terminal/open":
            result = open_project_terminal()
            self.send_json(result, 200 if result.get("ok") else 500)
            return
        if request_path == "/api/paper-studio/start":
            result = start_paper_studio()
            self.send_json(result, 200 if result.get("ok") else 500)
            return
        self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        # Avoid persisting client addresses. Product diagnostics stay request-content only.
        print(f"Research Studio: {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Research Studio.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8780)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument(
        "--paper-root",
        help=(
            "optional overlay project for Literature/Experiment/Paper stages; "
            "missing artifacts fall back to the main workspace"
        ),
    )
    parser.add_argument(
        "--ensure",
        action="store_true",
        help="reuse the current server or start it once in the background",
    )
    parser.add_argument(
        "--ensure-studios",
        action="store_true",
        help="start Research Studio and its embedded paper editor, then open Research Studio",
    )
    args = parser.parse_args()
    if args.paper_root:
        os.environ["RESEARCH_AVATAR_PAPER_ROOT"] = str(
            Path(args.paper_root).expanduser().resolve()
        )
    if args.ensure_studios:
        result = ensure_project_studios(
            args.host,
            args.port,
            open_browser=not args.no_browser,
        )
        print(f"Research Studio ready: {result['research_studio']['url']}")
        print(
            "Paper editor ready inside Research Studio: "
            f"{result['research_studio']['url']} (论文写作 Tab)"
        )
        return
    if args.ensure:
        result = ensure_research_studio(args.host, args.port)
        action = "started" if result["started"] else "already running"
        print(f"Research Studio {action}: {result['url']}")
        return
    server = StudioHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}"
    print(f"Research Studio: {url}")
    print(f"Workspace: {ROOT}")
    if not args.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nResearch Studio stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
