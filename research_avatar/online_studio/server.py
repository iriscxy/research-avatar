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
COOKIE_NAME = "paper_studio_session"
AUTH_COOKIE_NAME = "online_studio_auth"
GOOGLE_STATE_COOKIE = "online_studio_google_state"
MAX_BODY_BYTES = 24 * 1024 * 1024
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_FILES = 20
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


@dataclass
class Session:
    session_id: str
    user_id: str
    root: Path
    provider: str
    model: str
    process: subprocess.Popen[bytes]
    port: int
    created_at: float = field(default_factory=time.time)
    last_access: float = field(default_factory=time.time)


SESSIONS: dict[str, Session] = {}
SESSIONS_LOCK = threading.RLock()
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


def _project_identity(files: list[tuple[str, str]]) -> tuple[str, str]:
    """Derive safe setup metadata so the upload page does not ask for it twice."""

    supporting = [(name, source) for name, source in files if name.lower() != "profile.html"]
    if not supporting:
        raise OnlineStudioError("除 PROFILE.html 外，还必须上传结果 HTML 或实验计划 HTML。")
    name, source = supporting[0]
    parser = _HTMLIdentity()
    parser.feed(source)
    parser.close()
    candidates = [parser.value("h1"), parser.value("title"), Path(name).stem]
    project_name = next((value for value in candidates if value), "Online Paper")[:160]
    title = next(
        (
            value
            for value in candidates
            if value and value.isascii() and len(value) <= 300
        ),
        "Research Paper Draft",
    )
    return project_name, title


def _write_workspace(
    root: Path,
    *,
    project_name: str,
    title: str,
    files: list[tuple[str, str]],
    sections: list[tuple[str, str, str, str]] | None = None,
) -> None:
    paper = root / "paper"
    sections_dir = paper / "sections"
    sources_dir = root / "sources"
    profile_dir = root / "researcher-profile"
    sections_dir.mkdir(parents=True)
    sources_dir.mkdir(parents=True)
    profile_dir.mkdir(parents=True)
    profile = next(
        (source for name, source in files if name.lower() == "profile.html"), None
    )
    if profile is None:
        raise OnlineStudioError("必须上传名为 PROFILE.html 的研究者画像。")
    (profile_dir / "PROFILE.html").write_text(profile, encoding="utf-8")
    for name, source in files:
        (sources_dir / name).write_text(source, encoding="utf-8")

    reference = _source_text(files)
    reference_path = paper / "uploaded_sources.txt"
    reference_path.write_text(reference + "\n", encoding="utf-8")
    line_count = max(1, len(reference.splitlines()))
    sections = sections or list(DEFAULT_SECTIONS)
    section_specs = []
    plan_sections: dict[str, list[dict[str, Any]]] = {}
    outline_lines = [f"Title: {title}", "", "Approved section plan:"]
    for index, (section_id, section_title, render, purpose) in enumerate(sections, 1):
        filename = f"{section_id}.tex"
        section_specs.append(
            {
                "id": section_id,
                "title": section_title,
                "latex_title": "" if render == "abstract" else section_title,
                "file": filename,
                "render": render,
                "result_keys": [],
            }
        )
        paragraph_id = f"P{index}"
        plan_sections[section_id] = [
            {
                "id": paragraph_id,
                "purpose": purpose,
                "reference_lines": [1, line_count],
                "artifacts": [],
            }
        ]
        outline_lines.append(f"{index}. {section_title}: {purpose}")
        placeholder = "% Awaiting paragraph-level drafting in Paper Studio.\n"
        if render != "abstract":
            placeholder = f"\\section{{{_latex_escape(section_title)}}}\n\n" + placeholder
        (sections_dir / filename).write_text(placeholder, encoding="utf-8")

    main_inputs = []
    for section_id, _title, render, _purpose in sections:
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
    (paper / "metrics.json").write_text(
        json.dumps(
            {"online_sources": {"files": [name for name, _ in files], "user_supplied": True}},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (paper / "working_abstract.txt").write_text(
        "Draft the abstract only from accepted manuscript evidence and uploaded sources.\n",
        encoding="utf-8",
    )
    (paper / "outline.txt").write_text("\n".join(outline_lines) + "\n", encoding="utf-8")
    (paper / ".outline-approved").write_text(
        "Approved by the user in Online Paper Studio setup.\n", encoding="utf-8"
    )
    config = {
        "schema_version": "1.0",
        "project": {
            "id": _safe_slug(project_name) + "-" + secrets.token_hex(4),
            "name": project_name,
            "initial_title": title,
            "eyebrow": "ONLINE PAPER STUDIO",
            "studio_title": "Paper Studio",
            "subtitle": "基于已上传研究资料的隔离在线写作会话",
        },
        "sections": section_specs,
        "batch_writing_order": [item[0] for item in sections],
        "figure_order": [],
        "figures": {},
        "table_order": [],
        "tables": {},
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


def _start_worker(root: Path, provider: str, model: str, api_key: str) -> tuple[subprocess.Popen[bytes], int]:
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
    files = _decode_html_files(payload.get("files"))
    project_name, title = _project_identity(files)
    sections = _validated_sections(payload.get("sections"))
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
            project_name=project_name,
            title=title,
            files=files,
            sections=sections,
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

    def _headers(self, content_type: str, length: int, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
        )
        self.end_headers()

    def _bytes(self, data: bytes, content_type: str, status: int = 200) -> None:
        self._headers(content_type, len(data), status)
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

    def _proxy(self, session: Session, path: str) -> None:
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
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(session.root.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(session.root).as_posix())
        data = stream.getvalue()
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


if __name__ == "__main__":
    main()
