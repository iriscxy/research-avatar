import importlib.util
import csv
import json
import subprocess
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import paper_studio.server as studio
from tools import paper_checks, validate_ideagen_report


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EXPPLAN = load_module(
    "mengyao_expplan_validator",
    ".agents/skills/expplan/scripts/validate_experiment_plan.py",
)
RUNPLAN = load_module(
    "mengyao_runplan_validator",
    ".agents/skills/runplan/scripts/validate_results_ledger.py",
)
PROVENANCE_RENDERER = load_module(
    "mengyao_result_provenance_renderer",
    ".agents/skills/runplan/scripts/render_result_provenance.py",
)
CONFORMANCE = ROOT / ".agents/skills/paperwrite/scripts/plan_conformance.py"


def write_plan(path: Path, contract: dict) -> None:
    if contract.get("approval_status") == "approved":
        contract["approval_contract_sha256"] = EXPPLAN.contract_digest(contract)
    path.write_text(
        '<script type="application/json" id="experiment-plan-contract">'
        + json.dumps(contract) + "</script>", encoding="utf-8"
    )


def write_profile_fixture(root: Path) -> None:
    profile = root / "researcher-profile"
    profile.mkdir()
    (profile / "PROFILE.md").write_text("# Fixture Researcher\n", encoding="utf-8")
    (profile / "publications.json").write_text(
        json.dumps({"publications": [{"citation_key": "owned2026",
                                      "authors": ["Fixture Researcher"],
                                      "fulltext_path": "owned.txt"}]}), encoding="utf-8"
    )
    (root / "owned.txt").write_text("owned paper", encoding="utf-8")


def minimal_contract() -> dict:
    return {
        "approval_status": "pending",
        "profile_contract": {
            "profile_path": "researcher-profile/PROFILE.md",
            "publications_path": "researcher-profile/publications.json",
            "researcher_identity": "Fixture Researcher",
            "authorship_verified": True,
            "structure_reference_key": "owned2026",
        },
        "generated_at": "2026-08-09",
        "target": {"deadline_status": "upcoming", "confirmed_at": "2026-08-09"},
        "references": {"confirmed_at": "2026-08-09", "researcher_owned_structure": {
            "url": "https://example.org/owned", "local_full_text": "owned.txt",
            "publication_key": "owned2026",
        }},
        "dataset_confirmation": {"confirmed": True, "confirmed_at": "2026-08-09"},
        "grounding": {}, "metric_contract": [], "claims": [],
        "decision_space_contract": [{
            "id": "D1", "experiment_ids": [], "decision_variable": "threshold",
            "disposition": "FIXED_BY_DESIGN", "allowed_values": [0.05],
            "source": "approved design", "selection_rule": "fixed",
            "selection_observable": "not searched", "budget": "0 searches",
            "freeze_point": "approval", "final_value_source": "03",
            "test_access_prohibited": True,
        }],
        "consistency_requirements": {
            "canonical_terms": [], "source_values": ["D1"], "formal_links": [],
        },
        "paper_artifacts": [], "result_requirements": [],
        "paper_outline": [], "baseline_contract": {"selected": [], "unselected": []},
        "repository_contract": {"references": []},
    }


class MengyaoRegressionTests(unittest.TestCase):
    def test_1_differentiable_idea_cannot_be_default_recommendation(self):
        audit = '<script id="idea-novelty-audit" type="application/json">' + json.dumps({
            "candidates": [{
                "idea_id": "I1", "verdict": "differentiable", "absorbable": False,
                "closest_work": "Adaptive stability", "overlap": "active stopping",
                "independent_difference": "matched falsification control",
                "latest_search_date": "2026-08-09",
                "review_context": "fresh", "reviewer_run_id": "review-001",
                "source_urls": ["https://arxiv.org/abs/2601.00001",
                                "https://aclanthology.org/2026.acl-long.1/"],
            }]
        }) + "</script>"
        old = audit + (
            '<article data-idea-id="I1" data-scope-necessity="ESSENTIAL" '
            'data-scope-action="retain" data-novelty-status="differentiable" '
            'data-idea-tier="B" data-default-pick="true"></article>'
        )
        self.assertTrue(any("only a novel Tier A" in error
                            for error in validate_ideagen_report.validate(old)))
        corrected = old.replace('data-default-pick="true"', 'data-default-pick="false"')
        self.assertEqual(validate_ideagen_report.validate(corrected), [])
        disguised = corrected.replace('data-novelty-status="differentiable"',
                                      'data-novelty-status="novel"').replace(
                                          'data-idea-tier="B"', 'data-idea-tier="A"')
        self.assertTrue(any("disagrees with independent audit" in error
                            for error in validate_ideagen_report.validate(disguised)))
        fake_sources = corrected.replace("https://arxiv.org/abs/2601.00001", "https://example.org/a")
        self.assertTrue(any("direct source URLs" in error
                            for error in validate_ideagen_report.validate(fake_sources)))
        invalid_date = corrected.replace('"2026-08-09"', '"not-a-date"')
        self.assertTrue(any("ISO YYYY-MM-DD" in error
                            for error in validate_ideagen_report.validate(invalid_date)))

    def test_2_passed_venue_requires_dated_purpose_bound_override(self):
        with tempfile.TemporaryDirectory() as directory:
            write_profile_fixture(Path(directory))
            plan = Path(directory) / "03.html"
            contract = minimal_contract()
            contract["target"]["deadline_status"] = "passed"
            write_plan(plan, contract)
            self.assertTrue(any("passed venue cycle" in error for error in EXPPLAN.validate(plan)))
            contract["target"]["deadline_override"] = {
                "confirmed": True, "confirmed_at": "2026-08-09",
                "reason": "method feasibility study", "intended_use": "internal feasibility",
            }
            write_plan(plan, contract)
            self.assertFalse(any("deadline_override" in error or "passed venue cycle" in error
                                 for error in EXPPLAN.validate(plan)))
            contract["target"]["deadline_override"] = {
                "confirmed": True, "confirmed_at": "x", "reason": "x", "intended_use": "x"
            }
            write_plan(plan, contract)
            bypass_errors = EXPPLAN.validate(plan)
            self.assertTrue(any("ISO date" in error for error in bypass_errors))
            self.assertTrue(any("intended_use" in error for error in bypass_errors))
            self.assertTrue(any("concrete purpose" in error for error in bypass_errors))
            contract = minimal_contract()
            contract["target"]["deadline_status"] = "passed"
            contract["target"]["deadline_override"] = {
                "confirmed": True, "confirmed_at": "1900-01-01",
                "reason": "prepare a documented next-cycle submission", "intended_use": "next cycle",
            }
            write_plan(plan, contract)
            self.assertTrue(any("must follow venue confirmation" in error
                                for error in EXPPLAN.validate(plan)))
            ordered = minimal_contract()
            ordered["target"]["confirmed_at"] = "2026-08-10"
            write_plan(plan, ordered)
            self.assertTrue(any("must precede" in error for error in EXPPLAN.validate(plan)))

    def test_3_external_paper_cannot_replace_owned_structure_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            write_profile_fixture(Path(directory))
            plan = Path(directory) / "03.html"
            contract = minimal_contract()
            contract.pop("profile_contract")
            contract["references"]["researcher_owned_structure"]["publication_key"] = "external"
            write_plan(plan, contract)
            old_errors = EXPPLAN.validate(plan)
            self.assertTrue(any("profile_contract" in error for error in old_errors))
            self.assertTrue(any("profile-verified publication key" in error for error in old_errors))
            write_plan(plan, minimal_contract())
            new_errors = EXPPLAN.validate(plan)
            self.assertFalse(any("profile_contract" in error or "profile-verified publication key" in error
                                 for error in new_errors))
            fake = minimal_contract()
            fake["profile_contract"]["researcher_identity"] = "Invented Person"
            fake["profile_contract"]["structure_reference_key"] = "invented2026"
            fake["references"]["researcher_owned_structure"]["publication_key"] = "invented2026"
            write_plan(plan, fake)
            fake_errors = EXPPLAN.validate(plan)
            self.assertTrue(any("identity is not present" in error for error in fake_errors))
            self.assertTrue(any("absent from publications" in error for error in fake_errors))
            forged = minimal_contract()
            publications = Path(directory) / "researcher-profile/publications.json"
            publications.write_text(json.dumps({"publications": [{
                "citation_key": "owned2026", "authors": ["Another Author"],
                "fulltext_path": "owned.txt",
            }]}), encoding="utf-8")
            write_plan(plan, forged)
            self.assertTrue(any("not an author" in error for error in EXPPLAN.validate(plan)))

    def test_4_derived_values_recompute_from_persisted_rounded_operands(self):
        spec = {
            "operation": "subtract",
            "operand_locators": ["/targeted_shift", "/control_shift"],
            "rounding": {"stage": "operands_before_operation", "decimals": 4},
        }
        record = {"targeted_shift": 0.12345, "control_shift": 0.12344}
        self.assertEqual(RUNPLAN.recompute_derivation(record, spec), Decimal("0.0001"))
        self.assertNotEqual(Decimal("0.0000"), RUNPLAN.recompute_derivation(record, spec))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = root / "ledger.csv"
            with ledger.open("w", newline="", encoding="utf-8") as handle:
                csv.DictWriter(handle, fieldnames=RUNPLAN.COLUMNS).writeheader()
            state = {"acquisition_contracts": [{
                "id": "A-gap", "artifact_id": "T1", "target_id": "gap",
                "source_type": "RUN_LOCAL", "producing_goal": "G1",
                "atomic_or_aggregate": "aggregate",
            }]}
            plan = root / "04.html"
            plan.write_text(
                '<script type="application/json" id="run-plan-state">'
                + json.dumps(state) + "</script>", encoding="utf-8"
            )
            args = SimpleNamespace(ledger=ledger, plan=plan, report=None,
                                   goal=None, strict_report=False)
            self.assertTrue(any("must be atomic or derived" in error
                                for error in RUNPLAN.validate(args)))
            state["acquisition_contracts"][0].update({
                "atomic_or_aggregate": "derived", "derivation": spec,
            })
            plan.write_text(
                '<script type="application/json" id="run-plan-state">'
                + json.dumps(state) + "</script>", encoding="utf-8"
            )
            self.assertFalse(any("atomic_or_aggregate" in error or "structured derivation" in error
                                 for error in RUNPLAN.validate(args)))

    def test_4b_filled_result_jumps_to_exact_generation_process(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "metrics.json"
            code = root / "run.py"
            raw.write_text('{"score": 0.75}', encoding="utf-8")
            code.write_text("# fixture\n", encoding="utf-8")
            row = {column: "" for column in RUNPLAN.COLUMNS}
            row.update({
                "result_id": "R1", "goal_id": "G1.1", "artifact_id": "T1",
                "target_id": "T1.score", "acquisition_id": "A1",
                "source_type": "RUN_LOCAL", "status": "REAL", "metric": "ASR",
                "value": "0.75", "unit": "%", "dimensions_json": '{"model":"M1"}',
                "raw_artifact": str(raw), "raw_locator": "/score",
                "command": "python run.py", "code_files": str(code),
                "code_revision": "abc123", "obtained_at": "2026-08-09T00:00:00Z",
                "verified_at": "2026-08-09T00:01:00Z",
                "verification_status": "VERIFIED",
            })
            ledger = root / "RESULTS_LEDGER.csv"
            with ledger.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=RUNPLAN.COLUMNS)
                writer.writeheader(); writer.writerow(row)
            state = {"acquisition_contracts": [{
                "id": "A1", "artifact_id": "T1", "target_id": "T1.score",
                "source_type": "RUN_LOCAL", "producing_goal": "G1.1",
                "atomic_or_aggregate": "atomic",
            }]}
            plan = root / "04_RUN_PLAN.html"
            plan.write_text(
                '<script type="application/json" id="run-plan-state">'
                + json.dumps(state) + "</script>", encoding="utf-8"
            )
            report = root / "05_EXP_RESULT.html"
            report.write_text(
                '<html><body><table><tr><td data-target-id="T1.score" '
                'data-result-id="R1">0.75</td></tr></table></body></html>',
                encoding="utf-8",
            )
            self.assertEqual(PROVENANCE_RENDERER.update_report(report, ledger, plan), 1)
            rendered = report.read_text(encoding="utf-8")
            self.assertIn('href="#provenance-R1"', rendered)
            self.assertIn('id="result-provenance-index"', rendered)
            self.assertIn("Command actually run", rendered)
            args = SimpleNamespace(
                ledger=ledger, plan=plan, report=report, goal=None, strict_report=True
            )
            self.assertEqual(RUNPLAN.validate(args), [])

    def test_5_paper_studio_preflight_rejects_missing_paths_and_bad_grid(self):
        config = {
            "schema_version": "1.0", "project": {"id": "fixture", "name": "Fixture"},
            "sections": [{"id": "method", "title": "Method", "file": "method.tex",
                          "result_keys": []}],
            "figure_order": [], "figures": {}, "table_order": ["T1"],
            "tables": {"T1": {
                "title": "Results", "label": "tab:results", "kind": "data",
                "width": "single", "source_sections": ["method"],
                "description": "results", "caption": "Results",
                "data_grid": {"type": "benchmark_rows", "path": "rows",
                              "row_key": "method", "benchmarks": ["D1"],
                              "metrics": "score"},
            }},
            "paths": {"metrics": "results.json"},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "paper_studio.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(studio.ProjectConfigError, "metrics must be a non-empty list"):
                studio.load_project_config(path, root=root)
            config["tables"]["T1"]["data_grid"]["metrics"] = [{"key": "score", "label": "Score"}]
            (root / "results.json").write_text('{"rows": []}', encoding="utf-8")
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(studio.ProjectConfigError, "paths.main is required"):
                studio.load_project_config(path, root=root)
            config["paths"].update({"main": "main.tex", "reference": "reference.txt"})
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(studio.ProjectConfigError, "paths.main does not exist"):
                studio.load_project_config(path, root=root)
            (root / "main.tex").write_text(r"\begin{document}\end{document}", encoding="utf-8")
            (root / "reference.txt").write_text("reference paper", encoding="utf-8")
            self.assertEqual(studio.load_project_config(path, root=root)["project"]["id"], "fixture")
            config["paths"] = {"metrics": "results.json", "main": "results.json",
                               "reference": "results.json"}
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(studio.ProjectConfigError, "must be distinct"):
                studio.load_project_config(path, root=root)
            config["paths"] = {"metrics": "empty.json", "main": "main.tex",
                               "reference": "reference.txt"}
            (root / "empty.json").write_text("{}", encoding="utf-8")
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(studio.ProjectConfigError, "non-empty JSON"):
                studio.load_project_config(path, root=root)
            paragraph_plan = root / "paragraph_plan.json"
            paragraph_plan.write_text(json.dumps({
                "reference_file": "reference.txt",
                "sections": {"method": [{"id": "M1", "reference_lines": [9, 2],
                                            "artifacts": []}]},
            }), encoding="utf-8")
            with (
                patch.object(studio, "EMPTY_PROJECT_MODE", False),
                patch.object(studio, "SECTION_MAP", {"method": {}}),
                patch.object(studio, "FIGURES", {}),
                patch.object(studio, "TABLES", {}),
                patch.object(studio, "PROJECT_CONFIG", {"paths": {"reference": "reference.txt"}}),
                patch.object(studio, "PARAGRAPH_PLAN_FILE", paragraph_plan),
            ):
                with self.assertRaisesRegex(studio.StudioError, "reference_lines"):
                    studio.validate_project_workspace()

    def test_6_modular_latex_is_expanded_before_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sections").mkdir()
            (root / "main.tex").write_text(r"\input{sections/body}", encoding="utf-8")
            (root / "sections/body.tex").write_text(
                r"\section{Evaluation}Visible evidence.\begin{table}\label{tab:x}\end{table}",
                encoding="utf-8",
            )
            expanded = paper_checks.read_tex_tree(root / "main.tex", root=root)
            self.assertIn("Visible evidence", expanded)
            self.assertIn(r"\label{tab:x}", expanded)

    def test_7_cross_artifact_values_terms_formulas_and_claim_citations_are_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            paper = project / "paper"
            (paper / "theory").mkdir(parents=True)
            (project / "results").mkdir()
            (project / "reports").mkdir()
            write_plan(project / "reports" / "03_EXPERIMENT_PLAN.html", {
                "approval_status": "approved",
                "consistency_requirements": {
                    "canonical_terms": ["B2"], "source_values": ["stability-grid"],
                    "formal_links": ["conditional-cost"],
                },
            })
            (project / "results" / "config.json").write_text(
                json.dumps({"thresholds": {"stability": [0.03, 0.05, 0.08]}}), encoding="utf-8"
            )
            (paper / "main.tex").write_text(
                r"\begin{document}\section{Method}Static majority uses thresholds "
                r"$\{0.03,0.05,0.08\}$. The conditional identity is $E[HX]=p_hE[X\mid H=1]$. "
                "Selective prediction supports rejection under insufficient evidence "
                "\\cite{selective}.\n"
                + r"\begin{equation}a=a\end{equation}" * 4
                + r"\appendix\section{Derivations}Proof and derivation.\end{document}",
                encoding="utf-8"
            )
            (paper / "theory" / "verify.py").write_text(
                "import json\nFORMULA = 'E[HX]=p_hE[X|H=1]'\n"
                "print(json.dumps({'checks':[{'id':'conditional-cost','passed':True,"
                "'method':'symbolic','residual':'0'}]}))\n", encoding="utf-8"
            )
            contract = {
                "source_plan": "reports/03_EXPERIMENT_PLAN.html",
                "canonical_terms": [{"id": "B2", "canonical": "Static majority",
                                      "forbidden_aliases": ["Self-consistency"]}],
                "source_values": [{
                    "id": "stability-grid", "source_path": "results/config.json",
                    "source_locator": "/thresholds/stability", "expected_value": [0.03, 0.05, 0.08],
                    "manuscript_evidence": r"$\{0.03,0.05,0.08\}$",
                }],
                "formal_links": [{
                    "id": "conditional-cost",
                    "manuscript_evidence": r"$E[HX]=p_hE[X\mid H=1]$",
                    "verifier_evidence": "E[HX]=p_hE[X|H=1]",
                }],
            }
            (paper / "scientific_consistency.json").write_text(json.dumps(contract), encoding="utf-8")
            args = SimpleNamespace(paper_dir=str(paper), main="main.tex")
            self.assertTrue(paper_checks.check_consistency(args)["ok"])
            self.assertTrue(paper_checks.check_formal(args)["ok"])

            omitted = json.loads(json.dumps(contract))
            omitted["canonical_terms"] = []
            (paper / "scientific_consistency.json").write_text(json.dumps(omitted), encoding="utf-8")
            self.assertTrue(any(item["issue"] == "consistency_coverage_mismatch"
                                for item in paper_checks.check_consistency(args)["violations"]))
            (paper / "scientific_consistency.json").write_text(json.dumps(contract), encoding="utf-8")

            contract["source_values"][0]["expected_value"] = [0.03, 0.05, 0.10]
            (paper / "scientific_consistency.json").write_text(json.dumps(contract), encoding="utf-8")
            self.assertTrue(any(item["issue"] == "source_value_mismatch"
                                for item in paper_checks.check_consistency(args)["violations"]))
            contract["source_values"][0]["expected_value"] = [0.03, 0.05, 0.08]
            (paper / "main.tex").write_text(
                (paper / "main.tex").read_text(encoding="utf-8").replace(
                    "Static majority", "Self-consistency"
                ), encoding="utf-8"
            )
            (paper / "scientific_consistency.json").write_text(json.dumps(contract), encoding="utf-8")
            term_issues = {item["issue"] for item in paper_checks.check_consistency(args)["violations"]}
            self.assertIn("canonical_term_missing", term_issues)
            self.assertIn("forbidden_term_alias", term_issues)
            (paper / "main.tex").write_text(
                (paper / "main.tex").read_text(encoding="utf-8").replace(
                    "Self-consistency", "Static majority"
                ), encoding="utf-8"
            )
            visible_source = (paper / "main.tex").read_text(encoding="utf-8")
            hidden_source = visible_source.replace(
                r"$\{0.03,0.05,0.08\}$", r"$\{0.03,0.05,0.10\}$", 1
            ).replace(
                r"\begin{document}",
                r"\begin{document}\iffalse $\{0.03,0.05,0.08\}$ \fi",
            )
            (paper / "main.tex").write_text(hidden_source, encoding="utf-8")
            self.assertTrue(any(item["issue"] == "source_value_manuscript_evidence_missing"
                                for item in paper_checks.check_consistency(args)["violations"]))
            (paper / "main.tex").write_text(visible_source, encoding="utf-8")
            (paper / "theory" / "verify.py").write_text("raise SystemExit(1)\n", encoding="utf-8")
            self.assertTrue(any(item["issue"] == "mechanical_check_failed"
                                for item in paper_checks.check_formal(args)["violations"]))
            (paper / "theory" / "verify.py").write_text(
                "import json\nFORMULA = 'E[HX]=p_hE[X|H=1]'\n"
                "print(json.dumps({'checks':[{'id':'conditional-cost','passed':True,"
                "'method':'symbolic','residual':'0'}]}))\n", encoding="utf-8"
            )

            (paper / "scholarship_contract.json").write_text(json.dumps({
                "independent_source_audit": {
                    "verdict": "pass", "reviewed_at": "2026-08-09",
                    "metadata_verified": True, "checked_keys": ["selective"],
                    "unsupported_clauses": [],
                },
                "citation_obligations": [{
                    "name": "Selective prediction", "kind": "method", "section": "Method",
                    "citation_key": "selective",
                    "supported_clause": "Selective prediction supports rejection under insufficient evidence",
                    "source_evidence_path": "sources/selective.txt",
                    "source_evidence_excerpt": "supports rejection under insufficient evidence",
                }],
                "setup_entities": [{
                    "name": "Static majority", "kind": "baseline", "section": "Method",
                    "description_evidence": "Static majority uses thresholds",
                    "rationale_evidence": "conditional identity", "claim_ids": ["C1"],
                    "citation_key": "selective",
                }],
            }), encoding="utf-8")
            (project / "sources").mkdir()
            (project / "sources/selective.txt").write_text(
                "Selective prediction supports rejection under insufficient evidence.", encoding="utf-8"
            )
            self.assertTrue(paper_checks.check_scholarship(args)["ok"])
            source = (paper / "main.tex").read_text(encoding="utf-8")
            (paper / "main.tex").write_text(source.replace(
                r"\appendix",
                r"Selective prediction proves exact calibration and compute efficiency.\appendix",
            ), encoding="utf-8")
            self.assertTrue(any(item["issue"] == "named_source_claim_outside_supported_clause"
                                for item in paper_checks.check_scholarship(args)["violations"]))

    def test_8_posthoc_ledger_amendment_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paper = root / "paper"
            results = root / "results"
            paper.mkdir(); results.mkdir()
            contract = {"approval_status": "approved", "paper_artifacts": [{
                "id": "T1", "kind": "table", "label": "tab:projection",
                "placement": "body", "dimensions": ["seed", "proxy", "condition"],
                "visible_dimensions": ["seed", "proxy", "condition"],
                "shell": {"column_labels": ["method", "score"]},
            }], "result_requirements": [{"id": "R1", "any_of": ["rows"]}]}
            plan = root / "03.html"
            write_plan(plan, contract)
            (paper / "main.tex").write_text(
                r"\begin{document}\begin{table}method score condition\label{tab:projection}\end{table}"
                r"\end{document}", encoding="utf-8"
            )
            (paper / "paper_studio.json").write_text(json.dumps({
                "figures": {}, "tables": {"T1": {"data_grid": {
                    "type": "records", "path": "rows", "columns": [
                        {"key": "method", "label": "method"},
                        {"key": "score", "label": "score"},
                    ]
                }}},
            }), encoding="utf-8")
            (results / "bundle.json").write_text(json.dumps({"rows": []}), encoding="utf-8")
            waiver = paper / "SEMANTIC_WAIVER.md"
            waiver.write_text("waive dimensions", encoding="utf-8")
            process = subprocess.run(
                ["python3", str(CONFORMANCE), "--plan", str(plan), "--paper-dir", str(paper),
                 "--results-dir", str(results)], text=True, capture_output=True, check=False,
            )
            report = json.loads(process.stdout)
            self.assertEqual(process.returncode, 1)
            self.assertIn("posthoc_artifact_amendment_forbidden",
                          {item["issue"] for item in report["violations"]})
            self.assertIn("planned_artifact_dimensions_not_visible",
                          {item["issue"] for item in report["violations"]})
            waiver.unlink()
            (paper / "main.tex").write_text(
                r"\begin{document}\begin{table}method score seed proxy condition"
                r"\label{tab:projection}\end{table}\end{document}", encoding="utf-8"
            )
            corrected = subprocess.run(
                ["python3", str(CONFORMANCE), "--plan", str(plan), "--paper-dir", str(paper),
                 "--results-dir", str(results)], text=True, capture_output=True, check=False,
            )
            self.assertEqual(corrected.returncode, 0, corrected.stdout)
            tampered = json.loads(json.dumps(contract))
            tampered["paper_artifacts"][0]["visible_dimensions"] = ["condition"]
            plan.write_text('<script type="application/json" id="experiment-plan-contract">'
                            + json.dumps(tampered) + '</script>', encoding="utf-8")
            digest_check = subprocess.run(
                ["python3", str(CONFORMANCE), "--plan", str(plan), "--paper-dir", str(paper),
                 "--results-dir", str(results)], text=True, capture_output=True, check=False,
            )
            self.assertIn("approved_contract_digest_mismatch",
                          {item["issue"] for item in json.loads(digest_check.stdout)["violations"]})
            write_plan(plan, contract)
            (paper / "main.tex").write_text(
                "\\begin{document}\\begin{table}method score\n% seed proxy condition\n"
                "\\label{tab:projection}\\end{table}\\end{document}", encoding="utf-8"
            )
            hidden = subprocess.run(
                ["python3", str(CONFORMANCE), "--plan", str(plan), "--paper-dir", str(paper),
                 "--results-dir", str(results)], text=True, capture_output=True, check=False,
            )
            hidden_report = json.loads(hidden.stdout)
            self.assertIn("planned_artifact_dimensions_not_visible",
                          {item["issue"] for item in hidden_report["violations"]})


if __name__ == "__main__":
    unittest.main()
