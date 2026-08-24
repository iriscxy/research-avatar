"""Private online gateway for Paper Studio.

The gateway accepts researcher-owned project documents and Scholar HTML, scaffolds an approved draft
workspace, and proxies the unchanged Paper Studio UI to an isolated localhost
worker. LLM credentials are held only in process memory.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html as html_lib
import http.client
import io
import json
import math
import os
import re
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable

from research_avatar.paper_studio.api_usage import append_usage, usage_record, usage_summary
from research_avatar.paper_structure import (
    PaperStructureError,
    materialize_reference_contexts,
    normalize_reference_line_ranges,
    normalize_structure_design,
    parse_structure_response,
    structure_prompt,
)
from research_avatar.survey_bibliography import verified_survey_bibliography


STATIC = Path(__file__).resolve().parent / "static"
DEMO_STATIC = Path(__file__).resolve().parents[1] / "web" / "demo"
DEMO_PROJECT = Path(__file__).resolve().parent / "demo_project"
VENUE_TEMPLATES_DIR = Path(__file__).resolve().parent / "venue_templates"
COOKIE_NAME = "paper_studio_session"
AUTH_COOKIE_NAME = "online_studio_auth"
GOOGLE_STATE_COOKIE = "online_studio_google_state"
# POST-shaped endpoints that only ever read (never mutate) manuscript state,
# so they stay reachable on a read-only demo session despite using a
# non-GET method. /api/pdf/locate is the double-click-PDF-to-source-line
# lookup: it needs a POST body for click coordinates, but the response is
# purely a computed location, nothing on disk changes.
DEMO_SAFE_WRITE_PATHS = {"/api/pdf/locate", "/api/select-paragraph"}
# Base64 expands the three bounded HTML files plus the 32 MB ZIP by roughly 4/3.
MAX_BODY_BYTES = 80 * 1024 * 1024
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_FILES = 20
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_ARCHIVE_EXPANDED_BYTES = 128 * 1024 * 1024
MAX_ARCHIVE_FILES = 2000
MAX_EXPORT_BYTES = 256 * 1024 * 1024
MAX_EXPORT_FILES = 5000
MAX_SOURCE_TEXT_CHARS = 60_000
MAX_STRUCTURE_REFERENCE_CHARS = 120_000
MAX_ACTIVE_SESSIONS = int(os.environ.get("ONLINE_STUDIO_MAX_SESSIONS", "16"))
SESSION_IDLE_SECONDS = int(os.environ.get("ONLINE_STUDIO_IDLE_SECONDS", "14400"))
SESSION_ACTIVITY_FILE = ".last-online-use"
AUTH_SESSION_SECONDS = int(os.environ.get("ONLINE_STUDIO_AUTH_SECONDS", "2592000"))
KEY_ENVIRONMENTS = ("OPENAI_API_KEY", "DEEPSEEK_API_KEY", "LLM_API_KEY")
PROVIDERS = {
    "openai": ("OPENAI_API_KEY", "gpt-5-nano"),
    "deepseek": ("DEEPSEEK_API_KEY", "deepseek-v4-flash"),
}
# Every online session shares one server-held DeepSeek key (no per-user
# bring-your-own-key flow anymore); a hard per-user RMB cap bounds the
# exposure from that shared credential. The USD->RMB rate is a fixed,
# documented approximation, not a live quote -- it only needs to be roughly
# right for a soft-landing spend cap, not exact billing reconciliation.
SHARED_PROVIDER = "deepseek"
USD_TO_RMB_RATE = float(os.environ.get("ONLINE_STUDIO_USD_TO_RMB_RATE", "7.2"))
USER_SPEND_CAP_RMB = float(os.environ.get("ONLINE_STUDIO_SPEND_CAP_RMB", "200"))
DEFAULT_SECTIONS = (
    ("abstract", "Abstract", "abstract", "Summarize the problem, approach, evidence, and main conclusion in one self-contained paragraph."),
    ("introduction", "Introduction", "section", "Motivate the research problem, identify the precise gap, and state the paper's contributions without overclaiming."),
    ("related_work", "Related Work", "section", "Position the work against the closest research threads and make the distinction from prior work explicit."),
    ("method", "Method", "section", "Explain the proposed approach, its design choices, and enough operational detail for a technical reader to reproduce it."),
    ("experiments", "Experiments", "section", "Describe the evaluation protocol and report only results supported by the uploaded evidence; preserve placeholders for missing measurements."),
    ("discussion", "Discussion", "section", "Interpret the evidence, discuss limitations and failure modes, and separate observations from hypotheses."),
    ("conclusion", "Conclusion", "section", "Close the argument with the supported findings, limitations, and concrete future work."),
)

# Path 02 remains a compact paragraph-by-paragraph writing workflow, but one paragraph per section
# cannot produce a reviewable conference-paper body. These are manuscript roles,
# not inferred researcher preferences; each role is independently aligned to a
# real excerpt from the selected author-owned structural reference.
LIGHTWEIGHT_PARAGRAPH_PURPOSES = {
    "abstract": [
        "Summarize the problem, approach, evidence, and main conclusion in one self-contained paragraph.",
    ],
    "introduction": [
        "Establish the concrete problem and why it matters using only project evidence.",
        "Explain the closest unresolved gap and why existing approaches do not settle it.",
        "State the proposed approach, supported findings, and contributions without overclaiming.",
        "Define the evaluation question and claim boundary that the method and experiments must resolve.",
    ],
    "related_work": [
        "Organize the closest methodological research thread and identify its boundary relative to this work.",
        "Cover the closest task or evaluation thread and state this paper's evidence-backed distinction.",
        "Synthesize the two threads into the precise position occupied by this paper without inventing citations.",
    ],
    "method": [
        "Give an overview of the proposed approach and connect each component to the research problem.",
        "Define the core procedure, notation, and design choices precisely enough to reproduce it.",
        "Describe training or execution details and distinguish fixed choices from tested variables.",
        "Explain the method's expected mechanism while marking any unsupported causal account as a hypothesis.",
    ],
    "experiments": [
        "Describe datasets, baselines, metrics, and evaluation protocol using only uploaded evidence.",
        "Report the main comparison and introduce the bound table and Python data figure without inventing values.",
        "Analyze the supported result pattern and state what the evidence does and does not establish.",
        "Close the evaluation with robustness checks or explicit evidence gaps, preserving placeholders where measurements are absent.",
    ],
    "discussion": [
        "Interpret the findings, separate observation from hypothesis, and explain practical implications.",
        "Discuss limitations, failure modes, and threats to validity grounded in the project materials.",
    ],
    "conclusion": [
        "Close the argument with supported findings, limitations, and concrete future work.",
    ],
}


class OnlineStudioError(RuntimeError):
    """A safe, user-facing online gateway error."""


_EXPORT_EXCLUDED_DIR_NAMES = {"__pycache__", ".git"}
_EXPORT_EXCLUDED_FILE_SUFFIXES = {".pyc", ".pyo"}
_EXPORT_EXCLUDED_FILE_NAMES = {".DS_Store"}


def _project_zip_bytes(root: Path) -> bytes:
    """Build a bounded project export without following Agent-created symlinks."""
    files: list[Path] = []
    total = 0
    for path in sorted(root.rglob("*")):
        try:
            if path.is_symlink() or not path.is_file():
                continue
        except FileNotFoundError:
            # Preview/build workers create and remove bounded temporary
            # directories under the project while an export is being scanned.
            continue
        relative_parts = path.relative_to(root).parts
        if _EXPORT_EXCLUDED_DIR_NAMES.intersection(relative_parts[:-1]):
            continue
        if path.suffix in _EXPORT_EXCLUDED_FILE_SUFFIXES or path.name in _EXPORT_EXCLUDED_FILE_NAMES:
            continue
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            continue
        files.append(path)
        total += size
        if len(files) > MAX_EXPORT_FILES or total > MAX_EXPORT_BYTES:
            raise OnlineStudioError("项目过大，无法导出 ZIP；请先删除不需要的生成缓存。")
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            try:
                archive.write(path, path.relative_to(root).as_posix())
            except FileNotFoundError:
                # A transient compiler file may disappear after rglob/stat but
                # before ZipFile opens it. Stable project files still export;
                # an ephemeral preview log must never cancel the download.
                continue
    return stream.getvalue()


@dataclass
class Session:
    session_id: str
    user_id: str
    root: Path
    provider: str
    model: str
    process: subprocess.Popen[bytes]
    port: int
    # In-memory only, exactly like the child process's own environment
    # variable copy of the same value: never logged, persisted, or returned
    # to the browser. Kept so a crashed child (see _ensure_session_alive)
    # can be respawned without asking the researcher to re-enter it.
    api_key: str = ""
    kind: str = "user"
    created_at: float = field(default_factory=time.time)
    last_access: float = field(default_factory=time.time)


@dataclass
class OnboardingJob:
    job_id: str
    user_id: str
    status: str = "running"
    stage: str = "queued"
    message: str = "正在校验上传材料…"
    progress: int = 2
    session_id: str = ""
    error: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


SESSIONS: dict[str, Session] = {}
SESSIONS_LOCK = threading.RLock()
ONBOARDING_JOBS: dict[str, OnboardingJob] = {}
ONBOARDING_JOBS_LOCK = threading.RLock()
DEMO_SESSION: Session | None = None
DEMO_SESSION_LOCK = threading.RLock()
OAUTH_STATES: dict[str, tuple[str, float]] = {}
OAUTH_STATES_LOCK = threading.RLock()
DATA_ROOT = Path(
    os.environ.get("ONLINE_STUDIO_DATA_ROOT", Path.cwd() / ".online-paper-studio")
).resolve()


class _VisibleHTMLText(HTMLParser):
    """Extract visible block text without executing or retaining markup."""

    BLOCK_TAGS = {
        "article", "aside", "blockquote", "br", "div", "dd", "dl", "dt",
        "figcaption", "footer", "h1", "h2", "h3", "h4", "h5", "h6",
        "header", "li", "main", "nav", "ol", "p", "pre", "section", "table",
        "td", "th", "tr", "ul",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hidden_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in {"script", "style", "noscript"}:
            self.hidden_depth += 1
        elif not self.hidden_depth and tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            self.hidden_depth = max(0, self.hidden_depth - 1)
        elif not self.hidden_depth and tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            self.parts.append(data)

    def text(self) -> str:
        return "\n".join(
            line.strip()
            for line in "".join(self.parts).splitlines()
            if line.strip()
        )


class _HTMLIdentity(HTMLParser):
    """Read only the document title and first heading from an uploaded page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.capture: str | None = None
        self.parts: dict[str, list[str]] = {"title": [], "h1": []}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in self.parts and not self.parts[tag]:
            self.capture = tag

    def handle_endtag(self, tag: str) -> None:
        if self.capture == tag:
            self.capture = None

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.parts[self.capture].append(data)

    def value(self, tag: str) -> str:
        return " ".join("".join(self.parts[tag]).split()).strip()


class _ResultArtifactTables(HTMLParser):
    """Extract verified table-shaped evidence from canonical 05 HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.artifact_id: str | None = None
        self.artifact_tag: str | None = None
        self.artifact_tag_depth = 0
        self.row: list[str] | None = None
        self.cell_tag: str | None = None
        self.cell_parts: list[str] = []
        self.rows: dict[str, list[list[str]]] = {}
        self.artifact_ids: list[str] = []
        self.target_ids: set[str] = set()
        self.result_ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.cell_tag and tag not in {"th", "td"}:
            self.cell_parts.append(" ")
        attributes = {key: value or "" for key, value in attrs}
        artifact_id = attributes.get("data-artifact-id", "").strip()
        if artifact_id:
            self.artifact_ids.append(artifact_id)
            if self.artifact_id is None:
                self.artifact_id = artifact_id
                self.artifact_tag = tag
                self.artifact_tag_depth = 1
        elif self.artifact_id and tag == self.artifact_tag:
            self.artifact_tag_depth += 1
        target_id = attributes.get("data-target-id", "").strip()
        result_id = attributes.get("data-result-id", "").strip()
        if target_id:
            self.target_ids.add(target_id)
        if result_id:
            self.result_ids.add(result_id)
        if self.artifact_id and tag == "tr":
            self.row = []
        if self.artifact_id and self.row is not None and tag in {"th", "td"}:
            self.cell_tag = tag
            self.cell_parts = []

    def handle_data(self, data: str) -> None:
        if self.cell_tag:
            self.cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.cell_tag == tag and self.row is not None:
            self.row.append(" ".join("".join(self.cell_parts).split()).strip())
            self.cell_tag = None
            self.cell_parts = []
        if tag == "tr" and self.artifact_id and self.row is not None:
            if any(self.row):
                self.rows.setdefault(self.artifact_id, []).append(self.row)
            self.row = None
        if self.artifact_id and tag == self.artifact_tag:
            self.artifact_tag_depth -= 1
        if self.artifact_id and self.artifact_tag_depth == 0:
            self.artifact_id = None
            self.artifact_tag = None


def _database() -> sqlite3.Connection:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATA_ROOT / "auth.sqlite3", timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            subject TEXT NOT NULL,
            email TEXT NOT NULL,
            password_salt BLOB,
            password_hash BLOB,
            created_at INTEGER NOT NULL,
            UNIQUE(provider, subject)
        );
        CREATE TABLE IF NOT EXISTS auth_sessions (
            token_hash TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at INTEGER NOT NULL,
            created_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS auth_sessions_user_id
            ON auth_sessions(user_id);
        """
    )
    return connection


def _normalize_email(value: Any) -> str:
    email = str(value or "").strip().lower()
    if (
        len(email) > 254
        or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email)
        or any(ord(character) < 32 for character in email)
    ):
        raise OnlineStudioError("请输入有效的邮箱地址。")
    return email


def _password_digest(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        600_000,
        dklen=32,
    )


def create_local_user(email_value: Any, password_value: Any) -> dict[str, str]:
    email = _normalize_email(email_value)
    password = str(password_value or "")
    if len(password) < 6 or len(password) > 1024:
        raise OnlineStudioError("密码必须为 6–1024 个字符。")
    salt = secrets.token_bytes(16)
    digest = _password_digest(password, salt)
    user_id = secrets.token_urlsafe(24)
    try:
        with _database() as connection:
            connection.execute(
                """
                INSERT INTO users
                    (id, provider, subject, email, password_salt, password_hash, created_at)
                VALUES (?, 'local', ?, ?, ?, ?, ?)
                """,
                (user_id, email, email, salt, digest, int(time.time())),
            )
    except sqlite3.IntegrityError as exc:
        raise OnlineStudioError("该邮箱已经注册，请直接登录。") from exc
    return {"id": user_id, "email": email, "provider": "local"}


def authenticate_local_user(email_value: Any, password_value: Any) -> dict[str, str]:
    email = _normalize_email(email_value)
    password = str(password_value or "")
    with _database() as connection:
        row = connection.execute(
            """
            SELECT id, email, provider, password_salt, password_hash
            FROM users WHERE provider = 'local' AND subject = ?
            """,
            (email,),
        ).fetchone()
    # Run the same expensive hash for unknown users to reduce account probing.
    salt = bytes(row["password_salt"]) if row else b"\0" * 16
    expected = bytes(row["password_hash"]) if row else b"\0" * 32
    try:
        actual = _password_digest(password, salt)
    except (ValueError, OverflowError):
        actual = b"\1" * 32
    if not row or not secrets.compare_digest(actual, expected):
        raise OnlineStudioError("邮箱或密码不正确。")
    return {"id": str(row["id"]), "email": str(row["email"]), "provider": "local"}


def google_user(subject: str, email_value: Any) -> dict[str, str]:
    email = _normalize_email(email_value)
    with _database() as connection:
        row = connection.execute(
            "SELECT id, email, provider FROM users WHERE provider = 'google' AND subject = ?",
            (subject,),
        ).fetchone()
        if row is None:
            user_id = secrets.token_urlsafe(24)
            connection.execute(
                """
                INSERT INTO users (id, provider, subject, email, created_at)
                VALUES (?, 'google', ?, ?, ?)
                """,
                (user_id, subject, email, int(time.time())),
            )
            return {"id": user_id, "email": email, "provider": "google"}
        if str(row["email"]) != email:
            connection.execute("UPDATE users SET email = ? WHERE id = ?", (email, row["id"]))
        return {"id": str(row["id"]), "email": email, "provider": "google"}


def create_auth_session(user_id: str) -> str:
    token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = int(time.time())
    with _database() as connection:
        connection.execute(
            """
            INSERT INTO auth_sessions (token_hash, user_id, expires_at, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (token_hash, user_id, now + AUTH_SESSION_SECONDS, now),
        )
        connection.execute("DELETE FROM auth_sessions WHERE expires_at <= ?", (now,))
    return token


def authenticated_user(cookie_header: str | None) -> dict[str, str] | None:
    token = _cookie_value(cookie_header, AUTH_COOKIE_NAME)
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = int(time.time())
    with _database() as connection:
        row = connection.execute(
            """
            SELECT users.id, users.email, users.provider
            FROM auth_sessions
            JOIN users ON users.id = auth_sessions.user_id
            WHERE auth_sessions.token_hash = ? AND auth_sessions.expires_at > ?
            """,
            (token_hash, now),
        ).fetchone()
    if row is None:
        return None
    return {"id": str(row["id"]), "email": str(row["email"]), "provider": str(row["provider"])}


def revoke_auth_session(cookie_header: str | None) -> None:
    token = _cookie_value(cookie_header, AUTH_COOKIE_NAME)
    if not token:
        return
    with _database() as connection:
        connection.execute(
            "DELETE FROM auth_sessions WHERE token_hash = ?",
            (hashlib.sha256(token.encode("utf-8")).hexdigest(),),
        )


def _cookie_value(header: str | None, name: str) -> str | None:
    if not header:
        return None
    cookie = SimpleCookie()
    try:
        cookie.load(header)
    except Exception:
        return None
    morsel = cookie.get(name)
    return morsel.value if morsel is not None else None


def _secure_cookies() -> bool:
    return os.environ.get("ONLINE_STUDIO_SECURE_COOKIE", "").lower() in {
        "1",
        "true",
        "yes",
    }


def _public_registration() -> bool:
    return os.environ.get("ONLINE_STUDIO_PUBLIC_REGISTRATION", "").lower() in {
        "1",
        "true",
        "yes",
    }


def _auth_cookie(token: str, *, clear: bool = False) -> str:
    value = "" if clear else token
    attributes = f"{AUTH_COOKIE_NAME}={value}; Path=/; HttpOnly; SameSite=Strict"
    if clear:
        attributes += "; Max-Age=0"
    else:
        attributes += f"; Max-Age={AUTH_SESSION_SECONDS}"
    if _secure_cookies():
        attributes += "; Secure"
    return attributes


def google_login_configured() -> bool:
    return all(
        os.environ.get(name)
        for name in (
            "GOOGLE_OAUTH_CLIENT_ID",
            "GOOGLE_OAUTH_CLIENT_SECRET",
            "ONLINE_STUDIO_PUBLIC_URL",
        )
    )


def exchange_google_code(code: str, redirect_uri: str) -> str:
    form = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        token_payload = json.loads(response.read().decode("utf-8"))
    encoded_id_token = str(token_payload.get("id_token") or "")
    if not encoded_id_token:
        raise OnlineStudioError("Google 未返回 ID token。")
    return encoded_id_token


def verify_google_id_token(encoded_id_token: str) -> dict[str, Any]:
    try:
        from google.auth.transport.requests import Request as GoogleRequest
        from google.oauth2 import id_token as google_id_token
    except ImportError as exc:
        raise OnlineStudioError("服务端缺少 Google 登录验证依赖。") from exc
    claims = google_id_token.verify_oauth2_token(
        encoded_id_token,
        GoogleRequest(),
        os.environ["GOOGLE_OAUTH_CLIENT_ID"],
    )
    if not isinstance(claims, dict):
        raise OnlineStudioError("Google ID token 内容无效。")
    return claims


def _safe_slug(value: str, fallback: str = "online-paper") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (slug or fallback)[:64]


def _latex_escape(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(character, character) for character in value)


def _scholarly_bibtex_from_url(url: str) -> tuple[str, str] | None:
    """Fetch one BibTeX record from a primary scholarly record URL."""
    normalized = str(url or "").strip().rstrip("/")
    try:
        if re.fullmatch(r"https://aclanthology\.org/[^/]+", normalized):
            request = urllib.request.Request(normalized + ".bib", headers={"User-Agent": "ResearchAvatar/1.0"})
            with urllib.request.urlopen(request, timeout=15) as response:
                bibtex = response.read().decode("utf-8", errors="replace").strip()
            match = re.search(r"@\w+\s*\{\s*([^,\s]+)", bibtex)
            if match and bibtex.count("{") == bibtex.count("}"):
                return match.group(1), bibtex
            return None
        arxiv = re.fullmatch(r"https?://(?:www\.)?arxiv\.org/abs/([0-9]+\.[0-9]+)(?:v\d+)?", normalized)
        if arxiv:
            identifier = arxiv.group(1)
            request = urllib.request.Request(
                "https://export.arxiv.org/api/query?id_list=" + urllib.parse.quote(identifier),
                headers={"User-Agent": "ResearchAvatar/1.0"},
            )
            with urllib.request.urlopen(request, timeout=15) as response:
                feed = ET.fromstring(response.read())
            atom = "{http://www.w3.org/2005/Atom}"
            entry = feed.find(atom + "entry")
            if entry is None:
                return None
            title = re.sub(r"\s+", " ", entry.findtext(atom + "title") or "").strip()
            published = entry.findtext(atom + "published") or ""
            authors = [
                re.sub(r"\s+", " ", node.findtext(atom + "name") or "").strip()
                for node in entry.findall(atom + "author")
            ]
            if not title or not authors or not re.match(r"\d{4}", published):
                return None
            key = "arxiv" + identifier.replace(".", "")
            bibtex = "\n".join([
                f"@misc{{{key},",
                f"  title = {{{_latex_escape(title)}}},",
                f"  author = {{{' and '.join(_latex_escape(name) for name in authors)}}},",
                f"  year = {{{published[:4]}}},",
                f"  eprint = {{{identifier}}},",
                "  archivePrefix = {arXiv},",
                f"  url = {{https://arxiv.org/abs/{identifier}}}",
                "}",
            ])
            return key, bibtex
    except (OSError, ValueError, ET.ParseError, urllib.error.URLError):
        return None
    return None


def _verified_contract_bibliography(contract: dict[str, Any] | None) -> list[tuple[str, str]]:
    """Resolve plan-declared scholarly URLs without using the structural reference."""
    if not isinstance(contract, dict):
        return []
    structural_url = str(
        (((contract.get("references") or {}).get("researcher_owned_logic") or {}).get("url"))
        or ""
    ).strip().rstrip("/")
    records: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    candidates: list[Any] = []
    candidates.extend(contract.get("dataset_citations") or [])
    candidates.extend(((contract.get("baseline_contract") or {}).get("selected") or []))
    candidates.extend(contract.get("metric_contract") or [])
    for item in candidates:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip().rstrip("/")
        if not url or url == structural_url or url in seen_urls:
            continue
        seen_urls.add(url)
        record = _scholarly_bibtex_from_url(url)
        if record is not None:
            records.append(record)
        if len(records) >= 12:
            break
    return records


def _validated_sections(raw_sections: Any) -> list[tuple[str, str, str, str]]:
    if raw_sections is None:
        return list(DEFAULT_SECTIONS)
    if not isinstance(raw_sections, list) or not 2 <= len(raw_sections) <= 12:
        raise OnlineStudioError("论文结构必须包含 2–12 个 section。")
    sections: list[tuple[str, str, str, str]] = []
    used_ids: set[str] = set()
    for index, item in enumerate(raw_sections):
        if not isinstance(item, dict):
            raise OnlineStudioError("论文结构格式无效。")
        title = str(item.get("title") or "").strip()
        purpose = str(item.get("purpose") or "").strip()
        if not title or len(title) > 80 or not title.isascii():
            raise OnlineStudioError("Section 标题必须是 1–80 个字符的英文/ASCII 文本。")
        if len(purpose) < 10 or len(purpose) > 800:
            raise OnlineStudioError("每个 section 的写作目的必须为 10–800 个字符。")
        render = "abstract" if index == 0 else "section"
        if index == 0 and title.lower() != "abstract":
            raise OnlineStudioError("第一个 section 必须是 Abstract。")
        section_id = "abstract" if index == 0 else _safe_slug(title, f"section-{index + 1}").replace("-", "_")
        if section_id in used_ids:
            raise OnlineStudioError(f"Section 标题生成了重复 ID：{title}")
        used_ids.add(section_id)
        sections.append((section_id, title, render, purpose))
    return sections


def _decode_html_files(raw_files: Any) -> list[tuple[str, str]]:
    if not isinstance(raw_files, list) or not raw_files:
        raise OnlineStudioError("请至少上传一个 HTML 文件。")
    if len(raw_files) > MAX_FILES:
        raise OnlineStudioError(f"一次最多上传 {MAX_FILES} 个 HTML 文件。")
    decoded: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in raw_files:
        if not isinstance(item, dict):
            raise OnlineStudioError("上传文件格式无效。")
        name = Path(str(item.get("name") or "")).name
        if not name or name.lower() in seen or Path(name).suffix.lower() not in {".html", ".htm"}:
            raise OnlineStudioError("文件必须是名称唯一的 .html 或 .htm 文件。")
        try:
            content = base64.b64decode(str(item.get("data") or ""), validate=True)
        except (ValueError, TypeError) as exc:
            raise OnlineStudioError(f"{name} 不是有效的上传内容。") from exc
        if not content or len(content) > MAX_FILE_BYTES:
            raise OnlineStudioError(f"{name} 必须非空且不超过 8 MB。")
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise OnlineStudioError(f"{name} 必须使用 UTF-8 编码。") from exc
        decoded.append((name, text))
        seen.add(name.lower())
    return decoded


DOCUMENT_SUFFIXES = {
    ".doc",
    ".docx",
    ".txt",
    ".pdf",
    ".md",
    ".markdown",
    ".json",
    ".html",
    ".htm",
}


def _extract_document_text(name: str, content: bytes) -> str:
    suffix = Path(name).suffix.lower()
    if suffix in {".txt", ".md", ".markdown"}:
        try:
            return content.decode("utf-8-sig").strip()
        except UnicodeDecodeError as exc:
            raise OnlineStudioError(f"{name} 必须使用 UTF-8 编码。") from exc
    if suffix == ".json":
        try:
            value = json.loads(content.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OnlineStudioError(f"{name} 不是有效的 UTF-8 JSON 文件。") from exc
        return json.dumps(value, ensure_ascii=False, indent=2)
    if suffix in {".html", ".htm"}:
        try:
            source = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise OnlineStudioError(f"{name} 必须使用 UTF-8 编码。") from exc
        parser = _VisibleHTMLText()
        parser.feed(source)
        parser.close()
        visible = parser.text().strip()
        # A complete project brief may itself be the approved Experiment Plan.
        # Its machine-readable contract lives in a non-visible JSON <script>,
        # so a visible-text-only extraction silently discarded the exact paper
        # outline and all figure/table obligations before lightweight onboarding
        # saw them. Preserve only this named JSON payload (never arbitrary
        # scripts) beside the human-readable text for the downstream parser.
        contract_match = re.search(
            r'<script\b[^>]*\bid=["\']experiment-plan-contract["\'][^>]*>'
            r'(.*?)</script>',
            source,
            re.IGNORECASE | re.DOTALL,
        )
        if contract_match is not None:
            try:
                contract = json.loads(contract_match.group(1))
            except json.JSONDecodeError as exc:
                raise OnlineStudioError(
                    f"{name} 的 experiment-plan-contract 不是有效 JSON。"
                ) from exc
            if not isinstance(contract, dict):
                raise OnlineStudioError(
                    f"{name} 的 experiment-plan-contract 必须是 JSON object。"
                )
            visible += (
                "\n\n<experiment-plan-contract>\n"
                + json.dumps(contract, ensure_ascii=False)
                + "\n</experiment-plan-contract>"
            )
        return visible
    if suffix == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = [
                    item
                    for item in archive.namelist()
                    if item == "word/document.xml"
                    or re.fullmatch(r"word/(?:header|footer)\d+\.xml", item)
                ]
                blocks: list[str] = []
                for member in names:
                    root = ET.fromstring(archive.read(member))
                    parts: list[str] = []
                    for element in root.iter():
                        tag = element.tag.rsplit("}", 1)[-1]
                        if tag == "t" and element.text:
                            parts.append(element.text)
                        elif tag in {"p", "br", "tab"}:
                            parts.append("\n" if tag != "tab" else "\t")
                    text = "".join(parts).strip()
                    if text:
                        blocks.append(text)
                return "\n\n".join(blocks)
        except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
            raise OnlineStudioError(f"{name} 不是有效的 DOCX 文件。") from exc
    if suffix == ".pdf":
        return _extract_pdf_text_with_llm(name, content)
    command = None
    if suffix == ".doc":
        if shutil.which("antiword"):
            command = ["antiword"]
        elif shutil.which("textutil"):
            command = ["textutil", "-convert", "txt", "-stdout"]
        else:
            raise OnlineStudioError(
                "服务器缺少读取 DOC 的工具 antiword（macOS 本地也可使用 textutil）。"
            )
    if command:
        if shutil.which(command[0]) is None:
            raise OnlineStudioError(
                f"服务器缺少读取 {suffix.upper().lstrip('.')} 的工具 {command[0]}。"
            )
        with tempfile.NamedTemporaryFile(suffix=suffix) as handle:
            handle.write(content)
            handle.flush()
            completed = subprocess.run(
                [*command, handle.name, "-"] if suffix == ".pdf" else [*command, handle.name],
                capture_output=True,
                timeout=45,
                check=False,
            )
        if completed.returncode:
            raise OnlineStudioError(f"无法从 {name} 提取文本。")
        return completed.stdout.decode("utf-8", errors="replace").strip()
    raise OnlineStudioError(f"不支持的文档格式：{name}。")


def _extract_pdf_text_with_llm(name: str, content: bytes) -> str:
    """Extract PDF layout locally, then restore semantic order with DeepSeek."""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise OnlineStudioError(
            "服务端缺少 DEEPSEEK_API_KEY，无法整理 PDF 文本。"
        )
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        raise OnlineStudioError("服务器缺少 PDF 文本提取工具 pdftotext。")
    with tempfile.NamedTemporaryFile(suffix=".pdf") as handle:
        handle.write(content)
        handle.flush()
        try:
            completed = subprocess.run(
                [pdftotext, "-layout", handle.name, "-"],
                capture_output=True,
                timeout=120,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise OnlineStudioError(f"提取 {name} 的页面文本时超时。") from exc
    if completed.returncode:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise OnlineStudioError(
            f"无法从 {name} 提取页面文本：{detail[-300:] or 'pdftotext failed'}"
        )
    layout_text = completed.stdout.decode("utf-8", errors="replace").strip()
    if len(layout_text) < 200:
        raise OnlineStudioError(f"{name} 没有足够的可提取文本；当前不支持纯扫描 PDF。")
    if len(layout_text) > MAX_STRUCTURE_REFERENCE_CHARS:
        raise OnlineStudioError(
            f"{name} 提取后超过 {MAX_STRUCTURE_REFERENCE_CHARS} 字符，请上传较短的参考论文。"
        )
    model = os.environ.get(
        "DEEPSEEK_PDF_EXTRACTION_MODEL", PROVIDERS["deepseek"][1]
    ).strip() or PROVIDERS["deepseek"][1]
    prompt = """Restore the supplied layout-preserving PDF text into semantic reading order.
Return only the transcript, with no commentary and no Markdown code fence.

Requirements:
1. Preserve the paper's wording. Do not summarize, paraphrase, infer, or add text.
2. Preserve section/subsection headings and natural paragraph boundaries.
3. For every multi-column page, finish the left column before reading the right column.
4. Reconstruct words split by visual line wrapping. Remove discretionary line-break
   hyphens, including the invisible U+00AD soft hyphen (for example,
   "under<soft-hyphen>standing" must become "understanding"), while preserving
   genuine lexical hyphens.
5. Omit page headers, page footers, line numbers, and standalone page numbers.
6. Start the transcript with the paper's actual scholarly title, even when a copyright,
   permission, publisher, or repository notice appears earlier in the PDF layout. Omit
   those legal/distribution notices from the transcript. Then include the abstract, all
   main-paper sections, captions, appendices, and references.
7. Put each heading and each natural paragraph in its own block separated by one blank line.
8. Treat form-feed characters as page boundaries. Never invent text absent from the input.

<layout_preserving_pdf_text>
""" + layout_text + "\n</layout_preserving_pdf_text>"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Preserve only supplied text and reading order."},
            {"role": "user", "content": prompt},
        ],
        "thinking": {"type": "disabled"},
        "temperature": 0.0,
        "max_tokens": 16000,
    }
    request = urllib.request.Request(
        os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise OnlineStudioError(
            f"LLM 读取 {name} 时 API 返回 HTTP {exc.code}：{detail[:500]}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
        reason = getattr(exc, "reason", str(exc))
        raise OnlineStudioError(f"LLM 读取 {name} 时 API 连接失败：{reason}") from exc
    except json.JSONDecodeError as exc:
        raise OnlineStudioError(f"LLM 读取 {name} 时返回了无效 JSON。") from exc
    choices = body.get("choices") or []
    transcript = (
        str((choices[0].get("message") or {}).get("content") or "").strip()
        if choices else ""
    )
    if len(transcript) < 200:
        raise OnlineStudioError(
            f"DeepSeek 未能完整整理 {name} 的文本。"
        )
    return transcript


def _decode_document_files(
    raw_files: Any,
    *,
    label: str,
    required: bool,
    max_files: int = MAX_FILES,
) -> list[tuple[str, str]]:
    if raw_files in (None, []):
        if required:
            raise OnlineStudioError(f"请上传{label}。")
        return []
    if not isinstance(raw_files, list) or not raw_files:
        raise OnlineStudioError(f"{label}上传格式无效。")
    if len(raw_files) > max_files:
        raise OnlineStudioError(f"{label}一次最多上传 {max_files} 个文件。")
    decoded: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in raw_files:
        if not isinstance(item, dict):
            raise OnlineStudioError(f"{label}上传格式无效。")
        name = Path(str(item.get("name") or "")).name
        suffix = Path(name).suffix.lower()
        if not name or name.lower() in seen or suffix not in DOCUMENT_SUFFIXES:
            raise OnlineStudioError(
                f"{label}必须使用名称唯一的 DOC、DOCX、TXT、PDF、Markdown、JSON 或 HTML 文件。"
            )
        try:
            content = base64.b64decode(str(item.get("data") or ""), validate=True)
        except (ValueError, TypeError) as exc:
            raise OnlineStudioError(f"{name} 不是有效的上传内容。") from exc
        if not content or len(content) > MAX_FILE_BYTES:
            raise OnlineStudioError(f"{name} 必须非空且不超过 8 MB。")
        text = _extract_document_text(name, content)
        if not text.strip():
            raise OnlineStudioError(f"{name} 没有可用于写作的文本。")
        decoded.append((name, text.strip()))
        seen.add(name.lower())
    return decoded


def _plain_source_text(files: list[tuple[str, str]], role: str) -> str:
    return "\n\n".join(
        f"SOURCE ROLE: {role}\nSOURCE: {name}\n{text}" for name, text in files
    ).strip()


def _canonical_pipeline_sources(files: list[tuple[str, str]]) -> dict[str, str]:
    expected = {
        "profile.html": "PROFILE.html",
        "03_experiment_plan.html": "03_EXPERIMENT_PLAN.html",
        "05_exp_result.html": "05_EXP_RESULT.html",
    }
    sources = {name.lower(): source for name, source in files}
    missing = [display for key, display in expected.items() if key not in sources]
    extras = [name for name, _source in files if name.lower() not in expected]
    if missing:
        raise OnlineStudioError("缺少必需文件：" + "、".join(missing) + "。")
    if extras:
        raise OnlineStudioError(
            "HTML 上传区只接受 PROFILE、03 和 05；其他证据请放入 ZIP："
            + "、".join(extras)
        )
    return {display: sources[key] for key, display in expected.items()}


def _script_json(source: str, identifier: str) -> dict[str, Any]:
    match = re.search(
        rf'<script\b[^>]*\bid=["\']{re.escape(identifier)}["\'][^>]*>(.*?)</script>',
        source,
        re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        raise OnlineStudioError(f"上传文件缺少 {identifier} 数据契约。")
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise OnlineStudioError(f"{identifier} 数据契约不是有效 JSON。") from exc
    if not isinstance(payload, dict):
        raise OnlineStudioError(f"{identifier} 数据契约必须是 JSON object。")
    return payload


def _decode_evidence_archive(raw_archive: Any) -> bytes:
    if not isinstance(raw_archive, dict):
        raise OnlineStudioError("请上传研究证据 ZIP。")
    name = Path(str(raw_archive.get("name") or "")).name
    if Path(name).suffix.lower() != ".zip":
        raise OnlineStudioError("研究证据包必须是 .zip 文件。")
    try:
        content = base64.b64decode(str(raw_archive.get("data") or ""), validate=True)
    except (ValueError, TypeError) as exc:
        raise OnlineStudioError("研究证据 ZIP 内容无效。") from exc
    if not content or len(content) > MAX_ARCHIVE_BYTES:
        raise OnlineStudioError("研究证据 ZIP 必须非空且不超过 32 MB。")
    return content


def _archive_path_allowed(path: Path) -> bool:
    value = path.as_posix()
    return (
        value.startswith("results/")
        or value.startswith("figures/")
        or value.startswith("paper/fig/")
        or value.startswith("paper/figsrc/")
        or value.startswith("references/")
        or value.startswith("researcher-profile/fulltext/")
        or (value.startswith("reports/sources/") and path.suffix.lower() == ".txt")
        or value in {
            "project-package.json",
            "researcher-profile/PROFILE.html",
            "researcher-profile/publications.json",
            "code/RESULTS_LEDGER.csv",
            "reports/01_LIT_SURVEY.html",
            "reports/02_IDEA_REPORT.html",
            "reports/03_EXPERIMENT_PLAN.html",
            "reports/04_RUN_PLAN.html",
            "reports/05_EXP_RESULT.html",
        }
    )


def _extract_evidence_archive(content: bytes, root: Path) -> None:
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise OnlineStudioError("研究证据包不是有效 ZIP。") from exc
    infos = [item for item in archive.infolist() if not item.is_dir()]
    if not infos or len(infos) > MAX_ARCHIVE_FILES:
        raise OnlineStudioError(f"研究证据 ZIP 必须包含 1–{MAX_ARCHIVE_FILES} 个文件。")
    expanded = 0
    accepted: list[tuple[zipfile.ZipInfo, Path]] = []
    for info in infos:
        candidate = Path(info.filename.replace("\\", "/"))
        mode = (info.external_attr >> 16) & 0o170000
        if (
            candidate.is_absolute()
            or ".." in candidate.parts
            or not candidate.parts
            or mode == 0o120000
            or not _archive_path_allowed(candidate)
        ):
            raise OnlineStudioError(f"研究证据 ZIP 包含不允许的路径：{info.filename}")
        expanded += int(info.file_size)
        if expanded > MAX_ARCHIVE_EXPANDED_BYTES:
            raise OnlineStudioError("研究证据 ZIP 解压后不得超过 128 MB。")
        accepted.append((info, candidate))
    if not any(path.parts and path.parts[0] == "results" for _info, path in accepted):
        raise OnlineStudioError("研究证据 ZIP 必须包含非空的 results/ 目录。")
    if not any(path.as_posix() == "researcher-profile/publications.json" for _info, path in accepted):
        raise OnlineStudioError("研究证据 ZIP 必须包含 researcher-profile/publications.json。")
    if not any(path.as_posix() == "references/logic-reference.txt" for _info, path in accepted):
        raise OnlineStudioError("研究项目 ZIP 必须包含 03 选定的 references/logic-reference.txt。")
    for info, relative in accepted:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(info) as source, target.open("wb") as destination:
            shutil.copyfileobj(source, destination)


def _validate_project_package(root: Path) -> None:
    manifest_path = root / "project-package.json"
    if not manifest_path.is_file():
        raise OnlineStudioError("研究项目 ZIP 缺少 project-package.json。")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OnlineStudioError("project-package.json 不是有效 JSON。") from exc
    if manifest.get("schema_version") != "2.0" or manifest.get("kind") != "research-avatar-paper-input":
        raise OnlineStudioError("研究项目 ZIP 版本不受支持，请重新运行打包命令。")
    hashes = manifest.get("files")
    if not isinstance(hashes, dict):
        raise OnlineStudioError("project-package.json 缺少文件哈希。")
    required = {
        "researcher-profile/PROFILE.html",
        "researcher-profile/publications.json",
        "reports/01_LIT_SURVEY.html",
        "reports/02_IDEA_REPORT.html",
        "reports/03_EXPERIMENT_PLAN.html",
        "reports/04_RUN_PLAN.html",
        "reports/05_EXP_RESULT.html",
        "references/logic-reference.txt",
    }
    missing = sorted(required - set(hashes))
    if missing:
        raise OnlineStudioError("研究项目 ZIP 缺少必需文件：" + "、".join(missing))
    for name, expected in hashes.items():
        path = (root / str(name)).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError as exc:
            raise OnlineStudioError("project-package.json 包含越界路径。") from exc
        if not path.is_file():
            raise OnlineStudioError(f"研究项目 ZIP 清单文件不存在：{name}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if not secrets.compare_digest(actual, str(expected)):
            raise OnlineStudioError(f"研究项目 ZIP 文件哈希不匹配：{name}")


def _validated_upstream_contract(root: Path, plan_source: str, result_source: str) -> dict[str, Any]:
    contract = _script_json(plan_source, "experiment-plan-contract")
    if str(contract.get("schema_version")) != "1.2":
        raise OnlineStudioError("03 必须使用只含一篇作者自有逻辑参考的 schema 1.2 合同。")
    outline = contract.get("paper_outline")
    artifacts = contract.get("paper_artifacts")
    if not isinstance(outline, list) or not outline:
        raise OnlineStudioError("03 的 paper_outline 为空，无法构建 Paper Studio。")
    if not isinstance(artifacts, list):
        raise OnlineStudioError("03 的 paper_artifacts 格式无效。")
    target = contract.get("target")
    references = contract.get("references")
    structural_reference = (
        references.get("researcher_owned_logic")
        if isinstance(references, dict)
        else None
    )
    if not isinstance(target, dict) or not str(target.get("venue") or "").strip():
        raise OnlineStudioError("03 缺少已确认的 target conference。")
    if not isinstance(structural_reference, dict) or not str(
        structural_reference.get("title") or ""
    ).strip():
        raise OnlineStudioError("03 缺少已确认的作者自有逻辑 reference paper。")
    result_parser = _ResultArtifactTables()
    result_parser.feed(result_source)
    result_parser.close()
    duplicates = sorted(
        artifact_id
        for artifact_id in set(result_parser.artifact_ids)
        if result_parser.artifact_ids.count(artifact_id) > 1
    )
    if duplicates:
        raise OnlineStudioError("05 中存在重复 artifact：" + "、".join(duplicates))
    required_artifacts = {
        str(requirement.get("artifact_id"))
        for requirement in contract.get("result_requirements", [])
        if isinstance(requirement, dict) and requirement.get("artifact_id")
    }
    missing_artifacts = sorted(required_artifacts - set(result_parser.artifact_ids))
    if missing_artifacts:
        raise OnlineStudioError("05 缺少结果 artifact：" + "、".join(missing_artifacts))
    required_targets = {
        str(target)
        for requirement in contract.get("result_requirements", [])
        if isinstance(requirement, dict)
        for key in ("cell_ids", "panel_ids")
        for target in requirement.get(key, [])
    }
    missing_targets = sorted(required_targets - result_parser.target_ids)
    if missing_targets:
        raise OnlineStudioError(
            "05 尚未填满 03 规定的结果目标：" + "、".join(missing_targets[:12])
        )
    validation_commands = [
        [
            sys.executable,
            str(Path(__file__).resolve().parents[2] / "research_avatar/tools/validate_report_structure.py"),
            "--kind", "expplan", "--html", str(root / "reports/03_EXPERIMENT_PLAN.html"),
        ],
        [
            sys.executable,
            str(Path(__file__).resolve().parents[2] / "research_avatar/tools/validate_report_structure.py"),
            "--kind", "results", "--html", str(root / "reports/05_EXP_RESULT.html"),
        ],
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "tools/validate_experiment_plan.py"),
            "--plan", str(root / "reports/03_EXPERIMENT_PLAN.html"),
        ],
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "tools/plan_conformance.py"),
            "--plan", str(root / "reports/03_EXPERIMENT_PLAN.html"),
            "--results-dir", str(root / "results"),
            "--results-only",
        ],
    ]
    for command in validation_commands:
        completed = subprocess.run(
            command,
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if completed.returncode:
            detail = (completed.stderr or completed.stdout).strip().splitlines()
            raise OnlineStudioError(
                "上传产物未通过科研契约校验：" + (detail[0] if detail else "validator failed")
            )
    contract["_result_tables"] = result_parser.rows
    return contract


def _source_text(files: list[tuple[str, str]]) -> str:
    blocks: list[str] = []
    for name, source in files:
        parser = _VisibleHTMLText()
        parser.feed(source)
        parser.close()
        text = parser.text()
        if text:
            blocks.append(f"SOURCE: {name}\n{text}")
    merged = "\n\n".join(blocks).strip()
    if not merged:
        raise OnlineStudioError("上传的 HTML 没有可用于写作的文本。")
    if len(merged) > MAX_SOURCE_TEXT_CHARS:
        merged = (
            merged[:MAX_SOURCE_TEXT_CHARS].rstrip()
            + "\n\n[ONLINE STUDIO NOTE: additional uploaded text was truncated at the configured context limit.]"
        )
    return merged


def _project_identity(plan_source: str, contract: dict[str, Any]) -> tuple[str, str]:
    """Derive display metadata without replacing the approved scientific contract."""

    parser = _HTMLIdentity()
    parser.feed(plan_source)
    parser.close()
    source_plan = contract.get("source_plan")
    target = contract.get("target") if isinstance(contract.get("target"), dict) else {}
    candidates = [
        str(contract.get("paper_title") or "").strip(),
        str(contract.get("title") or "").strip(),
        str(source_plan.get("title") or "").strip() if isinstance(source_plan, dict) else "",
        parser.value("h1"),
        parser.value("title"),
    ]
    project_name = next((value for value in candidates if value), "Online Paper")[:160]
    title = next(
        (
            value
            for value in candidates
            if value and value.isascii() and len(value) <= 300
        ),
        "Research Paper Draft",
    )
    if title.lower().startswith("experiment plan"):
        title = "Research Paper Draft"
    venue = str(target.get("venue") or "").strip()
    if venue and venue not in project_name:
        project_name = f"{project_name} · {venue}"[:160]
    return project_name, title


def _outline_sections(contract: dict[str, Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    used: set[str] = set()
    for index, raw in enumerate(contract.get("paper_outline", []), 1):
        if not isinstance(raw, dict):
            raise OnlineStudioError("03 paper_outline section 必须是 object。")
        title = str(raw.get("title") or raw.get("name") or raw.get("id") or "").strip()
        if not title:
            raise OnlineStudioError("03 paper_outline 存在无标题 section。")
        candidate = str(raw.get("id") or "").strip()
        section_id = _safe_slug(candidate or title, f"section-{index}").replace("-", "_")
        if title.lower() == "abstract" or section_id == "abstract":
            section_id = "abstract"
        if section_id in used:
            raise OnlineStudioError(f"03 paper_outline section ID 重复：{section_id}")
        paragraphs = raw.get("paragraphs")
        if not isinstance(paragraphs, list) or not paragraphs:
            raise OnlineStudioError(f"03 section {title} 没有 paragraph blueprint。")
        normalized_paragraphs = []
        for paragraph_index, paragraph in enumerate(paragraphs, 1):
            if not isinstance(paragraph, dict):
                raise OnlineStudioError(f"03 section {title} 的 paragraph 格式无效。")
            paragraph_id = str(paragraph.get("id") or f"{section_id}-P{paragraph_index}").strip()
            purpose = str(paragraph.get("plan_sentence") or paragraph.get("purpose") or "").strip()
            if not paragraph_id or not purpose:
                raise OnlineStudioError(f"03 section {title} 存在缺少 ID 或规划句的 paragraph。")
            reference_mapping = paragraph.get("reference_mapping", [])
            reference_paragraph_ids = [
                str(
                    mapping.get("source_paragraph_id")
                    or mapping.get("reference_paragraph_id")
                    or mapping.get("id")
                    or ""
                ).strip()
                for mapping in reference_mapping
                if isinstance(mapping, dict)
            ] if isinstance(reference_mapping, list) else []
            normalized_paragraphs.append(
                {
                    "id": paragraph_id,
                    "purpose": purpose,
                    "rhetorical_role": str(paragraph.get("rhetorical_role") or "").strip(),
                    "relation_to_previous": str(paragraph.get("relation_to_previous") or "").strip(),
                    "relation_to_next": str(paragraph.get("relation_to_next") or "").strip(),
                    "artifacts": [str(item) for item in paragraph.get("artifact_refs", [])],
                    "artifact_dependencies": [
                        str(item)
                        for item in paragraph.get(
                            "artifact_dependencies", paragraph.get("artifact_refs", [])
                        )
                    ],
                    "heading": str(paragraph.get("heading") or paragraph.get("subsection") or "").strip(),
                    "heading_style": str(paragraph.get("heading_style") or "").strip(),
                    "reference_paragraph_ids": list(
                        dict.fromkeys(item for item in reference_paragraph_ids if item)
                    ),
                }
            )
            for field in ("rhetorical_role", "relation_to_previous", "relation_to_next"):
                if not normalized_paragraphs[-1][field]:
                    raise OnlineStudioError(f"03 paragraph {paragraph_id} 缺少已批准的 {field}。")
        normalized.append(
            {
                "id": section_id,
                "source_id": candidate or section_id,
                "title": title,
                "render": "abstract" if section_id == "abstract" else "section",
                "paragraphs": normalized_paragraphs,
                "reference_context": raw.get("reference_context", {}),
            }
        )
        used.add(section_id)
    return normalized


def _write_reference_contexts(
    root: Path,
    paper: Path,
    contexts: dict[str, Any],
    *,
    reference_source: str,
    reference_title: str,
) -> None:
    if not contexts:
        return
    payload = {
        "reference_title": reference_title,
        "reference_source": reference_source,
        "sections": contexts,
    }
    (paper / "reference_context.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _require_complete_reference_contexts(
    contexts: dict[str, Any], section_ids: list[str]
) -> dict[str, Any]:
    """Reject online scaffolds that lost any approved section-level reference."""
    expected = set(section_ids)
    actual = set(contexts)
    if actual != expected:
        missing = ", ".join(sorted(expected - actual)) or "none"
        extra = ", ".join(sorted(actual - expected)) or "none"
        raise OnlineStudioError(
            f"参考论文上下文与论文结构不一致（缺少：{missing}；多出：{extra}）。"
        )
    for section_id in section_ids:
        context = contexts.get(section_id)
        excerpts = context.get("excerpts") if isinstance(context, dict) else None
        if (
            not isinstance(context, dict)
            or not str(context.get("source_heading") or "").strip()
            or not str(context.get("logic_summary_zh") or "").strip()
            or not isinstance(excerpts, list)
            or not 1 <= len(excerpts) <= 3
            or any(
                not isinstance(item, dict)
                or not str(item.get("text") or "").strip()
                for item in excerpts
            )
        ):
            raise OnlineStudioError(f"{section_id} 的参考论文上下文不完整。")
    return contexts


def _artifact_rows(raw_rows: Any, labels: list[str]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rows = [list(map(str, row)) for row in raw_rows or [] if isinstance(row, list) and row]
    width = max([len(row) for row in rows] + [len(labels), 1])
    headers = [str(item).strip() for item in labels if str(item).strip()]
    if len(headers) < width and rows and len(rows[0]) == width:
        # The scraped table's own header row commonly has extra columns
        # that 03's column_labels never declares -- most often a leading
        # identifier column such as "Method" that every row already
        # carries and 03 doesn't need to name separately. Locate the
        # declared labels as a contiguous run inside the real header row
        # and borrow its text for the missing slots, instead of always
        # inventing "Value N" placeholders at the end: that silently
        # shifted every declared header one column out of alignment with
        # its data, and also broke the duplicate-header-row strip check
        # below (a real batch-writing run compiled a table with its own
        # "Method Swap Delete ..." header rendered as if it were a data
        # row, with the label of the shifted-out last column replaced by
        # a meaningless "Value N").
        raw_header = [str(item).strip() for item in rows[0]]
        folded_raw = [item.casefold() for item in raw_header]
        folded_labels = [item.casefold() for item in headers]
        for start in range(len(folded_raw) - len(folded_labels) + 1):
            if folded_raw[start : start + len(folded_labels)] == folded_labels:
                headers = raw_header[:start] + headers + raw_header[start + len(folded_labels) :]
                break
    if len(headers) < width:
        headers.extend(f"Value {index}" for index in range(len(headers) + 1, width + 1))
    headers = headers[:width]
    keys: list[str] = []
    for index, header in enumerate(headers, 1):
        # Preserve numeric condition signs in the machine key.  Plain slugging
        # collapsed both "Multiplier +1" and "Multiplier -1" to
        # ``multiplier_1``; duplicate disambiguation then produced
        # ``multiplier_1_2``, which a writing model reasonably interpreted as
        # the nonexistent value 1.2.  Encode signs before slugging while
        # retaining ordinary word hyphens such as "held-out".
        key_source = re.sub(
            r"(?<![A-Za-z0-9])[+＋](?=\s*\d)", " plus ", header
        )
        key_source = re.sub(
            r"(?<![A-Za-z0-9])[-−–](?=\s*\d)", " minus ", key_source
        )
        base = _safe_slug(key_source, f"value-{index}").replace("-", "_")
        key = base
        suffix = 2
        while key in keys:
            key = f"{base}_{suffix}"
            suffix += 1
        keys.append(key)
    if rows and [item.casefold() for item in rows[0][:width]] == [item.casefold() for item in headers]:
        rows = rows[1:]
    records = [
        {key: (row[index] if index < len(row) else "—") for index, key in enumerate(keys)}
        for row in rows
    ]
    return records, [
        {"key": key, "label": header} for key, header in zip(keys, headers)
    ]


def _artifact_definitions(
    contract: dict[str, Any], sections: list[dict[str, Any]],
    *, allow_empty_result_artifacts: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    section_ids = {item["id"] for item in sections}
    section_aliases = {
        str(alias): section["id"]
        for section in sections
        for alias in (section["id"], section.get("source_id"), section["title"])
        if alias
    }
    paragraph_locations = {
        paragraph["id"]: section["id"]
        for section in sections
        for paragraph in section["paragraphs"]
    }
    figures: dict[str, Any] = {}
    tables: dict[str, Any] = {}
    metrics: dict[str, Any] = {"artifacts": {}}
    raw_tables = contract.get("_result_tables", {})
    requirement_artifacts = {
        str(item.get("artifact_id"))
        for item in contract.get("result_requirements", [])
        if isinstance(item, dict) and item.get("artifact_id")
    }
    for raw in contract.get("paper_artifacts", []):
        if not isinstance(raw, dict):
            raise OnlineStudioError("03 paper_artifacts entry 必须是 object。")
        artifact_id = str(raw.get("id") or "").strip()
        contract_kind = str(raw.get("kind") or "").strip().lower()
        if not artifact_id or contract_kind not in {"figure", "table"}:
            raise OnlineStudioError("03 artifact 必须包含 ID，kind 必须是 figure 或 table。")
        section_id = section_aliases.get(str(raw.get("section_id") or "").strip(), "")
        if section_id not in section_ids:
            introduced = str(raw.get("introduced_after") or "").strip()
            section_id = paragraph_locations.get(introduced, section_id)
        if section_id not in section_ids:
            raise OnlineStudioError(f"03 artifact {artifact_id} 引用了未知 section。")
        shell = raw.get("shell") if isinstance(raw.get("shell"), dict) else {}
        source_asset = str(
            raw.get("source_asset") or shell.get("source_asset") or ""
        ).strip()
        caption = str(shell.get("caption") or raw.get("caption") or artifact_id).strip()
        title = str(raw.get("title") or caption or artifact_id).strip()
        # Expplan stores publication layout under the artifact shell.  Ignoring
        # ``shell.span`` silently turned declared double-column result tables
        # into tiny single-column tables, even though their ten columns were
        # only readable as ``table*``.
        span = str(
            raw.get("span")
            or raw.get("width")
            or shell.get("span")
            or shell.get("width")
            or "single-column"
        ).lower()
        width = "two-column" if any(token in span for token in ("two", "full", "double")) else "single-column"
        bindings = [
            paragraph["id"]
            for section in sections
            for paragraph in section["paragraphs"]
            if artifact_id in paragraph["artifacts"]
        ]
        if not bindings:
            introduced = str(raw.get("introduced_after") or "").strip()
            bindings = [introduced] if introduced in paragraph_locations else []
        if not bindings:
            raise OnlineStudioError(f"03 artifact {artifact_id} 没有 paragraph binding。")
        rows = raw_tables.get(artifact_id, []) if isinstance(raw_tables, dict) else []
        labels = [str(item) for item in shell.get("column_labels", [])]
        records, columns = _artifact_rows(rows, labels)
        placeholder_table = bool(
            allow_empty_result_artifacts and contract_kind == "table" and not records
        )
        if placeholder_table:
            if not columns:
                columns = [
                    {"key": "planned_item", "label": "Planned item"},
                    {"key": "value", "label": "Value"},
                ]
            records = [{column["key"]: "xx" for column in columns}]
        if (
            artifact_id in requirement_artifacts
            and not records
            and not allow_empty_result_artifacts
        ):
            raise OnlineStudioError(
                f"05 中的结果 artifact {artifact_id} 没有可读取的数据行；不会用占位值代替实验结果。"
            )
        if records or (allow_empty_result_artifacts and contract_kind == "table"):
            metrics["artifacts"][artifact_id] = {
                "rows": records,
                "source": (
                    "online-placeholder-no-results"
                    if placeholder_table else "reports/05_EXP_RESULT.html"
                ),
                "contract_verified": not placeholder_table,
                "placeholder": placeholder_table,
            }
        result_path = f"artifacts.{artifact_id}.rows"
        common = {
            "title": title,
            "label": str(raw.get("label") or ("fig:" if contract_kind == "figure" else "tab:") + artifact_id.lower()),
            "width": width,
            "source_sections": [section_id],
            "description": str(raw.get("description") or caption),
            "caption": caption,
            "result_keys": [result_path] if records else [],
            "related_paragraphs": {section_id: bindings},
            "dimensions": [str(item) for item in raw.get("dimensions", [])],
            "visible_dimensions": [
                str(item) for item in raw.get("visible_dimensions", [])
            ],
            "x_axis_label": str(
                raw.get("x_axis_label") or shell.get("x_axis_label") or ""
            ).strip(),
            "y_axis_label": str(
                raw.get("y_axis_label") or shell.get("y_axis_label") or ""
            ).strip(),
            "source_asset": source_asset,
            "online_placeholder": placeholder_table,
        }
        if contract_kind == "table":
            tables[artifact_id] = {
                **common,
                "kind": "table",
                "data_grid": {"type": "records", "path": result_path, "columns": columns},
                "prompt": {
                    "columns": " | ".join(item["label"] for item in columns),
                    "rows": "source",
                    "font_size": "small",
                    # "03" never actually supplies a per-column metric
                    # direction here (only caption/column_labels are read
                    # above), so there is no verified signal to bold a
                    # "best" value by. Default to "none" rather than
                    # guessing a direction that could bold the wrong column.
                    "best_values": "none",
                },
            }
            continue
        data_driven = bool(records) and (
            bool(raw.get("data_driven")) or artifact_id in requirement_artifacts
        )
        raw_panels = shell.get("panels")
        if raw_panels is None and isinstance(shell.get("plotting"), dict):
            raw_panels = shell["plotting"].get("panels")
        if isinstance(raw_panels, dict):
            panel_items = [(str(key), value) for key, value in raw_panels.items()]
        elif isinstance(raw_panels, list):
            panel_items = []
            for index, item in enumerate(raw_panels):
                if isinstance(item, dict):
                    panel_items.append((str(item.get("id") or chr(97 + index)), item))
                elif str(item).strip():
                    panel_items.append((str(item).strip(), {}))
        else:
            panel_items = []
        panels = [
            {
                "id": panel_id,
                "title": str(panel.get("title") or panel.get("name") or panel_id),
                "goal": str(panel.get("goal") or panel.get("description") or caption),
                "result_keys": [result_path] if data_driven else [],
            }
            for panel_id, panel in panel_items
        ]
        if data_driven and not panels:
            panels = [{"id": "a", "title": title, "goal": caption, "result_keys": [result_path]}]
        figure = {
            **common,
            "kind": "source" if source_asset else "data" if data_driven else "mechanism",
            "panels": panels,
            "depends_on_paragraphs": {section_id: bindings},
            "deliverable_stem": _safe_slug(artifact_id),
        }
        if data_driven and records and not source_asset:
            figure["data_grid"] = {
                "type": "records",
                "path": result_path,
                "columns": columns,
            }
        if not data_driven and not source_asset:
            figure["generation_requires_paragraphs"] = {section_id: bindings}
        figures[artifact_id] = figure
    return figures, tables, metrics


def _load_venue_templates() -> dict[str, dict[str, Any]]:
    """Load the bundled official venue LaTeX templates under venue_templates/.

    Each subdirectory is one template family (e.g. the ACL/EMNLP/NAACL/COLING
    family, which all share acl.sty) described by its own template.json plus
    the real .sty/.cls/.bst assets it ships. This is intentionally a small,
    explicit, verified registry rather than a generic fallback: an unmatched
    venue must fail the scaffold instead of silently compiling as a plain
    article, which is the defect this registry exists to prevent.
    """
    templates: dict[str, dict[str, Any]] = {}
    if not VENUE_TEMPLATES_DIR.is_dir():
        return templates
    for family_dir in sorted(VENUE_TEMPLATES_DIR.iterdir()):
        manifest_path = family_dir / "template.json"
        if not manifest_path.is_file():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["_dir"] = family_dir
        templates[str(manifest["family"])] = manifest
    return templates


VENUE_TEMPLATES = _load_venue_templates()


def _resolve_venue_template(venue: str) -> dict[str, Any] | None:
    normalized = re.sub(r"[^a-z0-9 ]+", " ", venue.lower())
    for manifest in VENUE_TEMPLATES.values():
        for alias in manifest.get("aliases", []):
            pattern = rf"(?<![a-z0-9]){re.escape(str(alias).lower())}(?![a-z0-9])"
            if re.search(pattern, normalized):
                return manifest
    return None


def _venue_family(venue: str) -> str:
    template = _resolve_venue_template(venue)
    if template is not None:
        return str(template.get("family") or "").lower()
    return re.sub(r"[^a-z0-9]+", " ", venue.lower()).strip()


def _write_workspace(
    root: Path,
    *,
    files: list[tuple[str, str]],
    archive: bytes,
    api_key: str = "",
    model: str = "",
) -> None:
    paper = root / "paper"
    sections_dir = paper / "sections"
    sources_dir = root / "sources"
    profile_dir = root / "researcher-profile"
    reports_dir = root / "reports"
    sections_dir.mkdir(parents=True)
    sources_dir.mkdir(parents=True)
    profile_dir.mkdir(parents=True)
    reports_dir.mkdir(parents=True)
    _extract_evidence_archive(archive, root)
    if not files:
        _validate_project_package(root)
        packaged_sources = {
            "PROFILE.html": root / "researcher-profile/PROFILE.html",
            "03_EXPERIMENT_PLAN.html": root / "reports/03_EXPERIMENT_PLAN.html",
            "05_EXP_RESULT.html": root / "reports/05_EXP_RESULT.html",
        }
        missing = [name for name, path in packaged_sources.items() if not path.is_file()]
        if missing:
            raise OnlineStudioError("研究项目 ZIP 缺少必需文件：" + "、".join(missing))
        files = [(name, path.read_text(encoding="utf-8")) for name, path in packaged_sources.items()]
    sources = _canonical_pipeline_sources(files)
    profile = sources["PROFILE.html"]
    if "writing style" not in profile.lower():
        raise OnlineStudioError("PROFILE.html 缺少完整的 Writing Style 部分，请先刷新 profileconstruct。")
    (profile_dir / "PROFILE.html").write_text(profile, encoding="utf-8")
    (reports_dir / "03_EXPERIMENT_PLAN.html").write_text(
        sources["03_EXPERIMENT_PLAN.html"], encoding="utf-8"
    )
    (reports_dir / "05_EXP_RESULT.html").write_text(
        sources["05_EXP_RESULT.html"], encoding="utf-8"
    )
    for name, source in sources.items():
        (sources_dir / name).write_text(source, encoding="utf-8")
    contract = _validated_upstream_contract(
        root, sources["03_EXPERIMENT_PLAN.html"], sources["05_EXP_RESULT.html"]
    )
    target = contract.get("target") if isinstance(contract.get("target"), dict) else {}
    venue = str(target.get("venue") or "").strip()
    venue_template = _resolve_venue_template(venue)
    if venue_template is None:
        raise OnlineStudioError(
            f"在线 Paper Studio 尚未内置目标会议“{venue}”的官方 LaTeX 模板，"
            "不能用通用 article 模板顶替。请在 "
            "research_avatar/online_studio/venue_templates/ 下添加该会议的官方 "
            ".sty/.cls 与 template.json 后重新打包上传。"
        )
    project_name, title = _project_identity(sources["03_EXPERIMENT_PLAN.html"], contract)
    if str(contract.get("schema_version")) != "1.2":
        raise OnlineStudioError(
            "项目中的 03 仍是旧结构合同；请用新版 expplan 选择一篇作者自有逻辑参考并重新批准。"
        )
    sections = _outline_sections(contract)
    figures, tables, metrics = _artifact_definitions(contract, sections)

    section_specs = []
    plan_sections: dict[str, list[dict[str, Any]]] = {}
    for index, section in enumerate(sections, 1):
        section_id = section["id"]
        section_title = section["title"]
        render = section["render"]
        filename = f"{section_id}.tex"
        result_keys = sorted(
            {
                key
                for definition in list(figures.values()) + list(tables.values())
                if section_id in definition["source_sections"]
                for key in definition.get("result_keys", [])
            }
        )
        section_specs.append(
            {
                "id": section_id,
                "title": section_title,
                "latex_title": "" if render == "abstract" else section_title,
                "start_label": "" if render == "abstract" else f"sec:{section_id.replace('_', '-')}",
                "file": filename,
                "render": render,
                "result_keys": result_keys,
            }
        )
        plan_sections[section_id] = []
        for paragraph in section["paragraphs"]:
            planned = {
                "id": paragraph["id"],
                "purpose": paragraph["purpose"],
                "rhetorical_role": paragraph["rhetorical_role"],
                "relation_to_previous": paragraph["relation_to_previous"],
                "relation_to_next": paragraph["relation_to_next"],
                "artifacts": paragraph["artifacts"],
                "reference_paragraph_ids": paragraph["reference_paragraph_ids"],
            }
            if paragraph["heading"]:
                planned["heading"] = paragraph["heading"]
                planned["heading_style"] = paragraph["heading_style"] or "subsection"
            plan_sections[section_id].append(planned)
        section_specs[-1]["paragraphs"] = plan_sections[section_id]
        placeholder = "% Awaiting paragraph-level drafting in Paper Studio.\n"
        if render != "abstract":
            placeholder = f"\\section{{{_latex_escape(section_title)}}}\n\n" + placeholder
        (sections_dir / filename).write_text(placeholder, encoding="utf-8")

    section_contexts = {
        section["id"]: section["reference_context"]
        for section in sections
        if isinstance(section.get("reference_context"), dict)
        and section["reference_context"]
    }
    packaged_contexts = root / "references/section-contexts.json"
    if not section_contexts and packaged_contexts.is_file():
        packaged_payload = json.loads(packaged_contexts.read_text(encoding="utf-8"))
        candidate_contexts = packaged_payload.get("sections")
        if isinstance(candidate_contexts, dict):
            section_contexts = candidate_contexts
    section_contexts = _require_complete_reference_contexts(
        section_contexts, [section["id"] for section in sections]
    )
    _write_reference_contexts(
        root,
        paper,
        section_contexts,
        reference_source="references/logic-reference.txt",
        reference_title=str(
            ((contract.get("references") or {}).get("researcher_owned_logic") or {}).get("title")
            or ""
        ),
    )

    main_inputs = []
    for section in sections:
        section_id = section["id"]
        render = section["render"]
        if render == "abstract":
            main_inputs.append(
                "\\begin{abstract}\n\\input{sections/abstract}\n\\end{abstract}"
            )
        else:
            main_inputs.append(f"\\input{{sections/{section_id}}}")
    for asset_name in venue_template.get("assets", []):
        asset_source = Path(venue_template["_dir"]) / asset_name
        if not asset_source.is_file():
            raise OnlineStudioError(
                f"内置模板“{venue_template['family']}”缺少必需资源文件：{asset_name}。"
            )
        shutil.copyfile(asset_source, paper / asset_name)
    bibliography_lines = (
        [r"\input{sections/bibliography}"]
        if not venue_template.get("needs_bibliographystyle", True)
        else [r"\bibliographystyle{plain}", r"\input{sections/bibliography}"]
    )
    abstract_inputs = [line for line in main_inputs if line.startswith("\\begin{abstract}")]
    body_inputs = [line for line in main_inputs if not line.startswith("\\begin{abstract}")]
    before_maketitle = abstract_inputs if venue_template.get("abstract_before_maketitle") else []
    # For conventional templates (including ACL), the abstract belongs directly
    # after \maketitle and before every numbered body section.  Appending it to
    # body_inputs put the abstract after the appendix while still producing a
    # technically valid PDF, so compilation alone could not catch the mistake.
    after_maketitle = ([] if before_maketitle else abstract_inputs) + body_inputs
    main_tex = "\n".join(
        [
            str(venue_template["documentclass"]),
            *[str(line) for line in venue_template.get("preamble", [])],
            r"\makeatletter\let\paperstudio@cite\cite\renewcommand{\cite}[1]{\if\relax\detokenize{#1}\relax\textbf{[CITATION NEEDED]}\else\paperstudio@cite{#1}\fi}\makeatother",
            f"\\title{{{_latex_escape(title)}}}",
            r"\author{Anonymous Author(s)}",
            r"\date{}",
            r"\begin{document}",
            *before_maketitle,
            r"\maketitle",
            *after_maketitle,
            *bibliography_lines,
            r"\end{document}",
            "",
        ]
    )
    (paper / "main.tex").write_text(main_tex, encoding="utf-8")
    survey_path = root / "reports/01_LIT_SURVEY.html"
    survey_source = (
        survey_path.read_text(encoding="utf-8", errors="replace")[:4_000_000]
        if survey_path.is_file()
        else ""
    )
    (paper / "references.bib").write_text(
        verified_survey_bibliography(survey_source), encoding="utf-8"
    )
    (sections_dir / "bibliography.tex").write_text(
        "% Paper Studio enables the bibliography after the first accepted citation.\n",
        encoding="utf-8",
    )
    metrics["online_sources"] = {
        "files": list(sources),
        "evidence_archive": True,
        "contract_approval_sha256": contract.get("approval_contract_sha256"),
    }
    (paper / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (paper / "working_abstract.txt").write_text(
        "Draft the abstract only from accepted manuscript evidence and uploaded sources.\n",
        encoding="utf-8",
    )
    (paper / ".outline-approved").write_text(
        "Inherited from approved reports/03_EXPERIMENT_PLAN.html.\n", encoding="utf-8"
    )
    references = (
        contract.get("references")
        if isinstance(contract.get("references"), dict)
        else {}
    )
    structural_reference = (
        references.get("researcher_owned_logic")
        if isinstance(references.get("researcher_owned_logic"), dict)
        else {}
    )
    config = {
        "schema_version": "1.0",
        "project": {
            "id": _safe_slug(project_name) + "-" + secrets.token_hex(4),
            "name": project_name,
            "initial_title": title,
            "venue": str(target.get("venue") or ""),
            "target": {
                key: value
                for key in (
                    "venue",
                    "track",
                    "cycle",
                    "submission_content_pages",
                    "deadline",
                )
                if (value := target.get(key)) not in (None, "")
            },
            "reference_paper": {
                key: value
                for key in ("title", "authors", "venue", "publication_key", "url")
                if (value := structural_reference.get(key))
            },
            "decision_source": "reports/03_EXPERIMENT_PLAN.html",
            "eyebrow": "ONLINE PAPER STUDIO",
            "studio_title": "Paper Studio",
        },
        "sections": section_specs,
        "batch_writing_order": [item["id"] for item in sections],
        "figure_order": [item["id"] for item in contract.get("paper_artifacts", []) if item.get("id") in figures],
        "figures": figures,
        "table_order": [item["id"] for item in contract.get("paper_artifacts", []) if item.get("id") in tables],
        "tables": tables,
        "paths": {
            "metrics": "paper/metrics.json",
            "main": "paper/main.tex",
        },
    }
    (paper / "paper_studio.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _decode_results_records(
    raw_results: Any,
) -> tuple[str, list[dict[str, str]], list[dict[str, Any]]]:
    """Validate the lightweight path's structured-results payload.

    Returns (caption, columns, rows) where columns is
    [{"key", "label"}, ...] and rows is a list of flat dicts keyed by
    column key -- exactly the records-type data_grid shape
    generate_table_latex/table_grid and render_data_figure_deterministic
    already consume, so no new rendering logic is needed for this path.
    """
    if raw_results is None:
        return "", [], []
    if not isinstance(raw_results, dict):
        raise OnlineStudioError("实验结果数据格式无效。")
    caption = str(raw_results.get("caption") or "").strip()
    if not caption or len(caption) > 400:
        raise OnlineStudioError("实验结果数据必须包含 1-400 字符的 caption。")
    columns = raw_results.get("columns")
    if not isinstance(columns, list) or not 2 <= len(columns) <= 8:
        raise OnlineStudioError("实验结果数据必须包含 2-8 列（第一列为标识列）。")
    normalized_columns: list[dict[str, str]] = []
    seen_keys: set[str] = set()
    for item in columns:
        if not isinstance(item, dict):
            raise OnlineStudioError("实验结果列定义格式无效。")
        key = str(item.get("key") or "").strip()
        label = str(item.get("label") or "").strip()
        if not key or not label or key in seen_keys:
            raise OnlineStudioError("实验结果列必须有唯一且非空的 key 与 label。")
        seen_keys.add(key)
        normalized_columns.append({"key": key, "label": label})
    rows = raw_results.get("rows")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 200:
        raise OnlineStudioError("实验结果数据必须包含 1-200 行。")
    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise OnlineStudioError("实验结果行格式无效。")
        normalized_rows.append(
            {column["key"]: row.get(column["key"]) for column in normalized_columns}
        )
    return caption, normalized_columns, normalized_rows


def _infer_results_records(
    filename: str, payload: Any
) -> tuple[str, list[dict[str, str]], list[dict[str, Any]], str]:
    """Turn a conventional nested result mapping into a provenance-bound grid.

    Path 02 accepts researchers' existing JSON rather than requiring an
    application-specific upload schema.  We only infer a grid when a mapping
    contains at least two named conditions that share at least two finite,
    scalar numeric metrics.  This deliberately excludes isolated metadata,
    per-seed blobs, confidence-interval arrays, and booleans: those shapes do
    not define a defensible comparison figure without scientific judgement.
    """

    if not isinstance(payload, dict):
        return "", [], [], ""

    candidates: list[tuple[tuple[int, int, int, str], str, list[str], list[dict[str, Any]]]] = []

    def visit(value: Any, path: tuple[str, ...]) -> None:
        if not isinstance(value, dict):
            return
        named_rows = [(str(key), child) for key, child in value.items() if isinstance(child, dict)]
        if 2 <= len(named_rows) <= 200:
            common: set[str] | None = None
            for _row_name, child in named_rows:
                numeric_keys = {
                    str(key)
                    for key, item in child.items()
                    if not isinstance(item, bool)
                    and isinstance(item, (int, float))
                    and math.isfinite(float(item))
                }
                common = numeric_keys if common is None else common & numeric_keys
            available_keys = list(common or ())
            # A single-column conference table/figure cannot communicate
            # seven or eight undifferentiated measures. Prefer compact
            # headline/summary metrics while remaining schema-agnostic, then
            # fill from the remaining shared scalar fields deterministically.
            def metric_rank(key: str) -> tuple[int, str]:
                normalized = key.casefold()
                priority = 0
                if normalized in {"clean", "clean_accuracy", "accuracy"}:
                    priority += 40
                if any(token in normalized for token in ("mean", "average", "avg")):
                    priority += 30
                if any(token in normalized for token in ("worst", "minimum", "min")):
                    priority += 20
                if any(token in normalized for token in ("primary", "score", "f1")):
                    priority += 10
                return (-priority, normalized)

            metric_keys = sorted(available_keys, key=metric_rank)[:4]
            if len(metric_keys) >= 2:
                rows = [
                    {"condition": row_name, **{key: child[key] for key in metric_keys}}
                    for row_name, child in named_rows
                ]
                semantic_bonus = 1000 if path and path[-1].casefold() in {
                    "aggregate", "aggregates", "summary", "results", "metrics"
                } else 0
                score = (
                    semantic_bonus + len(rows) * len(metric_keys),
                    len(metric_keys),
                    -len(path),
                    "/".join(path),
                )
                candidates.append((score, "/".join(path), metric_keys, rows))
        for key, child in value.items():
            if isinstance(child, dict) and len(path) < 6:
                visit(child, (*path, str(key)))

    visit(payload, ())
    if not candidates:
        return "", [], [], ""
    _score, source_path, metric_keys, rows = max(candidates, key=lambda item: item[0])
    source_label = source_path or "root"
    columns = [{"key": "condition", "label": "Condition"}] + [
        {"key": key, "label": key.replace("_", " ").strip().title()}
        for key in metric_keys
    ]
    metric_labels = [column["label"] for column in columns[1:]]
    if len(metric_labels) == 1:
        metric_phrase = metric_labels[0]
    elif len(metric_labels) == 2:
        metric_phrase = " and ".join(metric_labels)
    else:
        metric_phrase = ", ".join(metric_labels[:-1]) + f", and {metric_labels[-1]}"
    qualifiers: list[str] = []
    config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    for key, value in config.items():
        normalized = str(key).casefold()
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        if normalized in {"intent_count", "class_count", "label_count"}:
            qualifiers.append(f"{value:g}-class scope")
        elif "severity" in normalized:
            qualifiers.append(f"severity {value:g}")
        elif "budget" in normalized and "fraction" in normalized:
            qualifiers.append(f"{value * 100:g}% budget")
        if len(qualifiers) == 3:
            break
    qualifier = f" ({'; '.join(qualifiers)})" if qualifiers else ""
    caption = f"{metric_phrase} across experimental conditions{qualifier}."
    return caption, columns, rows, source_path


def _result_prompt_summary(payload: Any) -> Any:
    """Retain result-bearing JSON while bounding raw/run-level collections."""
    def omitted_collection(value: Any) -> dict[str, Any]:
        records: list[dict[str, Any]] = []

        def collect(node: Any) -> None:
            if isinstance(node, dict):
                records.append(node)
                for child in node.values():
                    collect(child)
            elif isinstance(node, list):
                for child in node:
                    collect(child)

        collect(value)
        zero_audits: dict[str, dict[str, int]] = {}
        for record in records:
            for key, item in record.items():
                normalized = str(key).casefold().replace("-", "_")
                if not any(token in normalized for token in ("edit", "mutation", "perturb", "change")):
                    continue
                if isinstance(item, bool) or not isinstance(item, (int, float)):
                    continue
                audit = zero_audits.setdefault(str(key), {"observed": 0, "zero": 0})
                audit["observed"] += 1
                audit["zero"] += int(float(item) == 0.0)
        result: dict[str, Any] = {
            "_omitted_from_writing_context": True,
            "count": len(value) if isinstance(value, (dict, list)) else None,
        }
        if zero_audits:
            result["zero_value_audit"] = zero_audits
        return result

    if isinstance(payload, dict):
        summary: dict[str, Any] = {}
        for key, value in payload.items():
            normalized = str(key).casefold().replace("-", "_")
            if normalized in {
                "per_seed", "selected_examples", "selected_examples_audit",
                "records", "raw_records", "traces",
            }:
                summary[str(key)] = omitted_collection(value)
            else:
                summary[str(key)] = _result_prompt_summary(value)
        return summary
    if isinstance(payload, list):
        if len(payload) > 20 and any(isinstance(item, (dict, list)) for item in payload):
            return {"_omitted_from_writing_context": True, "count": len(payload)}
        return [_result_prompt_summary(item) for item in payload]
    if isinstance(payload, str) and len(payload) > 500:
        return payload[:500] + "…"
    return payload


def _publication_year(item: dict[str, Any]) -> int:
    match = re.search(r"\d{4}", str(item.get("year") or item.get("venue") or ""))
    return int(match.group(0)) if match else 0


def _topic_tokens(value: str) -> set[str]:
    stop = {
        "a", "an", "and", "are", "as", "at", "by", "for", "from", "in",
        "is", "of", "on", "or", "our", "the", "this", "to", "via", "with",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) > 2 and token not in stop
    }


def _rank_author_publications(
    publications: list[dict[str, Any]], *, venue: str, project_text: str
) -> list[dict[str, Any]]:
    """Rank only papers present in the uploaded author's Scholar list.

    This ranking only decides which 3--4 full texts to acquire. An LLM later
    reads all of them and selects exactly one logic reference; this heuristic
    must never make that semantic decision.
    """
    target_family = _venue_family(venue)
    project_tokens = _topic_tokens(project_text)

    def score(item: dict[str, Any]) -> tuple[int, int, int, int, str]:
        item_venue = str(item.get("venue") or "")
        venue_match = int(_venue_family(item_venue) == target_family)
        overlap = len(_topic_tokens(str(item.get("title") or "")) & project_tokens)
        return (
            venue_match,
            overlap,
            min(int(item.get("cited_by") or 0), 10_000),
            _publication_year(item),
            str(item.get("title") or ""),
        )

    return sorted(
        (dict(item) for item in publications if isinstance(item, dict) and item.get("title")),
        key=score,
        reverse=True,
    )


def _acquire_author_fulltexts(
    root: Path, publications: list[dict[str, Any]], *, venue: str, project_text: str
) -> list[dict[str, Any]]:
    """Acquire 3--4 readable full texts from ranked author-owned papers."""
    from research_avatar.tools.fetch_fulltext import process
    from research_avatar.tools.profile_enrich import _bibtex, _make_keys

    ranked = _rank_author_publications(publications, venue=venue, project_text=project_text)
    _make_keys(ranked)
    fulltext_dir = root / "researcher-profile" / "fulltext"
    selected: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    # Try enough candidates to survive closed-access papers, but stop as soon
    # as the requested four author-owned full texts are available.
    for paper in ranked[:12]:
        venue_text = str(paper.get("venue") or "")
        arxiv = re.search(r"arXiv\s*:\s*([0-9]+\.[0-9]+)", venue_text, re.I)
        if arxiv and not paper.get("doi"):
            paper["doi"] = f"10.48550/arXiv.{arxiv.group(1)}"
        record = process(paper, fulltext_dir, use_s2=True, delay=0)
        records.append(record)
        if record.get("status") != "done":
            continue
        paper["bibtex"] = _bibtex(paper, str(paper["bibtex_key"]))
        paper["fulltext_txt"] = f"researcher-profile/fulltext/txt/{paper['bibtex_key']}.txt"
        paper["fulltext_pdf"] = f"researcher-profile/fulltext/pdf/{paper['bibtex_key']}.pdf"
        paper["fulltext_provenance"] = {
            "source": record.get("pdf_source"),
            "url": record.get("pdf_url"),
            "characters": record.get("txt_chars"),
        }
        selected.append(paper)
        if len(selected) == 4:
            break
    fulltext_dir.mkdir(parents=True, exist_ok=True)
    (fulltext_dir / "index.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if len(selected) < 3:
        raise OnlineStudioError(
            "无法从该作者的 Scholar paper list 中取得至少 3 篇可读全文；"
            "当前只取得 " + str(len(selected)) + " 篇。请确认列表中的论文有公开 PDF 后重试。"
        )
    return selected


def _summarize_author_writing_style(
    root: Path, papers: list[dict[str, Any]], *, api_key: str, model: str,
    project_text: str, venue: str,
) -> dict[str, Any]:
    """Read owned papers, select one logic reference, and summarize writing traits."""
    if not api_key:
        raise OnlineStudioError("缺少线上写作模型凭证，不能阅读代表作并归纳写作特点。")
    full_papers: list[str] = []
    for index, paper in enumerate(papers, 1):
        path = root / str(paper["fulltext_txt"])
        text = path.read_text(encoding="utf-8", errors="replace")
        full_papers.append(
            f"\n===== AUTHOR PAPER {index}: {paper['title']} =====\n{text}"
        )
    prompt = f"""You are analyzing 3--4 full papers written by one research author.
Return one JSON object with exactly these keys:
{{"selected_reference_index": 1, "selection_reason": "...", "writing_style": "..."}}

Select exactly ONE supplied author-owned paper as the target project's logic reference.
The primary criterion is argumentative-logic similarity: contribution type, section
progression, experiment organization, paragraph-to-paragraph reasoning, and figure/table
rhythm. Topic-word overlap alone is insufficient. Venue compatibility is a constraint or
tie-breaker, not the primary score. The index is 1-based.

Then give a concise evidence-bounded writing guide based on all supplied papers. Cover
only observed textual characteristics: abstract argument arc; introduction paragraph
roles; related-work organization; method exposition and notation; result-paragraph
pattern; claim calibration and hedging; paragraph/sentence cadence; caption habits.
State variation when present. Do not infer personality or copy distinctive phrases.

TARGET VENUE: {venue}
TARGET PROJECT:
{project_text}

FULL PAPERS:
""" + "\n".join(full_papers)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Analyze only the supplied full text; do not invent traits."},
            {"role": "user", "content": prompt},
        ],
        # This is an extraction/synthesis transaction over already supplied
        # author papers.  Hosted DeepSeek models otherwise default to a long
        # hidden reasoning pass, which can exhaust the gateway timeout before
        # returning the short visible style guide.
        "thinking": {"type": "disabled"},
        "temperature": 0.1,
        "max_tokens": 2500,
        "response_format": {"type": "json_object"},
    }
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    request = urllib.request.Request(
        base_url + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise OnlineStudioError(f"阅读代表作时模型 API 返回 HTTP {exc.code}：{detail[:500]}") from exc
    except urllib.error.URLError as exc:
        raise OnlineStudioError(f"阅读代表作时模型 API 连接失败：{exc.reason}") from exc
    choices = body.get("choices") or []
    content = str((choices[0].get("message") or {}).get("content") or "").strip() if choices else ""
    try:
        decision = json.loads(content)
    except json.JSONDecodeError as exc:
        raise OnlineStudioError("模型没有返回有效的作者论文选择 JSON，请重试。") from exc
    selected_index = decision.get("selected_reference_index")
    style = str(decision.get("writing_style") or "").strip()
    reason = str(decision.get("selection_reason") or "").strip()
    if not isinstance(selected_index, int) or not 1 <= selected_index <= len(papers):
        raise OnlineStudioError("模型选择的作者参考论文编号无效，请重试。")
    if len(style) < 200 or len(reason) < 20:
        raise OnlineStudioError("模型没有返回可审计的参考选择理由与写作特点，请重试。")
    normalized = {
        "id": body.get("id"),
        "model": body.get("model") or model,
        "usage": body.get("usage") or {},
        "output": [{"type": "message", "content": [{"type": "output_text", "text": content}]}],
    }
    append_usage(
        root / "paper/.paper_studio/api_usage.jsonl",
        usage_record(normalized, provider="deepseek", requested_model=model, operation="author_style_analysis"),
    )
    return {
        "reference": papers[selected_index - 1],
        "selection_reason": reason,
        "writing_style": style,
    }


def _analyze_target_project_online(
    root: Path,
    project_text: str,
    *,
    venue: str,
    api_key: str,
    model: str,
) -> dict[str, Any]:
    """Classify target-paper needs from the target brief alone."""
    if not api_key:
        raise OnlineStudioError("缺少线上写作模型凭证，不能分析目标项目。")
    requested_model = os.environ.get("DEEPSEEK_ALIGNMENT_MODEL", model).strip() or model
    prompt = f"""Read only the TARGET PROJECT BRIEF below. Do not use any reference
paper or outside source. Return one JSON object with exactly these fields:
{{
  "target_title": "6--18 word English paper title",
  "research_question": "one concise sentence",
  "contribution_type": "evaluation_study | model_architecture | method_non_architecture | dataset | analysis | other",
  "proposes_model_architecture": false,
  "model_figure_rationale": "one concise sentence"
}}

Set proposes_model_architecture=true only when the target work itself introduces
or modifies a model architecture or learned model component whose information
flow should be diagrammed. Evaluating, prompting, perturbing, comparing, or
calling an existing language model is not a proposed model architecture.
The title, research question, and classification must describe the target brief,
not a possible reference paper. Target venue: {venue}.

<target_project_brief>
{project_text}
</target_project_brief>
"""
    payload = {
        "model": requested_model,
        "messages": [
            {
                "role": "system",
                "content": "Analyze only the supplied target brief and return only JSON.",
            },
            {"role": "user", "content": prompt},
        ],
        "thinking": {"type": "disabled"},
        "temperature": 0.0,
        "max_tokens": 1200,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise OnlineStudioError(
            f"分析目标项目时模型 API 返回 HTTP {exc.code}：{detail[:500]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise OnlineStudioError(f"分析目标项目时模型 API 连接失败：{exc.reason}") from exc
    choices = body.get("choices") or []
    content = (
        str((choices[0].get("message") or {}).get("content") or "").strip()
        if choices else ""
    )
    try:
        analysis = json.loads(content)
    except json.JSONDecodeError as exc:
        raise OnlineStudioError("目标项目分析没有返回有效 JSON，请重试。") from exc
    allowed_types = {
        "evaluation_study", "model_architecture", "method_non_architecture",
        "dataset", "analysis", "other",
    }
    if not isinstance(analysis, dict):
        raise OnlineStudioError("目标项目分析必须是 JSON object。")
    if analysis.get("contribution_type") not in allowed_types:
        raise OnlineStudioError("目标项目分析返回了未知的 contribution_type。")
    if not isinstance(analysis.get("proposes_model_architecture"), bool):
        raise OnlineStudioError("目标项目分析缺少模型架构布尔判断。")
    for field in ("target_title", "research_question", "model_figure_rationale"):
        if not str(analysis.get(field) or "").strip():
            raise OnlineStudioError(f"目标项目分析缺少 {field}。")
    normalized = {
        "id": body.get("id"),
        "model": body.get("model") or requested_model,
        "usage": body.get("usage") or {},
        "output": [
            {"type": "message", "content": [{"type": "output_text", "text": content}]}
        ],
    }
    append_usage(
        root / "paper/.paper_studio/api_usage.jsonl",
        usage_record(
            normalized,
            provider="deepseek",
            requested_model=requested_model,
            operation="target_project_analysis",
        ),
    )
    return {
        "target_title": str(analysis["target_title"]).strip(),
        "research_question": str(analysis["research_question"]).strip(),
        "contribution_type": str(analysis["contribution_type"]),
        "proposes_model_architecture": analysis["proposes_model_architecture"],
        "model_figure_rationale": str(analysis["model_figure_rationale"]).strip(),
    }


def _design_lightweight_structure_online(
    root: Path,
    contract: dict[str, Any],
    reference_source: str,
    reference: dict[str, Any],
    *,
    api_key: str,
    model: str,
) -> dict[str, Any]:
    """One hosted call reads the full owned paper and designs the target outline."""
    if not api_key:
        raise OnlineStudioError("缺少线上写作模型凭证，不能设计论文结构。")
    requested_model = os.environ.get("DEEPSEEK_ALIGNMENT_MODEL", model).strip() or model
    prompt = structure_prompt(
        contract,
        reference_source,
        reference=reference,
        paragraph_mapping=True,
        selected_reference_inventory=True,
    )
    prompt += (
        "\n\nWrite every generated JSON string value in English, including section "
        "titles, paragraph plans, reference-move summaries, and mapping rationales. "
        "Quoted reference excerpts must preserve the source paper verbatim."
    )
    payload = {
        "model": requested_model,
        "messages": [
            {"role": "system", "content": "Return only the requested complete JSON object."},
            {"role": "user", "content": prompt},
        ],
        "thinking": {"type": "disabled"},
        "temperature": 0.0,
        # A full reference-to-target paragraph map is larger than ordinary
        # prose.  The prompt enforces compact fields, while this ceiling leaves
        # enough room for the complete JSON instead of truncating it mid-string.
        "max_tokens": 16000,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=360) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise OnlineStudioError(f"设计论文结构时模型 API 返回 HTTP {exc.code}：{detail[:500]}") from exc
    except urllib.error.URLError as exc:
        raise OnlineStudioError(f"设计论文结构时模型 API 连接失败：{exc.reason}") from exc
    choices = body.get("choices") or []
    content = str((choices[0].get("message") or {}).get("content") or "").strip() if choices else ""
    try:
        result = parse_structure_response(content)
        normalize_reference_line_ranges(reference_source, result)
        normalize_structure_design(contract, result, paragraph_mapping=True)
        materialize_reference_contexts(reference_source, result)
    except PaperStructureError as exc:
        raise OnlineStudioError("写作结构服务返回了无法读取的数据，请重试。") from exc
    normalized = {
        "id": body.get("id"), "model": body.get("model") or requested_model,
        "usage": body.get("usage") or {},
        "output": [{"type": "message", "content": [{"type": "output_text", "text": content}]}],
    }
    append_usage(
        root / "paper/.paper_studio/api_usage.jsonl",
        usage_record(normalized, provider="deepseek", requested_model=requested_model, operation="paper_structure_design"),
    )
    return result


def _write_lightweight_researcher_profile(
    root: Path,
    scholar_html: str,
    *,
    venue: str,
    project_text: str,
    api_key: str,
    model: str,
    structural_reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build writing-style personalization and bind the user-uploaded reference."""
    from research_avatar.tools.scholar_profile import parse_html

    try:
        parsed = parse_html(scholar_html)
    except RuntimeError as exc:
        raise OnlineStudioError("上传的 Scholar HTML 中没有可识别的作者 paper list。") from exc

    profile = parsed.get("profile") if isinstance(parsed.get("profile"), dict) else {}
    publications = (
        parsed.get("publications")
        if isinstance(parsed.get("publications"), list)
        else []
    )
    name = str(profile.get("name") or "Researcher").strip()
    affiliation = str(profile.get("affiliation") or "").strip()
    selected = _acquire_author_fulltexts(
        root, publications, venue=venue, project_text=project_text
    )
    analysis = _summarize_author_writing_style(
        root, selected, api_key=api_key, model=model,
        project_text=project_text, venue=venue,
    )
    writing_style = analysis["writing_style"]
    main_reference = structural_reference or analysis["reference"]
    selection_reason = (
        "The researcher explicitly uploaded this paper as the structural reference."
        if structural_reference is not None
        else analysis["selection_reason"]
    )
    title_items = "".join(
        "<li>"
        + html_lib.escape(str(item.get("title") or "Untitled"))
        + (f" ({html_lib.escape(str(item.get('year')))})" if item.get("year") else "")
        + "</li>"
        for item in selected
    )
    profile_html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Online Writing Reference Profile</title></head><body>
<h1>Online Writing Reference Profile — {html_lib.escape(name)}</h1>
<section data-report-section="source-coverage"><h2>Source and Coverage</h2>
<p>The uploaded Scholar HTML contains {len(publications)} publication records. The unified onboarding flow selected and read {len(selected)} full papers from that same author's list for writing-style analysis.</p></section>
<section data-report-section="research-identity"><h2>Research Identity</h2>
<p><strong>Name:</strong> {html_lib.escape(name)}. <strong>Affiliation:</strong> {html_lib.escape(affiliation or 'Not available in the uploaded page')}.</p></section>
<section data-report-section="research-lineage"><h2>Research Lineage</h2>
<p>Representative author-owned papers were read for writing analysis. The structural logic reference is the separately uploaded paper: {html_lib.escape(str(main_reference.get('title') or 'Untitled'))}. Reason: {html_lib.escape(selection_reason)}</p><ol>{title_items}</ol></section>
<section data-report-section="writing-style"><h2>Writing Style</h2>
<p>{html_lib.escape(writing_style)}</p></section>
<section data-report-section="experiment-templates"><h2>Experiment Templates</h2><p>Not personalized in path 02.</p></section>
<section data-report-section="workflow-preferences"><h2>Workflow Preferences</h2><p>Not personalized in path 02.</p></section>
<section data-report-section="publication-records"><h2>Publication Records</h2><p>Structured Scholar metadata is stored in publications.json for project export and audit.</p></section>
</body></html>"""
    profile_dir = root / "researcher-profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "PROFILE.html").write_text(profile_html, encoding="utf-8")
    parsed["selected_writing_references"] = [
        {key: item.get(key) for key in ("title", "authors", "venue", "year", "url", "bibtex_key", "fulltext_txt", "fulltext_pdf", "fulltext_provenance")}
        for item in selected
    ]
    (profile_dir / "publications.json").write_text(
        json.dumps(parsed, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "mode": "author_fulltext_reference",
        "name": name,
        "affiliation": affiliation,
        "publication_count": len(publications),
        "writing_style_inferred": True,
        "representative_papers": parsed["selected_writing_references"],
        "reference_paper": main_reference,
        "reference_selection_reason": selection_reason,
    }


def _write_reference_only_profile(
    root: Path, structural_reference: dict[str, Any]
) -> dict[str, Any]:
    """Write the neutral profile used by the three-material online path."""
    profile_dir = root / "researcher-profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    title = str(structural_reference.get("title") or "Uploaded structural reference")
    profile_html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Online Writing Profile</title></head><body>
<h1>Online Writing Profile</h1>
<section data-report-section="source-coverage"><h2>Source and Coverage</h2><p>No author profile was requested for this online session.</p></section>
<section data-report-section="research-identity"><h2>Research Identity</h2><p>Not supplied.</p></section>
<section data-report-section="research-lineage"><h2>Research Lineage</h2><p>The uploaded structural reference is {html_lib.escape(title)}. It is used only for organization and argumentative flow.</p></section>
<section data-report-section="writing-style"><h2>Writing Style</h2><p>No author-specific style is inferred. Use clear, concise conference prose grounded in the uploaded project evidence.</p></section>
<section data-report-section="experiment-templates"><h2>Experiment Templates</h2><p>Not personalized.</p></section>
<section data-report-section="workflow-preferences"><h2>Workflow Preferences</h2><p>Not personalized.</p></section>
<section data-report-section="publication-records"><h2>Publication Records</h2><p>No Scholar publication list was uploaded.</p></section>
</body></html>"""
    (profile_dir / "PROFILE.html").write_text(profile_html, encoding="utf-8")
    (profile_dir / "publications.json").write_text(
        json.dumps({"publications": []}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "mode": "uploaded_reference_only",
        "name": "Researcher",
        "affiliation": "",
        "publication_count": 0,
        "writing_style_inferred": False,
        "representative_papers": [],
        "reference_paper": structural_reference,
        "reference_selection_reason": (
            "The researcher explicitly uploaded this paper as the structural reference."
        ),
    }


def _approved_contract_from_project_text(project_text: str) -> dict[str, Any] | None:
    """Return an embedded Experiment Plan contract when one exists.

    Lightweight onboarding still accepts an ordinary brief in every supported
    document format.  When that brief is the exported 03 HTML, however, its
    available outline and artifact obligations are stronger evidence than the
    generic seven-section fallback and must survive unchanged into the one-shot
    reference-informed structure design.
    """
    match = re.search(
        r"<experiment-plan-contract>\s*(.*?)\s*</experiment-plan-contract>",
        project_text,
        re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        return None
    try:
        contract = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise OnlineStudioError("项目说明中的 experiment-plan-contract 不是有效 JSON。") from exc
    if not isinstance(contract, dict):
        raise OnlineStudioError("项目说明中的 experiment-plan-contract 必须是 JSON object。")
    if str(contract.get("schema_version")) != "1.2":
        raise OnlineStudioError("项目说明中的实验计划必须使用 schema 1.2。")
    if not isinstance(contract.get("paper_outline"), list) or not contract["paper_outline"]:
        raise OnlineStudioError("项目说明中的实验计划缺少 paper_outline。")
    if not isinstance(contract.get("paper_artifacts"), list):
        raise OnlineStudioError("项目说明中的实验计划缺少 paper_artifacts。")
    # Reuse the full-package validators for section/paragraph and reference
    # shape, without requiring the 05 HTML that path 02 intentionally does not
    # ask the researcher to upload.
    _outline_sections(contract)
    references = contract.get("references")
    owned = references.get("researcher_owned_logic") if isinstance(references, dict) else None
    if not isinstance(owned, dict) or not str(owned.get("title") or "").strip():
        raise OnlineStudioError("项目说明中的实验计划缺少作者自有逻辑参考论文。")
    return contract


def _lightweight_paper_title(
    explicit_title: str,
    project_text: str,
    approved_contract: dict[str, Any] | None,
    project_brief_name: str,
) -> str:
    """Derive the paper title from the uploaded brief instead of asking twice."""
    candidates: list[str] = [str(explicit_title or "").strip()]
    # Exported Experiment Plans place the actual English manuscript title directly
    # below "Projected Title and Abstract". Prefer that field over the bilingual
    # selected-idea display name; otherwise the ASCII safety fallback keeps only the
    # short prefix before the Chinese colon (for example, just "Steering Commutator").
    projected_match = re.search(
        r"(?im)^\s*(?:\d+(?:\.\d+)?\s+)?Projected Title and Abstract\s*$"
        r"\s*^\s*([^\n]+?)\s*$",
        project_text,
    )
    if projected_match:
        candidates.append(projected_match.group(1).strip())
    if isinstance(approved_contract, dict):
        candidates.extend(
            [
                str(approved_contract.get("paper_title") or "").strip(),
                str(approved_contract.get("title") or "").strip(),
                str((approved_contract.get("selected_idea") or {}).get("title") or "").strip()
                if isinstance(approved_contract.get("selected_idea"), dict)
                else "",
            ]
        )
    for pattern in (
        r"(?im)^\s*(?:paper\s+title|manuscript\s+title|论文标题)\s*[:：]\s*(.+?)\s*$",
        r"(?m)^\s*#\s+(.+?)\s*$",
    ):
        match = re.search(pattern, project_text)
        if match:
            candidate = match.group(1).strip().strip("#")
            if candidate.casefold() not in {"project", "project brief", "项目说明", "研究项目"}:
                candidates.append(candidate)
    candidates.append(Path(project_brief_name).stem.replace("_", " ").replace("-", " ").strip())
    title = next((item for item in candidates if 1 <= len(item) <= 300), "Research Paper Draft")
    # ACL's pdfLaTeX template cannot typeset arbitrary CJK text.  Project
    # plans may use a bilingual display title such as ``English: Chinese``; keep
    # its English paper-title prefix instead of emitting an uncompilable
    # initial main.tex.  A wholly non-ASCII display name remains available as
    # project metadata, while the manuscript starts from a safe neutral title.
    normalized = unicodedata.normalize("NFKC", title).strip()
    if normalized.isascii():
        return normalized
    english_prefix = normalized.split(":", 1)[0].strip()
    if english_prefix.isascii() and re.search(r"[A-Za-z]", english_prefix):
        return english_prefix
    return "Research Paper Draft"


def _generated_structure_title(
    structure_design: dict[str, Any], fallback: str
) -> str:
    """Accept a safe English title generated in the structure-design call."""
    candidate = unicodedata.normalize(
        "NFKC", str(structure_design.get("target_paper_title") or "")
    ).strip().strip('"\'')
    candidate = re.sub(r"\s+", " ", candidate).rstrip(".")
    word_count = len(re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?", candidate))
    if (
        candidate.isascii()
        and 6 <= word_count <= 18
        and len(candidate) <= 180
        and re.search(r"[A-Za-z]", candidate)
        and not re.search(r"\b(?:xx|untitled|draft|placeholder)\b", candidate, re.I)
    ):
        return candidate
    return fallback


def _walk_named_values(value: Any, wanted: str) -> list[Any]:
    """Find values under an exact key without guessing document-specific paths."""
    matches: list[Any] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) == wanted:
                matches.append(child)
            matches.extend(_walk_named_values(child, wanted))
    elif isinstance(value, list):
        for child in value:
            matches.extend(_walk_named_values(child, wanted))
    return matches


def _chart_payload_records(
    payload: Any,
) -> tuple[list[str], list[list[Any]]] | None:
    """Convert a generic categories+series result payload into record rows."""
    if not isinstance(payload, dict):
        return None
    categories = payload.get("categories")
    series = payload.get("series")
    if (
        not isinstance(categories, list)
        or not categories
        or not isinstance(series, list)
        or not series
    ):
        return None
    headers = ["Setting"]
    columns: list[tuple[str, list[Any]]] = []
    for index, item in enumerate(series, 1):
        if not isinstance(item, dict):
            return None
        name = str(item.get("name") or f"Series {index}").strip()
        values = item.get("values")
        if not isinstance(values, list) or len(values) != len(categories):
            return None
        headers.append(name)
        columns.append((name, values))
        for suffix, label in (("ci_low", "CI low"), ("ci_high", "CI high")):
            interval = item.get(suffix)
            if interval is None:
                continue
            if not isinstance(interval, list) or len(interval) != len(categories):
                return None
            interval_name = f"{name} {label}"
            headers.append(interval_name)
            columns.append((interval_name, interval))
    rows = [
        [category, *[values[row_index] for _name, values in columns]]
        for row_index, category in enumerate(categories)
    ]
    return headers, rows


def _contract_result_tables(
    contract: dict[str, Any], result_documents: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, list[list[Any]]]]:
    """Bind approved artifacts to uploaded JSON using contract-owned IDs.

    This is intentionally schema-driven: table IDs, panel IDs, captions,
    row/column labels, and cell IDs all come from the uploaded approved plan.
    The result documents may organize those values differently, so matching is
    by those stable IDs rather than by filenames or this project's vocabulary.
    """
    enriched = json.loads(json.dumps(contract))
    tables: dict[str, list[list[Any]]] = {}
    values_maps = [
        candidate
        for document in result_documents
        for candidate in _walk_named_values(document, "values")
        if isinstance(candidate, dict)
    ]
    requirements = {
        str(item.get("artifact_id")): item
        for item in contract.get("result_requirements", [])
        if isinstance(item, dict) and item.get("artifact_id")
    }
    for artifact in enriched.get("paper_artifacts", []):
        if not isinstance(artifact, dict):
            continue
        artifact_id = str(artifact.get("id") or "").strip()
        shell = artifact.setdefault("shell", {})
        if not isinstance(shell, dict) or not artifact_id:
            continue
        kind = str(artifact.get("kind") or "").lower()
        raw_rows: list[list[Any]] | None = None
        if kind == "table":
            record_candidates: list[list[dict[str, Any]]] = []
            for document in result_documents:
                for candidate in _walk_named_values(document, artifact_id):
                    if isinstance(candidate, dict):
                        candidate = candidate.get("studio_rows", candidate.get("rows"))
                    if (
                        isinstance(candidate, list)
                        and candidate
                        and all(isinstance(row, dict) for row in candidate)
                    ):
                        record_candidates.append(candidate)
            if record_candidates:
                records = record_candidates[0]
                keys = list(records[0])
                headers = [str(key).replace("_", " ").strip().title() for key in keys]
                raw_rows = [headers] + [[row.get(key, "—") for key in keys] for row in records]
                shell["column_labels"] = headers
            else:
                requirement = requirements.get(artifact_id, {})
                cell_ids = [str(item) for item in requirement.get("cell_ids", [])]
                row_labels = [str(item) for item in shell.get("row_labels", [])]
                column_labels = [str(item) for item in shell.get("column_labels", [])]
                value_map = next(
                    (mapping for mapping in values_maps if cell_ids and all(key in mapping for key in cell_ids)),
                    None,
                )
                if value_map is not None and row_labels and column_labels and len(cell_ids) == len(row_labels) * len(column_labels):
                    raw_rows = [["Method", *column_labels]]
                    for row_index, row_label in enumerate(row_labels):
                        cells = []
                        for column_index in range(len(column_labels)):
                            cell_id = cell_ids[row_index * len(column_labels) + column_index]
                            cell = value_map[cell_id]
                            cells.append(cell.get("value") if isinstance(cell, dict) else cell)
                        raw_rows.append([row_label, *cells])
                    shell["column_labels"] = ["Method", *column_labels]
        elif kind == "figure":
            panel_values = shell.get("panels", [])
            panel_ids = [
                str(item.get("id") if isinstance(item, dict) else item)
                for item in (panel_values.values() if isinstance(panel_values, dict) else panel_values)
            ]
            for panel_id in panel_ids or ["a"]:
                candidates: list[Any] = []
                composite_key = f"{artifact_id}.{panel_id}"
                for document in result_documents:
                    candidates.extend(_walk_named_values(document, composite_key))
                    for artifact_payload in _walk_named_values(document, artifact_id):
                        if isinstance(artifact_payload, dict) and panel_id in artifact_payload:
                            candidates.append(artifact_payload[panel_id])
                converted = next(
                    (result for candidate in candidates if (result := _chart_payload_records(candidate)) is not None),
                    None,
                )
                if converted is not None:
                    headers, rows = converted
                    raw_rows = [headers, *rows]
                    shell["column_labels"] = headers
                    break
        if raw_rows:
            tables[artifact_id] = raw_rows
    enriched["_result_tables"] = tables
    return enriched, tables


def _write_lightweight_workspace(
    root: Path,
    *,
    venue: str,
    project_name: str,
    title: str,
    scholar_files: list[tuple[str, str]],
    project_brief_files: list[tuple[str, str]],
    results_files: list[tuple[str, str]],
    api_key: str,
    model: str,
    reference_paper_files: list[tuple[str, str]] | None = None,
    progress: Callable[[str, str, int], None] | None = None,
) -> None:
    """Scaffold a text-first Paper Studio project from raw materials only.

    For researchers who never ran the full Research Avatar pipeline (no
    approved 03/05 contract or RESULTS_LEDGER). It maps a compact paper plan to
    the one structural reference explicitly uploaded by the researcher. The
    project brief and result documents remain the scientific evidence;
    reference prose is structural context, not a source of project claims.
    If a result JSON follows the structured
    records schema, one
    deterministic table and one deterministic data figure (both online-
    safe -- no Agent, no pdfcrop/node/latexmk) are auto-bound to the
    Experiments section.
    """
    paper = root / "paper"
    sections_dir = paper / "sections"
    sections_dir.mkdir(parents=True)

    def report(stage: str, status: str, percent: int) -> None:
        if progress is not None:
            progress(stage, status, percent)

    report("materials", "正在解析当前工作说明和结构参考论文…", 10)

    venue_template = _resolve_venue_template(venue)
    if venue_template is None:
        raise OnlineStudioError(
            f"在线 Paper Studio 尚未内置目标会议“{venue}”的官方 LaTeX 模板，"
            "不能用通用 article 模板顶替。请在 "
            "research_avatar/online_studio/venue_templates/ 下添加该会议的官方 "
            ".sty/.cls 与 template.json 后重试。"
        )

    if len(project_brief_files) != 1:
        raise OnlineStudioError("请上传一个当前工作说明文档。")
    if not reference_paper_files or len(reference_paper_files) != 1:
        raise OnlineStudioError("请上传一篇完整的结构参考论文。")
    project_text = _plain_source_text(project_brief_files, "PROJECT BRIEF")
    approved_contract = _approved_contract_from_project_text(project_text)
    title_was_explicit = bool(title.strip())
    title = _lightweight_paper_title(
        title,
        project_text,
        approved_contract,
        project_brief_files[0][0],
    )
    report("target_analysis", "正在分析目标项目的研究类型与图表需求…", 18)
    target_analysis = _analyze_target_project_online(
        root,
        project_text,
        venue=venue,
        api_key=api_key,
        model=model,
    )
    if not title_was_explicit:
        title = _generated_structure_title(
            {"target_paper_title": target_analysis["target_title"]},
            title,
        )
    project_name = project_name.strip() or title
    main_reference: dict[str, Any] | None = None
    reference_name = ""
    reference_source = ""
    reference_path: Path | None = None
    if reference_paper_files:
        reference_name, reference_source = reference_paper_files[0]
        # The LLM-restored transcript starts with the scholarly title as one
        # semantic block. PDF line wrapping can still split that title across
        # two or more physical lines, so use the complete first block rather
        # than truncating the displayed reference title at its first line.
        source_lines = reference_source.strip().splitlines()
        first_nonempty = next((line.strip() for line in source_lines if line.strip()), "")
        if first_nonempty.startswith("#"):
            # A Markdown heading is already an explicit title boundary. Do not
            # concatenate the following author line or body paragraph.
            reference_title = re.sub(r"^#+\s*", "", first_nonempty).strip()
        else:
            first_block = re.split(r"\n\s*\n", reference_source.strip(), maxsplit=1)[0]
            reference_title = " ".join(
                re.sub(r"^[#\s]+", "", line).strip()
                for line in first_block.splitlines()
                if re.sub(r"^[#\s]+", "", line).strip()
            )
        reference_title = reference_title[:300] or Path(reference_name).stem
        reference_dir = root / "uploaded-evidence" / "reference"
        reference_dir.mkdir(parents=True, exist_ok=True)
        reference_path = reference_dir / "structural-reference.txt"
        reference_path.write_text(reference_source.rstrip() + "\n", encoding="utf-8")
        main_reference = {
            "title": reference_title or Path(reference_name).stem,
            "authors": "Uploaded structural reference",
            "venue": "",
            "year": "",
            "url": "",
            "bibtex_key": "uploadedstructuralreference",
            "bibtex": (
                "@misc{uploadedstructuralreference,\n"
                f"  title = {{{_latex_escape(reference_title or Path(reference_name).stem)}}},\n"
                "  note = {Researcher-uploaded structural reference}\n"
                "}"
            ),
            "fulltext_txt": reference_path.relative_to(root).as_posix(),
            "fulltext_provenance": "researcher_upload",
            "upload_name": reference_name,
        }
    if scholar_files:
        lightweight_profile = _write_lightweight_researcher_profile(
            root,
            scholar_files[0][1],
            venue=venue,
            project_text=project_text,
            api_key=api_key,
            model=model,
            structural_reference=main_reference,
        )
    else:
        lightweight_profile = _write_reference_only_profile(root, main_reference)
    source_blocks = [project_text]
    if scholar_files:
        source_blocks.insert(0, _source_text(scholar_files))
    if results_files:
        source_blocks.append(_plain_source_text(results_files, "EXPERIMENT EVIDENCE"))
    report("writing_boundary", "正在建立实验部分仅规划的写作边界…", 24)
    reference = "\n\n".join(source_blocks)
    if len(reference) > MAX_SOURCE_TEXT_CHARS:
        reference = (
            reference[:MAX_SOURCE_TEXT_CHARS].rstrip()
            + "\n\n[ONLINE STUDIO NOTE: additional uploaded text was truncated at the configured context limit.]"
        )
    main_reference = lightweight_profile["reference_paper"]
    if reference_path is None:
        reference_path = root / str(main_reference["fulltext_txt"])
        reference_source = reference_path.read_text(encoding="utf-8", errors="replace")
        reference_name = reference_path.name
    if len(reference_source) > MAX_STRUCTURE_REFERENCE_CHARS:
        marker = (
            "\n\n[ONLINE STUDIO: middle of structural reference omitted to bound "
            "the one-shot API prompt; front matter/body opening and conclusion are retained.]\n\n"
        )
        usable = MAX_STRUCTURE_REFERENCE_CHARS - len(marker)
        head = usable * 3 // 4
        reference_source = (
            reference_source[:head]
            + marker
            + reference_source[-(usable - head):]
        )
    (paper / "uploaded_sources.txt").write_text(
        reference + "\n", encoding="utf-8"
    )
    if approved_contract is not None:
        reports_dir = root / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "03_EXPERIMENT_PLAN.html").write_text(
            "<!doctype html><html><body>"
            '<script type="application/json" id="experiment-plan-contract">'
            + json.dumps(approved_contract, ensure_ascii=False)
            + "</script></body></html>\n",
            encoding="utf-8",
        )

    # Keep every uploaded result document in the exported project.  When an
    # approved 03 names an exact result path, also restore the matching upload
    # at that path so provenance/conformance checks can follow the contract
    # instead of seeing only the derived metrics.json summary.
    evidence_results_dir = root / "uploaded-evidence" / "results"
    evidence_results_dir.mkdir(parents=True, exist_ok=True)
    contract_result_paths: dict[str, set[Path]] = {}
    if approved_contract is not None:
        for requirement in approved_contract.get("result_requirements", []):
            if not isinstance(requirement, dict):
                continue
            for locator in requirement.get("any_of", []):
                raw_path = str(locator).split(":", 1)[0].strip()
                candidate = Path(raw_path)
                if (
                    not raw_path
                    or candidate.is_absolute()
                    or ".." in candidate.parts
                    or candidate.name != Path(candidate.name).name
                ):
                    continue
                contract_result_paths.setdefault(candidate.name, set()).add(candidate)
    for index, (name, text) in enumerate(results_files, start=1):
        basename = Path(name).name or f"result-{index}.txt"
        destination = evidence_results_dir / basename
        if destination.exists():
            destination = evidence_results_dir / f"{index}-{basename}"
        destination.write_text(text, encoding="utf-8")
        for relative_path in contract_result_paths.get(basename, set()):
            restored = root / relative_path
            restored.parent.mkdir(parents=True, exist_ok=True)
            restored.write_text(text, encoding="utf-8")

    structured_results = None
    inferred_results: tuple[str, list[dict[str, str]], list[dict[str, Any]], str] | None = None
    result_source_file = ""
    result_prompt_summaries: dict[str, Any] = {}
    result_documents: list[dict[str, Any]] = []
    for name, text in results_files:
        if Path(name).suffix.lower() != ".json":
            continue
        try:
            candidate = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            result_documents.append(candidate)
        result_prompt_summaries[name] = _result_prompt_summary(candidate)
        if (
            structured_results is None
            and isinstance(candidate, dict)
            and {"caption", "columns", "rows"}.issubset(candidate)
        ):
            structured_results = candidate
            result_source_file = name
        inferred = _infer_results_records(name, candidate)
        if inferred[2] and inferred_results is None:
            inferred_results = inferred
            result_source_file = name
    if structured_results is not None:
        caption, columns, rows = _decode_results_records(structured_results)
        result_source_path = "root"
        result_extraction = "declared-records-schema"
    elif inferred_results is not None:
        caption, columns, rows, result_source_path = inferred_results
        result_extraction = "shared-numeric-mapping-v1"
    else:
        caption, columns, rows = "", [], []
        result_source_path = ""
        result_extraction = "none"
    has_results = bool(rows)

    sections = _validated_sections(None)
    figures: dict[str, Any] = {}
    tables: dict[str, Any] = {}
    figure_order: list[str] = []
    table_order: list[str] = []
    has_model_improvement = target_analysis["proposes_model_architecture"]
    # A motivation figure is part of the default Introduction contract even
    # for a text-first hosted session.  The hosted UI preserves its float,
    # caption and prose binding; the exported project carries the actual
    # drawing task to the local terminal workflow.
    motivation_figure_id = "F1"
    model_figure_id = "F2" if has_model_improvement else ""
    data_figure_id = "F3" if has_model_improvement else "F2"
    figures[motivation_figure_id] = {
        "title": "Problem motivation and evaluation question",
        "label": "fig:motivation",
        "kind": "mechanism",
        "phase": 1,
        "width": "single-column",
        "source_sections": ["introduction"],
        "description": (
            "A concrete visual motivation that shows the real problem setting, "
            "the unresolved failure or comparison, and the paper's evaluation question."
        ),
        "caption": (
            "Motivation and evaluation question of the study; the hosted Studio "
            "reserves this location for artwork completed after project export."
        ),
        "result_keys": [],
        "depends_on_paragraphs": {"introduction": ["I1"]},
        "generation_requires_paragraphs": {"introduction": ["I1"]},
        "panels": [],
        "deliverable_stem": "motivation",
    }
    figure_order.append(motivation_figure_id)
    if has_model_improvement:
        figures[model_figure_id] = {
            "title": "Proposed model architecture",
            "label": "fig:model-architecture",
            "kind": "mechanism",
            "phase": 1,
            "width": "single-column",
            "source_sections": ["method"],
            "description": (
                "Placeholder for the proposed model improvement, showing inputs, "
                "new modules, information flow, and prediction output."
            ),
            "caption": (
                "Architecture of the proposed model improvement; the hosted Studio "
                "reserves this location as a placeholder for the final model diagram."
            ),
            "result_keys": [],
            "depends_on_paragraphs": {"method": ["M2"]},
            "generation_requires_paragraphs": {"method": ["M2"]},
            "panels": [],
            "deliverable_stem": "model_architecture",
        }
        figure_order.append(model_figure_id)
    if has_results:
        data_grid = {
            "type": "records",
            "path": "lightweight_results.rows",
            "columns": columns,
        }
        tables["T1"] = {
            "title": caption,
            "label": "tab:results",
            "kind": "table",
            "phase": 1,
            "width": "single-column",
            "source_sections": ["experiments"],
            "description": caption,
            "caption": caption,
            "related_paragraphs": {"experiments": ["E2"]},
            "data_grid": data_grid,
            "prompt": {
                "columns": " | ".join(column["label"] for column in columns),
                "rows": "source",
                "font_size": "small",
                "best_values": "none",
            },
        }
        table_order.append("T1")
        figures[data_figure_id] = {
            "title": caption,
            "label": "fig:results",
            "kind": "data",
            "phase": 1,
            "width": "single-column",
            "source_sections": ["experiments"],
            "description": caption,
            "caption": caption,
            "result_keys": ["lightweight_results.rows"],
            "depends_on_paragraphs": {"experiments": ["E2"]},
            "panels": [
                {
                    "id": "a",
                    "title": caption,
                    "goal": caption,
                    "result_keys": ["lightweight_results.rows"],
                }
            ],
            "data_grid": data_grid,
            "deliverable_stem": "lightweight_results",
        }
        figure_order.append(data_figure_id)
    else:
        tables["T1"] = {
            "title": "Planned main experimental comparison",
            "label": "tab:main-results",
            "kind": "table",
            "phase": 1,
            "width": "single-column",
            "source_sections": ["experiments"],
            "description": "Placeholder for the planned main experimental comparison.",
            "caption": "Planned main experimental comparison across methods and evaluation criteria.",
            "result_keys": [],
            "related_paragraphs": {"experiments": ["E2"]},
            "online_placeholder": True,
            "data_grid": {
                "type": "records",
                "path": "lightweight_results.rows",
                "columns": [
                    {"key": "method", "label": "Method"},
                    {"key": "main_result", "label": "Main result"},
                ],
            },
            "prompt": {
                "columns": "Method | Main result",
                "rows": "source",
                "font_size": "small",
                "best_values": "none",
            },
        }
        table_order.append("T1")
        figures[data_figure_id] = {
            "title": "Planned primary result analysis",
            "label": "fig:planned-results",
            "kind": "data",
            "phase": 1,
            "width": "single-column",
            "source_sections": ["experiments"],
            "description": (
                "Placeholder for the planned primary numerical comparison; no "
                "measurements are available in the hosted project yet."
            ),
            "caption": (
                "Planned primary result analysis; values and curves will be filled "
                "after the experiment evidence is supplied."
            ),
            "result_keys": [],
            "depends_on_paragraphs": {"experiments": ["E2"]},
            "panels": [
                {
                    "id": "a",
                    "title": "Planned primary result analysis",
                    "goal": (
                        "Show the planned numerical trend or comparison without "
                        "inventing measurements."
                    ),
                    "result_keys": [],
                }
            ],
            "data_grid": {
                "type": "records",
                "path": "lightweight_results.rows",
                "columns": [
                    {"key": "condition", "label": "Condition"},
                    {"key": "main_result", "label": "Main result"},
                ],
            },
            "deliverable_stem": "planned_results",
            "online_placeholder": True,
        }
        figure_order.append(data_figure_id)

    contract_metrics: dict[str, Any] = {}
    if approved_contract is not None:
        structure_contract, _contract_rows = _contract_result_tables(
            approved_contract, result_documents
        )
    else:
        experiments_artifacts = ["T1", data_figure_id]
        seed_outline = []
        for section_id, section_title, _render, default_purpose in sections:
            seed_paragraphs = []
            for paragraph_index, paragraph_purpose in enumerate(
                LIGHTWEIGHT_PARAGRAPH_PURPOSES.get(section_id, [default_purpose]), 1
            ):
                if section_id == "experiments" and paragraph_index == 2 and not has_results:
                    paragraph_purpose = (
                        "Introduce the planned main comparison, cite its bound table "
                        "and data-figure placeholders, and use xx for every unavailable "
                        "result without claiming an observed outcome."
                    )
                if section_id == "discussion" and paragraph_index == 1:
                    paragraph_purpose = (
                        "Interpret the verified findings, cite the bound result table "
                        "and data figure, separate observation from hypothesis, and "
                        "explain practical implications."
                        if has_results
                        else
                        "Cite the bound result-table and data-figure placeholders, "
                        "explain what comparisons and trends they are designed to test, "
                        "state the current evidence gap explicitly, and discuss only "
                        "hypotheses without claiming observed findings."
                    )
                seed_paragraphs.append({
                    "id": f"{section_id[:1].upper()}{paragraph_index}",
                    "plan_sentence": paragraph_purpose,
                    "supports": [],
                    "evidence": ["uploaded project brief and experiment evidence"],
                    "artifact_refs": (
                        experiments_artifacts
                        if section_id == "experiments" and paragraph_index == 2
                        else [motivation_figure_id]
                        if section_id == "introduction" and paragraph_index == 1
                        else experiments_artifacts
                        if section_id == "discussion" and paragraph_index == 1
                        else [model_figure_id]
                        if section_id == "method" and paragraph_index == 2 and has_model_improvement
                        else []
                    ),
                })
            seed_outline.append({"section_id": section_id, "title": section_title, "paragraphs": seed_paragraphs})
        structure_contract = {
            "target": {"venue": venue}, "paper_title": title,
            "claims": [], "paper_outline": seed_outline,
            "paper_artifacts": [
                {"id": artifact_id, "kind": definition.get("kind"), "section_id": (definition.get("source_sections") or ["experiments"])[0], "supports": [], "shell": {"caption": definition.get("caption", "")}}
                for artifact_id, definition in {**figures, **tables}.items()
            ],
        }
    structure_contract["writing_boundary"] = {
        "experiment_results_available": bool(results_files),
        "numeric_policy": (
            "verified_values" if results_files else "replace_quantitative_values_with_xx"
        ),
        "from_experiments_onward": (
            "draft_with_verified_results"
            if results_files else "draft_proposed_experiment_design_without_results"
        ),
    }
    # For an exported Experiment Plan, claims/obligations already identify the
    # target. For a raw TXT brief they do not; the brief must therefore travel
    # in the same target-only contract sent to the structure designer. It is
    # never appended to the structure-reference source.
    structure_contract["target_project_brief"] = project_text
    structure_contract["target_project_analysis"] = target_analysis
    report(
        "reference_analysis",
        "正在分析 ref paper，并为目标论文逐段匹配写作结构…",
        38,
    )
    structure_design = _design_lightweight_structure_online(
        root, structure_contract, reference_source,
        {key: main_reference.get(key) for key in ("title", "authors", "venue", "year", "url", "bibtex_key")},
        api_key=api_key, model=model,
    )
    report("workspace", "逐段映射已完成，正在生成 Paper Studio 项目…", 82)
    if approved_contract is not None:
        designed_sections = []
        for index, designed in enumerate(structure_design["paper_outline"], 1):
            section_id = _safe_slug(
                str(designed.get("section_id") or designed.get("title")),
                f"section-{index}",
            ).replace("-", "_")
            if str(designed.get("title") or "").casefold() == "abstract":
                section_id = "abstract"
            designed_sections.append({
                "id": section_id,
                "source_id": str(designed.get("section_id") or section_id),
                "title": str(designed.get("title") or section_id),
                "paragraphs": [
                    {
                        "id": str(paragraph.get("id") or ""),
                        "artifacts": [str(item) for item in paragraph.get("artifact_refs", [])],
                    }
                    for paragraph in designed.get("paragraphs", [])
                    if isinstance(paragraph, dict)
                ],
            })
        figures, tables, contract_metrics = _artifact_definitions(
            structure_contract,
            designed_sections,
            allow_empty_result_artifacts=True,
        )
        for definition in [*figures.values(), *tables.values()]:
            definition["phase"] = 1
        figure_order = [
            str(item.get("id"))
            for item in structure_contract.get("paper_artifacts", [])
            if isinstance(item, dict) and item.get("id") in figures
        ]
        table_order = [
            str(item.get("id"))
            for item in structure_contract.get("paper_artifacts", [])
            if isinstance(item, dict) and item.get("id") in tables
        ]
        has_results = bool(contract_metrics.get("artifacts"))
    section_specs = []
    plan_sections: dict[str, list[dict[str, Any]]] = {}
    for index, designed in enumerate(structure_design["paper_outline"], 1):
        section_id = _safe_slug(str(designed.get("section_id") or designed.get("title")), f"section-{index}").replace("-", "_")
        section_title = str(designed.get("title") or section_id).strip()
        render = "abstract" if section_id == "abstract" or section_title.casefold() == "abstract" else "section"
        filename = f"{section_id}.tex"
        section_result_keys = [
            key
            for definition in [*figures.values(), *tables.values()]
            if section_id in definition.get("source_sections", [])
            for key in definition.get("result_keys", [])
        ]
        if approved_contract is not None:
            section_result_keys = [
                *dict.fromkeys(
                    ["lightweight_result_summaries", *section_result_keys, "lightweight_project"]
                )
            ]
        elif has_results:
            section_result_keys = [
                "lightweight_result_summaries", "lightweight_results", "lightweight_project"
            ]
        else:
            section_result_keys = ["lightweight_project"]
        section_specs.append({
            "id": section_id, "title": section_title,
            "latex_title": "" if render == "abstract" else section_title,
            "start_label": "" if render == "abstract" else f"sec:{section_id.replace('_', '-')}",
            "file": filename,
            "render": render,
            # Put concise numeric evidence first because section_evidence has
            # a strict context bound; uploaded prose/raw samples remain useful
            # background but must not crowd out available measurements.
            "result_keys": section_result_keys,
            "writing_mode": "draft",
        })
        plan_sections[section_id] = []
        for paragraph in designed.get("paragraphs", []):
            planned = {
                "id": str(paragraph["id"]),
                "purpose": str(paragraph["plan_sentence"]),
                "rhetorical_role": str(paragraph["rhetorical_role"]),
                "relation_to_previous": str(paragraph["relation_to_previous"]),
                "relation_to_next": str(paragraph["relation_to_next"]),
                "artifacts": [str(item) for item in paragraph.get("artifact_refs", [])],
                "reference_paragraph_ids": [
                    str(item)
                    for item in paragraph.get("reference_paragraph_ids", [])
                ],
            }
            plan_sections[section_id].append(planned)
        section_specs[-1]["paragraphs"] = plan_sections[section_id]
        placeholder = "% Awaiting paragraph-level drafting in Paper Studio.\n"
        if render != "abstract":
            placeholder = f"\\section{{{_latex_escape(section_title)}}}\n\n" + placeholder
        (sections_dir / filename).write_text(placeholder, encoding="utf-8")
    _write_reference_contexts(
        root,
        paper,
        {
            _safe_slug(str(section.get("section_id") or section.get("title")), f"section-{index}").replace("-", "_"):
            section["reference_context"]
            for index, section in enumerate(structure_design["paper_outline"], 1)
        },
        reference_source=reference_path.relative_to(root).as_posix(),
        reference_title=str(main_reference.get("title") or ""),
    )
    for artifact_id, definition in {**figures, **tables}.items():
        owner = next(
            section_id for section_id, paragraphs in plan_sections.items()
            if any(artifact_id in paragraph["artifacts"] for paragraph in paragraphs)
        )
        paragraph_ids = [paragraph["id"] for paragraph in plan_sections[owner] if artifact_id in paragraph["artifacts"]]
        definition["source_sections"] = [owner]
        definition["related_paragraphs"] = {owner: paragraph_ids}
        if artifact_id in figures:
            definition["depends_on_paragraphs"] = {owner: paragraph_ids}
            # The online structure designer is allowed to renumber paragraph
            # IDs while preserving artifact obligations.  Mechanism figures
            # initially use a seed binding (for example method/M2), so every
            # paragraph-owned prerequisite must be rebound to the approved
            # IDs returned by that design call.  Leaving the seed value here
            # made otherwise-valid model-improvement projects fail Paper
            # Studio preflight after onboarding.
            if "generation_requires_paragraphs" in definition:
                definition["generation_requires_paragraphs"] = {
                    owner: paragraph_ids
                }

    main_inputs = []
    for spec in section_specs:
        section_id, render = spec["id"], spec["render"]
        if render == "abstract":
            main_inputs.append("\\begin{abstract}\n\\input{sections/abstract}\n\\end{abstract}")
        else:
            main_inputs.append(f"\\input{{sections/{section_id}}}")
    for asset_name in venue_template.get("assets", []):
        asset_source = Path(venue_template["_dir"]) / asset_name
        if not asset_source.is_file():
            raise OnlineStudioError(
                f"内置模板“{venue_template['family']}”缺少必需资源文件：{asset_name}。"
            )
        shutil.copyfile(asset_source, paper / asset_name)
    bibliography_lines = (
        [r"\input{sections/bibliography}"]
        if not venue_template.get("needs_bibliographystyle", True)
        else [r"\bibliographystyle{plain}", r"\input{sections/bibliography}"]
    )
    abstract_inputs = [line for line in main_inputs if line.startswith("\\begin{abstract}")]
    body_inputs = [line for line in main_inputs if not line.startswith("\\begin{abstract}")]
    before_maketitle = abstract_inputs if venue_template.get("abstract_before_maketitle") else []
    # Keep the abstract ahead of every body section when the venue places it
    # after \maketitle (ACL and most supported templates).
    after_maketitle = ([] if before_maketitle else abstract_inputs) + body_inputs
    main_tex = "\n".join(
        [
            str(venue_template["documentclass"]),
            *[str(line) for line in venue_template.get("preamble", [])],
            r"\makeatletter\let\paperstudio@cite\cite\renewcommand{\cite}[1]{\if\relax\detokenize{#1}\relax\textbf{[CITATION NEEDED]}\else\paperstudio@cite{#1}\fi}\makeatother",
            f"\\title{{{_latex_escape(title)}}}",
            r"\author{Anonymous Author(s)}",
            r"\date{}",
            r"\begin{document}",
            *before_maketitle,
            r"\maketitle",
            *after_maketitle,
            *bibliography_lines,
            r"\end{document}",
            "",
        ]
    )
    (paper / "main.tex").write_text(main_tex, encoding="utf-8")
    # Build the online citation bank only from metadata already verified by
    # onboarding: the author-owned Scholar papers whose records/full text were
    # used for the profile.  The explicitly uploaded reference is structural
    # authority only and must never become evidence for this project's claims.
    # The
    # paragraph writer receives this bounded bank and may select a key only
    # when it directly supports the claim.  Additional topic sources found by
    # scholarly lookup can be appended later without changing this trust
    # boundary.
    bibliography_records: list[str] = []
    bibliography_keys_seen: set[str] = set()
    for record in lightweight_profile.get("representative_papers", []):
        if not isinstance(record, dict):
            continue
        key = str(record.get("bibtex_key") or "").strip()
        bibtex = str(record.get("bibtex") or "").strip()
        if not key or not bibtex or key in bibliography_keys_seen:
            continue
        bibliography_keys_seen.add(key)
        bibliography_records.append(bibtex)
    # The hosted two-file flow has no Scholar upload. Resolve only scholarly
    # URLs explicitly declared by the project plan. The uploaded reference
    # paper remains structure authority and is excluded from this citation bank.
    for key, bibtex in _verified_contract_bibliography(approved_contract):
        if key in bibliography_keys_seen:
            continue
        bibliography_keys_seen.add(key)
        bibliography_records.append(bibtex)
    (paper / "references.bib").write_text(
        "\n\n".join(bibliography_records).rstrip() + "\n",
        encoding="utf-8",
    )
    (sections_dir / "bibliography.tex").write_text(
        "% Paper Studio enables the bibliography after the first accepted citation.\n",
        encoding="utf-8",
    )
    metrics = {
        "lightweight_project": {
            "has_structured_results": has_results,
            "project_brief_files": [name for name, _text in project_brief_files],
            "result_evidence_files": [name for name, _text in results_files],
            "structural_reference_file": reference_name,
            "citation_policy": "verified_bibliography_with_required_audit",
            "numeric_policy": (
                "verified_values" if results_files else "replace_quantitative_values_with_xx"
            ),
            "project_evidence": reference,
            "personalization": lightweight_profile,
            "result_artifact_source": {
                "file": result_source_file,
                "json_path": result_source_path,
                "extraction": result_extraction,
            },
            "approved_plan_contract": approved_contract is not None,
        }
    }
    if approved_contract is not None:
        metrics.update(contract_metrics)
    elif has_results:
        metrics["lightweight_results"] = {"rows": rows}
    if result_prompt_summaries:
        metrics["lightweight_result_summaries"] = result_prompt_summaries
    (paper / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (paper / "working_abstract.txt").write_text(
        "Draft the abstract only from the project brief and accepted manuscript evidence. No experiment results were uploaded: do not state observed findings or invent measurements, and write every quantitative value as xx. The abstract is self-contained and must contain no citation command. Body paragraphs may use only verified keys supplied in references.bib.\n",
        encoding="utf-8",
    )
    (paper / ".outline-approved").write_text(
        "Auto-approved for the lightweight onboarding path.\n", encoding="utf-8"
    )
    config = {
        "schema_version": "1.0",
        "project": {
            "id": _safe_slug(project_name) + "-" + secrets.token_hex(4),
            "name": project_name,
            "initial_title": title,
            "venue": venue,
            "target": {"venue": venue},
            "reference_paper": {
                key: main_reference.get(key)
                for key in ("title", "authors", "venue", "bibtex_key", "url")
                if main_reference.get(key)
            } | {"publication_key": main_reference["bibtex_key"]},
            "decision_source": (
                "reports/03_EXPERIMENT_PLAN.html"
                if approved_contract is not None
                else "lightweight-onboarding"
            ),
            "eyebrow": "ONLINE PAPER STUDIO",
            "studio_title": "Paper Studio",
            "subtitle": "从科研项目主旨与指定参考论文开始写作",
        },
        "sections": section_specs,
        "batch_writing_order": [item["id"] for item in section_specs],
        "figure_order": figure_order,
        "figures": figures,
        "table_order": table_order,
        "tables": tables,
        "paths": {
            "metrics": "paper/metrics.json",
            "main": "paper/main.tex",
        },
    }
    (paper / "paper_studio.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report("worker", "项目文件已生成，正在启动 Paper Studio 服务…", 94)


def _available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _ensure_unexecuted_result_placeholders(root: Path) -> bool:
    """Keep legacy text-first projects aligned with the hosted placeholder contract."""
    config_path = root / "paper/paper_studio.json"
    metrics_path = root / "paper/metrics.json"
    if not config_path.is_file() or not metrics_path.is_file():
        return False
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    lightweight = metrics.get("lightweight_project", {})
    if not isinstance(lightweight, dict) or lightweight.get("numeric_policy") != (
        "replace_quantitative_values_with_xx"
    ):
        return False

    figures = config.setdefault("figures", {})
    figure_order = config.setdefault("figure_order", [])
    tables = config.setdefault("tables", {})
    if "T1" not in tables:
        return False
    tables["T1"]["online_placeholder"] = True

    data_figure_id = next(
        (
            figure_id
            for figure_id in figure_order
            if figures.get(figure_id, {}).get("kind") == "data"
        ),
        "",
    )
    if not data_figure_id:
        number = 1
        while f"F{number}" in figures:
            number += 1
        data_figure_id = f"F{number}"
        figures[data_figure_id] = {
            "title": "Planned primary result analysis",
            "label": "fig:planned-results",
            "kind": "data",
            "phase": 1,
            "width": "single-column",
            "source_sections": ["experiments"],
            "description": (
                "Placeholder for the planned primary numerical comparison; no "
                "measurements are available in the hosted project yet."
            ),
            "caption": (
                "Planned primary result analysis; values and curves will be filled "
                "after the experiment evidence is supplied."
            ),
            "result_keys": [],
            "depends_on_paragraphs": {"experiments": ["E-P2"]},
            "panels": [{
                "id": "a",
                "title": "Planned primary result analysis",
                "goal": "Show the planned comparison without inventing measurements.",
                "result_keys": [],
            }],
            "data_grid": {
                "type": "records",
                "path": "lightweight_results.rows",
                "columns": [
                    {"key": "condition", "label": "Condition"},
                    {"key": "main_result", "label": "Main result"},
                ],
            },
            "deliverable_stem": "planned_results",
            "online_placeholder": True,
        }
        figure_order.append(data_figure_id)
    else:
        figures[data_figure_id]["online_placeholder"] = True

    changed = False
    for section in config.get("sections", []):
        section_id = str(section.get("id") or "")
        paragraphs = section.get("paragraphs", [])
        if section_id == "experiments" and len(paragraphs) >= 2:
            paragraph = paragraphs[1]
            paragraph["artifacts"] = ["T1", data_figure_id]
            paragraph["purpose"] = (
                "Introduce the planned main comparison, cite its bound table and "
                "data-figure placeholders, and use xx for every unavailable result "
                "without claiming an observed outcome."
            )
            changed = True
        elif section_id == "discussion" and paragraphs:
            paragraph = paragraphs[0]
            paragraph["artifacts"] = ["T1", data_figure_id]
            paragraph["purpose"] = (
                "Cite the bound result-table and data-figure placeholders, explain "
                "what comparisons and trends they are designed to test, state the "
                "current evidence gap explicitly, and discuss only hypotheses without "
                "claiming observed findings."
            )
            changed = True
    if not changed:
        return False
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return True


def _discard_worker_stderr(stream: Any) -> None:
    """Drain the post-startup stderr pipe and close it when the child exits."""
    try:
        while stream.read(8192):
            pass
    except (OSError, ValueError):
        pass
    finally:
        try:
            stream.close()
        except (OSError, ValueError):
            pass


def _start_worker(
    root: Path,
    provider: str,
    model: str,
    api_key: str,
    *,
    demo_mode: bool = False,
) -> tuple[subprocess.Popen[bytes], int]:
    if not demo_mode:
        _ensure_unexecuted_result_placeholders(root)
    port = _available_port()
    environment = dict(os.environ)
    for name in KEY_ENVIRONMENTS:
        environment.pop(name, None)
    key_environment, _default_model = PROVIDERS[provider]
    environment.update(
        {
            "RESEARCH_AVATAR_ROOT": str(root),
            "PAPER_STUDIO_PROVIDER": provider,
            "PAPER_STUDIO_MODEL": model,
            # The public Demo is the completed local/full Paper Studio surface
            # with every real figure and editable artifact visible.  It stays
            # safe because DEMO_MODE disables controls in the UI and the
            # gateway rejects every mutating request; ONLINE mode is reserved
            # for real hosted writing sessions, where unsupported figures are
            # intentionally placeholders.
            "PAPER_STUDIO_ONLINE": "0" if demo_mode else "1",
            "PAPER_STUDIO_DEMO_MODE": "1" if demo_mode else "0",
            key_environment: api_key,
        }
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "research_avatar.paper_studio.server",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-browser",
            "--provider",
            provider,
            "--model",
            model,
        ],
        # Keep module discovery independent from the untrusted session root.
        # All project reads/writes are already redirected by RESEARCH_AVATAR_ROOT.
        cwd=Path(__file__).resolve().parents[2],
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        # Keep startup diagnostics long enough to report configuration and
        # dependency failures to the onboarding surface.  Discarding stderr
        # here used to turn every actionable preflight error into the same
        # opaque "writer startup failed" message and made a generated workspace
        # impossible to debug.  Paper Studio is intentionally quiet on
        # stderr after startup, so the bounded pipe is safe for the worker's
        # lifetime.
        stderr=subprocess.PIPE,
    )
    deadline = time.time() + 15
    while time.time() < deadline:
        if process.poll() is not None:
            stderr = b""
            if process.stderr is not None:
                stderr = process.stderr.read()
            detail = stderr.decode("utf-8", errors="replace").strip()
            if detail:
                # Do not return an unbounded traceback through the public
                # endpoint.  The final lines contain the raised validation
                # error and are the useful part for both users and operators.
                detail = "\n".join(detail.splitlines()[-8:])[-1600:]
                raise OnlineStudioError(f"Paper Studio 写作进程启动失败：\n{detail}")
            raise OnlineStudioError("Paper Studio 写作进程启动失败，请检查服务端依赖。")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=0.5):
                if process.stderr is not None:
                    threading.Thread(
                        target=_discard_worker_stderr,
                        args=(process.stderr,),
                        daemon=True,
                        name=f"paper-studio-stderr-{port}",
                    ).start()
                return process, port
        except (urllib.error.URLError, TimeoutError, socket.timeout):
            time.sleep(0.1)
    process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)
    stderr = b""
    if process.stderr is not None:
        stderr = process.stderr.read()
    detail = stderr.decode("utf-8", errors="replace").strip()
    if detail:
        detail = "\n".join(detail.splitlines()[-8:])[-1600:]
        raise OnlineStudioError(f"Paper Studio 写作进程启动超时：\n{detail}")
    raise OnlineStudioError("Paper Studio 写作进程启动超时。")


def shared_deepseek_api_key() -> str:
    """The one server-held DeepSeek key every online session uses."""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise OnlineStudioError("服务端尚未配置共享 DeepSeek API key，请联系管理员。")
    return api_key


def user_project_root(user_id: str) -> Path:
    return DATA_ROOT / "projects" / hashlib.sha256(user_id.encode("utf-8")).hexdigest()


def user_cumulative_cost_usd(user_id: str) -> float:
    """Sum estimated cost across every session this user has ever created.

    Each session is its own subprocess with its own project-scoped usage
    ledger (paper/.paper_studio/api_usage.jsonl); this walks all of a
    user's session directories under their stable per-user root so the
    spend cap holds across sessions, not just within one.
    """
    total = 0.0
    root = user_project_root(user_id)
    if not root.is_dir():
        return total
    for ledger in root.glob("*/paper/.paper_studio/api_usage.jsonl"):
        summary = usage_summary(ledger)
        total += float(summary.get("estimated_cost_usd") or 0.0)
    return total


def require_under_spend_cap(user_id: str) -> None:
    spent_rmb = user_cumulative_cost_usd(user_id) * USD_TO_RMB_RATE
    if spent_rmb >= USER_SPEND_CAP_RMB:
        raise OnlineStudioError(
            f"当前账户共享额度已用满（上限 {USER_SPEND_CAP_RMB:.0f} 元），"
            "暂时无法创建或继续写作会话。"
        )


def create_session(
    payload: dict[str, Any], *, user_id: str,
    progress: Callable[[str, str, int], None] | None = None,
) -> Session:
    with SESSIONS_LOCK:
        active_sessions = sum(
            session.process.poll() is None for session in SESSIONS.values()
        )
    if active_sessions >= MAX_ACTIVE_SESSIONS:
        raise OnlineStudioError("当前在线写作会话已满，请稍后重试。")
    require_under_spend_cap(user_id)
    api_key = shared_deepseek_api_key()
    provider = SHARED_PROVIDER
    model = PROVIDERS[provider][1]
    session_id = secrets.token_urlsafe(32)
    root = user_project_root(user_id) / hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    mode = str(payload.get("mode") or "package").strip().lower()
    if progress is not None:
        progress("validation", "正在校验上传文件…", 5)
    try:
        if mode in {"materials", "lightweight"}:
            project_brief_files = _decode_document_files(
                payload.get("project_brief_files"),
                label="当前工作说明",
                required=True,
                max_files=1,
            )
            if progress is not None:
                progress(
                    "reference_pdf",
                    "正在提取并由 DeepSeek 整理结构参考论文 PDF…",
                    8,
                )
            reference_paper_files = _decode_document_files(
                payload.get("reference_paper_files"),
                label="结构参考论文",
                required=True,
                max_files=1,
            )
            _write_lightweight_workspace(
                root,
                venue=str(payload.get("venue") or ""),
                project_name=str(payload.get("project_name") or ""),
                title=str(payload.get("title") or ""),
                scholar_files=[],
                project_brief_files=project_brief_files,
                # The hosted flow deliberately does not accept or analyze
                # experiment results. Experiments onward remain plan-only.
                results_files=[],
                reference_paper_files=reference_paper_files,
                api_key=api_key,
                model=model,
                progress=progress,
            )
        else:
            files = _decode_html_files(payload.get("files")) if payload.get("files") else []
            archive = _decode_evidence_archive(payload.get("evidence_archive"))
            _write_workspace(
                root,
                files=files,
                archive=archive,
                api_key=api_key,
                model=model,
            )
        if progress is not None:
            progress("worker", "正在启动 Paper Studio 服务…", 96)
        process, port = _start_worker(root, provider, model, api_key)
    except Exception:
        if root.exists():
            shutil.rmtree(root)
        raise
    session = Session(session_id, user_id, root, provider, model, process, port, api_key)
    _record_session_access(session)
    with SESSIONS_LOCK:
        SESSIONS[session_id] = session
    return session


def _update_onboarding_job(
    job_id: str, stage: str, message: str, progress: int
) -> None:
    with ONBOARDING_JOBS_LOCK:
        job = ONBOARDING_JOBS.get(job_id)
        if job is None or job.status != "running":
            return
        job.stage = stage
        job.message = message
        job.progress = max(job.progress, min(99, int(progress)))
        job.updated_at = time.time()


def start_onboarding_job(payload: dict[str, Any], *, user_id: str) -> OnboardingJob:
    """Start session creation off-request so proxies never hold a minute-long POST."""
    with ONBOARDING_JOBS_LOCK:
        running = next(
            (
                item for item in ONBOARDING_JOBS.values()
                if item.user_id == user_id and item.status == "running"
            ),
            None,
        )
        if running is not None:
            return running
        job = OnboardingJob(secrets.token_urlsafe(24), user_id)
        ONBOARDING_JOBS[job.job_id] = job

    def work() -> None:
        try:
            session = create_session(
                payload,
                user_id=user_id,
                progress=lambda stage, status, percent: _update_onboarding_job(
                    job.job_id, stage, status, percent
                ),
            )
        except OnlineStudioError as exc:
            with ONBOARDING_JOBS_LOCK:
                current = ONBOARDING_JOBS.get(job.job_id)
                if current is not None:
                    current.status = "failed"
                    current.error = str(exc)
                    current.message = "初始化失败。"
                    current.updated_at = time.time()
            return
        except Exception:
            with ONBOARDING_JOBS_LOCK:
                current = ONBOARDING_JOBS.get(job.job_id)
                if current is not None:
                    current.status = "failed"
                    current.error = "初始化发生内部错误，请重试。"
                    current.message = "初始化失败。"
                    current.updated_at = time.time()
            return
        with ONBOARDING_JOBS_LOCK:
            current = ONBOARDING_JOBS.get(job.job_id)
            if current is not None:
                current.status = "completed"
                current.stage = "ready"
                current.message = "Paper Studio 已就绪，正在打开…"
                current.progress = 100
                current.session_id = session.session_id
                current.updated_at = time.time()

    threading.Thread(
        target=work,
        daemon=True,
        name=f"online-onboarding-{job.job_id[:8]}",
    ).start()
    return job


def onboarding_job(job_id: str, *, user_id: str) -> OnboardingJob | None:
    with ONBOARDING_JOBS_LOCK:
        job = ONBOARDING_JOBS.get(job_id)
        return job if job is not None and job.user_id == user_id else None


def demo_session() -> Session:
    """Start one shared read-only worker from the committed completed project."""
    global DEMO_SESSION
    with DEMO_SESSION_LOCK:
        if DEMO_SESSION and DEMO_SESSION.process.poll() is None:
            DEMO_SESSION.last_access = time.time()
            return DEMO_SESSION
        if not (DEMO_PROJECT / "paper/paper_studio.json").is_file():
            raise OnlineStudioError("完成态 Demo 论文项目尚未安装。")
        session_id = "demo-" + secrets.token_urlsafe(12)
        root = DATA_ROOT / "demo" / hashlib.sha256(session_id.encode("utf-8")).hexdigest()
        if root.exists():
            raise OnlineStudioError("Demo 工作目录冲突，请重试。")
        root.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(DEMO_PROJECT, root)
        try:
            process, port = _start_worker(
                root,
                "openai",
                "gpt-5-nano",
                "demo-read-only-no-api-calls",
                demo_mode=True,
            )
        except Exception:
            shutil.rmtree(root, ignore_errors=True)
            raise
        DEMO_SESSION = Session(
            session_id,
            "*",
            root,
            "openai",
            "gpt-5-nano",
            process,
            port,
            "demo-read-only-no-api-calls",
            kind="demo",
        )
        return DEMO_SESSION


def _ensure_session_alive(session: Session) -> bool:
    """Respawn a session's writer process if it died underneath it.

    A live batch full-draft job runs almost entirely in a background thread
    with no inbound HTTP request in flight; a container platform hiccup or
    an unexpected child-process death otherwise strands the researcher with
    a permanent "session missing or expired" error even though every accepted paragraph
    was already durably written to paper/sections/*.tex and
    paper/.paper_studio/state.json. research_avatar.paper_studio.server
    already has dedicated recovery logic for exactly this — a fresh process
    pointed at the same root detects a stale full_draft_job from a
    different SERVER_INSTANCE_TOKEN at startup and turns it into a clean
    recoverable "service restarted; continue unfinished paragraphs" state, but
    only if something actually
    restarts the child. This is that something.
    """
    if session.process.poll() is None:
        return True
    if not session.api_key:
        return False
    try:
        process, port = _start_worker(
            session.root,
            session.provider,
            session.model,
            session.api_key,
            demo_mode=(session.kind == "demo"),
        )
    except Exception:
        return False
    with SESSIONS_LOCK:
        if session.process.poll() is None:
            # Another thread already respawned this session first.
            process.terminate()
            return True
        session.process = process
        session.port = port
    return True


def _record_session_access(session: Session, now: float | None = None) -> None:
    """Record user-visible activity in memory and beside the durable project."""
    timestamp = time.time() if now is None else now
    session.last_access = timestamp
    if session.kind != "user":
        return
    marker = session.root / SESSION_ACTIVITY_FILE
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch(exist_ok=True)
        os.utime(marker, (timestamp, timestamp))
    except OSError:
        # In-memory expiry remains authoritative while this gateway is alive.
        pass


def _project_last_access(root: Path) -> float | None:
    """Read persisted activity, with a migration fallback for older projects."""
    candidates = (root / SESSION_ACTIVITY_FILE, root / "paper/paper_studio.json")
    for candidate in candidates:
        try:
            return candidate.stat().st_mtime
        except OSError:
            continue
    return None


def _terminate_session(session: Session, *, delete_content: bool) -> None:
    if session.process.poll() is None:
        session.process.terminate()
    if delete_content and session.kind == "user":
        shutil.rmtree(session.root, ignore_errors=True)


def _expire_session(session: Session, *, now: float | None = None) -> bool:
    """Delete an idle user's whole temporary project, never merely its worker."""
    timestamp = time.time() if now is None else now
    if session.kind != "user" or timestamp - session.last_access <= SESSION_IDLE_SECONDS:
        return False
    with SESSIONS_LOCK:
        current = SESSIONS.get(session.session_id)
        if current is session:
            SESSIONS.pop(session.session_id, None)
    _terminate_session(session, delete_content=True)
    return True


def _session_from_cookie(
    header: str | None, *, user_id: str, record_access: bool = True
) -> Session | None:
    session_id = _cookie_value(header, COOKIE_NAME)
    with SESSIONS_LOCK:
        session = SESSIONS.get(session_id) if session_id is not None else None
        if session is not None and session.user_id != user_id:
            # Never turn a foreign session cookie into an account-level lookup.
            return None
        if session is None:
            # Auth sessions survive browser restarts, while the HttpOnly writer
            # cookie may not (private windows and browser-test contexts are the
            # common case). Recover the researcher's most recently used live
            # session by authenticated owner identity; user_id remains the
            # authorization boundary, so this never exposes another account.
            owned = sorted(
                (
                    candidate
                    for candidate in SESSIONS.values()
                    if candidate.user_id == user_id and candidate.kind == "user"
                ),
                key=lambda candidate: candidate.last_access,
                reverse=True,
            )
            session = owned[0] if owned else None
    if session is not None and _expire_session(session):
        return None
    if session is None and session_id:
        # The gateway itself may restart while the durable Paper Studio project
        # remains intact. The session cookie is high entropy and its project
        # path is additionally scoped under the authenticated user, so it is
        # safe to reconstruct the in-memory proxy and respawn its worker.
        root = user_project_root(user_id) / hashlib.sha256(
            session_id.encode("utf-8")
        ).hexdigest()
        if (root / "paper/paper_studio.json").is_file():
            persisted_access = _project_last_access(root)
            if (
                persisted_access is None
                or time.time() - persisted_access > SESSION_IDLE_SECONDS
            ):
                shutil.rmtree(root, ignore_errors=True)
                return None
            try:
                api_key = shared_deepseek_api_key()
                process, port = _start_worker(
                    root, SHARED_PROVIDER, PROVIDERS[SHARED_PROVIDER][1], api_key
                )
            except Exception:
                return None
            recovered = Session(
                session_id,
                user_id,
                root,
                SHARED_PROVIDER,
                PROVIDERS[SHARED_PROVIDER][1],
                process,
                port,
                api_key,
                last_access=persisted_access,
            )
            with SESSIONS_LOCK:
                existing = SESSIONS.setdefault(session_id, recovered)
            if existing is not recovered:
                process.terminate()
            session = existing
    if session is None:
        return None
    if not _ensure_session_alive(session):
        with SESSIONS_LOCK:
            SESSIONS.pop(session.session_id, None)
        return None
    if record_access:
        _record_session_access(session)
    return session


def close_session(header: str | None, *, user_id: str) -> bool:
    """End the caller's own writing session immediately on logout.

    Without this, a session's spawned research_avatar.paper_studio.server
    child process only ever stops via the four-hour idle reaper, so it keeps
    running (and consuming the shared container's finite memory) for the
    rest of that window even though the researcher is gone. Scoped to the
    caller's own user_id, matching every other session lookup in this file.
    """
    session_id = _cookie_value(header, COOKIE_NAME)
    with SESSIONS_LOCK:
        session = SESSIONS.get(session_id) if session_id is not None else None
        if session is not None and session.user_id != user_id:
            return False
        if session is None:
            owned = sorted(
                (
                    candidate
                    for candidate in SESSIONS.values()
                    if candidate.user_id == user_id and candidate.kind == "user"
                ),
                key=lambda candidate: candidate.last_access,
                reverse=True,
            )
            session = owned[0] if owned else None
        if session is None:
            return False
        SESSIONS.pop(session.session_id)
    _terminate_session(session, delete_content=False)
    return True


def reset_session(header: str | None, *, user_id: str) -> bool:
    """Destroy the caller's current temporary project and its writer process."""
    session_id = _cookie_value(header, COOKIE_NAME)
    session: Session | None = None
    with SESSIONS_LOCK:
        if session_id is not None:
            candidate = SESSIONS.get(session_id)
            if candidate is not None and candidate.user_id != user_id:
                return False
            session = candidate
        if session is None:
            owned = sorted(
                (
                    candidate
                    for candidate in SESSIONS.values()
                    if candidate.user_id == user_id and candidate.kind == "user"
                ),
                key=lambda candidate: candidate.last_access,
                reverse=True,
            )
            session = owned[0] if owned else None
        if session is not None:
            SESSIONS.pop(session.session_id, None)
    if session is not None:
        _terminate_session(session, delete_content=True)
        return True
    if session_id:
        root = user_project_root(user_id) / hashlib.sha256(
            session_id.encode("utf-8")
        ).hexdigest()
        existed = root.exists()
        shutil.rmtree(root, ignore_errors=True)
        return existed
    return False


def _reap_expired_sessions(*, now: float | None = None) -> int:
    """Apply idle expiry immediately; split out so the policy is testable."""
    timestamp = time.time() if now is None else now
    with SESSIONS_LOCK:
        candidates = list(SESSIONS.values())
    return sum(_expire_session(session, now=timestamp) for session in candidates)


def _reap_expired_projects(*, now: float | None = None) -> int:
    """Delete stale user projects even when logout/restart removed memory state."""
    timestamp = time.time() if now is None else now
    with SESSIONS_LOCK:
        active_roots = {
            session.root.resolve()
            for session in SESSIONS.values()
            if session.kind == "user"
        }
    projects_root = DATA_ROOT / "projects"
    removed = 0
    if not projects_root.is_dir():
        return removed
    for owner_root in projects_root.iterdir():
        if not owner_root.is_dir():
            continue
        for project_root in owner_root.iterdir():
            if not project_root.is_dir() or project_root.resolve() in active_roots:
                continue
            last_access = _project_last_access(project_root)
            if (
                last_access is not None
                and timestamp - last_access > SESSION_IDLE_SECONDS
            ):
                shutil.rmtree(project_root, ignore_errors=True)
                removed += 1
    return removed


def _reap_sessions() -> None:
    while True:
        time.sleep(60)
        _reap_expired_sessions()
        _reap_expired_projects()
        job_cutoff = time.time() - 1800
        with ONBOARDING_JOBS_LOCK:
            for job_id in [
                key
                for key, job in ONBOARDING_JOBS.items()
                if job.status != "running" and job.updated_at < job_cutoff
            ]:
                ONBOARDING_JOBS.pop(job_id, None)


class OnlineServer(ThreadingHTTPServer):
    request_queue_size = 64


class Handler(BaseHTTPRequestHandler):
    server_version = "OnlinePaperStudio/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        del fmt
        path = self.path.split("?", 1)[0]
        status = str(args[1]) if len(args) > 1 else "-"
        print(
            f"[online-paper-studio] {self.address_string()} "
            f"{self.command} {path} {status}"
        )

    def _headers(
        self,
        content_type: str,
        length: int,
        status: int = 200,
        *,
        allow_same_origin_frame: bool = False,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "X-Frame-Options",
            "SAMEORIGIN" if allow_same_origin_frame else "DENY",
        )
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; object-src 'none'; base-uri 'none'; "
            + (
                "frame-src 'self'; frame-ancestors 'self'"
                if allow_same_origin_frame
                else "frame-ancestors 'none'"
            ),
        )
        self.end_headers()

    def _bytes(
        self,
        data: bytes,
        content_type: str,
        status: int = 200,
        *,
        allow_same_origin_frame: bool = False,
    ) -> None:
        self._headers(
            content_type,
            len(data),
            status,
            allow_same_origin_frame=allow_same_origin_frame,
        )
        self._write_body(data)

    def _write_body(self, data: bytes) -> None:
        """Write one response body without logging normal browser cancellation."""
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True

    def _json(
        self,
        payload: Any,
        status: int = 200,
        *,
        cookie: str | None = None,
        cookies: list[str] | None = None,
    ) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        for value in cookies or []:
            self.send_header("Set-Cookie", value)
        self.end_headers()
        self._write_body(data)

    def _redirect(self, location: str, *, cookies: list[str] | None = None) -> None:
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        for cookie in cookies or []:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise OnlineStudioError("请求长度无效。") from exc
        if length <= 0 or length > MAX_BODY_BYTES:
            raise OnlineStudioError("请求为空或超过 24 MB。")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OnlineStudioError("请求必须是有效 JSON。") from exc
        if not isinstance(payload, dict):
            raise OnlineStudioError("请求必须是 JSON 对象。")
        return payload

    def _current_user(self) -> dict[str, str] | None:
        if os.environ.get("ONLINE_STUDIO_TRUST_PROXY_AUTH", "").lower() in {
            "1",
            "true",
            "yes",
        }:
            user_id = self.headers.get("X-Online-User-Id", "").strip()
            email = self.headers.get("X-Online-User-Email", "").strip()
            provider = self.headers.get("X-Online-User-Provider", "").strip()
            if user_id and email and provider in {"local", "google"}:
                return {"id": user_id, "email": email, "provider": provider}
            return None
        return authenticated_user(self.headers.get("Cookie"))

    def _require_user(self) -> dict[str, str] | None:
        user = self._current_user()
        if user is None:
            self._json({"ok": False, "error": "请先登录。"}, 401)
        return user

    def _require_session(self, user: dict[str, str]) -> Session | None:
        session = _session_from_cookie(
            self.headers.get("Cookie"), user_id=user["id"]
        )
        if session is None:
            self._json({"ok": False, "error": "会话不存在或已过期，请重新上传资料。"}, 401)
        return session

    def _clear_paper_session_cookie(self) -> str:
        cookie = f"{COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"
        if _secure_cookies():
            cookie += "; Secure"
        return cookie

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._bytes((STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif path in {"/studio", "/demo-studio"} or path.startswith("/demo-studio/"):
            # Browser navigation must always end on HTML.  The Cloudflare
            # gateway already performs this redirect; keep the local online
            # debug server identical instead of showing a bare 401 JSON page.
            if self._current_user() is None:
                self._redirect("/?login_required=1")
                return
            if path == "/studio" and self.headers.get("Sec-Fetch-Dest", "").lower() != "iframe":
                self._redirect("/?open=use")
                return
            if path == "/demo-studio":
                self._redirect("/demo-studio/")
                return
            if path.startswith("/demo-studio/"):
                try:
                    session = demo_session()
                    upstream = "/" + path[len("/demo-studio/") :]
                    self._proxy(session, upstream, read_only=True)
                except OnlineStudioError as exc:
                    self._json({"ok": False, "error": str(exc)}, 503)
                return
            session = _session_from_cookie(
                self.headers.get("Cookie"), user_id=self._current_user()["id"]
            )
            if session is None:
                self._redirect(
                    "/?session_expired=1",
                    cookies=[self._clear_paper_session_cookie()],
                )
                return
            self._proxy(session, "/")
        elif path == "/online-assets/app.js":
            self._bytes((STATIC / "app.js").read_bytes(), "text/javascript; charset=utf-8")
        elif path == "/online-assets/style.css":
            self._bytes((STATIC / "style.css").read_bytes(), "text/css; charset=utf-8")
        elif path == "/demo":
            if self._require_user():
                self._redirect("/demo/")
        elif path.startswith("/demo/"):
            if not self._require_user():
                return
            relative = path[len("/demo/") :] or "index.html"
            candidate = (DEMO_STATIC / relative).resolve()
            try:
                candidate.relative_to(DEMO_STATIC.resolve())
            except ValueError:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            content_types = {
                ".html": "text/html; charset=utf-8",
                ".js": "text/javascript; charset=utf-8",
                ".css": "text/css; charset=utf-8",
                ".json": "application/json; charset=utf-8",
                ".png": "image/png",
                ".svg": "image/svg+xml; charset=utf-8",
            }
            if not candidate.is_file() or candidate.suffix.lower() not in content_types:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self._bytes(
                candidate.read_bytes(),
                content_types[candidate.suffix.lower()],
                allow_same_origin_frame=True,
            )
        elif path == "/api/online/health":
            self._json({"ok": True, "service": "online-paper-studio"})
        elif path == "/api/auth/session":
            user = self._current_user()
            self._json(
                {
                    "ok": True,
                    "authenticated": user is not None,
                    "user": (
                        {"email": user["email"], "provider": user["provider"]}
                        if user
                        else None
                    ),
                    "google_configured": google_login_configured(),
                }
            )
        elif path == "/api/online/session/job":
            user = self._require_user()
            if user:
                query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                job_id = str((query.get("job_id") or [""])[0]).strip()
                job = onboarding_job(job_id, user_id=user["id"])
                if job is None:
                    self._json({"ok": False, "error": "初始化任务不存在或已过期。"}, 404)
                elif job.status == "failed":
                    self._json({"ok": False, "error": job.error}, 400)
                elif job.status == "completed":
                    with SESSIONS_LOCK:
                        session = SESSIONS.get(job.session_id)
                    if session is None:
                        self._json({"ok": False, "error": "写作会话启动后意外丢失，请重试。"}, 500)
                    else:
                        cookie = (
                            f"{COOKIE_NAME}={session.session_id}; Path=/; HttpOnly; SameSite=Strict"
                            + ("; Secure" if _secure_cookies() else "")
                        )
                        self._json(
                            {
                                "ok": True,
                                "ready": True,
                                "stage": job.stage,
                                "message": job.message,
                                "progress": job.progress,
                            },
                            cookie=cookie,
                        )
                else:
                    self._json(
                        {
                            "ok": True,
                            "ready": False,
                            "stage": job.stage,
                            "message": job.message,
                            "progress": job.progress,
                        }
                    )
        elif path == "/auth/google/start":
            self._google_start()
        elif path == "/auth/google/callback":
            self._google_callback()
        elif path == "/api/online/session":
            user = self._require_user()
            if user:
                session = _session_from_cookie(
                    self.headers.get("Cookie"),
                    user_id=user["id"],
                    record_access=False,
                )
                self._json(
                    {
                        "ok": True,
                        "active": session is not None,
                        "provider": session.provider if session else None,
                        "model": session.model if session else None,
                    },
                    cookies=(
                        [self._clear_paper_session_cookie()]
                        if session is None
                        else None
                    ),
                )
        elif path == "/api/online/export":
            user = self._require_user()
            if user:
                session = self._require_session(user)
                if session:
                    self._export(session)
        else:
            user = self._require_user()
            if user:
                session = _session_from_cookie(
                    self.headers.get("Cookie"), user_id=user["id"]
                )
                if session is None and path == "/studio":
                    self._redirect(
                        "/?session_expired=1",
                        cookies=[self._clear_paper_session_cookie()],
                    )
                    return
                if session is None:
                    self._json(
                        {"ok": False, "error": "会话不存在或已过期，请重新上传资料。"},
                        401,
                    )
                    return
                if session:
                    upstream = "/" if path == "/studio" else self.path
                    self._proxy(session, upstream)

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in {"/api/auth/signup", "/api/auth/login"}:
            try:
                body = self._read_json()
                user = (
                    create_local_user(body.get("email"), body.get("password"))
                    if path.endswith("signup")
                    else authenticate_local_user(body.get("email"), body.get("password"))
                )
                token = create_auth_session(user["id"])
                self._json(
                    {
                        "ok": True,
                        "user": {"email": user["email"], "provider": user["provider"]},
                    },
                    cookie=_auth_cookie(token),
                )
            except OnlineStudioError as exc:
                self._json({"ok": False, "error": str(exc)}, 400)
        elif path == "/api/auth/logout":
            user = self._current_user()
            if user:
                close_session(self.headers.get("Cookie"), user_id=user["id"])
            revoke_auth_session(self.headers.get("Cookie"))
            self._json(
                {"ok": True},
                cookies=[
                    _auth_cookie("", clear=True),
                    self._clear_paper_session_cookie(),
                ],
            )
        elif path == "/api/online/session/close":
            # Called by the edge Worker's logout handler (proxyIdentified) so a
            # researcher's spawned Paper Studio child process is terminated the
            # moment they log out, instead of leaking into the shared container
            # for up to SESSION_IDLE_SECONDS. Best-effort and idempotent: a
            # missing/foreign/already-closed session is not an error here.
            user = self._current_user()
            if user:
                close_session(self.headers.get("Cookie"), user_id=user["id"])
            self._json({"ok": True})
        elif path == "/api/online/session/reset":
            user = self._require_user()
            if user:
                reset_session(self.headers.get("Cookie"), user_id=user["id"])
                self._json(
                    {"ok": True},
                    cookies=[self._clear_paper_session_cookie()],
                )
        elif path == "/api/online/session":
            user = self._require_user()
            if not user:
                return
            try:
                job = start_onboarding_job(self._read_json(), user_id=user["id"])
                self._json(
                    {
                        "ok": True,
                        "pending": True,
                        "job_id": job.job_id,
                        "stage": job.stage,
                        "message": job.message,
                        "progress": job.progress,
                    },
                    202,
                )
            except OnlineStudioError as exc:
                self._json({"ok": False, "error": str(exc)}, 400)
        elif path.startswith("/demo-studio/"):
            if not self._require_user():
                return
            upstream = "/" + path[len("/demo-studio/") :]
            if upstream not in DEMO_SAFE_WRITE_PATHS:
                self._json({"ok": False, "error": "完成态 Demo 为只读展示。"}, 405)
                return
            try:
                session = demo_session()
                self._proxy(session, upstream, read_only=True)
            except OnlineStudioError as exc:
                self._json({"ok": False, "error": str(exc)}, 503)
        else:
            user = self._require_user()
            if user:
                session = self._require_session(user)
                if session:
                    self._proxy(session, self.path)

    def _google_start(self) -> None:
        if not google_login_configured():
            self._json({"ok": False, "error": "管理员尚未配置 Google 登录。"}, 503)
            return
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        now = time.time()
        with OAUTH_STATES_LOCK:
            OAUTH_STATES[state] = (nonce, now + 600)
            expired = [
                key for key, (_nonce, deadline) in OAUTH_STATES.items() if deadline <= now
            ]
            for key in expired:
                OAUTH_STATES.pop(key, None)
        public_url = os.environ["ONLINE_STUDIO_PUBLIC_URL"].rstrip("/")
        redirect_uri = public_url + "/auth/google/callback"
        query = urllib.parse.urlencode(
            {
                "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"],
                "response_type": "code",
                "scope": "openid email",
                "redirect_uri": redirect_uri,
                "state": state,
                "nonce": nonce,
            }
        )
        state_cookie = (
            f"{GOOGLE_STATE_COOKIE}={state}; Path=/auth/google/callback; "
            "HttpOnly; SameSite=Lax; Max-Age=600"
            + ("; Secure" if _secure_cookies() else "")
        )
        self._redirect(
            "https://accounts.google.com/o/oauth2/v2/auth?" + query,
            cookies=[state_cookie],
        )

    def _google_callback(self) -> None:
        clear_state_cookie = (
            f"{GOOGLE_STATE_COOKIE}=; Path=/auth/google/callback; "
            "HttpOnly; SameSite=Lax; Max-Age=0"
            + ("; Secure" if _secure_cookies() else "")
        )
        try:
            if not google_login_configured():
                raise OnlineStudioError("管理员尚未配置 Google 登录。")
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            state = str((query.get("state") or [""])[0])
            code = str((query.get("code") or [""])[0])
            cookie_state = _cookie_value(self.headers.get("Cookie"), GOOGLE_STATE_COOKIE)
            if (
                not state
                or not code
                or not cookie_state
                or not secrets.compare_digest(state, cookie_state)
            ):
                raise OnlineStudioError("Google 登录 state 校验失败。")
            with OAUTH_STATES_LOCK:
                stored = OAUTH_STATES.pop(state, None)
            if stored is None or stored[1] <= time.time():
                raise OnlineStudioError("Google 登录请求已过期，请重试。")
            nonce = stored[0]
            public_url = os.environ["ONLINE_STUDIO_PUBLIC_URL"].rstrip("/")
            redirect_uri = public_url + "/auth/google/callback"
            encoded_id_token = exchange_google_code(code, redirect_uri)
            claims = verify_google_id_token(encoded_id_token)
            if not secrets.compare_digest(str(claims.get("nonce") or ""), nonce):
                raise OnlineStudioError("Google 登录 nonce 校验失败。")
            if claims.get("email_verified") is not True:
                raise OnlineStudioError("Google 账户邮箱尚未验证。")
            subject = str(claims.get("sub") or "")
            if not subject:
                raise OnlineStudioError("Google 账户缺少稳定 subject。")
            user = google_user(subject, claims.get("email"))
            auth_token = create_auth_session(user["id"])
            self._redirect(
                "/",
                cookies=[clear_state_cookie, _auth_cookie(auth_token)],
            )
        except Exception:
            self._redirect("/?auth_error=google", cookies=[clear_state_cookie])

    def _proxy(self, session: Session, path: str, *, read_only: bool = False) -> None:
        if (
            read_only
            and self.command not in {"GET", "HEAD"}
            and path.split("?", 1)[0] not in DEMO_SAFE_WRITE_PATHS
        ):
            self._json({"ok": False, "error": "完成态 Demo 为只读展示。"}, 405)
            return
        if (
            session.kind == "user"
            and self.command not in {"GET", "HEAD"}
            and user_cumulative_cost_usd(session.user_id) * USD_TO_RMB_RATE >= USER_SPEND_CAP_RMB
        ):
            self._json(
                {
                    "ok": False,
                    "error": f"当前账户共享额度已用满（上限 {USER_SPEND_CAP_RMB:.0f} 元），"
                    "写作会话已切换为只读。",
                },
                402,
            )
            return
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            length = 0
        if length > 2_000_000:
            self._json({"ok": False, "error": "Paper Studio 请求过大。"}, 413)
            return
        body = self.rfile.read(length) if length else None
        headers = {}
        if self.headers.get("Content-Type"):
            headers["Content-Type"] = self.headers["Content-Type"]
        connection = http.client.HTTPConnection("127.0.0.1", session.port, timeout=300)
        response_started = False
        try:
            connection.request(self.command, path, body=body, headers=headers)
            response = connection.getresponse()
            data = response.read()
            self.send_response(response.status)
            response_started = True
            for name, value in response.getheaders():
                if name.lower() not in {"connection", "server", "date", "transfer-encoding", "content-length"}:
                    self.send_header(name, value)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except (OSError, http.client.HTTPException):
            if response_started:
                self.close_connection = True
            else:
                self._json({"ok": False, "error": "写作进程暂时不可用。"}, 502)
        finally:
            connection.close()

    def _export(self, session: Session) -> None:
        try:
            data = _project_zip_bytes(session.root)
        except OnlineStudioError as exc:
            self._json({"ok": False, "error": str(exc)}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", 'attachment; filename="paper-studio-project.zip"')
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self._write_body(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the private Online Paper Studio gateway.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8876)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        if os.environ.get("ONLINE_STUDIO_SECURE_COOKIE", "").lower() not in {"1", "true", "yes"}:
            raise SystemExit("ONLINE_STUDIO_SECURE_COOKIE=1 is required for a non-loopback bind behind HTTPS.")
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=_reap_sessions, daemon=True).start()
    server = OnlineServer((args.host, args.port), Handler)
    print(f"Online Paper Studio: http://{args.host}:{args.port}")
    print(f"Session data: {DATA_ROOT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nOnline Paper Studio stopped.")
    finally:
        server.server_close()
        with SESSIONS_LOCK:
            for session in SESSIONS.values():
                if session.process.poll() is None:
                    session.process.terminate()
        with DEMO_SESSION_LOCK:
            if DEMO_SESSION and DEMO_SESSION.process.poll() is None:
                DEMO_SESSION.process.terminate()


if __name__ == "__main__":
    main()
