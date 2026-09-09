"""Account billing survives temporary project deletion and container replacement.

Local SQLite is an outbox and the local edition's durable ledger. Hosted workers
mirror monotonic per-project totals to D1 before reporting a successful update.
No paper text, email address, or API credential is stored in the usage records.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path
from contextlib import contextmanager


class UsageUnavailable(RuntimeError):
    pass


@contextmanager
def _database(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(root / "usage.sqlite3", timeout=15)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS account_usage (
        account_id TEXT NOT NULL, project_id TEXT NOT NULL,
        amount INTEGER NOT NULL, synced_amount INTEGER NOT NULL DEFAULT -1,
        PRIMARY KEY(account_id, project_id))""")
    try:
        with db:
            yield db
    finally:
        db.close()


def persist_project_cost(root: Path, account: str, project: Path, cost: float) -> None:
    if not math.isfinite(cost) or cost < 0:
        raise UsageUnavailable("Invalid account usage amount.")
    project_id = hashlib.sha256(project.relative_to(root).as_posix().encode()).hexdigest()
    amount = math.ceil(cost * 1_000_000)
    with _database(root) as db:
        db.execute("""INSERT INTO account_usage(account_id, project_id, amount)
            VALUES (?, ?, ?) ON CONFLICT(account_id, project_id) DO UPDATE
            SET amount = MAX(account_usage.amount, excluded.amount)""", (account, project_id, amount))


def _remote(account: str, rows: list[tuple[str, int]]) -> int:
    url = os.environ.get("ONLINE_STUDIO_USAGE_URL", "")
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not url.startswith("https://") or not key:
        raise UsageUnavailable("Account usage service is not configured.")
    request = urllib.request.Request(url, method="POST", headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + key,
    }, data=json.dumps({"account": account, "projects": [
        {"id": project, "amount": amount} for project, amount in rows
    ]}).encode())
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read(65536))
        amount = payload["amount"]
        if not payload.get("ok") or type(amount) is not int or amount < 0:
            raise ValueError("Invalid usage total")
        return amount
    except (OSError, ValueError, KeyError, urllib.error.URLError) as exc:
        # Fail closed and retain the unsent SQLite outbox for a retry.
        raise UsageUnavailable("Account usage service is temporarily unavailable; please retry.") from exc


def account_total(root: Path, account: str) -> float:
    with _database(root) as db:
        local_total = db.execute("SELECT COALESCE(SUM(amount), 0) FROM account_usage WHERE account_id=?", (account,)).fetchone()[0]
        pending = db.execute("SELECT project_id, amount FROM account_usage WHERE account_id=? AND amount>synced_amount", (account,)).fetchall()
    if not os.environ.get("ONLINE_STUDIO_USAGE_URL"):
        return local_total / 1_000_000
    # Even an empty outbox queries D1: a fresh container must see prior charges.
    batches = [pending[index:index + 250] for index in range(0, len(pending), 250)] or [[]]
    for rows in batches:
        remote_total = _remote(account, rows)
        with _database(root) as db:
            db.executemany("UPDATE account_usage SET synced_amount=MAX(synced_amount, ?) WHERE account_id=? AND project_id=?",
                           [(amount, account, project) for project, amount in rows])
    return remote_total / 1_000_000


def persist_ledger_total(path: Path, cost: float) -> None:
    root = Path(os.environ.get("ONLINE_STUDIO_DATA_ROOT", Path.cwd() / ".online-paper-studio")).resolve()
    try:
        parts = path.resolve().relative_to(root).parts
    except ValueError:
        return  # Ordinary local manuscript; no hosted account owns this ledger.
    if len(parts) != 6 or parts[0] != "projects" or parts[3:] != ("paper", ".paper_studio", "api_usage.jsonl"):
        return
    project = root.joinpath(*parts[:3])
    persist_project_cost(root, parts[1], project, cost)
    account_total(root, parts[1])


def ensure_ledger_budget(path: Path) -> None:
    root = Path(os.environ.get("ONLINE_STUDIO_DATA_ROOT", Path.cwd() / ".online-paper-studio")).resolve()
    try:
        parts = path.resolve().relative_to(root).parts
    except ValueError:
        return
    if len(parts) != 6 or parts[0] != "projects":
        return
    cap = float(os.environ.get("ONLINE_STUDIO_SPEND_CAP_RMB", "200"))
    rate = float(os.environ.get("ONLINE_STUDIO_USD_TO_RMB_RATE", "7.2"))
    if account_total(root, parts[1]) * rate >= cap:
        raise UsageUnavailable("Account usage limit reached; export your project to continue locally.")
