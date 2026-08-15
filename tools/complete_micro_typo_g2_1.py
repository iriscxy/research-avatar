#!/usr/bin/env python3
"""Finalize exactly G2.1 from its deterministic word-level raw result."""

from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from run_plan_progress import goal_command, refresh


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "reports/04_RUN_PLAN.html"
REPORT = ROOT / "reports/05_EXP_RESULT.html"
LEDGER = ROOT / "code/RESULTS_LEDGER.csv"
RAW = ROOT / "results/micro_typo_intent/word_level_results.json"
STATE_RE = re.compile(r'<script type="application/json" id="run-plan-state">(.*?)</script>', re.S)
RESULT_PREFIX = "R-G2.1-"
COMMAND = "python3 -m code.micro_typo.run --stage word-level --config code/micro_typo/config.json"


def digest_paths(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for item in paths:
        digest.update(str(item.relative_to(ROOT)).encode())
        digest.update(item.read_bytes())
    return digest.hexdigest()


def load_state() -> tuple[str, dict]:
    source = PLAN.read_text(encoding="utf-8")
    match = STATE_RE.search(source)
    if not match:
        raise ValueError("run-plan-state missing")
    return source, json.loads(match.group(1))


def result_id(target_id: str) -> str:
    return RESULT_PREFIX + target_id


def append_rows(state: dict, raw: dict, now: str, revision: str) -> list[dict[str, str]]:
    contracts = {
        item["target_id"]: item for item in state["acquisition_contracts"]
        if item["producing_goal"] == "G2.1"
    }
    if set(contracts) != set(raw["paper_targets"]):
        raise ValueError("raw target set differs from G2.1 acquisition contracts")
    with LEDGER.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames
        rows = list(reader)
    if not columns:
        raise ValueError("ledger header missing")
    foreign = [row for row in rows if row["goal_id"] not in {"G1.1", "G2.1"}]
    if foreign:
        raise ValueError("ledger contains a successor goal result")
    existing = {row["result_id"]: row for row in rows}
    appended: list[dict[str, str]] = []
    for target_id in sorted(contracts):
        rid = result_id(target_id)
        if rid in existing:
            appended.append(existing[rid])
            continue
        contract = contracts[target_id]
        value = raw["paper_targets"][target_id]["value"]
        row = {
            "result_id": rid, "goal_id": "G2.1", "artifact_id": contract["artifact_id"],
            "target_id": target_id, "acquisition_id": contract["id"],
            "source_type": "RUN_LOCAL", "status": "REAL", "metric": contract["metric"],
            "value": value, "unit": contract["unit"],
            "dimensions_json": json.dumps(contract["dimensions"], ensure_ascii=False, separators=(",", ":")),
            "raw_artifact": "results/micro_typo_intent/word_level_results.json",
            "raw_locator": contract["raw_locator"], "source_reference": "", "source_locator": "",
            "command": COMMAND,
            "code_files": "code/micro_typo/__init__.py;code/micro_typo/core.py;code/micro_typo/data.py;code/micro_typo/run.py",
            "config_files": "code/micro_typo/config.json;data/micro_typo_intent/manifest.json",
            "environment_files": "code/micro_typo/environment.json", "code_revision": revision,
            "obtained_at": now, "verified_at": now, "verification_status": "VERIFIED",
            "notes": "Two consecutive full G2.1 executions matched byte-for-byte; value recomputed from persisted operands without changing the frozen configuration.",
        }
        with LEDGER.open("a", newline="", encoding="utf-8") as handle:
            csv.DictWriter(handle, fieldnames=columns).writerow(row)
        appended.append(row)
    return appended


def fill_report(rows: list[dict[str, str]], raw_sha: str, now: str) -> None:
    source = REPORT.read_text(encoding="utf-8")
    # The report shell contains an empty payload and the renderer appends the
    # canonical payload block.  Never leave two identical element IDs: browsers
    # and the strict validator would otherwise read the stale empty shell first.
    source = re.sub(
        r'<script type="application/json" id="result-provenance">.*?</script>', "", source,
        flags=re.S,
    )
    source = source.replace('id="result-provenance-index" data-result-id="R-G1.1-A-INF"', 'id="g1-instrumentation-provenance" data-result-id="R-G1.1-A-INF"')
    for row in rows:
        target_id = re.escape(row["target_id"])
        acquisition_id = re.escape(row["acquisition_id"])
        replacement = (
            f'<td data-target-id="{html.escape(row["target_id"])}" '
            f'data-acquisition-id="{html.escape(row["acquisition_id"])}" '
            f'data-result-id="{html.escape(row["result_id"])}">{html.escape(row["value"])}</td>'
        )
        pattern = re.compile(
            rf'<td\b[^>]*data-target-id="{target_id}"[^>]*data-acquisition-id="{acquisition_id}"[^>]*>.*?</td>',
            re.S,
        )
        source, count = pattern.subn(replacement, source, count=1)
        if count != 1:
            raise ValueError(f"result shell missing for {row['target_id']}")
    source = re.sub(
        r'<section data-report-section="artifact-completion"><h2>1\. Artifact Completion</h2>.*?</section>',
        '<section data-report-section="artifact-completion"><h2>1. Artifact Completion</h2><p><strong>0/3 artifacts complete；12/20 paper-facing numeric targets filled.</strong> G2.1 已填 T1 的前两行和 F2 的 word-unigram 系列；Character-trigram 的 8 个目标仍由 G3.1 锁定。</p></section>',
        source, count=1, flags=re.S,
    )
    marker = (
        f'<details class="g2-run-record" data-result-id="R-G2.1-RUN" open><summary>G2.1 run-level verification · PASS</summary>'
        f'<p><strong>Raw:</strong> <code>results/micro_typo_intent/word_level_results.json</code>；SHA-256 <code>{raw_sha}</code>。</p>'
        f'<p><strong>Command:</strong> <code>{html.escape(COMMAND)}</code>（连续执行两次）</p>'
        f'<p><strong>Verified:</strong> {html.escape(now)}；320 条逐记录预测，12 个采集目标。</p></details>'
    )
    if 'class="g2-run-record"' not in source:
        source = source.replace('</section>\n    </main>', marker + '</section>\n    </main>', 1)
    REPORT.write_text(source, encoding="utf-8")


def main() -> None:
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    if raw.get("status") != "PASS" or not all(raw.get("checks", {}).values()):
        raise ValueError("G2.1 raw evidence did not pass")
    if raw.get("methods") != ["majority", "word_unigram_nb"]:
        raise ValueError("G2.1 ran an unauthorized method")
    if len(raw.get("predictions", [])) != 320:
        raise ValueError("G2.1 prediction row count mismatch")
    source, state = load_state()
    if state.get("active_goal") not in ("G2.1", None):
        raise ValueError("G2.1 is not active")
    paths = [
        ROOT / "code/micro_typo/__init__.py", ROOT / "code/micro_typo/core.py",
        ROOT / "code/micro_typo/data.py", ROOT / "code/micro_typo/run.py",
        ROOT / "code/micro_typo/config.json", ROOT / "code/micro_typo/environment.json",
        ROOT / "data/micro_typo_intent/manifest.json", RAW,
    ]
    if not all(item.is_file() for item in paths):
        raise ValueError("required G2.1 path is not reopenable")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    revision = f"git:{head};g2.1-snapshot-sha256:{digest_paths(paths)}"
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    rows = append_rows(state, raw, now, revision)
    if len(rows) != 12:
        raise ValueError("G2.1 must have exactly 12 ledger rows")
    now = rows[0]["verified_at"]
    raw_sha = hashlib.sha256(RAW.read_bytes()).hexdigest()
    fill_report(rows, raw_sha, now)
    subprocess.run([
        "python3", ".agents/skills/runplan/scripts/render_result_provenance.py",
        "--ledger", "code/RESULTS_LEDGER.csv", "--plan", "reports/04_RUN_PLAN.html",
        "--report", "reports/05_EXP_RESULT.html",
    ], cwd=ROOT, check=True)

    source, state = load_state()
    for goal in state["goals"]:
        if goal["id"] == "G2.1":
            goal["status"] = "completed"
            goal["visible_evidence"] = "T1 前两行与 F2 word-unigram 系列共 12 个真实目标已验证；10% word-unigram Robustness Drop 为 0，未支持预期退化。"
            goal["completion_check"] = "两次完整 raw 文件 SHA-256 一致；320 条预测、12 个目标及其 operands 均可重算和重新打开。"
        elif goal["id"] == "G3.1":
            goal["status"] = "proposed"
            goal["goal_command"] = goal_command(goal)
    state["state"] = "awaiting_goal_activation"
    state["active_goal"] = None
    state["proposed_goal_id"] = "G3.1"
    state["completed_results"] = [
        *[item for item in state.get("completed_results", []) if item.get("goal_id") != "G2.1"],
        *[{"result_id": row["result_id"], "goal_id": "G2.1", "artifact_id": row["artifact_id"],
           "target_id": row["target_id"], "acquisition_id": row["acquisition_id"],
           "status": "REAL", "raw_path": row["raw_artifact"], "verified_at": row["verified_at"]}
          for row in rows],
    ]
    state["attempts"] = [
        *[item for item in state.get("attempts", []) if item.get("goal_id") != "G2.1"],
        {"goal_id": "G2.1", "command": COMMAND, "executions": 2,
         "raw_sha256": raw_sha, "payload_sha256": raw["hashes"]["run_1_sha256"], "status": "identical"},
    ]
    if "results/micro_typo_intent/word_level_results.json" not in state["result_paths"]:
        state["result_paths"].append("results/micro_typo_intent/word_level_results.json")
    state["gate_decisions"] = [
        *[item for item in state.get("gate_decisions", []) if item.get("goal_id") != "G2.1"],
        {"goal_id": "G2.1", "decision": "COMPLETE_NEGATIVE_RESULT",
         "reason": "Word-unigram clean and 10% swap Accuracy are both 1.0 on the frozen 40-record test, so the observed 10% Robustness Drop is 0; retain without tuning or replacement.",
         "paper_targets_filled": sorted(raw["paper_targets"])},
    ]
    state["next_authorized_action"] = "Automatically continue to G3.1 after the G2.1 boundary checks pass."
    state["ledger_audit"] = {"status": "PASS_G2.1", "checked_at": now, "ledger": "code/RESULTS_LEDGER.csv"}
    serialized = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
    source = STATE_RE.sub(f'<script type="application/json" id="run-plan-state">{serialized}</script>', source, count=1)
    PLAN.write_text(source, encoding="utf-8")
    refresh(PLAN)
    print(json.dumps({"status": "PASS", "completed_goal": "G2.1", "results": 12, "next_goal": "G3.1"}))


if __name__ == "__main__":
    main()
