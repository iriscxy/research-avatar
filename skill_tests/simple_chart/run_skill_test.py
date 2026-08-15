#!/usr/bin/env python3
"""Run a real, isolated Run Plan lifecycle for one tiny chart-producing goal."""

from __future__ import annotations

import csv
import html
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
CODE = ROOT / "code"
RESULTS = ROOT / "results"
PLAN03 = REPORTS / "03_EXPERIMENT_PLAN.html"
PLAN04 = REPORTS / "04_RUN_PLAN.html"
REPORT05 = REPORTS / "05_EXP_RESULT.html"
LEDGER = CODE / "RESULTS_LEDGER.csv"
sys.path.insert(0, str(REPO))

from tools.run_plan_progress import render_parts_and_goals, refresh  # noqa: E402


COLUMNS = [
    "result_id", "goal_id", "artifact_id", "target_id", "acquisition_id", "source_type",
    "status", "metric", "value", "unit", "dimensions_json", "raw_artifact", "raw_locator",
    "source_reference", "source_locator", "command", "code_files", "config_files",
    "environment_files", "code_revision", "obtained_at", "verified_at",
    "verification_status", "notes",
]
TARGETS = ["f1-curve-00", "f1-curve-01", "f1-curve-02"]


def page_style() -> str:
    return """
    *{box-sizing:border-box}:root{--ink:#172a35;--teal:#087f74;--line:#cbdad9;--wash:#f4f8f7;--muted:#60737e}
    body{margin:0;background:#fff;color:var(--ink);font:17px/1.58 Inter,system-ui,sans-serif}main{max-width:1180px;margin:auto;padding:38px 46px 90px}
    h1{font:700 38px Georgia,serif}h2{font:700 28px Georgia,serif;border-bottom:2px solid var(--teal);padding-bottom:8px;margin-top:42px}
    h3{font-size:21px}.banner{position:sticky;top:0;z-index:100;margin:-38px -46px 24px;padding:13px 46px;background:#8d2d24;color:#fff;font-weight:900;letter-spacing:.04em}
    .table-wrap{overflow:auto}table{width:100%;border-collapse:collapse}th,td{padding:10px;border:1px solid var(--line);text-align:left}thead th{background:#eaf3f1}
    .part{border-left:4px solid var(--teal);padding-left:20px}.goal{padding:8px 18px 18px;border:1px solid var(--line);border-radius:10px}.mapping{color:var(--teal);font-weight:850}
    .goal-results{margin-top:18px;padding:16px;border-top:3px solid var(--teal);background:#f8fbfa}.panel-pair{display:grid;grid-template-columns:1fr 1fr;gap:20px}.result-plot svg{width:100%;height:auto;border:1px solid var(--line);background:#fff}
    .notice{padding:14px 17px;border:2px solid var(--teal);background:var(--wash)}.pill{display:inline-block;padding:3px 8px;border:1px solid var(--teal);border-radius:99px}
    @media(max-width:760px){main{padding:24px 16px}.banner{margin:-24px -16px 20px;padding:12px 16px}.panel-pair{grid-template-columns:1fr}}
    """


def contract() -> dict:
    return {
        "schema_version": "1.1",
        "approval_status": "approved",
        "decision_space_contract": [],
        "implementation_contract": [{
            "method": "Deterministic chart generator",
            "implementation_summary": "Local Python writes three raw points and generates the SVG from those same points.",
        }],
        "paper_artifacts": [{"id": "F1", "kind": "figure", "label": "fig:skill-test-curve"}],
    }


def state(status: str) -> dict:
    acquisitions = []
    for index, target in enumerate(TARGETS):
        acquisitions.append({
            "id": f"A-{target}", "artifact_id": "F1", "target_id": target,
            "source_type": "RUN_LOCAL", "producing_goal": "G1.1",
            "figure_source_cell": True, "metric": "y=x²", "unit": "value",
            "dimensions": {"panel": "curve", "x": index},
            "atomic_or_aggregate": "atomic",
            "raw_output_path": str(RESULTS / "points.json"),
            "raw_locator": f"/points/{index}/y",
        })
    goal = {
        "id": "G1.1", "part_id": "P1", "subpart_id": "G1.1", "stage": "S0",
        "title": "生成三个点并画折线图", "status": status,
        "decision_question": "真实 Run Plan 完成一个 Goal 后，能否立即显示可追溯的数据表和图？",
        "visible_work": "运行本地 Python，保存 x=0,1,2 与 y=x² 的原始 JSON，并由同一数据生成 SVG。",
        "visible_evidence": "在本 Goal 下展示三行源数据表和对应折线图。",
        "completion_check": "三个 locator 均可重开，表中数字与 raw JSON 一致，SVG 的 source target IDs 完整。",
        "artifact_ids": ["F1"], "dependencies": [], "decision_ids": [],
        "outputs": [str(RESULTS / "points.json"), str(RESULTS / "curve.svg")],
        "budget": "<1 CPU-second", "required_checks": ["raw locator", "ledger", "plot source IDs"],
    }
    return {
        "schema_version": "1.0", "source_plan": str(PLAN03),
        "state": "completed" if status == "completed" else "awaiting_goal_activation",
        "proposed_goal_id": None if status == "completed" else "G1.1", "active_goal": None,
        "parts": [{"id": "P1", "title": "Skill-test plotting", "decision": goal["decision_question"], "goals": ["G1.1"]}],
        "goals": [goal], "approved_artifact_ids": ["F1"],
        "artifact_coverage": {"F1": {"goals": ["G1.1"]}},
        "decision_space_contract": [], "implementation_contract": contract()["implementation_contract"],
        "execution_splits": [], "frozen_configuration": {},
        "result_paths": [str(RESULTS / "points.json")] if status == "completed" else [],
        "acquisition_contracts": acquisitions,
    }


def write_plan03() -> None:
    payload = json.dumps(contract(), ensure_ascii=False).replace("<", "\\u003c")
    PLAN03.write_text(f'''<!doctype html><html><head><meta charset="utf-8"><style>{page_style()}</style></head><body><main>
    <div class="banner">SKILL-TEST — fabricated data, NOT a scientific result</div><h1>Simple Chart Experiment Plan</h1>
    <section data-report-section="target-and-references"><h2>1. Target Conference and Reference Papers</h2><p>Internal workflow test; no scientific submission or literature claim.</p></section>
    <section data-report-section="projected-paper"><h2>2. Projected Paper</h2>
      <section data-report-subsection="projected-title-abstract"><h3>2.1 Projected Title and Abstract</h3><p>Test whether one deterministic local run fills a traceable chart.</p></section>
      <section data-report-subsection="figure-table-count"><h3>2.2 Figure/Table Count</h3><p>One figure with one curve panel and its adjacent three-row numeric source table.</p></section>
      <section data-report-subsection="paragraph-blueprint"><h3>2.3 Paragraph Blueprint and Evidence Shells</h3><p>One paragraph points to F1.</p><table><tr><th>x</th><th>y=x²</th></tr><tr><td>0</td><td>[PENDING]</td></tr><tr><td>1</td><td>[PENDING]</td></tr><tr><td>2</td><td>[PENDING]</td></tr></table></section>
      <section data-report-subsection="claim-falsifier-evidence"><h3>2.4 Claim–Falsifier–Evidence</h3><p>Fail if any displayed value cannot be reopened from raw JSON.</p></section>
      <section data-report-subsection="implementation-plan"><h3>2.5 Implementation Plan</h3><p>Local deterministic Python.</p></section>
      <section data-report-subsection="budget-decision-criteria"><h3>2.6 Budget and Decision Criteria</h3><p>Under one CPU-second; pass only on exact validation.</p></section>
    </section>
    <section data-report-section="approval"><h2>3. Approval</h2><p>Approved only as an explicit fabricated skill test.</p></section>
    <script type="application/json" id="experiment-plan-contract">{payload}</script></main></body></html>''', encoding="utf-8")


def write_plan04(plan_state: dict) -> None:
    implementation = plan_state["implementation_contract"][0]
    parts = render_parts_and_goals(plan_state)
    payload = json.dumps(plan_state, ensure_ascii=False).replace("<", "\\u003c")
    PLAN04.write_text(f'''<!doctype html><html><head><meta charset="utf-8"><style>{page_style()}</style></head><body><main>
    <div class="banner">SKILL-TEST — fabricated data, NOT a scientific result</div><h1>Simple Chart Run Plan</h1>
    <section data-report-section="execution-estimate"><h2>1. Execution Estimate</h2><p class="notice"><strong>图表覆盖：1/1</strong> — F1 · 1 Goal · CPU only · under one second.</p></section>
    <section data-report-section="implementation-sources"><h2>2. Implementation Sources</h2><table><tr><th>Method</th><th>How it is implemented</th></tr><tr><td>{html.escape(implementation['method'])}</td><td>{html.escape(implementation['implementation_summary'])}</td></tr></table></section>
    <section data-report-section="artifact-coverage"><h2>3. Figure/Table Coverage</h2><p>F1 — Goal G1.1.</p></section>{parts}
    <script type="application/json" id="run-plan-state">{payload}</script></main></body></html>''', encoding="utf-8")


def write_report05() -> None:
    raw = json.loads((RESULTS / "points.json").read_text(encoding="utf-8"))
    rows = []
    for index, point in enumerate(raw["points"]):
        rows.append(f'<tr><th>{point["x"]}</th><td data-target-id="{TARGETS[index]}" data-acquisition-id="A-{TARGETS[index]}" data-result-id="R-{index + 1}">{point["y"]}</td></tr>')
    svg = (RESULTS / "curve.svg").read_text(encoding="utf-8")
    ids = " ".join(TARGETS)
    REPORT05.write_text(f'''<!doctype html><html><head><meta charset="utf-8"><style>{page_style()}</style></head><body><main>
    <div class="banner">SKILL-TEST — fabricated data, NOT a scientific result</div><h1>Simple Chart Results</h1>
    <section data-report-section="artifact-completion"><h2>1. Artifact Completion</h2><p>F1 FILLED · 3/3 verified.</p></section>
    <section data-report-section="paper-artifacts"><h2>2. Paper Tables and Figures</h2><section class="figure-result" data-artifact-id="F1" data-source-target-ids="{ids}"><h3>F1 · y=x²</h3><div class="result-panel"><h4>curve</h4><div class="panel-pair"><div class="table-wrap"><table><thead><tr><th>x</th><th>y</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div><figure class="result-plot" data-generated-from-target-ids="{ids}">{svg}<figcaption>Generated from the adjacent three verified cells.</figcaption></figure></div></div></section></section>
    <section data-report-section="generation-process"><h2>3. 生成过程</h2><p>由 provenance renderer 填充。</p></section></main></body></html>''', encoding="utf-8")


def write_ledger() -> None:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    command = f"python3 {CODE / 'run_chart.py'}"
    with LEDGER.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for index, value in enumerate((0, 1, 4)):
            row = {column: "" for column in COLUMNS}
            row.update({
                "result_id": f"R-{index + 1}", "goal_id": "G1.1", "artifact_id": "F1",
                "target_id": TARGETS[index], "acquisition_id": f"A-{TARGETS[index]}",
                "source_type": "RUN_LOCAL", "status": "REAL", "metric": "y=x²",
                "value": str(value), "unit": "value", "dimensions_json": json.dumps({"x": index}),
                "raw_artifact": str(RESULTS / "points.json"), "raw_locator": f"/points/{index}/y",
                "command": command, "code_files": str(CODE / "run_chart.py"),
                "environment_files": str(RESULTS / "environment.json"), "code_revision": "SKILL-TEST",
                "obtained_at": timestamp, "verified_at": timestamp,
                "verification_status": "VERIFIED", "notes": "fabricated deterministic skill-test datum",
            })
            writer.writerow(row)


def run() -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    write_plan03()
    write_plan04(state("proposed"))
    subprocess.run([sys.executable, str(CODE / "run_chart.py")], check=True)
    write_ledger()
    completed = state("completed")
    write_plan04(completed)
    write_report05()
    subprocess.run([
        sys.executable, str(REPO / ".agents/skills/runplan/scripts/render_result_provenance.py"),
        "--ledger", str(LEDGER), "--plan", str(PLAN04), "--report", str(REPORT05),
    ], check=True)
    refresh(PLAN04)
    subprocess.run([
        sys.executable, str(REPO / ".agents/skills/runplan/scripts/validate_results_ledger.py"),
        "--ledger", str(LEDGER), "--plan", str(PLAN04), "--report", str(REPORT05),
        "--goal", "G1.1", "--strict-report",
    ], check=True)
    print(json.dumps({"status": "PASS", "run_plan": str(PLAN04), "result_rows": 3}, ensure_ascii=False))


if __name__ == "__main__":
    run()
