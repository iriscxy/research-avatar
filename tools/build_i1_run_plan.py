#!/usr/bin/env python3
"""Generate the I1 run plan, empty ledger, and pending result counterpart."""

from __future__ import annotations

import csv
import html
import json
import re
from pathlib import Path

from run_plan_progress import goal_command, render_parts_and_goals


ROOT = Path(__file__).resolve().parents[1]
EXPPLAN = ROOT / "reports/03_EXPERIMENT_PLAN.html"
RUNPLAN = ROOT / "reports/04_RUN_PLAN.html"
RESULTS = ROOT / "reports/05_EXP_RESULT.html"
LEDGER = ROOT / "code/RESULTS_LEDGER.csv"
STATE_RE = re.compile(r'<script type="application/json" id="experiment-plan-contract">(.*?)</script>', re.S)
LEDGER_COLUMNS = [
    "result_id", "goal_id", "artifact_id", "target_id", "acquisition_id", "source_type",
    "status", "metric", "value", "unit", "dimensions_json", "raw_artifact", "raw_locator",
    "source_reference", "source_locator", "command", "code_files", "config_files", "environment_files",
    "code_revision", "obtained_at", "verified_at", "verification_status", "notes",
]


def load_contract() -> dict:
    match = STATE_RE.search(EXPPLAN.read_text(encoding="utf-8"))
    if not match:
        raise ValueError("approved experiment plan contract not found")
    contract = json.loads(match.group(1))
    if contract.get("approval_status") != "approved":
        raise ValueError("experiment plan is not approved")
    return contract


def goal(gid: str, part: str, stage: str, title: str, why: str, work: str, evidence: str, check: str, artifacts: list[str], deps: list[str], decisions: list[str], budget: str, experiment_ids: list[str]) -> dict:
    return {
        "id": gid, "part_id": part, "subpart_id": gid, "stage": stage, "title": title,
        "status": "pending" if gid == "G1.1" else "locked", "decision_question": why,
        "visible_work": work, "visible_evidence": evidence, "completion_check": check,
        "artifact_ids": artifacts, "dependencies": deps, "decision_ids": decisions,
        "budget": budget, "experiment_ids": experiment_ids,
        "inputs": ["reports/03_EXPERIMENT_PLAN.html", "approved repository contract"],
        "outputs": [f"code/{gid.replace('.', '_').lower()}_manifest.json", f"results/first_divergence_repair/{gid.replace('.', '_').lower()}.json"],
        "authorized_runs": "Only the approved models, datasets, methods, metrics, and bounded decisions assigned here.",
        "required_checks": ["schema validation", "raw-path resolution", "reproducibility smoke check"],
        "falsifier": "Apply the claim-specific falsifier from the approved experiment contract.",
        "successor_branches": ["continue", "refine within approved budget", "pivot/stop and return to expplan"],
        "exclusions": ["no new metric/dataset/baseline", "no final-data tuning", "no successor execution"],
    }


def main() -> None:
    contract = load_contract()
    goals = [
        goal("G1.1","P1","S0","最小可复现轨迹通路","最便宜的路径能否稳定记录层×token 激活、生成、judge 与 provenance？","在一个批准模型和极小的批准输入切片上建立统一 ModelAdapter、TraceRecorder、DatasetRecord、Defense 和 Evaluator 接口；固定随机性，重复运行并整理代码、配置与环境记录。","建立后续所有机制实验的可信输入，并冻结非实验动机图 F1 的构图规格。","两次相同 smoke run 的结构、字段、层索引和 judge 输出一致，且所有记录路径可重新打开。",["F1"],[],["D1","D2","D5","D6","D7"],"4 GPU-hours",["E0"]),
        goal("G2.1","P2","S1","AdvBench 首次偏离探针","风格改变后是否出现稳定而非弥散的首次安全管道退出？","在批准模型上完成 AdvBench 50 意图的直接形式与匹配风格形式追踪，先完成语义/危害等价性审计，再记录逐层退出事件。","填充 F2 的 AdvBench 首次退出曲线。","每个意图与风格均有可追溯配对记录，bootstrap 区间可由原始记录重算。",["F2"],["G1.1"],[],"28 GPU-hours",["E1"]),
        goal("G2.2","P2","S1","HarmBench 成功/失败退出集中度","首次退出是否只在成功 jailbreak 中形成可复现集中峰？","按相同追踪协议完成 HarmBench 成功与失败输出的分组诊断，并保持模型、解码和 judge 一致。","填充 F2 的 HarmBench 成功/失败集中度面板并完成动机门。","成功/失败标签、首退层与配对元数据均可从保存的 JSONL 重建。",["F2"],["G2.1"],[],"20 GPU-hours",["E1"]),
        goal("G3.1","P3","S2","单模型单点修复可行性","一次首次退出层修复能否影响预期轨迹，而不是只改变输出表面？","在一个模型上实现首次退出定位和 norm-matched 单点修复，运行首次层、错误层和无修复的小规模机制对照。","产生进入正式调参前的机制可行性证据，不直接填最终图表。","修复位置、位移范数和下游相似度均记录完整；若首次层无特异作用则触发停止。",[],["G2.2"],[],"24 GPU-hours",["E3"]),
        goal("G4.1","P4","S3","冻结安全管道阈值","哪一个批准的校准分位数能在开发数据上稳定定位首次退出？","只在已记录的开发来源上搜索 0.90、0.95、0.975、0.99 四个分位数，并保存每个候选的完整诊断。","冻结 D3，供所有最终数据目标共同使用。","选择规则、开发观测量和最终阈值写入 frozen_configuration，未访问最终来源。",[],["G3.1"],["D3"],"12 GPU-hours",["E1","E3"]),
        goal("G4.2","P4","S3","冻结最小有效修复强度","哪个批准强度在开发数据上达到安全条件且最少损伤良性行为？","在 0.25、0.5、0.75、1.0、1.25 中按批准规则选择最小有效强度，并保留完整候选记录。","冻结 D4，之后任何主结果和敏感性结论不得回看最终数据调参。","候选值、选择观测量和来源 goal 写入 frozen_configuration。",[],["G4.1"],["D4"],"16 GPU-hours",["E5"]),
        goal("G5.1","P5","S4","统一协议主比较","冻结后的方法是否在两个有害基准和两个效用基准上优于五个共同协议基线？","在三个批准模型上重跑 No Defense、ABD、RTV、JBShield、TrajGuard 和 First-Divergence Repair；每个种子先落盘，再计算宏平均与区间。","完整填充主结果表 T1。","24 个批准单元格均由可重算的原始记录和统一 judge 合同支持。",["T1"],["G4.2"],[],"160 GPU-hours",["E2"]),
        goal("G6.1","P6","S5","修复层偏移因果曲线","效果是否在首次退出层达到独特峰值？","对首次退出层前后 −3 到 +3 的偏移做 strength-matched 干预，并同时测安全恢复与良性保留。","填充 F3 的 repair-offset 面板。","14 个源数据格完成且首次层与错误层比较可由同一 paired record 重算。",["F3"],["G5.1"],[],"28 GPU-hours",["E3"]),
        goal("G6.2","P6","S5","下游轨迹恢复检验","一次修复后，后续层是否自行回到安全参考轨迹？","比较无修复、首次退出修复和错误层修复在后续六层的安全参考相似度。","填充 F3 的 downstream-recovery 面板。","21 个源数据格与轨迹原始张量摘要一致，缺层或对齐失败均显式标记。",["F3"],["G6.1"],[],"36 GPU-hours",["E3"]),
        goal("G6.3","P6","S5","唯一性消融矩阵","随机层、ABD 层、最后退出层或重复修复能否解释相同收益？","完成完整方法与四个批准消融的共同协议比较，保持修复范数和评测条件一致。","完整填充 T2，并直接裁决唯一性与单点充分性。","20 个批准格全部可重算；若任何对照并列则弱化或否证 C2。",["T2"],["G6.2"],[],"72 GPU-hours",["E4"]),
        goal("G7.1","P7","S5","修复强度鲁棒性","冻结选择附近的安全、过度拒答与通用能力曲线是否形成稳定前沿？","在三个模型上运行五个已批准强度，不更改主比较中冻结的最终配置。","填充 F4 的 15 个敏感性源数据点。","每个点由相同数据、judge 和种子政策生成，图只能从旁侧数据表生成。",["F4"],["G6.3"],[],"48 GPU-hours",["E5"]),
        goal("G8.1","P8","S6","成本与失败表面","安全收益在延迟、显存和未恢复案例上付出什么代价？","对六种方法完成同步计时、峰值显存记录和未恢复案例归类，并保存实际命令及环境。","填充 T3；必要时按批准合同移至附录。","18 个单元格均有原始计时/显存/失败记录，负面结果不得省略。",["T3"],["G7.1"],[],"32 GPU-hours",["E6"]),
    ]
    parts = [
        {"id":"P1","title":"Instrumentation","decision":"最小实验路径是否可复现？","claims":[],"artifact_ids":["F1"],"dependencies":[],"entry":"approved plan","exit_gate":"trace and evaluator smoke reproducible","goals":["G1.1"]},
        {"id":"P2","title":"Problem-Existence Validation","decision":"稳定的首次偏离现象是否存在？","claims":["C1"],"artifact_ids":["F2"],"dependencies":["P1"],"entry":"G1.1 complete","exit_gate":"first-exit motivation gate passes","goals":["G2.1","G2.2"]},
        {"id":"P3","title":"Method Feasibility","decision":"单点修复是否作用于预期内部量？","claims":["C2"],"artifact_ids":[],"dependencies":["P2"],"entry":"C1 motivated","exit_gate":"first-layer-specific pilot effect","goals":["G3.1"]},
        {"id":"P4","title":"Development Tuning","decision":"批准的阈值和强度取值是什么？","claims":["C1","C2"],"artifact_ids":[],"dependencies":["P3"],"entry":"mechanism feasible","exit_gate":"D3 and D4 frozen without final access","goals":["G4.1","G4.2"]},
        {"id":"P5","title":"Primary Evidence","decision":"冻结方法能否改善主要安全–效用比较？","claims":["C2","C3"],"artifact_ids":["T1"],"dependencies":["P4"],"entry":"configuration frozen","exit_gate":"T1 complete","goals":["G5.1"]},
        {"id":"P6","title":"Causal Controls and Ablation","decision":"首次退出层是否唯一且单点充分？","claims":["C2"],"artifact_ids":["F3","T2"],"dependencies":["P5"],"entry":"primary evidence complete","exit_gate":"wrong-layer controls adjudicated","goals":["G6.1","G6.2","G6.3"]},
        {"id":"P7","title":"Robustness and Sensitivity","decision":"收益能否跨模型和强度保持？","claims":["C3"],"artifact_ids":["F4"],"dependencies":["P6"],"entry":"causal gate resolved","exit_gate":"sensitivity figure complete","goals":["G7.1"]},
        {"id":"P8","title":"Cost and Failure Analysis","decision":"方法何时失败且部署成本多大？","claims":["C3"],"artifact_ids":["T3"],"dependencies":["P7"],"entry":"final evidence available","exit_gate":"cost/failure table complete","goals":["G8.1"]},
    ]

    target_goal = {}
    for requirement in contract["result_requirements"]:
        aid = requirement["artifact_id"]
        for target in requirement.get("cell_ids", []):
            if aid == "F2": target_goal[(aid,target)] = "G2.1" if "exit_depth" in target else "G2.2"
            elif aid == "F3": target_goal[(aid,target)] = "G6.1" if "repair_offset" in target else "G6.2"
            elif aid == "F4": target_goal[(aid,target)] = "G7.1"
            elif aid == "T1": target_goal[(aid,target)] = "G5.1"
            elif aid == "T2": target_goal[(aid,target)] = "G6.3"
            elif aid == "T3": target_goal[(aid,target)] = "G8.1"

    artifact_by_id = {item["id"]: item for item in contract["paper_artifacts"]}
    figure_schema = json.loads((ROOT / "paper/figsrc/first_divergence_repair/figure_schema.json").read_text(encoding="utf-8"))
    panel_by_target = {}
    for aid, panels in figure_schema["figures"].items():
        shell_data = artifact_by_id[aid]["shell"]["required_data"]
        for panel, approved in zip(panels, shell_data):
            for target in approved["cell_ids"]:
                panel_by_target[(aid,target)] = panel

    acquisitions = []
    # Non-paper state acquisitions keep configuration and smoke evidence inspectable.
    for acq_id, gid, metric_name, raw in [
        ("A-INF-G1.1","G1.1","instrumentation smoke reproducibility","results/first_divergence_repair/g1_1.json"),
        ("A-INF-G3.1","G3.1","single-site feasibility gate","results/first_divergence_repair/g3_1.json"),
        ("A-DEC-D3","G4.1","selected safety-tube threshold","results/first_divergence_repair/g4_1.json"),
        ("A-DEC-D4","G4.2","selected repair strength","results/first_divergence_repair/g4_2.json"),
    ]:
        acquisitions.append({"id":acq_id,"acquisition_id":acq_id,"artifact_id":"","target_id":"","source_type":"RUN_LOCAL","producing_goal":gid,"figure_source_cell":False,"metric":metric_name,"unit":"status or selected value","dimensions":{},"atomic_or_aggregate":"atomic","experiment":"approved instrumentation/development decision","method":"First-Divergence Repair","dataset":"approved development source","execution_split":"development","model":"approved smoke/development model","condition":"approved bounded condition","seed_policy":"fixed reproducibility seed plus repeat","command_template":f"python -m code.first_divergence --goal {gid}","code_paths":["code/first_divergence"],"config_paths":["code/configs/first_divergence.yaml"],"input_paths":["reports/03_EXPERIMENT_PLAN.html"],"raw_output_path":raw,"raw_locator":"/value","computation_formula":"direct persisted gate/status value","aggregation":"none","uncertainty_rule":"not applicable","prerequisites":next(g["dependencies"] for g in goals if g["id"]==gid),"verification_procedure":"rerun or recompute from persisted raw record","final_placement":"run-plan state only"})

    method_models = ["Llama-3.1-8B-Instruct","Mistral-7B-Instruct-v0.3","Qwen2.5-7B-Instruct"]
    for (aid, target), gid in target_goal.items():
        art = artifact_by_id[aid]
        figure_cell = aid.startswith("F")
        if figure_cell:
            panel = panel_by_target[(aid,target)]
            metric_name = panel["metric"]
            dataset = panel["dataset"]
            condition = next(name for name in panel["series"] if target.endswith(f"-{panel['series'].index(name):02d}"))
            unit = "normalized score" if "Normalized" in metric_name else "rate or similarity"
            dimensions = {"dataset":dataset,"panel":panel["panel"],"condition":condition,"x_axis":panel["x_axis"]}
        else:
            shell = art["shell"]
            parts_target = target.split("-")
            row_i, col_i = int(parts_target[-2]), int(parts_target[-1])
            method_name = shell["row_labels"][row_i]
            metric_name = shell["column_labels"][col_i]
            dataset = "AdvBench + HarmBench + XSTest + Just-Eval" if aid != "T3" else "approved local timing and failure records"
            condition = method_name
            unit = "% or normalized score" if aid != "T3" else ("ms/query" if col_i == 0 else "GiB" if col_i == 1 else "%")
            dimensions = {"dataset":dataset,"method":method_name,"metric_column":metric_name}
        operands = [f"/operands/{model}" for model in method_models]
        acq_id = f"A-{aid}-{target}"
        acquisitions.append({
            "id":acq_id,"acquisition_id":acq_id,"artifact_id":aid,"target_id":target,
            "source_type":"RUN_LOCAL","producing_goal":gid,"figure_source_cell":figure_cell,
            "metric":metric_name,"unit":unit,"dimensions":dimensions,"atomic_or_aggregate":"derived",
            "derivation":{"operation":"mean","operand_locators":operands,"rounding":{"stage":"none","decimals":None}},
            "experiment":next(req["experiment_id"] for req in contract["result_requirements"] if req["artifact_id"]==aid),
            "method":condition,"dataset":dataset,"execution_split":"final","model":"macro-average over the three approved models",
            "condition":condition,"seed_policy":"persist every approved seed before aggregation",
            "command_template":f"python -m code.first_divergence.acquire --artifact {aid} --target {target}",
            "code_paths":["code/first_divergence"],"config_paths":["code/configs/frozen.json"],
            "input_paths":["reports/03_EXPERIMENT_PLAN.html"],
            "raw_output_path":f"results/first_divergence_repair/{gid.replace('.', '_').lower()}.json",
            "raw_locator":f"/paper_targets/{target}/value","computation_formula":"macro-mean of persisted model-level values",
            "aggregation":"approved macro-average with prompt bootstrap 95% CI; target stores the displayed central value",
            "uncertainty_rule":"paired prompt bootstrap 95% CI retained beside the central record",
            "prerequisites":next(g["dependencies"] for g in goals if g["id"]==gid),
            "verification_procedure":"reload model operands, recompute with Decimal, check frozen config and source paths",
            "final_placement":"reports/05_EXP_RESULT.html",
        })

    artifact_coverage = {
        "F1":{"goals":["G1.1"],"note":"非实验图，仅计数，后续由 paperwrite/figureppt 绘制"},
        "F2":{"goals":["G2.1","G2.2"]},"F3":{"goals":["G6.1","G6.2"]},
        "F4":{"goals":["G7.1"]},"T1":{"goals":["G5.1"]},"T2":{"goals":["G6.3"]},"T3":{"goals":["G8.1"]},
    }
    execution_splits = []
    for exp in contract["experiment_contracts"]:
        execution_splits.append({
            "experiment_id":exp["id"],
            "development_source":"Calibration-only AdvBench/Alpaca records and matched-style intent families reserved by intent_id before tuning.",
            "final_source":"Confirmed AdvBench 50, HarmBench standard behaviors, XSTest, and Just-Eval final acquisition records, never read during selection.",
            "protocol_source":"ABD calibration convention plus official HarmBench/XSTest/Just-Eval protocols and the approved matched-style construction audit.",
            "disjoint":True,"frozen_before_final":True,
        })
    state = {
        "schema_version":"1.0","generated_at":"2026-08-15","source_plan":"reports/03_EXPERIMENT_PLAN.html",
        "source_plan_approval":{"status":"approved","approved_at":contract["approved_at"],"contract_version":contract.get("approval_contract_version", contract.get("contract_version")),"digest":contract["approval_contract_sha256"]},
        "state":"awaiting_goal_confirmation","execution_mode":"awaiting_goal_confirmation",
        "goal_confirmation":{"status":"pending","scope":None,"confirmed_goal_ids":[],"plan_digest":None,"confirmed_at":None},
        "proposed_goal_id":None,"active_goal":None,
        "parts":parts,"goals":goals,"completed_results":[],"frozen_configuration":{},"attempts":[],
        "raw_paths":[],"result_paths":[],"gate_decisions":[],"amendments":[],"skips":[],
        "next_authorized_action":"Researcher chooses either confirm-all automatic execution or one-goal-at-a-time review.",
        "ledger_audit":{"status":"PASS_EMPTY","checked_at":"2026-08-15","ledger":"code/RESULTS_LEDGER.csv"},
        "decision_space_contract":contract["decision_space_contract"],"execution_splits":execution_splits,
        "implementation_contract":contract["implementation_contract"],
        "approved_artifact_ids":[item["id"] for item in contract["paper_artifacts"]],
        "artifact_coverage":artifact_coverage,"acquisition_contracts":acquisitions,
    }

    command = "/goal Complete G1.1: build the smallest reproducible unified trace path on one approved 7–8B model and a tiny approved input slice; implement and verify ModelAdapter, DatasetRecord with intent_id/style_id, layer×token TraceRecorder, disabled-defense generation, and the frozen evaluator path; run the identical smoke configuration twice and require matching schemas, layer indices, deterministic outputs, and reopenable raw/provenance paths; record the instrumentation smoke result A-INF-G1.1 without filling empirical paper cells; follow reports/04_RUN_PLAN.html and its embedded run-plan state; save each result immediately; before completing the goal, organize its code and files, remove only disposable temporary artifacts, and verify every recorded path; append and validate every result in code/RESULTS_LEDGER.csv; update the embedded state, regenerate reports/04_RUN_PLAN.html so the goal shows ✅, and update the matching shells in reports/05_EXP_RESULT.html from the ledger; stop after G1.1, do not start the successor goal, and only propose the next unlocked /goal."
    for item in goals:
        if item["id"] == "G1.1":
            item["goal_command"] = command
        else:
            item["goal_command"] = goal_command(item)

    impl_rows = []
    for item in contract["implementation_contract"]:
        source = (f' <a href="{item["source_url"]}">Official GitHub</a>'
                  if item.get("source_url") else '')
        impl_rows.append(
            f'<tr><th>{html.escape(item["display_name"])}</th>'
            f'<td>{html.escape(item["implementation_summary"])}{source}</td></tr>'
        )

    coverage_items = "".join(f'<li><strong>{aid}</strong> — Goals {", ".join(info["goals"])}{("；"+info["note"]) if info.get("note") else ""}</li>' for aid, info in artifact_coverage.items())
    css = '''*{box-sizing:border-box}:root{--ink:#172a35;--teal:#087f74;--line:#cbdad9;--wash:#f4f8f7;--muted:#60737e}body{margin:0;background:#fff;color:var(--ink);font:17px/1.58 Inter,system-ui,sans-serif}main{max-width:1450px;margin:auto;padding:42px 52px 100px}h1{font:700 42px Georgia,serif;margin:6px 0}h2{font:700 29px Georgia,serif;border-bottom:2px solid var(--teal);padding-bottom:8px;margin-top:48px}h3{font-size:21px;margin:22px 0 7px}.kicker{color:var(--teal);font-weight:900;letter-spacing:.12em}.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;min-width:800px}th,td{border:1px solid var(--line);padding:11px;text-align:left;vertical-align:top}thead th{background:#eaf3f1}.estimate td:nth-child(2){font-weight:800}.part{border-left:4px solid var(--teal);padding:3px 0 10px 22px;margin:30px 0}.goal{border:1px solid var(--line);border-radius:10px;padding:4px 18px 14px;margin:13px 0;background:#fff}.goal p{margin:7px 0}.mapping{color:var(--teal);font-weight:850}.current-goal{margin:16px -5px 1px;padding:16px 18px;border:2px solid var(--teal);border-radius:9px;background:var(--wash)}.current-goal h4{margin:0 0 8px;font-size:18px}.goal-results{margin:18px -5px 2px;padding:16px 18px;border-top:3px solid var(--teal);background:#f8fbfa}.goal-results>h4{margin:0 0 6px;font-size:19px}.goal-results .figure-result,.goal-results .table-result,.goal-results .concept-figure{margin:18px 0;padding-top:10px;border-top:1px solid var(--line)}.goal-results .panel-pair{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(240px,.85fr);gap:18px}.goal-results .panel-pair>*{min-width:0}.goal-results .empty-plot{min-height:210px;border:2px dashed var(--line);display:grid;place-items:center;text-align:center;color:var(--muted);font-weight:800}.goal-results a[data-result-id]{font-weight:850;color:var(--teal);text-underline-offset:3px}.copybox{white-space:pre-wrap;background:#10232c;color:#eaf7f4;padding:18px;border-radius:10px;font:14px/1.55 ui-monospace,monospace;overflow:auto}.notice{background:var(--wash);border:2px solid var(--teal);padding:15px 18px}.coverage{columns:2}.pill{display:inline-block;padding:3px 9px;border:1px solid var(--teal);border-radius:99px;color:var(--teal);font-weight:850}@media(max-width:820px){main{padding:25px 17px}.coverage{columns:1}.goal-results .panel-pair{grid-template-columns:1fr}}'''
    state_json = json.dumps(state, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    parts_html = render_parts_and_goals(state)
    run_html = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>I1 Run Plan</title><style>{css}</style></head><body><main><p class="kicker">RUN PLAN · I1</p><h1>First-Divergence Repair Execution Funnel</h1>
    <section data-report-section="execution-estimate"><h2>1. Execution Estimate</h2><div class="table-wrap"><table class="estimate"><tbody><tr><th>Total goals</th><td>12</td><td>8 major evidence parts</td></tr><tr><th>Recommended GPUs</th><td>4×A100</td><td>One-GPU execution remains possible with longer wall time.</td></tr><tr><th>Approved envelope</th><td>≈428 GPU-hours</td><td>Approximate; excludes queue time.</td></tr><tr><th>Compute-only wall time</th><td>≈107 h on 4 GPUs / ≈428 h on 1 GPU</td><td>Assumes useful parallel scaling; actual throughput is measured in G1.1.</td></tr><tr><th>End-to-end calendar</th><td>≈10–14 researcher-weeks</td><td>Includes engineering, paired-style audit, reruns, and evidence checks.</td></tr></tbody></table></div><p class="notice"><strong>图表覆盖：7/7</strong> — F1, F2, F3, F4, T1, T2, T3. Estimates are approximate and must be revised from measured smoke throughput.</p></section>
    <section data-report-section="implementation-sources"><h2>2. Implementation Sources</h2><div class="table-wrap"><table><thead><tr><th>Method</th><th>How it is implemented</th></tr></thead><tbody>{''.join(impl_rows)}</tbody></table></div></section>
    <section data-report-section="artifact-coverage"><h2>3. Figure/Table Coverage</h2><p>每个批准图表至少有一个拥有它的 Goal；非实验图不会获得数值采集合同。</p><ul class="coverage">{coverage_items}</ul></section>
    {parts_html}
    <script type="application/json" id="run-plan-state">{state_json}</script></main></body></html>'''
    RUNPLAN.write_text(run_html, encoding="utf-8")

    if not LEDGER.exists():
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("w", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerow(LEDGER_COLUMNS)

    # Pending paper-shaped result counterpart.
    pending_sections = []
    for artifact in contract["paper_artifacts"]:
        aid = artifact["id"]
        shell = artifact["shell"]
        if aid == "F1":
            pending_sections.append('<section class="concept-figure" data-artifact-id="F1"><h3>F1 · Motivation figure</h3><p>非实验图，仅计数；由 paperwrite/figureppt 根据已批准规格绘制，目前状态 PENDING。</p></section>')
        elif artifact["kind"] == "figure":
            cells = [cid for req in contract["result_requirements"] if req["artifact_id"]==aid for cid in req["cell_ids"]]
            cell_set = " ".join(cells)
            panel_tables = []
            for panel in figure_schema["figures"][aid]:
                approved = next(x for x in shell["required_data"] if x["panel"]==panel["panel"])
                ids_iter = iter(approved["cell_ids"])
                headers = "".join(f'<th>{html.escape(name)}</th>' for name in panel["series"])
                rows = []
                for x in panel["x_values"]:
                    values = "".join(f'<td class="pending" data-target-id="{next(ids_iter)}">[PENDING]</td>' for _ in panel["series"])
                    rows.append(f'<tr><th>{html.escape(str(x))}</th>{values}</tr>')
                panel_tables.append(f'<div class="result-panel"><h4>{html.escape(panel["panel"])}</h4><div class="panel-pair"><div><p><strong>Dataset / benchmark:</strong> {html.escape(panel["dataset"])}</p><p><strong>Metric / axes:</strong> {html.escape(panel["metric"])}; {html.escape(panel["x_axis"])} → {html.escape(panel["y_axis"])}.</p><div class="table-wrap"><table><thead><tr><th>{html.escape(panel["x_axis"])}</th>{headers}</tr></thead><tbody>{"".join(rows)}</tbody></table></div></div><div class="empty-plot">PENDING<br>图只会从左侧全部验证后的数字生成</div></div></div>')
            pending_sections.append(f'<section class="figure-result" data-artifact-id="{aid}" data-source-target-ids="{cell_set}"><h3>{aid} · {html.escape(shell["caption"])}</h3>{"".join(panel_tables)}</section>')
        else:
            ids_iter = iter(shell["pending_cell_ids"])
            headers = "".join(f'<th>{html.escape(name)}</th>' for name in shell["column_labels"])
            rows = []
            for row in shell["row_labels"]:
                values = "".join(f'<td class="pending" data-target-id="{next(ids_iter)}">[PENDING]</td>' for _ in shell["column_labels"])
                rows.append(f'<tr><th>{html.escape(row)}</th>{values}</tr>')
            pending_sections.append(f'<section class="table-result" data-artifact-id="{aid}"><h3>{aid} · {html.escape(shell["caption"])}</h3><div class="table-wrap"><table><thead><tr><th>Method / condition</th>{headers}</tr></thead><tbody>{"".join(rows)}</tbody></table></div></section>')

    result_css = css + '.paper-artifact{margin:28px 0}.figure-result,.table-result,.concept-figure{margin:30px 0;padding-top:12px;border-top:3px solid var(--teal)}.panel-pair{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(260px,.9fr);gap:20px}.panel-pair>*{min-width:0}.empty-plot{min-height:250px;border:2px dashed var(--line);display:grid;place-items:center;text-align:center;color:var(--muted);font-weight:800}.pending{color:#9b3c2e;font-weight:850;text-align:center;background:#fff7f3}details{border:1px solid var(--line);padding:10px 14px}@media(max-width:850px){.panel-pair{grid-template-columns:1fr}}'
    results_html = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>I1 Experiment Results</title><style>{result_css}</style></head><body><main><p class="kicker">EXPERIMENT RESULTS · PENDING</p><h1>First-Divergence Repair Evidence</h1>
    <section data-report-section="artifact-completion"><h2>1. Artifact Completion</h2><p><strong>0/7 artifacts complete；0/144 paper-facing numeric targets filled.</strong> F1 awaits the later paper figure stage; every empirical target remains visibly pending until a validated ledger row exists.</p></section>
    <section data-report-section="paper-artifacts"><h2>2. Paper Tables and Figures</h2><p>这些外壳严格保持 03 中批准的行、列、面板、坐标轴与聚合语义；空图不会显示合成预览。</p>{''.join(pending_sections)}</section>
    <section data-report-section="generation-process"><h2>3. 生成过程</h2><details id="result-provenance-index" open><summary>尚无已验证结果</summary><p>当前 ledger 只有规范表头。每个真实数值产生后，页面会在此加入可点击的 raw path、实际命令、代码/配置、计算公式和验证状态。</p></details><script type="application/json" id="result-provenance">{{}}</script></section>
    </main></body></html>'''
    RESULTS.write_text(results_html, encoding="utf-8")


if __name__ == "__main__":
    main()
