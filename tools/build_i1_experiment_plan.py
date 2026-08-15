#!/usr/bin/env python3
"""Build the approved-gate I1 experiment plan with pending empirical cells."""

from __future__ import annotations

import base64
import hashlib
import html
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/03_EXPERIMENT_PLAN.html"
ASSET_ROOT = ROOT / ".agents/skills/expplan/assets"
SCHEMA_REL = "paper/figsrc/first_divergence_repair/figure_schema.json"
FIXTURE_REL = "paper/figsrc/first_divergence_repair/projected_fixture.json"
FIG_SOURCE = "paper/fig/make_figs.py"
FIXTURE_GEN = "paper/figsrc/first_divergence_repair/make_projected_fixture.py"
SCHEMA = json.loads(
    (ASSET_ROOT / "first_divergence_repair/figure_schema.json").read_text(
        encoding="utf-8"
    )
)


URLS = {
    "venue": "https://2027.aclweb.org/",
    "rtv": "https://arxiv.org/abs/2605.03095",
    "abd": "https://aclanthology.org/2025.acl-long.1233/",
    "trajguard": "https://aclanthology.org/2026.findings-acl.655/",
    "jbshield": "https://arxiv.org/abs/2502.07557",
    "jbshield_code": "https://github.com/NISPLab/JBShield",
    "harmbench": "https://github.com/centerforaisafety/HarmBench",
    "advbench": "https://github.com/llm-attacks/llm-attacks/blob/main/data/advbench/harmful_behaviors.csv",
    "sorry": "https://github.com/SORRY-Bench/sorry-bench",
    "xstest": "https://github.com/paul-rottger/exaggerated-safety",
    "justeval": "https://github.com/Re-Align/just-eval",
    "alpaca": "https://github.com/tatsu-lab/stanford_alpaca",
}


def pending(cell_id: str) -> str:
    return f'<td class="pending" data-target-id="{cell_id}">[PENDING]</td>'


def encode_png(path: str) -> str:
    return base64.b64encode((ROOT / path).read_bytes()).decode("ascii")


def figure_panel_html(figure: str, panel: dict) -> tuple[str, list[str]]:
    slug = panel["panel"]
    cell_ids = []
    headers = "".join(f"<th>{html.escape(name)}</th>" for name in panel["series"])
    rows = []
    for i, x in enumerate(panel["x_values"]):
        value_cells = []
        for s, _name in enumerate(panel["series"]):
            cid = f"{figure.lower()}-{slug}-{i:02d}-{s:02d}"
            cell_ids.append(cid)
            value_cells.append(pending(cid))
        rows.append(f'<tr class="plot-point"><th>{html.escape(str(x))}</th>{"".join(value_cells)}</tr>')
    png_rel = f"paper/fig/first_divergence_repair/projected/{figure}_{slug}.png"
    block = f'''
    <section class="panel-pair">
      <div class="required-data figure-source-data">
        <p><strong>Dataset / benchmark:</strong> {html.escape(panel["dataset"])} · <a href="{URLS["harmbench"]}">HarmBench 1.0</a> · <a href="{URLS["advbench"]}">AdvBench 50-behavior subset</a> · <a href="{URLS["xstest"]}">XSTest</a></p>
        <p><strong>Metric / axes:</strong> {html.escape(panel["metric"])}; x = {html.escape(panel["x_axis"])}; y = {html.escape(panel["y_axis"])}.</p>
        <p><strong>Required fields:</strong> <code>{html.escape(", ".join(panel["required_fields"]))}</code>. Aggregation: {html.escape(panel["aggregation"])}.</p>
        <div class="table-wrap"><table><thead><tr><th>{html.escape(panel["x_axis"])}</th>{headers}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>
      </div>
      <div class="projected-preview"><img alt="{figure} {html.escape(slug)} projected preview" src="data:image/png;base64,{encode_png(png_rel)}"><p>PROJECTED SHAPE — NOT RESULTS；左表才是后续实验必须填入的真实数字来源。</p></div>
    </section>'''
    return block, cell_ids


def figure_shell_html(figure: str, title: str) -> tuple[str, list[str], list[dict]]:
    panels_html, cells, required_data = [], [], []
    for panel in SCHEMA["figures"][figure]:
        block, ids = figure_panel_html(figure, panel)
        panels_html.append(block)
        cells.extend(ids)
        required_data.append({
            "panel": panel["panel"],
            "fixture_key": panel["fixture_key"],
            "cell_ids": ids,
            "required_fields": panel["required_fields"],
        })
    return (
        f'<div class="shell projected-figure"><div class="shell-title">{figure} · {html.escape(title)}</div>{"".join(panels_html)}</div>',
        cells,
        required_data,
    )


def result_table_html(aid: str, title: str, rows: list[str], columns: list[str], note: str) -> tuple[str, list[str]]:
    ids, body = [], []
    for r, label in enumerate(rows):
        values = []
        for c, _column in enumerate(columns):
            cid = f"{aid.lower()}-{r:02d}-{c:02d}"
            ids.append(cid)
            values.append(pending(cid))
        body.append(f"<tr><th>{html.escape(label)}</th>{''.join(values)}</tr>")
    header = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    block = f'''<div class="shell result-table-shell"><div class="shell-title">{aid} · {html.escape(title)}</div>
    <p class="warning">RESULT PLACEHOLDER — NO NUMBERS FABRICATED</p>
    <div class="table-wrap"><table><thead><tr><th>Method / condition</th>{header}</tr></thead><tbody>{''.join(body)}</tbody></table></div>
    <p>{note} Dataset sources: <a href="{URLS["advbench"]}">AdvBench 50-behavior subset</a>, <a href="{URLS["harmbench"]}">HarmBench 1.0</a>, <a href="{URLS["xstest"]}">XSTest</a>, and <a href="{URLS["justeval"]}">Just-Eval</a>.</p></div>'''
    return block, ids


def metric(mid: str, name: str, provenance: str, definition: str, range_: str, construct: str, claims: list[tuple[str, str]], cannot: str, alternatives: list[str], companions: list[str], url: str) -> dict:
    return {
        "id": mid, "name": name, "provenance": provenance, "definition": definition,
        "range": range_, "decision_rule": "Freeze computation before final acquisition; report prompt-bootstrap 95% CI.",
        "aggregation": "Macro-average by intent family, then model; paired prompt bootstrap 95% CI.",
        "url": url, "construct": construct,
        "claim_mappings": [{"claim_id": cid, "measurement_role": role, "cannot_establish": cannot, "companion_requirements": companions} for cid, role in claims],
        "cannot_establish": cannot, "alternative_explanations": alternatives, "companion_requirements": companions,
    }


def plotting_python() -> str:
    """Return an available interpreter that satisfies the locked plotting stack."""
    candidates = [sys.executable, shutil.which("python3.12"), shutil.which("python3")]
    for candidate in dict.fromkeys(item for item in candidates if item):
        check = subprocess.run(
            [candidate, "-c", "import matplotlib, numpy"],
            capture_output=True,
            text=True,
        )
        if check.returncode == 0:
            return candidate
    raise RuntimeError(
        "No Python interpreter with the locked matplotlib/numpy dependencies is "
        "available; install requirements.lock before building the experiment plan."
    )


def materialize_projected_assets() -> None:
    """Create every Expplan-owned preview input/output from tracked skill assets."""
    schema_path = ROOT / SCHEMA_REL
    fixture_generator = ROOT / FIXTURE_GEN
    figure_source = ROOT / FIG_SOURCE
    fixture_path = ROOT / FIXTURE_REL
    for source, target in (
        (ASSET_ROOT / "first_divergence_repair/figure_schema.json", schema_path),
        (ASSET_ROOT / "first_divergence_repair/make_projected_fixture.py", fixture_generator),
        (ASSET_ROOT / "make_figs.py", figure_source),
    ):
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    python = plotting_python()
    subprocess.run(
        [
            python,
            str(fixture_generator),
            "--schema",
            str(schema_path),
            "--output",
            str(fixture_path),
            "--source-schema",
            SCHEMA_REL,
        ],
        check=True,
    )
    for figure, panels in SCHEMA["figures"].items():
        for panel in panels:
            stem = ROOT / f"paper/fig/first_divergence_repair/projected/{figure}_{panel['panel']}"
            subprocess.run(
                [
                    python,
                    str(figure_source),
                    "--schema",
                    str(schema_path),
                    "--figure",
                    figure,
                    "--panel",
                    panel["panel"],
                    "--metrics",
                    str(fixture_path),
                    "--pdf",
                    str(stem.with_suffix(".pdf")),
                    "--png",
                    str(stem.with_suffix(".png")),
                ],
                check=True,
            )


def main() -> None:
    materialize_projected_assets()
    f2_html, f2_cells, f2_data = figure_shell_html("F2", "Where the safety trajectory first leaves its tube")
    f3_html, f3_cells, f3_data = figure_shell_html("F3", "Does one repair restore the downstream trajectory?")
    f4_html, f4_cells, f4_data = figure_shell_html("F4", "Repair-strength safety–utility sensitivity")

    methods = ["No Defense", "ABD", "RTV", "JBShield", "TrajGuard", "First-Divergence Repair"]
    t1_cols = ["AdvBench DSR ↑ (%, 95% CI)", "HarmBench DSR ↑ (%, 95% CI)", "XSTest false refusal ↓ (%, 95% CI)", "Just-Eval retention ↑ (%, 95% CI)"]
    t1_html, t1_cells = result_table_html("T1", "Main safety–utility comparison", methods, t1_cols, "Every row is rerun locally under one decoding and judge contract; no published number is reused.")
    ablations = ["Full first-exit repair", "Random layer", "ABD-selected layer", "Latest-exit layer", "Repeated multi-layer repair"]
    t2_cols = ["First-exit stability ↑", "Downstream recovery ↑", "HarmBench DSR ↑", "XSTest false refusal ↓"]
    t2_html, t2_cells = result_table_html("T2", "Single-site causal ablation matrix", ablations, t2_cols, "The decisive comparison is full repair versus random, ABD-selected, latest-exit, and repeated-repair controls.")
    t3_cols = ["Latency overhead ↓ (ms/query)", "Peak memory overhead ↓ (GiB)", "Unrecovered cases ↓ (%, 95% CI)"]
    t3_html, t3_cells = result_table_html("T3", "Efficiency and failure surface", methods, t3_cols, "Failure cases are categorized after metrics are frozen; the table does not convert qualitative causes into fabricated scores.")

    baselines = [
        {"id":"B1","name":"No Defense","url":"","family":"LLM-based","tags":["control"],"grounded_support":["ABD","RTV","TrajGuard"],"frequency":3,"scientific_role":"direct control","protocol_compatibility":"full","code_availability":"native model inference","reproduction_burden":"low","inclusion_rationale":"Measures the untreated failure trajectory."},
        {"id":"B2","name":"ABD","url":URLS["abd"],"family":"LLM-based","tags":["representation intervention"],"grounded_support":["ABD primary reference"],"frequency":1,"scientific_role":"researcher-owned must-cover floor","protocol_compatibility":"full after local reimplementation","code_availability":"paper only","reproduction_burden":"medium","inclusion_rationale":"Direct layer-selective intervention floor."},
        {"id":"B3","name":"RTV","url":URLS["rtv"],"family":"LLM-based","tags":["trajectory detection"],"grounded_support":["RTV"],"frequency":1,"scientific_role":"closest external mechanism","protocol_compatibility":"full after local reimplementation","code_availability":"announced after review","reproduction_burden":"high","inclusion_rationale":"Closest multi-layer trajectory competitor."},
        {"id":"B4","name":"JBShield","url":URLS["jbshield"],"family":"LLM-based","tags":["concept detection","activation manipulation"],"grounded_support":["JBShield","RTV"],"frequency":2,"scientific_role":"source-available representation baseline","protocol_compatibility":"mixed-input gate must be restored","code_availability":"official MIT repository","reproduction_burden":"medium","inclusion_rationale":"Tests whether concept manipulation already explains the gains."},
        {"id":"B5","name":"TrajGuard","url":URLS["trajguard"],"family":"LLM-based","tags":["trajectory guard"],"grounded_support":["TrajGuard"],"frequency":1,"scientific_role":"recent trajectory SOTA","protocol_compatibility":"full after local reimplementation","code_availability":"no official code found","reproduction_burden":"high","inclusion_rationale":"Tests whether trajectory-wide guarding dominates one-shot repair."},
    ]
    shared_boundary = "Local unified ModelAdapter, DatasetRecord, TraceRecorder, evaluator, and JSONL result contract."
    implementation = [
        {"method":"No Defense","display_name":"No Defense","implementation_summary":"Implement this control in the shared local framework by running the common generation path with every defense disabled.","mode":"SELF_IMPLEMENT","source_kind":"LOCAL","source_label":"Implemented locally","source_url":"","paper_url":"","repository_status":"not applicable","upstream_reuse":"None.","local_implementation":"Write the disabled-defense adapter and use the exact shared generation path.","shared_boundary":shared_boundary,"fallback":"Not applicable; this is the local control."},
        {"method":"ABD","display_name":"ABD","implementation_summary":"Implement ABD in the shared local framework: safety-boundary estimation, penalty, and layer selection use the common hooks.","mode":"SELF_IMPLEMENT","source_kind":"LOCAL","source_label":"Implemented locally","source_url":"","paper_url":URLS["abd"],"repository_status":"No official repository is used.","upstream_reuse":"None.","local_implementation":"Implement safety-boundary estimation, penalty, and layer selection inside the common hooks.","shared_boundary":shared_boundary,"fallback":"If a later official repository is considered, return for repository-contract approval before using it."},
        {"method":"RTV","display_name":"RTV","implementation_summary":"Implement RTV in the shared local framework: refusal-direction fingerprints and multi-layer Mahalanobis trajectory scoring use the common trace hooks.","mode":"SELF_IMPLEMENT","source_kind":"LOCAL","source_label":"Implemented locally","source_url":"","paper_url":URLS["rtv"],"repository_status":"No official repository is used.","upstream_reuse":"None.","local_implementation":"Implement refusal-direction fingerprints and multi-layer Mahalanobis trajectory scoring.","shared_boundary":shared_boundary,"fallback":"Follow the frozen scientific specification and report any unresolved detail as a limitation."},
        {"method":"JBShield","display_name":"JBShield","implementation_summary":"Integrate the official NISPLab/JBShield concept extraction, scoring, and mitigation modules into the shared local framework through a local adapter, with mixed-input gating restored.","mode":"SOURCE_GUIDED_REIMPLEMENT","source_kind":"OFFICIAL_GITHUB","source_label":"Official NISPLab/JBShield GitHub","source_url":URLS["jbshield_code"],"paper_url":URLS["jbshield"],"repository_status":"Official USENIX Security 2025 artifact; pin and smoke-test before reuse.","repository_id":"R2","upstream_reuse":"Reuse concept extraction, scoring, and mitigation logic from the pinned official repository.","local_implementation":"Write a thin adapter to the common model/data/evaluator interfaces and restore mixed-input detection gating.","shared_boundary":shared_boundary,"fallback":"If the pinned code fails compatibility checks, reimplement only the approved modules from the paper and recorded source locations."},
        {"method":"TrajGuard","display_name":"TrajGuard","implementation_summary":"Implement TrajGuard in the shared local framework: sliding-window hidden-state aggregation, persistence thresholding, and semantic adjudication use the common trace and evaluator hooks.","mode":"SELF_IMPLEMENT","source_kind":"LOCAL","source_label":"Implemented locally","source_url":"","paper_url":URLS["trajguard"],"repository_status":"No official repository is used.","upstream_reuse":"None.","local_implementation":"Implement sliding-window hidden-state aggregation, persistence thresholding, and semantic adjudication.","shared_boundary":shared_boundary,"fallback":"Follow the frozen scientific specification and mark unresolved details explicitly."},
        {"method":"First-Divergence Repair","display_name":"Our method — First-Divergence Repair","implementation_summary":"Implement our method in the same shared local framework: first-exit localization, one-shot repair, downstream recovery, and instrumentation use the common model, trace, generation, and evaluator interfaces.","mode":"SELF_IMPLEMENT","source_kind":"LOCAL","source_label":"Implemented locally","source_url":"","paper_url":URLS["rtv"],"repository_status":"New project method.","upstream_reuse":"No baseline code; RTV is scientific grounding only.","local_implementation":"Write first-exit localization, one-shot repair, downstream recovery, and their instrumentation.","shared_boundary":shared_boundary,"fallback":"Stop or narrow the claim if the local mechanism fails its preregistered checks."},
    ]
    metrics = [
        metric("M1","First-exit stability","PROPOSED matched-counterfactual diagnostic","Fraction of paired style variants whose first tube-exit falls within one normalized-depth bin.","0–1","style-invariant localization",[("C1","DIRECT")],"Does not by itself establish causal sufficiency.",["token alignment artifact","probe calibration drift"],["wrong-layer intervention","paired semantic audit"],URLS["rtv"]),
        metric("M2","Downstream trajectory recovery","Adapted from representation-trajectory comparison","Cosine similarity to the safe-reference trajectory after the intervention layer.","−1–1","geometric recovery",[("C2","PROXY")],"Similarity alone cannot establish safe behavior.",["representation rotation without behavioral change"],["DSR","wrong-layer control"],URLS["rtv"]),
        metric("M3","Defense Success Rate (DSR)","ABD protocol","One minus harmful-compliance rate under the frozen safety judge.","0–100%","behavioral safety",[("C2","DIRECT"),("C3","DIRECT")],"Judge agreement is not a proof of harmlessness.",["judge error","attack invalidity"],["SORRY-Bench judge","manual audit sample"],URLS["abd"]),
        metric("M4","XSTest false-refusal rate","XSTest protocol","Fraction of clearly safe XSTest prompts refused by the model.","0–100%","over-refusal",[("C3","DIRECT")],"Does not cover all benign utility.",["prompt-format mismatch"],["Just-Eval retention"],URLS["xstest"]),
        metric("M5","Just-Eval retention","Just-Eval protocol","Defense-on multi-aspect score divided by no-defense score.","0–1+","general response quality",[("C3","DIRECT")],"LLM-judge score is not task-complete utility.",["judge preference bias","length bias"],["XSTest false-refusal rate"],URLS["justeval"]),
        metric("M6","Latency overhead","Local wall-clock instrumentation","Median defended minus undefended milliseconds per query under synchronized inference.","≥0 ms/query","deployment cost",[("C3","DIRECT")],"Does not establish throughput under every serving stack.",["kernel warm-up","batch-size interaction"],["peak-memory overhead"],URLS["jbshield"]),
    ]

    claims = [
        {"id":"C1","claim":"Matched intent-preserving style transformations produce a reproducible earliest safety-tube exit rather than diffuse trajectory drift.","falsifier":"First-exit depth is unstable across paraphrases, seeds, or models beyond the preregistered tolerance.","requires_formal_check":False,"measurement_contract":{"construct_definition":"A style-invariant earliest transition out of the calibrated safe trajectory tube.","primary_observable":"paired first_exit_layer records","metric_ids":["M1"],"measurement_role":"DIRECT","cannot_establish":"Causal sufficiency.","alternative_explanations":["alignment artifact","threshold instability"],"required_controls":["semantic equivalence audit","token alignment ablation"],"support_pattern":"High paired stability and concentration before harmful compliance.","weaken_pattern":"Model-specific but repeatable exits.","falsify_pattern":"No concentration or instability beyond tolerance.","uncertainty_rule":"Paired bootstrap 95% CI over intent families."}},
        {"id":"C2","claim":"Repairing only the first-exit layer is causally sufficient to recover downstream safety geometry and reduce harmful compliance.","falsifier":"Random, ABD-selected, later, or repeated multi-layer repair matches or exceeds first-exit repair, or downstream recovery does not occur.","requires_formal_check":False,"measurement_contract":{"construct_definition":"Unique single-site causal sufficiency of the first divergence.","primary_observable":"intervention-indexed trajectory and judge records","metric_ids":["M2","M3"],"measurement_role":"PROXY_WITH_COMPANION","cannot_establish":"Geometry alone cannot prove causal safety.","alternative_explanations":["generic activation damping","decoding perturbation"],"required_controls":["behavioral DSR","wrong-layer interventions","strength-matched controls"],"support_pattern":"First-exit repair uniquely restores geometry and DSR.","weaken_pattern":"First-exit is best but not unique.","falsify_pattern":"Other layers match it or repeated repairs are necessary.","uncertainty_rule":"Paired bootstrap 95% CI and seed-wise consistency."}},
        {"id":"C3","claim":"The one-shot repair improves the safety–utility–cost frontier over representation-level baselines.","falsifier":"No simultaneous DSR gain without worse XSTest, Just-Eval, or latency at matched conditions.","requires_formal_check":False,"measurement_contract":{"construct_definition":"Pareto improvement in behavioral safety, benign handling, response quality, and serving overhead.","primary_observable":"per-prompt judge labels, quality scores, and timed inference","metric_ids":["M3","M4","M5","M6"],"measurement_role":"DIRECT","cannot_establish":"Performance outside approved models and datasets.","alternative_explanations":["judge bias","different generation lengths"],"required_controls":["common decoding","common evaluator","No Defense"],"support_pattern":"Non-dominated safety–utility point with lower or comparable cost.","weaken_pattern":"Safety gain with a small bounded trade-off.","falsify_pattern":"Dominated by a selected baseline.","uncertainty_rule":"Prompt bootstrap 95% CI; latency median and IQR."}},
    ]

    variables = [
        {"id":"V1","name":"first-exit layer","status":"PROPOSED","used_in":["C1","C2"],"purpose":"localize earliest tube exit","source":"adapted from RTV trajectories","required_observable":"layer activations and calibrated safe tube","available_now":True,"fallback_or_proxy":"normalized depth bin","raw_field":"first_exit_layer","evidence_grade":"direct diagnostic"},
        {"id":"V2","name":"safe-reference similarity","status":"ADAPTED","used_in":["C2"],"purpose":"measure downstream geometric recovery","source":"trajectory similarity literature","required_observable":"paired safe reference activations","available_now":True,"fallback_or_proxy":"centered cosine similarity","raw_field":"safe_reference_similarity","evidence_grade":"proxy with DSR companion"},
        {"id":"V3","name":"style equivalence","status":"PROPOSED","used_in":["C1","C2"],"purpose":"hold harmful intent fixed while style changes","source":"matched counterfactual construction","required_observable":"intent_id, style_id, semantic and harmfulness audit","available_now":False,"fallback_or_proxy":"dual-judge plus human audit subset","raw_field":"equivalence_pass","evidence_grade":"construction validity"},
        {"id":"V4","name":"repair strength","status":"PROPOSED","used_in":["C2","C3"],"purpose":"dose the one-shot state correction","source":"adapted from activation steering","required_observable":"intervention norm and output","available_now":True,"fallback_or_proxy":"norm-matched displacement","raw_field":"repair_strength","evidence_grade":"intervention variable"},
    ]

    experiments = []
    for eid, name, vars_, repo, compute in [
        ("E0","Instrumentation sanity",["V1","V2"],"local unified framework","4 GPU-hours"),
        ("E1","First-exit diagnosis",["V1","V3"],"R1/R4/R6 data authority","48 GPU-hours"),
        ("E2","Main comparison",["V1","V4"],"R1/R3/R5 evaluator authority","160 GPU-hours"),
        ("E3","Causal repair offsets",["V1","V2","V4"],"local unified framework","64 GPU-hours"),
        ("E4","Ablation matrix",["V1","V2","V4"],"local unified framework","72 GPU-hours"),
        ("E5","Strength/model sensitivity",["V4"],"local unified framework","48 GPU-hours"),
        ("E6","Efficiency and failure analysis",["V1","V4"],"R3/R5 evaluator authority","32 GPU-hours"),
    ]:
        experiments.append({"id":eid,"name":name,"variable_ids":vars_,"raw_fields":["model_id","prompt_id","intent_id","style_id","layer_id","seed","judge_label","latency_ms"],"computation":"Use table-defined dataset/metric semantics and paired aggregation.","uncertainty":"Prompt bootstrap 95% CI unless the metric contract specifies median/IQR.","authorized_decisions":["D1","D2","D3","D4","D5","D6","D7"],"repository_authority":repo,"estimated_compute":compute,"source_action":"RUN_LOCAL"})

    decisions = []
    decision_specs = [
        ("D1","target models","FIXED_BY_DESIGN",["Llama-3.1-8B-Instruct","Mistral-7B-Instruct-v0.3","Qwen2.5-7B-Instruct"],"Three 7–8B white-box families fit 4×A100.","before instrumentation"),
        ("D2","style families","FIXED_BY_DESIGN",["persona","narrative","register/persuasion","encoding","language"],"Chosen to span the confirmed style scope.","before counterfactual construction"),
        ("D3","safety-tube threshold","SEARCHED",["calibration quantiles 0.90","0.95","0.975","0.99"],"Select by bounded benign calibration observable.","after calibration, before diagnosis"),
        ("D4","repair strength","SEARCHED",[0.25,0.5,0.75,1.0,1.25],"Select the smallest strength meeting the frozen safety criterion.","before main comparison"),
        ("D5","token alignment","FIXED_BY_DESIGN",["last-user-token","semantic-span pooling"],"Report both to expose alignment artifacts.","before instrumentation"),
        ("D6","decoding","FIXED_BY_SOURCE",["temperature=0","max_new_tokens=256"],"Common deterministic decoding for all methods.","before generation"),
        ("D7","safety judge","FIXED_BY_SOURCE",["SORRY-Bench ft-Mistral judge","HarmBench classifier cross-check"],"Use official protocols and adjudicate disagreements on an audit sample.","before evaluation"),
    ]
    for did, var, disposition, values, rule, freeze in decision_specs:
        decisions.append({"id":did,"experiment_ids":[e["id"] for e in experiments] if experiments else ["E0","E1","E2","E3","E4","E5","E6"],"decision_variable":var,"disposition":disposition,"allowed_values":values,"source":"approved design or grounded source","selection_rule":rule,"selection_observable":"calibration-only observable; never final-result access","budget":"bounded by listed values","freeze_point":freeze,"final_value_source":"runplan acquisition ledger","test_access_prohibited":True})

    # The loop above is built before experiments is populated in ordinary Python execution,
    # so normalize experiment coverage after creating both records.
    for decision in decisions:
        decision["experiment_ids"] = [item["id"] for item in experiments]

    repositories = [
        ("R1","centerforaisafety/HarmBench",URLS["harmbench"],"VERIFY_AND_USE","data/preprocessing; evaluator protocol","MIT; 8e1604d1171fe8a48d8febecd22f600e462bdcdd","vLLM, transformers, spaCy","attack-centric pipeline; import-time spaCy model"),
        ("R2","NISPLab/JBShield","https://github.com/NISPLab/JBShield","REFERENCE_ONLY","baseline implementation reference","MIT; 8b96f00d15647ad9e729635384ac3e705dcae032","transformers, FastChat","hard-coded model paths and all-jailbreak shortcut"),
        ("R3","SORRY-Bench/sorry-bench",URLS["sorry"],"VERIFY_AND_USE","evaluator/metric protocol","MIT; 7da10addffb6790cfeb75281eaffb5a176861653","FastChat, vLLM","fixed file layout and API clients"),
        ("R4","paul-rottger/exaggerated-safety",URLS["xstest"],"VERIFY_AND_USE","data/preprocessing","MIT; d7bb5bd738c1fcbc36edd83d5e7d1b71a3e2d84d","pandas; optional OpenAI script","legacy global OpenAI API usage"),
        ("R5","Re-Align/just-eval",URLS["justeval"],"VERIFY_AND_USE","evaluator/metric protocol","Apache-2.0; 3e1a1265e210be1d6ad71624c91da3efc36493ca","openai, datasets","global API state and provider coupling"),
        ("R6","tatsu-lab/stanford_alpaca",URLS["alpaca"],"VERIFY_AND_USE","data/preprocessing","Apache-2.0 code; CC BY-NC 4.0 data; 761dc5bfbdeeffa89b8bff5d038781a4055f796a","transformers; legacy OpenAI generator","non-commercial data and stale generation code"),
    ]
    repo_contract = []
    for rid, name, url, mode, scope, license_rev, deps, risk in repositories:
        repo_contract.append({"id":rid,"name":name,"url":url,"use_mode":mode,"allowed_scope":scope,"prohibited_scope":"May not replace the local unified execution/result contract.","integration_target":"adapter or frozen source asset","precedence":"approved experiment contract first; original dataset labels next","verification_checklist":["pin revision","inspect license/dependencies","smallest smoke test","record reused files"],"fallback":"local schema-compatible reimplementation from the approved paper/protocol","discovery_source":"paper/project official link","provenance_status":"official or author-provided","priority":"Preferred" if rid != "R6" else "Supplementary","verification_status":"paper-linked; not verified runnable","license_revision":license_rev,"dependencies":deps,"compatibility_risk":risk})

    artifacts = []
    artifacts.append({"id":"F1","kind":"figure","label":"fig:motivation","span":"single_column","placement":"body","supports":["C1"],"section_id":"introduction","dimensions":["matched intent","style","depth"],"visible_dimensions":["matched intent","style","depth"],"introduced_after":"I-P3","shell":{"data_driven":False,"rhetorical_role":"motivation","caption":"Same harmful intent, different style, first divergent depth highlighted."}})
    plotting_common = {"source":FIG_SOURCE,"schema":SCHEMA_REL,"fixture_generator":FIXTURE_GEN,"fixture":FIXTURE_REL}
    for aid, title, supports, section_id, introduced, data, first_panel in [
        ("F2","First-exit localization",["C1"],"observation","O-P2",f2_data,"exit_depth"),
        ("F3","Single-site causal recovery",["C2"],"experiments","E-P2",f3_data,"repair_offset"),
        ("F4","Repair-strength sensitivity",["C3"],"experiments","E-P5",f4_data,"repair_strength"),
    ]:
        panels = {}
        for item in data:
            slug = item["panel"]
            panels[slug] = {"pdf":f"paper/fig/first_divergence_repair/projected/{aid}_{slug}.pdf","png":f"paper/fig/first_divergence_repair/projected/{aid}_{slug}.png"}
        plot = dict(plotting_common)
        plot.update({"pdf":panels[first_panel]["pdf"],"png":panels[first_panel]["png"],"panels":panels})
        artifacts.append({"id":aid,"kind":"figure","label":f"fig:{aid.lower()}-i1","span":"double_column","placement":"body","supports":supports,"section_id":section_id,"dimensions":["dataset","model","condition","depth"],"visible_dimensions":["dataset","model","condition","depth"],"introduced_after":introduced,"shell":{"data_driven":True,"caption":title,"panels":[x["panel"] for x in data],"axes_legend":"Frozen in figure schema","source_variables":["V1","V2","V4"],"aggregation":"Prompt-level paired bootstrap 95% CI","required_data":data,"plotting":plot}})
    for aid, title, supports, section_id, introduced, rows, cols, cells, label in [
        ("T1","Main safety–utility comparison",["C2","C3"],"experiments","E-P3",methods,t1_cols,t1_cells,"tab:main-results"),
        ("T2","Single-site causal ablation matrix",["C2"],"experiments","E-P4",ablations,t2_cols,t2_cells,"tab:causal-ablation"),
        ("T3","Efficiency and failure surface",["C3"],"experiments","E-P6",methods,t3_cols,t3_cells,"tab:efficiency-failure"),
    ]:
        shell = {"caption":title,"row_labels":rows,"column_labels":cols,"dataset_bearing_headers":["AdvBench","HarmBench","XSTest","Just-Eval"],"metric_uncertainty":"Prompt-bootstrap 95% CI; median/IQR for latency","pending_cell_ids":cells}
        if aid == "T2": shell["required_visible_tokens"] = ablations
        artifacts.append({"id":aid,"kind":"table","label":label,"span":"double_column","placement":"body" if aid != "T3" else "body_or_appendix","supports":supports,"section_id":section_id,"dimensions":["dataset","model","method","metric"],"visible_dimensions":["dataset","model","method","metric"],"introduced_after":introduced,"shell":shell})

    paragraphs = [
        ("abstract","Abstract",[
            ("A-P1","The abstract states the style-induced safety failure, the first-exit hypothesis, the single-layer repair, the matched evaluation, and only the results eventually supported by the frozen cells.","summary","C2",[]),
        ]),
        ("introduction","1. Introduction",[
            ("I-P1","Safety-aligned LLMs remain vulnerable when harmful intent is restyled without changing its meaning.","problem","C1",[]),
            ("I-P2","Prior representation defenses detect or reshape broad trajectories but do not identify a unique causal origin of failure.","gap","C1",[]),
            ("I-P3","We ask whether the first depth-wise exit from a calibrated safety tube is the single repair point that restores all downstream computation.","question","C1",["F1"]),
            ("I-P4","Our planned contribution is a falsifiable first-exit diagnostic, one-shot repair, and matched-style evaluation that must beat wrong-layer controls.","contribution","C2",[]),
        ]),
        ("related","2. Related Work",[
            ("R-P1","Behavioral jailbreak transformations motivate holding semantic intent fixed while persona, narrative, register, encoding, and language vary.","context","C1",[]),
            ("R-P2","ABD, JBShield, RTV, and TrajGuard establish the boundary, concept, and trajectory baselines against which uniqueness must be tested.","positioning","C2",[]),
        ]),
        ("observation","3. Locating the First Safety-Trajectory Divergence",[
            ("O-P1","We define the safe trajectory tube from benign and direct-harm calibration traces and define first exit at the earliest violating layer.","definition","C1",[]),
            ("O-P2","Matched counterfactuals test whether successful jailbreaks exhibit a stable, concentrated first exit rather than diffuse drift.","diagnosis","C1",["F2"]),
            ("O-P3","Token-alignment and threshold controls distinguish a genuine depth transition from probe and sequence-length artifacts.","validity","C1",[]),
        ]),
        ("method","4. First-Divergence Repair",[
            ("M-P1","The method receives one prompt trace and returns the earliest tube exit together with its safe-reference displacement.","input-output","C2",[]),
            ("M-P2","A single norm-controlled correction is applied at that layer and nowhere else before generation continues unchanged.","mechanism","C2",[]),
            ("M-P3","Wrong-layer, latest-layer, repeated-repair, and strength-matched controls make uniqueness and sufficiency directly falsifiable.","causal design","C2",[]),
        ]),
        ("experiments","5. Experiments",[
            ("E-P1","Setup uses three open 7–8B models, the confirmed harmful and benign benchmarks, five rerun baselines, common decoding, and frozen judges.","setup","C3",[]),
            ("E-P2","The mechanism test measures whether first-exit repair uniquely restores the safe-reference trajectory downstream.","mechanism result","C2",["F3"]),
            ("E-P3","The main comparison jointly reports DSR, XSTest false refusal, and Just-Eval retention under one local protocol.","main result","C3",["T1"]),
            ("E-P4","The causal ablation matrix removes each claimed source of uniqueness rather than merely tuning components.","ablation","C2",["T2"]),
            ("E-P5","Strength sensitivity tests whether the safety gain survives without collapsing benign handling or response quality.","sensitivity","C3",["F4"]),
            ("E-P6","Efficiency and failure analysis reports latency, memory, and unrecovered cases, with deployment conclusions bounded to the approved stack.","cost and failure","C3",["T3"]),
        ]),
        ("conclusion","6. Conclusion",[
            ("C-P1","The paper will conclude only if one first-exit repair survives the causal controls; otherwise it will report the failed single-origin hypothesis.","closure","C2",[]),
        ]),
        ("limitations","7. Limitations",[
            ("L-P1","The limitations bound the claims to the approved open models, style families, white-box access, evaluators, and the uncertainty of semantic-equivalence judgments.","scope boundary","C3",[]),
        ]),
        ("ethics","8. Ethics Statement",[
            ("H-P1","The ethics statement describes controlled handling of harmful prompts, restricted release of attack material, evaluator limitations, and the intended defensive use.","risk disclosure","C3",[]),
        ]),
        ("appendix","Appendix A. Reproducibility and Extended Results",[
            ("X-P1","The appendix records prompts, frozen configurations, additional uncertainty analyses, provenance, and any body float moved under the approved page-pressure rule.","reproducibility","C3",[]),
        ]),
    ]
    paper_outline = []
    for sid, title, items in paragraphs:
        out = []
        for pid, sentence, role, claim_id, refs in items:
            row = {"id":pid,"plan_sentence":sentence,"reference_anchor":"ABD structure; RTV scientific content","rhetorical_role":role,"supports":[claim_id],"evidence":"planned artifact or grounded argument","transition":"Advances to the next stated need.","length_share":"one focused paragraph","artifact_refs":refs}
            if pid.startswith("M"):
                row.update({"inputs":["layer activations","safe tube","matched intent metadata"],"outputs":["first_exit_layer","repaired activation","generation"],"variable_ids":["V1","V2","V4"],"raw_fields":["layer_id","activation","repair_strength","safe_reference_similarity"],"evidence_grade":"mechanism definition plus causal intervention"})
            out.append(row)
        paper_outline.append({"id":sid,"title":title,"paragraphs":out})

    result_requirements = []
    for rid, aid, cells, eid, supports in [
        ("REQ-F2","F2",f2_cells,"E1",["C1"]),("REQ-F3","F3",f3_cells,"E3",["C2"]),("REQ-F4","F4",f4_cells,"E5",["C3"]),
        ("REQ-T1","T1",t1_cells,"E2",["C2","C3"]),("REQ-T2","T2",t2_cells,"E4",["C2"]),("REQ-T3","T3",t3_cells,"E6",["C3"]),
    ]:
        result_requirements.append({"id":rid,"artifact_id":aid,"cell_ids":cells,"experiment_id":eid,"source_action":"RUN_LOCAL","any_of":[f"results/{eid}.json:records.*"],"supports":supports})

    contract = {
        "schema_version":"1.1","contract_version":1,
        "revision_history":[{"version":1,"changed_at":"2026-08-15","reason":"Regenerate the approved I1 design after removing the disposable Toy workflow and normalize it to the current experiment-plan contract.","changed_fields":["*"],"compatibility":"Scientific scope and the researcher-approved choices from 2026-08-09 are unchanged; downstream artifacts must be regenerated."}],
        "source_plan":"reports/02_IDEA_REPORT.html","approval_status":"approved","generated_at":"2026-08-15",
        "profile_contract":{"profile_path":"researcher-profile/PROFILE.html","publications_path":"researcher-profile/publications.json","researcher_identity":"Xiuying Chen","authorship_verified":True,"structure_reference_key":"gao2024shaping"},
        "target":{"venue":"ACL 2027 Main Conference / Long Paper","track":"Main Conference / Long Paper","cycle":"2027","submission_content_pages":8,"page_rule":"Official 2027 body-length rule is TBA; 8 content pages is a planning assumption and must be replaced when the CFP appears.","official_rules_url":URLS["venue"],"deadline_status":"call_pending","confirmed_at":"2026-08-15"},
        "references":{"confirmed_at":"2026-08-15","external_mechanism":{"title":"Revisiting JBShield: Breaking and Rebuilding Representation-Level Jailbreak Defenses","authors":"Kemal Derya and Berk Sunar","venue":"arXiv 2026","url":URLS["rtv"],"local_full_text":"reports/sources/i1/rtv.txt","role":"scientific-content authority"},"researcher_owned_structure":{"title":"Shaping the Safety Boundaries: Understanding and Defending Against Jailbreaks in Large Language Models","authors":"Gao et al., including Xiuying Chen","venue":"ACL 2025","url":URLS["abd"],"local_full_text":"researcher-profile/fulltext/txt/gao2024shaping.txt","publication_key":"gao2024shaping","role":"structure-only authority"}},
        "dataset_confirmation":{"confirmed":True,"confirmed_at":"2026-08-09"},
        "dataset_citations":[{"name":"AdvBench 50-behavior subset","url":URLS["advbench"]},{"name":"HarmBench 1.0","url":URLS["harmbench"]},{"name":"XSTest","url":URLS["xstest"]},{"name":"Just-Eval","url":URLS["justeval"]},{"name":"Alpaca benign controls","url":URLS["alpaca"]},{"name":"SORRY-Bench evaluator","url":URLS["sorry"]}],
        "grounding":{"selected_idea":"I1 — First-Divergence Repair","proposed_method":"First-Divergence Repair","primary_reference":"ABD","closest_papers":[URLS["rtv"],URLS["trajguard"],URLS["abd"],URLS["jbshield"]],"architecture":"One local unified experiment framework owns model, data, evaluator, trace, intervention, and result interfaces.","architecture_confirmed_at":"2026-08-09"},
        "claims":claims,"variables":variables,
        "baseline_contract":{"confirmed_at":"2026-08-09","result_reuse":"NO_REUSE; every selected method is rerun locally","selected":baselines,"unselected":[]},
        "repository_contract":{"confirmed_at":"2026-08-09","architecture":"unified local framework","primary_base":"local project-owned implementation","references":repo_contract},
        "experiment_contracts":experiments,"metric_contract":metrics,"decision_space_contract":decisions,
        "consistency_requirements":{"canonical_terms":[*[b["id"] for b in baselines],*[m["id"] for m in metrics]],"source_values":[d["id"] for d in decisions],"formal_links":[]},
        "implementation_contract":implementation,"paper_outline":paper_outline,"paper_artifacts":artifacts,
        "float_budget":{"body_figures":4,"body_tables":3,"reference_body_figures":4,"reference_body_tables":3},
        "required_labels":[a["label"] for a in artifacts],"result_requirements":result_requirements,
        "execution_dependency_sketch":["E0 instrumentation sanity","E1 first-exit diagnosis","E2 main comparison","E3 causal offsets","E4 ablation","E5 sensitivity","E6 efficiency/failure"],
        "budget":{"total_gpu_hours":428,"hardware":"4×A100","long_runs_requiring_signoff":["E2 main comparison"]},
    }

    unsigned_contract = {
        key: value for key, value in contract.items()
        if key not in {"approval_status", "approved_at", "approval_channel", "approval_contract_sha256"}
    }
    canonical = json.dumps(unsigned_contract, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    contract["approved_at"] = "2026-08-09"
    contract["approval_channel"] = "researcher conversation"
    contract["approval_contract_version"] = 1
    contract["approval_contract_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    setup_impl_rows = []
    for item in implementation:
        source = (f' <a href="{item["source_url"]}">Official GitHub</a>'
                  if item["source_url"] else '')
        setup_impl_rows.append(
            f'<tr><th>{html.escape(item["display_name"])}</th>'
            f'<td>{html.escape(item["implementation_summary"])}{source}</td></tr>'
        )
    metric_prose = " ".join(f'<a href="{m["url"]}">{html.escape(m["name"])}</a>（{html.escape(m["provenance"]) }）' for m in metrics)
    baseline_links = "、".join((f'<a href="{b["url"]}">{b["name"]}</a>' if b["url"] else b["name"]) for b in baselines)
    setup_html = f'''<h4>5.1 Setup</h4><p>Models are Llama-3.1-8B-Instruct, Mistral-7B-Instruct-v0.3, and Qwen2.5-7B-Instruct. Harmful evaluation uses <a href="{URLS["advbench"]}">AdvBench 50-behavior subset</a> and <a href="{URLS["harmbench"]}">HarmBench 1.0</a>; benign and quality controls use <a href="{URLS["xstest"]}">XSTest</a>, <a href="{URLS["justeval"]}">Just-Eval</a>, and <a href="{URLS["alpaca"]}">Alpaca benign controls</a>; safety judgment uses the <a href="{URLS["sorry"]}">SORRY-Bench evaluator</a>.</p>
    <p>Selected rerun baselines are {baseline_links}. Metrics and provenance are {metric_prose}.</p>
    <div class="table-wrap"><table class="implementation-table"><thead><tr><th>Method</th><th>How it is implemented</th></tr></thead><tbody>{''.join(setup_impl_rows)}</tbody></table></div>'''

    artifact_html = {"F2":f2_html,"F3":f3_html,"F4":f4_html,"T1":t1_html,"T2":t2_html,"T3":t3_html}
    blueprint_parts = []
    for section in paper_outline:
        blueprint_parts.append(f'<h4>{html.escape(section["title"])}</h4>')
        if section["id"] == "experiments": blueprint_parts.append(setup_html)
        blueprint_parts.append('<table class="blueprint"><thead><tr><th>Paragraph</th><th>One-sentence plan</th><th>Artifact</th></tr></thead><tbody>')
        for para in section["paragraphs"]:
            refs = ", ".join(para["artifact_refs"]) or "—"
            blueprint_parts.append(f'<tr><th>{para["id"]}</th><td>{html.escape(para["plan_sentence"])}</td><td>{html.escape(refs)}</td></tr>')
            for ref in para["artifact_refs"]:
                if ref in artifact_html: blueprint_parts.append(f'</tbody></table>{artifact_html[ref]}<table class="blueprint"><tbody>')
        blueprint_parts.append('</tbody></table>')

    claim_rows = "".join(f'<tr><th>{c["id"]}</th><td>{html.escape(c["claim"])}</td><td>{html.escape(c["falsifier"])}</td><td>{html.escape(c["measurement_contract"]["primary_observable"])}</td></tr>' for c in claims)
    ledger_rows = "".join(f'<tr><th>{a["id"]}</th><td>{a["kind"]}</td><td>{html.escape(a["section_id"])}</td><td>{html.escape(", ".join(a["supports"]))}</td><td>{html.escape(a["placement"])}</td></tr>' for a in artifacts)

    css = '''
    :root{--ink:#172a35;--muted:#617681;--teal:#087f74;--line:#cbdad9;--wash:#f4f8f7;--warn:#9b3c2e}*{box-sizing:border-box}body{margin:0;background:white;color:var(--ink);font:17px/1.58 Inter,system-ui,sans-serif}main{max-width:1500px;margin:auto;padding:44px 54px 100px}h1{font:700 42px/1.12 Georgia,serif;margin:5px 0 12px}h2{font:700 30px/1.2 Georgia,serif;margin:54px 0 18px;border-bottom:2px solid var(--teal);padding-bottom:8px}h3{font:700 23px/1.25 Georgia,serif;margin:34px 0 12px}h4{font-size:19px;margin:24px 0 8px}.kicker{letter-spacing:.12em;text-transform:uppercase;color:var(--teal);font-weight:800}.hero{border-left:5px solid var(--teal);padding:8px 24px;background:var(--wash)}a{color:#076e68}.float-budget{font-size:18px;border:2px solid var(--teal);padding:14px 18px;background:#edf8f5;font-weight:800}.table-wrap{overflow:auto;margin:12px 0 20px}table{width:100%;border-collapse:collapse;min-width:760px}th,td{border:1px solid var(--line);padding:11px 12px;text-align:left;vertical-align:top}thead th{background:#eaf3f1}tbody th{background:#f7faf9}.pending{color:var(--warn);font-weight:800;text-align:center;background:#fff7f3}.shell{border-top:3px solid var(--teal);margin:24px 0 34px;padding-top:12px}.shell-title{font:700 21px Georgia,serif}.warning{color:var(--warn);font-weight:800}.panel-pair{display:grid;grid-template-columns:minmax(0,1.08fr) minmax(0,.92fr);gap:22px;align-items:start;margin:18px 0 28px}.panel-pair>*{min-width:0}.projected-preview{border:1px solid var(--line);padding:10px;background:#fff}.projected-preview img{width:100%;max-width:100%;height:auto;display:block}.projected-preview p{font-size:14px;color:var(--muted)}code{font-size:.88em}var{font-family:Georgia,serif;font-style:italic}var sub{font-style:normal;font-size:.72em}.approval{background:#f5f8f7;border:2px solid var(--line);padding:20px}.pill{display:inline-block;border:1px solid var(--teal);color:var(--teal);padding:3px 9px;border-radius:99px;font-weight:800}.budget{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.budget>div{border:1px solid var(--line);padding:15px}@media(max-width:900px){main{padding:28px 18px}.panel-pair,.budget{grid-template-columns:1fr}body{font-size:16px}}
    '''
    contract_json = json.dumps(contract, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    document = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>I1 Experiment Plan</title><style>{css}</style></head><body><main>
    <p class="kicker">EXPERIMENT PLAN · I1 · 2026-08-15</p><h1>First-Divergence Repair</h1><p>从预计论文反推证据：每一个数字都保持待填，每一个图形都绑定旁侧真实数据表。</p>
    <template aria-hidden="true"><h2>1. Target Conference and Reference Papers</h2><div class="hero"><p><strong>Target conference:</strong> <a href="{URLS["venue"]}">ACL 2027</a></p><p><strong>External mechanism reference:</strong> <a href="{URLS["rtv"]}">RTV</a></p><p><strong>Researcher-owned structure reference:</strong> <a href="{URLS["abd"]}">ABD</a></p></div><h2>2. Projected Paper</h2></template>
    <section data-report-section="target-and-references"><h2>1. Target Conference and Reference Papers</h2><div class="hero">
      <p><strong>Target conference:</strong> ACL 2027 Main Conference / Long Paper；官方 2027 页数与截止日期尚未发布（<code>call_pending</code>），当前按 8 个正文内容页规划，提交前必须以 <a href="{URLS["venue"]}">ACL 2027 官方网站</a>更新。</p>
      <p><strong>External mechanism reference:</strong> Derya &amp; Sunar, <a href="{URLS["rtv"]}">Revisiting JBShield: Breaking and Rebuilding Representation-Level Jailbreak Defenses</a>（arXiv 2026），负责科学问题、轨迹机制和必须击败的比较地板。</p>
      <p><strong>Researcher-owned structure reference:</strong> Gao et al., <a href="{URLS["abd"]}">Shaping the Safety Boundaries</a>（ACL 2025；publication key <code>gao2024shaping</code>），只负责段落功能、章节比例和图表节奏。</p>
    </div></section>
    <section data-report-section="projected-paper"><h2>2. Projected Paper</h2><p class="float-budget">图表数量：本计划 7（4 图，3 表） · 参考论文 7（4 图，3 表）</p>
      <section data-report-subsection="projected-title-abstract"><h3>2.1 Projected Title and Abstract</h3><p><strong>Projected title:</strong> First-Divergence Repair: Causal Single-Layer Recovery from Style-Induced Jailbreaks</p><p><strong>PROJECTED abstract:</strong> Safety-aligned language models can respond differently when the same harmful intent is expressed through a new persona, narrative, register, encoding, or language. Existing representation defenses monitor or alter broad activation regions, but they do not establish where a successful style-induced jailbreak first departs from safe computation or whether that origin is sufficient for repair. We study a depth-wise safety trajectory tube calibrated on direct harmful and benign prompts, then define the first exit of each matched style counterfactual. First-Divergence Repair applies one norm-controlled correction only at that layer and leaves subsequent computation unchanged. Across three open 7–8B models, AdvBench, HarmBench, XSTest, and Just-Eval, the planned evaluation compares five rerun baselines under common generation and judging protocols. The central hypothesis is supported only if first exits are stable across matched styles, the proposed intervention improves defense success by [X%] while limiting false-refusal change to [Y%] and retaining [Z%] response quality, and wrong-layer or repeated-repair controls do not explain the same recovery. These tests separate a causal single-origin account from generic multi-layer steering and report latency, memory, and unrecovered cases alongside safety and utility.</p></section>
      <section data-report-subsection="figure-table-count"><h3>2.2 Figure/Table Count</h3><p>4 figures · 3 tables.</p></section>
      <section data-report-subsection="paragraph-blueprint"><h3>2.3 Paragraph Blueprint and Evidence Shells</h3>{''.join(blueprint_parts)}</section>
      <h3>Compact artifact ledger</h3><div class="table-wrap"><table><thead><tr><th>Artifact</th><th>Kind</th><th>Paper section</th><th>Claims</th><th>Placement</th></tr></thead><tbody>{ledger_rows}</tbody></table></div>
      <p><strong>Page-fill feasibility:</strong> seven claim-bearing floats match the structure reference's four-figure/three-table body rhythm and cover diagnosis, mechanism, main comparison, ablation, sensitivity, cost, and failure analysis.</p>
      <section data-report-subsection="claim-falsifier-evidence"><h3>2.4 Claim–Falsifier–Evidence</h3><div class="table-wrap"><table><thead><tr><th>Claim</th><th>Planned statement</th><th>Decisive falsifier</th><th>Primary observable</th></tr></thead><tbody>{claim_rows}</tbody></table></div></section>
      <section data-report-subsection="implementation-plan"><h3>2.5 Implementation Plan</h3><p><span class="pill">Confirmed architecture</span> One local unified framework owns model, paired-data, evaluator, layer×token trace, intervention, and JSONL provenance interfaces.</p>{setup_html}</section>
      <section data-report-subsection="budget-decision-criteria"><h3>2.6 Budget and Decision Criteria</h3><div class="budget"><div><strong>Estimate</strong><br>428 GPU-hours on 4×A100; E2 requires explicit sign-off if projected wall time exceeds one day.</div><div><strong>Continue</strong><br>First-exit localization is stable and first-exit repair uniquely restores both trajectory and DSR.</div><div><strong>Stop or pivot</strong><br>Stop the single-origin claim if exits are unstable, wrong layers tie, or repeated repair is necessary; do not morph it into generic multi-layer steering.</div></div><p>First dependency sequence: instrumentation sanity → first-exit diagnosis → common-protocol main comparison.</p></section>
    </section>
    <section data-report-section="approval"><h2>3. Approval</h2><div class="approval"><p><strong>Status: approved by the researcher on 2026-08-09.</strong></p><p>All observed values remain unfilled. Approval freezes claims, baselines, datasets, metrics, implementation authority, artifact dimensions, and source actions; later experiments may fill only the signed cells.</p><p>The signed contract digest is stored in the embedded machine-readable contract.</p></div></section>
    <script type="application/json" id="experiment-plan-contract">{contract_json}</script>
    </main></body></html>'''
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(document, encoding="utf-8")


if __name__ == "__main__":
    main()
