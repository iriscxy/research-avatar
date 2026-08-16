import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from research_avatar.tools import paper_checks, validate_ideagen_report


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_experiment_plan",
    ROOT / ".agents/skills/expplan/scripts/validate_experiment_plan.py",
)
EXPPLAN_VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXPPLAN_VALIDATOR)
RUNPLAN_SPEC = importlib.util.spec_from_file_location(
    "validate_results_ledger",
    ROOT / ".agents/skills/runplan/scripts/validate_results_ledger.py",
)
RUNPLAN_VALIDATOR = importlib.util.module_from_spec(RUNPLAN_SPEC)
RUNPLAN_SPEC.loader.exec_module(RUNPLAN_VALIDATOR)


def write_plan(path: Path, contract: dict) -> None:
    path.write_text(
        '<script type="application/json" id="experiment-plan-contract">'
        + json.dumps(contract)
        + "</script>",
        encoding="utf-8",
    )


def scientific_contract() -> dict:
    metric_common = {
        "provenance": "DIRECT",
        "range": "[0,1]",
        "decision_rule": "higher is better",
        "aggregation": "macro mean",
        "url": "https://example.org/protocol",
        "alternative_explanations": [],
        "companion_requirements": [],
    }
    return {
        "approval_status": "pending",
        "profile_contract": {
            "profile_path": "researcher-profile/PROFILE.html",
            "publications_path": "researcher-profile/publications.json",
            "researcher_identity": "Fixture Researcher",
            "authorship_verified": True,
            "structure_reference_key": "fixture2026",
        },
        "generated_at": "2026-08-09",
        "target": {"deadline_status": "upcoming", "confirmed_at": "2026-08-09"},
        "references": {"confirmed_at": "2026-08-09", "researcher_owned_structure": {
            "url": "https://example.org/owned", "local_full_text": "owned.txt",
            "publication_key": "fixture2026",
        }},
        "dataset_confirmation": {"confirmed": True, "confirmed_at": "2026-08-09"},
        "grounding": {},
        "metric_contract": [
            {
                **metric_common,
                "id": "M-current",
                "name": "current-evidence accuracy",
                "definition": "fraction selecting the latest valid evidence",
                "construct": "temporal currentness",
                "cannot_establish": "general multimodal consistency",
                "claim_mappings": [{
                    "claim_id": "C1",
                    "measurement_role": "DIRECT",
                    "cannot_establish": "performance outside update events",
                    "companion_requirements": [],
                }],
            },
            {
                **metric_common,
                "id": "M-core",
                "name": "CoRe",
                "definition": "multimodal consistency and reliability",
                "construct": "multimodal consistency",
                "cannot_establish": "temporal currentness",
                "companion_requirements": ["M-current"],
                "claim_mappings": [{
                    "claim_id": "C1",
                    "measurement_role": "PROXY",
                    "cannot_establish": "selection of the newest evidence",
                    "companion_requirements": ["M-current"],
                }],
            },
        ],
        "claims": [{
            "id": "C1",
            "measurement_contract": {
                "construct_definition": "select evidence valid at query time",
                "primary_observable": "selected source timestamp and validity",
                "metric_ids": ["M-current", "M-core"],
                "measurement_role": "DIRECT",
                "cannot_establish": "all forms of memory quality",
                "alternative_explanations": ["retrieval recall"],
                "required_controls": ["matched retrieval candidate set"],
                "support_pattern": "higher current-evidence accuracy",
                "weaken_pattern": "gain only in CoRe",
                "falsify_pattern": "no currentness gain under matched recall",
                "uncertainty_rule": "95% bootstrap interval",
            },
        }],
        "decision_space_contract": [{
            "id": "D1",
            "experiment_ids": ["E1"],
            "decision_variable": "authority-score weights and abstention margin",
            "disposition": "SEARCHED",
            "allowed_values": {"weight": [0, 0.25, 0.5, 1], "margin": [0.05, 0.1, 0.2]},
            "source": "bounded design space",
            "selection_rule": "maximize current-evidence accuracy, then minimize abstention",
            "selection_observable": "development current-evidence accuracy",
            "budget": "12 configurations",
            "freeze_point": "before final evaluation",
            "final_value_source": "runplan frozen-configuration record",
            "test_access_prohibited": True,
        }],
        "consistency_requirements": {
            "canonical_terms": ["M-current", "M-core"],
            "source_values": ["D1"], "formal_links": [],
        },
        "paper_artifacts": [],
        "result_requirements": [],
        "paper_outline": [],
        "baseline_contract": {"selected": [], "unselected": []},
        "repository_contract": {"references": []},
    }


class GengsenRegressionTests(unittest.TestCase):
    def test_scope_gate_relabels_evaluation_only_scope(self):
        old = '<article data-idea-id="I1"><h2>Multimodal Temporal Authority Memory</h2></article>'
        self.assertTrue(validate_ideagen_report.validate(old))
        corrected = (
            '<script id="idea-novelty-audit" type="application/json">'
            '{"candidates":[{"idea_id":"I1","verdict":"novel","absorbable":false,'
            '"closest_work":"Prior memory","overlap":"retrieval",'
            '"independent_difference":"authority mechanism","latest_search_date":"2026-08-09",'
            '"review_context":"fresh","reviewer_run_id":"gengsen-review-1",'
            '"source_urls":["https://arxiv.org/abs/2601.00001",'
            '"https://aclanthology.org/2026.acl-long.1/"]}]}</script>'
            '<article data-idea-id="I1" data-scope-necessity="EVALUATION_SCOPE_ONLY" '
            'data-scope-action="relabel" data-novelty-status="novel" '
            'data-idea-tier="A" data-default-pick="true">'
            '<h2>Temporal Authority Memory</h2></article>'
        )
        self.assertEqual(validate_ideagen_report.validate(corrected), [])

    def test_expplan_rejects_old_and_accepts_new_scientific_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "03.html"
            old = scientific_contract()
            for metric in old["metric_contract"]:
                for key in ("id", "construct", "claim_mappings", "cannot_establish",
                            "alternative_explanations", "companion_requirements"):
                    metric.pop(key, None)
            old["claims"] = [{"id": "C1"}]
            old.pop("decision_space_contract")
            write_plan(path, old)
            old_errors = EXPPLAN_VALIDATOR.validate(path)
            self.assertTrue(any("measurement_contract" in error for error in old_errors))
            self.assertTrue(any("decision_space_contract" in error for error in old_errors))

            proxy_only = scientific_contract()
            proxy_only["claims"][0]["measurement_contract"]["metric_ids"] = ["M-core"]
            write_plan(path, proxy_only)
            proxy_errors = EXPPLAN_VALIDATOR.validate(path)
            self.assertTrue(any("no directly mapped metric" in error for error in proxy_errors))

            write_plan(path, scientific_contract())
            new_errors = EXPPLAN_VALIDATOR.validate(path)
            relevant = [error for error in new_errors if any(token in error for token in (
                "metric_contract", "measurement_contract", "decision_space_contract", "uses a proxy"
            ))]
            self.assertEqual(relevant, [])

    def test_runplan_preserves_and_freezes_the_decision_space(self):
        contract = scientific_contract()
        decision = contract["decision_space_contract"]
        old_state = {"goals": [{"id": "G3.1", "stage": "S3", "decision_ids": ["D1"]}]}
        old_errors = RUNPLAN_VALIDATOR.validate_decision_handoff(contract, old_state)
        self.assertTrue(any("dev/final split" in error for error in old_errors))

        planned = {
            "decision_space_contract": decision,
            "goals": [{"id": "G3.1", "stage": "S3", "status": "pending",
                       "decision_ids": ["D1"]}],
            "frozen_configuration": {},
            "execution_splits": [{
                "experiment_id": "E1",
                "development_source": "official development sessions",
                "final_source": "held-out official final sessions",
                "protocol_source": "benchmark protocol",
                "disjoint": True,
                "frozen_before_final": True,
            }],
        }
        self.assertEqual(RUNPLAN_VALIDATOR.validate_decision_handoff(contract, planned), [])
        planned["goals"].append({"id": "G4.1", "stage": "S4", "status": "completed",
                                 "decision_ids": []})
        self.assertTrue(any("frozen value" in error
                            for error in RUNPLAN_VALIDATOR.validate_decision_handoff(contract, planned)))
        planned["frozen_configuration"] = {
            "D1": {"value": {"weight": 0.5, "margin": 0.1}, "source_goal": "G3.1"}
        }
        self.assertEqual(RUNPLAN_VALIDATOR.validate_decision_handoff(contract, planned), [])

    def test_paper_regression_catches_old_failures_and_accepts_corrected_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = SimpleNamespace(paper_dir=str(root), main="main.tex")
            short_abstract = (
                "Persistent agents must know which evidence is current. We propose Temporal Authority "
                "Memory to rank claims by time, source, and conflict. We evaluate three benchmarks."
            )
            (root / "main.tex").write_text(
                "\\begin{document}\\begin{abstract}" + short_abstract + "\\end{abstract}"
                "\\section{Method}The identity is checked by paper/theory/verify.py."
                + "\\begin{equation}x=x\\end{equation}" * 4
                + "\\end{document}", encoding="utf-8"
            )
            (root / "abstract_contract.json").write_text(json.dumps({
                "min_words": 120, "max_words": 220, "source": "reference",
                "slot_evidence": {
                    "motivation": "Persistent agents must know",
                    "gap": "which evidence is current",
                    "method": "propose Temporal Authority Memory",
                    "evaluation_scope": "evaluate three benchmarks",
                    "principal_result": "missing result",
                    "takeaway": "missing takeaway",
                },
            }), encoding="utf-8")
            old_style = paper_checks.check_style(args)
            metrics = {item.get("metric") for item in old_style["violations"]}
            self.assertIn("abstract_length", metrics)
            self.assertIn("abstract_slots", metrics)
            self.assertIn("internal_workflow_leak", metrics)
            self.assertFalse(paper_checks.check_scholarship(args)["ok"])

            abstract = (
                "Long-horizon agents must distinguish evidence that remains valid from observations "
                "that have been superseded. Existing memory systems retrieve relevant content but do "
                "not directly represent which source is authoritative at query time, causing obsolete "
                "facts and screen states to be reused confidently. We introduce Temporal Authority "
                "Memory, a source-agnostic claim graph that records timestamps, conflicts, and "
                "supersession relations. The method ranks evidence chains with an authority score and "
                "abstains when competing chains remain unresolved. We evaluate temporal currentness on "
                "matched long-conversation and changing-state benchmarks, while multimodal consistency "
                "is reported only as a complementary outcome. Across these settings, the method improves "
                "current-evidence accuracy under a fixed retrieval candidate set and reduces stale-source "
                "selection without relying on the consistency proxy alone. Component and threshold "
                "analyses test whether the gains arise from supersession tracking rather than retrieval "
                "recall. These results make evidence freshness an explicit and falsifiable property of "
                "agent memory."
            )
            tex = (
                "\\begin{document}\\begin{abstract}" + abstract + "\\end{abstract}"
                "\\section{Method}We represent observations as time-indexed claims and resolve "
                "supersession before response generation \\cite{tamgraph}."
                + "\\begin{equation}x=x\\end{equation}" * 4
                + "\\section{Experiments}LoCoMo is a long-conversation benchmark that tests memory "
                "over extended dialogue \\cite{locomo}; we include it to measure temporal question "
                "answering without visual updates. Changing-State evaluates whether an agent selects "
                "the latest valid observation \\cite{changing}; we include it as the direct test of "
                "temporal currentness. Retrieval baselines select semantically relevant evidence "
                "\\cite{retrieval}; we include this family to isolate authority resolution from recall."
                "\\end{document}"
            )
            (root / "main.tex").write_text(tex, encoding="utf-8")
            sources = root.parent / "sources"
            sources.mkdir(exist_ok=True)
            source_text = ("resolve supersession before response generation\n"
                           "LoCoMo is a long-conversation benchmark that tests memory over extended dialogue\n"
                           "Changing-State evaluates whether an agent selects the latest valid observation\n"
                           "Retrieval baselines select semantically relevant evidence")
            (sources / "verified.txt").write_text(source_text, encoding="utf-8")
            (root / "abstract_contract.json").write_text(json.dumps({
                "min_words": 120, "max_words": 220, "source": "reference",
                "slot_evidence": {
                    "motivation": "Long-horizon agents must distinguish evidence",
                    "gap": "do not directly represent which source is authoritative",
                    "method": "introduce Temporal Authority Memory",
                    "evaluation_scope": "evaluate temporal currentness on matched long-conversation",
                    "principal_result": "improves current-evidence accuracy",
                    "takeaway": "evidence freshness an explicit and falsifiable property",
                },
            }), encoding="utf-8")
            (root / "scholarship_contract.json").write_text(json.dumps({
                "independent_source_audit": {
                    "verdict": "pass", "reviewed_at": "2026-08-09",
                    "metadata_verified": True,
                    "checked_keys": ["tamgraph", "locomo", "changing", "retrieval"],
                    "unsupported_clauses": [],
                },
                "citation_obligations": [
                    {"name": "claim graph", "kind": "method", "section": "Method",
                     "citation_key": "tamgraph", "supported_clause": "resolve supersession before response generation",
                     "source_evidence_path": "sources/verified.txt", "source_evidence_excerpt": "resolve supersession before response generation"},
                    {"name": "LoCoMo", "kind": "dataset", "section": "Experiments",
                     "citation_key": "locomo", "supported_clause": "LoCoMo is a long-conversation benchmark that tests memory over extended dialogue",
                     "source_evidence_path": "sources/verified.txt", "source_evidence_excerpt": "LoCoMo is a long-conversation benchmark that tests memory over extended dialogue"},
                    {"name": "Changing-State", "kind": "dataset", "section": "Experiments",
                     "citation_key": "changing", "supported_clause": "Changing-State evaluates whether an agent selects the latest valid observation",
                     "source_evidence_path": "sources/verified.txt", "source_evidence_excerpt": "Changing-State evaluates whether an agent selects the latest valid observation"},
                    {"name": "retrieval", "kind": "baseline family", "section": "Experiments",
                     "citation_key": "retrieval", "supported_clause": "Retrieval baselines select semantically relevant evidence",
                     "source_evidence_path": "sources/verified.txt", "source_evidence_excerpt": "Retrieval baselines select semantically relevant evidence"},
                ],
                "setup_entities": [
                    {"name": "LoCoMo", "kind": "dataset", "section": "Experiments",
                     "description_evidence": "long-conversation benchmark that tests memory",
                     "rationale_evidence": "include it to measure temporal question answering",
                     "claim_ids": ["C2"], "citation_key": "locomo"},
                    {"name": "Changing-State", "kind": "dataset", "section": "Experiments",
                     "description_evidence": "evaluates whether an agent selects the latest valid observation",
                     "rationale_evidence": "include it as the direct test of temporal currentness",
                     "claim_ids": ["C1"], "citation_key": "changing"},
                    {"name": "retrieval baselines", "kind": "baseline family", "section": "Experiments",
                     "description_evidence": "select semantically relevant evidence",
                     "rationale_evidence": "isolate authority resolution from recall",
                     "claim_ids": ["C1"], "citation_key": "retrieval"},
                ],
            }), encoding="utf-8")
            new_style = paper_checks.check_style(args)
            forbidden = {"abstract_contract", "abstract_length", "abstract_slots",
                         "internal_workflow_leak"}
            self.assertFalse(any(item.get("metric") in forbidden for item in new_style["violations"]))
            self.assertTrue(paper_checks.check_scholarship(args)["ok"])


if __name__ == "__main__":
    unittest.main()
