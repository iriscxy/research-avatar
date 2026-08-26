"""Build an independent I6 experiment plan without touching the canonical I1 plan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "reports/03_EXPERIMENT_PLAN.html"
DEFAULT_OUTPUT = ROOT / "reports/03_EXPERIMENT_PLAN_I6.html"


PLAN_SENTENCES = {
    "A-P1": "Summarize the gap between reward-score disagreement and genuine objective conflict, introduce CRCD, name the two dialogue benchmarks, and state the planned diagnostic and utility tests.",
    "I-P1": "Frame multi-objective dialogue learning as a setting where task success, naturalness, faithfulness, and safety rewards can disagree.",
    "I-P2": "Use a concrete dialogue pair to show that the same reward-score disagreement can arise from evaluator noise or a real behavioral trade-off.",
    "I-P3": "Explain why score correlation and negative gradient cosine alone cannot identify whether changing one objective causes another behavior to degrade.",
    "I-P4": "Preview CRCD as a paired intervention test that combines reward-channel perturbations, gradient traces, and response-level causal effects.",
    "I-P5": "State the planned contributions as a causal diagnostic, a noise-calibrated decision rule, and an evaluation across datasets, models, judges, and intervention strengths.",
    "RW-P1": "Organize prior multi-objective learning methods by scalar weighting, gradient balancing, and Pareto or bargaining updates.",
    "RW-P2": "Review task-oriented dialogue benchmarks and explain which task and response-quality observables they expose.",
    "RW-P3": "Separate work that mitigates gradient conflict from work that tests whether an observed conflict is causal rather than evaluative noise.",
    "M-P1": "Formalize a dialogue context, candidate response set, reward vector, per-reward gradient, and downstream behavioral measurements.",
    "M-P2": "Construct matched reward-channel interventions by shifting one normalized reward while holding candidates, prompts, decoding, and all other channels fixed.",
    "M-P3": "Estimate the direct and cross-objective response effects of each intervention with paired samples and bootstrap confidence intervals.",
    "M-P4": "Calibrate evaluator noise through judge resampling, prompt paraphrases, and label-preserving response perturbations.",
    "M-P5": "Define genuine conflict as replicated negative gradient interaction accompanied by a significant adverse cross-objective behavioral effect beyond the noise envelope.",
    "M-P6": "Aggregate channel-pair evidence into a conflict graph while retaining effect direction, uncertainty, and the cases that remain undecidable.",
    "E-P1": "Specify MultiWOZ 2.2 and SGD, two open instruction models, seven comparison methods, five seeds, paired interventions, and the complete metric set.",
    "E-P2": "Compare CRCD with score-only and gradient-only diagnostics on conflict detection, false positives, behavioral effect recovery, task success, and naturalness.",
    "E-P3": "Test whether conflict decisions transfer across two dialogue datasets, two model families, and two independent reward judges.",
    "E-P4": "Measure sensitivity to intervention strength and identify the range where effects are detectable without leaving the local response neighborhood.",
    "E-P5": "Report compute, memory, judge-call, and wall-clock overhead relative to ordinary multi-objective training diagnostics.",
    "AN-P1": "Ablate behavioral effects, gradient evidence, noise calibration, paired sampling, and replication to identify which components prevent false conflict declarations.",
    "AN-P2": "Measure agreement between CRCD decisions and blinded human judgments of whether an objective trade-off is behaviorally real.",
    "AN-P3": "Analyze conflict graphs by reward pair, domain, model, and judge without interpreting association alone as causation.",
    "AN-P4": "Characterize undecidable and judge-sensitive cases and report how often the method appropriately abstains.",
    "AN-P5": "Use qualitative dialogue cases to contrast a true task-success versus naturalness trade-off with a disagreement caused only by evaluator instability.",
    "C-P1": "Conclude with the bounded claim that paired interventions can distinguish reproducible behavioral conflicts from reward-evaluator noise under the tested dialogue settings.",
}


BASELINES = [
    ("B01", "Equal weighting", "control", "https://papers.neurips.cc/paper_files/paper/2018/hash/432aca3a1e345e339f35a30c8f65edce-Abstract.html"),
    ("B02", "Score correlation", "score-only diagnostic", "https://arxiv.org/abs/1707.06299"),
    ("B03", "GradNorm", "adaptive weighting", "https://proceedings.mlr.press/v80/chen18a.html"),
    ("B04", "MGDA", "Pareto-gradient method", "https://papers.neurips.cc/paper_files/paper/2018/hash/432aca3a1e345e339f35a30c8f65edce-Abstract.html"),
    ("B05", "PCGrad", "gradient surgery", "https://papers.neurips.cc/paper_files/paper/2020/hash/3fe78a8acf5fda99de95303940a2420c-Abstract.html"),
    ("B06", "CAGrad", "conflict-averse update", "https://proceedings.neurips.cc/paper_files/paper/2021/hash/9d27fdf2477ffbff837d73ef7ae23db9-Abstract.html"),
    ("B07", "Nash-MTL", "bargaining update", "https://proceedings.mlr.press/v162/navon22a.html"),
]


METRICS = [
    ("M-CF1", "Conflict F1", "PROPOSED", "F1 over declared conflicting reward pairs against the controlled-intervention reference labels.", "[0,1]", "higher is better", "macro average over reward pairs and seeds", "causal conflict identification"),
    ("M-FPR", "Noise false-positive rate", "PROPOSED", "Fraction of noise-only channel pairs incorrectly declared as genuine conflicts.", "[0,1]", "lower is better", "mean over judge resamples and paraphrase controls", "noise rejection"),
    ("M-ACE", "Cross-objective effect error", "PROPOSED", "Absolute error between estimated and controlled paired average cross-objective response effects.", "non-negative", "lower is better", "mean absolute error with bootstrap interval", "behavioral causal effect recovery"),
    ("M-TS", "Task success", "DIRECT", "Fraction of dialogues that satisfy all database and user-goal constraints.", "[0,1]", "higher is better", "dialogue-level micro average", "task utility"),
    ("M-NAT", "Naturalness", "ADAPTED", "Mean blinded 1-to-5 response naturalness rating with fixed rubric.", "[1,5]", "higher is better", "mean with annotator-clustered confidence interval", "response quality"),
    ("M-COST", "Diagnostic overhead", "DIRECT", "Additional GPU time, peak memory, judge calls, and wall-clock time relative to trace-only diagnostics.", "non-negative", "lower is better at matched evidence coverage", "mean and standard deviation over five seeds", "efficiency"),
    ("M-HA", "Human conflict-label agreement", "PROPOSED", "Agreement between CRCD conflict labels and blinded human conflict labels collected with the registered rubric.", "[0,1]", "higher is better", "Krippendorff alpha plus label agreement with annotator-clustered interval", "human validity"),
]


METRIC_CLAIM_ROLES = {
    "M-CF1": {"C1": "DIRECT", "C3": "DIRECT", "C5": "PROXY"},
    "M-FPR": {"C1": "DIRECT", "C3": "DIRECT", "C4": "PROXY", "C5": "DIRECT"},
    "M-ACE": {"C2": "DIRECT", "C4": "DIRECT"},
    "M-TS": {"C2": "DIRECT"},
    "M-NAT": {"C2": "DIRECT"},
    "M-COST": {"C6": "DIRECT"},
    "M-HA": {"C5": "DIRECT"},
}


METRIC_EXECUTION = {
    "M-CF1": ("DERIVED", "%", ["predicted_conflict", "reference_conflict"], "compute macro F1 from saved pair labels"),
    "M-FPR": ("DERIVED", "%", ["predicted_conflict", "noise_control_label"], "divide false conflict declarations by all noise-only pairs"),
    "M-ACE": ("DERIVED", "reward-score units", ["estimated_effect", "controlled_effect"], "mean absolute paired-effect error"),
    "M-TS": ("BENCHMARK_LABEL", "%", ["dialogue_id", "goal_constraints", "success"], "official MultiWOZ or SGD task-success evaluator"),
    "M-NAT": ("HUMAN_ANNOTATION", "1--5 rating", ["item_id", "annotator_id", "naturalness_rating"], "mean blinded rating with annotator-clustered interval"),
    "M-COST": ("SYSTEM_TRACE", "seconds/GiB/calls", ["runtime_seconds", "peak_memory_gib", "judge_calls"], "report each resource field and matched-coverage relative overhead"),
    "M-HA": ("HUMAN_ANNOTATION", "agreement coefficient", ["item_id", "annotator_id", "human_conflict_label", "system_conflict_label"], "Krippendorff alpha and direct label agreement"),
}


TABLE_SPECS = {
    "T1": {
        "caption": "Main conflict-diagnosis results on MultiWOZ 2.2 and SGD",
        "rows": [name for _, name, _, _ in BASELINES] + ["CRCD"],
        "columns": ["Conflict F1 ↑", "Noise FPR ↓", "Effect error ↓", "Task success ↑", "Naturalness ↑", "Overhead ↓"],
        "datasets": ["MultiWOZ 2.2", "Schema-Guided Dialogue"],
        "supports": ["C1", "C2"],
        "after": "E-P2",
    },
    "T2": {
        "caption": "Cross-model, cross-dataset, and cross-judge robustness",
        "rows": ["Qwen2.5-7B · MultiWOZ", "Qwen2.5-7B · SGD", "Llama-3.1-8B · MultiWOZ", "Llama-3.1-8B · SGD"],
        "columns": ["Judge agreement ↑", "Conflict F1 ↑", "Effect sign agreement ↑", "Abstention rate"],
        "datasets": ["MultiWOZ 2.2", "Schema-Guided Dialogue"],
        "supports": ["C3"],
        "after": "E-P3",
    },
    "T3": {
        "caption": "Sensitivity to reward-channel intervention strength",
        "rows": ["0.25σ", "0.50σ", "0.75σ", "1.00σ", "1.50σ"],
        "columns": ["Detection power ↑", "Noise FPR ↓", "Locality retention ↑", "Effect error ↓"],
        "datasets": ["MultiWOZ 2.2"],
        "supports": ["C4"],
        "after": "E-P4",
    },
    "T4": {
        "caption": "Component ablation and human-validity analysis",
        "rows": ["Full CRCD", "w/o behavioral effect", "w/o gradient evidence", "w/o noise calibration", "w/o paired sampling"],
        "columns": ["Conflict F1 ↑", "Noise FPR ↓", "Human agreement ↑", "Task success ↑", "Naturalness ↑"],
        "datasets": ["MultiWOZ 2.2"],
        "supports": ["C1", "C5"],
        "after": "AN-P1",
    },
}


def make_table(soup: BeautifulSoup, artifact_id: str, spec: dict) -> tuple[object, list[str]]:
    wrapper = soup.new_tag("div", attrs={"class": "shell result-table-shell", "data-artifact-id": artifact_id})
    heading = soup.new_tag("div", attrs={"class": "shell-title"})
    heading.string = f"{artifact_id} · {spec['caption']}"
    wrapper.append(heading)
    note = soup.new_tag("p")
    note.append(BeautifulSoup("<b>RESULT PLACEHOLDER — NO NUMBERS FABRICATED.</b> Datasets: ", "html.parser"))
    for index, dataset in enumerate(spec["datasets"]):
        if index:
            note.append(NavigableString(", "))
        url = "https://aclanthology.org/2020.nlp4convai-1.13/" if dataset in {"MultiWOZ 2.2", "MultiWOZ"} else "https://ojs.aaai.org/index.php/AAAI/article/view/6394"
        link = soup.new_tag("a", href=url)
        link.string = dataset
        note.append(link)
    note.append(NavigableString("."))
    wrapper.append(note)
    table_wrap = soup.new_tag("div", attrs={"class": "table-wrap"})
    table = soup.new_tag("table")
    thead, tr = soup.new_tag("thead"), soup.new_tag("tr")
    for label in ["Method / condition", *spec["columns"]]:
        th = soup.new_tag("th")
        th.string = label
        tr.append(th)
    thead.append(tr)
    table.append(thead)
    tbody = soup.new_tag("tbody")
    cell_ids: list[str] = []
    for row_index, row_name in enumerate(spec["rows"], 1):
        tr = soup.new_tag("tr")
        th = soup.new_tag("th")
        th.string = row_name
        tr.append(th)
        for column_index in range(1, len(spec["columns"]) + 1):
            cell_id = f"{artifact_id.lower()}-r{row_index}-c{column_index}"
            td = soup.new_tag("td", attrs={"class": "pending", "data-target-id": cell_id})
            td.string = "[PENDING]"
            tr.append(td)
            cell_ids.append(cell_id)
        tbody.append(tr)
    table.append(tbody)
    table_wrap.append(table)
    wrapper.append(table_wrap)
    source = soup.new_tag("p", attrs={"class": "muted"})
    source.string = "Datasets: " + ", ".join(spec["datasets"]) + ". Display real mean ± standard deviation or confidence intervals only after validated runs."
    wrapper.append(source)
    return wrapper, cell_ids


def rebuild_visible_html(soup: BeautifulSoup) -> dict[str, list[str]]:
    soup.title.string = "Experiment Plan: CRCD for Causal Reward-Conflict Diagnostics"
    header = soup.select_one("body > header")
    header.select_one(".kicker").string = "EXPERIMENT PLAN · PENDING APPROVAL"
    header.h1.string = "CRCD: Causal Reward-Conflict Diagnostics for Multi-Objective Dialogue Learning"
    header.p.string = "Independent I6 plan. The existing MORE experiment plan remains unchanged. Flipping Knowledge Distillation supplies only paragraph logic and evidence rhythm."

    hero = soup.select_one('[data-report-section="target-and-references"] .hero')
    hero.clear()
    venue = BeautifulSoup('<p><b>Target conference:</b> <a href="https://2026.aclweb.org/calls/main_conference_papers/">ACL 2026 Main Conference</a>, eight content pages for a long paper.</p>', "html.parser").p
    reference = BeautifulSoup('<p><b>Researcher-owned logic reference:</b> <a href="https://aclanthology.org/2025.acl-long.1081/">Flipping Knowledge Distillation: Leveraging Small Models\' Expertise to Enhance LLMs in Text Matching</a>, used only for problem-to-method progression, paragraph transitions, and empirical-analysis rhythm.</p>', "html.parser").p
    hero.extend([venue, reference])

    soup.select_one(".float-budget").string = "图表数量：本计划 7（3 图，4 表） · 参考论文 8（6 图，2 表）"
    soup.select_one(".projected-title").string = "CRCD: Distinguishing Genuine Objective Conflict from Reward Noise in Dialogue Learning"
    callout = soup.select_one('[data-report-subsection="projected-title-abstract"] .callout')
    callout.clear()
    callout.append(BeautifulSoup("<b>PROJECTED — not results.</b> Multi-objective dialogue systems often treat reward disagreement as evidence of a real trade-off, although the same pattern can be caused by evaluator noise. We propose CRCD, a paired intervention diagnostic that changes one normalized reward channel at a time and jointly measures gradient interaction and response-level cross-objective effects. We will evaluate CRCD on MultiWOZ 2.2 and Schema-Guided Dialogue with two open instruction models, seven comparison methods, two reward judges, and five seeds. If successful, CRCD will improve conflict-detection F1 by [X%], reduce noise-only false positives by [X%], and preserve task success within [X%]. These tests will establish when reward disagreement reflects a reproducible behavioral conflict and when the correct conclusion is uncertainty.", "html.parser"))

    paragraph_nodes = soup.select(".paragraph")
    for node in paragraph_nodes:
        key = node.find("b").get_text(strip=True)
        if key not in PLAN_SENTENCES:
            continue
        sibling = node.find("b").next_sibling
        if isinstance(sibling, NavigableString):
            sibling.replace_with(NavigableString(" · " + PLAN_SENTENCES[key]))
        for detail in node.select("details article p:last-child"):
            detail.string = f"Use only the rhetorical move of this complete reference paragraph for {key}; do not reuse its text-matching claims, results, or wording. CRCD supplies all scientific content independently."

    headings = soup.select('[data-report-subsection="projected-paper-structure"] > h4')
    for heading in headings:
        if heading.get_text(strip=True) == "MORE":
            heading.string = "CRCD Method"

    design = soup.select_one("[data-model-design]")
    design.clear()
    design.append(BeautifulSoup("""
      <h5>CRCD diagnostic design and information flow</h5>
      <table><tbody>
      <tr><th>Scientific source, inputs, and outputs</th><td>MultiWOZ 2.2, SGD, GradNorm, MGDA, PCGrad, CAGrad, and Nash-MTL primary papers ground the design. Input dialogue context <var>x</var>, fixed candidate responses <var>Y</var>, reward channels <var>R<sub>j</sub></var>, reward judges, and a frozen policy checkpoint; output a directed reward-conflict graph with effect sizes, confidence intervals, and abstentions. Models: Qwen2.5-7B-Instruct and Llama-3.1-8B-Instruct; datasets: MultiWOZ 2.2 and Schema-Guided Dialogue; five seeds, two judges, and strengths 0.25σ to 1.50σ.</td></tr>
      <tr><th>Symbols</th><td><var>r<sub>ij</sub></var> is reward <var>j</var> for response <var>i</var>; <var>g<sub>j</sub></var>=∇<var>L<sub>j</sub></var>; <var>δ</var> is intervention strength; <var>Δ<sub>j→k</sub></var> is the paired cross-objective behavioral effect.</td></tr>
      <tr><th>Candidate construction</th><td>Sample one fixed candidate group per context, then reuse the identical candidates, decoding trace, and evaluator prompts across all channel interventions.</td></tr>
      <tr><th>Normalization</th><td>Robustly center each reward by its median and scale by MAD before applying <var>δ</var>∈{0.25,0.50,0.75,1.00,1.50} standard units to one channel.</td></tr>
      <tr><th>Gradient evidence</th><td>Record pairwise cosine <var>c<sub>jk</sub></var>=<var>g<sub>j</sub></var>·<var>g<sub>k</sub></var>/(||<var>g<sub>j</sub></var>||||<var>g<sub>k</sub></var>||) and gradient norms at the same checkpoint.</td></tr>
      <tr><th>Behavioral intervention</th><td>Reweight only channel <var>j</var>, select or update responses under the fixed candidate boundary, and compute paired changes in every held-out objective <var>k</var>.</td></tr>
      <tr><th>Noise calibration</th><td>Repeat scoring across two judges, prompt paraphrases, and label-preserving response perturbations to estimate a channel-pair-specific null envelope.</td></tr>
      <tr><th>Decision rule</th><td>Declare <var>j→k</var> a conflict only when <var>c<sub>jk</sub></var>&lt;0, the bootstrap interval for <var>Δ<sub>j→k</sub></var> is adverse, and the effect exceeds the calibrated noise envelope in at least four of five seeds; otherwise abstain or label non-conflict.</td></tr>
      <tr><th>Algorithm</th><td>Freeze checkpoint → sample candidates → score all channels → trace gradients → estimate noise null → intervene on each channel → bootstrap paired cross-effects → apply replicated decision rule → emit conflict graph.</td></tr>
      <tr><th>Trainable and frozen</th><td>Freeze the model, judges, prompts, preprocessing, and candidates; normalize rewards and record per-channel gradients. No model parameters change between control and intervention acquisition; only one bounded reward-channel weight changes.</td></tr>
      <tr><th>Inference path</th><td>CRCD is used only during training-time diagnosis and auditing; deployment retains the original direct-response policy.</td></tr>
      <tr><th>Evidence bindings</th><td>T1 tests detection and utility; T2 tests robustness; T3 tests intervention strength; T4 tests component ablation.</td></tr>
      <tr><th>Unknowns for exact reproduction</th><td>Final candidate-group size, judge prompt wording, differentiable intervention step size, and human-rating sample size.</td></tr>
      <tr><th>Reproducibility status</th><td>partial_due_to_source_omissions for implementation hyperparameters; the diagnostic equations and acquisition boundary are fully specified.</td></tr>
      </tbody></table>
    """, "html.parser"))

    setup = soup.select_one("[data-experiment-setup]")
    setup.clear()
    setup.append(BeautifulSoup("""
      <table class="setup-table"><tbody>
      <tr><th>Dataset</th><td>2 — <a href="https://aclanthology.org/2020.nlp4convai-1.13/">MultiWOZ 2.2</a> and <a href="https://ojs.aaai.org/index.php/AAAI/article/view/6394">Schema-Guided Dialogue</a>.</td></tr>
      <tr><th>Model</th><td>2 — Qwen2.5-7B-Instruct and Llama-3.1-8B-Instruct under one shared generation and tracing boundary.</td></tr>
      <tr><th>Baselines</th><td>7 — equal weighting, score correlation, GradNorm, MGDA, PCGrad, CAGrad, and Nash-MTL.</td></tr>
      <tr><th>Proposed method</th><td>1 — CRCD paired reward-channel intervention with gradient evidence and judge-noise calibration.</td></tr>
      <tr><th>Noise and runs</th><td>Five seeds; two reward judges; prompt-paraphrase and label-preserving perturbation controls; paired bootstrap intervals.</td></tr>
      <tr><th>Metrics</th><td><a href="https://proceedings.neurips.cc/paper_files/paper/2020/hash/3fe78a8acf5fda99de95303940a2420c-Abstract.html">Conflict F1</a> (PROPOSED, %), <a href="https://proceedings.neurips.cc/paper_files/paper/2020/hash/3fe78a8acf5fda99de95303940a2420c-Abstract.html">Noise false-positive rate</a> (PROPOSED, %), <a href="https://proceedings.neurips.cc/paper_files/paper/2020/hash/3fe78a8acf5fda99de95303940a2420c-Abstract.html">Cross-objective effect error</a> (PROPOSED, reward-score units), <a href="https://aclanthology.org/2020.nlp4convai-1.13/">Task success</a> (DIRECT, %), <a href="https://proceedings.neurips.cc/paper_files/paper/2020/hash/3fe78a8acf5fda99de95303940a2420c-Abstract.html">Naturalness</a> (ADAPTED, 1--5 rating), <a href="https://proceedings.neurips.cc/paper_files/paper/2020/hash/3fe78a8acf5fda99de95303940a2420c-Abstract.html">Diagnostic overhead</a> (DIRECT, seconds/GiB/calls), and <a href="https://proceedings.neurips.cc/paper_files/paper/2020/hash/3fe78a8acf5fda99de95303940a2420c-Abstract.html">Human conflict-label agreement</a> (PROPOSED, agreement coefficient).</td></tr>
      </tbody></table>
      <table class="implementation-table"><thead><tr><th>Method</th><th>Selection and implementation</th></tr></thead><tbody>
      <tr><th>Our method — CRCD</th><td>Local implementation in the shared PyTorch model, data, reward, trace, intervention, and evaluator framework.</td></tr>
      <tr><th>Equal weighting</th><td>Required scalarization control, locally implemented under the same framework; protocol grounded by <a href="https://papers.neurips.cc/paper_files/paper/2018/hash/432aca3a1e345e339f35a30c8f65edce-Abstract.html">Sener and Koltun (2018)</a>.</td></tr>
      <tr><th>Score correlation</th><td>Required score-only diagnostic control, locally implemented from paired reward traces; grounded by <a href="https://arxiv.org/abs/1707.06299">multi-objective dialogue reward balancing</a>.</td></tr>
      <tr><th>GradNorm</th><td>Adaptive weighting baseline, locally implemented from the <a href="https://proceedings.mlr.press/v80/chen18a.html">GradNorm</a> equations.</td></tr>
      <tr><th>MGDA</th><td>Pareto-gradient baseline, locally implemented behind the common gradient interface from <a href="https://papers.neurips.cc/paper_files/paper/2018/hash/432aca3a1e345e339f35a30c8f65edce-Abstract.html">MGDA-UB</a>.</td></tr>
      <tr><th>PCGrad</th><td>Gradient-surgery baseline, locally reimplemented in PyTorch because the official repository is TensorFlow v1; see <a href="https://papers.neurips.cc/paper_files/paper/2020/hash/3fe78a8acf5fda99de95303940a2420c-Abstract.html">PCGrad</a>.</td></tr>
      <tr><th>CAGrad</th><td>Conflict-averse update baseline, locally adapted from its objective after source inspection; see <a href="https://proceedings.neurips.cc/paper_files/paper/2021/hash/9d27fdf2477ffbff837d73ef7ae23db9-Abstract.html">CAGrad</a>.</td></tr>
      <tr><th>Nash-MTL</th><td>Bargaining baseline, locally adapted behind the same gradient interface with the official repository used as reference only; see <a href="https://proceedings.mlr.press/v162/navon22a.html">Nash-MTL</a>.</td></tr>
      </tbody></table>
    """, "html.parser"))

    cell_map: dict[str, list[str]] = {}
    for artifact_id, spec in TABLE_SPECS.items():
        old = soup.select_one(f'[data-artifact-id="{artifact_id}"]')
        new, ids = make_table(soup, artifact_id, spec)
        if old is None:
            setup.insert_after(new)
        else:
            old.replace_with(new)
        cell_map[artifact_id] = ids

    ledger_heading = next((heading for heading in soup.select("h4") if heading.get_text(strip=True) == "Compact artifact ledger"), None)
    ledger = ledger_heading.find_next("table") if ledger_heading else None
    if ledger:
        rows = [
            ("F1", "figure", "introduction", "I-P2", "Motivation example separating evaluator disagreement from a real behavioral trade-off."),
            ("F2", "figure", "method", "M-P5", "CRCD intervention, noise calibration, replicated decision rule, and conflict graph."),
            ("F3", "figure", "analysis", "AN-P3", "Reward-pair conflict graph with direction, uncertainty, and abstentions."),
            *[(aid, "table", "experiments" if aid != "T4" else "analysis", spec["after"], spec["caption"]) for aid, spec in TABLE_SPECS.items()],
        ]
        tbody = ledger.find("tbody")
        if tbody is None:
            tbody = soup.new_tag("tbody")
            ledger.append(tbody)
        tbody.clear()
        for row in rows:
            tr = soup.new_tag("tr")
            for value in row:
                td = soup.new_tag("td")
                td.string = value
                tr.append(td)
            tbody.append(tr)

    for text in soup.find_all(string=lambda value: value and "APPROVED" in value):
        text.replace_with(text.replace("APPROVED", "PENDING"))
    return cell_map


def metric_record(metric: tuple[str, str, str, str, str, str, str, str]) -> dict:
    metric_id, name, provenance, definition, range_, rule, aggregation, construct = metric
    evidence_source, unit, input_fields, calculation = METRIC_EXECUTION[metric_id]
    claim_roles = METRIC_CLAIM_ROLES[metric_id]
    record = {
        "id": metric_id,
        "name": name,
        "provenance": provenance,
        "definition": definition,
        "range": range_,
        "decision_rule": rule,
        "aggregation": aggregation,
        "url": "https://aclanthology.org/2020.nlp4convai-1.13/" if metric_id == "M-TS" else "https://proceedings.neurips.cc/paper_files/paper/2020/hash/3fe78a8acf5fda99de95303940a2420c-Abstract.html",
        "construct": construct,
        "claim_mappings": [{"claim_id": claim_id, "measurement_role": role, "construct_definition": construct, "cannot_establish": "This metric alone cannot establish a causal conflict.", "companion_requirements": ["paired intervention", "gradient trace", "noise calibration"]} for claim_id, role in claim_roles.items()],
        "cannot_establish": "This metric alone cannot establish cross-domain causal generalization.",
        "alternative_explanations": ["judge drift", "candidate-set variation", "decoding variance"],
        "companion_requirements": ["paired intervention", "five-seed replication", "noise-only control"],
        "unit": unit,
        "evidence_source": evidence_source,
        "input_fields": input_fields,
        "calculation": calculation,
        "implementation": f"code/i6_crcd/metrics.py:{metric_id.lower().replace('-', '_')}",
        "protocol_checks": ["input schema validation", "saved-operands recomputation", "unit and range validation"],
    }
    if evidence_source == "HUMAN_ANNOTATION":
        record["human_annotation_contract"] = {
            "annotator_count": 3,
            "item_count": 200,
            "blinding": "annotators are blinded to method and condition",
            "rubric_path": "code/i6_crcd/config/human_rubric.md",
            "annotation_file": "results/i6_crcd/human_annotations.jsonl",
            "agreement_calculation": "Krippendorff alpha with annotator-clustered interval",
        }
    return record


def rebuild_contract(soup: BeautifulSoup, cell_map: dict[str, list[str]]) -> None:
    contract_tag = soup.select_one("#experiment-plan-contract")
    contract = json.loads(contract_tag.string)
    for key in ("parent_approval_sha256", "approval_channel", "approved_at", "approval_contract_sha256"):
        contract.pop(key, None)
    contract.update({
        "schema_version": "1.2",
        "scientific_integrity_version": 1,
        "contract_version": 1,
        "revision_history": [{"version": 1, "changed_at": "2026-08-22", "reason": "Independent experiment plan for Idea I6", "changed_fields": ["selected_idea", "grounding", "claims", "experiments", "paper_outline", "paper_artifacts"], "compatibility": "new independent plan; canonical I1 plan unchanged"}],
        "source_plan": "reports/03_EXPERIMENT_PLAN_I6.html",
        "generated_at": "2026-08-22",
        "approval_status": "pending",
        "approval_contract_version": 1,
        "selected_idea": {"id": "I6", "title": "Causal Reward-Conflict Diagnostics"},
        "target": {"venue": "ACL 2026 Main Conference", "track": "Main Conference", "cycle": "2026", "submission_content_pages": 8, "rules_url": "https://2026.aclweb.org/calls/main_conference_papers/", "confirmed_at": "2026-08-22", "deadline_status": "passed", "deadline_override": {"confirmed": True, "confirmed_at": "2026-08-22", "reason": "Planning the work as a preprint after the conference cycle.", "intended_use": "preprint"}},
        "dataset_confirmation": {"confirmed": True, "confirmed_at": "2026-08-22"},
        "dataset_citations": [
            {"name": "MultiWOZ 2.2", "status": "PUBLISHED", "url": "https://aclanthology.org/2020.nlp4convai-1.13/", "role": "headline task-oriented dialogue benchmark"},
            {"name": "Schema-Guided Dialogue", "status": "PUBLISHED", "url": "https://ojs.aaai.org/index.php/AAAI/article/view/6394", "role": "cross-domain and unseen-service robustness benchmark"},
        ],
        "float_budget": {"body_figures": 3, "body_tables": 4, "reference_body_figures": 6, "reference_body_tables": 2},
        "budget": {"pilot": {"gpus": 2, "hours": 24}, "full": {"gpus": 4, "hours": 96, "signoff_required": True}},
        "missing_output_policy": "Mark missing; never infer a conflict decision or numeric result.",
    })
    contract.pop("target_work", None)
    contract["references"]["confirmed_at"] = "2026-08-22"
    contract["references"]["researcher_owned_logic"]["experiment_design_alignment"] = "Reuse only problem-to-method progression and evidence rhythm; CRCD scientific content is independently grounded."

    model_design = {
        "source_authority": "MultiWOZ 2.2, SGD, GradNorm, MGDA, PCGrad, CAGrad, and Nash-MTL primary papers",
        "reconstruction_policy": "The Flipping-KD reference controls rhetoric only and supplies no CRCD method content.",
        "inputs": ["dialogue context x", "fixed candidate set Y", "reward channels R_j", "frozen policy and judges"],
        "outputs": ["directed conflict graph", "paired effect estimates and intervals", "abstention labels"],
        "modules": ["Candidate construction", "Normalization", "Gradient evidence", "Behavioral intervention", "Noise calibration", "Decision rule"],
        "symbols": "r ij is reward j for response i ; g j =∇ L j ; δ is intervention strength; Δ j→k is the paired cross-objective behavioral effect.",
        "symbol_ids": ["SYM-R", "SYM-G", "SYM-DELTA", "SYM-EFFECT"],
        "data_flow": "Freeze checkpoint → sample candidates → score all channels → trace gradients → estimate noise null → intervene on each channel → bootstrap paired cross-effects → apply replicated decision rule → emit conflict graph.",
        "backbone": "A frozen dialogue checkpoint and fixed candidate boundary provide paired observations for every diagnostic condition.",
        "stage_1": "Freeze the model, judges, prompts, preprocessing, and candidates; normalize rewards and record per-channel gradients.",
        "stage_boundary": "No model parameters change between control and intervention acquisition; only one bounded reward-channel weight changes.",
        "stage_2": "Reweight only channel j , select or update responses under the fixed candidate boundary, and compute paired changes in every held-out objective k .",
        "adaptive_rule": "Declare j→k a conflict only when c jk <0, the bootstrap interval for Δ j→k is adverse, and the effect exceeds the calibrated noise envelope in at least four of five seeds; otherwise abstain or label non-conflict.",
        "objectives": ["Record pairwise cosine c jk = g j · g k /(|| g j |||| g k ||) and gradient norms at the same checkpoint."],
        "algorithm_steps": ["Freeze checkpoint → sample candidates → score all channels → trace gradients → estimate noise null → intervene on each channel → bootstrap paired cross-effects → apply replicated decision rule → emit conflict graph."],
        "implementation_details": ["Models: Qwen2.5-7B-Instruct and Llama-3.1-8B-Instruct; datasets: MultiWOZ 2.2 and Schema-Guided Dialogue; five seeds, two judges, and strengths 0.25σ to 1.50σ."],
        "inference": "CRCD is used only during training-time diagnosis and auditing; deployment retains the original direct-response policy.",
        "unknowns": ["Final candidate-group size, judge prompt wording, differentiable intervention step size, and human-rating sample size."],
        "reproducibility_status": "partial_due_to_source_omissions",
        "falsifiable_links": ["T1 tests detection and utility", "T2 tests robustness", "T3 tests intervention strength", "T4 tests component ablation"],
    }
    contract["grounding"] = {"proposed_method": "CRCD", "primary_family": "causal diagnostics for multi-objective language-model training", "hybrid_tags": ["task-oriented dialogue", "gradient analysis", "reward-model evaluation"], "model_design": model_design}

    claim_specs = [
        ("C1", "CRCD distinguishes reproducible behavioral conflicts from reward-evaluator noise more accurately than score-only or gradient-only diagnostics.", "CRCD does not improve conflict F1 or noise false-positive rate over both required controls.", ["M-CF1", "M-FPR"]),
        ("C2", "CRCD recovers the direction and magnitude of controlled cross-objective behavioral effects while preserving task utility and response naturalness.", "Effect error is not lower than controls or task success or naturalness degrades beyond the fixed non-inferiority margin.", ["M-ACE", "M-TS", "M-NAT"]),
        ("C3", "Conflict decisions remain stable across the two selected datasets, model families, and independent reward judges.", "Effect signs or conflict labels fail to replicate in a majority of cross-setting comparisons.", ["M-CF1", "M-FPR"]),
        ("C4", "A bounded intervention-strength region yields detectable effects without leaving the local response neighborhood.", "No tested strength jointly achieves detection power and locality retention.", ["M-ACE", "M-FPR"]),
        ("C5", "Noise calibration and paired behavioral evidence are necessary to prevent false conflict declarations.", "Removing either component does not materially worsen false positives or agreement with blinded human conflict labels.", ["M-CF1", "M-FPR", "M-HA"]),
        ("C6", "CRCD has bounded diagnostic overhead relative to trace-only diagnostics at matched evidence coverage.", "Runtime, memory, or judge-call overhead exceeds the preregistered budget.", ["M-COST"]),
    ]
    contract["claims"] = []
    for claim_id, claim, falsifier, metric_ids in claim_specs:
        contract["claims"].append({
            "id": claim_id,
            "scope": "MultiWOZ 2.2 and SGD with the two planned open instruction models and reward judges",
            "claim": claim,
            "falsifier": falsifier,
            "requires_formal_check": True,
            "measurement_contract": {"construct_definition": "causal reward conflict under controlled dialogue-generation interventions", "primary_observable": "paired reward, gradient, response, judge, seed, and cost records", "metric_ids": metric_ids, "measurement_role": "DIRECT", "cannot_establish": "Universal conflict structure outside the tested data, models, judges, and intervention range.", "alternative_explanations": ["judge drift", "candidate sampling", "optimization noise"], "required_controls": ["noise-only control", "paired no-intervention control", "five-seed replication"], "support_pattern": "pre-registered directional improvement with confidence intervals", "weaken_pattern": "inconsistent direction or wide intervals", "falsify_pattern": falsifier, "uncertainty_rule": "paired bootstrap 95% confidence intervals plus variation across five independent seeds", "outcome_rule": {"rule_id": f"OR-{claim_id}", "primary_metric_id": metric_ids[0], "operator": "pre_registered_comparison", "support_threshold": "strictly passes the registered directional margin and uncertainty condition", "uncertainty_condition": "the paired 95% interval excludes the null in the registered direction", "tie_outcome": "inconclusive", "missing_outcome": "inconclusive"}},
        })

    variable_specs = [
        ("V-REWARD", "DIRECT", "per-channel reward score", "reward_scores.jsonl:score"),
        ("V-GRAD", "DIRECT", "per-channel gradient vector and cosine", "gradient_traces.npz"),
        ("V-EFFECT", "PROPOSED", "paired cross-objective behavioral effect", "paired_effects.jsonl:delta"),
        ("V-NOISE", "ADAPTED", "judge-noise null envelope", "noise_controls.jsonl"),
        ("V-UTILITY", "DIRECT", "task success and naturalness", "dialogue_metrics.jsonl"),
    ]
    contract["variables"] = [{"id": i, "provenance": p, "used_in": ["EX-I6"], "purpose": purpose, "source": "planned local instrumentation", "required_observable": purpose, "available_now": False, "fallback_or_proxy": "none; mark missing", "raw_field": raw, "evidence_grade": "planned claim-grade"} for i, p, purpose, raw in variable_specs]
    contract["metric_contract"] = [metric_record(metric) for metric in METRICS]

    selected = []
    for baseline_id, name, role, url in BASELINES:
        selected.append({"id": baseline_id, "name": name, "url": url, "family": "multi-objective diagnostic or optimizer", "tags": [role], "grounded_support": [url], "frequency": "selected for a distinct comparison role", "scientific_role": role, "protocol_compatibility": "rerun locally under shared candidates, traces, interventions, judges, and metrics", "code_availability": "paper and inspected public source where available", "reproduction_burden": "moderate", "inclusion_rationale": "smallest claim-complete set spanning score, weighting, Pareto, surgery, conflict-averse, and bargaining families", "action": "RUN_LOCAL", "reuse_status": "NO_REUSE"})
    contract["baseline_contract"] = {"selected": selected, "unselected": [], "decision": "Automatic recommended selection requested by the researcher; all selected methods rerun locally."}

    implementation = []
    for _, name, role, url in BASELINES:
        implementation.append({"method": name, "display_name": name, "implementation_summary": f"Local implementation of the {role} behind the shared PyTorch gradient and evaluator interfaces.", "source_kind": "LOCAL", "source_url": "", "paper_url": url, "mode": "SELF_IMPLEMENT", "local_implementation": "planned code/i6_crcd", "upstream_reuse": "none", "shared_boundary": "model, data, candidates, rewards, gradients, interventions, judges, metrics, and result schema", "fallback": "mark method unavailable rather than change protocol", "implementation_verification": {"protocol_source": url, "required_components": [role, "shared candidate/evaluator adapter"], "conformance_tests": ["paper-equation fixture", "shared-boundary parity test"], "method_name_in_model_prompt": False}})
    implementation.append({"method": "CRCD", "display_name": "Our method — CRCD", "implementation_summary": "Local implementation of paired channel interventions, gradient tracing, noise calibration, effect estimation, and replicated decisions.", "source_kind": "LOCAL", "source_url": "", "paper_url": "", "mode": "SELF_IMPLEMENT", "local_implementation": "planned code/i6_crcd", "upstream_reuse": "none", "shared_boundary": "model, data, candidates, rewards, gradients, interventions, judges, metrics, and result schema", "fallback": "stop if paired acquisition cannot be verified", "implementation_verification": {"protocol_source": "approved CRCD model-design contract", "required_components": ["paired interventions", "gradient tracing", "noise calibration", "replicated decision rule"], "conformance_tests": ["paired-variable isolation test", "noise-control calibration test", "decision-rule replay test"], "method_name_in_model_prompt": False}})
    contract["implementation_contract"] = implementation
    contract["repository_contract"] = {"architecture": "one local unified PyTorch experiment framework", "references": [{"id": "R1", "url": "https://github.com/AvivNavon/nash-mtl", "commit": "cce18403ef5557a6b30f4ba43b896117107d6902", "mode": "REFERENCE_ONLY", "scope": ["gradient weighting equations and interface patterns"], "prohibited_scope": ["native vision datasets and trainer"], "source_audit": "methods/weight_methods.py provides a shared PyTorch interface for MGDA, PCGrad, CAGrad, and Nash-MTL but imports cvxpy/scipy and assumes task-loss tensors; adapt equations locally instead of adopting its trainer.", "discovery_source": "official paper repository and source audit", "provenance_status": "author-provided", "priority": "Preferred", "verification_status": "metadata-checked and source-inspected", "license_revision": "MIT at cce18403ef5557a6b30f4ba43b896117107d6902", "dependencies": ["PyTorch", "NumPy", "SciPy", "CVXPY", "wandb"], "compatibility_risk": "native experiments are vision/chemistry tasks and the optimization module assumes task-loss tensors, so the trainer and datasets are not reusable for dialogue"}], "authority": "local shared model/data/reward/trace/intervention/evaluator/result interfaces", "fallback": "self-implement paper equations and mark unavailable methods rather than mix native pipelines"}
    contract["experiment_contracts"] = [{"id": "EX-I6", "purpose": "Acquire all conflict-diagnosis, robustness, sensitivity, ablation, human-validity, and cost evidence", "dataset_ids": ["MultiWOZ 2.2", "Schema-Guided Dialogue"], "metric_ids": [m[0] for m in METRICS], "authorized_decisions": ["D-I6"], "repository_authority": "local unified PyTorch framework; inspected Nash-MTL source is reference-only", "seed_policy": "five independent seeds; paired candidates and controls within seed"}]
    contract["decision_space_contract"] = [{"id": "D-I6", "experiment_ids": ["EX-I6"], "decision_variable": "candidate size, judge prompt, intervention step, and human sample size", "disposition": "SEARCHED", "allowed_values": ["candidate size 4/8/16", "intervention strengths fixed at 0.25/0.50/0.75/1.00/1.50", "two predeclared judge prompts", "human sample 100/200/400"], "source": "bounded design space", "selection_rule": "select on instrumentation and development evidence only; never inspect final results", "selection_observable": "coverage, variance, locality retention, and budget", "budget": "pilot <=24 GPU-hours", "freeze_point": "before final acquisition", "final_value_source": "runplan decision ledger", "test_access_prohibited": True}]
    contract["consistency_requirements"] = {"canonical_terms": [b[0] for b in BASELINES] + [m[0] for m in METRICS], "source_values": ["D-I6"], "formal_links": [c[0] for c in claim_specs], "symbol_registry": [
        {"id": "SYM-R", "latex": "r_{ij}", "meaning": "reward-channel j score for response i"},
        {"id": "SYM-G", "latex": "g_j", "meaning": "gradient of reward-channel j loss"},
        {"id": "SYM-DELTA", "latex": "\\delta", "meaning": "registered intervention strength"},
        {"id": "SYM-EFFECT", "latex": "\\Delta_{j\\to k}", "meaning": "paired cross-objective behavioral effect"},
    ]}

    for section in contract["paper_outline"]:
        if section.get("title") == "MORE":
            section["title"] = "CRCD Method"
        for paragraph in section.get("paragraphs", []):
            paragraph_id = paragraph["id"]
            if paragraph_id in PLAN_SENTENCES:
                paragraph["plan_sentence"] = PLAN_SENTENCES[paragraph_id]
                paragraph["evidence"] = ["planned local experiment contract", "verified primary sources"]
                for mapping in paragraph.get("reference_mapping", []):
                    mapping["adaptation_note"] = f"Use only the rhetorical move of complete Flipping-KD paragraph {mapping['source_paragraph_id']} for {paragraph_id}; do not reuse its scientific claims or wording."
                if paragraph_id.startswith("M-"):
                    paragraph.update({"inputs": model_design["inputs"], "outputs": model_design["outputs"], "variable_ids": [v[0] for v in variable_specs], "raw_fields": [v[3] for v in variable_specs], "evidence_grade": "claim-grade"})

    figure_updates = {
        "F1": ("motivation-conflict-vs-noise", "I-P2", ["C1"], "Motivation example contrasting genuine behavioral conflict with evaluator-only disagreement."),
        "F2": ("crcd-method", "M-P5", ["C1", "C2"], "CRCD paired intervention, noise calibration, and replicated decision pipeline."),
        "F3": ("reward-conflict-graph", "AN-P3", ["C3", "C5"], "Directed reward-conflict graph with effect direction, uncertainty, and abstentions."),
    }
    artifacts = []
    for artifact in contract["paper_artifacts"]:
        artifact_id = artifact["id"]
        if artifact_id in figure_updates:
            label, after, supports, caption = figure_updates[artifact_id]
            artifact.update({"label": label, "introduced_after": after, "supports": supports, "section_id": "introduction" if artifact_id == "F1" else ("method" if artifact_id == "F2" else "analysis")})
            artifact["shell"]["caption"] = caption
            artifact["shell"]["data_driven"] = False
            artifacts.append(artifact)
        elif artifact_id in TABLE_SPECS:
            spec = TABLE_SPECS[artifact_id]
            artifacts.append({"id": artifact_id, "kind": "table", "label": f"i6-{artifact_id.lower()}", "span": "double_column", "placement": "body", "supports": spec["supports"], "section_id": "experiments" if artifact_id != "T4" else "analysis", "introduced_after": spec["after"], "dimensions": ["method_or_condition", "metric"], "visible_dimensions": ["method_or_condition", "metric"], "shell": {"caption": spec["caption"], "row_labels": spec["rows"], "column_labels": spec["columns"], "dataset_headers": spec["datasets"], "metric_uncertainty": "mean ± standard deviation or paired bootstrap 95% confidence interval", "pending_cell_ids": cell_map[artifact_id]}})
    contract["paper_artifacts"] = artifacts
    contract["required_labels"] = [artifact["label"] for artifact in artifacts]
    requirements = []
    for artifact_id, cell_ids in cell_map.items():
        for cell_id in cell_ids:
            requirements.append({"id": f"REQ-{cell_id}", "artifact_id": artifact_id, "cell_ids": [cell_id], "experiment_id": "EX-I6", "source_action": "RUN_LOCAL", "any_of": [f"metrics.i6.{cell_id}"], "supports": TABLE_SPECS[artifact_id]["supports"]})
    contract["result_requirements"] = requirements
    contract_tag.string = json.dumps(contract, ensure_ascii=False, separators=(",", ":"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if not SOURCE.is_file():
        raise SystemExit(f"Missing structural template: {SOURCE}")
    soup = BeautifulSoup(SOURCE.read_text(encoding="utf-8"), "html.parser")
    cell_map = rebuild_visible_html(soup)
    rebuild_contract(soup, cell_map)
    rendered = str(soup).replace(
        '<script id="experiment-plan-contract" type="application/json">',
        '<script type="application/json" id="experiment-plan-contract">',
    )
    rendered = rendered.replace(
        '<div class="setup-wrap" data-experiment-setup="">',
        '<div data-experiment-setup class="setup-wrap">',
    )
    args.output.write_text(rendered, encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
