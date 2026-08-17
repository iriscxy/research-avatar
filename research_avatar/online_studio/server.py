"""Private online gateway for Paper Studio.

The gateway accepts researcher-owned HTML sources, scaffolds an approved draft
workspace, and proxies the unchanged Paper Studio UI to an isolated localhost
worker. LLM credentials are held only in process memory.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import io
import json
import os
import re
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


STATIC = Path(__file__).resolve().parent / "static"
DEMO_STATIC = Path(__file__).resolve().parents[1] / "web" / "demo"
DEMO_PROJECT = Path(__file__).resolve().parent / "demo_project"
COOKIE_NAME = "paper_studio_session"
AUTH_COOKIE_NAME = "online_studio_auth"
GOOGLE_STATE_COOKIE = "online_studio_google_state"
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
MAX_ACTIVE_SESSIONS = int(os.environ.get("ONLINE_STUDIO_MAX_SESSIONS", "16"))
SESSION_IDLE_SECONDS = int(os.environ.get("ONLINE_STUDIO_IDLE_SECONDS", "14400"))
AUTH_SESSION_SECONDS = int(os.environ.get("ONLINE_STUDIO_AUTH_SECONDS", "2592000"))
KEY_ENVIRONMENTS = ("OPENAI_API_KEY", "DEEPSEEK_API_KEY", "LLM_API_KEY")
PROVIDERS = {
    "openai": ("OPENAI_API_KEY", "gpt-5-nano"),
    "deepseek": ("DEEPSEEK_API_KEY", "deepseek-v4-flash"),
}
DEFAULT_SECTIONS = (
    ("abstract", "Abstract", "abstract", "Summarize the problem, approach, evidence, and main conclusion in one self-contained paragraph."),
    ("introduction", "Introduction", "section", "Motivate the research problem, identify the precise gap, and state the paper's contributions without overclaiming."),
    ("related_work", "Related Work", "section", "Position the work against the closest research threads and make the distinction from prior work explicit."),
    ("method", "Method", "section", "Explain the proposed approach, its design choices, and enough operational detail for a technical reader to reproduce it."),
    ("experiments", "Experiments", "section", "Describe the evaluation protocol and report only results supported by the uploaded evidence; preserve placeholders for missing measurements."),
    ("discussion", "Discussion", "section", "Interpret the evidence, discuss limitations and failure modes, and separate observations from hypotheses."),
    ("conclusion", "Conclusion", "section", "Close the argument with the supported findings, limitations, and concrete future work."),
)


class OnlineStudioError(RuntimeError):
    """A safe, user-facing online gateway error."""


def _project_zip_bytes(root: Path) -> bytes:
    """Build a bounded project export without following Agent-created symlinks."""
    files: list[Path] = []
    total = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        files.append(path)
        total += path.stat().st_size
        if len(files) > MAX_EXPORT_FILES or total > MAX_EXPORT_BYTES:
            raise OnlineStudioError("项目过大，无法导出 ZIP；请先删除不需要的生成缓存。")
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(root).as_posix())
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
    kind: str = "user"
    created_at: float = field(default_factory=time.time)
    last_access: float = field(default_factory=time.time)


SESSIONS: dict[str, Session] = {}
SESSIONS_LOCK = threading.RLock()
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
    has_structural_reference = any(
        path.as_posix() == "references/structure.txt" for _info, path in accepted
    )
    has_legacy_reference = any(
        path.as_posix().startswith("researcher-profile/fulltext/") and path.suffix.lower() == ".txt"
        for _info, path in accepted
    )
    if not has_structural_reference and not has_legacy_reference:
        raise OnlineStudioError("研究项目 ZIP 必须包含 03 选定的 references/structure.txt。")
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
        "references/structure.txt",
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
    if contract.get("approval_status") != "approved":
        raise OnlineStudioError("03_EXPERIMENT_PLAN.html 尚未批准，请先完成 expplan approval。")
    outline = contract.get("paper_outline")
    artifacts = contract.get("paper_artifacts")
    if not isinstance(outline, list) or not outline:
        raise OnlineStudioError("03 的 paper_outline 为空，无法构建 Paper Studio。")
    if not isinstance(artifacts, list):
        raise OnlineStudioError("03 的 paper_artifacts 格式无效。")
    target = contract.get("target")
    references = contract.get("references")
    structural_reference = (
        references.get("researcher_owned_structure")
        if isinstance(references, dict)
        else None
    )
    if not isinstance(target, dict) or not str(target.get("venue") or "").strip():
        raise OnlineStudioError("03 缺少已确认的 target conference。")
    if not isinstance(structural_reference, dict) or not str(
        structural_reference.get("title") or ""
    ).strip():
        raise OnlineStudioError("03 缺少已确认的结构 reference paper。")
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
            str(Path(__file__).resolve().parents[2] / ".agents/skills/expplan/scripts/validate_experiment_plan.py"),
            "--plan", str(root / "reports/03_EXPERIMENT_PLAN.html"),
        ],
        [
            sys.executable,
            str(Path(__file__).resolve().parents[2] / ".agents/skills/paperwrite/scripts/plan_conformance.py"),
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


def _reference_chunks(source: str, limit: int = 4000) -> list[str]:
    """Normalize one structural paper into bounded prompt excerpts."""
    blocks = [re.sub(r"\s+", " ", item).strip() for item in re.split(r"\n\s*\n", source)]
    blocks = [item for item in blocks if item]
    if len(blocks) <= 1:
        blocks = [re.sub(r"\s+", " ", item).strip() for item in source.splitlines() if item.strip()]
    chunks: list[str] = []
    current = ""
    for block in blocks:
        for start in range(0, len(block), limit):
            piece = block[start : start + limit]
            candidate = f"{current} {piece}".strip()
            if current and len(candidate) > limit:
                chunks.append(current)
                current = piece
            else:
                current = candidate
    if current:
        chunks.append(current)
    return chunks or ["Structural reference text was empty."]


def _matched_reference_line(chunks: list[str], query: str) -> int:
    terms = {
        term
        for term in re.findall(r"[a-z]{4,}", query.lower())
        if term not in {"this", "that", "with", "from", "into", "only", "paper"}
    }
    scores = [sum(chunk.lower().count(term) for term in terms) for chunk in chunks]
    return max(range(len(chunks)), key=lambda index: (scores[index], -index)) + 1


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
            normalized_paragraphs.append(
                {
                    "id": paragraph_id,
                    "purpose": purpose,
                    "artifacts": [str(item) for item in paragraph.get("artifact_refs", [])],
                    "heading": str(paragraph.get("heading") or paragraph.get("subsection") or "").strip(),
                    "heading_style": str(paragraph.get("heading_style") or "").strip(),
                }
            )
        normalized.append(
            {
                "id": section_id,
                "source_id": candidate or section_id,
                "title": title,
                "render": "abstract" if section_id == "abstract" else "section",
                "paragraphs": normalized_paragraphs,
            }
        )
        used.add(section_id)
    return normalized


def _artifact_rows(raw_rows: Any, labels: list[str]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rows = [list(map(str, row)) for row in raw_rows or [] if isinstance(row, list) and row]
    width = max([len(row) for row in rows] + [len(labels), 1])
    headers = [str(item).strip() for item in labels if str(item).strip()]
    if len(headers) < width:
        headers.extend(f"Value {index}" for index in range(len(headers) + 1, width + 1))
    headers = headers[:width]
    keys: list[str] = []
    for index, header in enumerate(headers, 1):
        base = _safe_slug(header, f"value-{index}").replace("-", "_")
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
    contract: dict[str, Any], sections: list[dict[str, Any]]
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
        caption = str(shell.get("caption") or raw.get("caption") or artifact_id).strip()
        title = str(raw.get("title") or caption or artifact_id).strip()
        span = str(raw.get("span") or raw.get("width") or "single-column").lower()
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
        if artifact_id in requirement_artifacts and not records:
            raise OnlineStudioError(
                f"05 中的结果 artifact {artifact_id} 没有可读取的数据行；不会用占位值代替实验结果。"
            )
        metrics["artifacts"][artifact_id] = {
            "rows": records,
            "source": "reports/05_EXP_RESULT.html",
            "contract_verified": True,
        }
        result_path = f"artifacts.{artifact_id}.rows"
        common = {
            "title": title,
            "label": str(raw.get("label") or ("fig:" if contract_kind == "figure" else "tab:") + artifact_id.lower()),
            "width": width,
            "source_sections": [section_id],
            "description": str(raw.get("description") or caption),
            "caption": caption,
            "result_keys": [result_path] if artifact_id in requirement_artifacts else [],
            "related_paragraphs": {section_id: bindings},
        }
        if contract_kind == "table":
            tables[artifact_id] = {
                **common,
                "kind": "table",
                "data_grid": {"type": "records", "path": result_path, "columns": columns},
                "prompt": {
                    "columns": " | ".join(item["label"] for item in columns),
                    "rows": "保持 05 的已验证顺序",
                    "font_size": "small",
                    "best_values": "仅按 03 指定的 metric direction 标记",
                },
            }
            continue
        data_driven = bool(raw.get("data_driven")) or artifact_id in requirement_artifacts
        raw_panels = shell.get("panels")
        if raw_panels is None and isinstance(shell.get("plotting"), dict):
            raw_panels = shell["plotting"].get("panels")
        if isinstance(raw_panels, dict):
            panel_items = [(str(key), value) for key, value in raw_panels.items()]
        elif isinstance(raw_panels, list):
            panel_items = [
                (str(item.get("id") or chr(97 + index)), item)
                for index, item in enumerate(raw_panels)
                if isinstance(item, dict)
            ]
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
            "kind": "data" if data_driven else "mechanism",
            "panels": panels,
            "depends_on_paragraphs": {section_id: bindings},
            "deliverable_stem": _safe_slug(artifact_id),
        }
        if not data_driven:
            figure["generation_requires_paragraphs"] = {section_id: bindings}
        figures[artifact_id] = figure
    return figures, tables, metrics


def _write_workspace(
    root: Path,
    *,
    files: list[tuple[str, str]],
    archive: bytes,
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
    project_name, title = _project_identity(sources["03_EXPERIMENT_PLAN.html"], contract)
    sections = _outline_sections(contract)
    figures, tables, metrics = _artifact_definitions(contract, sections)

    reference_files = [root / "references/structure.txt"]
    if not reference_files[0].is_file():
        reference_files = sorted((root / "researcher-profile/fulltext").rglob("*.txt"))[:1]
    if not reference_files:
        raise OnlineStudioError("研究项目 ZIP 缺少结构参考论文文本。")
    reference = reference_files[0].read_text(encoding="utf-8", errors="replace")
    reference_chunks = _reference_chunks(reference)
    reference_path = paper / "uploaded_sources.txt"
    reference_path.write_text("\n".join(reference_chunks) + "\n", encoding="utf-8")
    section_specs = []
    plan_sections: dict[str, list[dict[str, Any]]] = {}
    outline_lines = [f"Title: {title}", "", "Approved section plan:"]
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
                "file": filename,
                "render": render,
                "result_keys": result_keys,
            }
        )
        plan_sections[section_id] = []
        outline_lines.append(f"{index}. {section_title}")
        for paragraph in section["paragraphs"]:
            reference_line = _matched_reference_line(
                reference_chunks,
                " ".join(
                    [
                        section_title,
                        str(paragraph.get("heading") or ""),
                        paragraph["purpose"],
                    ]
                ),
            )
            planned = {
                "id": paragraph["id"],
                "purpose": paragraph["purpose"],
                "reference_lines": [reference_line, reference_line],
                "artifacts": paragraph["artifacts"],
            }
            if paragraph["heading"]:
                planned["heading"] = paragraph["heading"]
                planned["heading_style"] = paragraph["heading_style"] or "subsection"
            plan_sections[section_id].append(planned)
            outline_lines.append(f"  - {paragraph['id']}: {paragraph['purpose']}")
        placeholder = "% Awaiting paragraph-level drafting in Paper Studio.\n"
        if render != "abstract":
            placeholder = f"\\section{{{_latex_escape(section_title)}}}\n\n" + placeholder
        (sections_dir / filename).write_text(placeholder, encoding="utf-8")

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
    main_tex = "\n".join(
        [
            r"\documentclass[11pt]{article}",
            r"\usepackage[margin=1in]{geometry}",
            r"\usepackage{graphicx}",
            r"\usepackage{booktabs}",
            r"\usepackage{hyperref}",
            f"\\title{{{_latex_escape(title)}}}",
            r"\author{Anonymous Author(s)}",
            r"\date{}",
            r"\begin{document}",
            r"\maketitle",
            *main_inputs,
            r"\bibliographystyle{plain}",
            r"\input{sections/bibliography}",
            r"\end{document}",
            "",
        ]
    )
    (paper / "main.tex").write_text(main_tex, encoding="utf-8")
    (paper / "references.bib").write_text("", encoding="utf-8")
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
    (paper / "outline.txt").write_text("\n".join(outline_lines) + "\n", encoding="utf-8")
    (paper / ".outline-approved").write_text(
        "Inherited from approved reports/03_EXPERIMENT_PLAN.html.\n", encoding="utf-8"
    )
    target = contract.get("target") if isinstance(contract.get("target"), dict) else {}
    references = (
        contract.get("references")
        if isinstance(contract.get("references"), dict)
        else {}
    )
    structural_reference = (
        references.get("researcher_owned_structure")
        if isinstance(references.get("researcher_owned_structure"), dict)
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
            "subtitle": "继承已批准 03、已验证 05 与 results 的隔离在线写作会话",
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
            "reference": "paper/uploaded_sources.txt",
        },
    }
    (paper / "paper_studio.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (paper / "paragraph_plan.json").write_text(
        json.dumps(
            {"reference_file": "paper/uploaded_sources.txt", "sections": plan_sections},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_worker(
    root: Path,
    provider: str,
    model: str,
    api_key: str,
    *,
    demo_mode: bool = False,
) -> tuple[subprocess.Popen[bytes], int]:
    skill_source = (
        Path(__file__).resolve().parents[2] / ".agents/skills/paperstudio"
    )
    if not (skill_source / "SKILL.md").is_file():
        raise OnlineStudioError("线上 Agent 的 Paper Studio 契约尚未安装。")
    skill_target = root / ".agents/skills/paperstudio"
    shutil.copytree(skill_source, skill_target, dirs_exist_ok=True)
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
            "PAPER_STUDIO_ONLINE": "1",
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
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 15
    while time.time() < deadline:
        if process.poll() is not None:
            raise OnlineStudioError("Paper Studio 写作进程启动失败，请检查服务端依赖。")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=0.5):
                return process, port
        except (urllib.error.URLError, TimeoutError, socket.timeout):
            time.sleep(0.1)
    process.terminate()
    raise OnlineStudioError("Paper Studio 写作进程启动超时。")


def create_session(payload: dict[str, Any], *, user_id: str) -> Session:
    with SESSIONS_LOCK:
        active_sessions = sum(
            session.process.poll() is None for session in SESSIONS.values()
        )
    if active_sessions >= MAX_ACTIVE_SESSIONS:
        raise OnlineStudioError("当前在线写作会话已满，请稍后重试。")
    provider = str(payload.get("provider") or "openai").strip().lower()
    if provider not in PROVIDERS:
        raise OnlineStudioError("请选择 OpenAI 或 DeepSeek。")
    api_key = str(payload.get("api_key") or "").strip()
    if len(api_key) < 8 or len(api_key) > 512 or any(character.isspace() for character in api_key):
        raise OnlineStudioError("API key 格式无效。")
    access_token = os.environ.get("ONLINE_STUDIO_ACCESS_TOKEN")
    supplied_access_token = str(payload.get("access_token") or "")
    if access_token and not secrets.compare_digest(access_token, supplied_access_token):
        raise OnlineStudioError("部署访问口令不正确。")
    model = str(payload.get("model") or PROVIDERS[provider][1]).strip()
    if not model or len(model) > 128 or any(character.isspace() for character in model):
        raise OnlineStudioError("模型名称格式无效。")
    files = _decode_html_files(payload.get("files")) if payload.get("files") else []
    archive = _decode_evidence_archive(payload.get("evidence_archive"))
    session_id = secrets.token_urlsafe(32)
    root = (
        DATA_ROOT
        / "projects"
        / hashlib.sha256(user_id.encode("utf-8")).hexdigest()
        / hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    )
    try:
        _write_workspace(
            root,
            files=files,
            archive=archive,
        )
        process, port = _start_worker(root, provider, model, api_key)
    except Exception:
        if root.exists():
            shutil.rmtree(root)
        raise
    session = Session(session_id, user_id, root, provider, model, process, port)
    with SESSIONS_LOCK:
        SESSIONS[session_id] = session
    return session


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
            kind="demo",
        )
        return DEMO_SESSION


def create_demo_copy_session(payload: dict[str, Any], *, user_id: str) -> Session:
    """Create a private writable copy of the completed demo after key entry."""
    with SESSIONS_LOCK:
        active_sessions = sum(
            session.process.poll() is None for session in SESSIONS.values()
        )
    if active_sessions >= MAX_ACTIVE_SESSIONS:
        raise OnlineStudioError("当前在线写作会话已满，请稍后重试。")
    api_key = str(payload.get("api_key") or "").strip()
    if len(api_key) < 8 or len(api_key) > 512 or any(character.isspace() for character in api_key):
        raise OnlineStudioError("API key 格式无效。")
    if not (DEMO_PROJECT / "paper/paper_studio.json").is_file():
        raise OnlineStudioError("完成态 Demo 论文项目尚未安装。")
    session_id = secrets.token_urlsafe(32)
    root = (
        DATA_ROOT
        / "projects"
        / hashlib.sha256(user_id.encode("utf-8")).hexdigest()
        / hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    )
    root.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copytree(DEMO_PROJECT, root)
        process, port = _start_worker(
            root,
            "openai",
            "gpt-5-nano",
            api_key,
            demo_mode=False,
        )
    except Exception:
        if root.exists():
            shutil.rmtree(root)
        raise
    session = Session(
        session_id,
        user_id,
        root,
        "openai",
        "gpt-5-nano",
        process,
        port,
        kind="demo-copy",
    )
    with SESSIONS_LOCK:
        SESSIONS[session_id] = session
    return session


def _session_from_cookie(header: str | None, *, user_id: str) -> Session | None:
    session_id = _cookie_value(header, COOKIE_NAME)
    if session_id is None:
        return None
    with SESSIONS_LOCK:
        session = SESSIONS.get(session_id)
        if (
            session
            and session.user_id == user_id
            and session.process.poll() is None
        ):
            session.last_access = time.time()
            return session
    return None


def _reap_sessions() -> None:
    while True:
        time.sleep(60)
        cutoff = time.time() - SESSION_IDLE_SECONDS
        with SESSIONS_LOCK:
            expired = [sid for sid, session in SESSIONS.items() if session.last_access < cutoff]
            for sid in expired:
                session = SESSIONS.pop(sid)
                if session.process.poll() is None:
                    session.process.terminate()


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
        self.wfile.write(data)

    def _json(self, payload: Any, status: int = 200, *, cookie: str | None = None) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(data)

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

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._bytes((STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
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
        elif path == "/demo-studio":
            if self._require_user():
                self._redirect("/demo-studio/")
        elif path.startswith("/demo-studio/"):
            if not self._require_user():
                return
            try:
                session = demo_session()
                upstream = "/" + path[len("/demo-studio/") :]
                self._proxy(session, upstream, read_only=True)
            except OnlineStudioError as exc:
                self._json({"ok": False, "error": str(exc)}, 503)
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
                    "access_token_required": bool(
                        os.environ.get("ONLINE_STUDIO_ACCESS_TOKEN")
                    ),
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
                    self.headers.get("Cookie"), user_id=user["id"]
                )
                self._json(
                    {
                        "ok": True,
                        "active": session is not None,
                        "provider": session.provider if session else None,
                        "model": session.model if session else None,
                    }
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
                session = self._require_session(user)
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
        elif path == "/api/online/demo-session":
            user = self._require_user()
            if not user:
                return
            try:
                session = create_demo_copy_session(
                    self._read_json(), user_id=user["id"]
                )
                cookie = (
                    f"{COOKIE_NAME}={session.session_id}; Path=/; HttpOnly; SameSite=Strict"
                    + ("; Secure" if _secure_cookies() else "")
                )
                self._json({"ok": True, "redirect": "/studio"}, cookie=cookie)
            except OnlineStudioError as exc:
                self._json({"ok": False, "error": str(exc)}, 400)
        elif path == "/api/auth/logout":
            revoke_auth_session(self.headers.get("Cookie"))
            self._json({"ok": True}, cookie=_auth_cookie("", clear=True))
        elif path == "/api/online/session":
            user = self._require_user()
            if not user:
                return
            try:
                session = create_session(self._read_json(), user_id=user["id"])
                cookie = (
                    f"{COOKIE_NAME}={session.session_id}; Path=/; HttpOnly; SameSite=Strict"
                    + ("; Secure" if _secure_cookies() else "")
                )
                self._json({"ok": True, "redirect": "/studio"}, cookie=cookie)
            except OnlineStudioError as exc:
                self._json({"ok": False, "error": str(exc)}, 400)
        elif path.startswith("/demo-studio/"):
            if self._require_user():
                self._json({"ok": False, "error": "完成态 Demo 为只读展示。"}, 405)
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
        if read_only and self.command not in {"GET", "HEAD"}:
            self._json({"ok": False, "error": "完成态 Demo 为只读展示。"}, 405)
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
        try:
            connection.request(self.command, path, body=body, headers=headers)
            response = connection.getresponse()
            data = response.read()
            self.send_response(response.status)
            for name, value in response.getheaders():
                if name.lower() not in {"connection", "server", "date", "transfer-encoding", "content-length"}:
                    self.send_header(name, value)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)
        except (OSError, http.client.HTTPException):
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
        self.wfile.write(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the private Online Paper Studio gateway.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8876)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        if not os.environ.get("ONLINE_STUDIO_ACCESS_TOKEN") and not _public_registration():
            raise SystemExit(
                "ONLINE_STUDIO_ACCESS_TOKEN or ONLINE_STUDIO_PUBLIC_REGISTRATION=1 "
                "is required for a non-loopback bind."
            )
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
