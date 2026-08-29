import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from research_avatar.tools import init_paper_studio_from_pipeline as initializer

from research_avatar.tools.init_paper_studio_from_pipeline import (
    artifact_binding_contract,
    completed_run_inputs,
    materialize_appendix_contracts,
    reference_contexts,
    repair_reference_context,
    require_report_html,
    result_evidence,
    selected_idea_from_report,
    validate_report_only_contract,
)


class InitPaperStudioFromPipelineTests(unittest.TestCase):
    def test_initialize_refreshes_instead_of_overwriting_accepted_browser_work(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            reports = root / "reports"
            state_dir = root / "paper/.paper_studio"
            reports.mkdir()
            state_dir.mkdir(parents=True)
            plan = reports / "03_EXPERIMENT_PLAN.html"
            results = reports / "05_EXP_RESULT.html"
            plan.write_text("<html>plan</html>", encoding="utf-8")
            results.write_text("<html>results</html>", encoding="utf-8")
            (state_dir / "state.json").write_text(json.dumps({
                "sections": {"introduction": {"paragraphs": [{
                    "id": "I-P1", "accepted_text": "Accepted manuscript text."
                }]}}
            }), encoding="utf-8")
            with patch.object(
                initializer,
                "repair_reference_context",
                return_value={"manuscript_reset": False},
            ) as repair:
                summary = initializer.initialize(root, plan, results)

            self.assertFalse(summary["manuscript_reset"])
            repair.assert_called_once_with(root, plan.resolve())

    def test_result_evidence_reads_only_the_embedded_structured_payload(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "05_EXP_RESULT.html"
            payload = {
                "execution_summary": {"saved_final_call_count": 640},
                "claim_dispositions": {"C2": {"status": "inconclusive"}},
            }
            path.write_text(
                "<p>Unstructured prose must not be parsed.</p>"
                '<script type="application/json" id="experiment-evidence">'
                + json.dumps(payload)
                + "</script>",
                encoding="utf-8",
            )

            self.assertEqual(result_evidence(path), payload)

    def test_result_evidence_rejects_a_non_object_payload(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "05_EXP_RESULT.html"
            path.write_text(
                '<script type="application/json" id="experiment-evidence">[]</script>',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "must be a JSON object"):
                result_evidence(path)

    def test_canonical_reference_mapping_survives_abstracted_external_mode(self):
        contract = {
            "references": {
                "researcher_owned_logic": {
                    "title": "Reference",
                    "mode": "abstracted",
                }
            },
            "paper_outline": [{
                "id": "introduction",
                "paragraphs": [{
                    "id": "I-P1",
                    "reference_mapping": [{
                        "source_paragraph_id": "REF-P7",
                        "source_heading": "Introduction",
                        "source_text": "A complete mapped source paragraph.",
                    }],
                }],
            }],
        }
        sections = [{
            "id": "introduction",
            "title": "Introduction",
            "paragraphs": [{
                "id": "I-P1",
                "purpose": "Frame the problem.",
                "rhetorical_role": "problem framing",
                "relation_to_previous": "opening",
                "relation_to_next": "state the gap",
            }],
        }]

        contexts = reference_contexts(contract, sections)

        self.assertEqual(sections[0]["paragraphs"][0]["reference_paragraph_ids"], ["REF-P7"])
        self.assertEqual(contexts["introduction"]["mode"], "source")
        self.assertEqual(
            contexts["introduction"]["excerpts"][0]["text"],
            "A complete mapped source paragraph.",
        )
        self.assertEqual(
            contexts["introduction"]["logic_summary_zh"],
            "I-P1(problem framing):Frame the problem.",
        )

    def test_legacy_source_mappings_remain_compatible(self):
        contract = {
            "paper_outline": [{
                "id": "method",
                "paragraphs": [{
                    "id": "M-P1",
                    "source_mappings": [{
                        "source_paragraph_id": "OLD-P2",
                        "complete_source_text": "Legacy complete paragraph.",
                    }],
                }],
            }],
        }
        sections = [{
            "id": "method",
            "title": "Method",
            "paragraphs": [{
                "id": "M-P1", "purpose": "Define the method.",
                "rhetorical_role": "method", "relation_to_previous": "gap",
                "relation_to_next": "evaluation",
            }],
        }]

        contexts = reference_contexts(contract, sections)

        self.assertEqual(contexts["method"]["mode"], "source")
        self.assertEqual(contexts["method"]["excerpts"][0]["id"], "OLD-P2")

    def test_truly_text_free_mapping_stays_abstracted(self):
        contract = {
            "references": {"researcher_owned_logic": {"mode": "abstracted"}},
            "paper_outline": [{
                "id": "abstract",
                "paragraphs": [{
                    "id": "A-P1",
                    "reference_mapping": [{"source_paragraph_id": "REF-A1"}],
                }],
            }],
        }
        sections = [{
            "id": "abstract", "title": "Abstract",
            "paragraphs": [{
                "id": "A-P1", "purpose": "Summarize.",
                "rhetorical_role": "summary", "relation_to_previous": "opening",
                "relation_to_next": "closing",
            }],
        }]

        contexts = reference_contexts(contract, sections)

        self.assertEqual(contexts["abstract"]["mode"], "abstracted")
        self.assertEqual(contexts["abstract"]["excerpts"], [])
        self.assertEqual(
            contexts["abstract"]["logic_summary_zh"],
            "A-P1(summary):Summarize.",
        )
        self.assertEqual(sections[0]["paragraphs"][0]["reference_paragraph_ids"], ["REF-A1"])

    def test_section_logic_summary_contains_the_complete_paragraph_chain(self):
        contract = {"paper_outline": [{"id": "method", "paragraphs": []}]}
        sections = [{
            "id": "method",
            "title": "Method",
            "paragraphs": [
                {"id": "M-P1", "purpose": "Define the input.",
                 "rhetorical_role": "setup", "relation_to_previous": "gap",
                 "relation_to_next": "derive the operator"},
                {"id": "M-P2", "purpose": "Derive the operator.",
                 "rhetorical_role": "mechanism", "relation_to_previous": "setup",
                 "relation_to_next": "state the output"},
                {"id": "M-P3", "purpose": "State the output criterion.",
                 "rhetorical_role": "criterion", "relation_to_previous": "mechanism",
                 "relation_to_next": "evaluation"},
            ],
        }]

        contexts = reference_contexts(contract, sections)

        self.assertEqual(
            contexts["method"]["logic_summary_zh"],
            "M-P1(setup):Define the input. → "
            "M-P2(mechanism):Derive the operator. → "
            "M-P3(criterion):State the output criterion.",
        )

    def test_reference_repair_preserves_manuscript_and_history(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            reports = root / "reports"
            paper = root / "paper"
            state_dir = paper / ".paper_studio"
            reports.mkdir()
            state_dir.mkdir(parents=True)
            contract = {
                "approval_status": "approved",
                "grounding": {"model_design": {"data_flow": "x -> model -> y"}},
                "references": {"researcher_owned_logic": {"title": "Reference"}},
                "paper_outline": [{
                    "id": "introduction",
                    "paragraphs": [{
                        "id": "I-P1",
                        "reference_mapping": [{
                            "source_paragraph_id": "REF-I1",
                            "source_text": "Mapped source paragraph.",
                        }],
                    }],
                }],
            }
            plan = reports / "03_EXPERIMENT_PLAN.html"
            plan.write_text(
                '<script id="experiment-plan-contract" type="application/json">'
                + json.dumps(contract)
                + "</script>",
                encoding="utf-8",
            )
            config = {
                "project": {"name": "Keep me"},
                "paths": {"metrics": "paper/metrics.json"},
                "sections": [{
                    "id": "introduction", "title": "Introduction",
                    "paragraphs": [{
                        "id": "I-P1", "purpose": "Frame the problem.",
                        "rhetorical_role": "problem framing",
                        "relation_to_previous": "opening",
                        "relation_to_next": "gap",
                        "reference_paragraph_ids": [],
                    }],
                }],
            }
            state = {
                "sections": {"introduction": {"paragraphs": [{
                    "id": "I-P1", "reference_paragraph_ids": [],
                    "accepted_text": "Existing manuscript paragraph.",
                    "history": [{"text": "Earlier draft."}],
                }]}}
            }
            (paper / "paper_studio.json").write_text(json.dumps(config), encoding="utf-8")
            (paper / "metrics.json").write_text('{"keep": true}', encoding="utf-8")
            (state_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

            summary = repair_reference_context(root, plan)

            repaired_state = json.loads((state_dir / "state.json").read_text())
            repaired_config = json.loads((paper / "paper_studio.json").read_text())
            context = json.loads((paper / "reference_context.json").read_text())
            metrics = json.loads((paper / "metrics.json").read_text())
        paragraph = repaired_state["sections"]["introduction"]["paragraphs"][0]
        self.assertEqual(paragraph["accepted_text"], "Existing manuscript paragraph.")
        self.assertEqual(paragraph["history"], [{"text": "Earlier draft."}])
        self.assertEqual(paragraph["reference_paragraph_ids"], ["REF-I1"])
        self.assertEqual(repaired_config["project"], {"name": "Keep me"})
        self.assertEqual(context["sections"]["introduction"]["mode"], "source")
        self.assertTrue(metrics["keep"])
        self.assertEqual(metrics["model_design"]["data_flow"], "x -> model -> y")
        self.assertTrue(summary["model_design_synced"])
        self.assertFalse(summary["manuscript_reset"])

    def test_reference_repair_is_transactional_when_artifact_refresh_fails(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            reports = root / "reports"
            paper = root / "paper"
            reports.mkdir()
            paper.mkdir()
            contract = {
                "approval_status": "approved",
                "grounding": {"model_design": {"data_flow": "x -> y"}},
                "references": {"researcher_owned_logic": {"title": "Reference"}},
                "paper_outline": [{
                    "id": "introduction",
                    "paragraphs": [{
                        "id": "I-P1",
                        "reference_mapping": [{
                            "source_paragraph_id": "REF-I1",
                            "source_text": "A complete structural paragraph.",
                        }],
                    }],
                }],
            }
            plan = reports / "03_EXPERIMENT_PLAN.html"
            plan.write_text(
                '<script id="experiment-plan-contract" type="application/json">'
                + json.dumps(contract)
                + "</script>",
                encoding="utf-8",
            )
            (reports / "05_EXP_RESULT.html").write_text(
                "<html><body>Executed results</body></html>", encoding="utf-8"
            )
            config_path = paper / "paper_studio.json"
            metrics_path = paper / "metrics.json"
            reference_path = paper / "reference_context.json"
            config_path.write_text(json.dumps({
                "project": {"name": "Existing"},
                "paths": {"metrics": "paper/metrics.json"},
                "sections": [{
                    "id": "introduction", "title": "Introduction",
                    "paragraphs": [{"id": "I-P1", "reference_paragraph_ids": []}],
                }],
            }), encoding="utf-8")
            metrics_path.write_text('{"keep": true}', encoding="utf-8")
            reference_path.write_text('{"keep": true}', encoding="utf-8")
            before = {
                path: path.read_bytes()
                for path in (config_path, metrics_path, reference_path)
            }

            with patch.object(
                initializer,
                "_artifact_definitions",
                side_effect=ValueError("incompatible artifact bindings"),
            ):
                with self.assertRaisesRegex(ValueError, "incompatible artifact"):
                    repair_reference_context(root, plan)

            self.assertEqual(
                {path: path.read_bytes() for path in before},
                before,
            )

    def test_artifact_dependencies_do_not_become_mandatory_citations(self):
        sections = [
            {
                "id": "introduction",
                "source_id": "introduction",
                "title": "Introduction",
                "paragraphs": [
                    {
                        "id": "I-P1",
                        "artifacts": [],
                        "artifact_dependencies": ["F1"],
                    },
                    {
                        "id": "I-P2",
                        "artifacts": ["F1"],
                        "artifact_dependencies": ["F1"],
                    },
                ],
            }
        ]
        contract = {
            "paper_artifacts": [
                {
                    "id": "F1",
                    "section_id": "introduction",
                    "introduced_after": "I-P2",
                }
            ]
        }

        citations, dependencies = artifact_binding_contract(contract, sections)

        self.assertEqual(citations, {"F1": {"introduction": ["I-P2"]}})
        self.assertEqual(
            dependencies, {"F1": {"introduction": ["I-P1", "I-P2"]}}
        )

    def test_cross_section_artifact_citation_is_rejected(self):
        sections = [
            {
                "id": "introduction",
                "source_id": "introduction",
                "title": "Introduction",
                "paragraphs": [{"id": "I-P1", "artifacts": ["F3"]}],
            },
            {
                "id": "method",
                "source_id": "method",
                "title": "Method",
                "paragraphs": [{"id": "M-P1", "artifacts": ["F3"]}],
            },
        ]
        contract = {
            "paper_artifacts": [
                {"id": "F3", "section_id": "method", "introduced_after": "M-P1"}
            ]
        }

        with self.assertRaisesRegex(ValueError, "cited before its owning float"):
            artifact_binding_contract(contract, sections)

    def test_discussion_may_reference_an_existing_experiment_artifact(self):
        sections = [
            {
                "id": "experiments",
                "source_id": "experiments",
                "title": "Experiments",
                "paragraphs": [{"id": "E-P2", "artifacts": ["T1"]}],
            },
            {
                "id": "discussion",
                "source_id": "discussion",
                "title": "Discussion",
                "paragraphs": [{"id": "D-P1", "artifacts": ["T1"]}],
            },
        ]
        contract = {
            "paper_artifacts": [{
                "id": "T1",
                "section_id": "experiments",
                "introduced_after": "E-P2",
            }]
        }

        citations, dependencies = artifact_binding_contract(contract, sections)

        self.assertEqual(
            citations,
            {"T1": {"experiments": ["E-P2"], "discussion": ["D-P1"]}},
        )
        self.assertEqual(dependencies, {"T1": {"experiments": ["E-P2"]}})

    def test_report_input_must_be_html_directly_inside_reports(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            reports = root / "reports"
            reports.mkdir()
            valid = reports / "03_EXPERIMENT_PLAN.html"
            valid.write_text("plan", encoding="utf-8")
            self.assertEqual(require_report_html(root, valid, "plan"), valid.resolve())

            outside = root / "03_EXPERIMENT_PLAN.html"
            outside.write_text("plan", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "directly inside reports"):
                require_report_html(root, outside, "plan")

    def test_selected_idea_is_read_from_idea_report_html(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "02_IDEA_REPORT.html"
            path.write_text(
                '<article data-idea-id="I2" data-default-pick="true">'
                "<h3>I2. Selected report idea</h3></article>",
                encoding="utf-8",
            )
            self.assertEqual(
                selected_idea_from_report(path),
                {"id": "I2", "title": "Selected report idea"},
            )

    def test_selected_idea_accepts_canonical_selected_attribute(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "02_IDEA_REPORT.html"
            path.write_text(
                '<article data-idea-id="I3" data-selected="true">'
                "<h3>I3 · Selected attribute idea</h3></article>",
                encoding="utf-8",
            )
            self.assertEqual(
                selected_idea_from_report(path),
                {"id": "I3", "title": "Selected attribute idea"},
            )

    def test_report_only_contract_requires_one_reference_and_all_five_html_files(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            reports = root / "reports"
            reports.mkdir()
            names = [
                "01_LIT_SURVEY.html",
                "02_IDEA_REPORT.html",
                "03_EXPERIMENT_PLAN.html",
                "04_RUN_PLAN.html",
                "05_EXP_RESULT.html",
            ]
            for name in names:
                (reports / name).write_text("<p>report</p>", encoding="utf-8")
            (reports / "02_IDEA_REPORT.html").write_text(
                '<article data-idea-id="I1" data-default-pick="true">'
                "<h3>I1. Planned idea</h3></article>",
                encoding="utf-8",
            )
            contract = {
                "selected_idea": {"id": "I1", "title": "Planned idea"},
                "downstream_input_policy": {
                    "mode": "REPORT_HTML_ONLY",
                    "files": [f"reports/{name}" for name in names],
                    "external_source_text_allowed": False,
                },
                "references": {
                    "confirmed_at": "2026-08-21",
                    "researcher_owned_logic": {
                        "title": "Reference",
                        "authors": "Researcher",
                        "venue": "Venue",
                        "publication_key": "ref",
                        "url": "https://example.test/ref",
                        "selection_basis": "Argument and experiment structure match.",
                        "experiment_design_alignment": "Setup, main results, and ablation.",
                        "mode": "abstracted",
                    },
                },
            }
            validate_report_only_contract(root, contract)
            contract["references"]["second_reference"] = {
                "title": "Second reference"
            }
            with self.assertRaisesRegex(ValueError, "exactly one"):
                validate_report_only_contract(root, contract)

    def test_legacy_approved_plan_can_initialize_from_the_five_canonical_reports(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            reports = root / "reports"
            reports.mkdir()
            for name in (
                "01_LIT_SURVEY.html",
                "02_IDEA_REPORT.html",
                "03_EXPERIMENT_PLAN.html",
                "04_RUN_PLAN.html",
                "05_EXP_RESULT.html",
            ):
                (reports / name).write_text("<p>report</p>", encoding="utf-8")
            contract = {
                "references": {
                    "researcher_owned_logic": {"title": "Structural Reference"}
                }
            }

            validate_report_only_contract(root, contract)

    def test_appendix_promises_become_headed_deliverable_contracts(self):
        sections = [{
            "id": "ap",
            "title": "Appendices",
            "render": "section",
            "paragraphs": [{
                "id": "AP-A-P1",
                "purpose": "Appendix A will give the complete proof.",
                "rhetorical_role": "Formal details",
                "heading": "",
                "heading_style": "",
            }],
        }]

        materialize_appendix_contracts(sections)

        paragraph = sections[0]["paragraphs"][0]
        self.assertEqual(paragraph["heading"], "Appendix A: Formal Details")
        self.assertEqual(paragraph["heading_style"], "subsection")
        self.assertTrue(paragraph["purpose"].startswith("Materialize this appendix"))

    def test_completed_run_resolves_the_executed_plan_variant(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            reports = root / "reports"
            reports.mkdir()
            plan = reports / "03_EXPERIMENT_PLAN_LOCAL_20MIN.html"
            results = reports / "05_EXP_RESULT.html"
            plan.write_text("plan", encoding="utf-8")
            results.write_text("results", encoding="utf-8")
            state = {
                "state": "completed",
                "source_plan": "reports/03_EXPERIMENT_PLAN_LOCAL_20MIN.html",
                "goals": [{"id": "G1", "status": "completed"}],
            }
            (reports / "04_RUN_PLAN.html").write_text(
                '<script id="run-plan-state" type="application/json">'
                + json.dumps(state)
                + "</script>",
                encoding="utf-8",
            )

            selected_plan, selected_results = completed_run_inputs(root)

        self.assertEqual(selected_plan, plan.resolve())
        self.assertEqual(selected_results, results.resolve())

    def test_completed_run_accepts_current_status_field(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            reports = root / "reports"
            reports.mkdir()
            plan = reports / "03_EXPERIMENT_PLAN.html"
            results = reports / "05_EXP_RESULT.html"
            plan.write_text("plan", encoding="utf-8")
            results.write_text("results", encoding="utf-8")
            state = {
                "status": "completed",
                "goals": [{"id": "G1", "status": "completed"}],
            }
            (reports / "04_RUN_PLAN.html").write_text(
                '<script id="run-plan-state" type="application/json">'
                + json.dumps(state)
                + "</script>",
                encoding="utf-8",
            )

            selected_plan, selected_results = completed_run_inputs(root)

        self.assertEqual(selected_plan, plan.resolve())
        self.assertEqual(selected_results, results.resolve())

    def test_incomplete_run_is_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            reports = root / "reports"
            reports.mkdir()
            (reports / "04_RUN_PLAN.html").write_text(
                '<script id="run-plan-state" type="application/json">'
                + json.dumps({
                    "state": "running",
                    "goals": [{"id": "G1", "status": "running"}],
                })
                + "</script>",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "not fully completed"):
                completed_run_inputs(root)


if __name__ == "__main__":
    unittest.main()
