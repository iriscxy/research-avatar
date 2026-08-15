#!/usr/bin/env python3
"""Build the approved micro typo-classification Run Plan and empty result backend."""

from __future__ import annotations

import csv
import hashlib
import html
import json
import re
from pathlib import Path

from run_plan_progress import render_parts_and_goals


ROOT = Path(__file__).resolve().parents[1]
EXPPLAN = ROOT / "reports/03_EXPERIMENT_PLAN.html"
RUNPLAN = ROOT / "reports/04_RUN_PLAN.html"
RESULTS = ROOT / "reports/05_EXP_RESULT.html"
LEDGER = ROOT / "code/RESULTS_LEDGER.csv"
SCHEMA = ROOT / "paper/figsrc/micro_typo_intent/figure_schema.json"
CONTRACT_RE = re.compile(
    r'<script type="application/json" id="experiment-plan-contract">(.*?)</script>', re.S
)
LEDGER_COLUMNS = [
    "result_id", "goal_id", "artifact_id", "target_id", "acquisition_id", "source_type",
    "status", "metric", "value", "unit", "dimensions_json", "raw_artifact", "raw_locator",
    "source_reference", "source_locator", "command", "code_files", "config_files",
    "environment_files", "code_revision", "obtained_at", "verified_at",
    "verification_status", "notes",
]


def load_contract() -> dict:
    source = EXPPLAN.read_text(encoding="utf-8")
    match = CONTRACT_RE.search(source)
    if not match:
        raise ValueError("approved experiment-plan contract not found")
    contract = json.loads(match.group(1))
    if contract.get("approval_status") != "approved":
        raise ValueError("experiment plan is not approved")
    return contract


def goal(
    gid: str, part: str, stage: str, title: str, question: str, work: str,
    evidence: str, check: str, artifacts: list[str], dependencies: list[str],
    decisions: list[str], outputs: list[str], experiment_ids: list[str], command: str = "",
) -> dict:
    return {
        "id": gid, "part_id": part, "subpart_id": gid, "stage": stage, "title": title,
        "status": "proposed" if gid == "G1.1" else "locked",
        "decision_question": question, "visible_work": work, "visible_evidence": evidence,
        "completion_check": check, "artifact_ids": artifacts, "dependencies": dependencies,
        "decision_ids": decisions, "budget": "Local CPU; expected under one minute after setup.",
        "experiment_ids": experiment_ids,
        "inputs": ["reports/03_EXPERIMENT_PLAN.html", "official CLINC150 JSON at approved revision"],
        "outputs": outputs,
        "authorized_runs": "Only the approved four labels, fixed rates, seed, methods, and metrics.",
        "required_checks": ["schema validation", "raw-path resolution", "identical rerun check"],
        "falsifier": "Apply the claim-specific falsifier from the approved experiment contract.",
        "successor_branches": ["continue", "repair within approved contract", "stop and amend expplan"],
        "exclusions": ["no tuning", "no extra data/method/metric", "no successor execution"],
        "goal_command": command,
    }


def derived_contract(
    *, artifact: str, target: str, goal_id: str, metric: str, unit: str,
    dimensions: dict, raw_path: str, operation: str, operand_count: int,
    method: str, condition: str, figure_cell: bool = False,
) -> dict:
    acq = f"A-{artifact}-{target}"
    return {
        "id": acq, "acquisition_id": acq, "artifact_id": artifact, "target_id": target,
        "source_type": "RUN_LOCAL", "producing_goal": goal_id,
        "figure_source_cell": figure_cell, "metric": metric, "unit": unit,
        "dimensions": dimensions, "atomic_or_aggregate": "derived",
        "derivation": {
            "operation": operation,
            "operand_locators": [f"/paper_targets/{target}/operands/{i}" for i in range(operand_count)],
            "rounding": {"stage": "none", "decimals": None},
        },
        "experiment": "E1", "method": method,
        "dataset": "CLINC150 frozen four-intent micro test split (40 records)",
        "execution_split": "final", "model": "local multinomial classifier",
        "condition": condition, "seed_policy": "fixed seed 20260814; identical rerun required",
        "command_template": (
            "python3 -m code.micro_typo.run --stage word-level --config code/micro_typo/config.json"
            if goal_id == "G2.1" else
            "python3 -m code.micro_typo.run --stage character --config code/micro_typo/config.json"
        ),
        "code_paths": ["code/micro_typo"], "config_paths": ["code/micro_typo/config.json"],
        "environment_paths": ["code/micro_typo/environment.json"],
        "input_paths": ["data/micro_typo_intent/manifest.json"],
        "raw_output_path": raw_path, "raw_locator": f"/paper_targets/{target}/value",
        "computation_formula": (
            "arithmetic mean of persisted per-record correctness indicators"
            if operation == "mean" else
            "clean Accuracy minus 10% swap Accuracy"
        ),
        "aggregation": "exact point estimate over the frozen test records",
        "uncertainty_rule": "retain raw integer counts; no population interval",
        "prerequisites": ["G1.1"] if goal_id == "G2.1" else ["G2.1"],
        "verification_procedure": "reload operands, recompute exactly, compare the identical rerun, and reopen every path",
        "final_placement": "reports/05_EXP_RESULT.html",
    }


def make_acquisitions(contract: dict) -> list[dict]:
    artifacts = {item["id"]: item for item in contract["paper_artifacts"]}
    acquisitions = [{
        "id": "A-INF-G1.1", "acquisition_id": "A-INF-G1.1", "artifact_id": "",
        "target_id": "", "source_type": "RUN_LOCAL", "producing_goal": "G1.1",
        "figure_source_cell": False, "metric": "instrumentation smoke reproducibility",
        "unit": "status", "dimensions": {"scope": "tiny internal smoke slice"},
        "atomic_or_aggregate": "atomic", "experiment": "E0",
        "method": "shared local framework", "dataset": "approved CLINC150 source records",
        "execution_split": "instrumentation only", "model": "local classical classifiers",
        "condition": "two identical smoke executions", "seed_policy": "20260814",
        "command_template": "python3 -m code.micro_typo.run --stage instrumentation --config code/micro_typo/config.json",
        "code_paths": ["code/micro_typo"], "config_paths": ["code/micro_typo/config.json"],
        "environment_paths": ["code/micro_typo/environment.json"],
        "input_paths": ["reports/03_EXPERIMENT_PLAN.html"],
        "raw_output_path": "results/micro_typo_intent/instrumentation.json",
        "raw_locator": "/status", "computation_formula": "direct persisted PASS/FAIL status",
        "aggregation": "none", "uncertainty_rule": "not applicable", "prerequisites": [],
        "verification_procedure": "compare source/data/edit/schema/prediction/metric hashes across two runs and reopen all paths",
        "final_placement": "run-plan state and provenance only",
    }]

    t1 = artifacts["T1"]["shell"]
    for row_i, method in enumerate(t1["row_labels"]):
        gid = "G2.1" if row_i < 2 else "G3.1"
        raw = (
            "results/micro_typo_intent/word_level_results.json"
            if gid == "G2.1" else "results/micro_typo_intent/character_results.json"
        )
        for col_i, metric in enumerate(t1["column_labels"]):
            target = f"t1-{row_i:02d}-{col_i:02d}"
            op = "subtract" if col_i == 3 else "mean"
            operands = 2 if op == "subtract" else (4 if col_i == 2 else 40)
            acquisitions.append(derived_contract(
                artifact="T1", target=target, goal_id=gid, metric=metric, unit="proportion",
                dimensions={"dataset": "CLINC150 four-intent micro subset", "method": method,
                            "metric_column": metric}, raw_path=raw, operation=op,
                operand_count=operands, method=method, condition=metric,
            ))

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))["figures"]["F2"][0]
    approved = artifacts["F2"]["shell"]["required_data"][0]["cell_ids"]
    index = 0
    for rate in schema["x_values"]:
        for series_i, method in enumerate(schema["series"]):
            target = approved[index]
            index += 1
            gid = "G2.1" if series_i == 0 else "G3.1"
            raw = (
                "results/micro_typo_intent/word_level_results.json"
                if gid == "G2.1" else "results/micro_typo_intent/character_results.json"
            )
            acquisitions.append(derived_contract(
                artifact="F2", target=target, goal_id=gid,
                metric="Intent classification accuracy", unit="proportion",
                dimensions={"dataset": schema["dataset"], "panel": schema["panel"],
                            "method": method, "perturbation_rate": rate},
                raw_path=raw, operation="mean", operand_count=40, method=method,
                condition=f"internal-character swap rate {rate}", figure_cell=True,
            ))
    return acquisitions


def stylesheet() -> str:
    return """
    :root{--ink:#172a35;--muted:#617681;--teal:#087f74;--line:#cbdad9;--wash:#f4f8f7;--warn:#9b3c2e}
    *{box-sizing:border-box}body{margin:0;background:#fff;color:var(--ink);font:16px/1.58 Inter,system-ui,sans-serif}
    main{max-width:1280px;margin:auto;padding:42px 48px 96px}h1{font:700 40px/1.12 Georgia,serif;margin:5px 0 12px}
    h2{font:700 29px/1.2 Georgia,serif;margin:48px 0 18px;border-bottom:2px solid var(--teal);padding-bottom:8px}
    h3{font:700 21px/1.3 Georgia,serif;margin:25px 0 10px}h4{font-size:17px}.kicker{letter-spacing:.12em;text-transform:uppercase;color:var(--teal);font-weight:800}
    .hero,.part,.goal{border-left:4px solid #b9ddd7;padding:10px 20px;margin:15px 0}.part{background:var(--wash)}.goal{background:#fff}
    .current-goal{border-top:2px solid var(--teal);margin-top:17px;padding-top:11px}.pill{display:inline-block;border-radius:999px;background:#dff4ef;color:var(--teal);padding:3px 9px;font-weight:800}
    .copybox{white-space:pre-wrap;overflow-wrap:anywhere;background:#102e3b;color:#eef9f7;padding:14px;border-radius:7px;font-size:13px}
    .table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;min-width:700px}th,td{border:1px solid var(--line);padding:10px;text-align:left;vertical-align:top}thead th{background:#eaf3f1}.coverage{font-size:19px;font-weight:850;color:var(--teal)}
    .figure-result,.table-result,.concept-figure{margin:28px 0;padding-top:12px;border-top:3px solid var(--teal)}.panel-pair{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(260px,.9fr);gap:20px}.panel-pair>*{min-width:0}.empty-plot{min-height:250px;border:2px dashed var(--line);display:grid;place-items:center;text-align:center;color:var(--muted);font-weight:800}.pending{color:var(--warn);font-weight:850;text-align:center;background:#fff7f3}details{border:1px solid var(--line);padding:10px 14px}@media(max-width:850px){main{padding:26px 17px}.panel-pair{grid-template-columns:1fr}}
    """


def render_runplan(contract: dict, state: dict) -> str:
    impl_rows = "".join(
        f'<tr><th>{html.escape(item["display_name"])}</th><td>{html.escape(item["implementation_summary"])}</td></tr>'
        for item in contract["implementation_contract"]
    )
    coverage_rows = "".join([
        '<tr><th>F1</th><td>G1.1</td><td>非实验图，仅计数，后续由 paperwrite/figureppt 绘制。</td></tr>',
        '<tr><th>T1</th><td>G2.1, G3.1</td><td>12 个真实结果格；每格绑定唯一采集合同。</td></tr>',
        '<tr><th>F2</th><td>G2.1, G3.1</td><td>8 个真实源数据格；图只从已验证源表生成。</td></tr>',
    ])
    state_json = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Micro Typo Run Plan</title><style>{stylesheet()}</style></head><body><main>
    <p class="kicker">RUN PLAN · APPROVED REAL-DATA MICRO STUDY</p><h1>Character Granularity under Typographical Shift</h1><p>3 Parts · 3 Goals；一次只解锁一个 Goal。当前只批准执行 G1.1，不运行论文结果。</p>
    <section data-report-section="execution-estimate"><h2>1. Execution Estimate</h2><p><strong>推荐资源：</strong>本地 CPU，0 GPU。数据和依赖就绪后，全部实验计算预计少于 1 分钟；代码实现、审计与页面更新预计 20–40 分钟。</p><p><strong>单 GPU：</strong>不是必要条件；使用 GPU 不改变批准的实验合同。估计假设为 80 条训练、40 条测试、3 个经典分类器、4 个固定扰动率、无超参数搜索。</p><p class="coverage">图表覆盖：3/3 — F1, T1, F2</p></section>
    <section data-report-section="implementation-sources"><h2>2. Implementation Sources</h2><p>三个方法都在同一个本地框架中实现，共用数据适配器、扰动器、分类器 API、评估器和 JSON 结果模式。</p><div class="table-wrap"><table><thead><tr><th>Method</th><th>Final implementation</th></tr></thead><tbody>{impl_rows}</tbody></table></div></section>
    <section data-report-section="artifact-coverage"><h2>3. Figure/Table Coverage</h2><div class="table-wrap"><table><thead><tr><th>Artifact</th><th>Owning goals</th><th>Completion contract</th></tr></thead><tbody>{coverage_rows}</tbody></table></div></section>
    {render_parts_and_goals(state)}
    <script type="application/json" id="run-plan-state">{state_json}</script></main></body></html>'''


def pending_cell(target: str, acquisition: str) -> str:
    return f'<td class="pending" data-target-id="{target}" data-acquisition-id="{acquisition}">[PENDING]</td>'


def render_results(contract: dict) -> str:
    artifacts = {item["id"]: item for item in contract["paper_artifacts"]}
    t1 = artifacts["T1"]["shell"]
    ids = iter(t1["pending_cell_ids"])
    rows = []
    for row in t1["row_labels"]:
        cells = []
        for _ in t1["column_labels"]:
            target = next(ids)
            cells.append(pending_cell(target, f"A-T1-{target}"))
        rows.append(f'<tr><th>{html.escape(row)}</th>{"".join(cells)}</tr>')
    headers = "".join(f'<th>{html.escape(item)}</th>' for item in t1["column_labels"])

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))["figures"]["F2"][0]
    f2_ids = artifacts["F2"]["shell"]["required_data"][0]["cell_ids"]
    f2_iter = iter(f2_ids)
    f2_rows = []
    for rate in schema["x_values"]:
        cells = []
        for _ in schema["series"]:
            target = next(f2_iter)
            cells.append(pending_cell(target, f"A-F2-{target}"))
        f2_rows.append(f'<tr><th>{rate}</th>{"".join(cells)}</tr>')
    f2_headers = "".join(f'<th>{html.escape(item)}</th>' for item in schema["series"])
    source_ids = " ".join(f2_ids)
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Micro Typo Experiment Results</title><style>{stylesheet()}</style></head><body><main>
    <p class="kicker">EXPERIMENT RESULTS · PENDING</p><h1>Character Granularity under Typographical Shift</h1>
    <section data-report-section="artifact-completion"><h2>1. Artifact Completion</h2><p><strong>0/3 artifacts complete；0/20 paper-facing numeric targets filled.</strong> F1 是不需要实验数字的概念图；T1 与 F2 保持空白，直到 ledger 中出现已验证真实结果。</p></section>
    <section data-report-section="paper-artifacts"><h2>2. Paper Tables and Figures</h2><p>这里严格保留批准的行、列、面板和聚合语义；图只会从左侧全部验证后的数字生成。</p>
      <section class="concept-figure" data-artifact-id="F1"><h3>F1 · Motivation figure</h3><p class="pending">PENDING — 非实验图，仅计数，后续由 paperwrite/figureppt 绘制。</p></section>
      <section class="table-result" data-artifact-id="T1"><h3>T1 · {html.escape(t1["caption"])}</h3><div class="table-wrap"><table><thead><tr><th>Method</th>{headers}</tr></thead><tbody>{"".join(rows)}</tbody></table></div></section>
      <section class="figure-result" data-artifact-id="F2" data-source-target-ids="{source_ids}"><h3>F2 · {html.escape(artifacts["F2"]["shell"]["caption"])}</h3><div class="result-panel"><h4>{html.escape(schema["panel"])}</h4><div class="panel-pair"><div><p><strong>Dataset / benchmark:</strong> {html.escape(schema["dataset"])}</p><p><strong>Metric / axes:</strong> {html.escape(schema["metric"])}; {html.escape(schema["x_axis"])} → {html.escape(schema["y_axis"])}.</p><div class="table-wrap"><table><thead><tr><th>{html.escape(schema["x_axis"])}</th>{f2_headers}</tr></thead><tbody>{"".join(f2_rows)}</tbody></table></div></div><div class="empty-plot">PENDING<br>8 个源数字全部验证后生成真实曲线</div></div></div></section>
    </section>
    <section data-report-section="generation-process"><h2>3. 生成过程</h2><details id="result-provenance-index" open><summary>尚无已验证结果</summary><p>当前 ledger 只有固定表头。完成 Goal 后，每个数字会链接到原始文件、JSON pointer、实际命令、代码/配置、版本和验证状态。</p></details><script type="application/json" id="result-provenance">{{}}</script></section>
    </main></body></html>'''


def ensure_ledger() -> None:
    if LEDGER.exists():
        with LEDGER.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.reader(handle))
        if rows and rows[0] != LEDGER_COLUMNS:
            raise ValueError("existing ledger header does not match the fixed schema")
        if len(rows) > 1:
            raise ValueError("refusing to replace a non-empty append-only ledger")
        return
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerow(LEDGER_COLUMNS)


def main() -> None:
    contract = load_contract()
    command = (
        "/goal Complete G1.1: build and verify the minimal reproducible local path for the approved "
        "CLINC150 micro study without running paper-facing experiments; materialize and verify R1 at "
        "the approved commit 828f8093932c8fe6ca7936c3d2e52903b1c523de, record the CC BY 3.0 license and JSON SHA-256, "
        "create the deterministic 80-train/40-test manifest for weather, restaurant_reviews, "
        "change_speed, and balance by sorting stable SHA-256 record IDs and taking 20 train plus 10 "
        "test records per label; implement the shared record schema, reconstructable internal-character "
        "swap edit log, majority and Naive Bayes interfaces, exact Accuracy/Macro-F1/Robustness-Drop "
        "metrics, and result/provenance paths; run only a tiny instrumentation smoke twice and require "
        "identical source hashes, manifests, edits, schemas, predictions, metrics, and reopenable paths; "
        "record A-INF-G1.1 without filling T1 or F2; follow reports/04_RUN_PLAN.html and its embedded "
        "run-plan state; save each result immediately; before completing the goal, organize its code and "
        "files, remove only disposable temporary artifacts, and verify every recorded path; append and "
        "validate every result in code/RESULTS_LEDGER.csv; update the embedded state, regenerate "
        "reports/04_RUN_PLAN.html so the goal shows ✅, and update reports/05_EXP_RESULT.html from the "
        "ledger; stop after G1.1, do not start the successor goal, and only propose the next unlocked /goal."
    )
    goals = [
        goal("G1.1", "P1", "S0", "最小本地可复现通路", "数据、扰动、分类和指标路径能否被两次相同 smoke run 完整复现？", "验证固定 CLINC150 来源，冻结 80-train/40-test manifest，并实现共享记录、扰动、分类器、指标与 provenance 接口；仅运行不填论文格的极小 smoke。", "产生 A-INF-G1.1，并把 F1 保持为非实验概念图。", "两次 smoke 的来源哈希、manifest、edit log、模式、预测和指标完全一致；所有路径可重新打开。", ["F1"], [], [f"D{i}" for i in range(1, 8)], ["data/micro_typo_intent/manifest.json", "code/micro_typo/config.json", "code/micro_typo/environment.json", "results/micro_typo_intent/instrumentation.json"], ["E0"], command),
        goal("G2.1", "P2", "S1", "词级脆弱性与控制基线", "词级特征在真实四意图切片上是否随拼写扰动产生可测退化？", "在冻结训练/测试记录和四个扰动率上运行 Majority 与 word-unigram，重复执行并保存所有逐条预测、计数和运行来源。", "填充 T1 的前两行与 F2 的 word-unigram 系列，共 12 个真实目标值。", "12 个值均能从 raw operands 精确重算，两次运行一致，且没有访问或改变批准配置。", ["T1", "F2"], ["G1.1"], [], ["results/micro_typo_intent/word_level_results.json"], ["E1"]),
        goal("G3.1", "P3", "S4", "字符三元组比较", "只改变特征粒度能否降低 10% 拼写扰动下的 Robustness Drop？", "在完全相同的数据、扰动、Naive Bayes 核心和评估合同上运行 character-trigram，并从 ledger 生成完整 T1 和 F2。", "填充 T1 最后一行与 F2 的 character-trigram 系列，共 8 个真实目标值，并裁决 C2。", "8 个新值均可重算；T1 的 12 格和 F2 的 8 个源格全部验证，真实图从源表生成。", ["T1", "F2"], ["G2.1"], [], ["results/micro_typo_intent/character_results.json", "paper/fig/micro_typo_intent/results/F2_typo_sensitivity.pdf"], ["E1"]),
    ]
    parts = [
        {"id": "P1", "title": "Instrumentation", "decision": "先证明最小通路可重复，但不产生论文数字。", "claims": [], "artifact_ids": ["F1"], "dependencies": [], "entry": "approved plan", "exit_gate": "E0 smoke reproducible", "goals": ["G1.1"]},
        {"id": "P2", "title": "Problem-Existence Validation", "decision": "确认词级模型是否存在拼写脆弱性。", "claims": ["C1"], "artifact_ids": ["T1", "F2"], "dependencies": ["P1"], "entry": "G1.1 complete", "exit_gate": "word/control targets verified", "goals": ["G2.1"]},
        {"id": "P3", "title": "Method Comparison", "decision": "确认字符三元组是否改善冻结比较。", "claims": ["C2"], "artifact_ids": ["T1", "F2"], "dependencies": ["P2"], "entry": "G2.1 complete", "exit_gate": "T1 and F2 complete", "goals": ["G3.1"]},
    ]
    acquisitions = make_acquisitions(contract)
    frozen = {
        item["id"]: {"value": item["allowed_values"], "source_goal": "approved expplan contract v2", "status": "fixed_before_execution"}
        for item in contract["decision_space_contract"]
    }
    state = {
        "schema_version": "1.0", "source_plan": "reports/03_EXPERIMENT_PLAN.html",
        "source_plan_identity": {"path": "reports/03_EXPERIMENT_PLAN.html", "sha256": hashlib.sha256(EXPPLAN.read_bytes()).hexdigest(), "approval_contract_version": contract["approval_contract_version"]},
        "source_plan_approval": {"status": "approved", "approved_at": contract["approved_at"], "digest": contract["approval_contract_sha256"]},
        "state": "awaiting_goal_activation", "proposed_goal_id": "G1.1", "active_goal": None,
        "parts": parts, "goals": goals, "completed_results": [], "frozen_configuration": frozen,
        "attempts": [], "raw_paths": [], "result_paths": [], "gate_decisions": [],
        "amendments": [
            {"at": "2026-08-14", "reason": "Approved micro-study contract v2 replaces the prior empty I1 execution graph.", "preserved_evidence": "none; ledger had no result rows"},
            {"at": "2026-08-14", "reason": "Corrected generated G1.1 revision 828f4a3c20fba50712b2e7eb6a42486e9590d206, which GitHub rejects as not our ref, to the approved 03 contract revision 828f8093932c8fe6ca7936c3d2e52903b1c523de.", "scope_change": "none; source repository, dataset file, labels, counts, and experiment design are unchanged"},
        ],
        "skips": [], "next_authorized_action": "Researcher manually activates exactly G1.1 using the nested /goal command.",
        "ledger_audit": {"status": "PASS_EMPTY", "checked_at": "2026-08-14", "ledger": "code/RESULTS_LEDGER.csv"},
        "decision_space_contract": contract["decision_space_contract"],
        "execution_splits": [
            {"experiment_id": "E0", "development_source": "Tiny instrumentation-only subset drawn from the frozen manifest; it cannot fill paper cells.", "final_source": "Not applicable; E0 produces no paper-facing result.", "protocol_source": "Approved E0 contract and official CLINC150 source metadata.", "disjoint": True, "frozen_before_final": True},
            {"experiment_id": "E1", "development_source": "None; all decisions are FIXED_BY_DESIGN and no hyperparameter search is authorized.", "final_source": "Official CLINC150 test split: first 10 stable SHA-256-sorted records per approved label (40 total).", "training_source": "Official CLINC150 train split: first 20 stable SHA-256-sorted records per approved label (80 total).", "selection_rule": "record_id = SHA-256(split + label + source text); sort ascending within label and split, then take the fixed count.", "protocol_source": "Official CLINC150 JSON at revision 828f4a3c20fba50712b2e7eb6a42486e9590d206 and approved D1–D7.", "disjoint": True, "frozen_before_final": True},
        ],
        "implementation_contract": contract["implementation_contract"],
        "approved_artifact_ids": [item["id"] for item in contract["paper_artifacts"]],
        "artifact_coverage": {"F1": {"goals": ["G1.1"], "note": "非实验图，仅计数，后续由 paperwrite/figureppt 绘制"}, "T1": {"goals": ["G2.1", "G3.1"]}, "F2": {"goals": ["G2.1", "G3.1"]}},
        "acquisition_contracts": acquisitions,
        "requirement_routes": [
            {"requirement_id": "REQ-T1", "artifact_id": "T1", "goals": ["G2.1", "G3.1"], "acquisition_ids": [item["id"] for item in acquisitions if item["artifact_id"] == "T1"], "raw_paths": ["results/micro_typo_intent/word_level_results.json", "results/micro_typo_intent/character_results.json"]},
            {"requirement_id": "REQ-F2", "artifact_id": "F2", "goals": ["G2.1", "G3.1"], "acquisition_ids": [item["id"] for item in acquisitions if item["artifact_id"] == "F2"], "raw_paths": ["results/micro_typo_intent/word_level_results.json", "results/micro_typo_intent/character_results.json"]},
        ],
    }
    ensure_ledger()
    RUNPLAN.write_text(render_runplan(contract, state), encoding="utf-8")
    RESULTS.write_text(render_results(contract), encoding="utf-8")


if __name__ == "__main__":
    main()
