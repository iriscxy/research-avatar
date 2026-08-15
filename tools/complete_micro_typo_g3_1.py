#!/usr/bin/env python3
"""Finalize G3.1, complete T1/F2, and render the real ledger-backed plot."""

from __future__ import annotations

import base64
import csv
import hashlib
import html
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from run_plan_progress import refresh


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "reports/04_RUN_PLAN.html"
REPORT = ROOT / "reports/05_EXP_RESULT.html"
LEDGER = ROOT / "code/RESULTS_LEDGER.csv"
RAW = ROOT / "results/micro_typo_intent/character_results.json"
FIXTURE = ROOT / "paper/figsrc/micro_typo_intent/result_fixture.json"
FIG_PDF = ROOT / "paper/fig/micro_typo_intent/results/F2_typo_sensitivity.pdf"
FIG_PNG = ROOT / "paper/fig/micro_typo_intent/results/F2_typo_sensitivity.png"
FIG_ENV = ROOT / "paper/figsrc/micro_typo_intent/result_figure_environment.json"
STATE_RE = re.compile(r'<script type="application/json" id="run-plan-state">(.*?)</script>', re.S)
RESULT_PREFIX = "R-G3.1-"
COMMAND = "python3 -m code.micro_typo.run --stage character --config code/micro_typo/config.json"


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
        if item["producing_goal"] == "G3.1"
    }
    if set(contracts) != set(raw["paper_targets"]):
        raise ValueError("raw target set differs from G3.1 acquisition contracts")
    with LEDGER.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames
        rows = list(reader)
    if not columns:
        raise ValueError("ledger header missing")
    if any(row["goal_id"] not in {"G1.1", "G2.1", "G3.1"} for row in rows):
        raise ValueError("ledger contains an unauthorized goal")
    existing = {row["result_id"]: row for row in rows}
    recorded: list[dict[str, str]] = []
    for target_id in sorted(contracts):
        rid = result_id(target_id)
        if rid in existing:
            recorded.append(existing[rid])
            continue
        contract = contracts[target_id]
        row = {
            "result_id": rid, "goal_id": "G3.1", "artifact_id": contract["artifact_id"],
            "target_id": target_id, "acquisition_id": contract["id"],
            "source_type": "RUN_LOCAL", "status": "REAL", "metric": contract["metric"],
            "value": raw["paper_targets"][target_id]["value"], "unit": contract["unit"],
            "dimensions_json": json.dumps(contract["dimensions"], ensure_ascii=False, separators=(",", ":")),
            "raw_artifact": "results/micro_typo_intent/character_results.json",
            "raw_locator": contract["raw_locator"], "source_reference": "", "source_locator": "",
            "command": COMMAND,
            "code_files": "code/micro_typo/__init__.py;code/micro_typo/core.py;code/micro_typo/data.py;code/micro_typo/run.py",
            "config_files": "code/micro_typo/config.json;data/micro_typo_intent/manifest.json",
            "environment_files": "code/micro_typo/environment.json", "code_revision": revision,
            "obtained_at": now, "verified_at": now, "verification_status": "VERIFIED",
            "notes": "Two consecutive full G3.1 executions matched byte-for-byte; value recomputed from persisted operands under the frozen G1.1/G2.1 inputs.",
        }
        with LEDGER.open("a", newline="", encoding="utf-8") as handle:
            csv.DictWriter(handle, fieldnames=columns).writerow(row)
        recorded.append(row)
    return recorded


def all_ledger_rows() -> list[dict[str, str]]:
    with LEDGER.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build_real_fixture() -> dict:
    rows = all_ledger_rows()
    by_target = {row["target_id"]: row for row in rows if row["artifact_id"] == "F2"}
    target_order = [
        f"f2-typo_sensitivity-{rate:02d}-{series:02d}"
        for rate in range(4) for series in range(2)
    ]
    if set(by_target) != set(target_order):
        raise ValueError("F2 requires exactly eight verified ledger source cells")
    if any(by_target[target]["verification_status"] != "VERIFIED" for target in target_order):
        raise ValueError("F2 source cell is not verified")
    fixture = {
        "synthetic": False,
        "source": "code/RESULTS_LEDGER.csv",
        "source_result_ids": [by_target[target]["result_id"] for target in target_order],
        "traceable_results": {
            "F2.typo_sensitivity": {
                "x": [0.0, 0.05, 0.1, 0.15],
                "series": {
                    "Word-unigram Naive Bayes": [float(by_target[f"f2-typo_sensitivity-{rate:02d}-00"]["value"]) for rate in range(4)],
                    "Character-trigram Naive Bayes": [float(by_target[f"f2-typo_sensitivity-{rate:02d}-01"]["value"]) for rate in range(4)],
                },
            }
        },
    }
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return fixture


def render_figure() -> None:
    candidates = [
        shutil.which("python"),
        shutil.which("python3"),
        "/Users/xiuying.chen/miniconda3/bin/python3.12",
    ]
    plot_python = None
    probe = None
    for candidate in dict.fromkeys(item for item in candidates if item):
        attempt = subprocess.run(
            [candidate, "-c", "import json,sys,matplotlib; print(json.dumps({'python':sys.version.split()[0],'matplotlib':matplotlib.__version__}))"],
            cwd=ROOT, capture_output=True, text=True,
        )
        if attempt.returncode == 0:
            plot_python = candidate
            probe = attempt
            break
    if not plot_python or probe is None:
        raise ValueError("no Python interpreter with the approved plotting dependency is available")
    figure_environment = json.loads(probe.stdout)
    if not figure_environment["matplotlib"].startswith(("3.9.", "3.10.")):
        raise ValueError("matplotlib does not satisfy the approved >=3.9,<4 range")
    figure_environment["interpreter"] = plot_python
    figure_environment["role"] = "artifact rendering only; experiment metrics use the frozen standard-library environment"
    FIG_ENV.write_text(json.dumps(figure_environment, indent=2) + "\n", encoding="utf-8")
    subprocess.run([
        plot_python, "paper/fig/make_figs.py",
        "--schema", "paper/figsrc/micro_typo_intent/figure_schema.json",
        "--figure", "F2", "--panel", "typo_sensitivity",
        "--metrics", str(FIXTURE.relative_to(ROOT)),
        "--pdf", str(FIG_PDF.relative_to(ROOT)), "--png", str(FIG_PNG.relative_to(ROOT)),
    ], cwd=ROOT, check=True)
    if not FIG_PDF.is_file() or not FIG_PNG.is_file() or FIG_PNG.stat().st_size < 10_000:
        raise ValueError("real F2 figure was not rendered correctly")


def fill_report(rows: list[dict[str, str]], raw_sha: str, now: str) -> None:
    source = REPORT.read_text(encoding="utf-8")
    source = re.sub(
        r'<script type="application/json" id="result-provenance">.*?</script>', "", source,
        flags=re.S,
    )
    for row in rows:
        pattern = re.compile(
            rf'<td\b[^>]*data-target-id="{re.escape(row["target_id"])}"[^>]*'
            rf'data-acquisition-id="{re.escape(row["acquisition_id"])}"[^>]*>.*?</td>', re.S,
        )
        replacement = (
            f'<td data-target-id="{html.escape(row["target_id"])}" '
            f'data-acquisition-id="{html.escape(row["acquisition_id"])}" '
            f'data-result-id="{html.escape(row["result_id"])}">{html.escape(row["value"])}</td>'
        )
        source, count = pattern.subn(replacement, source, count=1)
        if count != 1:
            raise ValueError(f"result shell missing for {row['target_id']}")
    source = re.sub(
        r'<section data-report-section="artifact-completion"><h2>1\. Artifact Completion</h2>.*?</section>',
        '<section data-report-section="artifact-completion"><h2>1. Artifact Completion</h2><p><strong>2/3 artifacts complete；20/20 paper-facing numeric targets filled.</strong> T1 与 F2 已由真实 ledger 数字完成；F1 仍是后续 paperwrite/figureppt 绘制的非实验概念图。</p></section>',
        source, count=1, flags=re.S,
    )
    all_f2_targets = " ".join(
        f"f2-typo_sensitivity-{rate:02d}-{series:02d}"
        for rate in range(4) for series in range(2)
    )
    encoded = base64.b64encode(FIG_PNG.read_bytes()).decode("ascii")
    plot = (
        f'<figure class="result-plot" data-generated-from-target-ids="{all_f2_targets}">'
        f'<img alt="Real F2 typo-sensitivity result" src="data:image/png;base64,{encoded}" style="display:block;width:100%;height:auto">'
        '<figcaption>REAL RESULT · generated only from the adjacent eight verified ledger cells.</figcaption></figure>'
    )
    source, count = re.subn(r'<div class="empty-plot">.*?</div>', plot, source, count=1, flags=re.S)
    if count != 1 and 'class="result-plot"' not in source:
        raise ValueError("F2 plot shell missing")
    marker = (
        f'<details class="g3-run-record" data-result-id="R-G3.1-RUN" open><summary>G3.1 run-level verification · PASS</summary>'
        f'<p><strong>Raw:</strong> <code>results/micro_typo_intent/character_results.json</code>；SHA-256 <code>{raw_sha}</code>。</p>'
        f'<p><strong>Command:</strong> <code>{html.escape(COMMAND)}</code>（连续执行两次）</p>'
        f'<p><strong>Verified:</strong> {html.escape(now)}；160 条逐记录预测，8 个新采集目标；C2 = FALSIFIED。</p></details>'
    )
    if 'class="g3-run-record"' not in source:
        source = source.replace('</section>\n    </main>', marker + '</section>\n    </main>', 1)
    REPORT.write_text(source, encoding="utf-8")


def main() -> None:
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    if raw.get("status") != "PASS" or not all(raw.get("checks", {}).values()):
        raise ValueError("G3.1 raw evidence did not pass")
    if raw.get("methods") != ["character_trigram_nb"] or len(raw.get("predictions", [])) != 160:
        raise ValueError("G3.1 method or prediction count is unauthorized")
    source, state = load_state()
    if state.get("active_goal") not in ("G3.1", None):
        raise ValueError("G3.1 is not active")
    paths = [
        ROOT / "code/micro_typo/__init__.py", ROOT / "code/micro_typo/core.py",
        ROOT / "code/micro_typo/data.py", ROOT / "code/micro_typo/run.py",
        ROOT / "code/micro_typo/config.json", ROOT / "code/micro_typo/environment.json",
        ROOT / "data/micro_typo_intent/manifest.json", RAW,
    ]
    if not all(item.is_file() for item in paths):
        raise ValueError("required G3.1 path is not reopenable")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    revision = f"git:{head};g3.1-snapshot-sha256:{digest_paths(paths)}"
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    rows = append_rows(state, raw, now, revision)
    if len(rows) != 8:
        raise ValueError("G3.1 must have exactly eight ledger rows")
    now = rows[0]["verified_at"]
    fixture = build_real_fixture()
    if fixture.get("synthetic") is not False:
        raise ValueError("result fixture must not be synthetic")
    render_figure()
    raw_sha = hashlib.sha256(RAW.read_bytes()).hexdigest()
    fill_report(rows, raw_sha, now)
    subprocess.run([
        "python3", ".agents/skills/runplan/scripts/render_result_provenance.py",
        "--ledger", "code/RESULTS_LEDGER.csv", "--plan", "reports/04_RUN_PLAN.html",
        "--report", "reports/05_EXP_RESULT.html",
    ], cwd=ROOT, check=True)

    source, state = load_state()
    for goal in state["goals"]:
        if goal["id"] == "G3.1":
            goal["status"] = "completed"
            goal["visible_evidence"] = "T1 最后一行和 F2 character-trigram 系列共 8 个真实目标已验证；F2 已从全部 8 个源格生成真实图。C2 因两种方法的 10% Drop 均为 0 而被否证。"
            goal["completion_check"] = "两次完整 raw SHA-256 一致；160 条预测和 8 个目标可重算；完整 T1、F2 源表、真实 PNG/PDF 与 provenance 均可重新打开。"
    state["state"] = "completed"
    state["active_goal"] = None
    state["proposed_goal_id"] = None
    state["completed_results"] = [
        *[item for item in state.get("completed_results", []) if item.get("goal_id") != "G3.1"],
        *[{"result_id": row["result_id"], "goal_id": "G3.1", "artifact_id": row["artifact_id"],
           "target_id": row["target_id"], "acquisition_id": row["acquisition_id"],
           "status": "REAL", "raw_path": row["raw_artifact"], "verified_at": row["verified_at"]}
          for row in rows],
    ]
    state["attempts"] = [
        *[item for item in state.get("attempts", []) if item.get("goal_id") != "G3.1"],
        {"goal_id": "G3.1", "command": COMMAND, "executions": 2,
         "raw_sha256": raw_sha, "payload_sha256": raw["hashes"]["run_1_sha256"], "status": "identical"},
    ]
    if "results/micro_typo_intent/character_results.json" not in state["result_paths"]:
        state["result_paths"].append("results/micro_typo_intent/character_results.json")
    state["artifact_paths"] = [
        "paper/figsrc/micro_typo_intent/result_fixture.json",
        "paper/figsrc/micro_typo_intent/result_figure_environment.json",
        "paper/fig/micro_typo_intent/results/F2_typo_sensitivity.pdf",
        "paper/fig/micro_typo_intent/results/F2_typo_sensitivity.png",
    ]
    state["gate_decisions"] = [
        *[item for item in state.get("gate_decisions", []) if item.get("goal_id") != "G3.1"],
        {"goal_id": "G3.1", "decision": raw["claim_adjudication"]["verdict"],
         "claim_id": "C2", "reason": "Character and word models both have 10% Robustness Drop 0; character does not achieve the strictly lower drop required by C2, although its clean Accuracy remains within the 0.10 boundary.",
         "paper_targets_filled": sorted(raw["paper_targets"])},
    ]
    state["next_authorized_action"] = "No successor goal: the approved three-goal run plan is complete."
    state["ledger_audit"] = {"status": "PASS_G3.1", "checked_at": now, "ledger": "code/RESULTS_LEDGER.csv"}
    serialized = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
    source = STATE_RE.sub(f'<script type="application/json" id="run-plan-state">{serialized}</script>', source, count=1)
    PLAN.write_text(source, encoding="utf-8")
    refresh(PLAN)
    print(json.dumps({"status": "PASS", "completed_goal": "G3.1", "results": 8, "claim_C2": raw["claim_adjudication"]["verdict"], "next_goal": None}))


if __name__ == "__main__":
    main()
