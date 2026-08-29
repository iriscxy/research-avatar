#!/usr/bin/env python3
"""Build the local workflow demo around the option-order permutation study."""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "research_avatar/web/demo"
ARTIFACTS = DEMO / "artifacts"
PAPER = ROOT / "research_avatar/online_studio/demo_project/paper"
PROJECT = ROOT / "research_avatar/online_studio/demo_project"
SOURCE_PATHS = {
    "profile.html": PROJECT / "researcher-profile/PROFILE.html",
    "literature.html": PROJECT / "reports/01_LIT_SURVEY.html",
    "ideas.html": PROJECT / "reports/02_IDEA_REPORT.html",
    "expplan.html": PROJECT / "reports/03_EXPERIMENT_PLAN.html",
    "runplan.html": PROJECT / "reports/04_RUN_PLAN.html",
}

# The public demo deliberately stores only distilled rhetorical moves. It must
# never embed or depend on the uploaded reference paper's verbatim transcript.
REFERENCE_MOVES = {
    "abstract": [
        "Open with the problem, identify the limitation of the prevailing account, introduce the proposed explanation, summarize the evidence, and close with a bounded implication.",
    ],
    "introduction": [
        "Establish why the problem matters and define the concrete behavior under study.",
        "Narrow from the broad motivation to the unresolved empirical gap.",
        "State the proposed perspective and explain how it resolves the gap.",
        "Separate what the study can determine from what remains uncertain.",
    ],
    "related_work": [
        "Group the closest methodological work by shared objective and limitation.",
        "Contrast the target contribution with methods that optimize performance rather than explain behavior.",
        "Synthesize the theoretical thread and locate the paper's distinct scope.",
    ],
    "method": [
        "Introduce the controlled approximation used to connect the hypothesis to observable behavior.",
        "Define the probing procedure before presenting implementation details.",
        "Describe the ordered stages that construct and inspect the local analysis space.",
        "Specify fixed settings, swept variables, and the resulting measurements.",
    ],
    "experiments": [
        "Name the evaluated models and justify the selected intervention points.",
        "Describe dataset construction and the sampling protocol.",
        "Define the compared methods and the inference-time sweep.",
        "State the evaluation metric and how the response trend is summarized.",
    ],
    "discussion": [
        "Frame the interpretation around which quantities are observable and which are not.",
        "State the formal limitation that bounds predictability.",
    ],
    "conclusion": [
        "Recap the contribution, the explanatory mechanism, the evidence boundary, and concrete future work.",
    ],
}

REFERENCE_LOGIC = {
    "abstract": "The abstract first presents the problem and limitations, then gives explanations, evidence, and prudent conclusions.",
    "introduction": "The Introduction narrows from importance to the gap, then proposes a plan and verifiable boundaries.",
    "related_work": "The reference paper first categorizes methods and theory, then situates its own contribution.",
    "method": "Reference Methods section first outlines the idea, then defines the process and implementation details.",
    "experiments": "Reference experiment section explains settings, data, comparison methods and metrics.",
    "discussion": "Discussion area distinguishes observable conclusions, indeterminate parts and applicable boundaries.",
    "conclusion": "Reference conclusions summarize contributions, evidence boundaries, and future directions.",
}


def page(title: str, body: str, embedded: str = "") -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>body{{font:15px/1.65 system-ui;margin:0;color:#17333d;background:#f5f8f7}}main{{max-width:1080px;margin:auto;padding:38px}}section{{margin:24px 0;padding:20px;background:#fff;border:1px solid #d7e3e0;border-radius:10px}}h1,h2,h3,h4{{font-family:Georgia,serif}}.paragraph{{margin:12px 0;padding:13px;border-left:3px solid #15917e;background:#f7fbfa}}small{{color:#60767e}}details{{margin-top:8px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px;border:1px solid #d7e3e0;text-align:left}}th{{background:#eaf4f1}}.pending{{color:#94620d;background:#fff8e8}}code{{white-space:pre-wrap}}</style></head><body><main><h1>{html.escape(title)}</h1>{body}{embedded}</main></body></html>"""


def write(name: str, source: str) -> None:
    (ARTIFACTS / name).write_text(source, encoding="utf-8")
    canonical = SOURCE_PATHS[name]
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_text(source, encoding="utf-8")


def prepare_paper_project() -> None:
    metrics_path = PAPER / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics.setdefault("lightweight_results", {})["rows"] = []
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_distilled_reference_context() -> None:
    """Replace private reference prose with a self-contained public summary."""
    config = json.loads((PAPER / "paper_studio.json").read_text(encoding="utf-8"))
    sections: dict[str, dict[str, object]] = {}
    for section in config["sections"]:
        section_id = section["id"]
        moves = REFERENCE_MOVES[section_id]
        paragraphs = section["paragraphs"]
        if len(moves) != len(paragraphs):
            raise ValueError(
                f"Reference-move count mismatch for {section_id}: "
                f"{len(moves)} moves for {len(paragraphs)} paragraphs"
            )
        excerpts = []
        for paragraph, move in zip(paragraphs, moves):
            reference_ids = paragraph.get("reference_paragraph_ids") or []
            if len(reference_ids) != 1:
                raise ValueError(
                    f"{paragraph['id']} must map to exactly one distilled reference move"
                )
            excerpts.append({
                "reference_paragraph_id": reference_ids[0],
                "text": move,
                "distilled": True,
            })
        sections[section_id] = {
            "source_heading": section["title"],
            "logic_summary_zh": REFERENCE_LOGIC[section_id],
            "excerpts": excerpts,
        }
    payload = {
        "reference_title": config["project"]["reference_paper"]["title"],
        "reference_source": "",
        "public_demo_distilled": True,
        "sections": sections,
    }
    (PAPER / "reference_context.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_profile() -> None:
    write("profile.html", page("Researcher Profile", """
<section data-report-section="research-interests"><h2>1. Research Interests</h2><p>Large-language-model evaluation, behavioral robustness, controlled black-box interventions, and reproducible short experiments.</p></section>
<section data-report-section="workflow-preferences"><h2>2. Workflow Preferences</h2><p>Prefer compact falsifiable questions, deterministic API settings, explicit data contracts, and paper figures whose plotted values are shown in adjacent source tables.</p></section>"""))


def build_literature() -> None:
    write("literature.html", page("Literature Survey: Option-Order Sensitivity", """
<section data-report-section="problem"><h2>1. Problem</h2><p>Multiple-choice evaluation assumes that changing only the position labels of semantically identical answers should not alter a model's selected answer. Violations indicate a surface-form dependency that benchmark accuracy alone does not reveal.</p></section>
<section data-report-section="approaches"><h2>2. Approaches</h2><p>Relevant work studies prompt sensitivity, label bias, calibration, and robustness under meaning-preserving perturbations. The present study isolates one intervention: permuting answer choices while preserving question and option semantics.</p></section>
<section data-report-section="evaluation"><h2>3. Evaluation</h2><p>Useful measurements include permutation consistency, answer-flip rate, accuracy range across orderings, and per-question entropy. Paired question-level analysis separates ordering effects from differences in item difficulty.</p></section>
<section data-report-section="gaps"><h2>4. Gap</h2><p>Typical benchmark reports evaluate one canonical order. A small controlled study can expose how much the reported answer depends on the arbitrary presentation order and whether the effect concentrates in particular question types.</p></section>"""))


def build_ideas() -> None:
    selection = {"selected_id": "I1", "selected_title": "Does Random Option Ordering Change Language Model Answers?", "reason": "Selected as the compact controlled black-box evaluation used by this local project.", "confirmed_at": "2026-08-23"}
    embedded = '<script type="application/json" id="idea-selection">' + json.dumps(selection, ensure_ascii=False).replace("<", "\\u003c") + "</script>"
    write("ideas.html", page("Research Idea", """
<section data-report-section="selected-idea"><h2>1. Selected Idea</h2><article data-idea-id="I1" data-selected="true"><h3>I1 · Does Random Option Ordering Change Language Model Answers?</h3><p class="pitch">Hold every question and answer meaning fixed, randomly permute the answer order, relabel A/B/C/D, and test whether the model's semantic choice remains invariant.</p></article></section>
<section data-report-section="falsifier"><h2>2. Claim and Falsifier</h2><p>The study is informative if answer consistency can be measured with paired interventions. A near-zero flip rate with tight uncertainty weakens the practical claim that option ordering materially affects this model and dataset.</p></section>
<section data-report-section="scope"><h2>3. Ten-Minute Scope</h2><p>Use 100 questions, five orderings per question, temperature 0, and exactly 500 model calls. Report the result as a bounded black-box evaluation rather than a universal claim about reasoning.</p></section>""", embedded))


def build_expplan() -> None:
    config = json.loads((PAPER / "paper_studio.json").read_text(encoding="utf-8"))
    references = json.loads((PAPER / "reference_context.json").read_text(encoding="utf-8"))
    paragraphs: list[str] = []
    for section in config["sections"]:
        section_id = section["id"]
        context = references["sections"][section_id]
        paragraphs.append(f"<h4>{html.escape(section['title'])}</h4>")
        excerpts = context["excerpts"]
        for index, paragraph in enumerate(section["paragraphs"]):
            excerpt = excerpts[min(index, len(excerpts) - 1)]
            artifacts = ", ".join(paragraph.get("artifacts") or []) or "none"
            paragraphs.append(
                '<div class="paragraph">'
                f"<b>{html.escape(paragraph['id'])}</b> · {html.escape(paragraph['purpose'])}<br>"
                f"<small>Role: {html.escape(paragraph['rhetorical_role'])} · Bound artifacts: {html.escape(artifacts)}</small>"
                "<details><summary>Distilled reference move</summary><article>"
                f"<p><b>{html.escape(excerpt['reference_paragraph_id'])} · {html.escape(context['source_heading'])}</b></p>"
                f"<p>{html.escape(excerpt['text'])}</p>"
                f"<p>{html.escape(context['logic_summary_zh'])}</p>"
                "</article></details></div>"
            )
    body = f"""
<section data-report-section="target-and-references"><h2>1. Target Conference and Reference Paper</h2><p><b>Target:</b> ACL short paper.</p><p><b>Topic:</b> permutation invariance of multiple-choice answers under semantics-preserving option reordering.</p><p><b>Structure reference:</b> {html.escape(references['reference_title'])}. It supplies paragraph organization only.</p></section>
<section data-report-section="projected-paper"><h2>2. Projected Paper</h2><section data-report-subsection="projected-title-abstract"><h3>2.1 Projected Title and Abstract</h3><p>{html.escape(config['project']['name'])}</p></section><section data-report-subsection="projected-paper-structure"><h3>2.2 Projected Paper Structure and Evidence Shells</h3>{''.join(paragraphs)}</section></section>
<section data-report-section="claims"><h2>3. Claims and Falsifiers</h2><table><tr><th>Claim</th><th>Supporting pattern</th><th>Falsifier</th></tr><tr><td>C1: answers are not perfectly permutation invariant</td><td>Non-zero paired flip rate with uncertainty excluding zero</td><td>Near-zero flip rate with a tight interval</td></tr><tr><td>C2: sensitivity is structured</td><td>Stable differences by question type or option position</td><td>No reproducible subgroup difference</td></tr></table></section>
<section data-report-section="experiments"><h2>4. Experiment Program</h2><p>Sample 100 questions. Create the original ordering plus four random permutations, update answer labels, use temperature 0, request only the final option, and issue 500 calls. Preserve question ID, permutation ID, option mapping, raw response, parsed semantic answer, correctness, latency, and token use.</p></section>
<section data-report-section="artifacts"><h2>5. Planned Paper Artifacts</h2><table><tr><th>ID</th><th>Artifact</th><th>Source data</th></tr><tr><td>F1</td><td>Motivation diagram of one question under two option orders</td><td>Question, mappings, and two responses</td></tr><tr><td>F2</td><td>Permutation-consistency curve</td><td>Permutation count x and consistency rate y</td></tr><tr><td>T1</td><td>Main paired results</td><td>Accuracy, flip rate, consistency, and uncertainty</td></tr></table></section>"""
    contract = {
        "schema_version": 2,
        "approval_status": "approved",
        "approved_at": "2026-08-23",
        "selected_idea": {"id": "I1", "title": "Does Random Option Ordering Change Language Model Answers?"},
        "target": {"venue": "ACL short paper", "paper_type": "short paper"},
        "baseline_contract": {"selected": ["original option order", "four semantics-preserving random permutations"]},
        "paper_artifacts": [
            {"id": "F1", "title": "Motivation example"},
            {"id": "F2", "title": "Permutation-consistency curve"},
            {"id": "T1", "title": "Paired main results"},
        ],
    }
    embedded = '<script type="application/json" id="experiment-plan-contract">' + json.dumps(contract, ensure_ascii=False).replace("<", "\\u003c") + "</script>"
    write("expplan.html", page("Experiment Plan: Option-Order Permutation", body, embedded))


def run_state() -> dict:
    goals = [
        ("P1", "G1.1", "Freeze questions and permutation protocol", ["F1"]),
        ("P2", "G2.1", "Generate and validate five orderings per question", []),
        ("P3", "G3.1", "Execute 500 deterministic model calls", ["T1"]),
        ("P4", "G4.1", "Compute paired invariance metrics and uncertainty", ["T1", "F2"]),
        ("P5", "G5.1", "Audit subgroups and representative answer flips", ["F1", "F2"]),
    ]
    parts = []
    goal_rows = []
    previous = []
    for part_id, goal_id, title, artifacts in goals:
        parts.append({"id": part_id, "title": title, "decision": "Complete and verify this evidence stage before advancing.", "status": "completed", "goals": [goal_id]})
        goal_rows.append({"id": goal_id, "part_id": part_id, "title": title, "status": "completed", "depends_on": list(previous), "artifact_ids": artifacts, "decision_question": "Does the saved evidence satisfy the approved acquisition contract?", "visible_work": "Run the recorded command and persist its manifest, logs, and raw outputs.", "visible_evidence": "Verified structured records linked to every displayed value.", "completion_check": "command exited successfully; raw records, provenance, and assigned artifacts validate", "goal_command": f"/goal {goal_id}"})
        previous = [goal_id]
    return {"schema_version": 2, "source_plan": "reports/03_EXPERIMENT_PLAN.html", "execution_mode": "sequential_all_goals", "goal_confirmation": {"status": "confirmed", "scope": "all_goals", "confirmed_goal_ids": [g[1] for g in goals]}, "state": "completed", "status": "completed", "active_goal": None, "proposed_goal_id": None, "approved_artifact_ids": ["F1", "F2", "T1"], "parts": parts, "goals": goal_rows}


def build_runplan() -> None:
    state = run_state()
    goals = "".join(f"<article><h3>✅ {html.escape(goal['id'])} · {html.escape(goal['title'])}</h3><p>{html.escape(goal['visible_work'])}</p><p><b>Completion:</b> {html.escape(goal['completion_check'])}</p></article>" for goal in state["goals"])
    body = f"""
<section data-report-section="execution-estimate"><h2>1. Execution Estimate</h2><p>Five sequential goals; the core run contains exactly 500 API calls. Wall time and cost depend on the selected model endpoint and are recorded from the actual run.</p></section>
<section data-report-section="implementation-sources"><h2>2. Implementation Sources</h2><p><code>python code/run_option_permutations.py --config code/configs/option_order.json --output results/option_order</code></p><p>The run manifest records working directory, entrypoint, arguments, inputs, environment, logs, exit status, timestamps, outputs, and revision.</p></section>
<section data-report-section="artifact-coverage"><h2>3. Figure/Table Coverage</h2><p>G1.1→F1; G3.1→T1; G4.1→T1/F2; G5.1→F1/F2.</p></section>
<section data-report-section="parts-and-goals"><h2>4. Parts and Goals</h2>{goals}</section>"""
    embedded = '<script type="application/json" id="run-plan-state">' + json.dumps(state, ensure_ascii=False).replace("<", "\\u003c") + "</script>"
    write("runplan.html", page("Run Plan: Option-Order Permutation", body, embedded))
    (DEMO / "runplan-state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_results() -> None:
    rows = [(1, "94.0%"), (2, "91.0%"), (3, "89.0%"), (4, "88.0%")]
    table_rows = "".join(
        f"<tr><th>{count}</th><td>{rate}</td></tr>" for count, rate in rows
    )
    result_payload = html.escape(json.dumps(
        [{"permutation_count": count, "consistency_rate": float(rate[:-1]) / 100}
         for count, rate in rows],
        ensure_ascii=False,
        indent=2,
    ))
    body = f"""
<section data-report-section="scope"><h2>1. Result Scope</h2><p>This local demonstration uses 100 multiple-choice questions, the original order plus four semantics-preserving random option permutations, temperature 0, and 500 model calls. The original ordering is always the reference condition.</p></section>
<section data-report-section="main-result"><h2>2. F2 · Permutation-Consistency Curve</h2><p>For each cumulative permutation count k, consistency is the proportion of questions receiving the same semantic answer in the original ordering and every included permutation.</p><table><thead><tr><th>x · Random permutations included</th><th>y · Questions with a consistently identical answer</th></tr></thead><tbody>{table_rows}</tbody></table></section>
<section data-report-section="main-table"><h2>3. T1 · Paired Main Results</h2><table><thead><tr><th>Questions</th><th>Calls</th><th>Orderings per question</th><th>Consistency after four permutations</th><th>Any-flip rate</th></tr></thead><tbody><tr><td>100</td><td>500</td><td>5</td><td>88.0%</td><td>12.0%</td></tr></tbody></table></section>
<section id="provenance-f2" data-report-section="provenance"><h2>4. Data and Acquisition Record</h2><p><b>Command:</b> <code>python code/run_option_permutations.py --config code/configs/option_order.json --output results/option_order</code></p><p><b>Expected run files:</b> <code>run_manifest.json</code>, <code>stdout.log</code>, <code>stderr.log</code>, <code>responses.jsonl</code>, and <code>G4.1/consistency_by_count.json</code>.</p><p><b>Coordinate data shown above:</b></p><pre>{result_payload}</pre><p><b>Demo status:</b> These values form the fixed completed example used by the local Research Studio interface; replace them with a real run before making empirical claims.</p></section>"""
    target = PROJECT / "reports/05_EXP_RESULT.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page("Experiment Results: Option-Order Permutation", body), encoding="utf-8")


def write_manifest() -> None:
    sources = {
        "profile": SOURCE_PATHS["profile.html"],
        "literature": SOURCE_PATHS["literature.html"],
        "ideas": SOURCE_PATHS["ideas.html"],
        "expplan": SOURCE_PATHS["expplan.html"],
        "runplan": SOURCE_PATHS["runplan.html"],
    }
    manifest = {}
    for key, source_path in sources.items():
        artifact = ARTIFACTS / f"{key}.html"
        manifest[key] = {"url": f"artifacts/{key}.html", "source": source_path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()}
    (DEMO / "artifact-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    prepare_paper_project()
    build_distilled_reference_context()
    build_profile()
    build_literature()
    build_ideas()
    build_expplan()
    build_runplan()
    build_results()
    write_manifest()
    print(json.dumps({"topic": "option-order permutation", "artifacts": 5, "goals": 5}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
