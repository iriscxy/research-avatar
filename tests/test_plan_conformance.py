import json
import importlib.util
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


SCRIPT = Path("research_avatar/tools/plan_conformance.py").resolve()
SPEC = importlib.util.spec_from_file_location("plan_conformance_fixture", SCRIPT)
CONFORMANCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONFORMANCE)


class PlanConformanceTests(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[Path, Path, Path]:
        contract = {
            "approval_status": "approved",
            "paper_artifacts": [
                {
                    "id": "F1",
                    "kind": "figure",
                    "label": "fig:one",
                    "placement": "body",
                    "shell": {"plotting": {"panels": {"left": {}, "right": {}}}},
                },
                {
                    "id": "T1",
                    "kind": "table",
                    "label": "tab:one",
                    "placement": "body",
                    "shell": {"column_labels": ["method", "score"]},
                },
            ],
            "result_requirements": [],
        }
        contract["approval_contract_sha256"] = CONFORMANCE.contract_digest(contract)
        plan = root / "plan.html"
        plan.write_text(
            '<script type="application/json" id="experiment-plan-contract">'
            + json.dumps(contract)
            + "</script>",
            encoding="utf-8",
        )
        paper = root / "paper"
        paper.mkdir()
        (paper / "main.tex").write_text(
            r"\begin{figure}\label{fig:one}\end{figure}"
            r"\begin{table}\label{tab:one}\end{table}",
            encoding="utf-8",
        )
        config = {
            "figures": {"F1": {"panels": [{"id": "left"}, {"id": "right"}]}},
            "tables": {
                "T1": {
                    "data_grid": {
                        "type": "records",
                        "path": "rows",
                        "columns": [
                            {"key": "method", "label": "Method"},
                            {"key": "score", "label": "Score"},
                        ],
                    }
                }
            },
        }
        (paper / "paper_studio.json").write_text(json.dumps(config), encoding="utf-8")
        results = root / "results"
        results.mkdir()
        return plan, paper, results

    def run_check(self, plan: Path, paper: Path, results: Path) -> tuple[int, dict]:
        process = subprocess.run(
            [
                "python3", str(SCRIPT), "--plan", str(plan), "--paper-dir", str(paper),
                "--results-dir", str(results),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        return process.returncode, json.loads(process.stdout)

    def test_exact_artifact_dimensions_pass(self):
        with TemporaryDirectory() as directory:
            plan, paper, results = self.fixture(Path(directory))
            code, report = self.run_check(plan, paper, results)
            self.assertEqual(code, 0, report)
            self.assertTrue(report["ok"])

    def test_panel_dimension_drift_fails(self):
        with TemporaryDirectory() as directory:
            plan, paper, results = self.fixture(Path(directory))
            config = json.loads((paper / "paper_studio.json").read_text())
            config["figures"]["F1"]["panels"] = [{"id": "a"}, {"id": "b"}]
            (paper / "paper_studio.json").write_text(json.dumps(config))
            code, report = self.run_check(plan, paper, results)
            self.assertEqual(code, 1)
            self.assertIn(
                "artifact_panel_dimension_mismatch",
                {item["issue"] for item in report["violations"]},
            )

    def test_table_metric_columns_may_exclude_the_leading_row_identifier(self):
        with TemporaryDirectory() as directory:
            plan, paper, results = self.fixture(Path(directory))
            prefix = '<script type="application/json" id="experiment-plan-contract">'
            contract = json.loads(plan.read_text().removeprefix(prefix).removesuffix("</script>"))
            contract["paper_artifacts"][1]["shell"]["column_labels"] = ["score"]
            contract["approval_contract_sha256"] = CONFORMANCE.contract_digest(contract)
            plan.write_text(prefix + json.dumps(contract) + "</script>")
            code, report = self.run_check(plan, paper, results)
            self.assertEqual(code, 0, report)

    def test_figure_visible_dimensions_are_verified_from_render_config(self):
        with TemporaryDirectory() as directory:
            plan, paper, results = self.fixture(Path(directory))
            prefix = '<script type="application/json" id="experiment-plan-contract">'
            contract = json.loads(plan.read_text().removeprefix(prefix).removesuffix("</script>"))
            contract["paper_artifacts"][0]["dimensions"] = ["budget", "accuracy"]
            contract["paper_artifacts"][0]["visible_dimensions"] = ["budget", "accuracy"]
            contract["approval_contract_sha256"] = CONFORMANCE.contract_digest(contract)
            plan.write_text(prefix + json.dumps(contract) + "</script>")
            config = json.loads((paper / "paper_studio.json").read_text())
            config["figures"]["F1"]["visible_dimensions"] = ["budget", "accuracy"]
            (paper / "paper_studio.json").write_text(json.dumps(config))
            code, report = self.run_check(plan, paper, results)
            self.assertEqual(code, 0, report)

    def test_posthoc_amendment_fails(self):
        with TemporaryDirectory() as directory:
            plan, paper, results = self.fixture(Path(directory))
            (paper / "ARTIFACT_LEDGER_AMENDMENT.md").write_text("waive it")
            code, report = self.run_check(plan, paper, results)
            self.assertEqual(code, 1)
            self.assertIn(
                "posthoc_artifact_amendment_forbidden",
                {item["issue"] for item in report["violations"]},
            )

    def set_result_requirement(self, plan: Path, requirement: dict) -> None:
        text = plan.read_text(encoding="utf-8")
        prefix = '<script type="application/json" id="experiment-plan-contract">'
        payload = json.loads(text.removeprefix(prefix).removesuffix("</script>"))
        payload["result_requirements"] = [requirement]
        payload["approval_contract_sha256"] = CONFORMANCE.contract_digest(payload)
        plan.write_text(prefix + json.dumps(payload) + "</script>", encoding="utf-8")

    def test_null_or_empty_result_fails(self):
        for empty_value in (None, [], {}, ""):
            with self.subTest(empty_value=empty_value), TemporaryDirectory() as directory:
                plan, paper, results = self.fixture(Path(directory))
                self.set_result_requirement(plan, {"id": "R1", "any_of": ["result.cells"]})
                (results / "main.json").write_text(json.dumps({"result": {"cells": empty_value}}))
                code, report = self.run_check(plan, paper, results)
                self.assertEqual(code, 1)
                self.assertIn("empty_value", report["result_checks"][0]["rejected"][0]["errors"])

    def test_explicit_result_file_cannot_be_replaced_by_index(self):
        with TemporaryDirectory() as directory:
            plan, paper, results = self.fixture(Path(directory))
            self.set_result_requirement(
                plan,
                {"id": "R1", "any_of": ["results/main_temporal.json:records.*"]},
            )
            (results / "contract_index.json").write_text(json.dumps({"records": [{"score": 1.0}]}))
            code, report = self.run_check(plan, paper, results)
            self.assertEqual(code, 1)
            self.assertEqual(report["result_checks"][0]["matches"], [])

    def test_explicit_result_file_with_schema_passes(self):
        with TemporaryDirectory() as directory:
            plan, paper, results = self.fixture(Path(directory))
            self.set_result_requirement(
                plan,
                {
                    "id": "R1",
                    "any_of": ["results/main_temporal.json:records.*"],
                    "expected_type": "object",
                    "min_items": 2,
                    "required_fields": ["score", "unit"],
                    "unit": "%",
                },
            )
            (results / "main_temporal.json").write_text(json.dumps({
                "records": [
                    {"score": 1.0, "unit": "%"},
                    {"score": 2.0, "unit": "%"},
                ]
            }))
            code, report = self.run_check(plan, paper, results)
            self.assertEqual(code, 0, report)
            self.assertTrue(report["result_checks"][0]["ok"])


if __name__ == "__main__":
    unittest.main()
