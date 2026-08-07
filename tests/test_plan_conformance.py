import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


SCRIPT = Path(".agents/skills/paperwrite/scripts/plan_conformance.py").resolve()


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


if __name__ == "__main__":
    unittest.main()
