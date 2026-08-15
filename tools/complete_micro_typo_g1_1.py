#!/usr/bin/env python3
"""Finalize only G1.1 from verified instrumentation evidence."""

from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from run_plan_progress import render_parts_and_goals


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "reports/04_RUN_PLAN.html"
REPORT = ROOT / "reports/05_EXP_RESULT.html"
LEDGER = ROOT / "code/RESULTS_LEDGER.csv"
RAW = ROOT / "results/micro_typo_intent/instrumentation.json"
STATE_RE = re.compile(r'<script type="application/json" id="run-plan-state">(.*?)</script>', re.S)
PARTS_RE = re.compile(r'<section data-report-section="parts-and-goals">.*?</section>', re.S)
RESULT_ID = "R-G1.1-A-INF"
COMMAND = "python3 -m code.micro_typo.run --stage instrumentation --config code/micro_typo/config.json"


def digest_paths(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def load_state(source: str) -> dict:
    match = STATE_RE.search(source)
    if not match:
        raise ValueError("run plan state missing")
    return json.loads(match.group(1))


def append_ledger(now: str, revision: str) -> dict[str, str]:
    with LEDGER.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames
        rows = list(reader)
    if not columns:
        raise ValueError("ledger header missing")
    existing = next((row for row in rows if row["result_id"] == RESULT_ID), None)
    if existing:
        return existing
    if rows:
        raise ValueError("G1.1 finalizer expected an empty ledger")
    row = {
        "result_id": RESULT_ID, "goal_id": "G1.1", "artifact_id": "", "target_id": "",
        "acquisition_id": "A-INF-G1.1", "source_type": "RUN_LOCAL", "status": "REAL",
        "metric": "instrumentation smoke reproducibility", "value": "PASS", "unit": "status",
        "dimensions_json": json.dumps({"scope": "tiny internal smoke slice"}, separators=(",", ":")),
        "raw_artifact": "results/micro_typo_intent/instrumentation.json", "raw_locator": "/status",
        "source_reference": "", "source_locator": "", "command": COMMAND,
        "code_files": "code/micro_typo/__init__.py;code/micro_typo/core.py;code/micro_typo/data.py;code/micro_typo/run.py",
        "config_files": "code/micro_typo/config.json;data/micro_typo_intent/manifest.json",
        "environment_files": "code/micro_typo/environment.json",
        "code_revision": revision, "obtained_at": now, "verified_at": now,
        "verification_status": "VERIFIED",
        "notes": "Two consecutive identical CLI executions produced the same raw SHA-256; no T1/F2 target was run or filled.",
    }
    with LEDGER.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writerow(row)
    return row


def update_report(raw: dict, now: str) -> None:
    source = REPORT.read_text(encoding="utf-8")
    if any(
        re.search(rf'data-target-id="{prefix}[^\"]*"[^>]*>\s*(?!\[PENDING\])', source)
        for prefix in ("t1-", "f2-")
    ):
        raise ValueError("paper-facing cell changed during G1.1")
    details = (
        f'<details id="result-provenance-index" data-result-id="{RESULT_ID}" open>'
        '<summary>A-INF-G1.1 · instrumentation smoke · PASS</summary>'
        f'<p><strong>Raw:</strong> <a href="../results/micro_typo_intent/instrumentation.json">results/micro_typo_intent/instrumentation.json</a> · <code>/status</code></p>'
        f'<p><strong>Command:</strong> <code>{html.escape(COMMAND)}</code>（连续执行两次）</p>'
        f'<p><strong>Verified:</strong> {html.escape(now)}；raw SHA-256 <code>{html.escape(hashlib.sha256(RAW.read_bytes()).hexdigest())}</code>。</p>'
        '<p><strong>Boundary:</strong> <code>paper_facing_targets_filled=[]</code>；T1 与 F2 仍全部 PENDING。</p>'
        '</details>'
    )
    source, count = re.subn(
        r'<details id="result-provenance-index".*?</details>', details, source, count=1, flags=re.S
    )
    if count != 1:
        raise ValueError("results provenance shell missing")
    REPORT.write_text(source, encoding="utf-8")


def main() -> None:
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    if raw.get("status") != "PASS" or raw.get("paper_facing_targets_filled") != []:
        raise ValueError("instrumentation evidence is not a passing non-paper result")
    if not all(raw.get("checks", {}).values()):
        raise ValueError("instrumentation check failed")
    paths = [
        ROOT / "code/micro_typo/__init__.py", ROOT / "code/micro_typo/core.py",
        ROOT / "code/micro_typo/data.py", ROOT / "code/micro_typo/run.py",
        ROOT / "code/micro_typo/config.json", ROOT / "code/micro_typo/environment.json",
        ROOT / "data/micro_typo_intent/manifest.json", RAW,
    ]
    if not all(path.is_file() for path in paths):
        raise ValueError("required G1.1 path is not reopenable")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    revision = f"git:{head};g1.1-snapshot-sha256:{digest_paths(paths)}"
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    ledger_row = append_ledger(now, revision)
    now = ledger_row["verified_at"]
    revision = ledger_row["code_revision"]

    source = PLAN.read_text(encoding="utf-8")
    state = load_state(source)
    for goal in state["goals"]:
        if goal["id"] == "G1.1":
            goal["status"] = "completed"
            goal["goal_command"] = goal.get("goal_command", "").replace(
                "828f4a3c20fba50712b2e7eb6a42486e9590d206",
                "828f8093932c8fe6ca7936c3d2e52903b1c523de",
            )
            goal["visible_evidence"] = "A-INF-G1.1 已验证 PASS；F1 保持为非实验概念图，T1/F2 未运行。"
            goal["completion_check"] = "两次 CLI 输出的完整 raw SHA-256 一致；内部两次 smoke hash 一致，所有来源、配置和结果路径均可重新打开。"
        elif goal["id"] == "G2.1":
            goal["status"] = "proposed"
    state["state"] = "awaiting_goal_activation"
    state["proposed_goal_id"] = "G2.1"
    state["active_goal"] = None
    state["completed_results"] = [{
        "result_id": RESULT_ID, "goal_id": "G1.1", "acquisition_id": "A-INF-G1.1",
        "status": "PASS", "raw_path": "results/micro_typo_intent/instrumentation.json",
        "raw_sha256": hashlib.sha256(RAW.read_bytes()).hexdigest(), "verified_at": now,
    }]
    state["attempts"] = [{
        "goal_id": "G1.1", "command": COMMAND, "executions": 2,
        "raw_sha256": hashlib.sha256(RAW.read_bytes()).hexdigest(), "status": "identical",
    }]
    state["raw_paths"] = [
        "data/micro_typo_intent/source/data_full.json", "data/micro_typo_intent/source/LICENSE",
        "data/micro_typo_intent/source/README.md", "data/micro_typo_intent/manifest.json",
    ]
    state["result_paths"] = ["results/micro_typo_intent/instrumentation.json"]
    state["gate_decisions"] = [{
        "goal_id": "G1.1", "decision": "PASS", "reason": "all deterministic instrumentation checks passed",
        "paper_targets_filled": [],
    }]
    correction = {
        "at": "2026-08-14",
        "reason": "Corrected generated G1.1 revision 828f4a3c20fba50712b2e7eb6a42486e9590d206, which GitHub rejects as not our ref, to the approved 03 contract revision 828f8093932c8fe6ca7936c3d2e52903b1c523de.",
        "scope_change": "none; source repository, dataset file, labels, counts, and experiment design are unchanged",
    }
    if correction not in state["amendments"]:
        state["amendments"].append(correction)
    state["next_authorized_action"] = "Researcher may manually activate exactly G2.1 using the nested /goal command."
    state["ledger_audit"] = {"status": "PASS_G1.1", "checked_at": now, "ledger": "code/RESULTS_LEDGER.csv"}
    rendered = render_parts_and_goals(state)
    source = PARTS_RE.sub(rendered, source, count=1)
    state_json = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
    source = STATE_RE.sub(
        f'<script type="application/json" id="run-plan-state">{state_json}</script>', source, count=1
    )
    PLAN.write_text(source, encoding="utf-8")
    update_report(raw, now)
    print(json.dumps({"status": "PASS", "completed_goal": "G1.1", "next_goal": "G2.1", "result_id": RESULT_ID}))


if __name__ == "__main__":
    main()
