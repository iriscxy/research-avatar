#!/usr/bin/env python3
"""Build the pending, real-data micro experiment plan used to exercise later skills."""

from __future__ import annotations

import base64
import hashlib
import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/03_EXPERIMENT_PLAN.html"
SCHEMA_REL = "paper/figsrc/micro_typo_intent/figure_schema.json"
FIXTURE_REL = "paper/figsrc/micro_typo_intent/projected_fixture.json"
FIXTURE_GEN = "paper/figsrc/micro_typo_intent/make_projected_fixture.py"
FIG_SOURCE = "paper/fig/make_figs.py"
FIG_PDF = "paper/fig/micro_typo_intent/projected/F2_typo_sensitivity.pdf"
FIG_PNG = "paper/fig/micro_typo_intent/projected/F2_typo_sensitivity.png"

URLS = {
    "venue": "https://www.aclweb.org/portal/content/32nd-international-conference-computational-linguistics",
    "external": "https://aclanthology.org/P19-1561/",
    "owned": "https://aclanthology.org/2025.findings-acl.866/",
    "clinc": "https://github.com/clinc/oos-eval",
    "clinc_paper": "https://aclanthology.org/D19-1131/",
}


def pending(cell_id: str) -> str:
    return f'<td class="pending" data-target-id="{cell_id}">[PENDING]</td>'


def paragraph_table(rows: list[dict]) -> str:
    body = []
    for row in rows:
        artifacts = ", ".join(row["artifact_refs"]) if row["artifact_refs"] else "—"
        body.append(
            f'<tr><th>{html.escape(row["id"])}</th><td>{html.escape(row["plan_sentence"])}</td>'
            f'<td>{html.escape(artifacts)}</td></tr>'
        )
    return (
        '<table class="blueprint"><thead><tr><th>Paragraph</th><th>One-sentence plan</th>'
        f'<th>Artifact</th></tr></thead><tbody>{"".join(body)}</tbody></table>'
    )


def para(
    pid: str,
    sentence: str,
    anchor: str,
    role: str,
    supports: list[str],
    artifacts: list[str] | None = None,
    *,
    method: bool = False,
) -> dict:
    record = {
        "id": pid,
        "plan_sentence": sentence,
        "reference_anchor": anchor,
        "rhetorical_role": role,
        "supports": supports,
        "evidence": "planned real-data artifact or grounded argument",
        "transition": "The next paragraph answers the next unresolved reader question.",
        "length_share": "one focused short-paper paragraph",
        "artifact_refs": artifacts or [],
    }
    if method:
        record.update(
            {
                "inputs": ["CLINC150 utterance", "feature granularity", "smoothing constant"],
                "outputs": ["intent prediction", "class log score"],
                "variable_ids": ["V1", "V3", "V4"],
                "raw_fields": ["record_id", "intent_label", "method_id", "prediction", "class_log_scores"],
                "evidence_grade": "claim-grade after E1; unavailable before execution",
            }
        )
    return record


def metric(
    mid: str,
    name: str,
    provenance: str,
    definition: str,
    range_: str,
    construct: str,
    mappings: list[tuple[str, str]],
    cannot: str,
    alternatives: list[str],
    companions: list[str],
    url: str,
) -> dict:
    return {
        "id": mid,
        "name": name,
        "provenance": provenance,
        "definition": definition,
        "range": range_,
        "decision_rule": "Compute only from frozen record-level predictions; no threshold is used.",
        "aggregation": "Pool the frozen evaluation records, then report the scalar score; deterministic rerun must match exactly.",
        "url": url,
        "construct": construct,
        "claim_mappings": [
            {
                "claim_id": claim_id,
                "measurement_role": role,
                "cannot_establish": cannot,
                "companion_requirements": companions,
            }
            for claim_id, role in mappings
        ],
        "cannot_establish": cannot,
        "alternative_explanations": alternatives,
        "companion_requirements": companions,
    }


def baseline(
    bid: str,
    name: str,
    family: str,
    role: str,
    tier: str,
    action: str,
    included: bool,
) -> dict:
    return {
        "id": bid,
        "name": name,
        "url": "",
        "family": family,
        "tags": ["micro-study", "local"],
        "grounded_support": ["Pruthi et al. (2019) comparison grammar"],
        "frequency": 1,
        "scientific_role": role,
        "protocol_compatibility": "full for the approved CLINC150 micro protocol" if included else "not selected for the micro protocol",
        "code_availability": "local implementation" if included else "not evaluated",
        "reproduction_burden": "negligible" if included else "outside the approved micro budget",
        "inclusion_rationale": f"{tier}; {role}.",
        "recommendation_tier": tier,
        "action": action,
    }


def implementation(method: str, display_name: str, summary: str, local: str) -> dict:
    return {
        "method": method,
        "display_name": display_name,
        "implementation_summary": summary,
        "mode": "SELF_IMPLEMENT",
        "source_kind": "LOCAL",
        "source_label": "Implemented locally",
        "source_url": "",
        "paper_url": "",
        "repository_status": "No external implementation code is used.",
        "upstream_reuse": "None.",
        "local_implementation": local,
        "shared_boundary": "One local data adapter, perturbation generator, classifier API, evaluator, and JSON result schema.",
        "fallback": "Stop and record the failed component; do not substitute another method silently.",
    }


def decision(did: str, variable: str, values: list, source: str, rule: str, observable: str) -> dict:
    return {
        "id": did,
        "experiment_ids": ["E0", "E1"],
        "decision_variable": variable,
        "disposition": "FIXED_BY_DESIGN",
        "allowed_values": values,
        "source": source,
        "selection_rule": rule,
        "selection_observable": observable,
        "budget": "No search; one frozen value or finite list.",
        "freeze_point": "Before E0 instrumentation sanity.",
        "final_value_source": "reports/03_EXPERIMENT_PLAN.html embedded contract",
        "test_access_prohibited": True,
    }


def main() -> None:
    schema = json.loads((ROOT / SCHEMA_REL).read_text(encoding="utf-8"))
    panel = schema["figures"]["F2"][0]
    png_data = base64.b64encode((ROOT / FIG_PNG).read_bytes()).decode("ascii")

    t1_rows = ["Majority Classifier", "Word-unigram Naive Bayes", "Character-trigram Naive Bayes"]
    t1_columns = [
        "Clean Accuracy ↑",
        "10% swap Accuracy ↑",
        "10% swap Macro-F1 ↑",
        "Robustness Drop ↓",
    ]
    t1_cells: list[str] = []
    t1_body: list[str] = []
    for row_index, label in enumerate(t1_rows):
        values = []
        for column_index in range(len(t1_columns)):
            cell_id = f"t1-{row_index:02d}-{column_index:02d}"
            t1_cells.append(cell_id)
            values.append(pending(cell_id))
        t1_body.append(f'<tr><th>{html.escape(label)}</th>{"".join(values)}</tr>')
    t1_header = "".join(f"<th>{html.escape(column)}</th>" for column in t1_columns)
    t1_html = f'''<div class="shell result-table-shell"><div class="shell-title">T1 · Main clean and typo-robustness comparison</div>
      <p class="warning">RESULT PLACEHOLDER — NO NUMBERS FABRICATED</p>
      <div class="table-wrap"><table><thead><tr><th>Method</th>{t1_header}</tr></thead><tbody>{''.join(t1_body)}</tbody></table></div>
      <p>Dataset: <a href="{URLS['clinc']}">CLINC150</a> four-intent micro subset. Every value is computed locally from the same frozen records; Accuracy and Macro-F1 are exact point estimates and Robustness Drop is clean Accuracy minus 10% swap Accuracy.</p></div>'''

    f2_cells: list[str] = []
    f2_rows: list[str] = []
    for point_index, x_value in enumerate(panel["x_values"]):
        values = []
        for series_index in range(len(panel["series"])):
            cell_id = f"f2-typo_sensitivity-{point_index:02d}-{series_index:02d}"
            f2_cells.append(cell_id)
            values.append(pending(cell_id))
        f2_rows.append(f'<tr class="plot-point"><th>{x_value}</th>{"".join(values)}</tr>')
    f2_headers = "".join(f"<th>{html.escape(name)}</th>" for name in panel["series"])
    f2_html = f'''<div class="shell projected-figure"><div class="shell-title">F2 · Accuracy across typo intensity</div>
      <section class="panel-pair">
        <div class="required-data figure-source-data">
          <p><strong>Dataset / benchmark:</strong> <a href="{URLS['clinc']}">CLINC150</a> four-intent micro subset.</p>
          <p><strong>Metric / axes:</strong> Accuracy; x = internal-character swap rate; y = accuracy.</p>
          <p><strong>Required fields:</strong> <code>{html.escape(', '.join(panel['required_fields']))}</code>. Aggregation: {html.escape(panel['aggregation'])}.</p>
          <div class="table-wrap"><table><thead><tr><th>Internal-character swap rate</th>{f2_headers}</tr></thead><tbody>{''.join(f2_rows)}</tbody></table></div>
        </div>
        <div class="projected-preview"><img alt="F2 projected typo-sensitivity preview" src="data:image/png;base64,{png_data}"><p>PROJECTED SHAPE — NOT RESULTS；左侧待填表是后续真实实验数字的唯一来源。</p></div>
      </section></div>'''

    selected = [
        baseline("B1", "Majority Classifier", "traditional", "uninformed lower-bound control", "Required", "RUN_LOCAL", True),
        baseline("B2", "Word-unigram Naive Bayes", "traditional", "word-level lexical comparison", "Required", "RUN_LOCAL", True),
    ]
    unselected = [
        baseline("B3", "Word-unigram NB with typo augmentation", "traditional", "training-augmentation control", "Strongly recommended", "NOT_SELECTED", False),
        baseline("B4", "BiLSTM word and character variants", "deep-learning", "external neural comparison", "Citation only", "CITATION_ONLY", False),
        baseline("B5", "BERT", "LLM-based", "external pretrained-model comparison", "Citation only", "CITATION_ONLY", False),
        baseline("B6", "ScRNN variants", "deep-learning", "word-recognition defense", "Citation only", "CITATION_ONLY", False),
        baseline("B7", "External spell corrector", "tool-using", "external correction component", "Citation only", "CITATION_ONLY", False),
    ]

    implementations = [
        implementation(
            "Majority Classifier",
            "Majority Classifier",
            "Implement this control in the shared local framework by predicting the most frequent observed intent with a deterministic lexical tie-break.",
            "Write the majority-count fit and prediction functions using the shared record schema.",
        ),
        implementation(
            "Word-unigram Naive Bayes",
            "Word-unigram Naive Bayes",
            "Implement multinomial Naive Bayes over lowercase word unigrams in the shared local framework with additive smoothing fixed at 1.0.",
            "Write token counts, class priors, additive smoothing, log scoring, and deterministic tie-breaking.",
        ),
        implementation(
            "Character-trigram Naive Bayes",
            "Our method — Character-trigram Naive Bayes",
            "Implement multinomial Naive Bayes over boundary-marked character trigrams in the same shared local framework and change no other classifier component.",
            "Reuse the local Naive Bayes core and replace only the feature extractor with boundary-marked character trigrams.",
        ),
    ]

    metrics = [
        metric(
            "M1", "Accuracy", "DIRECT from the CLINC150 evaluation protocol",
            "Number of records whose predicted intent equals the gold intent divided by the number of evaluated records.",
            "0–1", "overall intent correctness", [("C1", "DIRECT"), ("C2", "DIRECT")],
            "Accuracy can hide uneven performance across the four intents.",
            ["class imbalance", "one easy intent dominating the total"], ["Macro-F1", "per-record predictions"], URLS["clinc_paper"],
        ),
        metric(
            "M2", "Macro-F1", "DIRECT from the CLINC150 evaluation protocol",
            "Compute F1 independently for each of the four intents from one-vs-rest counts, then take their unweighted mean.",
            "0–1", "class-balanced intent correctness", [("C2", "DIRECT")],
            "Macro-F1 on four intents cannot establish broad-domain robustness.",
            ["small per-intent sample count", "label-specific vocabulary"], ["Accuracy", "per-intent confusion counts"], URLS["clinc_paper"],
        ),
        metric(
            "M3", "Robustness Drop", "ADAPTED from Pruthi et al. adversarial accuracy comparison",
            "Clean Accuracy minus Accuracy under the named deterministic internal-character swap rate.",
            "−1–1; lower is better", "performance retained under spelling shift", [("C1", "DIRECT"), ("C2", "DIRECT")],
            "A small drop can arise from uniformly poor clean and perturbed performance.",
            ["low clean ceiling", "perturbations too weak to change features"], ["Clean Accuracy", "perturbed Accuracy", "Macro-F1"], URLS["external"],
        ),
    ]

    claims = [
        {
            "id": "C1",
            "claim": "Deterministic internal-character swaps expose a measurable robustness gap for a word-unigram intent classifier on the approved CLINC150 micro subset.",
            "falsifier": "Word-unigram Accuracy does not decrease at the frozen 10% swap condition, or the decrease is not reproduced exactly on the second run.",
            "requires_formal_check": False,
            "measurement_contract": {
                "construct_definition": "Loss of intent-classification correctness caused by a label-preserving spelling shift.",
                "primary_observable": "paired clean and perturbed record-level predictions",
                "metric_ids": ["M1", "M3"],
                "measurement_role": "DIRECT",
                "cannot_establish": "Robustness on other intents, languages, perturbations, or model families.",
                "alternative_explanations": ["the chosen intents have unusually fragile keywords", "the micro sample is noisy"],
                "required_controls": ["clean-input evaluation", "deterministic rerun", "gold labels unchanged by perturbation"],
                "support_pattern": "Positive word-unigram Robustness Drop with identical rerun outputs.",
                "weaken_pattern": "A small but nonzero drop confined to one intent.",
                "falsify_pattern": "No positive drop or nondeterministic results.",
                "uncertainty_rule": "No inferential claim; report exact micro-sample point estimates and raw counts.",
            },
        },
        {
            "id": "C2",
            "claim": "Changing only the feature granularity to character trigrams reduces the 10% typo Robustness Drop while keeping clean Accuracy within 0.10 of word unigrams.",
            "falsifier": "Character trigrams do not lower Robustness Drop, or their clean Accuracy trails word unigrams by more than 0.10.",
            "requires_formal_check": False,
            "measurement_contract": {
                "construct_definition": "A feature-granularity advantage under spelling shift without a large clean-input penalty.",
                "primary_observable": "method-indexed clean and perturbed predictions",
                "metric_ids": ["M1", "M2", "M3"],
                "measurement_role": "DIRECT",
                "cannot_establish": "Novelty, state-of-the-art performance, or neural-model robustness.",
                "alternative_explanations": ["character features memorize this tiny subset", "intent labels differ in surface form"],
                "required_controls": ["shared Naive Bayes core", "fixed smoothing", "same records and perturbations"],
                "support_pattern": "Lower character-trigram Robustness Drop and clean Accuracy difference no worse than −0.10.",
                "weaken_pattern": "Lower drop accompanied by a clean penalty near the 0.10 boundary.",
                "falsify_pattern": "No robustness advantage or excessive clean penalty.",
                "uncertainty_rule": "No population generalization; preserve exact record predictions for later optional resampling.",
            },
        },
    ]

    variables = [
        {"id":"V1","name":"utterance text","used_in":["C1","C2"],"purpose":"classifier input","source":"CLINC150 official JSON","required_observable":"English utterance string","available_now":True,"fallback_or_proxy":"none","raw_field":"text","evidence_grade":"claim-grade after repository verification"},
        {"id":"V2","name":"internal-character swap rate","used_in":["C1","C2"],"purpose":"controlled spelling shift","source":"adapted from Pruthi et al. (2019)","required_observable":"eligible internal characters and deterministic swap decisions","available_now":False,"fallback_or_proxy":"stop if perturbation provenance cannot be reconstructed","raw_field":"perturbation_rate, perturbation_seed, edit_log","evidence_grade":"claim-grade after E0"},
        {"id":"V3","name":"feature granularity","used_in":["C2"],"purpose":"single changed mechanism","source":"fixed by design","required_observable":"word-unigram or boundary-marked character-trigram counts","available_now":False,"fallback_or_proxy":"none","raw_field":"method_id, feature_type, vocabulary_size","evidence_grade":"claim-grade after E0"},
        {"id":"V4","name":"intent prediction","used_in":["C1","C2"],"purpose":"compute all approved metrics","source":"local classifier output","required_observable":"gold label, predicted label, class log scores","available_now":False,"fallback_or_proxy":"none","raw_field":"intent_label, prediction, class_log_scores, is_correct","evidence_grade":"claim-grade after E1"},
    ]

    sections = [
        {"id":"abstract","title":"Abstract","paragraphs":[para("A-P1","The abstract will state the spelling-shift gap, the character-trigram comparison, the real CLINC150 micro scope, two placeholder findings, and the strict no-generalization boundary.","Word Form Matters abstract arc","summary",["C1","C2"])]},
        {"id":"introduction","title":"1. Introduction","paragraphs":[
            para("I-P1","Intent classifiers often depend on exact word forms even when a small spelling change preserves what the user means.","Word Form Matters §1 opening","stakes",["C1"]),
            para("I-P2","A concrete clean-versus-scrambled utterance will motivate measuring both clean correctness and robustness loss before presenting a method.","Word Form Matters §1 phenomenon example","gap",["C1"],["F1"]),
            para("I-P3","We test whether changing only feature granularity from words to character trigrams improves robustness in a controlled Naive Bayes comparison.","Word Form Matters §1 research question","question",["C2"]),
            para("I-P4","The contribution is a reproducible micro study with real data and a falsifiable boundary rather than a claim of state-of-the-art performance.","Word Form Matters §1 contributions","contribution",["C1","C2"]),
        ]},
        {"id":"related","title":"2. Related Work","paragraphs":[
            para("R1-P1","Prior misspelling attacks show that character swaps, additions, and deletions can sharply reduce text-classification accuracy.","Pruthi et al. §1–2","attack context",["C1"]),
            para("R2-P1","Word-recognition and character-aware defenses motivate isolating feature granularity while keeping the classifier and data fixed.","Pruthi et al. §3; Word Form Matters §2","method contrast",["C2"]),
        ]},
        {"id":"problem","title":"3. Problem Formulation","paragraphs":[
            para("P-P1","We define label-preserving internal-character swaps and Robustness Drop for a frozen four-intent classification problem.","Word Form Matters §3","formal object",["C1"]),
            para("P-P2","The decisive hypothesis requires character trigrams to reduce Robustness Drop without losing more than 0.10 clean Accuracy.","Word Form Matters §3 research questions","falsifier",["C2"]),
        ]},
        {"id":"method","title":"4. Character-Granularity Classifier","paragraphs":[
            para("M-P1","The unified classifier receives a labeled utterance collection and returns deterministic intent predictions from multinomial class scores.","Word Form Matters §4–5 input and metric progression","input-output",["C1","C2"],method=True),
            para("M-P2","The proposed variant replaces lowercase word unigrams with boundary-marked character trigrams while preserving the Naive Bayes core and smoothing value.","Pruthi et al. word-versus-character comparison","mechanism",["C2"],method=True),
            para("M-P3","The perturbation generator swaps eligible internal characters from a recorded seed and emits an edit log that can reconstruct every changed utterance.","Pruthi et al. §3.3","validity",["C1","C2"],method=True),
        ]},
        {"id":"experiments","title":"5. Experiments","paragraphs":[
            para("E1-P1","Setup uses the confirmed CLINC150 four-intent micro subset, two local baselines, one character-trigram method, three exact metrics, and one deterministic execution contract.","Word Form Matters §4; Pruthi et al. §4","setup",["C1","C2"]),
            para("E2-P1","The main table tests clean correctness, 10% swap robustness, the feature-granularity ablation, and the preregistered clean-performance boundary.","Word Form Matters §6 result progression","main result",["C1","C2"],["T1"]),
            para("E3-P1","The sensitivity curve tests whether any character-level advantage persists as the swap rate increases from zero to 0.15.","Word Form Matters severity curves","sensitivity",["C2"],["F2"]),
            para("E3-P2","Runtime is logged only as workflow provenance, while up to three mismatched predictions are discussed qualitatively without converting them into a broad error taxonomy.","Pruthi et al. qualitative analysis","cost and failure",["C1","C2"]),
        ]},
        {"id":"conclusion","title":"6. Conclusion","paragraphs":[para("C-P1","The conclusion will report whether the two micro claims survived and will explicitly restrict the finding to four CLINC150 intents and deterministic internal swaps.","Word Form Matters §8","closure",["C1","C2"])]},
        {"id":"limitations","title":"7. Limitations","paragraphs":[para("L-P1","The limitations will state that the tiny English-only classical-model study cannot support venue-scale, neural, multilingual, or adversarial robustness claims.","Word Form Matters §9","scope boundary",["C1","C2"])]},
        {"id":"appendix","title":"Appendix A. Reproducibility Details","paragraphs":[para("AP-P1","The appendix will list the frozen intents, perturbation rule, feature extraction, smoothing, tie-break, hashes, and exact rerun command without adding new paper claims.","Word Form Matters appendix reproducibility rhythm","reproducibility",[])]},
    ]

    decisions = [
        decision("D1","intent labels",["weather","restaurant_reviews","change_speed","balance"],"researcher-confirmed DS1 micro scope","Use exactly the four named labels.","actual label counts after R1 verification"),
        decision("D2","maximum selected records",[120],"researcher request for a very small real experiment","Cap the frozen micro slice at 120 records.","manifest record count"),
        decision("D3","perturbation rates",[0.0,0.05,0.10,0.15],"fixed sensitivity geometry","Use exactly the four rates in the F2 source table.","edit log realized rates"),
        decision("D4","perturbation seed",[20260814],"reproducibility design","Use one seed and reproduce the identical edit log twice.","edit-log SHA-256"),
        decision("D5","Naive Bayes additive smoothing",[1.0],"fixed classical default","Use 1.0 for both word and character variants.","serialized configuration"),
        decision("D6","feature definitions",["lowercase word unigram","boundary-marked character trigram"],"single-variable mechanism design","Change only the feature extractor between B2 and the proposed method.","feature vocabulary manifests"),
        decision("D7","prediction tie-break",["lexicographically smallest intent label"],"determinism design","Resolve equal class scores lexicographically.","prediction provenance"),
    ]

    artifacts = [
        {"id":"F1","kind":"figure","label":"fig:motivation","span":"single_column","placement":"body","supports":["C1"],"section_id":"introduction","dimensions":["clean utterance","internal swap","unchanged intent"],"visible_dimensions":["clean utterance","internal swap","unchanged intent"],"introduced_after":"I-P2","shell":{"data_driven":False,"rhetorical_role":"motivation","caption":"One intent-preserving spelling shift can change a word-dependent prediction, motivating paired robustness measurement."}},
        {"id":"T1","kind":"table","label":"tab:micro-main","span":"double_column","placement":"body","supports":["C1","C2"],"section_id":"experiments","dimensions":["dataset","method","input condition","metric"],"visible_dimensions":["dataset","method","input condition","metric"],"introduced_after":"E2-P1","shell":{"caption":"Main clean and typo-robustness comparison","row_labels":t1_rows,"column_labels":t1_columns,"dataset_bearing_headers":["CLINC150 four-intent micro subset"],"metric_uncertainty":"Exact micro-sample point estimates; raw integer counts retained; no inferential interval","pending_cell_ids":t1_cells}},
        {"id":"F2","kind":"figure","label":"fig:typo-sensitivity","span":"single_column","placement":"body","supports":["C2"],"section_id":"experiments","dimensions":["dataset","method","perturbation rate","accuracy"],"visible_dimensions":["dataset","method","perturbation rate","accuracy"],"introduced_after":"E3-P1","shell":{"data_driven":True,"caption":"Intent accuracy as deterministic internal-character swap rate increases.","panels":["typo_sensitivity"],"axes_legend":"x is swap rate; y is Accuracy; one series per feature granularity.","source_variables":["V1","V2","V3","V4"],"aggregation":panel["aggregation"],"required_data":[{"panel":"typo_sensitivity","fixture_key":panel["fixture_key"],"cell_ids":f2_cells,"required_fields":panel["required_fields"]}],"plotting":{"source":FIG_SOURCE,"schema":SCHEMA_REL,"fixture_generator":FIXTURE_GEN,"fixture":FIXTURE_REL,"pdf":FIG_PDF,"png":FIG_PNG,"panels":{"typo_sensitivity":{"pdf":FIG_PDF,"png":FIG_PNG}}}}},
    ]

    contract = {
        "schema_version":"1.1",
        "contract_version":2,
        "revision_history":[
            {"version":1,"changed_at":"2026-08-09","reason":"Initial approved First-Divergence Repair experiment plan.","changed_fields":["scientific scope","artifact ledger"],"compatibility":"Superseded by the user-requested independent micro experiment."},
            {"version":2,"changed_at":"2026-08-14","reason":"Replace the large jailbreak program with a real-data micro intent-classification experiment for downstream skill testing.","changed_fields":["idea","target","references","baselines","dataset","claims","experiments","artifacts","budget"],"compatibility":"Incompatible with the previous run plan; requires new approval and a fresh runplan."},
        ],
        "parent_approval_sha256":"1d5e184d774308309570b6cd37b18dd4b45643aae3aaaa048cf1394fad1f5ae1",
        "generated_at":"2026-08-14",
        "source_plan":"conversation: real-data micro experiment for testing downstream skills",
        "approval_status":"pending",
        "profile_contract":{"profile_path":"researcher-profile/PROFILE.html","publications_path":"researcher-profile/publications.json","researcher_identity":"Xiuying Chen","authorship_verified":True,"structure_reference_key":"wang2025word"},
        "target":{"venue":"COLING 2027 Short Paper","track":"Main conference short paper","cycle":"2027","submission_content_pages":4,"official_rules_url":URLS["venue"],"deadline_status":"upcoming","deadline":"2026-10-12","confirmed_at":"2026-08-14"},
        "references":{"confirmed_at":"2026-08-14","external_mechanism":{"title":"Combating Adversarial Misspellings with Robust Word Recognition","authors":"Danish Pruthi, Bhuwan Dhingra, Zachary C. Lipton","venue":"ACL 2019","url":URLS["external"],"full_text_status":"retrieved and experiments read"},"researcher_owned_structure":{"title":"Word Form Matters: LLMs' Semantic Reconstruction under Typoglycemia","authors":"Chenxi Wang, Tianle Gu, Zhongyu Wei, Lang Gao, Zirui Song, Xiuying Chen","venue":"Findings of ACL 2025","url":URLS["owned"],"publication_key":"wang2025word","local_full_text":"researcher-profile/fulltext/txt/wang2025word.txt"}},
        "dataset_confirmation":{"confirmed":True,"confirmed_at":"2026-08-14"},
        "dataset_citations":[{"name":"CLINC150","url":URLS["clinc"]}],
        "grounding":{"idea":"Character granularity for typo-robust micro intent classification","primary_reference":URLS["external"],"proposed_method":"Character-trigram Naive Bayes","selected_architecture":"One unified local Python experiment framework owns data, perturbation, classifiers, metrics, and results.","scientific_scope":"real CLINC150 records; micro study only"},
        "claims":claims,
        "variables":variables,
        "baseline_contract":{"taxonomy":{"selected_idea_primary_family":"traditional","secondary_tags":["character-aware","robustness diagnostic"],"families_present":["traditional","deep-learning","LLM-based","tool-using"]},"selected":selected,"unselected":unselected,"selection":"required","reuse_decision":"rerun all selected locally","confirmed_at":"2026-08-14"},
        "implementation_contract":implementations,
        "repository_contract":{"architecture":"unified local framework","architecture_confirmed_at":"2026-08-14","manual_additions":[],"references":[{"id":"R1","name":"clinc/oos-eval","url":URLS["clinc"],"use_mode":"VERIFY_AND_USE","allowed_scopes":["data/preprocessing"],"prohibited_scopes":["baseline implementation","evaluator/metric protocol","method module","reported results"],"integration_target":"local CLINC150 JSON data adapter","precedence":"R1 is authoritative only for data/data_full.json.","verification_checklist":["pin commit","record CC BY 3.0 license","hash data file","validate JSON schema","verify four labels","record files used"],"fallback":"Stop and request a plan amendment; do not silently replace the dataset.","discovery_source":"CLINC150 paper and official repository link","provenance_status":"official author repository","priority":"Preferred","verification_status":"source inspected; execution not yet verified","license_revision":"CC BY 3.0; HEAD 828f8093932c8fe6ca7936c3d2e52903b1c523de","dependencies":"No executable package; JSON data only.","compatibility_risk":"Repository lacks code and tests, so only the JSON data file is authorized."}]},
        "experiment_contracts":[
            {"id":"E0","name":"Instrumentation sanity","purpose":"Verify data provenance, perturbation reconstruction, feature extraction, prediction schema, metric paths, and identical rerun behavior before any paper cell is filled.","variable_ids":["V1","V2","V3","V4"],"raw_fields":["record_id","text","intent_label","perturbation_rate","perturbation_seed","edit_log","method_id","feature_type","prediction","class_log_scores","is_correct"],"computation":"Run a tiny internal smoke slice twice and compare schemas, hashes, edits, predictions, and metric calculations without filling empirical paper cells.","authorized_decisions":["D1","D2","D3","D4","D5","D6","D7"],"repository_authority":["R1"],"source_action":"RUN_LOCAL"},
            {"id":"E1","name":"Unified real-data micro comparison","purpose":"Fill T1 and F2 from one deterministic local execution on the approved CLINC150 micro scope.","variable_ids":["V1","V2","V3","V4"],"raw_fields":["record_id","intent_label","perturbation_rate","method_id","prediction","is_correct","tp","fp","fn","elapsed_ms"],"computation":"Fit the three frozen methods, generate deterministic internal swaps, record all predictions, compute Accuracy, Macro-F1, and Robustness Drop, then rerun identically.","uncertainty":"Exact micro-sample point estimates; retain raw counts and do not claim population inference.","authorized_decisions":["D1","D2","D3","D4","D5","D6","D7"],"repository_authority":["R1"],"source_action":"RUN_LOCAL"},
        ],
        "metric_contract":metrics,
        "decision_space_contract":decisions,
        "consistency_requirements":{"canonical_terms":["B1","B2","M1","M2","M3"],"source_values":["D1","D2","D3","D4","D5","D6","D7"],"formal_links":[]},
        "paper_outline":sections,
        "paper_artifacts":artifacts,
        "float_budget":{"body_figures":2,"body_tables":1,"reference_body_figures":4,"reference_body_tables":0},
        "required_labels":["fig:motivation","tab:micro-main","fig:typo-sensitivity"],
        "result_requirements":[
            {"id":"REQ-T1","artifact_id":"T1","cell_ids":t1_cells,"experiment_id":"E1","source_action":"RUN_LOCAL","any_of":["results/micro_typo_intent/main_results.json:table.T1.cells.*"],"supports":["C1","C2"]},
            {"id":"REQ-F2","artifact_id":"F2","cell_ids":f2_cells,"experiment_id":"E1","source_action":"RUN_LOCAL","any_of":["results/micro_typo_intent/sensitivity.json:figure.F2.typo_sensitivity.*"],"supports":["C2"]},
        ],
        "execution_dependency_sketch":["E0 instrumentation sanity","E1 unified real-data micro comparison","paper artifact regeneration from validated E1 outputs"],
        "budget":{"total_gpu_hours":0,"cpu_time":"under one minute expected after setup","hardware":"local CPU","network":"one small official JSON acquisition if not cached","long_runs_requiring_signoff":[]},
    }
    contract["approval_status"] = "approved"
    contract["approved_at"] = "2026-08-14"
    contract["approval_channel"] = "researcher conversation"
    contract["approval_contract_version"] = contract["contract_version"]
    approval_fields = {
        "approval_status",
        "approved_at",
        "approval_channel",
        "approval_contract_sha256",
        "approval_contract_version",
    }
    unsigned = {key: value for key, value in contract.items() if key not in approval_fields}
    canonical = json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    contract["approval_contract_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    setup = f'''<h4>5.1 Setup</h4>
      <p>The real-data evaluation uses the confirmed <a href="{URLS['clinc']}">CLINC150</a> four-intent micro subset, capped at 120 records across weather, restaurant_reviews, change_speed, and balance; exact record acquisition is deferred to the executable run plan. The selected local controls are Majority Classifier and Word-unigram Naive Bayes, while the proposed method changes only the feature extractor to character trigrams.</p>
      <p>Metrics are <a href="{URLS['clinc_paper']}">Accuracy</a>（DIRECT from the CLINC150 evaluation protocol）, <a href="{URLS['clinc_paper']}">Macro-F1</a>（DIRECT from the CLINC150 evaluation protocol）, and <a href="{URLS['external']}">Robustness Drop</a>（ADAPTED from Pruthi et al. adversarial accuracy comparison）. Accuracy is correct predictions divided by records; Macro-F1 is the unweighted mean of four one-vs-rest F1 values; Robustness Drop is clean Accuracy minus perturbed Accuracy.</p>
      <div class="table-wrap"><table class="implementation-table"><thead><tr><th>Method</th><th>How it is implemented</th></tr></thead><tbody>{''.join(f'<tr><th>{html.escape(item["display_name"])}</th><td>{html.escape(item["implementation_summary"])}</td></tr>' for item in implementations)}</tbody></table></div>'''

    blueprint_parts: list[str] = []
    for section in sections:
        title = section["title"]
        if section["id"] == "experiments":
            blueprint_parts.append(f"<h4>{html.escape(title)}</h4>{setup}{paragraph_table(section['paragraphs'])}")
            blueprint_parts.append(f"<h4>5.2 Main Results and Feature Ablation</h4>{t1_html}")
            blueprint_parts.append(f"<h4>5.3 Sensitivity, Cost, and Failures</h4>{f2_html}")
        else:
            blueprint_parts.append(f"<h4>{html.escape(title)}</h4>{paragraph_table(section['paragraphs'])}")

    artifact_rows = []
    for artifact in artifacts:
        dims = ", ".join(artifact["visible_dimensions"])
        artifact_rows.append(
            f'<tr><th>{artifact["id"]}</th><td>{artifact["kind"]}</td><td>{artifact["span"]}</td>'
            f'<td>{html.escape(", ".join(artifact["supports"]))}</td><td>{html.escape(dims)}</td></tr>'
        )

    claim_rows = "".join(
        f'<tr><th>{item["id"]}</th><td>{html.escape(item["claim"])}</td><td>{html.escape(item["falsifier"])}</td><td>{html.escape(", ".join(item["measurement_contract"]["metric_ids"]))}</td></tr>'
        for item in claims
    )

    css = '''
    :root{--ink:#172a35;--muted:#617681;--teal:#087f74;--line:#cbdad9;--wash:#f4f8f7;--warn:#9b3c2e}
    *{box-sizing:border-box}body{margin:0;background:white;color:var(--ink);font:16px/1.58 Inter,system-ui,sans-serif}main{max-width:1320px;margin:auto;padding:42px 48px 96px}
    h1{font:700 40px/1.12 Georgia,serif;margin:5px 0 12px}h2{font:700 29px/1.2 Georgia,serif;margin:52px 0 18px;border-bottom:2px solid var(--teal);padding-bottom:8px}h3{font:700 22px/1.25 Georgia,serif;margin:32px 0 12px}h4{font-size:18px;margin:24px 0 8px}.kicker{letter-spacing:.12em;text-transform:uppercase;color:var(--teal);font-weight:800}.hero{border-left:5px solid var(--teal);padding:8px 22px;background:var(--wash)}a{color:#076e68}.float-budget{font-size:18px;border:2px solid var(--teal);padding:14px 18px;background:#edf8f5;font-weight:800}.table-wrap{overflow:auto;margin:12px 0 20px}table{width:100%;border-collapse:collapse;min-width:720px}th,td{border:1px solid var(--line);padding:10px 11px;text-align:left;vertical-align:top}thead th{background:#eaf3f1}tbody th{background:#f7faf9}.pending{color:var(--warn);font-weight:800;text-align:center;background:#fff7f3}.shell{border-top:3px solid var(--teal);margin:22px 0 32px;padding-top:12px}.shell-title{font:700 20px Georgia,serif}.warning{color:var(--warn);font-weight:800}.panel-pair{display:grid;grid-template-columns:minmax(0,1.08fr) minmax(0,.92fr);gap:20px;align-items:start;margin:17px 0 26px}.panel-pair>*{min-width:0}.projected-preview{border:1px solid var(--line);padding:10px;background:#fff}.projected-preview img{width:100%;max-width:100%;height:auto;display:block}.projected-preview p{font-size:13px;color:var(--muted)}code{font-size:.88em}var{font-family:Georgia,serif;font-style:italic}var sub{font-style:normal;font-size:.72em}.approval{background:#f5f8f7;border:2px solid var(--line);padding:20px}.budget{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.budget>div{border:1px solid var(--line);padding:15px}@media(max-width:900px){main{padding:26px 17px}.panel-pair,.budget{grid-template-columns:1fr}body{font-size:15px}}
    '''
    document = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Micro Typo-Robust Intent Classification Experiment Plan</title><style>{css}</style></head><body><main>
      <p class="kicker">EXPERIMENT PLAN · REAL-DATA MICRO STUDY · 2026-08-14</p><h1>Character Granularity under Typographical Shift</h1><p>真实公开数据、真实本地分类与真实指标；规模刻意缩小，用于快速验证后续 research skills。</p>
      <template aria-hidden="true"><h2>1. Target Conference and Reference Papers</h2><div class="hero"><p><strong>Target conference:</strong> <a href="{URLS['venue']}">COLING 2027 Short Paper</a></p><p><strong>External mechanism reference:</strong> <a href="{URLS['external']}">Pruthi et al. (2019)</a></p><p><strong>Researcher-owned structure reference:</strong> <a href="{URLS['owned']}">Wang et al. (2025)</a></p></div><h2>2. Projected Paper</h2></template>
      <section data-report-section="target-and-references"><h2>1. Target Conference and Reference Papers</h2><div class="hero">
        <p><strong>Target conference:</strong> <a href="{URLS['venue']}">COLING 2027 Short Paper</a>；正文上限 4 页，ARR deadline 2026-10-12，status: upcoming。</p>
        <p><strong>External mechanism reference:</strong> Pruthi et al., <a href="{URLS['external']}">Combating Adversarial Misspellings with Robust Word Recognition</a>（ACL 2019），负责扰动、鲁棒性和比较逻辑。</p>
        <p><strong>Researcher-owned structure reference:</strong> Wang et al., <a href="{URLS['owned']}">Word Form Matters: LLMs' Semantic Reconstruction under Typoglycemia</a>（Findings of ACL 2025；publication key <code>wang2025word</code>），只负责章节顺序、段落功能和图表节奏。</p>
      </div></section>
      <section data-report-section="projected-paper"><h2>2. Projected Paper</h2><p class="float-budget">图表数量：本计划 3（2 图，1 表） · 参考论文 4（4 图，0 表）</p>
        <section data-report-subsection="projected-title-abstract"><h3>2.1 Projected Title and Abstract</h3>
          <p><strong>Projected title:</strong> Character Trigrams Preserve Micro Intent Classification under Typographical Shift</p>
          <p><strong>PROJECTED — not results:</strong> Small spelling changes can preserve a user's intent while disrupting word-based text classifiers. Existing robustness studies often use neural systems and broad attack suites, which makes them slow for testing a complete experimental workflow. We present a controlled real-data micro study that changes only feature granularity inside one multinomial Naive Bayes classifier. We evaluate Majority, word-unigram, and character-trigram variants on four confirmed CLINC150 intents under deterministic internal-character swaps. The study records every input edit and prediction, and reports clean Accuracy, typo Accuracy, Macro-F1, and Robustness Drop. If the hypothesis holds, character trigrams will reduce the 10% swap Robustness Drop by [X%] while keeping clean Accuracy within [X%] of word unigrams. A four-rate sensitivity curve will show whether the advantage persists as corruption increases. These results would establish only a reproducible micro-scale feature effect, not state-of-the-art or broad adversarial robustness.</p>
        </section>
        <section data-report-subsection="figure-table-count"><h3>2.2 Figure/Table Count</h3><p>F1 is a count-only motivation figure; T1 and F2 are the only experiment-backed artifacts, and both are filled by one real local run.</p></section>
        <section data-report-subsection="paragraph-blueprint"><h3>2.3 Paragraph Blueprint and Evidence Shells</h3>{''.join(blueprint_parts)}
          <p><strong>Page-fill feasibility:</strong> 这是一项刻意缩小的真实实验；3 个内容图表少于结构参考的 4 个，适合测试完整 skill 流程，但不足以支撑正式 COLING 投稿，除非批准后另行扩展实验范围。</p>
        </section>
        <h3>Compact artifact ledger</h3><div class="table-wrap"><table><thead><tr><th>Artifact</th><th>Kind</th><th>Span</th><th>Claims</th><th>Visible dimensions</th></tr></thead><tbody>{''.join(artifact_rows)}</tbody></table></div>
        <section data-report-subsection="claim-falsifier-evidence"><h3>2.4 Claim–Falsifier–Evidence</h3><div class="table-wrap"><table><thead><tr><th>Claim</th><th>Approved statement</th><th>Decisive falsifier</th><th>Metrics</th></tr></thead><tbody>{claim_rows}</tbody></table></div></section>
        <section data-report-subsection="implementation-plan"><h3>2.5 Implementation Plan</h3><p>R1 only supplies the official CLINC150 JSON. Every classifier, perturbation, metric, provenance record, and result file is implemented in one local framework, so all methods differ only where the plan says they differ.</p><div class="table-wrap"><table class="implementation-table"><thead><tr><th>Method</th><th>How it is implemented</th></tr></thead><tbody>{''.join(f'<tr><th>{html.escape(item["display_name"])}</th><td>{html.escape(item["implementation_summary"])}</td></tr>' for item in implementations)}</tbody></table></div></section>
        <section data-report-subsection="budget-decision-criteria"><h3>2.6 Budget and Decision Criteria</h3><div class="budget"><div><strong>Compute</strong><br>0 GPU-hours; local CPU; expected under one minute after setup.</div><div><strong>Continue</strong><br>Both reruns match and C2 passes both the robustness and clean-accuracy conditions.</div><div><strong>Stop or narrow</strong><br>Stop on provenance mismatch; report a negative micro result if either claim is falsified.</div></div><p>The first three dependencies are E0 instrumentation sanity, E1 unified real-data micro comparison, and artifact regeneration from validated E1 outputs.</p></section>
      </section>
      <section data-report-section="approval"><h2>3. Approval</h2><div class="approval"><p><strong>Status:</strong> pending researcher approval.</p><p>Approval freezes the real CLINC150 micro scope, B1+B2, the character-trigram method, T1/F2 acquisition contracts, and the CPU-only budget; it does not start experiments or `$runplan`.</p></div></section>
      <script type="application/json" id="experiment-plan-contract">{json.dumps(contract, ensure_ascii=False, separators=(',', ':'))}</script>
    </main></body></html>'''
    OUT.write_text(document, encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
